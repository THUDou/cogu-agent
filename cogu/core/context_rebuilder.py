"""Context Rebuilder — 上下文重建

基于小米 MiMo-Code 智能上下文管理方案：
当上下文接近 token 限制时，从 checkpoint + memory + task progress
重建精简上下文，使用 budget 分配策略确保关键信息不丢失。
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional, TYPE_CHECKING

from cogu.core.checkpoint import Checkpoint, CheckpointManager

if TYPE_CHECKING:
    from cogu.memory.memory_store import MemoryStore


@dataclass
class BudgetAllocation:
    system_prompt: int = 0
    checkpoint: int = 0
    memory: int = 0
    recent_messages: int = 0
    task_progress: int = 0

    def total(self) -> int:
        return (
            self.system_prompt
            + self.checkpoint
            + self.memory
            + self.recent_messages
            + self.task_progress
        )


SECTION_PRIORITY = [
    "summary",
    "key_decisions",
    "active_tasks",
    "file_changes",
    "tool_results",
]


class ContextRebuilder:
    def __init__(
        self,
        checkpoint_manager: Optional[CheckpointManager] = None,
        memory_store: Optional[MemoryStore] = None,
        recent_rounds: int = 5,
        system_prompt_ratio: float = 0.15,
        checkpoint_ratio: float = 0.25,
        memory_ratio: float = 0.20,
        recent_messages_ratio: float = 0.30,
        task_progress_ratio: float = 0.10,
    ):
        self._checkpoint_manager = checkpoint_manager
        self._memory_store = memory_store
        self._recent_rounds = recent_rounds
        self._ratios = {
            "system_prompt": system_prompt_ratio,
            "checkpoint": checkpoint_ratio,
            "memory": memory_ratio,
            "recent_messages": recent_messages_ratio,
            "task_progress": task_progress_ratio,
        }
        self._logger = logging.getLogger(__name__)

    def _budget_allocation(self, total_budget: int) -> BudgetAllocation:
        return BudgetAllocation(
            system_prompt=int(total_budget * self._ratios["system_prompt"]),
            checkpoint=int(total_budget * self._ratios["checkpoint"]),
            memory=int(total_budget * self._ratios["memory"]),
            recent_messages=int(total_budget * self._ratios["recent_messages"]),
            task_progress=int(total_budget * self._ratios["task_progress"]),
        )

    def _count_tokens(self, messages: list[dict]) -> int:
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                chinese = len(re.findall(r'[\u4e00-\u9fff]', content))
                english = len(content) - chinese
                total += chinese + (english + 3) // 4
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        total += len(json.dumps(block, ensure_ascii=False)) // 4
                    else:
                        total += len(str(block)) // 4
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                total += len(json.dumps(tool_calls, ensure_ascii=False)) // 4
            total += 4
        return total

    async def rebuild(
        self,
        messages: list[dict],
        session_id: str,
        token_limit: int,
    ) -> list[dict]:
        current_tokens = self._count_tokens(messages)
        if current_tokens <= token_limit:
            return messages

        budget = self._budget_allocation(token_limit)
        self._logger.info(
            f"context_rebuilder.rebuild: current_tokens={current_tokens}, "
            f"limit={token_limit}, budget={budget.total()}"
        )

        rebuilt: list[dict] = []

        system_messages = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]

        rebuilt.extend(self._fit_system_messages(system_messages, budget.system_prompt))

        checkpoint_block = await self._build_checkpoint_block(session_id, budget.checkpoint)
        if checkpoint_block:
            rebuilt.append(checkpoint_block)

        memory_block = await self._build_memory_block(session_id, budget.memory)
        if memory_block:
            rebuilt.append(memory_block)

        task_block = await self._build_task_progress_block(session_id, budget.task_progress)
        if task_block:
            rebuilt.append(task_block)

        recent = self._fit_recent_messages(non_system, budget.recent_messages)
        rebuilt.extend(recent)

        final_tokens = self._count_tokens(rebuilt)
        self._logger.info(
            f"context_rebuilder.rebuild.done: rebuilt_tokens={final_tokens}, "
            f"messages={len(rebuilt)}"
        )
        return rebuilt

    def _fit_system_messages(self, system_messages: list[dict], budget: int) -> list[dict]:
        if not system_messages:
            return []
        result = []
        used = 0
        for msg in system_messages:
            msg_tokens = self._count_tokens([msg])
            if used + msg_tokens <= budget:
                result.append(msg)
                used += msg_tokens
            else:
                remaining = budget - used
                if remaining > 50:
                    truncated = self._truncate_message(msg, remaining)
                    result.append(truncated)
                break
        return result

    async def _build_checkpoint_block(self, session_id: str, budget: int) -> Optional[dict]:
        if not self._checkpoint_manager:
            return None
        checkpoint = await self._checkpoint_manager.load_checkpoint(session_id)
        if not checkpoint:
            return None

        sources: dict[str, str] = {}
        if checkpoint.summary:
            sources["summary"] = checkpoint.summary
        if checkpoint.key_decisions:
            sources["key_decisions"] = "\n".join(f"- {d}" for d in checkpoint.key_decisions)
        if checkpoint.active_tasks:
            sources["active_tasks"] = "\n".join(f"- {t}" for t in checkpoint.active_tasks)
        if checkpoint.file_changes:
            sources["file_changes"] = "\n".join(f"- {f}" for f in checkpoint.file_changes)
        if checkpoint.tool_results_summary:
            sources["tool_results"] = "\n".join(f"- {r}" for r in checkpoint.tool_results_summary)

        content = await self.budgeted_read(sources, budget)
        if not content:
            return None

        return {
            "role": "system",
            "content": f"[Checkpoint Context — {checkpoint.session_id} @ {time.strftime('%H:%M:%S', time.localtime(checkpoint.created_at))}]\n{content}",
        }

    async def _build_memory_block(self, session_id: str, budget: int) -> Optional[dict]:
        if not self._memory_store:
            return None
        try:
            memory_content = self._memory_store.inject_context(
                session=type("FakeSession", (), {"id": session_id, "session_id": session_id})(),
                global_budget=int(budget * 0.3),
                project_budget=int(budget * 0.5),
                checkpoint_budget=int(budget * 0.2),
            )
            if not memory_content:
                return None
            return {
                "role": "system",
                "content": f"[Project Memory]\n{memory_content[:budget]}",
            }
        except Exception as e:
            self._logger.warning(f"context_rebuilder._build_memory_block.failed: {e}")
            return None

    async def _build_task_progress_block(self, session_id: str, budget: int) -> Optional[dict]:
        if not self._checkpoint_manager:
            return None
        checkpoints = await self._checkpoint_manager.list_checkpoints(session_id)
        if not checkpoints:
            return None

        progress_lines = []
        for cp in checkpoints[:3]:
            ts = time.strftime('%H:%M:%S', time.localtime(cp.created_at))
            line = f"[{ts}] tokens={cp.token_count}"
            if cp.active_tasks:
                line += f" | tasks: {', '.join(cp.active_tasks[:3])}"
            if cp.key_decisions:
                line += f" | decisions: {', '.join(cp.key_decisions[:2])}"
            progress_lines.append(line)

        content = "\n".join(progress_lines)
        if not content:
            return None
        return {
            "role": "system",
            "content": f"[Task Progress]\n{content[:budget]}",
        }

    def _fit_recent_messages(self, non_system: list[dict], budget: int) -> list[dict]:
        rounds = self._collect_recent_rounds(non_system)
        result = []
        used = 0
        for msg in reversed(rounds):
            msg_tokens = self._count_tokens([msg])
            if used + msg_tokens <= budget:
                result.insert(0, msg)
                used += msg_tokens
            else:
                remaining = budget - used
                if remaining > 50 and not result:
                    truncated = self._truncate_message(msg, remaining)
                    result.insert(0, truncated)
                break
        return result

    def _collect_recent_rounds(self, messages: list[dict]) -> list[dict]:
        round_count = 0
        cut_idx = len(messages)
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "user":
                round_count += 1
                if round_count >= self._recent_rounds:
                    cut_idx = i
                    break
        return messages[cut_idx:]

    async def budgeted_read(self, sources: dict[str, str], budget: int) -> str:
        if not sources or budget <= 0:
            return ""

        sections: list[tuple[str, str]] = []
        for key in SECTION_PRIORITY:
            if key in sources and sources[key].strip():
                sections.append((key, sources[key]))

        if not sections:
            return ""

        result_parts: list[str] = []
        remaining = budget

        for section_name, section_content in sections:
            if remaining <= 0:
                break
            header = f"### {section_name}"
            header_cost = len(header) // 4 + 4
            if header_cost >= remaining:
                break

            available = remaining - header_cost
            content_chars = available * 4
            truncated = section_content[:content_chars]
            result_parts.append(f"{header}\n{truncated}")
            remaining -= header_cost + self._estimate_text_tokens(truncated)

        return "\n\n".join(result_parts)

    def _estimate_text_tokens(self, text: str) -> int:
        chinese = len(re.findall(r'[\u4e00-\u9fff]', text))
        english = len(text) - chinese
        return chinese + (english + 3) // 4

    def _truncate_message(self, msg: dict, token_budget: int) -> dict:
        content = msg.get("content", "")
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)

        char_budget = token_budget * 4
        if len(content) <= char_budget:
            return msg

        truncated = content[:char_budget]
        result = dict(msg)
        result["content"] = truncated + "\n[...truncated]"
        return result


__all__ = ["ContextRebuilder", "BudgetAllocation", "SECTION_PRIORITY"]