import httpx
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db, SessionLocal
from app.models.part import Part, MarketplaceListing
from app.services.ml_importer import import_from_ml, sync_all_compatibility, get_valid_access_token, push_part_compatibility_to_ml
from app.services.title_compat_parser import sync_compat_from_titles
from app.services.auto_listing import prepare_part
from app.routes.auth import get_current_user

router = APIRouter(prefix="/import", tags=["import"], dependencies=[Depends(get_current_user)])

# Estado simples do job de sync em memória
sync_state = {"running": False, "processed": 0, "added": 0, "done": False, "error": None}
push_compat_state = {"running": False, "processed": 0, "pushed": 0, "skipped": 0, "errors": [], "done": False}
prepare_state = {"running": False, "processed": 0, "ready": 0, "needs_review": 0, "done": True}


async def _run_sync():
    sync_state.update({"running": True, "processed": 0, "added": 0, "done": False, "error": None})
    db = SessionLocal()
    try:
        result = await sync_all_compatibility(db)
        sync_state.update({"running": False, "done": True, "processed": result.get("processed", 0), "added": result.get("compatibilities_added", 0)})
    except Exception as e:
        sync_state.update({"running": False, "done": True, "error": str(e)})
    finally:
        db.close()


@router.post("/mercadolivre")
async def import_mercadolivre(db: Session = Depends(get_db)):
    result = await import_from_ml(db)
    return result


@router.post("/sync-compatibility")
async def sync_compatibility_start(background_tasks: BackgroundTasks):
    """Inicia sincronização de compatibilidade em background. Retorna imediatamente."""
    if sync_state["running"]:
        return {"status": "already_running", "processed": sync_state["processed"]}
    background_tasks.add_task(_run_sync)
    return {"status": "started"}


@router.get("/sync-compatibility/status")
def sync_compatibility_status():
    """Retorna o progresso atual da sincronização."""
    return sync_state


@router.post("/sync-compatibility-titles")
def sync_compat_titles(db: Session = Depends(get_db)):
    """Extrai compatibilidade de veículos direto do título de todas as peças."""
    result = sync_compat_from_titles(db)
    return result


@router.post("/push-compatibility/{part_id}")
async def push_compatibility_one(part_id: int, db: Session = Depends(get_db)):
    """Envia a compatibilidade de UMA peça pro ML — usado pra testar o formato
    aceito pela API antes de rodar em massa. Retorna a resposta crua do ML."""
    listing = db.query(MarketplaceListing).filter(
        MarketplaceListing.part_id == part_id,
        MarketplaceListing.marketplace == "mercadolivre",
    ).first()
    if not listing:
        raise HTTPException(404, "Peça sem anúncio ML no Pitbox")

    user_id, token = await get_valid_access_token(db)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        result = await push_part_compatibility_to_ml(part_id, listing.listing_id, db, headers, client)
    return {"part_id": part_id, "listing_id": listing.listing_id, **result}


async def _run_push_compat(limit: int | None = None):
    """Multi-conta: cada anúncio pode pertencer a uma conta ML diferente
    (legada ou extra, ex: pessoa física) — usar sempre o token da conta
    DONA do anúncio (resolve_account_for_listing), nunca um token fixo.
    Sem isso, todo anúncio de uma conta que não seja a legada recusa com
    403 'Unauthorized access to resource' (confirmado na prática:
    27 de 30 erros no primeiro teste em lote eram exatamente isso)."""
    from app.services.platform_registry import resolve_account_for_listing

    push_compat_state.update({"running": True, "processed": 0, "pushed": 0, "skipped": 0, "errors": [], "done": False})
    db = SessionLocal()
    try:
        query = db.query(MarketplaceListing).filter(
            MarketplaceListing.marketplace == "mercadolivre", MarketplaceListing.status == "active",
        )
        listings = query.limit(limit).all() if limit else query.all()
        async with httpx.AsyncClient(timeout=30) as client:
            for listing in listings:
                push_compat_state["processed"] += 1
                try:
                    account = await resolve_account_for_listing(listing, db)
                    if not account or not account.get("access_token"):
                        push_compat_state["errors"].append({"part_id": listing.part_id, "listing_id": listing.listing_id, "detail": "conta não resolvida"})
                        continue
                    headers = {"Authorization": f"Bearer {account['access_token']}", "Content-Type": "application/json"}
                    result = await push_part_compatibility_to_ml(listing.part_id, listing.listing_id, db, headers, client)
                    if result.get("ok"):
                        push_compat_state["pushed"] += 1
                    elif result.get("skipped"):
                        push_compat_state["skipped"] += 1
                    else:
                        push_compat_state["errors"].append({"part_id": listing.part_id, "listing_id": listing.listing_id, "detail": result.get("response")})
                except Exception as e:
                    push_compat_state["errors"].append({"part_id": listing.part_id, "listing_id": listing.listing_id, "detail": str(e)})
                if push_compat_state["processed"] % 20 == 0:
                    db.commit()
        db.commit()
    finally:
        push_compat_state.update({"running": False, "done": True})
        db.close()


@router.post("/push-compatibility")
def push_compatibility_all(background_tasks: BackgroundTasks, limit: int | None = None):
    """Envia em lote a compatibilidade (já cadastrada no Pitbox) das peças
    com anúncio ML ativo pro ML de verdade — corrige anúncios que caem
    'Inativo para revisar' por falta de ficha técnica de veículos. `limit`
    processa só as N primeiras (rodar em lotes menores em vez do catálogo
    inteiro de uma vez)."""
    if push_compat_state["running"]:
        return {"status": "already_running", **push_compat_state}
    background_tasks.add_task(_run_push_compat, limit)
    return {"status": "started", "limit": limit}


@router.get("/push-compatibility/status")
def push_compatibility_status():
    return push_compat_state


def _has_step(part: Part, step: str) -> bool:
    return any(s.get("step") == step for s in (part.pipeline_log or []))


async def _run_prepare_pending():
    prepare_state.update({"running": True, "processed": 0, "ready": 0, "needs_review": 0, "done": False})
    db = SessionLocal()
    try:
        listed_ids = {r[0] for r in db.query(MarketplaceListing.part_id).filter(MarketplaceListing.status == "active").all()}
        pending = db.query(Part).filter(Part.status == "draft", Part.active == True).all()  # noqa: E712
        for part in pending:
            if _has_step(part, "identificacao") or part.id in listed_ids:
                continue
            prepare_state["processed"] += 1
            result = await prepare_part(part.id, db)
            if result.get("status") == "ready_to_publish":
                prepare_state["ready"] += 1
            elif result.get("status") == "needs_review":
                prepare_state["needs_review"] += 1
    finally:
        prepare_state.update({"running": False, "done": True})
        db.close()


@router.post("/prepare-pending")
def prepare_pending(background_tasks: BackgroundTasks):
    """Identifica peças novas (fotos já otimizadas, esperando identificação),
    pesquisa preço e deixa prontas pra publicar com 1 clique — NUNCA publica
    sozinho no ML. Chamado automaticamente a cada N minutos (ver main.py) e
    também pode ser chamado manualmente (botão 'Verificar agora' no app)."""
    if prepare_state["running"]:
        return {"status": "already_running", **prepare_state}
    background_tasks.add_task(_run_prepare_pending)
    return {"status": "started"}


@router.get("/prepare-pending/status")
def prepare_pending_status():
    return prepare_state


@router.get("/disk-usage")
def disk_usage():
    """Diagnóstico rápido — descobrir o que está enchendo o volume do
    Railway (visto hoje 2026-07-21: upload falhou com 'No space left on
    device')."""
    import shutil
    from pathlib import Path
    from app.config import settings

    total, used, free = shutil.disk_usage(settings.uploads_dir)
    base = Path(settings.uploads_dir)
    tamanhos = []
    if base.exists():
        for item in base.iterdir():
            try:
                if item.is_dir():
                    size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
                else:
                    size = item.stat().st_size
                tamanhos.append({"nome": item.name, "mb": round(size / 1024 / 1024, 1)})
            except Exception:
                continue
    tamanhos.sort(key=lambda x: -x["mb"])
    return {
        "total_gb": round(total / 1024**3, 2),
        "usado_gb": round(used / 1024**3, 2),
        "livre_gb": round(free / 1024**3, 2),
        "maiores_itens": tamanhos[:20],
        "total_itens_na_raiz": len(tamanhos),
    }


@router.post("/disk-cleanup")
def disk_cleanup():
    """Libera espaço no volume — apaga o cache do modelo rembg (.u2net,
    ~342MB) que virou peso morto desde que o Photoroom passou a ser o motor
    principal de remoção de fundo (rembg só roda como reserva se o Photoroom
    falhar; nesse caso o modelo é baixado nessa hora, sem problema). Visto
    em 2026-07-21: volume de só 420MB total, quase todo ocupado por esse
    cache, causando 'No space left on device' no upload de foto."""
    import shutil
    from pathlib import Path
    from app.config import settings

    cache_dir = Path(settings.uploads_dir) / ".u2net"
    freed_mb = 0.0
    if cache_dir.exists():
        freed_mb = round(sum(f.stat().st_size for f in cache_dir.rglob("*") if f.is_file()) / 1024 / 1024, 1)
        shutil.rmtree(cache_dir)

    total, used, free = shutil.disk_usage(settings.uploads_dir)
    return {
        "liberado_mb": freed_mb,
        "livre_gb_agora": round(free / 1024**3, 2),
    }


@router.get("/ml-proxy")
async def ml_get_proxy(path: str, account_id: int | None = None, db: Session = Depends(get_db)):
    """Proxy só-leitura pra explorar endpoints GET da API do ML usando o token
    que o backend já gerencia — usado só durante o desenvolvimento da feature
    de compatibilidade (descobrir domain_id/attribute value_id), nunca expõe
    o token em si pro chamador. `account_id` opcional pra usar uma conta
    extra (ex: ML pessoa física) em vez da legada."""
    if account_id:
        from app.services.platform_registry import get_accounts_for_platform
        accounts = await get_accounts_for_platform("mercadolivre", db)
        account = next((a for a in accounts if a.get("account_id") == account_id), None)
        if not account:
            raise HTTPException(404, "conta não encontrada")
        token = account["access_token"]
    else:
        user_id, token = await get_valid_access_token(db)
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(f"https://api.mercadolibre.com/{path.lstrip('/')}", headers=headers)
    return {"status_code": r.status_code, "body": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:2000]}


@router.post("/ml-proxy-post")
async def ml_post_proxy(path: str, body: dict, db: Session = Depends(get_db)):
    """Mesma ideia do ml-proxy (GET), mas pra endpoints POST que são só
    consulta/contagem (ex: count_family_products) — usado só pra descobrir o
    formato certo de attribute id/value antes de gravar de verdade."""
    user_id, token = await get_valid_access_token(db)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(f"https://api.mercadolibre.com/{path.lstrip('/')}", headers=headers, json=body)
    return {"status_code": r.status_code, "body": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:2000]}
