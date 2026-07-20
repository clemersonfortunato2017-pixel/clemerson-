"""
Registro central de plataformas conectadas — multi-conta.

Cada plataforma pode ter N contas ativas (ex: Mercado Livre PJ + PF, Shopee
PJ). PlatformBase.publish/close/update_stock recebem o dict de conta
explicitamente — nada de credencial global escondida dentro da classe.

Pra adicionar plataforma nova: herdar PlatformBase, registrar em PLATFORMS.
Pra adicionar CONTA nova numa plataforma existente: usar o fluxo OAuth em
routes/platform_accounts.py (POST/GET /platform-accounts/{plataforma}/connect)
— não mexe em nenhuma linha deste arquivo.

A conta ML "legada" (a que já roda em produção via MLCredential + fallback
F:\\FORTUNATO AUTO PARTS\\ml_tokens.json) continua com seu próprio mecanismo,
intocado de propósito — é a única conta que não pode quebrar. Contas extras
(PlatformAccount) são só aditivas.
"""
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Optional
import httpx
from sqlalchemy.orm import Session
from app.models.part import Part, MarketplaceListing
from app.models.platform_account import PlatformAccount


class PlatformBase(ABC):
    name: str          # identificador interno (ex: "mercadolivre")
    display_name: str  # nome exibido (ex: "Mercado Livre")

    @abstractmethod
    async def publish(self, part: Part, account: dict) -> dict:
        """Publica peça na plataforma usando a conta informada. Retorna {listing_id, url} ou {error}."""
        ...

    @abstractmethod
    async def close(self, listing_id: str, account: dict) -> dict:
        """Encerra anúncio na plataforma usando a conta informada."""
        ...

    @abstractmethod
    async def update_stock(self, listing_id: str, quantity: int, account: dict) -> dict:
        """Atualiza estoque do anúncio usando a conta informada."""
        ...


# ---------------------------------------------------------------------------
# Resolução de contas (multi-conta)
# ---------------------------------------------------------------------------

async def _ml_legacy_account(db: Session) -> Optional[dict]:
    """Conta ML principal/legada — mecanismo já existente e comprovado em
    produção. Intocado de propósito: é a conta que já roda a esteira
    automática e o webhook de vendas, não pode quebrar por causa do multi-conta."""
    token, user_id = None, None
    try:
        from app.services.ml_importer import get_valid_access_token
        user_id, token = await get_valid_access_token(db)
    except Exception:
        pass

    if not token:
        import json, os
        tokens_file = r"F:\FORTUNATO AUTO PARTS\ml_tokens.json"
        if os.path.exists(tokens_file):
            with open(tokens_file, "r", encoding="utf-8-sig") as f:
                t = json.load(f)
                token, user_id = t.get("access_token"), t.get("user_id")
        else:
            from app.config import settings
            token, user_id = settings.ml_access_token, settings.ml_user_id

    if not token:
        return None
    return {
        "account_id": None,
        "platform": "mercadolivre",
        "label": "Mercado Livre — principal",
        "external_id": str(user_id) if user_id else None,
        "access_token": token,
        "extra": {},
    }


async def _ensure_fresh_extra_account(account: PlatformAccount, db: Session) -> Optional[dict]:
    """Renova token de uma PlatformAccount extra (multi-conta) se estiver
    perto de expirar, e devolve o dict pronto pra usar. Cada plataforma tem
    sua própria regra de refresh."""
    if not account or not account.active:
        return None

    now = datetime.now(timezone.utc)
    expires_at = account.token_expires_at
    needs_refresh = expires_at is not None and (
        expires_at.replace(tzinfo=timezone.utc) if expires_at.tzinfo is None else expires_at
    ) <= now

    if needs_refresh and account.refresh_token:
        if account.platform == "mercadolivre":
            from app.config import settings
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.post(
                    "https://api.mercadolibre.com/oauth/token",
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    data={
                        "grant_type": "refresh_token",
                        "client_id": settings.ml_app_id,
                        "client_secret": settings.ml_client_secret,
                        "refresh_token": account.refresh_token,
                    },
                )
            if r.status_code == 200:
                data = r.json()
                account.access_token = data["access_token"]
                account.refresh_token = data.get("refresh_token", account.refresh_token)
                account.token_expires_at = now + timedelta(seconds=data.get("expires_in", 21600) - 300)
                db.commit()
        elif account.platform == "shopee":
            from app.services.shopee_client import refresh_shopee_token
            data = await refresh_shopee_token(account.refresh_token, account.external_id)
            if data:
                account.access_token = data["access_token"]
                account.refresh_token = data.get("refresh_token", account.refresh_token)
                account.token_expires_at = now + timedelta(seconds=data.get("expire_in", 14400) - 300)
                db.commit()

    if not account.access_token:
        return None
    return {
        "account_id": account.id,
        "platform": account.platform,
        "label": account.label,
        "external_id": account.external_id,
        "access_token": account.access_token,
        "extra": account.extra or {},
    }


async def get_accounts_for_platform(platform_name: str, db: Session) -> list[dict]:
    """Todas as contas ATIVAS de uma plataforma: a legada (só existe pra ML)
    + as extras cadastradas em platform_accounts. É isso que todo fan-out
    (publish/sync) itera — adicionar conta nova não muda nenhuma linha de
    código aqui, só insere registro em platform_accounts."""
    accounts = []
    if platform_name == "mercadolivre":
        legacy = await _ml_legacy_account(db)
        if legacy:
            accounts.append(legacy)

    extra_rows = db.query(PlatformAccount).filter_by(platform=platform_name, active=True).all()
    for row in extra_rows:
        acc = await _ensure_fresh_extra_account(row, db)
        if acc:
            accounts.append(acc)
    return accounts


async def resolve_account_for_listing(listing: MarketplaceListing, db: Session) -> Optional[dict]:
    """Reconstrói o dict de conta a partir de uma listagem existente — usado
    quando preciso fechar/atualizar UM anúncio específico e já sei (pelo
    platform_account_id gravado nele) qual credencial usar, sem precisar
    adivinhar entre várias contas da mesma plataforma."""
    if listing.platform_account_id is None:
        if listing.marketplace == "mercadolivre":
            return await _ml_legacy_account(db)
        return None
    row = db.query(PlatformAccount).filter_by(id=listing.platform_account_id).first()
    if not row:
        return None
    return await _ensure_fresh_extra_account(row, db)


# ---------------------------------------------------------------------------
# Implementações por plataforma
# ---------------------------------------------------------------------------

class MercadoLivrePlatform(PlatformBase):
    name = "mercadolivre"
    display_name = "Mercado Livre"

    async def publish(self, part: Part, account: dict) -> dict:
        token = account.get("access_token")
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

    async def close(self, listing_id: str, account: dict) -> dict:
        token = account.get("access_token")
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

    async def update_stock(self, listing_id: str, quantity: int, account: dict) -> dict:
        token = account.get("access_token")
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

    async def publish(self, part: Part, account: dict) -> dict:
        if not account.get("access_token"):
            return {"error": "Shopee: conta não conectada (rode o fluxo OAuth em /platform-accounts/shopee/connect)"}
        from app.services.shopee_client import publish_item
        return await publish_item(part, account)

    async def close(self, listing_id: str, account: dict) -> dict:
        if not account.get("access_token"):
            return {"error": "Shopee: conta não conectada"}
        from app.services.shopee_client import unlist_item
        return await unlist_item(listing_id, account)

    async def update_stock(self, listing_id: str, quantity: int, account: dict) -> dict:
        if not account.get("access_token"):
            return {"error": "Shopee: conta não conectada"}
        from app.services.shopee_client import update_item_stock
        return await update_item_stock(listing_id, quantity, account)


class AmazonPlatform(PlatformBase):
    name = "amazon"
    display_name = "Amazon"

    async def publish(self, part: Part, account: dict) -> dict:
        return {"error": "Amazon: configure AMAZON_SELLER_ID e AMAZON_MWS_TOKEN no .env"}

    async def close(self, listing_id: str, account: dict) -> dict:
        return {"error": "Amazon não conectada"}

    async def update_stock(self, listing_id: str, quantity: int, account: dict) -> dict:
        return {"error": "Amazon não conectada"}


class MagaluPlatform(PlatformBase):
    name = "magalu"
    display_name = "Magazine Luiza"

    async def publish(self, part: Part, account: dict) -> dict:
        return {"error": "Magalu: parceria formal necessária — contact@magazineluiza.com.br"}

    async def close(self, listing_id: str, account: dict) -> dict:
        return {"error": "Magalu não conectada"}

    async def update_stock(self, listing_id: str, quantity: int, account: dict) -> dict:
        return {"error": "Magalu não conectada"}


class FacebookMarketplacePlatform(PlatformBase):
    name = "facebook"
    display_name = "Facebook Marketplace"

    async def publish(self, part: Part, account: dict) -> dict:
        from app.config import settings
        catalog_id = getattr(settings, "facebook_catalog_id", None)
        token = account.get("access_token")
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

    async def close(self, listing_id: str, account: dict) -> dict:
        from app.config import settings
        token = account.get("access_token")
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

    async def update_stock(self, listing_id: str, quantity: int, account: dict) -> dict:
        return await self.close(listing_id, account) if quantity == 0 else {"ok": True}


# Registro global de implementações de plataforma (uma instância por TIPO de
# plataforma — não por conta; contas são resolvidas à parte, ver acima)
PLATFORMS: dict[str, PlatformBase] = {
    p.name: p for p in [
        MercadoLivrePlatform(),
        ShopeePlatform(),
        AmazonPlatform(),
        MagaluPlatform(),
        FacebookMarketplacePlatform(),
    ]
}


async def get_platforms_status(db: Session) -> list[dict]:
    """Pra /platforms/status — quantas contas ativas cada plataforma tem."""
    result = []
    for platform in PLATFORMS.values():
        accounts = await get_accounts_for_platform(platform.name, db)
        result.append({
            "name": platform.name,
            "display_name": platform.display_name,
            "connected": len(accounts) > 0,
            "accounts": [{"account_id": a["account_id"], "label": a["label"], "external_id": a["external_id"]} for a in accounts],
        })
    return result


async def publish_to_all_accounts(part_id: int, db: Session) -> dict:
    """Publica a peça em TODAS as contas ativas (todas as plataformas, todas
    as contas dentro de cada plataforma) onde ela ainda não está listada.

    Chamado automaticamente pela esteira assim que a publicação principal é
    confirmada (routes/internal.py -> mark_published), e manualmente via
    POST /platforms/parts/{id}/publish-all."""
    part = db.query(Part).filter(Part.id == part_id).first()
    if not part:
        return {"error": "Peça não encontrada"}

    existing = {
        (l.marketplace, l.platform_account_id)
        for l in db.query(MarketplaceListing).filter(MarketplaceListing.part_id == part_id).all()
    }

    results = {}
    for platform_name, platform_impl in PLATFORMS.items():
        accounts = await get_accounts_for_platform(platform_name, db)
        for account in accounts:
            key = (platform_name, account["account_id"])
            if key in existing:
                results[account["label"]] = {"status": "already_listed"}
                continue
            r = await platform_impl.publish(part, account)
            if "listing_id" in r:
                listing = MarketplaceListing(
                    part_id=part.id,
                    marketplace=platform_name,
                    listing_id=r["listing_id"],
                    url=r.get("url", ""),
                    status="active",
                    price=part.sale_price,
                    platform_account_id=account["account_id"],
                )
                db.add(listing)
                results[account["label"]] = {"status": "published", "listing_id": r["listing_id"]}
            else:
                results[account["label"]] = {"status": "error", "detail": r.get("error")}

    db.commit()
    return results


async def close_on_all_accounts(part_id: int, db: Session) -> dict:
    """Encerra anúncios da peça em TODAS as contas/plataformas onde ela está listada."""
    listings = db.query(MarketplaceListing).filter(
        MarketplaceListing.part_id == part_id,
        MarketplaceListing.status == "active",
    ).all()

    results = {}
    for listing in listings:
        platform_impl = PLATFORMS.get(listing.marketplace)
        account = await resolve_account_for_listing(listing, db)
        key = f"{listing.marketplace}:{account['label'] if account else listing.platform_account_id}"
        if platform_impl and account:
            r = await platform_impl.close(listing.listing_id, account)
            listing.status = "closed"
            results[key] = r
        else:
            results[key] = {"error": "conta/plataforma não resolvida"}

    db.commit()
    return results


# Aliases (nomes antigos, mantidos pra não quebrar nenhum import existente
# fora deste arquivo — preferir os nomes _accounts acima em código novo)
publish_to_all_platforms = publish_to_all_accounts
close_on_all_platforms = close_on_all_accounts
