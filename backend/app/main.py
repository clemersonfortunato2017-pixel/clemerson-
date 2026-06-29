from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine
from app.routes import parts, import_ml, sales, compatibility, webhooks, platforms, feed

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Pitbox API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
