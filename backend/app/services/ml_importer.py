import httpx
import json
import os
from sqlalchemy.orm import Session
from app.models.part import Part, MarketplaceListing, Vehicle, Compatibility
from app.models.ml_credential import MLCredential

ML_API = "https://api.mercadolibre.com"
ML_TOKENS_FILE = r"F:\FORTUNATO AUTO PARTS\ml_tokens.json"
BATCH_SIZE = 20


async def get_valid_access_token(db: Session) -> tuple[str, str]:
    """Sempre renova o access_token via refresh_token antes de usar (evita expirar em 6h).
    O refresh_token mais recente fica salvo no banco (rotaciona a cada renovação)."""
    from app.config import settings

    cred = db.query(MLCredential).first()
    refresh_token = (cred.refresh_token if cred else None) or settings.ml_refresh_token

    if not refresh_token or not settings.ml_client_secret:
        return settings.ml_user_id, cred.access_token if cred else settings.ml_access_token

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{ML_API}/oauth/token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "refresh_token",
                "client_id": settings.ml_app_id,
                "client_secret": settings.ml_client_secret,
                "refresh_token": refresh_token,
            },
        )
        r.raise_for_status()
        data = r.json()

    new_access = data["access_token"]
    new_refresh = data.get("refresh_token", refresh_token)
    user_id = str(data.get("user_id") or settings.ml_user_id)

    if cred:
        cred.access_token = new_access
        cred.refresh_token = new_refresh
    else:
        cred = MLCredential(access_token=new_access, refresh_token=new_refresh)
        db.add(cred)
    db.commit()

    return user_id, new_access


def get_ml_credentials():
    """Legado: leitura estática (só usada como fallback caso a renovação via refresh_token falhe)."""
    if os.path.exists(ML_TOKENS_FILE):
        with open(ML_TOKENS_FILE, "r", encoding="utf-8-sig") as f:
            t = json.load(f)
            return str(t.get("user_id", "")), t.get("access_token", "")
    from app.config import settings
    return settings.ml_user_id, settings.ml_access_token


async def fetch_all_item_ids(user_id: str, headers: dict, client: httpx.AsyncClient) -> list[str]:
    ids = []
    offset = 0
    limit = 50
    while True:
        url = f"{ML_API}/users/{user_id}/items/search?status=active&limit={limit}&offset={offset}"
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()
        batch_ids = data.get("results", [])
        if not batch_ids:
            break
        ids.extend(batch_ids)
        offset += limit
        if offset >= data.get("paging", {}).get("total", 0):
            break
    return ids


async def fetch_items_detail(ids: list[str], headers: dict, client: httpx.AsyncClient) -> list[dict]:
    items = []
    for i in range(0, len(ids), BATCH_SIZE):
        batch = ids[i:i + BATCH_SIZE]
        url = f"{ML_API}/items?ids={','.join(batch)}"
        r = await client.get(url, headers=headers)
        if r.status_code != 200:
            continue
        for entry in r.json():
            if isinstance(entry, dict) and entry.get("code") == 200:
                items.append(entry["body"])
    return items


def _get_attr(attributes: list, attr_id: str) -> str | None:
    for a in attributes:
        if a.get("id") == attr_id:
            return a.get("value_name")
    return None


def _parse_years(year_str: str | None):
    """Parse '2017-2020' or '2017' into (year_start, year_end)."""
    if not year_str:
        return None, None
    parts = str(year_str).split("-")
    try:
        y1 = int(parts[0].strip())
        y2 = int(parts[1].strip()) if len(parts) > 1 else y1
        return y1, y2
    except (ValueError, IndexError):
        return None, None


def _get_or_create_vehicle(db: Session, brand: str, model: str, year_start, year_end, engine: str | None) -> Vehicle:
    """Find existing vehicle or create new one."""
    q = db.query(Vehicle).filter(
        Vehicle.brand == brand,
        Vehicle.model == model,
        Vehicle.year_start == year_start,
        Vehicle.year_end == year_end,
    )
    if engine:
        q = q.filter(Vehicle.engine == engine)
    v = q.first()
    if not v:
        v = Vehicle(brand=brand, model=model, year_start=year_start, year_end=year_end, engine=engine)
        db.add(v)
        db.flush()
    return v


async def sync_part_compatibility(part_id: int, listing_id: str, db: Session, headers: dict, client: httpx.AsyncClient) -> int:
    """Fetch compatibility list from ML for one listing and save to DB. Returns count of vehicles added."""
    try:
        r = await client.get(f"{ML_API}/items/{listing_id}/compatibilities", headers=headers, timeout=15)
        if r.status_code != 200:
            return 0
        data = r.json()
    except Exception:
        return 0

    compatibilities = data.get("compatibilities", [])
    if not compatibilities:
        return 0

    # Existing vehicle_ids already linked to this part
    existing_vehicle_ids = {
        c.vehicle_id for c in db.query(Compatibility).filter(Compatibility.part_id == part_id).all()
    }

    added = 0
    for compat in compatibilities:
        attrs = compat.get("attributes", [])
        brand = _get_attr(attrs, "BRAND") or _get_attr(attrs, "MAKE")
        model = _get_attr(attrs, "MODEL")
        engine = _get_attr(attrs, "ENGINE_VERSION") or _get_attr(attrs, "ENGINE")
        year_str = _get_attr(attrs, "YEARS") or _get_attr(attrs, "VEHICLE_YEAR")

        if not brand or not model:
            # Try to parse from product name
            product_name = compat.get("product", {}).get("name", "")
            if not brand and product_name:
                brand = product_name.split()[0] if product_name else None
            if not model and product_name:
                parts = product_name.split()
                model = parts[1] if len(parts) > 1 else None

        if not brand or not model:
            continue

        year_start, year_end = _parse_years(year_str)
        vehicle = _get_or_create_vehicle(db, brand.title(), model.title(), year_start, year_end, engine)

        if vehicle.id not in existing_vehicle_ids:
            oem = _get_attr(attrs, "PART_NUMBER") or _get_attr(attrs, "OEM_CODE")
            link = Compatibility(part_id=part_id, vehicle_id=vehicle.id, oem_code=oem)
            db.add(link)
            existing_vehicle_ids.add(vehicle.id)
            added += 1

    return added


async def push_part_compatibility_to_ml(part_id: int, listing_id: str, db: Session, headers: dict, client: httpx.AsyncClient) -> dict:
    """Envia pro ML a compatibilidade de veículos que o Pitbox já tem no banco
    pra essa peça — sem isso o anúncio fica sem 'ficha técnica' e o ML marca
    'Inativo para revisar / Não indica os veículos compatíveis' depois de uns
    dias (visto em anúncios reais em 2026-07-20).

    Formato correto descoberto na documentação oficial (a 1ª tentativa, com
    {"compatibilities": [{"attributes": ...}]}, é da API antiga e o ML recusa
    com "products, products_groups, products_families, universal ou item to
    copy" ausentes): precisa do wrapper `products_families`, com `domain_id`
    do domínio de veículos e `creation_source` (obrigatório desde a mudança
    de política do ML)."""
    compats = db.query(Compatibility).filter(Compatibility.part_id == part_id).all()
    if not compats:
        return {"skipped": "peça sem compatibilidade cadastrada no Pitbox"}

    families = []
    for c in compats:
        v = db.query(Vehicle).filter(Vehicle.id == c.vehicle_id).first()
        if not v:
            continue
        attrs = [
            {"id": "BRAND", "value_name": v.brand},
            {"id": "MODEL", "value_name": v.model},
        ]
        if v.year_start:
            years = str(v.year_start) if v.year_start == v.year_end or not v.year_end else f"{v.year_start}-{v.year_end}"
            attrs.append({"id": "YEARS", "value_name": years})
        if v.engine:
            attrs.append({"id": "ENGINE_VERSION", "value_name": v.engine})
        families.append({
            "domain_id": "MLB-CARS_AND_VANS",
            "creation_source": "DEFAULT",
            "attributes": attrs,
        })

    if not families:
        return {"skipped": "nenhum veículo válido pra enviar"}

    r = await client.post(
        f"{ML_API}/items/{listing_id}/compatibilities",
        headers=headers,
        json={"products_families": families},
        timeout=20,
    )
    return {
        "status_code": r.status_code,
        "ok": r.status_code in (200, 201),
        "sent": families,
        "response": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:500],
    }


async def import_from_ml(db: Session) -> dict:
    debug_error = None
    try:
        user_id, access_token = await get_valid_access_token(db)
    except Exception as e:
        debug_error = f"{type(e).__name__}: {e}"
        user_id, access_token = get_ml_credentials()

    if not user_id or not access_token:
        return {"error": "Credenciais do Mercado Livre não configuradas", "debug": debug_error}

    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient(timeout=60) as client:
        all_ids = await fetch_all_item_ids(user_id, headers, client)
        items = await fetch_items_detail(all_ids, headers, client)

    created = 0
    updated = 0
    compat_total = 0

    async with httpx.AsyncClient(timeout=60) as client:
        for item in items:
            photos = [p["url"] for p in item.get("pictures", [])]
            price = float(item.get("price") or 0)
            part_data = {
                "code": item["id"],
                "title": item.get("title", ""),
                "category": item.get("category_id", ""),
                "condition": item.get("condition", "used"),
                "sale_price": price,
                "suggested_price": price,
                "quantity": item.get("available_quantity", 0),
                "photos": photos,
                "active": item.get("status") == "active",
            }

            existing_listing = db.query(MarketplaceListing).filter_by(listing_id=item["id"]).first()

            if existing_listing:
                part = db.query(Part).filter_by(id=existing_listing.part_id).first()
                if part:
                    for k, v in part_data.items():
                        setattr(part, k, v)
                    existing_listing.status = item.get("status")
                    existing_listing.price = price
                    updated += 1
                    # Sync compatibility on update too
                    added = await sync_part_compatibility(part.id, item["id"], db, headers, client)
                    compat_total += added
            else:
                part = Part(**part_data)
                db.add(part)
                db.flush()
                listing = MarketplaceListing(
                    part_id=part.id,
                    marketplace="mercadolivre",
                    listing_id=item["id"],
                    url=item.get("permalink", ""),
                    status=item.get("status"),
                    price=price,
                )
                db.add(listing)
                created += 1
                # Sync compatibility for new parts
                added = await sync_part_compatibility(part.id, item["id"], db, headers, client)
                compat_total += added

    db.commit()
    return {"created": created, "updated": updated, "total": len(items), "compatibilities_added": compat_total}


async def sync_all_compatibility(db: Session) -> dict:
    """Re-sync compatibility for ALL parts that have a ML listing."""
    user_id, access_token = get_ml_credentials()
    if not user_id or not access_token:
        return {"error": "Credenciais do Mercado Livre não configuradas"}

    headers = {"Authorization": f"Bearer {access_token}"}
    listings = db.query(MarketplaceListing).filter(MarketplaceListing.marketplace == "mercadolivre").all()

    total_added = 0
    processed = 0

    async with httpx.AsyncClient(timeout=60) as client:
        for listing in listings:
            added = await sync_part_compatibility(listing.part_id, listing.listing_id, db, headers, client)
            total_added += added
            processed += 1
            if processed % 50 == 0:
                db.commit()

    db.commit()
    return {"processed": processed, "compatibilities_added": total_added}
