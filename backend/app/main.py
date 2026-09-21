from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from backend.app.api.assistant import router as assistant_router
from backend.app.api.auth import router as auth_router
from backend.app.api.routes import router
from backend.app.api.stream import router as stream_router
from backend.app.core.config import get_settings
from backend.app.db.session import engine

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    yield
    engine.dispose()


app = FastAPI(
    title="SentinelBank API",
    description="Accounts, transactions, and fraud flags for the SentinelBank demo.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(router, prefix="/api/v1")
app.include_router(assistant_router, prefix="/api/v1")
app.include_router(stream_router, prefix="/api/v1")


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/db", tags=["system"])
def health_db() -> dict[str, str]:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "database": "reachable"}
