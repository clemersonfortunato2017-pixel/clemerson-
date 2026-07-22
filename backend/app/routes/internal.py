"""Rotas máquina-a-máquina para a rotina agendada da esteira automática
(anuncio-ml-autopecas rodando sem humano no chat). Protegidas por uma chave
de serviço fixa (INTERNAL_SERVICE_KEY no .env) — não é login de usuário.

A rotina faz a identificação/pesquisa/geração de anúncio (raciocínio + WebSearch,
não dá pra ser só Python) e chama estas rotas pra: buscar o token ML sempre
fresco, gravar cada etapa no pipeline_log, validar antes de publicar, e
registrar o resultado final (publicado ou erro) — sem nunca parar pra
confirmação humana, conforme decisão do usuário."""

from datetime import datetime, timezone
from typing import Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.config import settings
from app.models.part import Part, Compatibility, MarketplaceListing
from app.services.ml_importer import get_valid_access_token, _get_or_create_vehicle

router = APIRouter(prefix="/internal", tags=["internal"])


def require_service_key(x_service_key: str = Header(default="")):
    if not settings.internal_service_key or x_service_key != settings.internal_service_key:
        raise HTTPException(status_code=401, detail="Chave de serviço inválida ou ausente")


@router.get("/parts/pending", dependencies=[Depends(require_service_key)])
def list_pending_parts(db: Session = Depends(get_db)):
    """Peças com foto já otimizada aguardando a esteira (status=draft) — é
    o que a rotina agendada consulta a cada execução pra saber se tem
    trabalho novo. draft = otimização de foto concluída (ver Passo A2);
    processing = upload ainda sendo processado, não pegar ainda."""
    parts = (
        db.query(Part)
        .filter(Part.status == "draft", Part.active == True)
        .order_by(Part.created_at.asc())
        .all()
    )
    return [
        {"id": p.id, "title": p.title, "photos": p.photos, "created_at": p.created_at}
        for p in parts
    ]


@router.post("/parts/{part_id}/reprocess", dependencies=[Depends(require_service_key)])
def reprocess_stuck_part(part_id: int, db: Session = Depends(get_db)):
    """Recupera peça travada em status=processing (ex: deploy do backend
    reiniciou o servidor no meio da otimização de foto). As fotos originais
    continuam no volume persistente — só reprocessa a partir delas."""
    from pathlib import Path
    from app.routes.parts import _process_photos

    part = db.query(Part).filter(Part.id == part_id).first()
    if not part:
        raise HTTPException(status_code=404, detail="Peça não encontrada")

    originais_dir = Path(settings.uploads_dir) / str(part_id) / "originais"
    if not originais_dir.exists():
        raise HTTPException(status_code=404, detail=f"Sem fotos originais salvas em {originais_dir}")

    originais_paths = [str(p) for p in sorted(originais_dir.iterdir()) if p.is_file()]
    if not originais_paths:
        raise HTTPException(status_code=404, detail="Pasta de originais vazia")

    _process_photos(part, originais_paths, db)
    return {"id": part.id, "status": part.status, "photos": part.photos}


@router.post("/parts/{part_id}/rebuild-photos", dependencies=[Depends(require_service_key)])
async def rebuild_photos(
    part_id: int, brand: str, model: str, year: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Reprocessa as fotos originais de uma peça já publicada (mesmo pipeline
    de otimização/remoção de fundo de hoje, já com a correção do bug do
    bbox — ver image_processor.py) e monta a foto de capa (veículo + peça,
    Passo 1B do skill). Depois empurra as fotos novas pros anúncios ML já
    ativos dessa peça (PUT /items/{id} com pictures por URL — o ML busca a
    imagem sozinho, não precisa pré-upload). Usado pra corrigir peças
    publicadas antes da correção do bug de remoção de fundo (2026-07-21),
    sem precisar tirar fotos novas nem republicar do zero."""
    import httpx
    from pathlib import Path
    from app.routes.parts import _process_photos
    from app.services.vehicle_photo import montar_capa
    from app.services.platform_registry import resolve_account_for_listing

    part = db.query(Part).filter(Part.id == part_id).first()
    if not part:
        raise HTTPException(404, "Peça não encontrada")

    originais_dir = Path(settings.uploads_dir) / str(part_id) / "originais"
    originais_paths = [str(p) for p in sorted(originais_dir.iterdir()) if p.is_file()] if originais_dir.exists() else []
    if not originais_paths:
        raise HTTPException(404, f"Sem fotos originais salvas em {originais_dir}")

    _process_photos(part, originais_paths, db)
    db.refresh(part)

    capa_url = None
    async with httpx.AsyncClient() as client:
        try:
            capa_url = await montar_capa(client, db, part_id, brand, model, year, part.photos[0])
        except Exception as e:
            _log(part, "rebuild_capa", f"erro: {e}")
    if capa_url:
        part.photos = [capa_url] + list(part.photos)
    _log(part, "rebuild_fotos", {"fotos": len(part.photos), "capa": bool(capa_url)})
    db.commit()

    listings = db.query(MarketplaceListing).filter(
        MarketplaceListing.part_id == part_id,
        MarketplaceListing.marketplace == "mercadolivre",
        MarketplaceListing.status == "active",
    ).all()

    resultados = []
    pictures = [{"source": url} for url in part.photos[:12]]
    async with httpx.AsyncClient(timeout=30) as client:
        for listing in listings:
            account = await resolve_account_for_listing(listing, db)
            if not account or not account.get("access_token"):
                resultados.append({"listing_id": listing.listing_id, "erro": "conta não resolvida"})
                continue
            headers = {"Authorization": f"Bearer {account['access_token']}", "Content-Type": "application/json"}
            r = await client.put(
                f"https://api.mercadolibre.com/items/{listing.listing_id}",
                headers=headers, json={"pictures": pictures},
            )
            resultados.append({"listing_id": listing.listing_id, "status_code": r.status_code,
                                "ok": r.status_code == 200})
    _log(part, "rebuild_push_ml", resultados)
    db.commit()

    return {"part_id": part_id, "photos": part.photos, "capa": capa_url, "listings_atualizados": resultados}


@router.get("/ml-token", dependencies=[Depends(require_service_key)])
async def get_ml_token(db: Session = Depends(get_db)):
    """Token ML sempre fresco (renova via refresh_token se preciso) — usado pela
    rotina agendada pra publicar anúncios sem depender do HD externo F:."""
    user_id, access_token = await get_valid_access_token(db)
    if not access_token:
        raise HTTPException(status_code=503, detail="Credenciais do Mercado Livre não configuradas")
    return {"user_id": user_id, "access_token": access_token}


class PartIdentification(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    condition: Optional[str] = None
    code_oem: Optional[str] = None
    code_manufacturer: Optional[str] = None
    weight: Optional[float] = None
    sale_price: Optional[float] = None
    quantity: Optional[int] = None
    description: Optional[str] = None


class LogEntry(BaseModel):
    step: str
    detail: Any = None


class CompatibilityItem(BaseModel):
    brand: str
    model: str
    year_start: Optional[int] = None
    year_end: Optional[int] = None
    engine: Optional[str] = None
    oem_code: Optional[str] = None


class PublishResult(BaseModel):
    listing_id: str
    url: str = ""
    price: float
    marketplace: str = "mercadolivre"


class ErrorResult(BaseModel):
    reason: str
    step: str = "publicacao"


def _get_part_or_404(part_id: int, db: Session) -> Part:
    part = db.query(Part).filter(Part.id == part_id).first()
    if not part:
        raise HTTPException(status_code=404, detail="Peça não encontrada")
    return part


def _log(part: Part, step: str, detail=None):
    log = list(part.pipeline_log or [])
    log.append({"step": step, "detail": detail, "at": datetime.now(timezone.utc).isoformat()})
    part.pipeline_log = log


@router.put("/parts/{part_id}", dependencies=[Depends(require_service_key)])
def update_identification(part_id: int, data: PartIdentification, db: Session = Depends(get_db)):
    """Rotina grava aqui o resultado da identificação (nome, OEM, categoria,
    condição, preço decidido pela pesquisa de concorrentes)."""
    part = _get_part_or_404(part_id, db)
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(part, k, v)
    _log(part, "identificacao", data.model_dump(exclude_none=True))
    db.commit()
    return {"ok": True}


@router.post("/parts/{part_id}/compatibility", dependencies=[Depends(require_service_key)])
def add_compatibility(part_id: int, items: list[CompatibilityItem], db: Session = Depends(get_db)):
    """Grava o resultado da pesquisa de compatibilidade de veículo/OEM feita
    pela rotina — é o que a validação de publicação exige antes de deixar
    publicar (compatibilidade vazia é o padrão que já causou mediação perdida)."""
    part = _get_part_or_404(part_id, db)
    added = 0
    for item in items:
        vehicle = _get_or_create_vehicle(
            db, item.brand.title(), item.model.title(), item.year_start, item.year_end, item.engine
        )
        db.add(Compatibility(part_id=part.id, vehicle_id=vehicle.id, oem_code=item.oem_code))
        added += 1
    _log(part, "compatibilidade", [i.model_dump() for i in items])
    db.commit()
    return {"added": added}


@router.post("/parts/{part_id}/log", dependencies=[Depends(require_service_key)])
def append_log(part_id: int, entry: LogEntry, db: Session = Depends(get_db)):
    """Registra uma etapa intermediária (pesquisa de compatibilidade, 5
    concorrentes, decisão de preço, geração de título/descrição) — vira a base
    do relatório diário e da auditoria de qualquer anúncio publicado sozinho."""
    part = _get_part_or_404(part_id, db)
    _log(part, entry.step, entry.detail)
    db.commit()
    return {"ok": True}


@router.get("/parts/{part_id}/validate", dependencies=[Depends(require_service_key)])
def validate_before_publish(part_id: int, db: Session = Depends(get_db)):
    """Regras determinísticas que barram publicação automática — não é
    pergunta ao usuário, é recusa dura com motivo logado (Passo A3.3 do plano).
    A rotina deve chamar isso antes de publicar e não seguir se ok=false."""
    part = _get_part_or_404(part_id, db)
    reasons = []

    if not part.title or part.title == "Peça aguardando identificação":
        reasons.append("peça sem identificação (título não definido)")
    if not part.photos:
        reasons.append("sem foto otimizada")
    if not part.compatibilities:
        reasons.append("compatibilidade vazia (risco de mediação por veículo errado)")
    if part.category and "direcao" in (part.category or "").lower() and part.condition != "new":
        reasons.append("categoria de direção só aceita condition=new no ML")
    if not part.sale_price or part.sale_price <= 0:
        reasons.append("sem preço definido")
    if part.cost_price and part.sale_price and part.sale_price < part.cost_price:
        reasons.append(f"preço de venda (R${part.sale_price}) abaixo do custo (R${part.cost_price})")

    ok = len(reasons) == 0
    if not ok:
        _log(part, "validacao_falhou", reasons)
        db.commit()
    return {"ok": ok, "reasons": reasons}


@router.post("/parts/{part_id}/mark-published", dependencies=[Depends(require_service_key)])
async def mark_published(part_id: int, data: PublishResult, db: Session = Depends(get_db)):
    """A rotina agendada chama isso depois de publicar a peça na conta ML
    principal (única publicação que exige raciocínio: título, categoria,
    preço pesquisado). A partir daqui é mecânico — o Pitbox assume e
    republica automaticamente em TODAS as outras contas/plataformas
    conectadas (ML pessoa física, Shopee PJ, etc), sem precisar a rotina
    saber nada de cada plataforma."""
    part = _get_part_or_404(part_id, db)
    listing = MarketplaceListing(
        part_id=part.id,
        marketplace=data.marketplace,
        listing_id=data.listing_id,
        url=data.url,
        status="active",
        price=data.price,
        platform_account_id=None,  # conta ML principal/legada
    )
    db.add(listing)
    part.status = "published"
    part.sale_price = data.price
    _log(part, "publicado", {"listing_id": data.listing_id, "url": data.url, "price": data.price})
    db.commit()

    from app.services.platform_registry import publish_to_all_accounts
    fanout = await publish_to_all_accounts(part.id, db)
    _log(part, "fanout_multiconta", fanout)
    db.commit()

    return {"ok": True, "fanout": fanout}


@router.post("/parts/{part_id}/mark-error", dependencies=[Depends(require_service_key)])
def mark_error(part_id: int, data: ErrorResult, db: Session = Depends(get_db)):
    part = _get_part_or_404(part_id, db)
    part.status = "error"
    _log(part, data.step, {"erro": data.reason})
    db.commit()
    return {"ok": True}
