from __future__ import annotations

from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cogu.app._lifespan import app_lifespan
from cogu.app._router import chat_router, agent_router, session_router, tool_router


def create_app(
    title: str = "COGU AGENT API",
    version: str = "0.6.0",
    cors_origins: Optional[list[str]] = None,
) -> FastAPI:
    app = FastAPI(
        title=title,
        version=version,
        description="COGU AGENT — 国产认知统一Agent框架 REST API",
        lifespan=app_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(chat_router)
    app.include_router(agent_router)
    app.include_router(session_router)
    app.include_router(tool_router)

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok", "version": version}

    return app
