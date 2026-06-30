"""脑启发三层记忆架构

融合自小红书+人大DeepAgent src/prompts/prompts_deepagent.py
三层记忆模型:
- Episodic Memory: 情景记忆, 存储完整交互片段(对话/工具调用/结果)
- Working Memory: 工作记忆, 当前推理所需的短期上下文(最近N轮)
- Tool Memory: 工具记忆, 工具调用历史和结果缓存(避免重复调用)

配合MemoryFolding实现: 当Working Memory溢出时触发折叠,
将Episodic Memory压缩为摘要, 保留关键进展
"""
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("cogu.memory.brain_memory")

EPISODIC_MAX_ENTRIES = 500
WORKING_MAX_TURNS = 10
TOOL_CACHE_MAX = 200


@dataclass
class EpisodicEntry:
    timestamp: float
    role: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCallRecord:
    tool_name: str
    arguments: Dict[str, Any]
    result: Optional[str] = None
    success: bool = True
    timestamp: float = 0.0
    cache_key: str = ""


class EpisodicMemory:
    """情景记忆 — 存储完整交互片段

    长期存储, 容量大, 可被折叠压缩
    """

    def __init__(self, max_entries: int = EPISODIC_MAX_ENTRIES):
        self.max_entries = max_entries
        self._entries: deque = deque(maxlen=max_entries)

    def add(self, role: str, content: str, metadata: Optional[Dict] = None):
        """添加交互记录"""
        entry = EpisodicEntry(
            timestamp=time.time(),
            role=role,
            content=content,
            metadata=metadata or {},
        )
        self._entries.append(entry)

    def get_recent(self, n: int = 10) -> List[EpisodicEntry]:
        """获取最近N条记录"""
        return list(self._entries)[-n:]

    def search(self, keyword: str, limit: int = 5) -> List[EpisodicEntry]:
        """关键词搜索"""
        results = []
        for entry in reversed(self._entries):
            if keyword.lower() in entry.content.lower():
                results.append(entry)
                if len(results) >= limit:
                    break
        return results

    def get_all(self) -> List[EpisodicEntry]:
        """获取所有记录"""
        return list(self._entries)

    def clear(self):
        """清空情景记忆"""
        self._entries.clear()

    @property
    def size(self) -> int:
        return len(self._entries)


class WorkingMemory:
    """工作记忆 — 当前推理所需的短期上下文

    最近N轮交互, 直接影响推理质量
    溢出时触发MemoryFolding
    """

    def __init__(self, max_turns: int = WORKING_MAX_TURNS):
        self.max_turns = max_turns
        self._turns: List[Dict] = []

    def add(self, role: str, content: str):
        """添加一轮交互"""
        self._turns.append({"role": role, "content": content})
        if len(self._turns) > self.max_turns * 2:
            self._turns = self._turns[-(self.max_turns * 2):]

    def get_context(self, max_turns: Optional[int] = None) -> List[Dict]:
        """获取工作记忆上下文"""
        n = max_turns or self.max_turns
        return self._turns[-n * 2:]

    def is_overflow(self, token_count: int, max_tokens: int) -> bool:
        """判断工作记忆是否溢出"""
        return token_count > max_tokens

    def clear(self):
        """清空工作记忆"""
        self._turns.clear()

    @property
    def size(self) -> int:
        return len(self._turns)


class ToolMemory:
    """工具记忆 — 工具调用历史和结果缓存

    避免重复调用相同工具, 缓存结果供后续使用
    """

    def __init__(self, max_cache: int = TOOL_CACHE_MAX):
        self.max_cache = max_cache
        self._history: deque = deque(maxlen=max_cache)
        self._cache: Dict[str, ToolCallRecord] = {}

    def record_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Optional[str] = None,
        success: bool = True,
    ) -> ToolCallRecord:
        """记录工具调用"""
        cache_key = self._make_cache_key(tool_name, arguments)
        record = ToolCallRecord(
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            success=success,
            timestamp=time.time(),
            cache_key=cache_key,
        )
        self._history.append(record)
        self._cache[cache_key] = record
        return record

    def get_cached(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[ToolCallRecord]:
        """获取缓存的工具调用结果"""
        cache_key = self._make_cache_key(tool_name, arguments)
        return self._cache.get(cache_key)

    def get_tool_history(self, tool_name: str, limit: int = 5) -> List[ToolCallRecord]:
        """获取特定工具的调用历史"""
        results = []
        for record in reversed(self._history):
            if record.tool_name == tool_name:
                results.append(record)
                if len(results) >= limit:
                    break
        return results

    def get_failed_calls(self, limit: int = 10) -> List[ToolCallRecord]:
        """获取失败的工具调用"""
        results = []
        for record in reversed(self._history):
            if not record.success:
                results.append(record)
                if len(results) >= limit:
                    break
        return results

    @staticmethod
    def _make_cache_key(tool_name: str, arguments: Dict[str, Any]) -> str:
        """生成缓存键"""
        import json
        try:
            args_str = json.dumps(arguments, sort_keys=True, ensure_ascii=False)
        except (TypeError, ValueError):
            args_str = str(arguments)
        return f"{tool_name}:{hash(args_str)}"

    def clear(self):
        """清空工具记忆"""
        self._history.clear()
        self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._history)


class BrainMemory:
    """脑启发三层记忆架构

    融合DeepAgent核心记忆模型:
    - Episodic: 情景记忆, 长期存储, 可折叠压缩
    - Working: 工作记忆, 短期上下文, 溢出触发折叠
    - Tool: 工具记忆, 调用历史+结果缓存

    三层协同: Working溢出时, 将Episodic压缩为摘要,
    清空Working, 以摘要为起点重新开始推理
    """

    def __init__(
        self,
        episodic_max: int = EPISODIC_MAX_ENTRIES,
        working_max_turns: int = WORKING_MAX_TURNS,
        tool_cache_max: int = TOOL_CACHE_MAX,
    ):
        self.episodic = EpisodicMemory(max_entries=episodic_max)
        self.working = WorkingMemory(max_turns=working_max_turns)
        self.tool = ToolMemory(max_cache=tool_cache_max)

    def add_interaction(self, role: str, content: str, metadata: Optional[Dict] = None):
        """添加交互到情景记忆和工作记忆"""
        self.episodic.add(role, content, metadata)
        self.working.add(role, content)

    def record_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Optional[str] = None,
        success: bool = True,
    ) -> ToolCallRecord:
        """记录工具调用"""
        record = self.tool.record_call(tool_name, arguments, result, success)

        self.episodic.add(
            "tool_call",
            f"Called {tool_name} with {arguments}",
            {"tool_name": tool_name, "success": success},
        )

        return record

    def get_working_context(self, max_turns: Optional[int] = None) -> List[Dict]:
        """获取工作记忆上下文"""
        return self.working.get_context(max_turns)

    def get_tool_summary(self) -> str:
        """获取工具调用摘要"""
        failed = self.tool.get_failed_calls(limit=5)
        if not failed:
            return "All tool calls succeeded."

        tool_names = [r.tool_name for r in failed]
        return f"Failed tools: {', '.join(tool_names)}"

    def reset(self):
        """重置所有记忆"""
        self.episodic.clear()
        self.working.clear()
        self.tool.clear()