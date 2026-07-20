import httpx
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db, SessionLocal
from app.models.part import Part, MarketplaceListing
from app.services.ml_importer import import_from_ml, sync_all_compatibility, get_valid_access_token, push_part_compatibility_to_ml
from app.services.title_compat_parser import sync_compat_from_titles
from app.routes.auth import get_current_user

router = APIRouter(prefix="/import", tags=["import"], dependencies=[Depends(get_current_user)])

# Estado simples do job de sync em memória
sync_state = {"running": False, "processed": 0, "added": 0, "done": False, "error": None}
push_compat_state = {"running": False, "processed": 0, "pushed": 0, "skipped": 0, "errors": [], "done": False}


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


async def _run_push_compat():
    push_compat_state.update({"running": True, "processed": 0, "pushed": 0, "skipped": 0, "errors": [], "done": False})
    db = SessionLocal()
    try:
        user_id, token = await get_valid_access_token(db)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        listings = db.query(MarketplaceListing).filter(MarketplaceListing.marketplace == "mercadolivre").all()
        async with httpx.AsyncClient(timeout=30) as client:
            for listing in listings:
                push_compat_state["processed"] += 1
                try:
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
def push_compatibility_all(background_tasks: BackgroundTasks):
    """Envia em lote a compatibilidade (já cadastrada no Pitbox) de TODAS as
    peças com anúncio ML pro ML de verdade — corrige anúncios que caem
    'Inativo para revisar' por falta de ficha técnica de veículos."""
    if push_compat_state["running"]:
        return {"status": "already_running", **push_compat_state}
    background_tasks.add_task(_run_push_compat)
    return {"status": "started"}


@router.get("/push-compatibility/status")
def push_compatibility_status():
    return push_compat_state
