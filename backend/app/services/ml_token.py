import httpx
import json
import os
from datetime import datetime, timedelta
from app.config import settings

ML_TOKENS_FILE = r"F:\FORTUNATO AUTO PARTS\ml_tokens.json"
ML_TOKEN_URL = "https://api.mercadolibre.com/oauth/token"


def load_tokens() -> dict:
    if not os.path.exists(ML_TOKENS_FILE):
        return {}
    with open(ML_TOKENS_FILE, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def save_tokens(tokens: dict):
    tokens["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(ML_TOKENS_FILE, "w", encoding="utf-8") as f:
        json.dump(tokens, f, indent=4, ensure_ascii=False)


def is_token_expired(tokens: dict) -> bool:
    generated_at = tokens.get("generated_at")
    expires_in = tokens.get("expires_in", 21600)
    if not generated_at:
        return True
    generated = datetime.strptime(generated_at, "%Y-%m-%d %H:%M:%S")
    return datetime.now() >= generated + timedelta(seconds=expires_in - 300)


async def get_valid_token() -> str:
    tokens = load_tokens()
    if not tokens:
        return ""
    if not is_token_expired(tokens):
        return tokens.get("access_token", "")
    refresh_token = tokens.get("refresh_token", "")
    if not refresh_token:
        return tokens.get("access_token", "")
    async with httpx.AsyncClient() as client:
        r = await client.post(
            ML_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": settings.ml_app_id,
                "client_secret": settings.ml_client_secret,
                "refresh_token": refresh_token,
            },
        )
        if r.status_code == 200:
            new_tokens = r.json()
            tokens.update(new_tokens)
            save_tokens(tokens)
            return new_tokens["access_token"]
    return tokens.get("access_token", "")
