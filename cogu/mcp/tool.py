from typing import Any, Optional

from cogu.tools.base import ToolSpec
from cogu.mcp.schema import normalize_schema_for_openai


class MCPTool(ToolSpec):
    def __init__(self, session, tool_def):
        self._session = session
        self._tool_def = tool_def
        self._raw_schema = tool_def.raw_input_schema
        self._normalized_schema = normalize_schema_for_openai(self._raw_schema)

    def name(self) -> str:
        return f"mcp__{self._session.server_name}__{self._tool_def.name}"

    def description(self) -> str:
        return self._tool_def.description or f"MCP tool from {self._session.server_name}"

    def input_schema(self) -> dict:
        return self._normalized_schema

    async def execute(self, **kwargs) -> Any:
        return await self._session.call_tool(self._tool_def.name, kwargs)
