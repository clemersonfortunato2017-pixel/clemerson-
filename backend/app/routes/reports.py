"""Relatório diário da esteira automática — o que foi publicado sozinho,
por quanto, e o que deu erro (pra auditar decisão tomada sem revisão humana)."""

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models.part import Part, MarketplaceListing
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
