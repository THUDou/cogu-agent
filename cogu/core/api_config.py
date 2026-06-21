import os
import json
import base64
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class Provider(str, Enum):
    OPENAI = "openai"
    CLAUDE = "claude"
    DEEPSEEK = "deepseek"
    QWEN = "qwen"
    ZHIPU = "zhipu"
    MOONSHOT = "moonshot"
    MINIMAX = "minimax"
    DOUBAO = "doubao"
    HUAWEI_CLOUD = "huawei_cloud"
    TENCENT_CLOUD = "tencent_cloud"
    LOCAL_PANGU = "local_pangu"
    LOCAL_QWEN = "local_qwen"
    OLLAMA = "ollama"
    CUSTOM = "custom"


PROVIDER_DEFAULTS = {
    Provider.OPENAI: {
        "base_url": "https://api.openai.com/v1",
        "chat_path": "/chat/completions",
        "models_path": "/models",
        "default_model": "gpt-4o",
        "headers_template": {"Authorization": "Bearer {api_key}"},
    },
    Provider.CLAUDE: {
        "base_url": "https://api.anthropic.com/v1",
        "chat_path": "/messages",
        "default_model": "claude-sonnet-4-20250514",
        "headers_template": {
            "x-api-key": "{api_key}",
            "anthropic-version": "2023-06-01",
        },
    },
    Provider.DEEPSEEK: {
        "base_url": "https://api.deepseek.com",
        "chat_path": "/chat/completions",
        "default_model": "deepseek-chat",
        "headers_template": {"Authorization": "Bearer {api_key}"},
    },
    Provider.QWEN: {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "chat_path": "/chat/completions",
        "default_model": "qwen-max",
        "headers_template": {"Authorization": "Bearer {api_key}"},
    },
    Provider.ZHIPU: {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "chat_path": "/chat/completions",
        "default_model": "glm-4",
        "headers_template": {"Authorization": "Bearer {api_key}"},
    },
    Provider.MOONSHOT: {
        "base_url": "https://api.moonshot.cn/v1",
        "chat_path": "/chat/completions",
        "default_model": "moonshot-v1-8k",
        "headers_template": {"Authorization": "Bearer {api_key}"},
    },
    Provider.MINIMAX: {
        "base_url": "https://api.minimax.chat/v1",
        "chat_path": "/text/chatcompletion_v2",
        "default_model": "abab6.5s-chat",
        "headers_template": {"Authorization": "Bearer {api_key}"},
    },
    Provider.DOUBAO: {
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "chat_path": "/chat/completions",
        "default_model": "doubao-pro-32k",
        "headers_template": {"Authorization": "Bearer {api_key}"},
    },
    Provider.HUAWEI_CLOUD: {
        "base_url": "https://maas-api.cn-north-4.myhuaweicloud.com/v1",
        "chat_path": "/chat/completions",
        "default_model": "pangu-plus",
        "headers_template": {"Authorization": "Bearer {api_key}"},
    },
    Provider.TENCENT_CLOUD: {
        "base_url": "https://hunyuan.tencentcloudapi.com/v1",
        "chat_path": "/chat/completions",
        "default_model": "hunyuan-lite",
        "headers_template": {"Authorization": "Bearer {api_key}"},
    },
    Provider.LOCAL_PANGU: {
        "base_url": "http://127.0.0.1:8199/v1",
        "chat_path": "/chat/completions",
        "default_model": "openPangu-Embedded-1B",
        "headers_template": {},
    },
    Provider.LOCAL_QWEN: {
        "base_url": "http://127.0.0.1:8199/v1",
        "chat_path": "/chat/completions",
        "default_model": "Qwen3.5-0.8B",
        "headers_template": {},
    },
    Provider.OLLAMA: {
        "base_url": "http://localhost:11434/v1",
        "chat_path": "/chat/completions",
        "models_path": "/models",
        "default_model": "qwen3",
        "headers_template": {},
    },
}


@dataclass
class ProviderConfig:
    provider: Provider
    base_url: str = ""
    chat_path: str = ""
    api_key: str = ""
    default_model: str = ""
    extra_headers: dict = field(default_factory=dict)
    timeout: int = 120
    max_retries: int = 3
    enabled: bool = True

    def __post_init__(self):
        defaults = PROVIDER_DEFAULTS.get(self.provider, {})
        if not self.base_url and "base_url" in defaults:
            self.base_url = defaults["base_url"]
        if not self.chat_path and "chat_path" in defaults:
            self.chat_path = defaults["chat_path"]
        if not self.default_model and "default_model" in defaults:
            self.default_model = defaults["default_model"]

    @property
    def chat_url(self) -> str:
        base = self.base_url.rstrip("/")
        path = self.chat_path
        if path and not path.startswith("/"):
            path = "/" + path
        return base + path

    @property
    def is_openai_compatible(self) -> bool:
        return self.chat_path.endswith("/chat/completions")

    def build_headers(self) -> dict:
        template = PROVIDER_DEFAULTS.get(self.provider, {}).get("headers_template", {})
        headers = {}
        for k, v in template.items():
            headers[k] = v.format(api_key=self.api_key)
        headers.update(self.extra_headers)
        return headers


@dataclass
class ApiTokenRecord:
    provider: Provider
    key_hash: str
    obfuscated_key: str
    label: str = ""
    created_at: float = 0.0
    last_used: float = 0.0
    usage_count: int = 0
    rate_limit_rpm: int = 0
    rate_limit_tpm: int = 0
    tags: list = field(default_factory=list)

    import time as _time

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()


class ApiTokenManager:
    _FERNET_SALT = b"cogu-agent-api-vault-salt"

    def __init__(self, config_dir: Path | str):
        self._config_dir = Path(config_dir)
        self._config_dir.mkdir(parents=True, exist_ok=True)
        self._tokens_file = self._config_dir / "api_tokens.json"
        self._key_file = self._config_dir / ".vault_key"
        self._fernet: Optional[Fernet] = None
        self._providers: dict[Provider, ProviderConfig] = {}
        self._tokens: list[ApiTokenRecord] = []
        self._load_or_init()

    def _derive_key(self, machine_id: str) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self._FERNET_SALT,
            iterations=480000,
        )
        return base64.urlsafe_b64encode(kdf.derive(machine_id.encode()))

    def _get_machine_id(self) -> str:
        mid = os.environ.get("COGU_MACHINE_ID", "")
        if not mid:
            try:
                import uuid
                mid = str(uuid.getnode())
            except Exception:
                mid = "cogu-default-machine"
        return hashlib.sha256(mid.encode()).hexdigest()[:32]

    @property
    def _cipher(self) -> Fernet:
        if self._fernet is None:
            if self._key_file.exists():
                key = self._key_file.read_bytes()
            else:
                key = self._derive_key(self._get_machine_id())
                self._key_file.write_bytes(key)
            self._fernet = Fernet(key)
        return self._fernet

    def _encrypt(self, plain: str) -> str:
        return self._cipher.encrypt(plain.encode()).decode()

    def _decrypt(self, cipher: str) -> str:
        return self._cipher.decrypt(cipher.encode()).decode()

    def _obfuscate(self, key: str) -> str:
        if len(key) <= 8:
            return "****"
        return key[:4] + "*" * (len(key) - 8) + key[-4:]

    def _hash_key(self, key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()

    def _load_or_init(self):
        if self._tokens_file.exists():
            raw = json.loads(self._tokens_file.read_text(encoding="utf-8"))
            for p_data in raw.get("providers", []):
                p = ProviderConfig(
                    provider=Provider(p_data["provider"]),
                    base_url=p_data.get("base_url", ""),
                    chat_path=p_data.get("chat_path", ""),
                    api_key=self._decrypt(p_data["api_key_encrypted"]),
                    default_model=p_data.get("default_model", ""),
                    extra_headers=p_data.get("extra_headers", {}),
                    timeout=p_data.get("timeout", 120),
                    max_retries=p_data.get("max_retries", 3),
                    enabled=p_data.get("enabled", True),
                )
                self._providers[p.provider] = p
            self._tokens = [
                ApiTokenRecord(
                    provider=Provider(t["provider"]),
                    key_hash=t["key_hash"],
                    obfuscated_key=t["obfuscated_key"],
                    label=t.get("label", ""),
                    created_at=t.get("created_at", 0),
                    last_used=t.get("last_used", 0),
                    usage_count=t.get("usage_count", 0),
                    rate_limit_rpm=t.get("rate_limit_rpm", 0),
                    rate_limit_tpm=t.get("rate_limit_tpm", 0),
                    tags=t.get("tags", []),
                )
                for t in raw.get("tokens", [])
            ]

    def save(self):
        data = {
            "providers": [
                {
                    "provider": p.provider.value,
                    "base_url": p.base_url,
                    "chat_path": p.chat_path,
                    "api_key_encrypted": self._encrypt(p.api_key),
                    "default_model": p.default_model,
                    "extra_headers": p.extra_headers,
                    "timeout": p.timeout,
                    "max_retries": p.max_retries,
                    "enabled": p.enabled,
                }
                for p in self._providers.values()
            ],
            "tokens": [
                {
                    "provider": t.provider.value,
                    "key_hash": t.key_hash,
                    "obfuscated_key": t.obfuscated_key,
                    "label": t.label,
                    "created_at": t.created_at,
                    "last_used": t.last_used,
                    "usage_count": t.usage_count,
                    "rate_limit_rpm": t.rate_limit_rpm,
                    "rate_limit_tpm": t.rate_limit_tpm,
                    "tags": t.tags,
                }
                for t in self._tokens
            ],
        }
        self._tokens_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def add_provider(
        self,
        provider: Provider,
        api_key: str,
        base_url: str = "",
        chat_path: str = "",
        default_model: str = "",
        extra_headers: dict = None,
        label: str = "",
    ) -> ProviderConfig:
        cfg = ProviderConfig(
            provider=provider,
            api_key=api_key,
            base_url=base_url,
            chat_path=chat_path,
            default_model=default_model,
            extra_headers=extra_headers or {},
        )
        self._providers[provider] = cfg
        self._tokens.append(
            ApiTokenRecord(
                provider=provider,
                key_hash=self._hash_key(api_key),
                obfuscated_key=self._obfuscate(api_key),
                label=label or provider.value,
            )
        )
        self.save()
        return cfg

    def remove_provider(self, provider: Provider) -> bool:
        if provider in self._providers:
            del self._providers[provider]
            self._tokens = [t for t in self._tokens if t.provider != provider]
            self.save()
            return True
        return False

    def get_provider(self, provider: Provider) -> Optional[ProviderConfig]:
        return self._providers.get(provider)

    def list_providers(self) -> list[ProviderConfig]:
        return [p for p in self._providers.values() if p.enabled]

    def list_all_providers(self) -> list[ProviderConfig]:
        return list(self._providers.values())

    def list_tokens(self) -> list[ApiTokenRecord]:
        return list(self._tokens)

    def update_provider(self, provider: Provider, **kwargs) -> Optional[ProviderConfig]:
        cfg = self._providers.get(provider)
        if not cfg:
            return None
        for k, v in kwargs.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        if "api_key" in kwargs:
            for t in self._tokens:
                if t.provider == provider:
                    t.key_hash = self._hash_key(kwargs["api_key"])
                    t.obfuscated_key = self._obfuscate(kwargs["api_key"])
        self.save()
        return cfg

    def record_usage(self, provider: Provider):
        import time
        for t in self._tokens:
            if t.provider == provider:
                t.last_used = time.time()
                t.usage_count += 1
        self.save()

    def get_active_config(self) -> Optional[ProviderConfig]:
        cloud_priority = [
            Provider.DEEPSEEK, Provider.OPENAI, Provider.CLAUDE,
            Provider.QWEN, Provider.HUAWEI_CLOUD, Provider.TENCENT_CLOUD,
            Provider.ZHIPU, Provider.MOONSHOT, Provider.MINIMAX, Provider.DOUBAO,
        ]
        for p in cloud_priority:
            cfg = self._providers.get(p)
            if cfg and cfg.enabled and cfg.api_key:
                return cfg
        for cfg in self._providers.values():
            if cfg.enabled and cfg.api_key and cfg.provider not in (Provider.LOCAL_PANGU, Provider.LOCAL_QWEN, Provider.OLLAMA):
                return cfg
        ollama_cfg = self._providers.get(Provider.OLLAMA)
        if ollama_cfg and ollama_cfg.enabled:
            return ollama_cfg
        try:
            from cogu.mini_engine.local_server_manager import check_ollama_available
            if check_ollama_available():
                ollama_cfg = ProviderConfig(provider=Provider.OLLAMA)
                self._providers[Provider.OLLAMA] = ollama_cfg
                return ollama_cfg
        except Exception:
            pass
        local_priority = [Provider.LOCAL_QWEN, Provider.LOCAL_PANGU]
        for p in local_priority:
            cfg = self._providers.get(p)
            if cfg and cfg.enabled:
                return cfg
        try:
            from cogu.mini_engine.local_server_manager import ensure_local_model_available
            local_cfg = ensure_local_model_available(self)
            if local_cfg:
                self._providers[local_cfg.provider] = local_cfg
                return local_cfg
        except Exception:
            pass
        return None

    def to_env_dict(self) -> dict[str, str]:
        env = {}
        for provider, cfg in self._providers.items():
            prefix = provider.value.upper()
            env[f"COGU_{prefix}_API_KEY"] = cfg.api_key
            env[f"COGU_{prefix}_BASE_URL"] = cfg.base_url
            env[f"COGU_{prefix}_MODEL"] = cfg.default_model
        return env

    def export_env_file(self, path: Path | str):
        path = Path(path)
        lines = ["# COGU AGENT API Configuration"]
        for k, v in self.to_env_dict().items():
            lines.append(f"{k}={v}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class OpenAICompatibleAdapter:

    def __init__(self, config: ProviderConfig):
        self._config = config

    def build_request(
        self,
        messages: list[dict],
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list[dict] = None,
        stream: bool = True,
        **kwargs,
    ) -> dict:
        body = {
            "model": model or self._config.default_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        body.update(kwargs)
        return body

    def build_headers(self) -> dict:
        headers = self._config.build_headers()
        headers.setdefault("Content-Type", "application/json")
        return headers

    @property
    def chat_url(self) -> str:
        return self._config.chat_url

    @property
    def is_openai_format(self) -> bool:
        return self._config.is_openai_compatible


class ClaudeAdapter(OpenAICompatibleAdapter):

    def build_request(
        self,
        messages: list[dict],
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list[dict] = None,
        stream: bool = True,
        **kwargs,
    ) -> dict:
        system_msgs = [m for m in messages if m.get("role") == "system"]
        chat_msgs = [m for m in messages if m.get("role") != "system"]
        converted = []
        for m in chat_msgs:
            entry = {"role": m["role"], "content": m.get("content", "")}
            if m["role"] == "assistant" and "tool_calls" in m:
                tool_use_blocks = []
                for tc in m["tool_calls"]:
                    tool_use_blocks.append({
                        "type": "tool_use",
                        "id": tc.get("id", ""),
                        "name": tc.get("function", {}).get("name", ""),
                        "input": json.loads(tc.get("function", {}).get("arguments", "{}")),
                    })
                entry["content"] = tool_use_blocks
            converted.append(entry)
        body = {
            "model": model or self._config.default_model,
            "messages": converted,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }
        if system_msgs:
            body["system"] = "\n".join(m["content"] for m in system_msgs)
        if tools:
            claude_tools = []
            for t in tools:
                if t.get("type") == "function":
                    claude_tools.append({
                        "name": t["function"]["name"],
                        "description": t["function"].get("description", ""),
                        "input_schema": t["function"].get("parameters", {}),
                    })
            if claude_tools:
                body["tools"] = claude_tools
        body.update(kwargs)
        return body

    def build_headers(self) -> dict:
        headers = super().build_headers()
        headers.pop("Content-Type", None)
        return headers


ADAPTER_MAP = {
    Provider.OPENAI: OpenAICompatibleAdapter,
    Provider.DEEPSEEK: OpenAICompatibleAdapter,
    Provider.QWEN: OpenAICompatibleAdapter,
    Provider.ZHIPU: OpenAICompatibleAdapter,
    Provider.MOONSHOT: OpenAICompatibleAdapter,
    Provider.MINIMAX: OpenAICompatibleAdapter,
    Provider.DOUBAO: OpenAICompatibleAdapter,
    Provider.HUAWEI_CLOUD: OpenAICompatibleAdapter,
    Provider.TENCENT_CLOUD: OpenAICompatibleAdapter,
    Provider.LOCAL_PANGU: OpenAICompatibleAdapter,
    Provider.LOCAL_QWEN: OpenAICompatibleAdapter,
    Provider.OLLAMA: OpenAICompatibleAdapter,
    Provider.CLAUDE: ClaudeAdapter,
}


def create_adapter(config: ProviderConfig):
    adapter_cls = ADAPTER_MAP.get(config.provider, OpenAICompatibleAdapter)
    return adapter_cls(config)


class MultiProviderClient:

    def __init__(self, token_manager: ApiTokenManager):
        self._tm = token_manager
        self._adapters: dict[Provider, OpenAICompatibleAdapter] = {}
        self._refresh_adapters()

    def _refresh_adapters(self):
        for cfg in self._tm.list_providers():
            self._adapters[cfg.provider] = create_adapter(cfg)

    @property
    def primary_provider(self) -> Optional[Provider]:
        cfg = self._tm.get_active_config()
        return cfg.provider if cfg else None

    @property
    def primary_adapter(self) -> Optional[OpenAICompatibleAdapter]:
        cfg = self._tm.get_active_config()
        if cfg:
            return self._adapters.get(cfg.provider)
        return None

    def get_adapter(self, provider: Provider) -> Optional[OpenAICompatibleAdapter]:
        return self._adapters.get(provider)

    def list_available(self) -> list[Provider]:
        return list(self._adapters.keys())

    def add_provider_adapter(self, cfg: ProviderConfig):
        self._adapters[cfg.provider] = create_adapter(cfg)

    def remove_provider_adapter(self, provider: Provider):
        self._adapters.pop(provider, None)
