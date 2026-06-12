from dataclasses import dataclass, field
from typing import Optional
import os
import json
from pathlib import Path


@dataclass
class ProviderConfig:
    name: str
    api_key: str = ""
    base_url: str = ""
    models: list[str] = field(default_factory=list)

    @property
    def default_model(self) -> str:
        return self.models[0] if self.models else ""


@dataclass
class DeepSeekConfig(ProviderConfig):
    name: str = "deepseek"
    base_url: str = "https://api.deepseek.com"
    models: list[str] = field(default_factory=lambda: [
        "deepseek-chat",
        "deepseek-reasoner",
    ])
    reasoning_effort: str = "medium"
    max_tokens: int = 16384
    context_window: int = 1000000


@dataclass
class MemoryConfig:
    db_path: str = ""
    fts_enabled: bool = True
    checkpoint_interval: int = 10
    max_messages: int = 10000
    compressor_model: str = "deepseek-chat"


@dataclass
class AgentConfig:
    model: str = "deepseek-chat"
    max_iterations: int = 25
    max_context_messages: int = 100
    default_window_rounds: int = 10
    temperature: float = 0.7
    top_p: float = 0.95
    system_prompt: Optional[str] = None


@dataclass
class DebateConfig:
    num_experts: int = 3
    max_rounds: int = 5
    pes_enabled: bool = True
    team_mode: str = "hots"
    evolution_islands: int = 3
    evolution_population: int = 50


@dataclass
class ToolConfig:
    sandbox_enabled: bool = True
    approval_mode: str = "auto"
    max_shell_timeout: int = 120
    allowed_paths: list[str] = field(default_factory=list)


@dataclass
class TUIConfig:
    enabled: bool = True
    theme: str = "dark"
    history_file: str = ".cogu_history"


@dataclass
class PanguMiniConfig:
    enabled: bool = False
    backend: str = "auto"
    model_dir: str = ""
    gguf_path: str = ""
    api_port: int = 8199
    device: str = "auto"
    _memorial: str = '2026.6.12 — COGU 诞生日，也是华为发布 OpenPangu 2.0 的日子。中国最早的大模型、领跑世界的大模型、国内首个全栈自主的大模型即将满血归来，宣布追赶"世界第一"。为做纪念，将此模型加入项目中。'


@dataclass
class Settings:
    deepseek: DeepSeekConfig = field(default_factory=DeepSeekConfig)
    providers: list[ProviderConfig] = field(default_factory=list)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    debate: DebateConfig = field(default_factory=DebateConfig)
    tools: ToolConfig = field(default_factory=ToolConfig)
    tui: TUIConfig = field(default_factory=TUIConfig)
    pangu_mini: PanguMiniConfig = field(default_factory=PanguMiniConfig)
    workspace: str = ""

    @classmethod
    def from_file(cls, path: str) -> "Settings":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        settings = cls()
        if "deepseek" in data:
            settings.deepseek = DeepSeekConfig(**data["deepseek"])
        if "memory" in data:
            settings.memory = MemoryConfig(**data["memory"])
        if "agent" in data:
            settings.agent = AgentConfig(**data["agent"])
        if "debate" in data:
            settings.debate = DebateConfig(**data["debate"])
        if "tools" in data:
            settings.tools = ToolConfig(**data["tools"])
        if "pangu_mini" in data:
            settings.pangu_mini = PanguMiniConfig(**{k: v for k, v in data["pangu_mini"].items() if not k.startswith("_")})
        if "providers" in data:
            settings.providers = [ProviderConfig(**p) for p in data["providers"]]
        return settings

    def to_dict(self) -> dict:
        return {
            "deepseek": self.deepseek.__dict__,
            "memory": self.memory.__dict__,
            "agent": self.agent.__dict__,
            "debate": self.debate.__dict__,
            "tools": self.tools.__dict__,
            "providers": [p.__dict__ for p in self.providers],
            "pangu_mini": {k: v for k, v in self.pangu_mini.__dict__.items() if not k.startswith("_")},
        }

    def resolve_api_key(self, provider: str) -> str:
        if provider == "deepseek":
            return self.deepseek.api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        env_key = f"{provider.upper()}_API_KEY"
        return os.environ.get(env_key, "")

    @classmethod
    def load(cls, workspace: str = "") -> "Settings":
        config_path = Path(workspace) / ".cogu" / "config.json" if workspace else None
        if config_path and config_path.exists():
            try:
                return cls.from_file(str(config_path))
            except (json.JSONDecodeError, IOError):
                pass
        return cls.default(workspace)

    @classmethod
    def default(cls, workspace: str = "") -> "Settings":
        s = cls()
        s.workspace = workspace or str(Path.home() / ".cogu")
        s.memory.db_path = str(Path(s.workspace) / "memory.db")
        return s
