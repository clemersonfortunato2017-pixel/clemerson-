from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.part import Part, MarketplaceListing, StockMovement, Compatibility
from app.services.platform_registry import (
    close_on_all_accounts, publish_to_all_accounts, get_platforms_status,
    _ml_legacy_account, _fetch_ml_item_detail, MercadoLivrePlatform,
)
from app.services.cross_platform_sync import retry_listing_sync
from app.routes.auth import get_current_user

router = APIRouter(prefix="/platforms", tags=["platforms"], dependencies=[Depends(get_current_user)])


class PublishWithReference(BaseModel):
    reference_listing_id: str
    family_name_override: Optional[str] = None


def _require_publish_ready(part: Part, db: Session) -> None:
    """Regra dura sem exceção (Clemerson, 2026-07-22): nenhum anúncio pode
    ir pro ar sem descrição preenchida e sem pelo menos uma compatibilidade
    de veículo registrada. Bloqueia bem aqui, no ponto que efetivamente cria
    o anúncio no ML — não só no status 'ready_to_publish' da esteira, que
    pode ser contornado publicando direto com publish-with-reference.
    Motivo real: auditoria de 2026-07-22 encontrou anúncios publicados sem
    nenhuma descrição, porque o código antigo só tentava enviar a descrição
    SE ela existisse, sem nunca exigir que existisse antes de publicar."""
    if not (part.description or "").strip():
        raise HTTPException(400, "Peça sem descrição preenchida — não pode publicar (regra sem exceção, 2026-07-22)")
    tem_compat = db.query(Compatibility).filter_by(part_id=part.id).first()
    if not tem_compat:
        raise HTTPException(400, "Peça sem nenhuma compatibilidade de veículo registrada — não pode publicar (regra sem exceção, 2026-07-22)")


@router.post("/parts/{part_id}/publish-with-reference")
async def publish_with_reference(part_id: int, data: PublishWithReference, db: Session = Depends(get_db)):
    """Publica uma peça NUNCA anunciada usando outro anúncio ML já ativo (de
    peça parecida, não necessariamente a mesma) como referência de categoria/
    atributos — pra quando a esteira automática identifica uma peça igual a
    algo que já vendemos, mas essa unidade física em si nunca foi publicada
    (então `publish_to_all_accounts` não tem nenhum listing próprio pra
    montar `reference` sozinho). Usa sempre as FOTOS da peça nova (nunca as
    da referência).

    `family_name_override`: quando a peça referência é de marca/modelo
    diferente (mesma categoria de produto, veículo diferente), o family_name
    da referência vem com o nome do OUTRO veículo — passar aqui o family_name
    certo pra essa peça (senão o título/família do anúncio sai com o carro
    errado, mesmo com os atributos BRAND/PART_NUMBER corretos)."""
    part = db.query(Part).filter(Part.id == part_id).first()
    if not part:
        raise HTTPException(404, "Peça não encontrada")
    _require_publish_ready(part, db)

    reference = await _fetch_ml_item_detail(data.reference_listing_id, db)
    if not reference:
        raise HTTPException(404, "Anúncio de referência não encontrado no ML")
    reference["pictures"] = []  # força usar as fotos da própria peça nova
    if data.family_name_override:
        reference["family_name"] = data.family_name_override

    account = await _ml_legacy_account(db)
    if not account:
        raise HTTPException(400, "Conta ML principal não conectada")

    result = await MercadoLivrePlatform().publish(part, account, reference=reference)
    if "listing_id" not in result:
        raise HTTPException(400, f"ML recusou: {result.get('error')}")

    listing = MarketplaceListing(
        part_id=part.id, marketplace="mercadolivre", listing_id=result["listing_id"],
        url=result.get("url", ""), status="active", price=part.sale_price,
    )
    db.add(listing)
    db.commit()

    fanout = await publish_to_all_accounts(part_id, db)
    return {"primary": result, "fanout": fanout}


@router.post("/parts/{part_id}/publish-ready")
async def publish_ready(part_id: int, db: Session = Depends(get_db)):
    """O botão de '1 clique' da esteira automática: a peça já foi
    identificada e teve preço pesquisado sozinha (status='ready_to_publish',
    ver auto_listing.py) — aqui só lê o reference_listing_id/family_name já
    decididos e efetivamente publica. Esta é a ÚNICA etapa que cria o
    anúncio de verdade no ML, e por isso sempre precisa desse clique humano
    (decisão do Clemerson em 2026-07-20: identificação/preço podem rodar
    sozinhos, publicar não)."""
    part = db.query(Part).filter(Part.id == part_id).first()
    if not part:
        raise HTTPException(404, "Peça não encontrada")
    if part.status != "ready_to_publish":
        raise HTTPException(400, f"Peça não está pronta pra publicar (status atual: {part.status})")
    _require_publish_ready(part, db)

    prep = next((s["detail"] for s in reversed(part.pipeline_log or []) if s.get("step") == "pronto_pra_publicar"), None)
    if not prep or not prep.get("reference_listing_id"):
        raise HTTPException(400, "Peça não tem referência de categoria preparada")

    reference = await _fetch_ml_item_detail(prep["reference_listing_id"], db)
    if not reference:
        raise HTTPException(404, "Anúncio de referência não encontrado no ML")
    reference["pictures"] = []
    if prep.get("family_name_override"):
        reference["family_name"] = prep["family_name_override"]

    account = await _ml_legacy_account(db)
    if not account:
        raise HTTPException(400, "Conta ML principal não conectada")

    result = await MercadoLivrePlatform().publish(part, account, reference=reference)
    if "listing_id" not in result:
        raise HTTPException(400, f"ML recusou: {result.get('error')}")

    listing = MarketplaceListing(
        part_id=part.id, marketplace="mercadolivre", listing_id=result["listing_id"],
        url=result.get("url", ""), status="active", price=part.sale_price,
    )
    db.add(listing)
    part.status = "published"
    db.commit()

    fanout = await publish_to_all_accounts(part_id, db)
    return {"primary": result, "fanout": fanout}


@router.get("/status")
async def platforms_status(db: Session = Depends(get_db)):
    """Lista todas as plataformas, quantas contas ativas cada uma tem
    (multi-conta: ML pode ter 2+, Shopee pode ter 1+) e o rótulo de cada."""
    return await get_platforms_status(db)


@router.post("/parts/{part_id}/publish-all")
async def publish_to_all(part_id: int, db: Session = Depends(get_db)):
    """Publica a peça em todas as contas conectadas (todas as plataformas,
    todas as contas de cada uma) onde ela ainda não está."""
    result = await publish_to_all_accounts(part_id, db)
    return result


@router.post("/parts/{part_id}/sold-balcao")
async def sold_at_counter(part_id: int, db: Session = Depends(get_db)):
    """
    Marca peça como vendida no balcão:
    - Zera estoque
    - Fecha anúncio em TODAS as contas/plataformas
    - Registra movimento de saída
    """
    part = db.query(Part).filter(Part.id == part_id).first()
    if not part:
        return {"error": "Peça não encontrada"}

    platform_results = await close_on_all_accounts(part_id, db)

    qty_sold = part.quantity
    movement = StockMovement(
        part_id=part_id,
        type="out",
        quantity=qty_sold,
        reason="Venda no balcão — baixado de todas as plataformas",
    )
    db.add(movement)
    part.quantity = 0
    part.active = False
    db.commit()

    return {
        "part_id": part_id,
        "qty_removed": qty_sold,
        "platforms": platform_results,
    }


@router.post("/parts/{part_id}/close-all")
async def close_all(part_id: int, db: Session = Depends(get_db)):
    """Fecha os anúncios ativos da peça em todas as contas/plataformas SEM
    zerar estoque nem marcar a peça inativa — usado pra desfazer uma
    publicação errada (ex: título/atributo saiu errado) antes de corrigir e
    publicar de novo, sem perder a peça do estoque no processo."""
    return await close_on_all_accounts(part_id, db)


@router.post("/parts/{part_id}/reactivate")
async def reactivate_part(part_id: int, db: Session = Depends(get_db)):
    """Reativa peça e republica em todas as contas conectadas."""
    part = db.query(Part).filter(Part.id == part_id).first()
    if not part:
        return {"error": "Peça não encontrada"}
    part.active = True
    db.commit()
    result = await publish_to_all_accounts(part_id, db)
    return result


@router.get("/sync-failures")
def sync_failures(db: Session = Depends(get_db)):
    """Anúncios cuja baixa de estoque automática (depois de venda em outra
    conta/plataforma) esgotou as tentativas — precisa de atenção manual,
    porque a peça pode estar vendável em mais de um lugar ao mesmo tempo."""
    listings = db.query(MarketplaceListing).filter(MarketplaceListing.sync_failed == True).all()  # noqa: E712
    result = []
    for l in listings:
        part = db.query(Part).filter(Part.id == l.part_id).first()
        result.append({
            "listing_id": l.id,
            "part_id": l.part_id,
            "part_title": part.title if part else None,
            "marketplace": l.marketplace,
            "marketplace_listing_id": l.listing_id,
            "status": l.status,
        })
    return result


@router.post("/sync-failures/{listing_id}/retry")
async def retry_sync_failure(listing_id: int, db: Session = Depends(get_db)):
    return await retry_listing_sync(listing_id, db)
