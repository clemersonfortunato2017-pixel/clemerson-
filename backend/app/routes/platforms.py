from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.part import Part, MarketplaceListing, StockMovement
from app.services.platform_registry import (
    close_on_all_accounts, publish_to_all_accounts, get_platforms_status,
)
from app.services.cross_platform_sync import retry_listing_sync
from app.routes.auth import get_current_user

router = APIRouter(prefix="/platforms", tags=["platforms"], dependencies=[Depends(get_current_user)])


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
