"""
Extrai compatibilidade de veículos a partir do título da peça.
Cobre as marcas mais comuns no mercado brasileiro.
"""
import re
from sqlalchemy.orm import Session
from app.models.part import Part, Vehicle, Compatibility

# Marcas conhecidas (ordem importa — mais específicas primeiro)
BRANDS = [
    "Volkswagen", "Chevrolet", "Fiat", "Ford", "Honda", "Toyota",
    "Hyundai", "Renault", "Nissan", "Peugeot", "Citroën", "Citroen",
    "Mitsubishi", "Kia", "Jeep", "Land Rover", "Landrover",
    "BMW", "Mercedes", "Audi", "Volvo", "Suzuki", "Subaru",
    "Dodge", "Chrysler", "Jac", "Chery", "Caoa", "BYD",
]

# Abreviações/apelidos → marca canônica
BRAND_ALIASES = {
    "VW": "Volkswagen", "GM": "Chevrolet", "GE": "General Electric",
    "MB": "Mercedes-Benz", "Merc": "Mercedes-Benz",
    "Citroen": "Citroën", "Landrover": "Land Rover",
}

# Modelos por marca — lista dos mais comuns no BR
MODELS_BY_BRAND = {
    "Volkswagen": [
        "Gol", "Voyage", "Saveiro", "Fox", "Golf", "Jetta", "Passat",
        "Polo", "Virtus", "T-Cross", "Tiguan", "Touareg", "Amarok",
        "Up", "Kombi", "Fusca", "Parati", "Quantum", "Santana",
        "G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8",
    ],
    "Chevrolet": [
        "Onix", "Prisma", "Cobalt", "Cruze", "Celta", "Corsa",
        "Classic", "Agile", "Montana", "S10", "Spin", "Tracker",
        "Equinox", "Trailblazer", "Captiva", "Zafira", "Vectra",
        "Astra", "Kadett", "Monza", "Omega", "Blazer", "Silverado",
    ],
    "Fiat": [
        "Uno", "Palio", "Siena", "Strada", "Doblò", "Doblo", "Bravo",
        "Punto", "Linea", "Freemont", "Toro", "Argo", "Cronos",
        "Mobi", "Pulse", "Fastback", "500", "Ducato", "Fiorino",
        "Tipo", "Tempra", "Elba",
    ],
    "Ford": [
        "Ka", "Fiesta", "Focus", "Ecosport", "Edge", "Fusion",
        "Territory", "Bronco", "Maverick", "Ranger", "F-250", "F250",
        "Courier", "Escort", "Mondeo", "Galaxy", "Transit", "Cargo",
        "Del Rey", "Pampa", "Verona",
    ],
    "Honda": [
        "Civic", "City", "Fit", "HRV", "CRV", "HR-V", "CR-V",
        "WRV", "WR-V", "Accord", "Pilot", "Ridgeline", "CR-Z",
        "Jazz", "Element", "Odyssey",
    ],
    "Toyota": [
        "Corolla", "Yaris", "Etios", "Hilux", "SW4", "RAV4",
        "Camry", "Prius", "Land Cruiser", "Bandeirante",
        "Fortuner", "Prado",
    ],
    "Hyundai": [
        "HB20", "HB20S", "Creta", "Tucson", "Santa Fe", "Veloster",
        "Elantra", "Sonata", "Azera", "IX35", "i30",
    ],
    "Renault": [
        "Sandero", "Logan", "Kwid", "Captur", "Duster", "Oroch",
        "Fluence", "Megane", "Clio", "Scenic", "Zoe", "Master",
    ],
    "Nissan": [
        "Kicks", "Versa", "Sentra", "Tiida", "Livina", "March",
        "Frontier", "Pathfinder", "X-Trail", "Murano",
    ],
}

# Todos os modelos em lowercase para busca rápida
_ALL_MODELS: dict[str, str] = {}  # modelo_lower → marca
for _brand, _models in MODELS_BY_BRAND.items():
    for _m in _models:
        _ALL_MODELS[_m.lower()] = _brand


def _normalize_title(title: str) -> str:
    return title.replace("â€™", "'").replace("ã¢", "").replace("�", "")


def _find_brand(title_lower: str) -> str | None:
    # Verificar aliases primeiro
    for alias, canonical in BRAND_ALIASES.items():
        if re.search(r'\b' + re.escape(alias.lower()) + r'\b', title_lower):
            return canonical
    # Verificar marcas diretas
    for brand in BRANDS:
        if re.search(r'\b' + re.escape(brand.lower()) + r'\b', title_lower):
            return brand
    return None


def _find_models(title_lower: str, brand: str | None) -> list[str]:
    """Retorna lista de modelos encontrados no título."""
    found = []
    # Se temos marca, priorizar modelos dela
    priority = MODELS_BY_BRAND.get(brand, []) if brand else []
    all_models = priority + [m for m in _ALL_MODELS if m not in [p.lower() for p in priority]]

    for model_str in priority:
        pat = r'\b' + re.escape(model_str.lower()) + r'\b'
        if re.search(pat, title_lower):
            if model_str not in found:
                found.append(model_str)

    if not found:
        # Busca global se nenhum modelo da marca foi achado
        for model_lower, mbrand in _ALL_MODELS.items():
            pat = r'\b' + re.escape(model_lower) + r'\b'
            if re.search(pat, title_lower):
                # Recuperar case original
                original = next(
                    m for models in MODELS_BY_BRAND.values() for m in models
                    if m.lower() == model_lower
                )
                if original not in found:
                    found.append(original)
    return found


def _find_years(title: str) -> tuple[int | None, int | None]:
    """Extrai anos do título. Padrões: 2016-2019, 2016/2019, 2016 A 2019, 2016."""
    # Faixa: 2016-2019 ou 2016/2019
    m = re.search(r'\b(20\d{2})\s*[-/]\s*(20\d{2})\b', title)
    if m:
        return int(m.group(1)), int(m.group(2))
    # "2016 A 2019" ou "2016 a 2019"
    m = re.search(r'\b(20\d{2})\s+[aA]\s+(20\d{2})\b', title)
    if m:
        return int(m.group(1)), int(m.group(2))
    # Ano único
    m = re.search(r'\b(20\d{2})\b', title)
    if m:
        y = int(m.group(1))
        return y, y
    # Ano 4 dígitos começando com 19
    m = re.search(r'\b(19\d{2})\s*[-/]\s*((?:19|20)\d{2})\b', title)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r'\b(19\d{2})\b', title)
    if m:
        y = int(m.group(1))
        return y, y
    return None, None


def parse_title(title: str) -> list[dict]:
    """
    Retorna lista de dicts {brand, model, year_start, year_end}
    extraídos do título. Pode retornar múltiplos (ex: Onix + Prisma).
    """
    t_lower = _normalize_title(title).lower()
    brand = _find_brand(t_lower)
    models = _find_models(t_lower, brand)
    year_start, year_end = _find_years(title)

    if not models:
        return []

    results = []
    for model in models:
        # Se não achou marca diretamente, pegar a da tabela de modelos
        b = brand or _ALL_MODELS.get(model.lower())
        if b:
            results.append({
                "brand": b,
                "model": model,
                "year_start": year_start,
                "year_end": year_end,
            })
    return results


def _get_or_create_vehicle(db: Session, brand: str, model: str, y1, y2) -> Vehicle:
    v = db.query(Vehicle).filter(
        Vehicle.brand == brand,
        Vehicle.model == model,
        Vehicle.year_start == y1,
        Vehicle.year_end == y2,
    ).first()
    if not v:
        v = Vehicle(brand=brand, model=model, year_start=y1, year_end=y2)
        db.add(v)
        db.flush()
    return v


def sync_compat_from_titles(db: Session) -> dict:
    """Percorre todas as peças ativas e cria compatibilidades a partir do título."""
    parts = db.query(Part).filter(Part.active == True).all()
    added = 0
    skipped = 0

    for part in parts:
        parsed = parse_title(part.title or "")
        if not parsed:
            skipped += 1
            continue

        existing_vids = {
            c.vehicle_id
            for c in db.query(Compatibility).filter(Compatibility.part_id == part.id).all()
        }

        for entry in parsed:
            vehicle = _get_or_create_vehicle(
                db, entry["brand"], entry["model"],
                entry["year_start"], entry["year_end"]
            )
            if vehicle.id not in existing_vids:
                db.add(Compatibility(part_id=part.id, vehicle_id=vehicle.id))
                existing_vids.add(vehicle.id)
                added += 1

    db.commit()
    return {"parts_processed": len(parts), "skipped": skipped, "compatibilities_added": added}
