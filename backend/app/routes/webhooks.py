from fastapi import APIRouter, Depends, Request, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.part import Part, StockMovement, MarketplaceListing
from app.models.sale import Sale, SaleItem
from app.models.platform_account import PlatformAccount
from app.services.cross_platform_sync import sync_after_sale
import httpx

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


async def get_ml_order(order_id: str, access_token: str) -> dict:
    if not access_token:
        return {}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"https://api.mercadolibre.com/orders/{order_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if r.status_code == 200:
            return r.json()
    return {}


async def resolve_ml_account(user_id, db: Session) -> dict | None:
    """Descobre qual conta ML recebeu o pedido — o payload do webhook do ML
    traz `user_id` (dono do recurso), que pode ser a conta principal (PJ,
    legada) ou uma das contas extras (ex: PF) cadastradas em platform_accounts."""
    from app.services.platform_registry import _ml_legacy_account, _ensure_fresh_extra_account

    legacy = await _ml_legacy_account(db)
    if legacy and user_id and str(legacy.get("external_id")) == str(user_id):
        return legacy

    if user_id:
        row = db.query(PlatformAccount).filter_by(
            platform="mercadolivre", external_id=str(user_id), active=True
        ).first()
        if row:
            acc = await _ensure_fresh_extra_account(row, db)
            if acc:
                return acc

    # Fallback: se não bateu com nenhuma conta conhecida, usa a legada mesmo
    # assim (melhor tentar com token possivelmente errado do que não tentar).
    return legacy


def process_order_items(order: dict, db: Session) -> tuple[list[dict], float]:
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

        items_data.append({"part": part, "qty": qty, "unit_price": unit_price, "listing": listing})
        total += unit_price * qty

    return items_data, total


@router.post("/mercadolivre")
async def ml_webhook(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    body = await request.json()
    topic = body.get("topic", "")
    resource = body.get("resource", "")
    ml_user_id = body.get("user_id")

    if topic != "orders_v2" or not resource:
        return {"ok": True}

    order_id = str(resource).split("/")[-1]

    existing = db.query(Sale).filter_by(platform_order_id=order_id).first()
    if existing:
        return {"ok": True, "msg": "already processed"}

    account = await resolve_ml_account(ml_user_id, db)
    access_token = account["access_token"] if account else None
    order = await get_ml_order(order_id, access_token)

    if not order or order.get("status") not in ("paid", "delivered"):
        return {"ok": True}

    items_data, total = process_order_items(order, db)
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

    sync_targets = []  # (part_id, listing.id) — pra propagar baixa de estoque pras outras contas/plataformas
    for item in items_data:
        item["part"].quantity -= item["qty"]
        db.add(StockMovement(
            part_id=item["part"].id, type="out",
            quantity=item["qty"],
            reason=f"Venda ML ({account['label'] if account else 'conta desconhecida'})",
            reference=order_id,
        ))
        db.add(SaleItem(
            sale_id=sale.id, part_id=item["part"].id,
            quantity=item["qty"], unit_price=item["unit_price"],
            total_price=item["unit_price"] * item["qty"],
        ))
        sync_targets.append((item["part"].id, item["listing"].id))

    db.commit()

    # Baixa instantânea nas OUTRAS plataformas/contas onde a mesma peça está
    # publicada — roda em background pra não segurar a resposta do webhook
    # (o ML espera resposta rápida, senão reenvia a notificação).
    for part_id, listing_id in sync_targets:
        background_tasks.add_task(sync_after_sale, part_id, listing_id)

    return {"ok": True, "sale_id": sale.id}


@router.post("/shopee")
async def shopee_webhook(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    raw = await request.body()
    body = await request.json()

    from app.services.shopee_client import verify_push_signature
    signature = request.headers.get("Authorization", "")
    if not verify_push_signature(str(request.url), raw, signature):
        raise HTTPException(status_code=401, detail="assinatura Shopee inválida")

    shop_id = body.get("shop_id")
    code = body.get("code")
    data = body.get("data", {}) or {}

    # code 3 = Order Status Push (Shopee Push Mechanism V2)
    if code != 3:
        return {"ok": True}

    order_sn = data.get("ordersn")
    status = data.get("status")
    if not order_sn or status not in ("READY_TO_SHIP", "PROCESSED", "COMPLETED"):
        return {"ok": True}

    existing = db.query(Sale).filter_by(platform_order_id=order_sn).first()
    if existing:
        return {"ok": True, "msg": "already processed"}

    account_row = db.query(PlatformAccount).filter_by(
        platform="shopee", external_id=str(shop_id), active=True
    ).first()
    if not account_row:
        return {"ok": True, "msg": "loja Shopee não cadastrada em platform_accounts"}

    from app.services.platform_registry import _ensure_fresh_extra_account
    account = await _ensure_fresh_extra_account(account_row, db)
    if not account:
        return {"ok": True, "msg": "conta Shopee sem token válido"}

    from app.services.shopee_client import get_order_detail
    order = await get_order_detail(order_sn, account)
    if not order:
        return {"ok": True, "msg": "pedido não encontrado na API Shopee"}

    items_data = []
    total = 0.0
    for item in order.get("item_list", []):
        shopee_item_id = str(item.get("item_id"))
        qty = item.get("model_quantity_purchased", 1)
        unit_price = float(item.get("model_discounted_price") or item.get("model_original_price") or 0)

        listing = db.query(MarketplaceListing).filter_by(listing_id=shopee_item_id).first()
        if not listing:
            continue
        part = db.query(Part).filter_by(id=listing.part_id).first()
        if not part or part.quantity < qty:
            continue

        items_data.append({"part": part, "qty": qty, "unit_price": unit_price, "listing": listing})
        total += unit_price * qty

    if not items_data:
        return {"ok": True, "msg": "no parts matched"}

    sale = Sale(
        platform="shopee",
        platform_order_id=order_sn,
        buyer_name=order.get("buyer_username", ""),
        total=total,
        status="completed",
    )
    db.add(sale)
    db.flush()

    sync_targets = []
    for item in items_data:
        item["part"].quantity -= item["qty"]
        db.add(StockMovement(
            part_id=item["part"].id, type="out", quantity=item["qty"],
            reason=f"Venda Shopee ({account['label']})", reference=order_sn,
        ))
        db.add(SaleItem(
            sale_id=sale.id, part_id=item["part"].id,
            quantity=item["qty"], unit_price=item["unit_price"],
            total_price=item["unit_price"] * item["qty"],
        ))
        sync_targets.append((item["part"].id, item["listing"].id))

    db.commit()

    for part_id, listing_id in sync_targets:
        background_tasks.add_task(sync_after_sale, part_id, listing_id)

    return {"ok": True, "sale_id": sale.id}


@router.post("/amazon")
async def amazon_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    return {"ok": True, "received": body}
