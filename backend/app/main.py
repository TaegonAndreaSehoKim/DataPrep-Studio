from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import initialize_database
from app.routers import analysis, dashboard, datasets, exports, health, pipeline, preview, projects


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(dashboard.router)
    app.include_router(projects.router)
    app.include_router(datasets.router)
    app.include_router(analysis.router)
    app.include_router(pipeline.router)
    app.include_router(preview.router)
    app.include_router(exports.router)
    return app


app = create_app()
