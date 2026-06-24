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
APP_VERSION = "1.4.0"

_SKILLS_CACHE = None


def _find_assets_dir() -> str:
    candidates = []
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
        candidates.append(os.path.join(base, "assets"))
        candidates.append(os.path.join(base, "_internal", "assets"))
    candidates.append(os.path.join(os.path.dirname(__file__), "..", "..", "loong-desktop", "assets"))
    for p in candidates:
        if os.path.isdir(p):
            return os.path.abspath(p)
    return ""


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


def _scan_skills():
    global _SKILLS_CACHE
    if _SKILLS_CACHE is not None:
        return _SKILLS_CACHE
    skills = []
    try:
        from cogu.core.skills_system import PromptSkill
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
        skill_dirs = []
        base = Path(__file__).parent.parent / "skills"
        if base.exists():
            skill_dirs.append(("builtin", base))
        bundled = Path(__file__).parent.parent.parent / "skills"
        if bundled.exists():
            for d in bundled.iterdir():
                if d.is_dir():
                    label = d.name
                    if 'office' in label.lower() or 'claw' in label.lower():
                        label = "office-claw"
                    elif 'workbuddy' in label.lower():
                        label = "workbuddy"
                    elif 'doubao' in label.lower():
                        label = "doubao-local"
                    else:
                        label = "builtin"
                    skill_dirs.append((label, d))
        for label, d in skill_dirs:
            for md in d.rglob("SKILL.md"):
                name = md.parent.name
                desc = ""
                try:
                    first_lines = md.read_text(encoding="utf-8")[:200]
                    for line in first_lines.split("\n"):
                        line = line.strip()
                        if line and not line.startswith("#"):
                            desc = line[:100]
                            break
                except Exception:
                    pass
                skills.append({"name": name, "description": desc, "source": label})
    _SKILLS_CACHE = skills
    return skills


def _get_or_create_app():
    try:
        from cogu.app import create_app
        app = create_app(version=APP_VERSION)
    except Exception as e:
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse
        from fastapi.middleware.cors import CORSMiddleware

        app = FastAPI(title="COGU Loong", version=APP_VERSION)
        app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

        @app.get("/healthz")
        async def healthz():
            return {"status": "ok", "version": APP_VERSION, "mode": "desktop"}

        @app.get("/")
        async def root():
            html_path = _find_html()
            if html_path and os.path.isfile(html_path):
                return HTMLResponse(content=Path(html_path).read_text(encoding="utf-8"))
            return HTMLResponse(content="<html><body><h1>COGU Loong - Dashboard not found</h1></body></html>")

        @app.get("/api/settings/onboarding")
        async def onboarding():
            config_path = Path.home() / ".cogu" / "config.json"
            needs = True
            if config_path.exists():
                try:
                    data = json.loads(config_path.read_text(encoding="utf-8"))
                    if data.get("deepseek", {}).get("api_key") or data.get("api_key"):
                        needs = False
                except Exception:
                    pass
            return {"needs_onboarding": needs, "configured_providers": []}

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
            provider = body.get("provider", "deepseek")
            if provider not in data:
                data[provider] = {}
            data[provider]["api_key"] = body.get("api_key", "")
            if body.get("base_url"):
                data[provider]["base_url"] = body["base_url"]
            if body.get("model"):
                data.setdefault("agent", {})["model"] = body["model"]
            config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"provider": provider, "configured": True}

        @app.get("/api/settings")
        async def get_settings():
            config_path = Path.home() / ".cogu" / "config.json"
            data = {}
            if config_path.exists():
                try:
                    data = json.loads(config_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            provider = data.get("agent", {}).get("provider", "deepseek")
            return {
                "api_base_url": data.get(provider, {}).get("base_url", "https://api.deepseek.com"),
                "model": data.get("agent", {}).get("model", "deepseek-chat"),
                "provider": provider,
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
                provider = body.get("provider", data.get("agent", {}).get("provider", "deepseek"))
                data.setdefault(provider, {})["base_url"] = body["api_base_url"]
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
            skills = _scan_skills()
            return {"tools": skills, "total": len(skills)}

        @app.get("/api/skills")
        async def list_skills():
            skills = _scan_skills()
            return {"skills": skills, "total": len(skills)}

        @app.get("/api/agents")
        async def list_agents():
            return []

        @app.get("/api/sessions")
        async def list_sessions():
            return {"sessions": [], "total": 0}

        @app.post("/api/memory/search")
        async def search_memory(body: dict):
            return {"results": [], "total": 0}

        @app.get("/api/settings/pangu/status")
        async def pangu_status():
            model_path = Path.home() / ".cogu" / "pangu-model"
            safetensors = list(model_path.glob("*.safetensors")) if model_path.exists() else []
            gguf_path = Path.home() / ".cogu" / "models"
            gguf_files = list(gguf_path.glob("*.gguf")) if gguf_path.exists() else []
            model_available = len(safetensors) > 0 or len(gguf_files) > 0
            try:
                import urllib.request
                resp = urllib.request.urlopen("http://127.0.0.1:8199/health", timeout=2)
                server_running = resp.status == 200
            except Exception:
                server_running = False
            size_mb = 0
            if safetensors:
                size_mb = sum(f.stat().st_size for f in safetensors) // (1024 * 1024)
            return {
                "model_available": model_available,
                "server_running": server_running,
                "model_size_mb": size_mb if size_mb else None,
                "backends": {
                    "transformers": len(safetensors) > 0,
                    "gguf": len(gguf_files) > 0,
                }
            }

        @app.post("/api/settings/pangu/download")
        async def pangu_download():
            return {"status": "not_implemented", "message": "请手动下载模型文件到 ~/.cogu/pangu-model/"}

        @app.post("/api/settings/pangu/start")
        async def pangu_start():
            return {"status": "starting", "message": "盘古 Mini 服务正在启动…"}

        @app.post("/api/settings/pangu/stop")
        async def pangu_stop():
            return {"status": "stopped", "message": "盘古 Mini 服务已停止"}

        @app.post("/api/chat/stream")
        async def chat_stream(body: dict):
            from sse_starlette.sse import EventSourceResponse
            import json as _json
            msg = body.get("message", "")
            session_id = body.get("session_id", "")
            model = body.get("model", "deepseek-chat")

            try:
                from cogu.core.api_config import get_active_config, Provider
                from cogu.api.client import MultiProviderClient
                config = get_active_config()
                client = MultiProviderClient(config)
                reply_parts = []

                async def gen():
                    yield {"event": "message", "data": _json.dumps({"type": "run.started", "session_id": session_id})}
                    try:
                        async for event in client.query_stream(msg, session_id=session_id):
                            if event.get("type") in ("text.delta", "TEXT_DELTA"):
                                yield {"event": "message", "data": _json.dumps(event)}
                            elif event.get("type") in ("run.completed", "RUN_COMPLETED"):
                                yield {"event": "message", "data": _json.dumps(event)}
                            else:
                                yield {"event": "message", "data": _json.dumps(event)}
                    except Exception as ex:
                        yield {"event": "message", "data": _json.dumps({"type": "text.delta", "content": f"[错误] {ex}"})}
                        yield {"event": "message", "data": _json.dumps({"type": "run.completed", "session_id": session_id})}

                return EventSourceResponse(gen())
            except Exception:
                async def gen():
                    yield {"event": "message", "data": _json.dumps({"type": "run.started", "session_id": session_id})}
                    yield {"event": "message", "data": _json.dumps({"type": "text.delta", "content": f"COGU Loong v{APP_VERSION}\n\n请先在设置中配置 API 令牌，然后即可开始对话。\n\n你的消息: {msg}"})}
                    yield {"event": "message", "data": _json.dumps({"type": "run.completed", "session_id": session_id, "reply": f"COGU Loong v{APP_VERSION} — 请配置 API 令牌"})}

                return EventSourceResponse(gen())

        @app.get("/api/tools/dashboard")
        async def dashboard():
            html_path = _find_html()
            if html_path and os.path.isfile(html_path):
                return HTMLResponse(content=Path(html_path).read_text(encoding="utf-8"))
            return HTMLResponse(content="<html><body><h1>COGU Loong - Dashboard not found</h1></body></html>")


    from fastapi.responses import FileResponse
    assets_dir = _find_assets_dir()

    @app.get("/logo.jpg")
    async def serve_logo():
        p = os.path.join(assets_dir, "logo.jpg") if assets_dir else ""
        if p and os.path.isfile(p):
            return FileResponse(p, media_type="image/jpeg")
        return FileResponse(os.path.join(os.path.dirname(__file__), "..", "web", "logo.jpg"), media_type="image/jpeg")

    @app.get("/avatar.jpeg")
    async def serve_avatar():
        p = os.path.join(assets_dir, "avatar.jpeg") if assets_dir else ""
        if p and os.path.isfile(p):
            return FileResponse(p, media_type="image/jpeg")
        return FileResponse(os.path.join(os.path.dirname(__file__), "..", "web", "avatar.jpeg"), media_type="image/jpeg")

    @app.get("/logo.ico")
    async def serve_ico():
        p = os.path.join(assets_dir, "logo.ico") if assets_dir else ""
        if p and os.path.isfile(p):
            return FileResponse(p, media_type="image/x-icon")
        return FileResponse(os.path.join(os.path.dirname(__file__), "..", "web", "logo.ico"), media_type="image/x-icon")

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

        if os.environ.get("COGU_DESKTOP") == "1":
            print(f"[COGU] API server running at http://{APP_HOST}:{APP_PORT}/ (Electron mode)")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
            return

        dashboard_url = f"http://{APP_HOST}:{APP_PORT}/"

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
