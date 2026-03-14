from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from auth.router import router as auth_router
from config import get_settings
from db.database import create_tables, engine
from history.router import router as history_router
from api.routes import router as api_router
from limiter import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    yield


settings = get_settings()

app = FastAPI(
    title="clarifi.ai",
    description="CSV data quality inspector and auto-fixer",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if settings.is_production:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts_list,
    )

app.include_router(auth_router, prefix="/api/v1")
app.include_router(history_router, prefix="/api/v1")
app.include_router(api_router, prefix="/api/v1")


@app.get("/health", include_in_schema=False)
async def health():
    db_status = "ok"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    overall = "ok" if db_status == "ok" else "degraded"
    status_code = 200 if overall == "ok" else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": overall,
            "db": db_status,
            "llm_enabled": settings.llm_enabled,
        },
    )