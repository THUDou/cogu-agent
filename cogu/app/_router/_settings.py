from __future__ import annotations

import json
import os
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