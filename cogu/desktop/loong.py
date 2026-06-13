import asyncio
import json
import os
import sys
import threading
import time
from pathlib import Path

import uvicorn

APP_PORT = 8198
APP_HOST = "127.0.0.1"
APP_VERSION = "0.9.1"


def _find_html() -> str:
    candidates = []
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
        candidates.append(os.path.join(base, "cogu", "web", "cogu-loong.html"))
        candidates.append(os.path.join(base, "_internal", "cogu", "web", "cogu-loong.html"))
    candidates.append(os.path.join(os.path.dirname(__file__), "..", "web", "cogu-loong.html"))
    candidates.append(os.path.join(os.path.dirname(__file__), "web", "cogu-loong.html"))
    for p in candidates:
        if os.path.isfile(p):
            return os.path.abspath(p)
    return ""


def _get_or_create_app():
    try:
        from cogu.app import create_app
        return create_app(version=APP_VERSION)
    except Exception as e:
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse
        from fastapi.middleware.cors import CORSMiddleware

        app = FastAPI(title="COGU Loong", version=APP_VERSION)
        app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

        @app.get("/healthz")
        async def healthz():
            return {"status": "ok", "version": APP_VERSION, "mode": "fallback"}

        @app.get("/api/settings/onboarding")
        async def onboarding():
            return {"needs_onboarding": True, "configured_providers": []}

        @app.post("/api/settings/api-key")
        async def set_api_key(body: dict):
            config_dir = Path.home() / ".cogu"
            config_dir.mkdir(parents=True, exist_ok=True)
            config_path = config_dir / "config.json"
            data = {}
            if config_path.exists():
                try:
                    data = json.loads(config_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            if "deepseek" not in data:
                data["deepseek"] = {}
            data["deepseek"]["api_key"] = body.get("api_key", "")
            if body.get("base_url"):
                data["deepseek"]["base_url"] = body["base_url"]
            if body.get("model"):
                data.setdefault("agent", {})["model"] = body["model"]
            config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"provider": body.get("provider", "deepseek"), "configured": True}

        @app.get("/api/settings")
        async def get_settings():
            config_path = Path.home() / ".cogu" / "config.json"
            data = {}
            if config_path.exists():
                try:
                    data = json.loads(config_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            return {
                "api_base_url": data.get("deepseek", {}).get("base_url", "https://api.deepseek.com"),
                "model": data.get("agent", {}).get("model", "deepseek-chat"),
                "providers": [],
                "pangu_mini_enabled": data.get("pangu_mini", {}).get("enabled", False),
                "pangu_mini_backend": data.get("pangu_mini", {}).get("backend", "auto"),
                "pangu_mini_api_port": data.get("pangu_mini", {}).get("api_port", 8199),
            }

        @app.put("/api/settings")
        async def update_settings(body: dict):
            config_path = Path.home() / ".cogu" / "config.json"
            data = {}
            if config_path.exists():
                try:
                    data = json.loads(config_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            if body.get("model"):
                data.setdefault("agent", {})["model"] = body["model"]
            if body.get("api_base_url"):
                data.setdefault("deepseek", {})["base_url"] = body["api_base_url"]
            if body.get("pangu_mini_enabled") is not None:
                data.setdefault("pangu_mini", {})["enabled"] = body["pangu_mini_enabled"]
            if body.get("pangu_mini_backend"):
                data.setdefault("pangu_mini", {})["backend"] = body["pangu_mini_backend"]
            if body.get("pangu_mini_api_port"):
                data.setdefault("pangu_mini", {})["api_port"] = body["pangu_mini_api_port"]
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return await get_settings()

        @app.get("/api/tools")
        async def list_tools():
            return {"tools": [], "total": 0}

        @app.get("/api/agents")
        async def list_agents():
            return []

        @app.get("/api/sessions")
        async def list_sessions():
            return {"sessions": [], "total": 0}

        @app.post("/api/memory/search")
        async def search_memory(body: dict):
            return {"results": [], "total": 0}

        @app.post("/api/chat/stream")
        async def chat_stream(body: dict):
            from sse_starlette.sse import EventSourceResponse
            import json as _json
            msg = body.get("message", "")
            session_id = body.get("session_id", "")

            async def gen():
                yield {"event": "message", "data": _json.dumps({"type": "run.started", "session_id": session_id})}
                yield {"event": "message", "data": _json.dumps({"type": "text.delta", "content": f"COGU Loong v{APP_VERSION} 已启动。\n\n请先在 Settings 中配置 API 令牌，然后即可开始对话。\n\n你的消息: {msg}"})}
                yield {"event": "message", "data": _json.dumps({"type": "run.completed", "session_id": session_id, "reply": f"COGU Loong v{APP_VERSION} 已启动。请先在 Settings 中配置 API 令牌，然后即可开始对话。"})}

            return EventSourceResponse(gen())

        @app.get("/api/tools/dashboard")
        async def dashboard():
            html_path = _find_html()
            if html_path and os.path.isfile(html_path):
                return HTMLResponse(content=Path(html_path).read_text(encoding="utf-8"))
            return HTMLResponse(content="<html><body><h1>COGU Loong - Dashboard not found</h1></body></html>")

        return app


class COGULoongDesktop:
    def __init__(self):
        self._server_ready = threading.Event()
        self._app = None

    def _run_server(self):
        self._app = _get_or_create_app()
        config = uvicorn.Config(
            self._app,
            host=APP_HOST,
            port=APP_PORT,
            log_level="warning",
            access_log=False,
        )
        server = uvicorn.Server(config)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def _serve():
            self._server_ready.set()
            await server.serve()

        loop.run_until_complete(_serve())

    def start(self):
        server_thread = threading.Thread(target=self._run_server, daemon=True)
        server_thread.start()

        if not self._server_ready.wait(timeout=10):
            print("[ERROR] Server failed to start within 10 seconds")
            sys.exit(1)

        dashboard_url = f"http://{APP_HOST}:{APP_PORT}/api/tools/dashboard"

        try:
            import webview
            window = webview.create_window(
                title=f"COGU Loong v{APP_VERSION}",
                url=dashboard_url,
                width=1280,
                height=800,
                min_size=(960, 600),
                resizable=True,
                frameless=False,
                easy_drag=True,
            )
            webview.start(debug=False)
        except ImportError:
            import webbrowser
            webbrowser.open(dashboard_url)
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
        except Exception as e:
            import webbrowser
            webbrowser.open(dashboard_url)
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass


def main():
    if getattr(sys, "frozen", False):
        os.chdir(os.path.dirname(sys.executable))
    desktop = COGULoongDesktop()
    desktop.start()


if __name__ == "__main__":
    main()
