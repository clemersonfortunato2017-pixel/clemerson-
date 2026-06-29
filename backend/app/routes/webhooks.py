from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.part import Part, StockMovement, MarketplaceListing
from app.models.sale import Sale, SaleItem
import httpx

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


async def get_ml_order(order_id: str, access_token: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"https://api.mercadolibre.com/orders/{order_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if r.status_code == 200:
            return r.json()
    return {}


def process_order_items(order: dict, platform: str, db: Session) -> tuple[int, float]:
    total = 0.0
    items_data = []

    for order_item in order.get("order_items", []):
        ml_item_id = order_item.get("item", {}).get("id")
        qty = order_item.get("quantity", 1)
        unit_price = float(order_item.get("unit_price", 0))

        listing = db.query(MarketplaceListing).filter_by(listing_id=ml_item_id).first()
        if not listing:
            continue

        part = db.query(Part).filter_by(id=listing.part_id).first()
        if not part or part.quantity < qty:
            continue

        items_data.append({"part": part, "qty": qty, "unit_price": unit_price})
        total += unit_price * qty

    return items_data, total


@router.post("/mercadolivre")
async def ml_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    topic = body.get("topic", "")
    resource = body.get("resource", "")

    if topic != "orders_v2" or not resource:
        return {"ok": True}

    order_id = str(resource).split("/")[-1]

    existing = db.query(Sale).filter_by(platform_order_id=order_id).first()
    if existing:
        return {"ok": True, "msg": "already processed"}

    from app.services.ml_token import get_valid_token
    access_token = await get_valid_token()
    order = await get_ml_order(order_id, access_token)

    if not order or order.get("status") not in ("paid", "delivered"):
        return {"ok": True}

    items_data, total = process_order_items(order, "mercadolivre", db)
    if not items_data:
        return {"ok": True, "msg": "no parts matched"}

    sale = Sale(
        platform="mercadolivre",
        platform_order_id=order_id,
        buyer_name=order.get("buyer", {}).get("nickname", ""),
        total=total,
        status="completed",
    )
    db.add(sale)
    db.flush()

    for item in items_data:
        item["part"].quantity -= item["qty"]
        db.add(StockMovement(
            part_id=item["part"].id, type="out",
            quantity=item["qty"], reason="Venda ML", reference=order_id,
        ))
        db.add(SaleItem(
            sale_id=sale.id, part_id=item["part"].id,
            quantity=item["qty"], unit_price=item["unit_price"],
            total_price=item["unit_price"] * item["qty"],
        ))

    db.commit()
    return {"ok": True, "sale_id": sale.id}


@router.post("/shopee")
async def shopee_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    return {"ok": True, "received": body}


@router.post("/amazon")
async def amazon_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    return {"ok": True, "received": body}
