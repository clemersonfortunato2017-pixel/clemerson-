import os
import asyncio
from pathlib import Path
from sqlalchemy import text
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.database import Base, engine, SessionLocal
from app.config import settings
from app.models import platform_account  # noqa: F401 — registra PlatformAccount/PlatformSyncLog no Base.metadata
from app.models.part import Part
from app.routes import (
    parts, import_ml, sales, compatibility, webhooks, platforms, feed, auth,
    internal, reports, platform_accounts,
)

Base.metadata.create_all(bind=engine)


def _migrate_new_columns():
    """create_all só cria tabelas que faltam, não colunas novas em tabela
    que já existe — essas duas linhas foram adicionadas em marketplace_listings
    pro multi-conta (ver app/models/part.py). Idempotente: se a coluna já
    existe, o ALTER falha e é ignorado."""
    stmts = [
        "ALTER TABLE marketplace_listings ADD COLUMN platform_account_id INTEGER",
        "ALTER TABLE marketplace_listings ADD COLUMN sync_failed BOOLEAN DEFAULT FALSE",
        "ALTER TABLE vehicles ADD COLUMN ref_photo_url VARCHAR(500)",
        "ALTER TABLE vehicles ADD COLUMN ml_brand_value_id VARCHAR(50)",
        "ALTER TABLE vehicles ADD COLUMN ml_model_value_id VARCHAR(50)",
        "ALTER TABLE sales ADD COLUMN platform_account_id INTEGER",
    ]
    with engine.connect() as conn:
        for stmt in stmts:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                conn.rollback()


_migrate_new_columns()

app = FastAPI(title="Pitbox API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Path(settings.uploads_dir).mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.uploads_dir), name="uploads")

app.include_router(auth.router)
app.include_router(internal.router)
app.include_router(reports.router)
app.include_router(parts.router)
app.include_router(import_ml.router)
app.include_router(sales.router)
app.include_router(compatibility.router)
app.include_router(webhooks.router)
app.include_router(platforms.router)
app.include_router(platform_accounts.router)
app.include_router(feed.router)

async def _auto_prepare_loop():
    """Roda dentro do próprio servidor, pra sempre, sem precisar de sessão de
    chat nenhuma aberta — a cada 10 min olha se tem peça esperando
    identificação e já deixa pronta (título/preço/compatibilidade), nunca
    publica sozinha (isso é sempre um clique do usuário, ver
    /platforms/parts/{id}/publish-ready). Decisão do Clemerson em
    2026-07-20: a esteira tem que andar sozinha sem ele precisar pedir."""
    from app.services.auto_listing import prepare_part

    while True:
        await asyncio.sleep(600)
        if not settings.anthropic_api_key:
            continue
        db = SessionLocal()
        try:
            from app.models.part import MarketplaceListing
            listed_ids = {r[0] for r in db.query(MarketplaceListing.part_id).filter(MarketplaceListing.status == "active").all()}
            pending = db.query(Part).filter(Part.status == "draft", Part.active == True).all()  # noqa: E712
            for part in pending:
                already = any(s.get("step") == "identificacao" for s in (part.pipeline_log or []))
                if already or part.id in listed_ids:
                    continue
                try:
                    await prepare_part(part.id, db)
                except Exception:
                    pass
        finally:
            db.close()


@app.on_event("startup")
async def _start_background_jobs():
    asyncio.create_task(_auto_prepare_loop())


@app.get("/")
def root():
    return {"status": "ok", "app": "Pitbox", "version": "0.2.0"}

@app.get("/health")
def health():
    return {"status": "healthy"}
