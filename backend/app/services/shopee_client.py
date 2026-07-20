"""Cliente Shopee Open Platform V2 — OAuth, publicação, estoque e leitura de
pedido, mais verificação de assinatura do push de pedidos.

Pré-requisito real (fora do nosso controle): SHOPEE_PARTNER_ID e
SHOPEE_PARTNER_KEY no .env, que só existem depois de a Shopee aprovar um app
em open.shopee.com (cadastro de desenvolvedor + revisão deles). Sem isso,
toda função aqui recebe conta sem access_token e as chamadas do
ShopeePlatform em platform_registry.py voltam erro "Shopee: conta não
conectada" sem nunca tentar a rede.

Depois que o app for aprovado:
1. Configurar SHOPEE_PARTNER_ID / SHOPEE_PARTNER_KEY no .env de produção.
2. Definir SHOPEE_DEFAULT_CATEGORY_ID (categoria de autopeças usadas no
   catálogo da Shopee — não tem fallback genérico como o MLB3937 do ML).
3. Chamar GET /platform-accounts/shopee/connect?label=Shopee - PJ Fortunato
   logado no Pitbox, abrir a auth_url retornada LOGADO NA LOJA SHOPEE PJ, e
   autorizar — o callback grava o access_token/refresh_token/shop_id.
4. Configurar no painel do Shopee Open Platform a URL de push de pedidos
   apontando pra POST {PUBLIC_BASE_URL}/webhooks/shopee.
"""
import hashlib
import hmac
import time
import httpx
from app.config import settings

SHOPEE_HOST = "https://partner.shopeemobile.com"


def _sign(path: str, timestamp: int, extra: str = "") -> str:
    base = f"{settings.shopee_partner_id}{path}{timestamp}{extra}"
    return hmac.new(settings.shopee_partner_key.encode(), base.encode(), hashlib.sha256).hexdigest()


def get_auth_url(redirect_uri: str) -> str:
    ts = int(time.time())
    path = "/api/v2/shop/auth_partner"
    sign = _sign(path, ts)
    return (
        f"{SHOPEE_HOST}{path}?partner_id={settings.shopee_partner_id}"
        f"&redirect={redirect_uri}&timestamp={ts}&sign={sign}"
    )


async def exchange_code(code: str, shop_id: str) -> dict | None:
    ts = int(time.time())
    path = "/api/v2/auth/token/get"
    sign = _sign(path, ts)
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            f"{SHOPEE_HOST}{path}?partner_id={settings.shopee_partner_id}&timestamp={ts}&sign={sign}",
            json={"code": code, "shop_id": int(shop_id), "partner_id": int(settings.shopee_partner_id)},
        )
    if r.status_code == 200:
        data = r.json()
        if "access_token" in data:
            return data
    return None


async def refresh_shopee_token(refresh_token: str, shop_id: str) -> dict | None:
    if not refresh_token or not shop_id:
        return None
    ts = int(time.time())
    path = "/api/v2/auth/access_token/get"
    sign = _sign(path, ts)
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            f"{SHOPEE_HOST}{path}?partner_id={settings.shopee_partner_id}&timestamp={ts}&sign={sign}",
            json={"refresh_token": refresh_token, "shop_id": int(shop_id), "partner_id": int(settings.shopee_partner_id)},
        )
    if r.status_code == 200:
        data = r.json()
        if "access_token" in data:
            return data
    return None


def _signed_url(path: str, account: dict) -> str:
    ts = int(time.time())
    shop_id = account.get("external_id")
    sign = _sign(path, ts, extra=f"{account['access_token']}{shop_id}")
    return (
        f"{SHOPEE_HOST}{path}?partner_id={settings.shopee_partner_id}&timestamp={ts}"
        f"&access_token={account['access_token']}&shop_id={shop_id}&sign={sign}"
    )


async def upload_image(url_source: str, account: dict) -> str | None:
    """Shopee exige imagem enviada pelo endpoint deles (não aceita URL externa
    direto no cadastro do item) — baixa a foto já hospedada pelo Pitbox e reenvia."""
    async with httpx.AsyncClient(timeout=30) as client:
        img = await client.get(url_source)
        if img.status_code != 200:
            return None
        url = _signed_url("/api/v2/media_space/upload_image", account)
        r = await client.post(url, files={"image": ("photo.jpg", img.content, "image/jpeg")})
    if r.status_code == 200:
        data = r.json()
        return (data.get("response") or {}).get("image_info", {}).get("image_id")
    return None


async def publish_item(part, account: dict) -> dict:
    if not settings.shopee_default_category_id:
        return {"error": "Shopee: SHOPEE_DEFAULT_CATEGORY_ID não configurado no .env"}

    image_ids = []
    for photo_url in (part.photos or [])[:9]:
        img_id = await upload_image(photo_url, account)
        if img_id:
            image_ids.append(img_id)
    if not image_ids:
        return {"error": "Shopee: nenhuma foto pôde ser enviada"}

    url = _signed_url("/api/v2/product/add_item", account)
    payload = {
        "item_name": part.title[:120],
        "description": part.notes or part.title,
        "item_sku": part.code_internal or str(part.id),
        "price_info": [{"currency": "BRL", "original_price": part.sale_price or 1.0}],
        "stock_info": [{"stock_type": 1, "stock": max(part.quantity, 1)}],
        "category_id": int(settings.shopee_default_category_id),
        "image": {"image_id_list": image_ids},
        "weight": part.weight or 0.3,
        "condition": "USED" if part.condition == "used" else "NEW",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json=payload)
    if r.status_code == 200:
        data = r.json()
        body = data.get("response", {})
        if "item_id" in body:
            return {"listing_id": str(body["item_id"]), "url": ""}
        return {"error": str(data.get("error") or data.get("message") or r.text[:200])}
    return {"error": f"Shopee {r.status_code}: {r.text[:200]}"}


async def update_item_stock(item_id: str, quantity: int, account: dict) -> dict:
    url = _signed_url("/api/v2/product/update_stock", account)
    payload = {
        "item_id": int(item_id),
        "stock_list": [{"model_id": 0, "seller_stock": [{"stock": max(quantity, 0)}]}],
    }
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(url, json=payload)
    ok = r.status_code == 200 and not (r.json() or {}).get("error")
    return {"ok": ok}


async def unlist_item(item_id: str, account: dict) -> dict:
    url = _signed_url("/api/v2/product/unlist_item", account)
    payload = {"item_list": [{"item_id": int(item_id), "unlist": True}]}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(url, json=payload)
    ok = r.status_code == 200 and not (r.json() or {}).get("error")
    return {"ok": ok}


async def get_order_detail(order_sn: str, account: dict) -> dict | None:
    url = _signed_url("/api/v2/order/get_order_detail", account)
    url += f"&order_sn_list={order_sn}&response_optional_fields=item_list,buyer_username"
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(url)
    if r.status_code == 200:
        orders = (r.json().get("response") or {}).get("order_list", [])
        return orders[0] if orders else None
    return None


def verify_push_signature(url: str, raw_body: bytes, signature: str) -> bool:
    """Assinatura do Shopee Push Mechanism V2: HMAC-SHA256("{url}|{body}",
    partner_key). Se o app ainda não tem partner_key configurada, não dá pra
    validar — deixa passar (é dev/staging, ainda não recebe push real) mas
    quem chama isso já loga que a verificação foi pulada."""
    if not settings.shopee_partner_key:
        return True
    base = f"{url}|{raw_body.decode('utf-8', errors='ignore')}"
    expected = hmac.new(settings.shopee_partner_key.encode(), base.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")
