import json
import logging
import os
from pathlib import Path
from typing import Optional

from cogu.config.settings import Settings


def _load_dotenv(path: str = "") -> dict[str, str]:
    raw = Path(path) if path else Path.cwd()
    target = raw if raw.is_file() else raw / ".env"
    if not target.is_file():
        target = Path.home() / ".cogu" / ".env"
    if not target.is_file():
        return {}
    env_vars = {}
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key:
            env_vars[key] = val
    return env_vars


class ConfigManager:
    CONFIG_DIR_NAME = ".cogu"
    CONFIG_FILE = "config.json"
    SECRETS_FILE = "secrets.json"

    # API Key 格式验证规则
    _PROVIDER_KEY_PATTERNS = {
        "deepseek": {"prefix": "sk-", "min_length": 20, "label": "DeepSeek"},
        "openai": {"prefix": "sk-", "min_length": 20, "label": "OpenAI"},
        "claude": {"prefix": "sk-", "min_length": 20, "label": "Claude"},
        "zhipu": {"prefix": "", "min_length": 10, "label": "智谱GLM"},
        "qwen": {"prefix": "sk-", "min_length": 20, "label": "通义千问"},
        "moonshot": {"prefix": "sk-", "min_length": 20, "label": "Moonshot"},
        "siliconflow": {"prefix": "sk-", "min_length": 20, "label": "SiliconFlow"},
    }

    def __init__(self, workspace: str = ""):
        self._workspace = Path(workspace).resolve() if workspace else Path.cwd()
        self._config_dir = self._workspace / self.CONFIG_DIR_NAME
        self._config_dir.mkdir(parents=True, exist_ok=True)
        self._secrets_path = self._config_dir / self.SECRETS_FILE
        self._settings: Optional[Settings] = None
        self._logger = logging.getLogger(__name__)

    @property
    def config_dir(self) -> Path:
        return self._config_dir

    def load_settings(self) -> Settings:
        if self._settings is not None:
            return self._settings
        dotenv_vars = _load_dotenv(str(self._workspace))
        for k, v in dotenv_vars.items():
            if k not in os.environ:
                os.environ[k] = v
        settings = Settings.load(str(self._workspace))
        self._apply_secrets(settings)
        self._settings = settings
        return settings

    def _read_secrets(self) -> dict:
        if not self._secrets_path.exists():
            return {}
        try:
            return json.loads(self._secrets_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            return {}

    def _write_secrets(self, data: dict):
        self._secrets_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _apply_secrets(self, settings: Settings):
        secrets = self._read_secrets()
        api_keys = secrets.get("api_keys", {})
        for name, key in api_keys.items():
            if name == "deepseek" and not settings.deepseek.api_key:
                settings.deepseek.api_key = key
            env_var = f"{name.upper()}_API_KEY"
            if env_var not in os.environ:
                os.environ[env_var] = key

    def _validate_api_key_format(self, provider: str, api_key: str) -> tuple[bool, str]:
        """验证 API Key 格式.

        Args:
            provider: 提供商名称
            api_key: API Key

        Returns:
            (是否有效, 错误信息)
        """
        if not api_key or not api_key.strip():
            return False, "API Key 不能为空"

        pattern = self._PROVIDER_KEY_PATTERNS.get(provider)
        if not pattern:
            return True, ""

        label = pattern["label"]
        prefix = pattern["prefix"]
        min_length = pattern["min_length"]

        if prefix and not api_key.startswith(prefix):
            return False, f"{label} API Key 应以 '{prefix}' 开头"

        if len(api_key) < min_length:
            return False, f"{label} API Key 长度不足（最少 {min_length} 字符）"

        return True, ""

    def set_api_key(self, provider: str, api_key: str):
        # ✅ 验证 API Key 格式
        is_valid, error_msg = self._validate_api_key_format(provider, api_key)
        if not is_valid:
            raise ValueError(f"❌ {error_msg}")

        secrets = self._read_secrets()
        secrets.setdefault("api_keys", {})[provider] = api_key
        self._write_secrets(secrets)
        env_var = f"{provider.upper()}_API_KEY"
        os.environ[env_var] = api_key
        if self._settings:
            if provider == "deepseek":
                self._settings.deepseek.api_key = api_key
        
        self._logger.info(f"API key set for provider '{provider}'")

    def get_api_key(self, provider: str) -> str:
        secrets = self._read_secrets()
        return secrets.get("api_keys", {}).get(provider, "") or os.environ.get(f"{provider.upper()}_API_KEY", "")

    def remove_api_key(self, provider: str):
        secrets = self._read_secrets()
        secrets.get("api_keys", {}).pop(provider, None)
        self._write_secrets(secrets)

    def list_providers(self) -> list[dict]:
        secrets = self._read_secrets()
        api_keys = secrets.get("api_keys", {})
        settings = self.load_settings()
        result = []
        for name, info in {
            "deepseek": {"base_url": "https://api.deepseek.com", "models": settings.deepseek.models},
            "openai": {"base_url": "https://api.openai.com/v1", "models": ["gpt-4o", "gpt-4.1"]},
            "claude": {"base_url": "https://api.anthropic.com", "models": ["claude-sonnet-4-20250514", "claude-opus-4-20250514"]},
            "zhipu": {"base_url": "https://open.bigmodel.cn/api/paas/v4", "models": ["glm-4-plus"]},
            "qwen": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "models": ["qwen-max"]},
            "moonshot": {"base_url": "https://api.moonshot.cn/v1", "models": ["moonshot-v1-128k"]},
            "siliconflow": {"base_url": "https://api.siliconflow.cn/v1", "models": ["deepseek-ai/DeepSeek-V3"]},
        }.items():
            result.append({
                "name": name,
                "base_url": info["base_url"],
                "models": info["models"],
                "configured": bool(name in api_keys),
                "key_preview": (api_keys.get(name, "")[:8] + "..." if api_keys.get(name) else ""),
            })
        return result

    def set_default_model(self, provider: str, model: str):
        cfg_path = self._config_dir / self.CONFIG_FILE
        data = {}
        if cfg_path.exists():
            try:
                data = json.loads(cfg_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, IOError):
                pass
        agent = data.setdefault("agent", {})
        agent["model"] = model
        if provider != "deepseek":
            prov = data.setdefault("providers", [])
            found = False
            for p in prov:
                if isinstance(p, dict) and p.get("name") == provider:
                    p["default_model"] = model
                    found = True
            if not found:
                prov.append({"name": provider, "default_model": model})
        data["agent"] = agent
        cfg_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        if self._settings:
            self._settings.agent.model = model
