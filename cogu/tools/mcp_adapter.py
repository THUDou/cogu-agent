"""MCP adapter for COGU — supports stdio / SSE / HTTP / StreamableHTTP.

Ported from Mini-Agent mini_agent/tools/mcp_loader.py (MiniMax),
with COGU tool system integration.

Requires::

    pip install mcp>=1.0

Usage::

    from cogu.tools.mcp_adapter import load_mcp_tools, cleanup_mcp
    tools = await load_mcp_tools("mcp.json")
    # register into ToolRegistry
    for t in tools:
        registry.register(t)
"""

from __future__ import annotations

import asyncio
import json
import uuid
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from cogu.tools.base import ToolSpec, ToolResult

# ---------------------------------------------------------------------------
# Connection type
# ---------------------------------------------------------------------------

ConnectionType = Literal["stdio", "sse", "http", "streamable_http"]


# ---------------------------------------------------------------------------
# Timeout config
# ---------------------------------------------------------------------------

@dataclass
class MCPTimeoutConfig:
    connect_timeout: float = 10.0
    execute_timeout: float = 60.0
    sse_read_timeout: float = 120.0


_default_timeout = MCPTimeoutConfig()


def set_mcp_timeout(connect: float | None = None, execute: float | None = None, sse: float | None = None) -> None:
    if connect is not None:
        _default_timeout.connect_timeout = connect
    if execute is not None:
        _default_timeout.execute_timeout = execute
    if sse is not None:
        _default_timeout.sse_read_timeout = sse


def get_mcp_timeout() -> MCPTimeoutConfig:
    return _default_timeout


# ---------------------------------------------------------------------------
# COGU MCP Tool wrapper
# ---------------------------------------------------------------------------

class MCPTool(ToolSpec):
    """COGU Tool wrapping one MCP server tool call."""

    def __init__(self, name: str, description: str, parameters: dict[str, Any],
                 session: Any, execute_timeout: float | None = None):
        self._name = name
        self._description = description
        self._parameters = parameters
        self._session = session
        self._execute_timeout = execute_timeout

    def name(self) -> str:
        return self._name

    def description(self) -> str:
        return self._description

    def input_schema(self) -> dict:
        return self._parameters

    @property
    def parameters(self) -> dict[str, Any]:
        return self._parameters

    async def execute(self, input: dict = None, **kwargs) -> ToolResult:
        call_args = input if input else kwargs
        timeout = self._execute_timeout or _default_timeout.execute_timeout
        try:
            async with asyncio.timeout(timeout):
                result = await self._session.call_tool(self._name, arguments=call_args)
            parts: list[str] = []
            for item in (result.content or []):
                if hasattr(item, "text"):
                    parts.append(item.text)
                else:
                    parts.append(str(item))
            content_str = "\n".join(parts)
            is_error = getattr(result, "isError", False)
            return ToolResult(success=not is_error, content=content_str,
                           error=None if not is_error else "MCP tool returned error")
        except TimeoutError:
            return ToolResult(success=False, content="",
                               error=f"MCP tool timed out after {timeout}s")
        except Exception as e:
            return ToolResult(success=False, content="", error=f"MCP error: {e}")


# ---------------------------------------------------------------------------
# MCP Server connection manager
# ---------------------------------------------------------------------------

class MCPServerConnection:
    def __init__(self, name: str, connection_type: ConnectionType = "stdio",
                 command: str | None = None, args: list[str] | None = None,
                 env: dict[str, str] | None = None,
                 url: str | None = None, headers: dict[str, str] | None = None,
                 connect_timeout: float | None = None,
                 execute_timeout: float | None = None,
                 sse_read_timeout: float | None = None):
        self.name = name
        self.connection_type = connection_type
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.url = url
        self.headers = headers or {}
        self.connect_timeout = connect_timeout
        self.execute_timeout = execute_timeout
        self.sse_read_timeout = sse_read_timeout
        self.session: Any = None
        self.exit_stack: AsyncExitStack | None = None
        self.tools: list[MCPTool] = []

    async def connect(self) -> bool:
        try:
            from mcp.client.stdio import stdio_client
            from mcp.client.sse import sse_client
            from mcp.client.streamable_http import streamablehttp_client
            from mcp import ClientSession
        except ImportError:
            print("[MCP] mcp package not installed. Run: pip install mcp")
            return False

        self.exit_stack = AsyncExitStack()
        try:
            async with asyncio.timeout(self.connect_timeout or _default_timeout.connect_timeout):
                if self.connection_type == "stdio":
                    read, write = await self.exit_stack.enter_async_context(
                        stdio_client(self.command, self.args, self.env or None))
                elif self.connection_type == "sse":
                    read, write = await self.exit_stack.enter_async_context(
                        sse_client(self.url, self.headers or None,
                                      timeout=self.connect_timeout or _default_timeout.connect_timeout,
                                      sse_read_timeout=self.sse_read_timeout or _default_timeout.sse_read_timeout))
                else:
                    read, write, _ = await self.exit_stack.enter_async_context(
                        streamablehttp_client(self.url, self.headers or None,
                                                timeout=self.connect_timeout or _default_timeout.connect_timeout,
                                                sse_read_timeout=self.sse_read_timeout or _default_timeout.sse_read_timeout))
                session = await self.exit_stack.enter_async_context(ClientSession(read, write))
                self.session = session
                await session.initialize()
                tools_list = await session.list_tools()

            exec_timeout = self.execute_timeout or _default_timeout.execute_timeout
            for t in tools_list.tools:
                params = t.inputSchema if hasattr(t, "inputSchema") else {}
                self.tools.append(MCPTool(t.name, t.description or "", params,
                                           session, exec_timeout))
            print(f"[MCP] ✓ {self.name}: {len(self.tools)} tools loaded")
            return True
        except TimeoutError:
            print(f"[MCP] ✗ {self.name}: connection timed out")
            await self._safe_close()
            return False
        except Exception as e:
            print(f"[MCP] ✗ {self.name}: {e}")
            await self._safe_close()
            return False

    async def _safe_close(self):
        if self.exit_stack:
            try:
                await self.exit_stack.aclose()
            except Exception:
                pass
            finally:
                self.exit_stack = None
                self.session = None

    async def disconnect(self):
        await self._safe_close()


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def _resolve_config(path: str) -> Path | None:
    p = Path(path)
    if p.exists():
        return p
    if p.name == "mcp.json":
        fallback = p.parent / "mcp-example.json"
        if fallback.exists():
            print(f"[MCP] mcp.json not found, using {fallback}")
            return fallback
    return None


async def load_mcp_tools(config_path: str = "mcp.json") -> list[ToolSpec]:
    config_file = _resolve_config(config_path)
    if config_file is None:
        print(f"[MCP] config not found: {config_path}")
        return []

    try:
        from mcp import ClientSession
    except ImportError:
        print("[MCP] mcp package not installed. Run: pip install mcp")
        return []

    with open(config_file, encoding="utf-8") as f:
        config = json.load(f)

    servers = config.get("mcpServers", {})
    if not servers:
        print("[MCP] no mcpServers configured")
        return []

    all_tools: list[ToolSpec] = []
    for name, cfg in servers.items():
        if cfg.get("disabled"):
            continue
        ct: ConnectionType = cfg.get("type", "stdio")
        if ct == "stdio" and not cfg.get("command"):
            continue
        if ct != "stdio" and not cfg.get("url"):
            continue
        conn = MCPServerConnection(
            name=name, connection_type=ct,
            command=cfg.get("command"), args=cfg.get("args", []), env=cfg.get("env", {}),
            url=cfg.get("url"), headers=cfg.get("headers", {}),
            connect_timeout=cfg.get("connect_timeout"),
            execute_timeout=cfg.get("execute_timeout"),
            sse_read_timeout=cfg.get("sse_read_timeout"),
        )
        if await conn.connect():
            all_tools.extend(conn.tools)
            _active_connections.append(conn)

    print(f"[MCP] total loaded: {len(all_tools)} tools from {len(_active_connections)} server(s)")
    return all_tools


async def cleanup_mcp() -> None:
    for conn in _active_connections:
        await conn.disconnect()
    _active_connections.clear()


_active_connections: list[MCPServerConnection] = []
