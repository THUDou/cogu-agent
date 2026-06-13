import asyncio
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class MCPSessionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    FAILED = "failed"


@dataclass
class MCPToolDef:
    name: str = ""
    description: str = ""
    input_schema: dict = field(default_factory=dict)
    raw_input_schema: dict = field(default_factory=dict)


class MCPSession:
    def __init__(
        self,
        server_name: str,
        transport: str = "stdio",
        command: str = "",
        args: list[str] = None,
        env: dict = None,
        url: str = "",
        timeout: float = 10.0,
    ):
        self.server_name = server_name
        self.transport = transport
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.url = url
        self.timeout = timeout
        self._state = MCPSessionState.DISCONNECTED
        self._tools: list[MCPToolDef] = []
        self._closing = False
        self._inflight = 0
        self._process: Optional[asyncio.subprocess.Process] = None

    @property
    def state(self) -> MCPSessionState:
        return self._state

    @property
    def tools(self) -> list[MCPToolDef]:
        return self._tools

    @property
    def is_connected(self) -> bool:
        return self._state == MCPSessionState.CONNECTED

    async def connect(self) -> bool:
        if self._state == MCPSessionState.CONNECTED:
            return True
        self._state = MCPSessionState.CONNECTING
        try:
            if self.transport == "stdio":
                await self._connect_stdio()
            elif self.transport in ("sse", "http"):
                await self._connect_http()
            elif self.transport == "streamable_http":
                await self._connect_streamable_http()
            self._state = MCPSessionState.CONNECTED
            await self._list_tools()
            return True
        except Exception:
            self._state = MCPSessionState.FAILED
            return False

    async def disconnect(self):
        self._closing = True
        while self._inflight > 0:
            await asyncio.sleep(0.1)
        if self._process:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None
        self._state = MCPSessionState.DISCONNECTED
        self._tools = []
        self._closing = False

    async def call_tool(self, name: str, arguments: dict, timeout: float = 60.0) -> dict:
        if not self.is_connected:
            return {"error": "not connected"}
        self._inflight += 1
        try:
            result = await asyncio.wait_for(
                self._execute_tool(name, arguments),
                timeout=timeout,
            )
            return result
        except asyncio.TimeoutError:
            return {"error": f"tool '{name}' timed out after {timeout}s"}
        except Exception as e:
            return {"error": str(e)}
        finally:
            self._inflight -= 1

    async def _connect_stdio(self):
        cmd_parts = [self.command] + self.args
        import shlex
        cmd_str = " ".join(cmd_parts)
        self._process = await asyncio.create_subprocess_shell(
            cmd_str,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self.env if self.env else None,
        )
        init_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "cogu-mcp", "version": "0.1.0"},
            },
        }
        await self._send_message(init_msg)
        response = await asyncio.wait_for(self._read_message(), timeout=self.timeout)
        if response and "result" in response:
            tools_msg = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            }
            await self._send_message(tools_msg)

    async def _connect_http(self):
        pass

    async def _connect_streamable_http(self):
        pass

    async def _list_tools(self):
        if self.transport == "stdio" and self._process:
            response = await asyncio.wait_for(self._read_message(), timeout=self.timeout)
            if response and "result" in response:
                tools = response["result"].get("tools", [])
                self._tools = [
                    MCPToolDef(
                        name=t.get("name", ""),
                        description=t.get("description", ""),
                        input_schema=t.get("inputSchema", {}),
                        raw_input_schema=t.get("inputSchema", {}),
                    )
                    for t in tools
                ]

    async def _execute_tool(self, name: str, arguments: dict) -> dict:
        if self.transport == "stdio" and self._process:
            call_msg = {
                "jsonrpc": "2.0",
                "id": int(time.time() * 1000),
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
            await self._send_message(call_msg)
            response = await asyncio.wait_for(self._read_message(), timeout=60.0)
            if response and "result" in response:
                return response["result"]
            return {"error": response.get("error", "unknown error") if response else "no response"}
        return {"error": f"unsupported transport: {self.transport}"}

    async def _send_message(self, msg: dict):
        if self._process and self._process.stdin:
            data = json.dumps(msg) + "\n"
            self._process.stdin.write(data.encode())
            await self._process.stdin.drain()

    async def _read_message(self) -> Optional[dict]:
        if self._process and self._process.stdout:
            line = await self._process.stdout.readline()
            if line:
                return json.loads(line.decode().strip())
        return None
