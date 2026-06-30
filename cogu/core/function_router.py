"""智能路由子代理 — Function Router Provider

融合自摩尔线程MTClaw function_router/server.py
核心能力:
- 本地路由模型判断是否命中自定义工具(6.85x加速)
- 元数据清洗: 清理工具定义中的环境变量和敏感信息
- Session-Scoped双上下文: Qwen内部上下文 + Upstream上游上下文
- Completion Check子代理: 判断任务是否完成
"""
import json
import logging
import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("cogu.core.function_router")

ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: Dict[str, Any]
    script_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RouteResult:
    hit: bool
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    response_text: Optional[str] = None
    execution_result: Optional[Any] = None
    execution_time_ms: float = 0.0


class CompletionChecker:
    """任务完成判断子代理

    融合MTClaw fr_completion_check机制:
    判断当前对话是否已达到自然终止点
    """

    COMPLETION_PROMPT = """You are a task completion judge.

Return TASK_COMPLETE if:
- the assistant completed the request, or
- the assistant successfully moved the task forward and is now waiting for the user.

Return TASK_INCOMPLETE only if:
- a necessary tool call failed,
- the assistant was blocked,
- or the task did not reach a valid stopping point.

Reply with exactly one of:
TASK_COMPLETE
TASK_INCOMPLETE"""

    def __init__(self, llm_client=None, mode: str = "permissive"):
        self.llm_client = llm_client
        self.mode = mode

    def check(self, conversation: List[Dict]) -> bool:
        """判断任务是否完成

        Args:
            conversation: 对话历史

        Returns:
            True if task is complete
        """
        if self.mode == "always_true":
            return True

        if not self.llm_client:
            return self._heuristic_check(conversation)

        try:
            messages = [
                {"role": "system", "content": self.COMPLETION_PROMPT},
            ]
            messages.extend(conversation[-6:])

            response = self.llm_client(messages)
            return "TASK_COMPLETE" in (response or "").upper()
        except Exception as e:
            logger.warning("Completion check失败: %s, 使用启发式", e)
            return self._heuristic_check(conversation)

    @staticmethod
    def _heuristic_check(conversation: List[Dict]) -> bool:
        """启发式完成判断(无LLM时)"""
        if not conversation:
            return False

        last_assistant = ""
        for msg in reversed(conversation):
            if msg.get("role") == "assistant":
                last_assistant = str(msg.get("content", ""))
                break

        incomplete_signals = ["error", "failed", "failed to", "i cannot", "无法"]
        for signal in incomplete_signals:
            if signal in last_assistant.lower():
                return False

        return len(last_assistant) > 20


class FunctionRouter:
    """智能路由子代理

    融合MTClaw核心路由能力:
    - 本地路由模型快速判断是否命中自定义工具
    - 命中时本地执行, 未命中时透传上游
    - Session-Scoped双上下文管理
    - 元数据清洗(环境变量/敏感信息)
    """

    def __init__(
        self,
        tools: Optional[List[ToolDefinition]] = None,
        routing_llm=None,
        upstream_llm=None,
        max_tool_rounds: int = 5,
        tool_executor: Optional[Callable] = None,
        completion_checker: Optional[CompletionChecker] = None,
    ):
        self.tools: Dict[str, ToolDefinition] = {}
        if tools:
            for tool in tools:
                self.tools[tool.name] = tool

        self.routing_llm = routing_llm
        self.upstream_llm = upstream_llm
        self.max_tool_rounds = max_tool_rounds
        self.tool_executor = tool_executor
        self.completion_checker = completion_checker or CompletionChecker()

        self._qwen_contexts: Dict[str, List[Dict]] = {}
        self._upstream_turns: Dict[str, List[Dict]] = {}
        self._tool_history: deque = deque(maxlen=200)

    def register_tool(self, tool: ToolDefinition):
        """注册自定义工具"""
        self.tools[tool.name] = tool
        logger.info("注册工具: %s", tool.name)

    def route(
        self,
        messages: List[Dict],
        session_key: str = "default",
    ) -> RouteResult:
        """路由请求

        1. 使用路由模型判断是否命中自定义工具
        2. 命中: 本地执行工具, 返回结果
        3. 未命中: 透传上游模型
        """
        start_time = time.time()

        if not self.tools:
            return self._fallback_upstream(messages, session_key, start_time)

        tool_names = list(self.tools.keys())
        tool_specs = self._build_tool_specs()

        route_prompt = self._build_route_prompt(messages, tool_names, tool_specs)

        if self.routing_llm:
            try:
                route_response = self.routing_llm([{"role": "user", "content": route_prompt}])
                tool_call = self._parse_route_response(route_response)

                if tool_call and tool_call.get("name") in self.tools:
                    tool_def = self.tools[tool_call["name"]]
                    result = self._execute_tool(tool_def, tool_call.get("arguments", {}))

                    elapsed = (time.time() - start_time) * 1000
                    self._tool_history.append({
                        "tool": tool_def.name,
                        "success": result is not None,
                        "time_ms": elapsed,
                    })

                    return RouteResult(
                        hit=True,
                        tool_name=tool_def.name,
                        tool_args=tool_call.get("arguments", {}),
                        execution_result=result,
                        execution_time_ms=elapsed,
                    )
            except Exception as e:
                logger.error("路由判断失败: %s", e)

        return self._fallback_upstream(messages, session_key, start_time)

    def _build_tool_specs(self) -> str:
        """构建工具规格描述"""
        specs = []
        for name, tool in self.tools.items():
            spec = {
                "name": name,
                "description": self._sanitize_description(tool.description),
                "parameters": tool.parameters,
            }
            specs.append(json.dumps(spec, ensure_ascii=False))
        return "\n".join(specs)

    @staticmethod
    def _build_route_prompt(messages: List[Dict], tool_names: List[str], tool_specs: str) -> str:
        """构建路由判断prompt"""
        last_user = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user = str(msg.get("content", ""))
                break

        return (
            f"Available tools: {', '.join(tool_names)}\n\n"
            f"Tool specifications:\n{tool_specs}\n\n"
            f"User request: {last_user}\n\n"
            f"If the user request matches a tool, respond with JSON: "
            f'{{"name": "tool_name", "arguments": {{...}}}}\n'
            f"If no tool matches, respond with: NO_TOOL_MATCH"
        )

    @staticmethod
    def _parse_route_response(response: str) -> Optional[Dict]:
        """解析路由响应"""
        if not response or "NO_TOOL_MATCH" in response.upper():
            return None

        try:
            start = response.index("{")
            end = response.rindex("}") + 1
            return json.loads(response[start:end])
        except (ValueError, json.JSONDecodeError):
            return None

    def _execute_tool(self, tool: ToolDefinition, arguments: Dict[str, Any]) -> Optional[Any]:
        """执行工具"""
        if self.tool_executor:
            return self.tool_executor(tool.name, arguments)

        logger.warning("无工具执行器, 工具 %s 未执行", tool.name)
        return None

    def _fallback_upstream(
        self, messages: List[Dict], session_key: str, start_time: float
    ) -> RouteResult:
        """透传上游模型"""
        if self.upstream_llm:
            try:
                response = self.upstream_llm(messages)
                elapsed = (time.time() - start_time) * 1000
                return RouteResult(
                    hit=False,
                    response_text=response,
                    execution_time_ms=elapsed,
                )
            except Exception as e:
                logger.error("上游调用失败: %s", e)

        return RouteResult(hit=False, execution_time_ms=(time.time() - start_time) * 1000)

    @staticmethod
    def _sanitize_description(description: str) -> str:
        """清洗工具描述中的环境变量和敏感信息"""
        def replace_env(match):
            var_name = match.group(1)
            return f"[{var_name}]"

        return ENV_PATTERN.sub(replace_env, description)

    def get_session_context(self, session_key: str) -> List[Dict]:
        """获取Session-Scoped上下文"""
        return self._qwen_contexts.get(session_key, [])

    def save_session_context(self, session_key: str, context: List[Dict]):
        """保存Session-Scoped上下文"""
        self._qwen_contexts[session_key] = context

    def get_tool_stats(self) -> Dict[str, Any]:
        """获取工具调用统计"""
        total = len(self._tool_history)
        if total == 0:
            return {"total_calls": 0}

        successes = sum(1 for r in self._tool_history if r.get("success"))
        avg_time = sum(r.get("time_ms", 0) for r in self._tool_history) / total

        return {
            "total_calls": total,
            "success_rate": successes / total,
            "avg_time_ms": avg_time,
            "registered_tools": len(self.tools),
        }