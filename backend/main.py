"""
clarifi.ai — FastAPI entry point.
Production-ready: lifespan startup/shutdown, CORS, routers, health check.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from auth.router import router as auth_router
from config import get_settings
from db.database import create_tables
from history.router import router as history_router

# Import your existing routes here — keep them intact
from api.routes import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run DB migrations on startup; cleanup on shutdown."""
    await create_tables()
    yield
    # Add cleanup here if needed (e.g., close Redis connections)


settings = get_settings()

app = FastAPI(
    title="clarifi.ai",
    description="CSV data quality inspector and auto-fixer",
    version="1.0.0",
    lifespan=lifespan,
    # Disable docs in production
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

# ─── Middleware ───────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,  # Required for cookies
    allow_methods=["*"],
    allow_headers=["*"],
)

if settings.is_production:
    # Reject requests with unexpected Host headers (prevents host header injection)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"],  # Replace with your actual domain: ["clarifi.ai", "www.clarifi.ai"]
    )

# ─── Routers ─────────────────────────────────────────────────────────────────

app.include_router(auth_router, prefix="/api/v1")
app.include_router(history_router, prefix="/api/v1")
app.include_router(api_router, prefix="/api/v1")  # your existing routes


# ─── Health check ─────────────────────────────────────────────────────────────

@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok", "llm_enabled": settings.llm_enabled}
