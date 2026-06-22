import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, AsyncGenerator, AsyncIterator, Callable, Optional, TYPE_CHECKING

from cogu.api.client import DeepSeekClient, LLMResponse, StreamEvent, StreamEventType
from cogu.config.settings import AgentConfig, Settings
from cogu.core.rails import (
    AgentCallbackContext,
    AgentCallbackEvent,
    RailRegistry,
    rail,
)
from cogu.core.session import Session, SessionState, StreamFrame
from cogu.core.streaming_executor import (
    ExecutionMode,
    PendingToolCall,
    StreamingToolExecutor,
    ToolExecutionEvent,
)
from cogu.core.tool_guard import (
    GuardSeverity,
    ThreatCategory,
    ToolGuardEngine,
    ToolGuardResult,
)
from cogu.memory.compression_pipeline import CompressionPipeline, CompressionLevel
from cogu.memory.context_offloader import ContextOffloader
from cogu.tools.base import ToolRegistry, ToolResult

if TYPE_CHECKING:
    from cogu.core.two_level_planner import TwoLevelPlanner, PlanMode, WorkIntent, WorkPlan, DAGExecutor
    from cogu.core.api_config import MultiProviderClient, Provider
    from cogu.core.skills_system import BuiltinSkillRegistry
    from cogu.memory.enhanced_memory import EnhancedSuperMemory, RecallResult


class TurnStatus(Enum):
    THINKING = "thinking"
    ACTING = "acting"
    OBSERVING = "observing"
    FINISHED = "finished"
    ERROR = "error"


class AgentState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    FINISHED = "finished"
    ERROR = "error"


class AgentMode(str, Enum):
    DEFAULT = "default"
    MISSION = "mission"
    CODING = "coding"


@dataclass
class TurnResult:
    status: TurnStatus
    content: str = ""
    thinking: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    iteration: int = 0
    elapsed_ms: float = 0.0


@dataclass
class AgentTurn:
    iteration: int
    messages: list[dict]
    tools: list[dict]
    started_at: float = field(default_factory=time.time)


@dataclass
class TurnEvent:
    type: str
    content: str = ""
    thinking: str = ""
    tool_name: str = ""
    tool_args: dict = field(default_factory=dict)
    tool_result: str = ""
    tool_id: str = ""
    usage: dict = field(default_factory=dict)
    iteration: int = 0
    metadata: dict = field(default_factory=dict)

    @property
    def has_tool_calls(self) -> bool:
        return self.type == "tool_calls_complete"

    @property
    def is_final(self) -> bool:
        return self.type in ("finish", "error", "max_iterations")


@dataclass
class InputValidationResult:
    """输入验证结果 — 借鉴 OfficeAce/MiClaw 安全输入处理模式."""
    is_valid: bool = True
    sanitized: str = ""
    error_message: str = ""
    warning: str = ""


_SOUL_PATH = Path(__file__).parent / "soul.md"
_SOUL_CONTENT = ""
if _SOUL_PATH.exists():
    _SOUL_CONTENT = _SOUL_PATH.read_text(encoding="utf-8")

_DEFAULT_SYSTEM_PROMPT = f"""You are COGU Loong, a cognitive unified agent. You have access to tools and can use them to accomplish tasks.
Think step by step. When you need information, use tools. When you have an answer, respond directly.
Be concise and precise. Use Chinese when the user communicates in Chinese.

{_SOUL_CONTENT}""" if _SOUL_CONTENT else """You are COGU, a cognitive unified agent. You have access to tools and can use them to accomplish tasks.
Think step by step. When you need information, use tools. When you have an answer, respond directly.
Be concise and precise. Use Chinese when the user communicates in Chinese."""


class ReActAgent:
    def __init__(
        self,
        settings: "AgentConfig | Settings" = None,
        client: "DeepSeekClient" = None,
        tool_registry: "ToolRegistry" = None,
        session: "Session" = None,
        rail_registry: "RailRegistry" = None,
        memory: "EnhancedSuperMemory" = None,
        planner: "TwoLevelPlanner" = None,
        skill_registry: "BuiltinSkillRegistry" = None,
        multi_provider_client: "MultiProviderClient" = None,
    ):
        from cogu.config.settings import AgentConfig, Settings as S

        if settings is None:
            settings = AgentConfig()
        if isinstance(settings, S):
            self._settings = settings
            self._agent_config = settings.agent
        elif isinstance(settings, AgentConfig):
            self._agent_config = settings
            self._settings = None
        else:
            self._agent_config = AgentConfig()
            self._settings = None

        self._client = client
        self._tool_registry = tool_registry or ToolRegistry()
        self._session = session
        self._rail_registry = rail_registry or RailRegistry()

        self._tool_executor = StreamingToolExecutor(self._tool_registry)
        self._tool_guard = ToolGuardEngine()
        self._compression = CompressionPipeline()
        self._offloader: Optional[ContextOffloader] = None

        self._memory: Optional[EnhancedSuperMemory] = memory
        self._planner: Optional[TwoLevelPlanner] = planner
        self._skill_registry: Optional[BuiltinSkillRegistry] = skill_registry
        self._multi_provider: Optional[MultiProviderClient] = multi_provider_client

        self._cached_memory_context: str = ""
        self._active_plan: Optional[WorkPlan] = None
        self._dag_executor: Optional[DAGExecutor] = None

        workspace = ""
        if self._settings:
            workspace = self._settings.workspace
        if workspace:
            self._offloader = ContextOffloader(
                offload_dir=str(Path(workspace) / ".cogu" / "offload"),
            )
            if self._memory:
                import os
                mem_ws = os.path.join(workspace, ".cogu", "memory")
                mem_file_root = os.path.join(workspace, ".cogu", "memory_files")
                os.makedirs(mem_ws, exist_ok=True)
                os.makedirs(mem_file_root, exist_ok=True)

        self._turn_counter = 0
        self._mode: AgentMode = AgentMode.DEFAULT
        self._mission_prd: Optional[str] = None
        self._mission_phase = "planning"

        # Agent state machine (OpenManus pattern)
        self._state: AgentState = AgentState.IDLE
        self._duplicate_threshold: int = 2
        self._message_history: list[str] = []

        # Logger
        self._logger = logging.getLogger(__name__)
        
        # Progress callback (for UI feedback)
        self._progress_callback: Optional[Callable[[str], None]] = None

        # MultiStep mode (EvoMaster pattern)
        self._trajectory: list[dict[str, Any]] = []
        self._step_history: list[TurnResult] = []

        if self._skill_registry:
            self._register_skills_as_tools()

    def _get_system_prompt(self) -> str:
        if self._agent_config.system_prompt:
            return self._agent_config.system_prompt
        return _DEFAULT_SYSTEM_PROMPT

    def _get_client(self) -> DeepSeekClient:
        if self._client:
            return self._client
        if self._multi_provider:
            return self._multi_provider
        raise RuntimeError("No LLM client configured. Set client or multi_provider_client in constructor.")

    def _validate_input(self, user_message: str, max_length: int = 50000) -> InputValidationResult:
        """验证并清理用户输入 — 借鉴 OfficeAce 安全输入处理 & MiClaw 防护模式.
        
        执行多层验证：
        1. 类型检查 — 确保输入为字符串
        2. 空值/纯空白检查
        3. 控制字符清理（保留换行符和制表符）
        4. 长度限制检查
        5. 潜在注入检测（警告级别，不阻止）
        
        借鉴 OfficeAce 模式：sanitize-first, then validate, warn on suspicious patterns.
        借鉴 MiClaw 模式：rail-based validation with progressive severity.
        
        Args:
            user_message: 原始用户输入
            max_length: 最大允许字符数
            
        Returns:
            InputValidationResult 包含验证状态、清理后的消息和警告信息
        """
        import re
        
        # 1. 类型检查
        if not isinstance(user_message, str):
            return InputValidationResult(
                is_valid=False,
                error_message="❌ 输入类型无效，请输入文本。",
            )
        
        # 2. 空值检查
        if not user_message or not user_message.strip():
            return InputValidationResult(
                is_valid=False,
                error_message="❌ 请输入有效的问题或指令。",
            )
        
        # 3. 清理 null 字节和危险控制字符
        sanitized = user_message.replace('\x00', '')
        # 移除 ASCII 控制字符（保留 \n \t）
        sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', sanitized)
        
        # 4. 清理后再次检查空值
        if not sanitized.strip():
            return InputValidationResult(
                is_valid=False,
                error_message="❌ 输入仅包含无效字符，请输入有效文本。",
            )
        
        # 5. 长度检查
        if len(sanitized) > max_length:
            return InputValidationResult(
                is_valid=False,
                error_message=(
                    f"❌ 输入过长（{len(sanitized)} 字符，最大 {max_length} 字符），"
                    f"请简化你的问题。"
                ),
            )
        
        # 6. 潜在注入检测（借鉴 OfficeAce factcheck 安全模式 — 仅警告，不阻止）
        warning = ""
        injection_patterns = [
            (r'\[system\]\(#.*?\)', '检测到可能的系统指令注入标记'),
            (r'<\|im_start\|>', '检测到可能的角色切换标记'),
            (r'\[INST\].*?\[/INST\]', '检测到可能的指令包装'),
            (r'ignore\s+(all\s+)?(previous|prior|above)\s+instructions?', '检测到可能的指令覆盖尝试'),
            (r'<\|endoftext\|>', '检测到可能的结束标记注入'),
            (r'\[DONE\]', '检测到可能的流结束标记'),
        ]
        for pattern, desc in injection_patterns:
            if re.search(pattern, sanitized, re.IGNORECASE):
                warning = f"⚠️ {desc}（已标记，继续处理）"
                self._logger.warning(f"input_validation.injection_detected: {desc}")
                break
        
        return InputValidationResult(
            is_valid=True,
            sanitized=sanitized.strip(),
            warning=warning,
        )

    def _is_retryable_error(self, error: Exception) -> bool:
        """判断错误是否可重试 — 借鉴 MiClaw retry classifier 模式.
        
        Args:
            error: 异常对象
            
        Returns:
            True 如果应该重试
        """
        error_text = type(error).__name__.lower() + " " + str(error).lower()
        retryable_keywords = ["connection", "timeout", "rate", "429", "502", "503", "504", "server error"]
        return any(keyword in error_text for keyword in retryable_keywords)

    async def _retry_llm_call(
        self,
        call_name: str,
        call_fn,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """通用 LLM 调用重试包装器 — 借鉴 OfficeAce 韧性调用模式.
        
        对可重试错误（网络、超时、限流）使用指数退避重试。
        不可重试错误（认证、参数错误）立即失败。
        
        Args:
            call_name: 调用名称（用于日志）
            call_fn: 异步无参数函数，返回 LLM 调用结果
            max_retries: 最大重试次数
            retry_delay: 初始退避延迟（秒）
            
        Returns:
            LLM 调用结果，如果所有重试都失败则返回 None
            
        Raises:
            不可重试的错误会直接抛出
        """
        last_error = None
        for attempt in range(max_retries):
            try:
                result = await call_fn()
                if attempt > 0:
                    self._logger.info(f"{call_name}: succeeded after {attempt + 1} attempts")
                return result
            except Exception as e:
                last_error = e
                if not self._is_retryable_error(e):
                    # 不可重试错误直接抛出
                    raise
                
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    self._logger.warning(
                        f"{call_name}: attempt {attempt + 1}/{max_retries} failed, "
                        f"retrying in {wait_time:.1f}s: {e}"
                    )
                    if self._progress_callback:
                        self._notify_progress(
                            f"网络异常，{wait_time:.0f}秒后重试 ({attempt + 1}/{max_retries})..."
                        )
                    await asyncio.sleep(wait_time)
                    continue
        
        # 所有重试用尽
        self._logger.error(f"{call_name}: all {max_retries} attempts failed: {last_error}")
        raise last_error

    def _format_user_friendly_error(self, e: Exception) -> str:
        """将技术错误转换为用户友好提示.
        
        Args:
            e: 原始异常
            
        Returns:
            用户友好的错误提示
        """
        error_type = type(e).__name__
        error_msg = str(e)
        
        # LLM API 相关错误
        if "APIConnectionError" in error_type or "Connection" in error_type:
            return (
                "❌ 无法连接到 AI 服务\n\n"
                "可能原因：\n"
                "• 网络连接不稳定\n"
                "• API 服务器暂时不可用\n"
                "• 防火墙阻止了连接\n\n"
                "建议：\n"
                "• 检查网络连接\n"
                "• 稍后重试\n"
                "• 运行 `cogu config list` 检查配置"
            )
        
        if "AuthenticationError" in error_type or "401" in error_msg:
            return (
                "❌ API 密钥无效或已过期\n\n"
                "建议：\n"
                "• 运行 `cogu config set deepseek <YOUR-KEY>` 重新配置\n"
                "• 检查 API Key 是否正确（应以 sk- 开头）\n"
                "• 前往 https://platform.deepseek.com/ 查看密钥状态"
            )
        
        if "RateLimitError" in error_type or "429" in error_msg:
            return (
                "⏳ AI 服务繁忙，已达到速率限制\n\n"
                "建议：\n"
                "• 等待 1-2 分钟后重试\n"
                "• 检查是否超出配额\n"
                "• 考虑升级 API 套餐"
            )
        
        if "TimeoutError" in error_type or "timeout" in error_msg.lower():
            return (
                "⏰ 请求超时\n\n"
                "可能原因：\n"
                "• 网络速度慢\n"
                "• AI 服务响应慢\n"
                "• 请求过于复杂\n\n"
                "建议：\n"
                "• 稍后重试\n"
                "• 简化你的问题\n"
                "• 检查网络速度"
            )
        
        if "InvalidRequestError" in error_type or "400" in error_msg:
            return (
                "❌ 请求格式错误\n\n"
                "可能原因：\n"
                "• 输入内容过长\n"
                "• 包含不支持的内容\n\n"
                "建议：\n"
                "• 简化你的问题\n"
                "• 缩短输入内容\n"
                "• 移除特殊字符"
            )
        
        # 通用错误
        return (
            f"❌ 处理请求时出现错误\n\n"
            f"错误类型：{error_type}\n"
            f"错误信息：{error_msg[:200]}\n\n"
            "建议：\n"
            "• 稍后重试\n"
            "• 检查输入内容\n"
            "• 查看日志获取详细信息\n"
            "• 如问题持续，请提交 Issue"
        )

    def _format_tool_error(self, tool_name: str, e: Exception) -> str:
        """将工具执行错误转换为用户友好提示.
        
        Args:
            tool_name: 工具名称
            e: 原始异常
            
        Returns:
            用户友好的错误提示
        """
        error_type = type(e).__name__
        error_msg = str(e)
        
        if "FileNotFoundError" in error_type:
            return f"❌ 工具 '{tool_name}' 失败：找不到文件。请检查文件路径是否正确。"
        
        if "PermissionError" in error_type:
            return f"❌ 工具 '{tool_name}' 失败：权限不足。请检查文件权限或使用管理员权限运行。"
        
        if "TimeoutError" in error_type or "timeout" in error_msg.lower():
            return f"❌ 工具 '{tool_name}' 失败：执行超时。请稍后重试或检查工具配置。"
        
        if "ValueError" in error_type:
            return f"❌ 工具 '{tool_name}' 失败：输入参数错误。请检查输入格式是否正确。"
        
        # 通用工具错误
        return f"❌ 工具 '{tool_name}' 执行失败：{error_msg[:100]}"

    def set_progress_callback(self, callback: Optional[Callable[[str], None]]) -> None:
        """设置进度回调函数.
        
        Args:
            callback: 进度回调函数，接收一个字符串参数（进度消息）
        """
        self._progress_callback = callback

    def _notify_progress(self, message: str) -> None:
        """发送进度通知.
        
        Args:
            message: 进度消息
        """
        if self._progress_callback:
            self._progress_callback(message)

    async def startup(self) -> None:
        """启动 Agent，初始化资源.
        
        此方法应在使用 Agent 前调用，用于初始化资源（如连接池、线程池等）。
        """
        self._logger.info("agent.startup.started")
        
        # 初始化工具执行器（如果需要）
        if hasattr(self._tool_executor, 'startup'):
            await self._tool_executor.startup()
        
        # 初始化记忆系统（如果需要）
        if self._memory and hasattr(self._memory, 'startup'):
            await self._memory.startup()
        
        self._state = AgentState.IDLE
        self._logger.info("agent.startup.completed")

    async def shutdown(self) -> None:
        """关闭 Agent，清理资源.
        
        此方法应在不使用 Agent 时调用，用于清理资源（如关闭连接、释放内存等）。
        """
        self._logger.info("agent.shutdown.started")
        
        # 清理工具执行器
        if hasattr(self._tool_executor, 'shutdown'):
            await self._tool_executor.shutdown()
        
        # 清理记忆系统
        if self._memory and hasattr(self._memory, 'close'):
            await self._memory.close()
        
        # 清理压缩管道
        if hasattr(self._compression, 'close'):
            await self._compression.close()
        
        # 清理 offloader
        if self._offloader and hasattr(self._offloader, 'close'):
            await self._offloader.close()
        
        self._state = AgentState.IDLE
        self._logger.info("agent.shutdown.completed")

    def __del__(self):
        """析构函数 - 兜底清理资源.
        
        注意：此方法不保证被调用（依赖垃圾回收），应优先使用 startup()/shutdown() 或上下文管理器。
        """
        try:
            if hasattr(self, '_logger'):
                self._logger.warning("agent.__del__ called - please use shutdown() explicitly")
        except Exception:
            pass

    async def __aenter__(self):
        """异步上下文管理器入口."""
        await self.startup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口."""
        await self.shutdown()

    def _register_skills_as_tools(self):
        if not self._skill_registry:
            return
        for skill in self._skill_registry.list_all():
            manifest = skill.manifest
            self._tool_registry.register_function(
                name=manifest.name,
                description=manifest.description,
                func=lambda _s=skill, **kwargs: asyncio.run(_s.execute(**kwargs)),
                tags=[manifest.category.value] + manifest.tags,
            )

    def is_stuck(self) -> bool:
        """Detect if agent is stuck (OpenManus pattern).

        Checks if the last N assistant messages are duplicates.
        """
        if len(self._message_history) < self._duplicate_threshold:
            return False
        recent = self._message_history[-self._duplicate_threshold:]
        return len(set(recent)) == 1 and recent[0] != ""

    def _get_stuck_prompt(self) -> str:
        """Generate a strategy-change prompt when stuck (OpenManus pattern)."""
        return (
            "I notice I've been repeating myself. Let me try a completely different approach. "
            "I'll break this problem into smaller steps and try alternative strategies."
        )

    def _track_message(self, content: str) -> None:
        """Track assistant messages for stuck detection."""
        self._message_history.append(content[:200])
        if len(self._message_history) > 20:
            self._message_history = self._message_history[-20:]

    async def _inject_memory_context(self, query: str) -> str:
        if not self._memory:
            return ""
        try:
            results = await self._memory.recall(
                query=query,
                strategy=self._memory.RecallStrategy.HYBRID if hasattr(self._memory, 'RecallStrategy') else "hybrid",
                limit=5,
            )
            if not results:
                return ""
            parts = ["[Relevant Memory Context]"]
            for r in results[:5]:
                parts.append(f"- [{r.source}/{r.level.value if hasattr(r.level, 'value') else r.level}] (score={r.score:.2f}) {r.content[:300]}")
            self._cached_memory_context = "\n".join(parts)
            return self._cached_memory_context
        except Exception as e:
            self._logger.warning(f"Memory recall failed: {e}")
            return ""

    async def _apply_context_compression(self):
        if not self._session:
            return
        token_estimate = self._session.estimate_tokens()
        if token_estimate > self._agent_config.context_max_tokens * 0.85:
            content = json.dumps(self._session.conversation, ensure_ascii=False)
            result = await self._compression.auto_compress(
                content,
                token_budget=self._agent_config.context_max_tokens,
                context={"messages": self._session.conversation},
            )
            if result.compressed_tokens < token_estimate:
                self._session.compress(result.content)

    async def _remember_tool_result(self, tool_name: str, result_content: str):
        if not self._memory:
            return
        try:
            await self._memory.remember(
                content=f"[{tool_name}]: {result_content[:500]}",
                role="tool",
                metadata={"tool": tool_name},
            )
        except Exception as e:
            self._logger.warning(f"Memory remember failed for tool '{tool_name}': {e}")

    def _build_enriched_system_prompt(self) -> str:
        prompt = self._get_system_prompt()
        if self._cached_memory_context:
            prompt += "\n\n" + self._cached_memory_context
        if self._active_plan:
            plan_summary = self._active_plan.stats()
            prompt += f"\n\n[Active Work Plan: {plan_summary['plan_id']}] {plan_summary['total_tasks']} tasks, mode={plan_summary['mode']}"
        return prompt

    def _format_tools(self, mode: AgentMode = None) -> list[dict]:
        mode = mode or self._mode
        if mode == AgentMode.MISSION and self._mission_phase == "planning":
            return self._tool_registry.to_openai_tools(group="planning")
        if mode == AgentMode.CODING:
            coding_tools = self._tool_registry.to_openai_tools(group="coding")
            if coding_tools:
                return coding_tools
        return self._tool_registry.to_openai_tools()

    async def _run_pre_hooks(self, inputs: dict) -> AgentCallbackContext:
        ctx = AgentCallbackContext(
            agent=self,
            session=self._session,
            event=AgentCallbackEvent.BEFORE_INVOKE,
            data={"inputs": inputs},
        )
        await self._rail_registry.trigger(ctx)
        if self._session:
            await self._session.pre_run(inputs)
        return ctx

    async def _run_post_hooks(self, result: TurnResult) -> AgentCallbackContext:
        ctx = AgentCallbackContext(
            agent=self,
            session=self._session,
            event=AgentCallbackEvent.AFTER_INVOKE,
            data={"result": result},
        )
        await self._rail_registry.trigger(ctx)
        if self._session:
            await self._session.post_run()
        return ctx

    async def _check_tool_guard(self, tool_name: str, tool_args: dict) -> ToolGuardResult:
        result = await self._tool_guard.check(tool_name, tool_args)
        if not result.allowed and result.severity == GuardSeverity.CRITICAL:
            return result
        if result.approval_required:
            approval_id = result.findings[-1].split(": ")[-1] if result.findings else ""
            if approval_id:
                approved = await self._tool_guard._approval_handler.request_approval(
                    approval_id, tool_name, tool_args,
                )
                return approved
            return ToolGuardResult(
                allowed=False,
                severity=GuardSeverity.HIGH,
                rejected_reason="approval required but no handler available",
            )
        return result

    async def _execute_tool_with_guard(
        self, tool_id: str, tool_name: str, tool_args: dict
    ) -> ToolResult:
        guard = await self._check_tool_guard(tool_name, tool_args)
        if not guard.allowed:
            return ToolResult.err(guard.rejected_reason or f"Tool '{tool_name}' blocked by guard")

        if guard.warning:
            self._logger.debug(f"Tool '{tool_name}' guard warning: {guard.warning}")

        ctx = AgentCallbackContext(
            agent=self,
            session=self._session,
            event=AgentCallbackEvent.BEFORE_TOOL_CALL,
            data={"tool_name": tool_name, "tool_args": tool_args, "tool_id": tool_id},
        )
        await self._rail_registry.trigger(ctx)
        if ctx.data.get("blocked"):
            return ToolResult.err(ctx.data.get("block_reason", "Blocked by rail"))

        try:
            result = await self._tool_registry.execute(tool_name, tool_args)
        except Exception as e:
            # ✅ 记录详细错误日志（不暴露给用户）
            self._logger.error(f"Tool '{tool_name}' execution failed: {e}", exc_info=True)
            
            # ✅ 返回用户友好的错误提示
            friendly_error = self._format_tool_error(tool_name, e)
            result = ToolResult.err(friendly_error)
            
            ctx_err = AgentCallbackContext(
                agent=self,
                session=self._session,
                event=AgentCallbackEvent.ON_TOOL_EXCEPTION,
                data={"tool_name": tool_name, "error": e, "friendly_error": friendly_error},
            )
            await self._rail_registry.trigger(ctx_err)

        after_ctx = AgentCallbackContext(
            agent=self,
            session=self._session,
            event=AgentCallbackEvent.AFTER_TOOL_CALL,
            data={"tool_name": tool_name, "result": result, "tool_id": tool_id},
        )
        await self._rail_registry.trigger(after_ctx)

        return result

    async def _maybe_compress_context(self):
        if not self._session:
            return
        token_estimate = self._session.estimate_tokens()
        compress_threshold = int(self._agent_config.context_max_tokens * 0.85)
        if token_estimate > compress_threshold:
            content = json.dumps(self._session.conversation, ensure_ascii=False)
            result = await self._compression.auto_compress(
                content,
                token_budget=self._agent_config.context_max_tokens,
                context={"messages": self._session.conversation},
            )

    async def _maybe_offload(self, content: str, tool_name: str):
        if not self._offloader:
            return
        if len(content) > 2000:
            self._offloader.offload(
                content=content,
                tool_name=tool_name,
                token_count=len(content) // 3,
            )

    async def invoke(self, user_message: str) -> TurnResult:
        started = time.time()
        
        # ✅ 增强输入验证（OfficeAce/MiClaw 多层安全验证模式）
        validation = self._validate_input(user_message)
        if not validation.is_valid:
            return TurnResult(
                status=TurnStatus.ERROR,
                content=validation.error_message,
            )
        user_message = validation.sanitized
        if validation.warning:
            self._logger.warning(f"invoke.input_suspicious: {validation.warning}")
        
        # ✅ 日志记录：开始处理
        self._logger.info(
            "agent.invoke.started",
            user_message_length=len(user_message),
            max_iterations=self._agent_config.max_iterations,
        )
        
        # ✅ 通知：开始处理
        self._notify_progress("正在思考...")
        
        ctx = AgentCallbackContext(
            agent=self,
            session=self._session,
            event=AgentCallbackEvent.BEFORE_INVOKE,
            data={"user_message": user_message},
        )
        await self._rail_registry.trigger(ctx)
        if self._session:
            await self._session.pre_run({"message": user_message})
            self._session.add_message("user", user_message)

        full_content = ""
        full_thinking = ""
        all_tool_calls: list[dict] = []
        all_tool_results: list[ToolResult] = []
        usage = {}
        final_status = TurnStatus.FINISHED

        for iteration in range(1, self._agent_config.max_iterations + 1):
            self._turn_counter = iteration

            # ✅ 通知：当前轮次
            if iteration == 1:
                self._notify_progress("正在调用 AI 模型...")
            else:
                self._notify_progress(f"第 {iteration} 轮思考中...")

            tools = self._format_tools()
            
            # ✅ 日志记录：开始第 N 轮
            self._logger.debug(
                "agent.invoke.iteration_start",
                iteration=iteration,
                tools_count=len(tools) if tools else 0,
            )
            
            # ✅ 重试机制（最多 3 次，指数退避）
            max_retries = 3
            retry_delay = 1.0
            response = None
            
            for retry_attempt in range(max_retries):
                try:
                    response: LLMResponse = await self._get_client().chat(
                        messages=self._session.conversation if self._session else [
                            {"role": "system", "content": self._get_system_prompt()},
                            {"role": "user", "content": user_message},
                        ],
                        system=self._get_system_prompt() if not self._session else "",
                        tools=tools or None,
                        temperature=self._agent_config.temperature,
                        top_p=self._agent_config.top_p,
                    )
                    break  # 成功则跳出重试循环
                except Exception as e:
                    error_type = type(e).__name__
                    # 只对可重试错误进行重试（网络、超时、速率限制）
                    is_retryable = any(keyword in error_type.lower() + str(e).lower() 
                                      for keyword in ["connection", "timeout", "rate", "429", "502", "503", "504"])
                    
                    if is_retryable and retry_attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** retry_attempt)
                        self._logger.warning(
                            f"LLM call failed (attempt {retry_attempt + 1}/{max_retries}), "
                            f"retrying in {wait_time}s: {e}"
                        )
                        self._notify_progress(f"网络异常，{wait_time:.0f}秒后重试 ({retry_attempt + 1}/{max_retries})...")
                        await asyncio.sleep(wait_time)
                        continue
                    
                    # 不可重试或重试次数用尽
                    self._logger.error(f"Agent invocation failed: {e}", exc_info=True)
                    final_status = TurnStatus.ERROR
                    full_content = self._format_user_friendly_error(e)
                    break
            
            if response is None:
                break

            full_thinking = response.thinking
            if response.content:
                full_content += response.content
            usage = response.usage

            # ✅ 日志记录：LLM 响应
            self._logger.debug(
                "agent.invoke.llm_response",
                iteration=iteration,
                has_content=bool(response.content),
                has_tool_calls=bool(response.tool_calls),
                tool_calls_count=len(response.tool_calls) if response.tool_calls else 0,
                usage=usage,
            )

            if not response.tool_calls:
                if self._session:
                    self._session.add_message("assistant", response.content)
                
                # ✅ 通知：完成
                elapsed = (time.time() - started) * 1000
                self._notify_progress(f"完成！用时 {elapsed/1000:.1f} 秒")
                
                # ✅ 日志记录：完成
                self._logger.info(
                    "agent.invoke.completed",
                    iteration=iteration,
                    elapsed_ms=elapsed,
                    content_length=len(full_content),
                )
                break

            # ✅ 通知：正在执行工具
            self._notify_progress(f"正在执行 {len(response.tool_calls)} 个工具...")
            
            all_tool_calls.extend(response.tool_calls)
            tool_result_texts = []
            for tc in response.tool_calls:
                # ✅ 通知：具体工具名称
                self._notify_progress(f"正在执行工具: {tc['name']}...")
                
                try:
                    args = json.loads(tc["arguments"])
                except (json.JSONDecodeError, TypeError):
                    args = {}
                
                # ✅ 日志记录：工具执行开始
                self._logger.debug(
                    "agent.invoke.tool_start",
                    iteration=iteration,
                    tool_name=tc['name'],
                    tool_id=tc.get('id', ''),
                )
                
                result = await self._execute_tool_with_guard(
                    tc.get("id", ""), tc["name"], args,
                )
                all_tool_results.append(result)
                tool_result_texts.append(f"[{tc['name']}]: {result.content or result.error}")
                
                # ✅ 日志记录：工具执行完成
                self._logger.debug(
                    "agent.invoke.tool_completed",
                    iteration=iteration,
                    tool_name=tc['name'],
                    success=result.success,
                    error=result.error if not result.success else None,
                )

            if self._session:
                assistant_msg = {"role": "assistant", "content": response.content or ""}
                if response.tool_calls:
                    assistant_msg["tool_calls"] = [
                        {
                            "id": tc.get("id", ""),
                            "type": "function",
                            "function": {"name": tc["name"], "arguments": tc["arguments"]},
                        }
                        for tc in response.tool_calls
                    ]
                self._session.add_message("assistant", assistant_msg.get("content", ""))
                for i, tc in enumerate(response.tool_calls):
                    tr = all_tool_results[i] if i < len(all_tool_results) else ToolResult.err("missing")
                    self._session.add_tool_result(
                        tc.get("id", ""),
                        tc["name"],
                        tr.content or tr.error or "",
                    )

        elapsed = (time.time() - started) * 1000

        result = TurnResult(
            status=final_status,
            content=full_content,
            thinking=full_thinking,
            tool_calls=all_tool_calls,
            tool_results=all_tool_results,
            usage=usage,
            iteration=self._turn_counter,
            elapsed_ms=elapsed,
        )

        await self._run_post_hooks(result)
        return result

    async def stream(self, user_message: str) -> AsyncIterator[StreamFrame]:
        # ✅ 增强输入验证（OfficeAce/MiClaw 多层安全验证模式）
        validation = self._validate_input(user_message)
        if not validation.is_valid:
            yield StreamFrame(type="error", content=validation.error_message)
            return
        user_message = validation.sanitized
        if validation.warning:
            self._logger.warning(f"stream.input_suspicious: {validation.warning}")
        
        if self._session:
            await self._session.pre_run({"message": user_message})
            self._session.add_message("user", user_message)

        yield StreamFrame(type="thinking", content="Analyzing...")
        yield StreamFrame(type="text_delta", content="")

        for iteration in range(1, self._agent_config.max_iterations + 1):
            self._turn_counter = iteration

            tools = self._format_tools()
            messages = self._session.conversation if self._session else [
                {"role": "system", "content": self._get_system_prompt()},
                {"role": "user", "content": user_message},
            ]

            full_text = ""
            has_tools = False
            async for event in self._get_client().chat_stream(
                messages=messages,
                system=self._get_system_prompt() if not self._session else "",
                tools=tools or None,
                temperature=self._agent_config.temperature,
                top_p=self._agent_config.top_p,
            ):
                if event.type == StreamEventType.TEXT_DELTA:
                    full_text += event.content
                    yield StreamFrame(type="text_delta", content=event.content)
                elif event.type == StreamEventType.THINKING_DELTA:
                    yield StreamFrame(type="thinking", content=event.content)
                elif event.type == StreamEventType.TOOL_CALL_START:
                    has_tools = True
                    yield StreamFrame(type="tool_start", tool_name=event.tool_name)
                elif event.type == StreamEventType.TOOL_CALL_ARGS:
                    try:
                        args = json.loads(event.content) if event.content else {}
                    except json.JSONDecodeError:
                        args = {}
                    yield StreamFrame(type="tool_args", content=event.content)
                elif event.type == StreamEventType.USAGE:
                    yield StreamFrame(type="usage", metadata=event.usage)

            if not has_tools:
                if self._session:
                    self._session.add_message("assistant", full_text)
                break

        yield StreamFrame(type="end_frame", content="completed")

        if self._session:
            await self._session.post_run()

    async def query(
        self,
        user_message: str,
        mode: AgentMode = AgentMode.DEFAULT,
        reasoning_mode: str = "react",
        use_planner: bool = False,
        use_memory_rag: bool = True,
    ) -> AsyncGenerator[TurnEvent, None]:
        # ✅ 增强输入验证（OfficeAce/MiClaw 多层安全验证模式）
        validation = self._validate_input(user_message)
        if not validation.is_valid:
            yield TurnEvent(type="error", content=validation.error_message)
            return
        user_message = validation.sanitized
        if validation.warning:
            self._logger.warning(f"query.input_suspicious: {validation.warning}")
        
        started = time.time()

        if use_memory_rag and self._memory:
            memory_ctx = await self._inject_memory_context(user_message)
            if memory_ctx:
                yield TurnEvent(
                    type="memory_rag",
                    content=memory_ctx,
                    metadata={"source": "enhanced_super_memory"},
                )

        if use_planner and self._planner:
            from cogu.core.two_level_planner import WorkIntent
            intent = WorkIntent(
                intent_id=f"intent_{int(started)}",
                description=user_message[:200],
                goal=user_message,
            )
            self._active_plan = await self._planner.plan(intent)
            yield TurnEvent(
                type="plan_ready",
                content=json.dumps(self._active_plan.stats(), ensure_ascii=False),
                metadata={"plan_id": self._active_plan.plan_id},
            )

        await self._run_pre_hooks({"message": user_message})
        if self._session:
            self._session.add_message("user", user_message)

        self._mode = mode
        self._mission_phase = "planning"

        if mode == AgentMode.MISSION:
            async for event in self._query_mission(user_message, started):
                yield event
        else:
            async for event in self._query_default(user_message, started, reasoning_mode):
                yield event

        self._cached_memory_context = ""
        self._active_plan = None

    async def _query_default(
        self, user_message: str, started: float, reasoning_mode: str = "react"
    ) -> AsyncGenerator[TurnEvent, None]:
        max_iters = self._agent_config.max_iterations
        final_content = ""
        final_thinking = ""
        all_tool_calls: list[dict] = []
        all_usage: dict = {}

        for iteration in range(1, max_iters + 1):
            self._turn_counter = iteration

            if iteration > 1:
                await self._apply_context_compression()
                if self._memory:
                    recent_context = ""
                    if self._session:
                        recent_context = " ".join(
                            m.get("content", "")[-200:]
                            for m in self._session.conversation[-3:]
                            if isinstance(m, dict)
                        )
                    await self._inject_memory_context(recent_context or user_message)

            tools = self._format_tools()
            messages = self._session.conversation if self._session else [
                {"role": "system", "content": self._build_enriched_system_prompt()},
                {"role": "user", "content": user_message},
            ]

            if self._session:
                messages = list(self._session.conversation)
                mem_ctx = self._cached_memory_context
                if mem_ctx and iteration == 1:
                    for m in messages:
                        if m.get("role") == "system":
                            m["content"] = m.get("content", "") + "\n\n" + mem_ctx
                            break
                    else:
                        messages.insert(0, {"role": "system", "content": mem_ctx})

            yield TurnEvent(type="turn_start", iteration=iteration)

            current_thinking = ""
            current_text = ""
            tool_call_buffer: dict[int, dict] = {}
            has_tool_calls = False

            async for sse in self._get_client().chat_stream(
                messages=messages,
                system=self._build_enriched_system_prompt() if not self._session else "",
                tools=tools or None,
                temperature=self._agent_config.temperature,
                top_p=self._agent_config.top_p,
            ):
                if sse.type == StreamEventType.THINKING_DELTA:
                    current_thinking += sse.content
                    yield TurnEvent(type="thinking", content=sse.content, iteration=iteration)
                elif sse.type == StreamEventType.TEXT_DELTA:
                    current_text += sse.content
                    yield TurnEvent(type="text_delta", content=sse.content, iteration=iteration)
                elif sse.type == StreamEventType.TOOL_CALL_START:
                    has_tool_calls = True
                    idx = sse.index
                    tool_call_buffer[idx] = {"id": sse.tool_id, "name": sse.tool_name, "arguments": ""}
                    yield TurnEvent(
                        type="tool_call_start",
                        tool_name=sse.tool_name,
                        tool_id=sse.tool_id,
                        iteration=iteration,
                    )
                elif sse.type == StreamEventType.TOOL_CALL_ARGS:
                    idx = sse.index
                    if idx in tool_call_buffer:
                        tool_call_buffer[idx]["arguments"] += sse.content
                elif sse.type == StreamEventType.USAGE:
                    all_usage = sse.usage
                    yield TurnEvent(type="usage", usage=sse.usage, iteration=iteration)
                elif sse.type == StreamEventType.ERROR:
                    yield TurnEvent(type="error", content=sse.error, iteration=iteration)
                    return

            final_thinking = current_thinking
            if current_text:
                final_content += current_text

            # Track message for stuck detection (OpenManus pattern)
            self._track_message(current_text)

            # Check if agent is stuck
            if self.is_stuck():
                stuck_prompt = self._get_stuck_prompt()
                yield TurnEvent(
                    type="stuck_detected",
                    content=stuck_prompt,
                    iteration=iteration,
                    metadata={"threshold": self._duplicate_threshold},
                )
                # Inject strategy change into session
                if self._session:
                    self._session.add_message("system", stuck_prompt)

            if has_tool_calls:
                parsed_calls = []
                for idx, buf in tool_call_buffer.items():
                    tc_dict = {
                        "id": buf["id"],
                        "name": buf["name"],
                        "arguments": buf["arguments"],
                    }
                    all_tool_calls.append(tc_dict)
                    parsed_calls.append(tc_dict)

                    try:
                        args = json.loads(buf["arguments"])
                    except (json.JSONDecodeError, TypeError):
                        args = {}

                    yield TurnEvent(
                        type="tool_call_args",
                        tool_name=buf["name"],
                        tool_id=buf["id"],
                        tool_args=args,
                        iteration=iteration,
                    )

                tool_results: list[ToolResult] = []
                async for tr_event in self._execute_tools_streaming(parsed_calls, iteration):
                    yield tr_event
                    if tr_event.tool_result:
                        tool_results.append(ToolResult.ok(tr_event.tool_result))

                if self._session:
                    assistant_content = current_text if current_text else ""
                    self._session._state.conversation.append({
                        "role": "assistant",
                        "content": assistant_content,
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {"name": tc["name"], "arguments": tc["arguments"]},
                            }
                            for tc in parsed_calls
                        ],
                    })
                    for tc, tr in zip(parsed_calls, tool_results):
                        self._session.add_tool_result(
                            tc["id"],
                            tc["name"],
                            tr.content or tr.error or "",
                        )
            else:
                if self._session:
                    self._session.add_message("assistant", current_text)
                yield TurnEvent(
                    type="finish",
                    content=final_content,
                    thinking=final_thinking,
                    usage=all_usage,
                    iteration=iteration,
                )
                elapsed = (time.time() - started) * 1000
                result = TurnResult(
                    status=TurnStatus.FINISHED,
                    content=final_content,
                    thinking=final_thinking,
                    tool_calls=all_tool_calls,
                    usage=all_usage,
                    iteration=iteration,
                    elapsed_ms=elapsed,
                )
                await self._run_post_hooks(result)
                return

            yield TurnEvent(
                type="turn_end",
                iteration=iteration,
                metadata={"tool_calls_count": len(parsed_calls)},
            )

        elapsed = (time.time() - started) * 1000
        result = TurnResult(
            status=TurnStatus.FINISHED,
            content=final_content,
            thinking=final_thinking,
            tool_calls=all_tool_calls,
            usage=all_usage,
            iteration=max_iters,
            elapsed_ms=elapsed,
        )
        await self._run_post_hooks(result)

    async def _execute_tools_streaming(
        self, tool_calls: list[dict], iteration: int
    ) -> AsyncGenerator[TurnEvent, None]:
        for tc in tool_calls:
            self._tool_executor.enqueue(tc["id"], tc["name"], tc["arguments"])

        events = await self._tool_executor.execute_pending()

        for evt in events:
            if evt.result and evt.result.content:
                content = evt.result.content
            elif evt.result and evt.result.error:
                content = f"Error: {evt.result.error}"
            else:
                content = ""

            await self._maybe_offload(content, evt.tool_name)
            await self._remember_tool_result(evt.tool_name, content)

            yield TurnEvent(
                type="tool_result",
                tool_name=evt.tool_name,
                tool_id=evt.tool_id,
                tool_result=content,
                iteration=iteration,
                metadata={
                    "status": evt.status,
                    "elapsed_ms": evt.elapsed_ms,
                },
            )

        self._tool_executor.clear()

    async def run_task(
        self,
        task_description: str,
        max_steps: int = 10,
        on_step: Optional[Callable] = None,
    ) -> dict[str, Any]:
        """MultiStep task execution (EvoMaster pattern).

        Runs the agent through multiple steps, recording trajectory.
        Returns a dict with: output, trajectory, step_count, success.
        """
        # ✅ 增强输入验证（OfficeAce/MiClaw 多层安全验证模式）
        validation = self._validate_input(task_description)
        if not validation.is_valid:
            return {
                "output": validation.error_message,
                "trajectory": [],
                "step_count": 0,
                "success": False,
                "total_tool_calls": 0,
                "total_elapsed_ms": 0,
                "error": validation.error_message,
            }
        task_description = validation.sanitized
        if validation.warning:
            self._logger.warning(f"run_task.input_suspicious: {validation.warning}")
        
        self._trajectory = []
        self._step_history = []

        for step_num in range(1, max_steps + 1):
            step_start = time.time()

            # Build context from trajectory
            context_parts = [f"Task: {task_description}"]
            if self._trajectory:
                context_parts.append("Previous steps:")
                for t in self._trajectory[-3:]:
                    context_parts.append(f"  Step {t.get('step', '?')}: {t.get('summary', '')[:200]}")

            step_prompt = "\n".join(context_parts)

            # Execute one step via invoke
            result = await self.invoke(step_prompt)

            step_record = {
                "step": step_num,
                "content": result.content[:500] if result.content else "",
                "thinking": result.thinking[:200] if result.thinking else "",
                "tool_calls": [{"name": tc.get("name", ""), "args": tc.get("arguments", "")[:100]} for tc in result.tool_calls],
                "tool_count": len(result.tool_calls),
                "elapsed_ms": result.elapsed_ms,
                "status": result.status.value,
            }
            self._trajectory.append(step_record)
            self._step_history.append(result)

            if on_step:
                try:
                    on_step(step_record)
                except Exception as e:
                    self._logger.warning(f"on_step callback failed: {e}")

            # Check if agent finished (no tool calls = done)
            if not result.tool_calls:
                break

        # Summarize trajectory
        summary = {
            "output": result.content if result else "",
            "trajectory": self._trajectory,
            "step_count": len(self._trajectory),
            "success": result.status == TurnStatus.FINISHED if result else False,
            "total_tool_calls": sum(t.get("tool_count", 0) for t in self._trajectory),
            "total_elapsed_ms": sum(t.get("elapsed_ms", 0) for t in self._trajectory),
        }

        # Record to memory
        if self._memory:
            try:
                await self._memory.remember(
                    content=f"[Task] {task_description[:100]} → {summary['step_count']} steps, {'success' if summary['success'] else 'failed'}",
                    role="system",
                    metadata={"type": "task_trajectory", "task": task_description[:200]},
                )
            except Exception as e:
                self._logger.warning(f"Memory remember (task trajectory) failed: {e}")

        return summary

    async def step(
        self,
        prompt: str,
        tools: Optional[list[dict]] = None,
    ) -> TurnResult:
        """Execute a single step (EvoMaster _step pattern).

        Returns TurnResult with content, tool_calls, tool_results.
        """
        # ✅ 增强输入验证（OfficeAce/MiClaw 多层安全验证模式）
        validation = self._validate_input(prompt)
        if not validation.is_valid:
            return TurnResult(
                status=TurnStatus.ERROR,
                content=validation.error_message,
            )
        prompt = validation.sanitized
        if validation.warning:
            self._logger.warning(f"step.input_suspicious: {validation.warning}")
        
        if tools is None:
            tools = self._format_tools()

        messages = self._session.conversation if self._session else [
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": prompt},
        ]

        full_content = ""
        full_thinking = ""
        all_tool_calls = []
        all_tool_results = []
        usage = {}

        # ✅ 重试机制（最多 3 次，指数退避）— 借鉴 MiClaw resilient agent 模式
        max_retries = 3
        retry_delay = 1.0
        response = None
        
        for retry_attempt in range(max_retries):
            try:
                response: LLMResponse = await self._get_client().chat(
                    messages=messages,
                    system=self._get_system_prompt() if not self._session else "",
                    tools=tools or None,
                    temperature=self._agent_config.temperature,
                    top_p=self._agent_config.top_p,
                )
                break
            except Exception as e:
                error_type = type(e).__name__
                is_retryable = any(keyword in error_type.lower() + str(e).lower() 
                                  for keyword in ["connection", "timeout", "rate", "429", "502", "503", "504"])
                
                if is_retryable and retry_attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** retry_attempt)
                    self._logger.warning(
                        f"LLM step() call failed (attempt {retry_attempt + 1}/{max_retries}), "
                        f"retrying in {wait_time}s: {e}"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                
                self._logger.error(f"Agent step() invocation failed: {e}", exc_info=True)
                return TurnResult(
                    status=TurnStatus.ERROR,
                    content=self._format_user_friendly_error(e),
                )
        
        if response is None:
            return TurnResult(
                status=TurnStatus.ERROR,
                content="❌ LLM 调用失败，已达最大重试次数。请稍后重试。",
            )

        full_thinking = response.thinking or ""
        full_content = response.content or ""
        usage = response.usage

        if response.tool_calls:
            all_tool_calls = response.tool_calls
            for tc in response.tool_calls:
                try:
                    args = json.loads(tc["arguments"])
                except (json.JSONDecodeError, TypeError):
                    args = {}
                result = await self._execute_tool_with_guard(tc.get("id", ""), tc["name"], args)
                all_tool_results.append(result)

        return TurnResult(
            status=TurnStatus.FINISHED if not response.tool_calls else TurnStatus.ACTING,
            content=full_content,
            thinking=full_thinking,
            tool_calls=all_tool_calls,
            tool_results=all_tool_results,
            usage=usage,
            iteration=1,
            elapsed_ms=0,
        )

    def get_trajectory(self) -> list[dict[str, Any]]:
        """Return execution trajectory (EvoMaster pattern)."""
        return list(self._trajectory)

    def get_step_history(self) -> list[TurnResult]:
        """Return step history."""
        return list(self._step_history)

    async def _query_mission(
        self, user_message: str, started: float
    ) -> AsyncGenerator[TurnEvent, None]:
        plan_tools = self._tool_registry.to_openai_tools(group="planning")
        planning_messages = [
            {"role": "system", "content": self._get_system_prompt() + "\n[MISSION PLANNING PHASE] Research and design only. Use read-only tools to explore the problem. Produce a detailed PRD."},
            {"role": "user", "content": user_message},
        ]

        plan_content = ""
        plan_thinking = ""

        for iteration in range(1, self._agent_config.max_iterations + 1):
            self._turn_counter = iteration

            yield TurnEvent(type="turn_start", iteration=iteration)

            tool_call_buffer: dict[int, dict] = {}
            has_tool_calls = False

            async for sse in self._get_client().chat_stream(
                messages=planning_messages,
                tools=plan_tools or None,
                temperature=self._agent_config.temperature,
                top_p=self._agent_config.top_p,
            ):
                if sse.type == StreamEventType.THINKING_DELTA:
                    plan_thinking += sse.content
                    yield TurnEvent(type="thinking", content=sse.content, iteration=iteration)
                elif sse.type == StreamEventType.TEXT_DELTA:
                    plan_content += sse.content
                    yield TurnEvent(type="text_delta", content=sse.content, iteration=iteration)
                elif sse.type == StreamEventType.TOOL_CALL_START:
                    has_tool_calls = True
                    idx = sse.index
                    tool_call_buffer[idx] = {"id": sse.tool_id, "name": sse.tool_name, "arguments": ""}
                    yield TurnEvent(
                        type="tool_call_start",
                        tool_name=sse.tool_name,
                        tool_id=sse.tool_id,
                        iteration=iteration,
                    )
                elif sse.type == StreamEventType.TOOL_CALL_ARGS:
                    idx = sse.index
                    if idx in tool_call_buffer:
                        tool_call_buffer[idx]["arguments"] += sse.content
                elif sse.type == StreamEventType.ERROR:
                    yield TurnEvent(type="error", content=sse.error, iteration=iteration)
                    return

            if has_tool_calls:
                parsed_calls = []
                for idx, buf in tool_call_buffer.items():
                    parsed_calls.append({
                        "id": buf["id"],
                        "name": buf["name"],
                        "arguments": buf["arguments"],
                    })
                async for tr_event in self._execute_tools_streaming(parsed_calls, iteration):
                    yield tr_event
            else:
                break

        self._mission_prd = plan_content
        yield TurnEvent(
            type="mission_prd_ready",
            content=plan_content,
            thinking=plan_thinking,
        )

        self._mission_phase = "execution"
        execution_tools = self._tool_registry.to_openai_tools()

        execution_messages = [
            {"role": "system", "content": self._get_system_prompt() + f"\n[MISSION EXECUTION PHASE] Execute the following PRD:\n\n{plan_content}"},
            {"role": "user", "content": f"Execute the plan above for: {user_message}"},
        ]

        exec_content = ""
        exec_thinking = ""

        for iteration in range(1, self._agent_config.max_iterations + 1):
            self._turn_counter = iteration + self._turn_counter
            actual_iter = self._turn_counter

            yield TurnEvent(type="turn_start", iteration=actual_iter)

            tool_call_buffer: dict[int, dict] = {}
            has_tool_calls = False

            async for sse in self._get_client().chat_stream(
                messages=execution_messages,
                tools=execution_tools or None,
                temperature=self._agent_config.temperature,
                top_p=self._agent_config.top_p,
            ):
                if sse.type == StreamEventType.THINKING_DELTA:
                    exec_thinking += sse.content
                    yield TurnEvent(type="thinking", content=sse.content, iteration=actual_iter)
                elif sse.type == StreamEventType.TEXT_DELTA:
                    exec_content += sse.content
                    yield TurnEvent(type="text_delta", content=sse.content, iteration=actual_iter)
                elif sse.type == StreamEventType.TOOL_CALL_START:
                    has_tool_calls = True
                    idx = sse.index
                    tool_call_buffer[idx] = {"id": sse.tool_id, "name": sse.tool_name, "arguments": ""}
                    yield TurnEvent(
                        type="tool_call_start",
                        tool_name=sse.tool_name,
                        tool_id=sse.tool_id,
                        iteration=actual_iter,
                    )
                elif sse.type == StreamEventType.TOOL_CALL_ARGS:
                    idx = sse.index
                    if idx in tool_call_buffer:
                        tool_call_buffer[idx]["arguments"] += sse.content
                elif sse.type == StreamEventType.ERROR:
                    yield TurnEvent(type="error", content=sse.error, iteration=actual_iter)
                    return

            if has_tool_calls:
                parsed_calls = []
                for idx, buf in tool_call_buffer.items():
                    parsed_calls.append({
                        "id": buf["id"],
                        "name": buf["name"],
                        "arguments": buf["arguments"],
                    })
                async for tr_event in self._execute_tools_streaming(parsed_calls, actual_iter):
                    yield tr_event
            else:
                break

        yield TurnEvent(
            type="mission_complete",
            content=exec_content,
            thinking=exec_thinking,
        )

        elapsed = (time.time() - started) * 1000
        result = TurnResult(
            status=TurnStatus.FINISHED,
            content=exec_content,
            thinking=exec_thinking,
            elapsed_ms=elapsed,
        )
        await self._run_post_hooks(result)

    async def execute_tools_guarded(
        self, tool_calls: list[dict]
    ) -> list[ToolResult]:
        results: list[ToolResult] = []
        for tc in tool_calls:
            try:
                args = json.loads(tc["arguments"]) if isinstance(tc["arguments"], str) else tc["arguments"]
            except (json.JSONDecodeError, TypeError):
                args = {}
            result = await self._execute_tool_with_guard(
                tc.get("id", ""), tc["name"], args,
            )
            results.append(result)
        return results

    @property
    def session(self) -> Optional[Session]:
        return self._session

    @property
    def mode(self) -> AgentMode:
        return self._mode

    @mode.setter
    def mode(self, value: AgentMode):
        self._mode = value

    @property
    def tool_registry(self) -> ToolRegistry:
        return self._tool_registry

    @property
    def tool_guard(self) -> ToolGuardEngine:
        return self._tool_guard

    @property
    def turn_count(self) -> int:
        return self._turn_counter

    def __repr__(self) -> str:
        return f"ReActAgent(mode={self._mode.value}, turns={self._turn_counter}, session={self._session})"
