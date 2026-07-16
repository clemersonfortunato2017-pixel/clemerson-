from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from typing import Optional
from pydantic import BaseModel
from datetime import datetime
from app.database import get_db
from app.models.sale import Sale, SaleItem
from app.models.part import Part, StockMovement
from app.routes.auth import get_current_user

router = APIRouter(prefix="/sales", tags=["sales"], dependencies=[Depends(get_current_user)])

PLATFORM_FEES = {
    "mercadolivre": 14.0,
    "shopee": 12.0,
    "amazon": 15.0,
    "balcao": 0.0,
}

PAYMENT_FEES = {
    "cartao_credito": 3.49,
    "cartao_debito": 1.49,
    "pix": 0.0,
    "dinheiro": 0.0,
    "boleto": 2.0,
    "prazo": 0.0,
}


class SaleItemIn(BaseModel):
    part_id: int
    quantity: int
    unit_price: float


class SaleCreate(BaseModel):
    platform: str
    platform_order_id: Optional[str] = None
    buyer_name: Optional[str] = None
    buyer_phone: Optional[str] = None
    payment_method: Optional[str] = "dinheiro"
    notes: Optional[str] = None
    items: list[SaleItemIn]


@router.post("/")
def create_sale(data: SaleCreate, db: Session = Depends(get_db)):
    revenue = sum(i.unit_price * i.quantity for i in data.items)

    platform_fee_pct = PLATFORM_FEES.get(data.platform, 0)
    payment_fee_pct = PAYMENT_FEES.get(data.payment_method or "dinheiro", 0)
    total_fee_pct = platform_fee_pct + payment_fee_pct
    fee_value = round(revenue * total_fee_pct / 100, 2)
    net = round(revenue - fee_value, 2)

    sale = Sale(
        platform=data.platform,
        platform_order_id=data.platform_order_id,
        buyer_name=data.buyer_name,
        buyer_phone=data.buyer_phone,
        payment_method=data.payment_method,
        notes=data.notes,
        total=round(revenue, 2),
        payment_fee_pct=total_fee_pct,
        payment_fee_value=fee_value,
        net_total=net,
    )
    db.add(sale)
    db.flush()

    cost_total = 0.0
    for item_data in data.items:
        part = db.query(Part).filter_by(id=item_data.part_id).first()
        if not part:
            raise HTTPException(status_code=404, detail=f"Peça {item_data.part_id} não encontrada")
        if part.quantity < item_data.quantity:
            raise HTTPException(status_code=400, detail=f"Estoque insuficiente para {part.title}")

        part.quantity -= item_data.quantity

        item_cost = (part.cost_price or 0) * item_data.quantity
        item_revenue = item_data.unit_price * item_data.quantity
        cost_total += item_cost

        margin = 0.0
        if part.cost_price and part.cost_price > 0:
            margin = round(((item_data.unit_price - part.cost_price) / part.cost_price) * 100, 2)

        movement = StockMovement(
            part_id=part.id,
            type="out",
            quantity=item_data.quantity,
            reason=f"Venda {data.platform}",
            reference=str(sale.id),
        )
        db.add(movement)

        sale_item = SaleItem(
            sale_id=sale.id,
            part_id=item_data.part_id,
            quantity=item_data.quantity,
            unit_price=item_data.unit_price,
            unit_cost=part.cost_price or 0,
            total_price=item_revenue,
            total_cost=item_cost,
            margin_pct=margin,
        )
        db.add(sale_item)

    sale.cost_total = round(cost_total, 2)
    sale.profit = round(net - cost_total, 2)
    sale.profit_pct = round((sale.profit / net * 100) if net > 0 else 0, 2)

    db.commit()
    db.refresh(sale)
    return sale


@router.get("/")
def list_sales(
    platform: Optional[str] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    query = db.query(Sale)
    if platform:
        query = query.filter(Sale.platform == platform)
    if month:
        query = query.filter(extract("month", Sale.sold_at) == month)
    if year:
        query = query.filter(extract("year", Sale.sold_at) == year)
    total = query.count()
    items = query.order_by(Sale.sold_at.desc()).offset(skip).limit(limit).all()
    return {"total": total, "items": items}


@router.get("/financial/monthly")
def monthly_financial(
    month: Optional[int] = None,
    year: Optional[int] = None,
    db: Session = Depends(get_db),
):
    now = datetime.now()
    m = month or now.month
    y = year or now.year

    platforms = ["mercadolivre", "shopee", "amazon", "balcao"]
    result = {}
    grand_total = 0
    grand_net = 0
    grand_profit = 0

    for platform in platforms:
        row = db.query(
            func.sum(Sale.total),
            func.count(Sale.id),
            func.sum(Sale.net_total),
            func.sum(Sale.profit),
            func.sum(Sale.payment_fee_value),
        ).filter(
            Sale.platform == platform,
            Sale.status == "completed",
            extract("month", Sale.sold_at) == m,
            extract("year", Sale.sold_at) == y,
        ).first()
        total = float(row[0] or 0)
        count = int(row[1] or 0)
        net = float(row[2] or 0)
        profit = float(row[3] or 0)
        fees = float(row[4] or 0)
        result[platform] = {"total": total, "count": count, "net": net, "profit": profit, "fees": fees}
        grand_total += total
        grand_net += net
        grand_profit += profit

    result["total"] = grand_total
    result["net_total"] = grand_net
    result["profit"] = grand_profit
    result["month"] = m
    result["year"] = y
    return result
