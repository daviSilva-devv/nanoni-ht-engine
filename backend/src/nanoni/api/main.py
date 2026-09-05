from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nanoni.api.routers import (
    admin_config,
    catalog,
    commerce,
    content,
    dashboard,
    jobs,
    publication,
    system,
    vault,
)
from nanoni.core.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Nanoni Engine",
        version="0.2.0",
        description="Nanoni control plane and local-media orchestration foundation",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(system.router)
    app.include_router(admin_config.router, prefix="/api/v1")
    app.include_router(dashboard.router, prefix="/api/v1")
    app.include_router(catalog.router, prefix="/api/v1")
    app.include_router(content.router, prefix="/api/v1")
    app.include_router(publication.router, prefix="/api/v1")
    app.include_router(commerce.router, prefix="/api/v1")
    app.include_router(jobs.router, prefix="/api/v1")
    app.include_router(vault.router, prefix="/api/v1")
    return app


app = create_app()
