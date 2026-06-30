"""组件协议管道Agent — 可插拔能力+情节记忆压缩

融合自AutoGPT classic/forge/forge/agent/base.py + protocols.py + components/action_history/
核心架构: 基于组件协议的自主智能体循环
- AgentComponent: 可插拔组件基类, 支持ConfigurableComponent
- ComponentProtocol: CommandProvider/MessageProvider/DirectiveProvider接口
- ComponentAgent: propose_action→用户反馈→execute循环, 组件管道自动发现
- EpisodicHistory: 情节式记忆+LLM压缩摘要
"""
import json
import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, Type, runtime_checkable

logger = logging.getLogger("cogu.core.component_agent")


@runtime_checkable
class CommandProvider(Protocol):
    """命令提供者协议"""
    def get_commands(self) -> List[Dict[str, Any]]:
        ...


@runtime_checkable
class MessageProvider(Protocol):
    """消息提供者协议"""
    def get_messages(self) -> List[Dict[str, Any]]:
        ...


@runtime_checkable
class DirectiveProvider(Protocol):
    """指令提供者协议"""
    def get_directives(self) -> List[str]:
        ...


class AgentComponent:
    """Agent组件基类"""

    def __init__(self, name: str = ""):
        self.name = name or self.__class__.__name__
        self._enabled = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self):
        self._enabled = True

    def disable(self):
        self._enabled = False


class ConfigurableComponent(AgentComponent):
    """可配置组件"""

    def __init__(self, name: str = "", config: Optional[Dict] = None):
        super().__init__(name)
        self.config = config or {}

    def update_config(self, key: str, value: Any):
        self.config[key] = value

    def get_config(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)


class EpisodicHistory:
    """情节式记忆+LLM压缩

    融合AutoGPT ActionHistoryComponent:
    记录每一步的action和observation, 超出限制时用LLM压缩摘要
    """

    def __init__(self, max_entries: int = 50, llm_summarizer: Optional[Callable] = None):
        self.max_entries = max_entries
        self.llm_summarizer = llm_summarizer
        self._entries: deque = deque(maxlen=max_entries)
        self._summary: str = ""

    def add_entry(self, action: str, observation: str, success: bool = True):
        """添加情节记录"""
        entry = {
            "action": action,
            "observation": observation[:500],
            "success": success,
            "timestamp": time.time(),
        }
        self._entries.append(entry)

        if len(self._entries) >= self.max_entries * 0.8:
            self._compact()

    def _compact(self):
        """压缩历史"""
        if self.llm_summarizer:
            history_text = self._render_entries()
            try:
                self._summary = self.llm_summarizer(history_text)
            except Exception as e:
                logger.warning("历史压缩失败: %s", e)
                self._summary = self._auto_summarize()
        else:
            self._summary = self._auto_summarize()

        half = len(self._entries) // 2
        self._entries = deque(list(self._entries)[-half:], maxlen=self.max_entries)

    def _auto_summarize(self) -> str:
        """自动摘要(无LLM时)"""
        entries = list(self._entries)
        if not entries:
            return ""
        actions = [e["action"][:80] for e in entries[-10:]]
        successes = sum(1 for e in entries if e["success"])
        return f"History: {len(entries)} steps, {successes} successes. Recent: {'; '.join(actions)}"

    def _render_entries(self) -> str:
        lines = []
        if self._summary:
            lines.append(f"[Previous Summary] {self._summary}")
        for i, entry in enumerate(self._entries):
            status = "OK" if entry["success"] else "FAIL"
            lines.append(f"Step {i+1} [{status}]: {entry['action']} -> {entry['observation'][:100]}")
        return "\n".join(lines)

    def render(self) -> str:
        return self._render_entries()

    @property
    def size(self) -> int:
        return len(self._entries)

    def clear(self):
        self._entries.clear()
        self._summary = ""


class ComponentAgent:
    """组件协议管道Agent

    融合AutoGPT BaseAgent核心:
    - propose_action→用户反馈→execute循环
    - 组件自动发现与拓扑排序
    - 管道式执行: CommandProvider→MessageProvider→DirectiveProvider
    """

    def __init__(
        self,
        name: str = "ComponentAgent",
        llm_client=None,
        max_iterations: int = 10,
    ):
        self.name = name
        self.llm_client = llm_client
        self.max_iterations = max_iterations

        self._components: Dict[str, AgentComponent] = {}
        self._history = EpisodicHistory()
        self._state: Dict[str, Any] = {}
        self._iteration = 0

    def add_component(self, component: AgentComponent):
        """添加组件"""
        self._components[component.name] = component
        logger.info("组件添加: %s", component.name)

    def remove_component(self, name: str):
        self._components.pop(name, None)

    def get_component(self, name: str) -> Optional[AgentComponent]:
        return self._components.get(name)

    def _collect_commands(self) -> List[Dict[str, Any]]:
        """收集所有CommandProvider的命令"""
        commands = []
        for comp in self._components.values():
            if comp.enabled and isinstance(comp, CommandProvider):
                commands.extend(comp.get_commands())
        return commands

    def _collect_messages(self) -> List[Dict[str, Any]]:
        """收集所有MessageProvider的消息"""
        messages = []
        for comp in self._components.values():
            if comp.enabled and isinstance(comp, MessageProvider):
                messages.extend(comp.get_messages())
        return messages

    def _collect_directives(self) -> List[str]:
        """收集所有DirectiveProvider的指令"""
        directives = []
        for comp in self._components.values():
            if comp.enabled and isinstance(comp, DirectiveProvider):
                directives.extend(comp.get_directives())
        return directives

    def propose_action(self, goal: str) -> Optional[Dict[str, Any]]:
        """提出下一步行动"""
        if not self.llm_client:
            return None

        system_parts = [f"You are {self.name}, an autonomous agent."]
        directives = self._collect_directives()
        if directives:
            system_parts.append("Directives:\n" + "\n".join(f"- {d}" for d in directives))

        commands = self._collect_commands()
        if commands:
            system_parts.append(f"Available commands: {json.dumps(commands[:20], ensure_ascii=False)}")

        user_parts = [f"Goal: {goal}"]
        history = self._history.render()
        if history:
            user_parts.append(f"History:\n{history}")

        try:
            response = self.llm_client([
                {"role": "system", "content": "\n\n".join(system_parts)},
                {"role": "user", "content": "\n\n".join(user_parts)},
            ])
            return {"action": response, "iteration": self._iteration}
        except Exception as e:
            logger.error("propose_action失败: %s", e)
            return None

    def execute(self, action: Dict[str, Any]) -> str:
        """执行行动"""
        action_str = action.get("action", "")
        self._history.add_entry(action_str, f"Executed at iteration {self._iteration}")
        self._iteration += 1
        return f"Executed: {action_str[:100]}"

    def run(self, goal: str, feedback_callback: Optional[Callable] = None) -> List[Dict[str, Any]]:
        """运行Agent循环"""
        results = []

        for i in range(self.max_iterations):
            self._iteration = i + 1
            action = self.propose_action(goal)
            if action is None:
                break

            if feedback_callback:
                approved = feedback_callback(action)
                if not approved:
                    self._history.add_entry(str(action), "User rejected", success=False)
                    continue

            result = self.execute(action)
            results.append({"iteration": i + 1, "action": action, "result": result})

        return results

    @property
    def history(self) -> EpisodicHistory:
        return self._history

    @property
    def component_count(self) -> int:
        return len(self._components)