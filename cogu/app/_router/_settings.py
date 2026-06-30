from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field

from cogu.config.settings import Settings, ProviderConfig, DeepSeekConfig

settings_router = APIRouter(prefix="/api/settings", tags=["settings"])


class APIKeyRequest(BaseModel):
    provider: str = Field(..., description="Provider name: deepseek/openai/claude/zhipu/qwen/moonshot/custom")
    api_key: str = Field(..., description="API key")
    base_url: str = Field(default="", description="Custom API base URL (for custom provider)")
    model: str = Field(default="", description="Default model name")


class APIKeyResponse(BaseModel):
    provider: str
    configured: bool
    key_preview: str = ""
    base_url: str = ""
    models: list[str] = []


class SettingsResponse(BaseModel):
    api_base_url: str = ""
    model: str = ""
    providers: list[APIKeyResponse] = []
    pangu_mini_enabled: bool = False
    pangu_mini_backend: str = "auto"
    pangu_mini_api_port: int = 8199


class SettingsUpdateRequest(BaseModel):
    api_base_url: str = ""
    model: str = ""
    pangu_mini_enabled: bool | None = None
    pangu_mini_backend: str | None = None
    pangu_mini_api_port: int | None = None


class OnboardingCheckResponse(BaseModel):
    needs_onboarding: bool
    configured_providers: list[str] = []


def _get_config_path() -> Path:
    workspace = os.environ.get("COGU_WORKSPACE", "")
    if workspace:
        return Path(workspace) / ".cogu" / "config.json"
    return Path.home() / ".cogu" / "config.json"


def _load_settings() -> Settings:
    config_path = _get_config_path()
    if config_path.exists():
        try:
            return Settings.from_file(str(config_path))
        except Exception:
            pass
    return Settings.default()


def _save_settings(settings: Settings) -> None:
    config_path = _get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(settings.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


@settings_router.get("/onboarding", response_model=OnboardingCheckResponse)
async def check_onboarding():
    settings = _load_settings()
    configured = []
    if settings.deepseek.api_key:
        configured.append("deepseek")
    for p in settings.providers:
        if p.api_key:
            configured.append(p.name)
    return OnboardingCheckResponse(
        needs_onboarding=len(configured) == 0,
        configured_providers=configured,
    )


@settings_router.get("", response_model=SettingsResponse)
async def get_settings():
    settings = _load_settings()
    providers = []
    if settings.deepseek.api_key:
        providers.append(APIKeyResponse(
            provider="deepseek",
            configured=True,
            key_preview=settings.deepseek.api_key[:8] + "..." if len(settings.deepseek.api_key) > 8 else "***",
            base_url=settings.deepseek.base_url,
            models=settings.deepseek.models,
        ))
    for p in settings.providers:
        providers.append(APIKeyResponse(
            provider=p.name,
            configured=bool(p.api_key),
            key_preview=p.api_key[:8] + "..." if p.api_key and len(p.api_key) > 8 else ("***" if p.api_key else ""),
            base_url=p.base_url,
            models=p.models,
        ))
    return SettingsResponse(
        api_base_url=settings.deepseek.base_url,
        model=settings.agent.model,
        providers=providers,
        pangu_mini_enabled=settings.pangu_mini.enabled,
        pangu_mini_backend=settings.pangu_mini.backend,
        pangu_mini_api_port=settings.pangu_mini.api_port,
    )


@settings_router.post("/api-key", response_model=APIKeyResponse)
async def set_api_key(body: APIKeyRequest):
    settings = _load_settings()

    if body.provider == "deepseek":
        settings.deepseek.api_key = body.api_key
        if body.base_url:
            settings.deepseek.base_url = body.base_url
        if body.model:
            if body.model not in settings.deepseek.models:
                settings.deepseek.models.insert(0, body.model)
            settings.agent.model = body.model
    else:
        existing = None
        for p in settings.providers:
            if p.name == body.provider:
                existing = p
                break
        if existing:
            existing.api_key = body.api_key
            if body.base_url:
                existing.base_url = body.base_url
            if body.model:
                existing.models = [body.model] + existing.models
        else:
            new_provider = ProviderConfig(
                name=body.provider,
                api_key=body.api_key,
                base_url=body.base_url or "",
                models=[body.model] if body.model else [],
            )
            settings.providers.append(new_provider)
            if body.model:
                settings.agent.model = body.model

    _save_settings(settings)

    key_preview = body.api_key[:8] + "..." if len(body.api_key) > 8 else "***"
    return APIKeyResponse(
        provider=body.provider,
        configured=True,
        key_preview=key_preview,
        base_url=body.base_url or settings.deepseek.base_url,
        models=[body.model] if body.model else settings.deepseek.models,
    )


@settings_router.delete("/api-key/{provider}")
async def remove_api_key(provider: str):
    settings = _load_settings()
    if provider == "deepseek":
        settings.deepseek.api_key = ""
    else:
        settings.providers = [p for p in settings.providers if p.name != provider]
    _save_settings(settings)
    return {"deleted": True, "provider": provider}


@settings_router.put("", response_model=SettingsResponse)
async def update_settings(body: SettingsUpdateRequest):
    settings = _load_settings()
    if body.model:
        settings.agent.model = body.model
    if body.api_base_url:
        settings.deepseek.base_url = body.api_base_url
    if body.pangu_mini_enabled is not None:
        settings.pangu_mini.enabled = body.pangu_mini_enabled
    if body.pangu_mini_backend is not None:
        settings.pangu_mini.backend = body.pangu_mini_backend
    if body.pangu_mini_api_port is not None:
        settings.pangu_mini.api_port = body.pangu_mini_api_port
    _save_settings(settings)
    return await get_settings()


def _find_pangu_model_dir() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
        candidates = [base / "pangu-model", base / "_internal" / "pangu-model"]
    else:
        candidates = [Path(__file__).resolve().parent.parent.parent / "pangu-model"]
    candidates.append(Path.home() / ".cogu" / "pangu-model")
    for d in candidates:
        if (d / "model.safetensors").exists():
            return d
    return candidates[0]


@settings_router.get("/pangu/status")
async def pangu_status():
    model_dir = _find_pangu_model_dir()
    model_file = model_dir / "model.safetensors"
    available = model_file.exists() and model_file.stat().st_size > 100_000_000
    server_running = False
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get(f"http://127.0.0.1:8199/healthz", timeout=2.0)
            if r.status_code == 200:
                server_running = True
    except Exception:
        pass
    return {
        "model_available": available,
        "model_dir": str(model_dir),
        "server_running": server_running,
        "model_size_mb": round(model_file.stat().st_size / 1_048_576, 1) if available else 0,
    }


@settings_router.post("/pangu/download")
async def pangu_download():
    model_dir = Path.home() / ".cogu" / "pangu-model"
    model_dir.mkdir(parents=True, exist_ok=True)
    model_file = model_dir / "model.safetensors"
    if model_file.exists() and model_file.stat().st_size > 100_000_000:
        return {"status": "already_downloaded", "path": str(model_dir)}
    try:
        from huggingface_hub import hf_hub_download
        repo_id = "PIKA665/openPangu-Embedded-1B"
        for filename in ["model.safetensors", "tokenizer.model", "config.json",
                         "modeling_openpangu_dense.py", "configuration_openpangu_dense.py",
                         "tokenization_openpangu.py", "generation_config.json",
                         "tokenizer_config.json", "special_tokens_map.json"]:
            try:
                hf_hub_download(repo_id=repo_id, filename=filename, local_dir=str(model_dir))
            except Exception:
                pass
        return {"status": "downloaded", "path": str(model_dir)}
    except ImportError:
        return {"status": "error", "message": "huggingface_hub not installed"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@settings_router.post("/pangu/start")
async def pangu_start():
    model_dir = _find_pangu_model_dir()
    model_file = model_dir / "model.safetensors"
    if not model_file.exists():
        return {"status": "error", "message": "Model not found. Install the full version or download model first."}
    try:
        import subprocess
        import sys
        if getattr(sys, "frozen", False):
            base = Path(sys.executable).parent
            engine_path = base / "_internal" / "cogu" / "mini_engine" / "server.py"
            if not engine_path.exists():
                engine_path = base / "cogu" / "mini_engine" / "server.py"
        else:
            engine_path = Path(__file__).resolve().parent.parent.parent / "mini_engine" / "server.py"
        if not engine_path.exists():
            return {"status": "error", "message": f"Engine not found at {engine_path}"}
        subprocess.Popen(
            [sys.executable, str(engine_path), "--port", "8199", "--backend", "transformers", "--device", "auto"],
            cwd=str(model_dir),
            creation_flags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        return {"status": "starting", "port": 8199}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@settings_router.post("/pangu/stop")
async def pangu_stop():
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            await client.post("http://127.0.0.1:8199/shutdown", timeout=3.0)
    except Exception:
        pass
    return {"status": "stopped"}
