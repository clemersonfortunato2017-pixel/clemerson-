"""
Registro central de plataformas conectadas.
Cada plataforma implementa publish(), update(), close() e get_status().
Para adicionar nova plataforma: criar classe herdando PlatformBase e registrar em PLATFORMS.
"""
from abc import ABC, abstractmethod
from typing import Optional
import httpx
from sqlalchemy.orm import Session
from app.models.part import Part, MarketplaceListing


class PlatformBase(ABC):
    name: str          # identificador interno (ex: "mercadolivre")
    display_name: str  # nome exibido (ex: "Mercado Livre")

    @abstractmethod
    async def publish(self, part: Part, db: Session) -> dict:
        """Publica peça na plataforma. Retorna {listing_id, url} ou {error}."""
        ...

    @abstractmethod
    async def close(self, listing_id: str) -> dict:
        """Encerra anúncio na plataforma."""
        ...

    @abstractmethod
    async def update_stock(self, listing_id: str, quantity: int) -> dict:
        """Atualiza estoque do anúncio."""
        ...

    def is_connected(self) -> bool:
        """Retorna True se as credenciais estão configuradas."""
        return False


class MercadoLivrePlatform(PlatformBase):
    name = "mercadolivre"
    display_name = "Mercado Livre"

    def _get_token(self, db: Session = None):
        """Token ML: prioriza o Postgres (MLCredential, mantido fresco por
        get_valid_access_token) — só cai pro HD externo F: se a migração de
        credencial ainda não rodou. A esteira automática (rotina agendada)
        sempre passa `db`, então nunca depende do F: em produção."""
        if db is not None:
            from app.models.ml_credential import MLCredential
            cred = db.query(MLCredential).first()
            if cred and cred.access_token:
                from app.config import settings
                return cred.access_token, settings.ml_user_id

        import json, os
        tokens_file = r"F:\FORTUNATO AUTO PARTS\ml_tokens.json"
        if os.path.exists(tokens_file):
            with open(tokens_file, "r", encoding="utf-8-sig") as f:
                t = json.load(f)
                return t.get("access_token"), t.get("user_id")
        from app.config import settings
        return settings.ml_access_token, settings.ml_user_id

    def is_connected(self) -> bool:
        token, _ = self._get_token()
        return bool(token)

    async def publish(self, part: Part, db: Session) -> dict:
        token, user_id = self._get_token(db)
        if not token:
            return {"error": "ML não conectado"}

        # Payload conforme regras fixas da skill anuncio-ml-autopecas (Passo 7)
        payload = {
            "title": part.title[:60],
            "category_id": part.category or "MLB3937",  # categoria genérica autopeças
            "price": part.sale_price or 1.0,
            "currency_id": "BRL",
            "available_quantity": max(part.quantity, 1),
            "buying_mode": "buy_it_now",
            "listing_type_id": "gold_pro",
            "condition": "new" if part.condition == "new" else "used",
            "shipping": {"free_shipping": True},
            "pictures": [{"source": url} for url in (part.photos or [])[:12]],
        }

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post("https://api.mercadolibre.com/items", json=payload, headers=headers)
            if r.status_code in (200, 201):
                data = r.json()
                return {"listing_id": data["id"], "url": data.get("permalink", "")}
            return {"error": f"ML {r.status_code}: {r.text[:200]}"}

    async def close(self, listing_id: str) -> dict:
        token, _ = self._get_token()
        if not token:
            return {"error": "ML não conectado"}
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.put(
                f"https://api.mercadolibre.com/items/{listing_id}",
                json={"status": "closed"},
                headers=headers,
            )
            return {"ok": r.status_code == 200, "status": r.status_code}

    async def update_stock(self, listing_id: str, quantity: int) -> dict:
        token, _ = self._get_token()
        if not token:
            return {"error": "ML não conectado"}
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.put(
                f"https://api.mercadolibre.com/items/{listing_id}",
                json={"available_quantity": max(quantity, 0)},
                headers=headers,
            )
            return {"ok": r.status_code == 200}


class ShopeePlatform(PlatformBase):
    name = "shopee"
    display_name = "Shopee"

    def is_connected(self) -> bool:
        from app.config import settings
        return bool(getattr(settings, "shopee_partner_id", None))

    async def publish(self, part: Part, db: Session) -> dict:
        return {"error": "Shopee: configure SHOPEE_PARTNER_ID e SHOPEE_PARTNER_KEY no .env"}

    async def close(self, listing_id: str) -> dict:
        return {"error": "Shopee não conectada"}

    async def update_stock(self, listing_id: str, quantity: int) -> dict:
        return {"error": "Shopee não conectada"}


class AmazonPlatform(PlatformBase):
    name = "amazon"
    display_name = "Amazon"

    def is_connected(self) -> bool:
        from app.config import settings
        return bool(getattr(settings, "amazon_seller_id", None))

    async def publish(self, part: Part, db: Session) -> dict:
        return {"error": "Amazon: configure AMAZON_SELLER_ID e AMAZON_MWS_TOKEN no .env"}

    async def close(self, listing_id: str) -> dict:
        return {"error": "Amazon não conectada"}

    async def update_stock(self, listing_id: str, quantity: int) -> dict:
        return {"error": "Amazon não conectada"}


class MagaluPlatform(PlatformBase):
    name = "magalu"
    display_name = "Magazine Luiza"

    def is_connected(self) -> bool:
        return False

    async def publish(self, part: Part, db: Session) -> dict:
        return {"error": "Magalu: parceria formal necessária — contact@magazineluiza.com.br"}

    async def close(self, listing_id: str) -> dict:
        return {"error": "Magalu não conectada"}

    async def update_stock(self, listing_id: str, quantity: int) -> dict:
        return {"error": "Magalu não conectada"}


class FacebookMarketplacePlatform(PlatformBase):
    name = "facebook"
    display_name = "Facebook Marketplace"

    def is_connected(self) -> bool:
        from app.config import settings
        return bool(getattr(settings, "facebook_page_token", None))

    async def publish(self, part: Part, db: Session) -> dict:
        """
        Facebook Commerce Catalog API.
        Requer: Business Manager + Catálogo aprovado + Page Access Token.
        Configure FACEBOOK_CATALOG_ID e FACEBOOK_PAGE_TOKEN no .env.
        """
        from app.config import settings
        catalog_id = getattr(settings, "facebook_catalog_id", None)
        token = getattr(settings, "facebook_page_token", None)
        if not catalog_id or not token:
            return {"error": "Facebook: configure FACEBOOK_CATALOG_ID e FACEBOOK_PAGE_TOKEN no .env"}

        payload = {
            "name": part.title[:100],
            "description": part.notes or part.title,
            "price": int((part.sale_price or 0) * 100),  # centavos
            "currency": "BRL",
            "availability": "in stock" if part.quantity > 0 else "out of stock",
            "condition": "new" if part.condition == "new" else "used",
            "image_url": (part.photos or [""])[0],
            "url": f"https://fortunatoautoparts.com.br/pecas/{part.id}",
        }
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                f"https://graph.facebook.com/v18.0/{catalog_id}/products",
                params={"access_token": token},
                json=payload,
            )
            if r.status_code == 200:
                return {"listing_id": r.json().get("id"), "url": ""}
            return {"error": f"Facebook {r.status_code}: {r.text[:200]}"}

    async def close(self, listing_id: str) -> dict:
        from app.config import settings
        token = getattr(settings, "facebook_page_token", None)
        catalog_id = getattr(settings, "facebook_catalog_id", None)
        if not token:
            return {"error": "Facebook não conectado"}
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"https://graph.facebook.com/v18.0/{catalog_id}/products",
                params={"access_token": token},
                json={"id": listing_id, "availability": "out of stock"},
            )
            return {"ok": r.status_code == 200}

    async def update_stock(self, listing_id: str, quantity: int) -> dict:
        return await self.close(listing_id) if quantity == 0 else {"ok": True}


# Registro global de plataformas
PLATFORMS: dict[str, PlatformBase] = {
    p.name: p for p in [
        MercadoLivrePlatform(),
        ShopeePlatform(),
        AmazonPlatform(),
        MagaluPlatform(),
        FacebookMarketplacePlatform(),
    ]
}


def get_connected_platforms() -> list[PlatformBase]:
    return [p for p in PLATFORMS.values() if p.is_connected()]


async def close_on_all_platforms(part_id: int, db: Session) -> dict:
    """Encerra anúncios da peça em TODAS as plataformas onde ela está listada."""
    listings = db.query(MarketplaceListing).filter(
        MarketplaceListing.part_id == part_id,
        MarketplaceListing.status == "active",
    ).all()

    results = {}
    for listing in listings:
        platform = PLATFORMS.get(listing.marketplace)
        if platform:
            r = await platform.close(listing.listing_id)
            listing.status = "closed"
            results[listing.marketplace] = r
        else:
            results[listing.marketplace] = {"error": "plataforma desconhecida"}

    db.commit()
    return results


async def publish_to_all_platforms(part_id: int, db: Session) -> dict:
    """Publica peça em todas as plataformas conectadas onde ela ainda não está listada."""
    part = db.query(Part).filter(Part.id == part_id).first()
    if not part:
        return {"error": "Peça não encontrada"}

    existing = {l.marketplace for l in db.query(MarketplaceListing).filter(
        MarketplaceListing.part_id == part_id
    ).all()}

    results = {}
    for platform in get_connected_platforms():
        if platform.name in existing:
            results[platform.name] = {"status": "already_listed"}
            continue
        r = await platform.publish(part, db)
        if "listing_id" in r:
            listing = MarketplaceListing(
                part_id=part.id,
                marketplace=platform.name,
                listing_id=r["listing_id"],
                url=r.get("url", ""),
                status="active",
                price=part.sale_price,
            )
            db.add(listing)
            results[platform.name] = {"status": "published", "listing_id": r["listing_id"]}
        else:
            results[platform.name] = {"status": "error", "detail": r.get("error")}

    db.commit()
    return results
