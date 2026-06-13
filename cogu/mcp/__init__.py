"""
COGU MCP — Model Context Protocol 全栈客户端
融合 Syll MCP (Schema归一化/command_hash/3层认证) + Mini-Agent MCP适配器
"""

from cogu.mcp.manager import MCPManager
from cogu.mcp.session import MCPSession
from cogu.mcp.tool import MCPTool
from cogu.mcp.schema import normalize_schema_for_openai

__all__ = [
    "MCPManager",
    "MCPSession",
    "MCPTool",
    "normalize_schema_for_openai",
]
