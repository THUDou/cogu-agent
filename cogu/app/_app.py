from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from cogu.app._lifespan import app_lifespan
from cogu.app._router import (
    chat_router, agent_router, session_router, tool_router,
    memory_router, settings_router, workflow_router,
    plugin_router, evaluator_router, playground_router,
    observability_router, knowledge_router, node_types_router,
)


def _find_dashboard_html() -> str:
    candidates = []
    if getattr(os, "frozen", False) or os.environ.get("COGU_FROZEN"):
        base = os.environ.get("COGU_BASE", os.path.dirname(os.environ.get("COGU_EXE", "")))
        candidates.append(os.path.join(base, "cogu", "web", "cogu-loong.html"))
        candidates.append(os.path.join(base, "_internal", "cogu", "web", "cogu-loong.html"))
    candidates.append(os.path.join(os.path.dirname(__file__), "..", "web", "cogu-loong.html"))
    for p in candidates:
        if os.path.isfile(p):
            return os.path.abspath(p)
    return ""


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
    app.include_router(memory_router)
    app.include_router(settings_router)
    app.include_router(workflow_router)
    app.include_router(plugin_router)
    app.include_router(evaluator_router)
    app.include_router(playground_router)
    app.include_router(observability_router)
    app.include_router(knowledge_router)
    app.include_router(node_types_router)

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok", "version": version}

    @app.get("/")
    async def dashboard_root():
        html_path = _find_dashboard_html()
        if html_path and os.path.isfile(html_path):
            return HTMLResponse(content=Path(html_path).read_text(encoding="utf-8"))
        return HTMLResponse(content="<html><body><h1>COGU Loong - Dashboard not found</h1></body></html>")

    @app.get("/api/skills")
    async def list_skills():
        skills = []
        try:
            from cogu.skills.registry import SkillRegistry
            reg = SkillRegistry()
            reg.discover()
            for name, skill in reg._skills.items():
                source = "builtin"
                if hasattr(skill, '_skill_path'):
                    sp = skill._skill_path.lower()
                    if 'office-claw' in sp or 'miclaw' in sp:
                        source = "office-claw"
                    elif 'workbuddy' in sp:
                        source = "workbuddy"
                    elif 'doubao' in sp:
                        source = "doubao-local"
                skills.append({
                    "name": name,
                    "description": getattr(skill, 'description', '') or '',
                    "source": source,
                })
        except Exception:
            pass
        return {"skills": skills, "total": len(skills)}

    return app
