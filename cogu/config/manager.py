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

    # API Key 格式验证规则 — 借鉴 OfficeAce provider registry 模式
    _PROVIDER_KEY_PATTERNS = {
        "deepseek": {"prefix": "sk-", "min_length": 20, "label": "DeepSeek"},
        "openai": {"prefix": "sk-", "min_length": 20, "label": "OpenAI"},
        "claude": {"prefix": "sk-", "min_length": 20, "label": "Claude"},
        "zhipu": {"prefix": "", "min_length": 10, "label": "智谱GLM"},
        "qwen": {"prefix": "sk-", "min_length": 20, "label": "通义千问"},
        "moonshot": {"prefix": "sk-", "min_length": 20, "label": "Moonshot"},
        "siliconflow": {"prefix": "sk-", "min_length": 20, "label": "SiliconFlow"},
        "minimax": {"prefix": "", "min_length": 20, "label": "MiniMax"},
        "groq": {"prefix": "gsk_", "min_length": 30, "label": "Groq"},
        "ollama": {"prefix": "", "min_length": 0, "label": "Ollama"},
        "hunyuan": {"prefix": "", "min_length": 20, "label": "腾讯混元"},
        "pangu": {"prefix": "", "min_length": 20, "label": "华为盘古"},
        "volcano": {"prefix": "", "min_length": 20, "label": "火山引擎"},
        "stepfun": {"prefix": "", "min_length": 20, "label": "阶跃星辰"},
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

    def validate_all_keys(self) -> dict[str, dict]:
        """验证所有已配置的 API Keys — 借鉴 OfficeAce 启动时健康检查模式.
        
        在 Agent 启动时调用，检查所有 provider 的 Key 格式是否有效。
        
        Returns:
            {
                "provider_name": {
                    "configured": bool,
                    "valid": bool,
                    "key_preview": str,  # 前8位...
                    "error": str,         # 失败原因
                    "label": str,         # 显示名称
                },
                ...
            }
        """
        secrets = self._read_secrets()
        api_keys = secrets.get("api_keys", {})
        result = {}
        
        for provider in self._PROVIDER_KEY_PATTERNS:
            key = api_keys.get(provider, "") or os.environ.get(f"{provider.upper()}_API_KEY", "")
            is_valid, error_msg = self._validate_api_key_format(provider, key)
            
            result[provider] = {
                "configured": bool(key),
                "valid": is_valid if key else True,  # 未配置不算无效
                "key_preview": (key[:8] + "..." if key and len(key) > 8 else (key if key else "")),
                "error": error_msg if key and not is_valid else "",
                "label": self._PROVIDER_KEY_PATTERNS[provider]["label"],
            }
        
        return result

    def validate_keys_on_startup(self) -> tuple[bool, list[str]]:
        """启动时 API Key 完整性检查 — 借鉴 OfficeAce 启动校验模式.
        
        检查至少有一个可用的 API Key 配置正确。
        
        Returns:
            (is_ready, warnings): 是否可以启动，以及警告信息列表
        """
        all_keys = self.validate_all_keys()
        configured_valid = [
            name for name, info in all_keys.items()
            if info["configured"] and info["valid"]
        ]
        configured_invalid = [
            (name, info["error"]) for name, info in all_keys.items()
            if info["configured"] and not info["valid"]
        ]
        
        warnings = []
        
        if not configured_valid:
            warnings.append(
                "⚠️ 未检测到有效的 API Key。\n"
                "请运行 `cogu config set <provider> <YOUR-KEY>` 配置 API 密钥。\n"
                f"支持的提供商: {', '.join(info['label'] for info in all_keys.values())}"
            )
        else:
            valid_labels = [
                all_keys[name]["label"] for name in configured_valid
            ]
            self._logger.info(f"API keys validated: {', '.join(valid_labels)}")
        
        for name, error in configured_invalid:
            warnings.append(f"⚠️ {all_keys[name]['label']} API Key 格式无效: {error}")
        
        return bool(configured_valid), warnings

    def get_key_status_report(self) -> str:
        """生成 API Key 状态报告 — 借鉴 OfficeAce 可读状态输出模式.
        
        Returns:
            格式化的状态报告字符串
        """
        all_keys = self.validate_all_keys()
        lines = ["📋 API Key 配置状态", "=" * 50]
        
        configured_count = 0
        valid_count = 0
        
        for name, info in all_keys.items():
            status_icon = "✅" if (info["configured"] and info["valid"]) else ("⚠️" if info["configured"] else "⬜")
            detail = ""
            if info["configured"] and info["valid"]:
                detail = f" ({info['key_preview']})"
                configured_count += 1
                valid_count += 1
            elif info["configured"] and not info["valid"]:
                detail = f" ❌ {info['error']}"
                configured_count += 1
            lines.append(f"  {status_icon} {info['label']:12s}{detail}")
        
        lines.append("=" * 50)
        if valid_count > 0:
            lines.append(f"✅ {valid_count} 个提供商已就绪")
        else:
            lines.append("❌ 没有可用的 API Key，请运行 cogu config set 配置")
        
        return "\n".join(lines)

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
            "minimax": {"base_url": "https://api.minimax.chat/v1", "models": ["abab6.5s-chat"]},
            "groq": {"base_url": "https://api.groq.com/openai/v1", "models": ["llama-3.3-70b-versatile"]},
            "ollama": {"base_url": "http://localhost:11434/v1", "models": ["llama3", "qwen3"]},
            "hunyuan": {"base_url": "https://api.hunyuan.cloud.tencent.com/v1", "models": ["hunyuan-lite"]},
            "pangu": {"base_url": "https://api.pangu.huawei.com/v1", "models": ["pangu-2.0"]},
            "volcano": {"base_url": "https://ark.cn-beijing.volces.com/api/v3", "models": ["doubao-pro-32k"]},
            "stepfun": {"base_url": "https://api.stepfun.com/v1", "models": ["step-2-16k"]},
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
