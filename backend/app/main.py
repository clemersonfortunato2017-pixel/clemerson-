import os
from pathlib import Path
from sqlalchemy import text
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.database import Base, engine
from app.config import settings
from app.models import platform_account  # noqa: F401 — registra PlatformAccount/PlatformSyncLog no Base.metadata
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

@app.get("/")
def root():
    return {"status": "ok", "app": "Pitbox", "version": "0.2.0"}

@app.get("/health")
def health():
    return {"status": "healthy"}
