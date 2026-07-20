"""Sincronização de estoque entre contas/plataformas depois de qualquer venda.

Roda em background (BackgroundTasks do FastAPI — não atrasa a resposta do
webhook) e loga CADA tentativa em platform_sync_logs. Uma peça publicada em
3+ contas não pode ficar vendável em duas ao mesmo tempo, então:

- Toda falha é registrada, nunca engolida em silêncio.
- Retry automático (3 tentativas, backoff curto) pra falha transitória de rede.
- Se esgotar as tentativas, marca MarketplaceListing.sync_failed=True — fica
  visível em GET /platforms/sync-failures pra alerta manual e retry sob demanda.
"""
import asyncio
from datetime import datetime, timezone
from app.database import SessionLocal
from app.models.part import Part, MarketplaceListing
from app.models.platform_account import PlatformSyncLog

MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 2


async def sync_after_sale(part_id: int, sold_listing_id: int | None = None):
    """Entry point pro BackgroundTasks — abre a própria sessão de banco
    (não reaproveita a do request, que já fechou quando isto roda)."""
    db = SessionLocal()
    try:
        part = db.query(Part).filter(Part.id == part_id).first()
        if not part:
            return

        others_q = db.query(MarketplaceListing).filter(
            MarketplaceListing.part_id == part_id,
            MarketplaceListing.status == "active",
        )
        if sold_listing_id:
            others_q = others_q.filter(MarketplaceListing.id != sold_listing_id)
        others = others_q.all()

        for listing in others:
            await _sync_listing(listing, part.quantity, db)
    finally:
        db.close()


async def _sync_listing(listing: MarketplaceListing, new_quantity: int, db) -> None:
    from app.services.platform_registry import PLATFORMS, resolve_account_for_listing

    platform_impl = PLATFORMS.get(listing.marketplace)
    account = await resolve_account_for_listing(listing, db)

    if not platform_impl or not account:
        db.add(PlatformSyncLog(
            part_id=listing.part_id, listing_id=listing.listing_id, marketplace=listing.marketplace,
            action="resolve_account", attempt=1, success=False,
            detail="conta não resolvida (plataforma desconhecida ou credencial ausente)",
        ))
        listing.sync_failed = True
        db.commit()
        return

    action = "close" if new_quantity <= 0 else "update_stock"

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            if action == "close":
                r = await platform_impl.close(listing.listing_id, account)
            else:
                r = await platform_impl.update_stock(listing.listing_id, new_quantity, account)
            ok = bool(r.get("ok"))
        except Exception as e:
            r, ok = {"error": str(e)}, False

        db.add(PlatformSyncLog(
            part_id=listing.part_id, listing_id=listing.listing_id, marketplace=listing.marketplace,
            action=action, attempt=attempt, success=ok, detail=str(r)[:500],
        ))
        db.commit()

        if ok:
            if action == "close":
                listing.status = "closed"
            listing.sync_failed = False
            listing.synced_at = datetime.now(timezone.utc)
            db.commit()
            return

        if attempt < MAX_ATTEMPTS:
            await asyncio.sleep(attempt * RETRY_BACKOFF_SECONDS)

    listing.sync_failed = True
    db.commit()


async def retry_listing_sync(listing_id: int, db) -> dict:
    """Reenvia manualmente a sincronização de UMA listagem marcada como
    sync_failed — chamado pela rota POST /platforms/sync-failures/{id}/retry."""
    listing = db.query(MarketplaceListing).filter(MarketplaceListing.id == listing_id).first()
    if not listing:
        return {"error": "listagem não encontrada"}
    part = db.query(Part).filter(Part.id == listing.part_id).first()
    if not part:
        return {"error": "peça não encontrada"}
    await _sync_listing(listing, part.quantity, db)
    return {"ok": True, "sync_failed": listing.sync_failed}
