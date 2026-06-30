"""上下文窗口分页管理引擎

融合自Letta(MemGPT) letta/schemas/memory.py + letta/schemas/block.py + letta/services/summarizer/compact.py
核心架构: 类操作系统虚拟内存分页机制
- Block: 上下文窗口最小分页单元(char_limit/label/read_only控制)
- Memory: 三级内存渲染(core/recall/archival), Block组装, token预算分配
- ContextWindowOverview: 上下文窗口全景监控
- compact_messages: 上下文溢出时的压缩/摘要策略(sliding window + self-summarize)
"""
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("cogu.memory.context_window")


@dataclass
class Block:
    """上下文窗口最小分页单元

    融合Letta Block概念:
    - 可编辑的内存块, 支持XML渲染到prompt
    - char_limit控制大小, 超出自动截断
    - read_only标记防止意外修改
    - label标识块用途(core/recall/archival/system)
    """
    label: str = "scratchpad"
    content: str = ""
    char_limit: Optional[int] = None
    read_only: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def set_content(self, content: str) -> bool:
        if self.read_only:
            logger.warning("Block '%s' is read-only", self.label)
            return False
        if self.char_limit and len(content) > self.char_limit:
            content = content[:self.char_limit]
        self.content = content
        return True

    def append(self, text: str) -> bool:
        if self.read_only:
            return False
        new_content = self.content + text
        if self.char_limit and len(new_content) > self.char_limit:
            new_content = new_content[-self.char_limit:]
        self.content = new_content
        return True

    def render(self) -> str:
        if not self.content:
            return ""
        return f"<{self.label}>\n{self.content}\n</{self.label}>"

    @property
    def token_estimate(self) -> int:
        return len(self.content) // 4

    @property
    def is_empty(self) -> bool:
        return len(self.content) == 0


@dataclass
class ContextWindowOverview:
    """上下文窗口全景监控

    融合Letta ContextWindowOverview:
    追踪token预算分配, 监控各Block占用比例
    """
    total_tokens: int = 4096
    used_tokens: int = 0
    blocks: Dict[str, int] = field(default_factory=dict)

    @property
    def remaining_tokens(self) -> int:
        return max(0, self.total_tokens - self.used_tokens)

    @property
    def utilization(self) -> float:
        if self.total_tokens == 0:
            return 0.0
        return self.used_tokens / self.total_tokens

    def is_overflow(self) -> bool:
        return self.used_tokens > self.total_tokens

    def update_block(self, label: str, tokens: int):
        self.blocks[label] = tokens
        self.used_tokens = sum(self.blocks.values())

    def render(self) -> str:
        lines = [f"Context Window: {self.used_tokens}/{self.total_tokens} tokens ({self.utilization:.1%})"]
        for label, tokens in self.blocks.items():
            pct = tokens / self.total_tokens * 100 if self.total_tokens else 0
            lines.append(f"  {label}: {tokens} tokens ({pct:.1f}%)")
        return "\n".join(lines)


class ContextWindowMemory:
    """上下文窗口分页管理引擎

    融合Letta核心内存管理:
    - 三级内存: core(核心指令)/recall(对话历史)/archival(长期存档)
    - Block组装: 每级内存由多个Block组成, 按优先级排列
    - Token预算: 超出时自动压缩或截断低优先级Block
    - compact_messages: 滑动窗口+自摘要压缩
    """

    CORE_LABELS = {"system", "identity", "instructions", "persona"}
    RECALL_LABELS = {"conversation", "history", "recent"}
    ARCHIVAL_LABELS = {"knowledge", "facts", "long_term"}

    def __init__(
        self,
        max_tokens: int = 4096,
        core_ratio: float = 0.3,
        recall_ratio: float = 0.5,
        archival_ratio: float = 0.2,
    ):
        self.max_tokens = max_tokens
        self.core_ratio = core_ratio
        self.recall_ratio = recall_ratio
        self.archival_ratio = archival_ratio

        self._blocks: Dict[str, Block] = {}
        self._overview = ContextWindowOverview(total_tokens=max_tokens)

    def add_block(self, block: Block):
        """添加内存块"""
        self._blocks[block.label] = block

    def get_block(self, label: str) -> Optional[Block]:
        return self._blocks.get(label)

    def remove_block(self, label: str):
        self._blocks.pop(label, None)

    def render_to_prompt(self) -> str:
        """将所有Block渲染为prompt文本"""
        core_parts = []
        recall_parts = []
        archival_parts = []
        other_parts = []

        for label, block in self._blocks.items():
            rendered = block.render()
            if not rendered:
                continue
            if label in self.CORE_LABELS:
                core_parts.append(rendered)
            elif label in self.RECALL_LABELS:
                recall_parts.append(rendered)
            elif label in self.ARCHIVAL_LABELS:
                archival_parts.append(rendered)
            else:
                other_parts.append(rendered)

        all_parts = core_parts + archival_parts + recall_parts + other_parts
        return "\n\n".join(all_parts)

    def get_overview(self) -> ContextWindowOverview:
        """获取上下文窗口全景"""
        overview = ContextWindowOverview(total_tokens=self.max_tokens)
        for label, block in self._blocks.items():
            overview.update_block(label, block.token_estimate)
        self._overview = overview
        return overview

    def compact_if_needed(self, llm_summarizer=None) -> bool:
        """上下文溢出时自动压缩

        策略:
        1. 先截断低优先级Block(archival)
        2. 再压缩recall Block(滑动窗口+摘要)
        3. 最后压缩core Block(仅摘要)
        """
        overview = self.get_overview()
        if not overview.is_overflow():
            return False

        logger.info("上下文溢出: %d/%d tokens, 开始压缩", overview.used_tokens, self.max_tokens)

        for label in list(self._blocks.keys()):
            if label in self.ARCHIVAL_LABELS:
                block = self._blocks[label]
                if not block.read_only:
                    truncated = block.content[:int(block.content.__len__() * 0.5)]
                    block.set_content(truncated + "\n[...truncated...]")

        overview = self.get_overview()
        if not overview.is_overflow():
            return True

        for label in list(self._blocks.keys()):
            if label in self.RECALL_LABELS:
                block = self._blocks[label]
                if not block.read_only and block.content:
                    if llm_summarizer:
                        summary = llm_summarizer(block.content)
                        block.set_content(f"[Summary]\n{summary}")
                    else:
                        half = len(block.content) // 2
                        block.set_content(block.content[-half:])

        overview = self.get_overview()
        if not overview.is_overflow():
            return True

        for label in list(self._blocks.keys()):
            if label not in self.CORE_LABELS and label in self._blocks:
                if not self._blocks[label].read_only:
                    self._blocks[label].set_content("")

        return True

    def reset(self):
        """重置所有Block"""
        self._blocks.clear()
        self._overview = ContextWindowOverview(total_tokens=self.max_tokens)