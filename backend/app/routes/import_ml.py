from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db, SessionLocal
from app.services.ml_importer import import_from_ml, sync_all_compatibility
from app.services.title_compat_parser import sync_compat_from_titles
from app.routes.auth import get_current_user

router = APIRouter(prefix="/import", tags=["import"], dependencies=[Depends(get_current_user)])

# Estado simples do job de sync em memória
sync_state = {"running": False, "processed": 0, "added": 0, "done": False, "error": None}


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
