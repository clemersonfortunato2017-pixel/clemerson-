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


async def get_item_visits(listing_id: str, headers: dict, client: httpx.AsyncClient) -> int:
    """Total de visitas do anúncio (endpoint só aceita 1 id por chamada —
    testado em 2026-07-21, `ids=A,B` dá erro 'maximum amount of items to
    query is 1'). Visitas atualizam com até 48h de atraso, isso é esperado."""
    try:
        r = await client.get(f"{ML_API}/visits/items", params={"ids": listing_id}, headers=headers, timeout=15)
        if r.status_code != 200:
            return 0
        data = r.json()
        return data.get(listing_id, 0) or 0
    except Exception:
        return 0


async def _resolve_brand_model_value_ids(client: httpx.AsyncClient, headers: dict, db: Session, vehicle: Vehicle) -> tuple[str | None, str | None]:
    """Resolve o value_id numérico de BRAND/MODEL no catálogo do ML pra um
    veículo — é isso (não o texto livre) que o ML exige pra achar produtos
    reais e aceitar a compatibilidade (ver _resolve... abaixo pra contexto
    completo do bug). Cacheado em Vehicle pra não repetir a busca a cada
    peça do mesmo modelo."""
    if vehicle.ml_brand_value_id and vehicle.ml_model_value_id:
        return vehicle.ml_brand_value_id, vehicle.ml_model_value_id

    r = await client.get(
        f"{ML_API}/products/search",
        params={"site_id": "MLB", "domain_id": "MLB-CARS_AND_VANS", "q": f"{vehicle.brand} {vehicle.model}"},
        headers=headers, timeout=15,
    )
    if r.status_code != 200:
        return None, None
    results = r.json().get("results", [])
    if not results:
        return None, None
    attrs = {a["id"]: a for a in results[0].get("attributes", [])}
    brand_id = attrs.get("BRAND", {}).get("value_id")
    model_id = attrs.get("MODEL", {}).get("value_id")
    if brand_id and model_id:
        vehicle.ml_brand_value_id = str(brand_id)
        vehicle.ml_model_value_id = str(model_id)
        db.commit()
    return brand_id, model_id


async def push_part_compatibility_to_ml(part_id: int, listing_id: str, db: Session, headers: dict, client: httpx.AsyncClient) -> dict:
    """Envia pro ML a compatibilidade de veículos que o Pitbox já tem no banco
    pra essa peça — sem isso o anúncio fica sem 'ficha técnica' e o ML marca
    'Inativo para revisar / Não indica os veículos compatíveis' (tag
    incomplete_compatibilities, confirmado em anúncios reais em 2026-07-22).

    LIÇÃO CARA — NUNCA REMOVER: BRAND/MODEL como texto livre (value_name)
    SEMPRE falha com "No products were found for the given product
    families", mesmo com domain_id/creation_source corretos. O ML só aceita
    porque o `products_families` casa contra PRODUTOS REAIS do catálogo
    (cada ano/versão/mercado de um modelo é um produto separado) — BRAND e
    MODEL precisam do `value_id` numérico do catálogo (constante por
    marca/modelo, ex: Ford=66432, Ka=68902), resolvido via
    GET /products/search?domain_id=MLB-CARS_AND_VANS&q={marca} {modelo}.
    Sem year_start, casa com TODOS os anos/versões do modelo — e se isso
    passar de 200 produtos, o ML recusa com "Maximum of 200 products...
    consider products families" (daí processar 1 ano por vez: nenhum
    modelo real chega perto de 200 variações num único ano)."""
    compats = db.query(Compatibility).filter(Compatibility.part_id == part_id).all()
    if not compats:
        return {"skipped": "peça sem compatibilidade cadastrada no Pitbox"}

    item_r = await client.get(f"{ML_API}/items/{listing_id}", headers=headers, timeout=15)
    item = item_r.json() if item_r.status_code == 200 else {}
    user_product_id = item.get("user_product_id")
    category_id = item.get("category_id")

    families = []
    pulados = []
    for c in compats:
        v = db.query(Vehicle).filter(Vehicle.id == c.vehicle_id).first()
        if not v:
            continue
        brand_id, model_id = await _resolve_brand_model_value_ids(client, headers, db, v)
        if not brand_id or not model_id:
            pulados.append(f"{v.brand} {v.model} (não encontrado no catálogo ML)")
            continue
        y1 = v.year_start or 0
        y2 = v.year_end or y1
        anos = range(y1, y2 + 1) if y1 else [None]
        for ano in anos:
            attrs = [
                {"id": "BRAND", "value_id": brand_id, "value_name": v.brand},
                {"id": "MODEL", "value_id": model_id, "value_name": v.model},
            ]
            if ano:
                attrs.append({"id": "VEHICLE_YEAR", "value_name": str(ano)})
            families.append({"domain_id": "MLB-CARS_AND_VANS", "creation_source": "DEFAULT", "attributes": attrs})

    if not families:
        return {"skipped": "nenhum veículo resolvido no catálogo ML", "detalhe": pulados}

    endpoint = (
        f"{ML_API}/user-products/{user_product_id}/compatibilities" if user_product_id
        else f"{ML_API}/items/{listing_id}/compatibilities"
    )

    async def enviar(lote: list[dict]):
        body = {"domain_id": "MLB-CARS_AND_VANS", "category_id": category_id, "products_families": lote}
        return await client.post(endpoint, headers=headers, json=body, timeout=30)

    # Duas restrições distintas do ML, confirmadas testando na prática
    # (2026-07-22): no máximo 10 "products_families" por request
    # ("size must be between 0 and 10") E no máximo 200 produtos
    # resolvidos no total ("Maximum of 200 products... consider products
    # families") — um veículo com muitos anos de compatibilidade estoura a
    # primeira, um modelo com muitas versões/mercados por ano estoura a
    # segunda. Processa em lotes de 10 famílias; se um lote estourar o
    # limite de produtos, refaz esse lote 1 família (ano) por vez.
    total_criadas = 0
    erros = []
    for i in range(0, len(families), 10):
        lote = families[i:i + 10]
        r = await enviar(lote)
        if r.status_code in (200, 201):
            total_criadas += r.json().get("created_compatibilities_count", 0)
        elif r.status_code == 400 and "Maximum of 200 products" in r.text:
            for familia in lote:
                r2 = await enviar([familia])
                if r2.status_code in (200, 201):
                    total_criadas += r2.json().get("created_compatibilities_count", 0)
                else:
                    erros.append({"familia": familia, "status": r2.status_code, "resposta": r2.text[:300]})
        else:
            erros.append({"lote": lote, "status": r.status_code, "resposta": r.text[:300]})

    # ok = nenhum lote falhou — created_compatibilities_count=0 sem erro
    # significa que a compatibilidade já existia (rodar de novo é
    # idempotente), não que falhou.
    return {
        "ok": not erros,
        "created_compatibilities_count": total_criadas,
        "erros": erros,
        "pulados": pulados,
        "user_product_id": user_product_id,
        "response": {"created_compatibilities_count": total_criadas, "erros": erros} if erros else {"created_compatibilities_count": total_criadas},
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
