from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.part import Part, MarketplaceListing, StockMovement
from app.services.platform_registry import (
    close_on_all_platforms, publish_to_all_platforms,
    PLATFORMS, get_connected_platforms,
)
from app.routes.auth import get_current_user

router = APIRouter(prefix="/platforms", tags=["platforms"], dependencies=[Depends(get_current_user)])


@router.get("/status")
def platforms_status():
    """Lista todas as plataformas e se estão conectadas."""
    return [
        {
            "name": p.name,
            "display_name": p.display_name,
            "connected": p.is_connected(),
        }
        for p in PLATFORMS.values()
    ]


@router.post("/parts/{part_id}/publish-all")
async def publish_to_all(part_id: int, db: Session = Depends(get_db)):
    """Publica a peça em todas as plataformas conectadas onde ela ainda não está."""
    result = await publish_to_all_platforms(part_id, db)
    return result


@router.post("/parts/{part_id}/sold-balcao")
async def sold_at_counter(part_id: int, db: Session = Depends(get_db)):
    """
    Marca peça como vendida no balcão:
    - Zera estoque
    - Fecha anúncio em TODAS as plataformas
    - Registra movimento de saída
    """
    part = db.query(Part).filter(Part.id == part_id).first()
    if not part:
        return {"error": "Peça não encontrada"}

    # Fechar em todas as plataformas
    platform_results = await close_on_all_platforms(part_id, db)

    # Registrar saída de estoque
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
    """Reativa peça e republica em todas as plataformas conectadas."""
    part = db.query(Part).filter(Part.id == part_id).first()
    if not part:
        return {"error": "Peça não encontrada"}
    part.active = True
    db.commit()
    result = await publish_to_all_platforms(part_id, db)
    return result
