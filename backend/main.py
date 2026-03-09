from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router
from auth.router import router as auth_router
from config import settings

app = FastAPI(
    title="Data Quality Inspector API",
    description="Backend engine for processing data files and detecting data issues.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(auth_router, prefix="/auth", tags=["auth"])

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Data Quality Engine is running."}