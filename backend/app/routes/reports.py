"""Relatório diário da esteira automática — o que foi publicado sozinho,
por quanto, e o que deu erro (pra auditar decisão tomada sem revisão humana)."""

import asyncio
import httpx
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from app.database import get_db
from app.models.part import Part, MarketplaceListing
from app.models.sale import Sale, SaleItem
from app.services.ml_importer import get_item_visits
from app.services.platform_registry import resolve_account_for_listing
from app.routes.auth import get_current_user

router = APIRouter(prefix="/reports", tags=["reports"], dependencies=[Depends(get_current_user)])


@router.get("/daily")
def daily_report(date: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """date no formato YYYY-MM-DD; default = hoje (UTC)."""
    day = datetime.strptime(date, "%Y-%m-%d").date() if date else datetime.now(timezone.utc).date()
    start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    listings = (
        db.query(MarketplaceListing)
        .filter(MarketplaceListing.created_at >= start, MarketplaceListing.created_at < end)
        .all()
    )
    published = []
    total_value = 0.0
    for listing in listings:
        part = db.query(Part).filter(Part.id == listing.part_id).first()
        published.append({
            "part_id": listing.part_id,
            "title": part.title if part else None,
            "marketplace": listing.marketplace,
            "listing_id": listing.listing_id,
            "url": listing.url,
            "price": listing.price,
        })
        total_value += listing.price or 0

    errors = (
        db.query(Part)
        .filter(Part.status == "error", Part.updated_at >= start, Part.updated_at < end)
        .all()
    )
    error_list = [
        {"part_id": p.id, "title": p.title, "log": p.pipeline_log}
        for p in errors
    ]

    return {
        "date": day.isoformat(),
        "published_count": len(published),
        "total_value": round(total_value, 2),
        "published": published,
        "error_count": len(error_list),
        "errors": error_list,
    }


@router.get("/anuncios-status")
async def anuncios_status(db: Session = Depends(get_db)):
    """Classifica cada anúncio ativo do ML em 4 categorias (método da aula
    'Líder ao Platinum', Alex Moro, 2026-07-21):
    - parado_visibilidade: 30+ dias sem venda E poucas visitas (<100) —
      problema de tráfego/visibilidade.
    - parado_conversao: 30+ dias sem venda MAS visitas altas (>=100) —
      problema de oferta/preço/foto, não de visibilidade.
    - estrela: vendeu nos últimos 30 dias com margem e volume acima da
      média da conta — prioridade de investimento (ads, Full, destaque).
    - saudavel: vendeu nos últimos 30 dias, dentro da média.
    Visitas do ML atualizam com até 48h de atraso (limitação da própria API,
    não é bug daqui)."""
    listings = db.query(MarketplaceListing).filter(
        MarketplaceListing.marketplace == "mercadolivre",
        MarketplaceListing.status == "active",
    ).all()
    if not listings:
        return {"parado_visibilidade": [], "parado_conversao": [], "estrela": [], "saudavel": [], "media_conta": {}}

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    # Média da conta (últimos 30 dias) pra decidir o que é "estrela"
    recent_items = (
        db.query(SaleItem, Sale)
        .join(Sale, SaleItem.sale_id == Sale.id)
        .filter(Sale.platform == "mercadolivre", Sale.sold_at >= cutoff)
        .all()
    )
    qty_by_part: dict[int, int] = {}
    margin_by_part: dict[int, list[float]] = {}
    for item, sale in recent_items:
        qty_by_part[item.part_id] = qty_by_part.get(item.part_id, 0) + item.quantity
        margin_by_part.setdefault(item.part_id, []).append(item.margin_pct or 0)

    avg_qty = (sum(qty_by_part.values()) / len(qty_by_part)) if qty_by_part else 0
    all_margins = [m for ms in margin_by_part.values() for m in ms]
    avg_margin = (sum(all_margins) / len(all_margins)) if all_margins else 0

    # Resolve a conta certa por anúncio ANTES de buscar visita — anúncio da
    # conta PF só pode ser consultado com o token da PF, não o da PJ
    # (legada). Sem isso, visita de anúncio PF sempre voltaria 0/erro.
    accounts_by_listing: dict[int, Optional[dict]] = {}
    for listing in listings:
        accounts_by_listing[listing.id] = await resolve_account_for_listing(listing, db)

    sem = asyncio.Semaphore(5)

    async def visits_for(listing: MarketplaceListing) -> int:
        account = accounts_by_listing.get(listing.id)
        if not account or not account.get("access_token"):
            return 0
        headers = {"Authorization": f"Bearer {account['access_token']}"}
        async with sem:
            async with httpx.AsyncClient() as client:
                return await get_item_visits(listing.listing_id, headers, client)

    visit_counts = await asyncio.gather(*(visits_for(l) for l in listings))

    buckets = {"parado_visibilidade": [], "parado_conversao": [], "estrela": [], "saudavel": []}
    for listing, visits in zip(listings, visit_counts):
        part = db.query(Part).filter(Part.id == listing.part_id).first()
        if not part:
            continue
        account = accounts_by_listing.get(listing.id)
        last_sale = (
            db.query(func.max(Sale.sold_at))
            .join(SaleItem, SaleItem.sale_id == Sale.id)
            .filter(SaleItem.part_id == part.id, Sale.platform == "mercadolivre")
            .scalar()
        )
        vendeu_recente = last_sale is not None and last_sale >= cutoff
        entry = {
            "part_id": part.id, "title": part.title, "listing_id": listing.listing_id,
            "url": listing.url, "visits_total": visits,
            "conta": account["label"] if account else "desconhecida",
            "last_sale_at": last_sale.isoformat() if last_sale else None,
        }
        if not vendeu_recente:
            entry["categoria"] = "parado_conversao" if visits >= 100 else "parado_visibilidade"
        else:
            qty = qty_by_part.get(part.id, 0)
            margins = margin_by_part.get(part.id, [])
            margin = (sum(margins) / len(margins)) if margins else 0
            entry["categoria"] = "estrela" if (qty >= avg_qty and margin >= avg_margin and avg_qty > 0) else "saudavel"
        buckets[entry["categoria"]].append(entry)

    return {**buckets, "media_conta": {"qtd_media_30d": round(avg_qty, 2), "margem_media_30d_pct": round(avg_margin, 2)}}
