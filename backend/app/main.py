from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, profile, documents, services, applications, consents, chat, mock_api, events, audit

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

import os
# Set up CORS middleware
origins = [str(origin).rstrip("/") for origin in settings.BACKEND_CORS_ORIGINS] if settings.BACKEND_CORS_ORIGINS else []
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_origin_regex=r"^https:\/\/.*(\.onrender\.com|\.vercel\.app)$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(chat.router)
app.include_router(documents.router)

@app.on_event("startup")
async def startup_event():
    if "sqlite" in settings.DATABASE_URL:
        from app.database import Base, engine
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        from app.seed import seed_data
        try:
            await seed_data()
        except Exception as e:
            print(f"Startup seed notice: {e}")
app.include_router(mock_api.router)
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(profile.router, prefix=settings.API_V1_STR)
app.include_router(services.router, prefix=settings.API_V1_STR)
app.include_router(applications.router, prefix=settings.API_V1_STR)
app.include_router(consents.router, prefix=settings.API_V1_STR)
app.include_router(events.router, prefix=settings.API_V1_STR)
app.include_router(audit.router, prefix=settings.API_V1_STR)


@app.get("/")
def root():
    return {
        "message": "Welcome to SEVA AI API",
        "docs": "/docs",
        "status": "active",
        "commit_sha": os.getenv("RENDER_GIT_COMMIT", os.getenv("GIT_COMMIT", "dev")),
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "commit_sha": os.getenv("RENDER_GIT_COMMIT", os.getenv("GIT_COMMIT", "dev")),
        "branch": os.getenv("RENDER_GIT_BRANCH", os.getenv("GIT_BRANCH", "dev")),
    }
