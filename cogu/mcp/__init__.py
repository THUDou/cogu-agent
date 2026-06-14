"""
COGU MCP — Model Context Protocol 全栈客户端 + A2A Agent-to-Agent 协议
融合 Syll MCP (Schema归一化/command_hash/3层认证) + Mini-Agent MCP适配器 + openJiuwen A2A
"""

from cogu.mcp.manager import MCPManager
from cogu.mcp.session import MCPSession
from cogu.mcp.tool import MCPTool
from cogu.mcp.schema import normalize_schema_for_openai
from cogu.mcp.a2a_adapter import (
    A2AClient,
    A2AServer,
    A2AExecutor,
    A2AAgentCard,
    A2ATask,
    A2ATaskState,
    A2AMessage,
    A2APart,
    A2AResponse,
)

__all__ = [
    "MCPManager",
    "MCPSession",
    "MCPTool",
    "normalize_schema_for_openai",
    "A2AClient",
    "A2AServer",
    "A2AExecutor",
    "A2AAgentCard",
    "A2ATask",
    "A2ATaskState",
    "A2AMessage",
    "A2APart",
    "A2AResponse",
]
