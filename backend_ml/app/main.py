import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import health, metrics, robots, telemetry
from app.config import Settings, get_settings
from app.db import Database
from app.grpc_server import create_grpc_server

log = logging.getLogger("app")


def create_app(
    settings: Settings | None = None,
    db: Database | None = None,
    start_grpc: bool = True,
) -> FastAPI:
    settings = settings or get_settings()
    db = db or Database(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db.create_all()
        grpc_server = None
        if start_grpc:
            grpc_server, port = create_grpc_server(
                db, None, settings.grpc_host, settings.grpc_port, settings.grpc_workers
            )
            grpc_server.start()
            app.state.grpc_port = port
            log.info("gRPC TelemetryService слушает %s:%d", settings.grpc_host, port)
        try:
            yield
        finally:
            if grpc_server is not None:
                grpc_server.stop(grace=2).wait()
                log.info("gRPC-сервер остановлен")

    app = FastAPI(
        title="Robot Metrics Backend",
        version=__version__,
        description="Приём телеметрии роботов по gRPC, хранение и REST/WebSocket API для фронтенда.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.db = db
    app.state.grpc_port = None

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(robots.router)
    app.include_router(telemetry.router)
    app.include_router(metrics.router)
    return app
