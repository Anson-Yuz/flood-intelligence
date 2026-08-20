from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import edge_router, public_router, router
from .auth import router as auth_router
from .auth import seed_admin_user
from .config import Settings, get_settings
from .database import Database
from .realtime import RealtimeBroker
from .seed import seed_database
from .simulator import ScenarioManager
from .ui_compat import router as ui_compat_router


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database = Database(app_settings.database_url)
        database.create_schema()
        seeded = False
        with database.session_factory() as db:
            if app_settings.seed_demo_data:
                seeded = seed_database(db)
            auth_admin_seeded = seed_admin_user(db, app_settings)
        broker = RealtimeBroker()
        scenario_manager = ScenarioManager(
            database=database,
            broker=broker,
            tick_seconds=app_settings.scenario_tick_seconds,
        )
        app.state.settings = app_settings
        app.state.database = database
        app.state.broker = broker
        app.state.scenario_manager = scenario_manager
        app.state.seeded_on_startup = seeded
        app.state.auth_admin_seeded_on_startup = auth_admin_seeded
        yield
        await scenario_manager.shutdown()
        database.dispose()

    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        description=(
            "预鉴 V5.1 后端：会话认证、积水状态、可审计预测、告警联动、"
            "确定性场景模拟与 Ubuntu 边缘接入协议。"
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    wildcard = "*" in app_settings.cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if wildcard else app_settings.cors_origins,
        allow_credentials=not wildcard,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Trace-Id"],
    )
    app.include_router(auth_router, prefix=app_settings.api_prefix)
    app.include_router(auth_router, prefix="/api", include_in_schema=False)
    app.include_router(public_router, prefix=app_settings.api_prefix)
    app.include_router(public_router, prefix="/api", include_in_schema=False)
    app.include_router(edge_router, prefix=app_settings.api_prefix)
    app.include_router(edge_router, prefix="/api", include_in_schema=False)
    app.include_router(router, prefix=app_settings.api_prefix)
    app.include_router(router, prefix="/api", include_in_schema=False)
    app.include_router(ui_compat_router, prefix=app_settings.api_prefix)
    app.include_router(ui_compat_router, prefix="/api", include_in_schema=False)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {
            "service": app_settings.app_name,
            "docs": "/docs",
            "health": f"{app_settings.api_prefix}/health",
        }

    @app.get("/health", include_in_schema=False)
    def root_health() -> dict[str, str]:
        return {"status": "ok", "service": app_settings.app_name, "version": app_settings.app_version}

    return app


app = create_app()
