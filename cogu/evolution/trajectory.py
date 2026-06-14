"""Trajectory — 完整执行轨迹数据模型

灵感来源: openjiuwen agent_evolving/trajectory/types.py (TrajectoryStep + Trajectory)
COGU 实现: 独立模块，支持 LLM 调用/工具调用/奖励/token ID 记录
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Literal


StepKind = Literal["llm", "tool", "system"]
CostInfo = dict[str, int]
UpdateKey = tuple[str, str]
Updates = dict[UpdateKey, Any]


@dataclass
class LLMCallDetail:
    model: str = ""
    messages: list[Any] = field(default_factory=list)
    response: Any = None
    tools: list[dict[str, Any]] | None = None
    usage: dict[str, Any] | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCallDetail:
    tool_name: str = ""
    call_args: Any = None
    call_result: Any = None
    tool_description: str | None = None
    tool_schema: dict[str, Any] | None = None
    tool_call_id: str | None = None


StepDetail = LLMCallDetail | ToolCallDetail | None


@dataclass
class TrajectoryStep:
    kind: StepKind
    error: dict[str, Any] | None = None
    start_time_ms: int | None = None
    end_time_ms: int | None = None
    detail: StepDetail = None
    reward: float | None = None
    prompt_token_ids: list[int] | None = None
    completion_token_ids: list[int] | None = None
    logprobs: Any = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> int | None:
        if self.start_time_ms is not None and self.end_time_ms is not None:
            return self.end_time_ms - self.start_time_ms
        return None

    @property
    def has_error(self) -> bool:
        return self.error is not None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"kind": self.kind}
        if self.error:
            d["error"] = self.error
        if self.start_time_ms is not None:
            d["start_time_ms"] = self.start_time_ms
        if self.end_time_ms is not None:
            d["end_time_ms"] = self.end_time_ms
        if self.reward is not None:
            d["reward"] = self.reward
        if self.meta:
            d["meta"] = self.meta
        if self.detail:
            d["detail"] = _detail_to_dict(self.detail)
        return d


def _detail_to_dict(detail: StepDetail) -> dict[str, Any]:
    if isinstance(detail, LLMCallDetail):
        return {
            "type": "llm",
            "model": detail.model,
            "usage": detail.usage,
            "meta": detail.meta,
        }
    if isinstance(detail, ToolCallDetail):
        return {
            "type": "tool",
            "tool_name": detail.tool_name,
            "tool_call_id": detail.tool_call_id,
        }
    return {}


@dataclass
class Trajectory:
    execution_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    steps: list[TrajectoryStep] = field(default_factory=list)
    source: str = "offline"
    case_id: str | None = None
    session_id: str | None = None
    cost: CostInfo | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def step_count(self) -> int:
        return len(self.steps)

    @property
    def llm_steps(self) -> list[TrajectoryStep]:
        return [s for s in self.steps if s.kind == "llm"]

    @property
    def tool_steps(self) -> list[TrajectoryStep]:
        return [s for s in self.steps if s.kind == "tool"]

    @property
    def error_steps(self) -> list[TrajectoryStep]:
        return [s for s in self.steps if s.has_error]

    @property
    def total_reward(self) -> float:
        return sum(s.reward or 0.0 for s in self.steps)

    @property
    def has_errors(self) -> bool:
        return any(s.has_error for s in self.steps)

    def add_step(self, step: TrajectoryStep) -> None:
        self.steps.append(step)

    def add_llm_call(
        self,
        model: str,
        messages: list[Any],
        response: Any = None,
        usage: dict[str, Any] | None = None,
        **meta: Any,
    ) -> TrajectoryStep:
        step = TrajectoryStep(
            kind="llm",
            start_time_ms=int(time.time() * 1000),
            detail=LLMCallDetail(model=model, messages=messages, response=response, usage=usage),
            meta=dict(meta),
        )
        step.end_time_ms = int(time.time() * 1000)
        self.add_step(step)
        return step

    def add_tool_call(
        self,
        tool_name: str,
        call_args: Any = None,
        call_result: Any = None,
        tool_call_id: str | None = None,
        **meta: Any,
    ) -> TrajectoryStep:
        step = TrajectoryStep(
            kind="tool",
            start_time_ms=int(time.time() * 1000),
            detail=ToolCallDetail(
                tool_name=tool_name,
                call_args=call_args,
                call_result=call_result,
                tool_call_id=tool_call_id,
            ),
            meta=dict(meta),
        )
        step.end_time_ms = int(time.time() * 1000)
        self.add_step(step)
        return step

    def to_messages(self) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        for step in self.steps:
            if step.kind == "llm" and isinstance(step.detail, LLMCallDetail):
                messages.extend(
                    _message_to_dict(m) for m in step.detail.messages
                )
                if step.detail.response is not None:
                    resp = _message_to_dict(step.detail.response)
                    if "role" in resp or "content" in resp:
                        messages.append(resp)
        return messages

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "steps": [s.to_dict() for s in self.steps],
            "source": self.source,
            "case_id": self.case_id,
            "session_id": self.session_id,
            "cost": self.cost,
            "meta": self.meta,
        }

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str | Path) -> Trajectory:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        traj = cls(
            execution_id=data.get("execution_id", uuid.uuid4().hex[:16]),
            source=data.get("source", "offline"),
            case_id=data.get("case_id"),
            session_id=data.get("session_id"),
            cost=data.get("cost"),
            meta=data.get("meta", {}),
        )
        for step_data in data.get("steps", []):
            step = TrajectoryStep(
                kind=step_data.get("kind", "system"),
                error=step_data.get("error"),
                start_time_ms=step_data.get("start_time_ms"),
                end_time_ms=step_data.get("end_time_ms"),
                reward=step_data.get("reward"),
                meta=step_data.get("meta", {}),
            )
            traj.add_step(step)
        return traj


def _message_to_dict(message: Any) -> dict[str, Any]:
    if isinstance(message, dict):
        return message
    role = getattr(message, "role", None)
    if role is not None:
        item: dict[str, Any] = {"role": role, "content": str(getattr(message, "content", ""))}
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            item["tool_calls"] = tool_calls
        return item
    return {"role": "unknown", "content": str(message)}


class TrajectoryRegistry:
    """轨迹注册表 — 管理多条轨迹的存储和查询"""

    def __init__(self, storage_dir: str | Path = "trajectories"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._trajectories: dict[str, Trajectory] = {}

    def register(self, trajectory: Trajectory) -> None:
        self._trajectories[trajectory.execution_id] = trajectory
        path = self.storage_dir / f"{trajectory.execution_id}.json"
        trajectory.save(path)

    def get(self, execution_id: str) -> Trajectory | None:
        if execution_id in self._trajectories:
            return self._trajectories[execution_id]
        path = self.storage_dir / f"{execution_id}.json"
        if path.exists():
            traj = Trajectory.load(path)
            self._trajectories[execution_id] = traj
            return traj
        return None

    def list_all(self, limit: int = 100) -> list[Trajectory]:
        trajectories = []
        for path in sorted(self.storage_dir.glob("*.json"), reverse=True)[:limit]:
            try:
                traj = Trajectory.load(path)
                trajectories.append(traj)
            except Exception:
                continue
        return trajectories

    def search_by_session(self, session_id: str) -> list[Trajectory]:
        return [
            t for t in self.list_all(limit=500)
            if t.session_id == session_id
        ]

    def aggregate_cost(self, trajectories: list[Trajectory] | None = None) -> CostInfo:
        trajectories = trajectories or self.list_all()
        total: CostInfo = {"input_tokens": 0, "output_tokens": 0}
        for t in trajectories:
            if t.cost:
                for key, val in t.cost.items():
                    total[key] = total.get(key, 0) + val
        return total
