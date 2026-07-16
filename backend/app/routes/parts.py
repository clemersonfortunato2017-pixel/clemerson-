from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import Optional
from pydantic import BaseModel
from app.database import get_db, SessionLocal
from app.models.part import Part, StockMovement, Compatibility
from app.config import settings
from app.routes.auth import get_current_user

router = APIRouter(prefix="/parts", tags=["parts"], dependencies=[Depends(get_current_user)])


class PartCreate(BaseModel):
    code: Optional[str] = None
    code_internal: Optional[str] = None
    code_oem: Optional[str] = None
    code_manufacturer: Optional[str] = None
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    condition: str = "used"
    cost_price: float = 0
    sale_price: float = 0
    quantity: int = 0
    min_quantity: int = 1
    max_quantity: int = 0
    location: Optional[str] = None
    loc_corridor: Optional[str] = None
    loc_shelf: Optional[str] = None
    loc_box: Optional[str] = None
    notes: Optional[str] = None


class PartUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    condition: Optional[str] = None
    cost_price: Optional[float] = None
    sale_price: Optional[float] = None
    quantity: Optional[int] = None
    min_quantity: Optional[int] = None
    max_quantity: Optional[int] = None
    location: Optional[str] = None
    loc_corridor: Optional[str] = None
    loc_shelf: Optional[str] = None
    loc_box: Optional[str] = None
    notes: Optional[str] = None
    active: Optional[bool] = None
    code_internal: Optional[str] = None
    code_oem: Optional[str] = None
    code_manufacturer: Optional[str] = None


class StockAdjust(BaseModel):
    quantity: int
    type: str = "adjustment"
    reason: Optional[str] = None


def _calc_margin(part: Part):
    if part.cost_price and part.sale_price and part.cost_price > 0:
        part.margin_percent = round(((part.sale_price - part.cost_price) / part.cost_price) * 100, 2)


def _log_step(part: Part, step: str, detail: str = ""):
    log = list(part.pipeline_log or [])
    log.append({"step": step, "detail": detail})
    part.pipeline_log = log


def _process_photos_background(part_id: int, originais_paths: list[str]):
    """Roda fora do request (BackgroundTasks): otimiza as fotos e marca a peça
    como pronta pra esteira automática (Passo A3) pegar e publicar."""
    from app.services.image_processor import processar_fotos_peca

    db = SessionLocal()
    try:
        part = db.query(Part).filter(Part.id == part_id).first()
        if not part:
            return
        try:
            otimizadas = processar_fotos_peca(
                part_id, [Path(p) for p in originais_paths], Path(settings.uploads_dir)
            )
            part.photos = otimizadas
            part.status = "draft"  # pronta p/ a rotina agendada (Passo A3) identificar e publicar
            _log_step(part, "otimizacao_foto", f"{len(otimizadas)} foto(s) otimizada(s)")
        except Exception as e:
            part.status = "error"
            _log_step(part, "otimizacao_foto", f"erro: {e}")
        db.commit()
    finally:
        db.close()


@router.post("/upload-photos")
async def upload_photos(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """Recebe fotos tiradas/enviadas no Pitbox, cria a peça em status=draft e
    dispara a otimização de imagem em background. A identificação da peça,
    pesquisa de compatibilidade/concorrentes e publicação no Mercado Livre
    ficam por conta da rotina agendada (esteira automática), não deste endpoint."""
    if not files:
        raise HTTPException(status_code=400, detail="Nenhuma foto enviada")

    part = Part(
        title="Peça aguardando identificação",
        status="processing",
        photos=[],
        pipeline_log=[{"step": "upload", "detail": f"{len(files)} foto(s) recebida(s)"}],
    )
    db.add(part)
    db.flush()

    originais_dir = Path(settings.uploads_dir) / str(part.id) / "originais"
    originais_dir.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    for f in files:
        dest = originais_dir / f.filename
        dest.write_bytes(await f.read())
        saved_paths.append(str(dest))

    db.commit()
    db.refresh(part)

    background_tasks.add_task(_process_photos_background, part.id, saved_paths)

    return {"id": part.id, "status": part.status, "photos_received": len(files)}


@router.get("/")
def list_parts(
    q: Optional[str] = Query(None),
    category: Optional[str] = None,
    condition: Optional[str] = None,
    status: Optional[str] = None,
    low_stock: bool = False,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    query = db.query(Part).filter(Part.active == True)

    if status:
        query = query.filter(Part.status == status)
    if q:
        query = query.filter(
            or_(
                Part.title.ilike(f"%{q}%"),
                Part.code.ilike(f"%{q}%"),
                Part.code_internal.ilike(f"%{q}%"),
                Part.code_oem.ilike(f"%{q}%"),
                Part.code_manufacturer.ilike(f"%{q}%"),
                Part.brand.ilike(f"%{q}%"),
            )
        )
    if category:
        query = query.filter(Part.category == category)
    if condition:
        query = query.filter(Part.condition == condition)
    if low_stock:
        query = query.filter(Part.quantity <= Part.min_quantity)

    total = query.count()
    parts = query.offset(skip).limit(limit).all()

    # Marcar quais peças têm anúncio ativo em alguma plataforma
    from app.models.part import MarketplaceListing
    listed_ids = {
        r[0] for r in db.query(MarketplaceListing.part_id)
        .filter(MarketplaceListing.status == "active")
        .filter(MarketplaceListing.part_id.in_([p.id for p in parts]))
        .all()
    }
    items = []
    for p in parts:
        d = {c.name: getattr(p, c.name) for c in p.__table__.columns}
        d["has_listings"] = p.id in listed_ids
        items.append(d)

    return {"total": total, "items": items}


@router.get("/alerts/low-stock")
def low_stock_alerts(db: Session = Depends(get_db)):
    parts = db.query(Part).filter(
        Part.active == True,
        Part.min_quantity > 0,
        Part.quantity <= Part.min_quantity,
    ).order_by(Part.quantity.asc()).limit(50).all()
    return parts


@router.get("/reports/abc")
def abc_curve(db: Session = Depends(get_db)):
    """Curva ABC: peças ordenadas por volume de vendas (valor total vendido)."""
    from app.models.sale import SaleItem
    rows = (
        db.query(
            Part.id,
            Part.title,
            Part.code,
            Part.code_internal,
            Part.category,
            func.sum(SaleItem.total_price).label("total_sold"),
            func.sum(SaleItem.quantity).label("units_sold"),
            Part.quantity.label("stock"),
            Part.sale_price,
            Part.cost_price,
            Part.margin_percent,
        )
        .outerjoin(SaleItem, SaleItem.part_id == Part.id)
        .filter(Part.active == True)
        .group_by(Part.id)
        .order_by(func.sum(SaleItem.total_price).desc().nulls_last())
        .all()
    )

    total_revenue = sum(r.total_sold or 0 for r in rows)
    result = []
    accumulated = 0
    for r in rows:
        sold = float(r.total_sold or 0)
        accumulated += sold
        pct = (accumulated / total_revenue * 100) if total_revenue > 0 else 0
        curve = "A" if pct <= 80 else ("B" if pct <= 95 else "C")
        result.append({
            "id": r.id,
            "title": r.title,
            "code": r.code_internal or r.code,
            "category": r.category,
            "total_sold": sold,
            "units_sold": int(r.units_sold or 0),
            "stock": r.stock,
            "sale_price": r.sale_price,
            "cost_price": r.cost_price,
            "margin_percent": r.margin_percent,
            "curve": curve,
            "accumulated_pct": round(pct, 1),
        })
    return result


@router.get("/similar/{part_id}")
def get_similar(part_id: int, db: Session = Depends(get_db)):
    """Retorna peças que compartilham compatibilidade com os mesmos veículos."""
    part = db.query(Part).filter(Part.id == part_id, Part.active == True).first()
    if not part:
        raise HTTPException(status_code=404, detail="Peça não encontrada")

    vehicle_ids = [c.vehicle_id for c in part.compatibilities]
    if not vehicle_ids:
        return []

    similar_part_ids = (
        db.query(Compatibility.part_id)
        .filter(
            Compatibility.vehicle_id.in_(vehicle_ids),
            Compatibility.part_id != part_id,
        )
        .distinct()
        .all()
    )
    ids = [r[0] for r in similar_part_ids]
    if not ids:
        return []

    return db.query(Part).filter(Part.id.in_(ids), Part.active == True, Part.quantity > 0).all()


@router.get("/{part_id}")
def get_part(part_id: int, db: Session = Depends(get_db)):
    part = db.query(Part).filter(Part.id == part_id).first()
    if not part:
        raise HTTPException(status_code=404, detail="Peça não encontrada")
    return part


@router.post("/")
def create_part(data: PartCreate, db: Session = Depends(get_db)):
    part = Part(**data.model_dump())
    _calc_margin(part)
    db.add(part)
    db.commit()
    db.refresh(part)
    return part


@router.put("/{part_id}")
def update_part(part_id: int, data: PartUpdate, db: Session = Depends(get_db)):
    part = db.query(Part).filter(Part.id == part_id).first()
    if not part:
        raise HTTPException(status_code=404, detail="Peça não encontrada")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(part, k, v)
    _calc_margin(part)
    db.commit()
    db.refresh(part)
    return part


@router.post("/{part_id}/stock")
def adjust_stock(part_id: int, data: StockAdjust, db: Session = Depends(get_db)):
    part = db.query(Part).filter(Part.id == part_id).first()
    if not part:
        raise HTTPException(status_code=404, detail="Peça não encontrada")

    if data.type == "in":
        part.quantity += data.quantity
    elif data.type == "out":
        if part.quantity < data.quantity:
            raise HTTPException(status_code=400, detail="Estoque insuficiente")
        part.quantity -= data.quantity
    else:
        part.quantity = data.quantity

    movement = StockMovement(
        part_id=part.id,
        type=data.type,
        quantity=data.quantity,
        reason=data.reason,
    )
    db.add(movement)
    db.commit()

    alert = None
    if part.min_quantity > 0 and part.quantity <= part.min_quantity:
        alert = f"Estoque baixo: {part.quantity} un. (mín: {part.min_quantity})"
    if part.max_quantity > 0 and part.quantity >= part.max_quantity:
        alert = f"Estoque acima do máximo: {part.quantity} un. (máx: {part.max_quantity})"

    return {"quantity": part.quantity, "alert": alert}


@router.delete("/{part_id}")
def delete_part(part_id: int, db: Session = Depends(get_db)):
    part = db.query(Part).filter(Part.id == part_id).first()
    if not part:
        raise HTTPException(status_code=404, detail="Peça não encontrada")
    part.active = False
    db.commit()
    return {"ok": True}
