"""Gestão de contas extras por plataforma (multi-conta).

A conta ML "principal" (a que já roda a esteira e o webhook em produção,
via MLCredential/F:) fica FORA daqui de propósito — isso é só pra CONTAS
ADICIONAIS: Mercado Livre pessoa física, Shopee PJ, etc.

Fluxo de conexão (OAuth authorization-code):
1. Logado no Pitbox, GET /platform-accounts/{plataforma}/connect?label=...
   → devolve auth_url.
2. Abrir auth_url NUM NAVEGADOR LOGADO NA CONTA QUE VOCÊ QUER CONECTAR
   (não na principal) e autorizar.
3. A plataforma redireciona pro callback abaixo, que troca o code por
   token e grava a PlatformAccount como ativa — a partir daí ela entra
   automaticamente em todo publish-all / sync de venda.

Os endpoints de callback são públicos de propósito (não dá pra carregar o
header de login numa navegação de redirect do navegador) — a segurança vem
do `state` de uso único gerado no passo 1, não de sessão de usuário.
"""
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import httpx
from app.database import get_db
from app.config import settings
from app.models.platform_account import PlatformAccount
from app.routes.auth import get_current_user

router = APIRouter(prefix="/platform-accounts", tags=["platform-accounts"])


@router.get("/", dependencies=[Depends(get_current_user)])
def list_accounts(db: Session = Depends(get_db)):
    rows = db.query(PlatformAccount).filter(PlatformAccount.oauth_state.is_(None)).order_by(PlatformAccount.platform).all()
    return [
        {
            "id": r.id, "platform": r.platform, "label": r.label,
            "external_id": r.external_id, "active": r.active,
            "has_token": bool(r.access_token), "created_at": r.created_at,
        }
        for r in rows
    ]


@router.post("/{account_id}/toggle", dependencies=[Depends(get_current_user)])
def toggle_account(account_id: int, db: Session = Depends(get_db)):
    row = db.query(PlatformAccount).filter_by(id=account_id).first()
    if not row:
        raise HTTPException(404, "Conta não encontrada")
    row.active = not row.active
    db.commit()
    return {"id": row.id, "active": row.active}


@router.delete("/{account_id}", dependencies=[Depends(get_current_user)])
def delete_account(account_id: int, db: Session = Depends(get_db)):
    row = db.query(PlatformAccount).filter_by(id=account_id).first()
    if not row:
        raise HTTPException(404, "Conta não encontrada")
    db.delete(row)
    db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------
# Mercado Livre — segunda conta (ex: pessoa física)
# --------------------------------------------------------------------------

@router.get("/mercadolivre/connect", dependencies=[Depends(get_current_user)])
def ml_connect(label: str = Query(...), db: Session = Depends(get_db)):
    if not settings.ml_app_id or not settings.ml_client_secret:
        raise HTTPException(503, "ML_APP_ID / ML_CLIENT_SECRET não configurados no .env")

    state = secrets.token_urlsafe(16)
    draft = PlatformAccount(platform="mercadolivre", label=label, active=False, oauth_state=state)
    db.add(draft)
    db.commit()

    redirect_uri = f"{settings.public_base_url}/platform-accounts/mercadolivre/callback"
    auth_url = (
        f"https://auth.mercadolivre.com.br/authorization?response_type=code"
        f"&client_id={settings.ml_app_id}&redirect_uri={redirect_uri}&state={state}"
    )
    return {
        "auth_url": auth_url,
        "account_id": draft.id,
        "instructions": "Abra auth_url num navegador LOGADO na conta ML que você quer conectar (a pessoa física, não a principal) e autorize.",
    }


@router.get("/mercadolivre/callback")
async def ml_callback(code: str = Query(...), state: str = Query(...), db: Session = Depends(get_db)):
    draft = db.query(PlatformAccount).filter_by(platform="mercadolivre", oauth_state=state).first()
    if not draft:
        raise HTTPException(400, "state inválido ou já usado — gere um novo link em GET /mercadolivre/connect")

    redirect_uri = f"{settings.public_base_url}/platform-accounts/mercadolivre/callback"
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            "https://api.mercadolibre.com/oauth/token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "authorization_code",
                "client_id": settings.ml_app_id,
                "client_secret": settings.ml_client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
    if r.status_code != 200:
        raise HTTPException(400, f"Falha ao trocar code por token: {r.text[:300]}")

    data = r.json()
    draft.access_token = data["access_token"]
    draft.refresh_token = data.get("refresh_token")
    draft.external_id = str(data.get("user_id"))
    draft.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=data.get("expires_in", 21600) - 300)
    draft.active = True
    draft.oauth_state = None
    db.commit()

    return {
        "ok": True,
        "label": draft.label,
        "external_id": draft.external_id,
        "msg": "Conta ML conectada — já entra no publish/sync automático de todas as peças.",
    }


# --------------------------------------------------------------------------
# Shopee — conta PJ (requer SHOPEE_PARTNER_ID/SHOPEE_PARTNER_KEY já aprovados)
# --------------------------------------------------------------------------

@router.get("/shopee/connect", dependencies=[Depends(get_current_user)])
def shopee_connect(label: str = Query(...), db: Session = Depends(get_db)):
    if not settings.shopee_partner_id or not settings.shopee_partner_key:
        raise HTTPException(
            503,
            "SHOPEE_PARTNER_ID / SHOPEE_PARTNER_KEY não configurados — precisa aprovar um app em "
            "open.shopee.com antes (cadastro de desenvolvedor + revisão da Shopee, não dá pra pular essa etapa).",
        )

    state = secrets.token_urlsafe(16)
    draft = PlatformAccount(platform="shopee", label=label, active=False, oauth_state=state)
    db.add(draft)
    db.commit()

    from app.services.shopee_client import get_auth_url
    redirect_uri = f"{settings.public_base_url}/platform-accounts/shopee/callback?state={state}"
    return {"auth_url": get_auth_url(redirect_uri), "account_id": draft.id}


@router.get("/shopee/callback")
async def shopee_callback(
    code: str = Query(...), shop_id: str = Query(...), state: str = Query(...), db: Session = Depends(get_db)
):
    draft = db.query(PlatformAccount).filter_by(platform="shopee", oauth_state=state).first()
    if not draft:
        raise HTTPException(400, "state inválido ou já usado")

    from app.services.shopee_client import exchange_code
    data = await exchange_code(code, shop_id)
    if not data:
        raise HTTPException(400, "Falha ao trocar code por token na Shopee")

    draft.access_token = data["access_token"]
    draft.refresh_token = data.get("refresh_token")
    draft.external_id = shop_id
    draft.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=data.get("expire_in", 14400) - 300)
    draft.active = True
    draft.oauth_state = None
    db.commit()

    return {"ok": True, "label": draft.label, "external_id": draft.external_id}
