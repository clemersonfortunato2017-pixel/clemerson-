from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from pydantic import BaseModel
from app.database import get_db
from app.models.part import Vehicle, Compatibility, Part
from app.routes.auth import get_current_user

router = APIRouter(prefix="/compatibility", tags=["compatibility"], dependencies=[Depends(get_current_user)])


class VehicleCreate(BaseModel):
    brand: str
    model: str
    year_start: Optional[int] = None
    year_end: Optional[int] = None
    engine: Optional[str] = None
    version: Optional[str] = None


class CompatibilityCreate(BaseModel):
    part_id: int
    vehicle_id: int
    oem_code: Optional[str] = None
    notes: Optional[str] = None


@router.get("/vehicles")
def list_vehicles(q: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Vehicle)
    if q:
        query = query.filter(
            or_(Vehicle.brand.ilike(f"%{q}%"), Vehicle.model.ilike(f"%{q}%"))
        )
    return query.order_by(Vehicle.brand, Vehicle.model).limit(50).all()


@router.post("/vehicles")
def create_vehicle(data: VehicleCreate, db: Session = Depends(get_db)):
    vehicle = Vehicle(**data.model_dump())
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.get("/parts/{part_id}")
def get_part_compatibility(part_id: int, db: Session = Depends(get_db)):
    part = db.query(Part).filter_by(id=part_id).first()
    if not part:
        raise HTTPException(status_code=404, detail="Peça não encontrada")
    comps = db.query(Compatibility).filter_by(part_id=part_id).all()
    result = []
    for c in comps:
        v = db.query(Vehicle).filter_by(id=c.vehicle_id).first()
        if v:
            result.append({
                "id": c.id,
                "oem_code": c.oem_code,
                "notes": c.notes,
                "vehicle": {
                    "id": v.id,
                    "brand": v.brand,
                    "model": v.model,
                    "year_start": v.year_start,
                    "year_end": v.year_end,
                    "engine": v.engine,
                    "version": v.version,
                }
            })
    return result


@router.post("/")
def add_compatibility(data: CompatibilityCreate, db: Session = Depends(get_db)):
    existing = db.query(Compatibility).filter_by(
        part_id=data.part_id, vehicle_id=data.vehicle_id
    ).first()
    if existing:
        return existing
    comp = Compatibility(**data.model_dump())
    db.add(comp)
    db.commit()
    db.refresh(comp)
    return comp


@router.delete("/{comp_id}")
def remove_compatibility(comp_id: int, db: Session = Depends(get_db)):
    comp = db.query(Compatibility).filter_by(id=comp_id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Não encontrado")
    db.delete(comp)
    db.commit()
    return {"ok": True}


@router.get("/search-by-vehicle")
def search_by_vehicle(brand: str, model: str, year: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(Vehicle).filter(
        Vehicle.brand.ilike(f"%{brand}%"),
        Vehicle.model.ilike(f"%{model}%"),
    )
    if year:
        query = query.filter(
            Vehicle.year_start <= year,
            Vehicle.year_end >= year,
        )
    vehicles = query.all()
    if not vehicles:
        return []
    vehicle_ids = [v.id for v in vehicles]
    comps = db.query(Compatibility).filter(Compatibility.vehicle_id.in_(vehicle_ids)).all()
    part_ids = list({c.part_id for c in comps})
    parts = db.query(Part).filter(Part.id.in_(part_ids), Part.active == True, Part.quantity > 0).all()
    return parts
