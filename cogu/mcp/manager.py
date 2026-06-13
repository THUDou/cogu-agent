import json
from pathlib import Path
from typing import Any, Optional

from cogu.mcp.session import MCPSession
from cogu.mcp.tool import MCPTool
from cogu.mcp.safety import command_hash, boot_validate, CommandHash


class MCPManager:
    def __init__(self, config_path: str = ""):
        self.config_path = Path(config_path) if config_path else Path(".cogu/mcp.json")
        self._sessions: dict[str, MCPSession] = {}
        self._tools: list[MCPTool] = []
        self._confirmed_hashes: dict[str, CommandHash] = {}
        self._enabled = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def sessions(self) -> dict[str, MCPSession]:
        return self._sessions

    @property
    def tools(self) -> list[MCPTool]:
        return self._tools

    def load_config(self) -> dict:
        if self.config_path.exists():
            return json.loads(self.config_path.read_text(encoding="utf-8"))
        return {}

    def save_config(self, config: dict):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    async def connect_all(self) -> list[str]:
        config = self.load_config()
        servers = config.get("mcp", {}).get("servers", {})
        errors = []
        for name, server_config in servers.items():
            if not server_config.get("enabled", True):
                continue
            session = MCPSession(
                server_name=name,
                transport=server_config.get("transport", "stdio"),
                command=server_config.get("command", ""),
                args=server_config.get("args", []),
                env=server_config.get("env", {}),
                url=server_config.get("url", ""),
            )
            connected = await session.connect()
            if connected:
                self._sessions[name] = session
                for tool_def in session.tools:
                    self._tools.append(MCPTool(session, tool_def))
            else:
                errors.append(name)
        return errors

    async def disconnect_all(self):
        for session in self._sessions.values():
            await session.disconnect()
        self._sessions.clear()
        self._tools.clear()

    def get_tool(self, name: str) -> Optional[MCPTool]:
        for tool in self._tools:
            if tool.name() == name:
                return tool
        return None

    def get_tools_for_registry(self) -> list[MCPTool]:
        return list(self._tools)

    def validate_boot(self) -> list[str]:
        config = self.load_config()
        servers = config.get("mcp", {}).get("servers", {})
        confirmed = {}
        for name, sc in servers.items():
            if sc.get("transport") == "stdio":
                h = command_hash(sc.get("command", ""), sc.get("args", []))
                confirmed[name] = h
        return boot_validate(servers, confirmed)
