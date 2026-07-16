import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.database import Base, engine
from app.config import settings
from app.routes import parts, import_ml, sales, compatibility, webhooks, platforms, feed, auth, internal, reports

Base.metadata.create_all(bind=engine)

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
app.include_router(feed.router)

@app.get("/")
def root():
    return {"status": "ok", "app": "Pitbox", "version": "0.2.0"}

@app.get("/health")
def health():
    return {"status": "healthy"}
