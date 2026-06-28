"""从历史session中蒸馏最佳实践 — 参考MiMo-Code /distill

从历史session中发现重复工作流并打包为可复用skill:
  - distill: 从session中蒸馏最佳实践
  - detect_patterns: 检测重复模式
  - generate_skill_from_pattern: 从模式生成skill
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class DistillResult:
    """蒸馏结果"""
    pattern_name: str = ""
    pattern_type: str = ""
    occurrences: int = 0
    confidence: float = 0.0
    skill_data: Optional[dict] = None
    sessions_involved: list[str] = field(default_factory=list)
    distilled_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "pattern_name": self.pattern_name,
            "pattern_type": self.pattern_type,
            "occurrences": self.occurrences,
            "confidence": self.confidence,
            "skill_data": self.skill_data,
            "sessions_involved": self.sessions_involved,
            "distilled_at": self.distilled_at,
        }


@dataclass
class WorkflowPattern:
    """检测到的工作流模式"""
    pattern_id: str = ""
    pattern_type: str = ""
    description: str = ""
    steps: list[str] = field(default_factory=list)
    tool_sequence: list[str] = field(default_factory=list)
    frequency: int = 0
    sessions: list[str] = field(default_factory=list)
    success_rate: float = 0.0

    def to_dict(self) -> dict:
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type,
            "description": self.description,
            "steps": self.steps,
            "tool_sequence": self.tool_sequence,
            "frequency": self.frequency,
            "sessions": self.sessions,
            "success_rate": self.success_rate,
        }


class Distiller:
    """从历史session中发现重复工作流并打包为可复用skill

    参考MiMo-Code /distill:
      - 从历史session中提取工具调用序列
      - 检测重复出现的工作流模式
      - 将高频模式打包为可复用skill
    """

    def __init__(self, storage_dir: str = "", llm_client: Any = None):
        if storage_dir:
            self._storage_dir = Path(storage_dir)
        else:
            self._storage_dir = Path.home() / ".cogu" / "distill"
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self.llm = llm_client
        self._patterns: list[WorkflowPattern] = []
        self._distilled_skills: list[dict] = []

    async def distill(
        self,
        session_ids: list[str] | None = None,
        min_occurrences: int = 2,
    ) -> list[DistillResult]:
        """从历史session中蒸馏最佳实践

        Args:
            session_ids: 指定session，None则扫描全部
            min_occurrences: 最小出现次数阈值

        Returns:
            蒸馏结果列表
        """
        sessions = self._load_sessions(session_ids)
        if not sessions:
            return []

        patterns = self._detect_patterns(sessions)
        results: list[DistillResult] = []

        for pattern in patterns:
            if pattern.frequency < min_occurrences:
                continue

            skill_data = self._generate_skill_from_pattern(pattern)
            if not skill_data:
                continue

            result = DistillResult(
                pattern_name=pattern.description[:50],
                pattern_type=pattern.pattern_type,
                occurrences=pattern.frequency,
                confidence=min(pattern.success_rate, pattern.frequency / max(len(sessions), 1)),
                skill_data=skill_data,
                sessions_involved=pattern.sessions,
            )
            results.append(result)
            self._patterns.append(pattern)
            self._distilled_skills.append(skill_data)

        self._save_distilled()
        return results

    def _detect_patterns(self, sessions: list[dict]) -> list[WorkflowPattern]:
        """检测重复工作流模式

        策略:
          1. 工具调用序列模式 — 相同的tool序列重复出现
          2. 错误恢复模式 — 相同错误→相同修复
          3. 任务完成模式 — 相同目标→相同步骤
        """
        patterns: list[WorkflowPattern] = []

        tool_seq_map: dict[str, WorkflowPattern] = {}
        for session in sessions:
            session_id = session.get("session_id", "")
            tool_calls = session.get("tool_calls", [])
            if not tool_calls:
                continue

            tool_names = [tc.get("tool_name", "") for tc in tool_calls if tc.get("tool_name")]

            for seq_len in range(2, min(len(tool_names) + 1, 6)):
                for i in range(len(tool_names) - seq_len + 1):
                    sub_seq = tool_names[i:i + seq_len]
                    seq_key = "->".join(sub_seq)

                    if seq_key not in tool_seq_map:
                        tool_seq_map[seq_key] = WorkflowPattern(
                            pattern_id=f"pat_{hashlib.md5(seq_key.encode()).hexdigest()[:8]}",
                            pattern_type="tool_sequence",
                            description=f"工具序列: {seq_key}",
                            tool_sequence=sub_seq,
                            sessions=[],
                        )

                    if session_id not in tool_seq_map[seq_key].sessions:
                        tool_seq_map[seq_key].sessions.append(session_id)
                        tool_seq_map[seq_key].frequency += 1

                    success = session.get("success", True)
                    if success:
                        tool_seq_map[seq_key].success_rate = min(
                            1.0,
                            tool_seq_map[seq_key].success_rate + 0.1,
                        )

        for pattern in tool_seq_map.values():
            if pattern.frequency >= 2:
                patterns.append(pattern)

        error_recovery_map: dict[str, WorkflowPattern] = {}
        for session in sessions:
            session_id = session.get("session_id", "")
            turns = session.get("turns", [])

            for i, turn in enumerate(turns):
                if turn.get("type") == "error":
                    error_msg = turn.get("message", "")[:100]
                    recovery_steps = []
                    for j in range(i + 1, min(i + 4, len(turns))):
                        if turns[j].get("type") == "tool_call":
                            recovery_steps.append(turns[j].get("tool_name", ""))

                    if recovery_steps:
                        key = f"err:{error_msg}:" + "->".join(recovery_steps)
                        if key not in error_recovery_map:
                            error_recovery_map[key] = WorkflowPattern(
                                pattern_id=f"pat_{hashlib.md5(key.encode()).hexdigest()[:8]}",
                                pattern_type="error_recovery",
                                description=f"错误恢复: {error_msg[:30]}",
                                steps=recovery_steps,
                                tool_sequence=recovery_steps,
                                sessions=[],
                            )
                        if session_id not in error_recovery_map[key].sessions:
                            error_recovery_map[key].sessions.append(session_id)
                            error_recovery_map[key].frequency += 1

        for pattern in error_recovery_map.values():
            if pattern.frequency >= 2:
                patterns.append(pattern)

        patterns.sort(key=lambda p: -p.frequency)
        return patterns

    def _generate_skill_from_pattern(self, pattern: WorkflowPattern) -> Optional[dict]:
        """从模式生成skill定义

        Args:
            pattern: 检测到的工作流模式

        Returns:
            skill定义字典，或None
        """
        if pattern.pattern_type == "tool_sequence":
            steps = []
            for i, tool in enumerate(pattern.tool_sequence, 1):
                steps.append(f"调用 {tool} 完成第{i}步操作")

            return {
                "name": f"auto_{pattern.pattern_id}",
                "version": "1.0.0",
                "description": pattern.description,
                "category": "custom",
                "tags": ["auto-distilled", pattern.pattern_type],
                "recipes": [{
                    "name": pattern.description,
                    "description": f"自动蒸馏的工具序列模式(出现{pattern.frequency}次)",
                    "trigger": pattern.tool_sequence[0] if pattern.tool_sequence else "",
                    "steps": steps,
                }],
                "required_tools": pattern.tool_sequence,
                "risk_level": "low",
                "disclosure_level": "summary",
            }

        if pattern.pattern_type == "error_recovery":
            return {
                "name": f"auto_fix_{pattern.pattern_id}",
                "version": "1.0.0",
                "description": pattern.description,
                "category": "custom",
                "tags": ["auto-distilled", "error-recovery"],
                "recipes": [{
                    "name": pattern.description,
                    "description": f"自动蒸馏的错误恢复模式(出现{pattern.frequency}次)",
                    "trigger": pattern.description.split(":")[-1].strip() if ":" in pattern.description else "",
                    "steps": pattern.steps,
                }],
                "required_tools": pattern.tool_sequence,
                "risk_level": "medium",
                "side_effects": ["可能执行修复操作"],
                "disclosure_level": "detail",
            }

        return None

    def _load_sessions(self, session_ids: list[str] | None = None) -> list[dict]:
        """加载session数据"""
        sessions: list[dict] = []
        sessions_dir = self._storage_dir / "sessions"
        if not sessions_dir.exists():
            return sessions

        for session_file in sessions_dir.glob("*.json"):
            if session_ids:
                if session_file.stem not in session_ids:
                    continue
            try:
                data = json.loads(session_file.read_text(encoding="utf-8"))
                data.setdefault("session_id", session_file.stem)
                sessions.append(data)
            except (json.JSONDecodeError, KeyError):
                pass

        return sessions

    def _save_distilled(self):
        """持久化蒸馏结果"""
        output_file = self._storage_dir / "distilled_skills.json"
        existing = []
        if output_file.exists():
            try:
                existing = json.loads(output_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, KeyError):
                pass

        existing.extend(self._distilled_skills)
        output_file.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_distilled_skills(self) -> list[dict]:
        """获取已蒸馏的skill列表"""
        output_file = self._storage_dir / "distilled_skills.json"
        if output_file.exists():
            try:
                return json.loads(output_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, KeyError):
                pass
        return []

    def get_stats(self) -> dict:
        """获取蒸馏统计"""
        return {
            "patterns_detected": len(self._patterns),
            "skills_distilled": len(self._distilled_skills),
            "storage_dir": str(self._storage_dir),
        }


__all__ = ["Distiller", "DistillResult", "WorkflowPattern"]