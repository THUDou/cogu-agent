"""进化信号检测器 — 参考openJiuwen agent_evolving/signal

从运行时数据中检测进化信号，驱动Agent自进化闭环:
  - 执行失败信号
  - 用户意图信号
  - 轨迹异常信号
  - 对话审查信号
  - 工具失败信号
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class EvolutionSignalType(Enum):
    EXECUTION_FAILURE = "execution_failure"
    USER_INTENT = "user_intent"
    TRAJECTORY_ISSUE = "trajectory_issue"
    CONVERSATION_REVIEW = "conversation_review"
    TOOL_FAILURE = "tool_failure"


class SignalSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class EvolutionSignal:
    """进化信号 — 触发自进化的最小单元"""
    signal_type: EvolutionSignalType
    severity: SignalSeverity = SignalSeverity.MEDIUM
    source: str = ""
    description: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    session_id: str = ""
    agent_id: str = ""

    def to_dict(self) -> dict:
        return {
            "signal_type": self.signal_type.value,
            "severity": self.severity.value,
            "source": self.source,
            "description": self.description,
            "context": self.context,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EvolutionSignal":
        sig_type = EvolutionSignalType(data.get("signal_type", "execution_failure"))
        severity = SignalSeverity(data.get("severity", "medium"))
        return cls(
            signal_type=sig_type,
            severity=severity,
            source=data.get("source", ""),
            description=data.get("description", ""),
            context=data.get("context", {}),
            timestamp=data.get("timestamp", time.time()),
            session_id=data.get("session_id", ""),
            agent_id=data.get("agent_id", ""),
        )


_USER_INTENT_PATTERNS = [
    (r"不(想|要|需要|应该)", "negative_intent"),
    (r"(希望|想要|需要|能不能|可以).{0,20}(改进|优化|更好|更快|更准)", "improvement_intent"),
    (r"(为什么|怎么).{0,20}(不|没有|不能|失败)", "failure_inquiry"),
    (r"(换|改用|切换|替代).{0,20}(工具|方法|策略|方式)", "tool_switch_intent"),
    (r"(太慢|太长|太多|重复|冗余|低效)", "efficiency_complaint"),
]

_EXECUTION_FAILURE_PATTERNS = [
    r"Error:",
    r"Exception:",
    r"Traceback",
    r"FAILED",
    r"timeout",
    r"Permission denied",
]


class SignalDetector:
    """从运行时数据中检测进化信号

    参考openJiuwen agent_evolving/signal:
      - 从session数据中提取信号
      - 从异常中提取信号
      - 从用户反馈中提取信号
    """

    def __init__(self, llm_client: Any = None):
        self.llm = llm_client
        self._signal_history: list[EvolutionSignal] = []
        self._max_history: int = 1000

    def detect_from_session(self, session_data: dict) -> list[EvolutionSignal]:
        """从session数据中检测进化信号

        Args:
            session_data: 包含turns/errors/tools等信息的session数据

        Returns:
            检测到的进化信号列表
        """
        signals: list[EvolutionSignal] = []
        session_id = session_data.get("session_id", "")
        agent_id = session_data.get("agent_id", "")

        for error in session_data.get("errors", []):
            signal = self._detect_execution_error(error, session_id, agent_id)
            if signal:
                signals.append(signal)

        for tool_result in session_data.get("tool_results", []):
            if not tool_result.get("success", True):
                signal = EvolutionSignal(
                    signal_type=EvolutionSignalType.TOOL_FAILURE,
                    severity=SignalSeverity.MEDIUM,
                    source="session_tool_result",
                    description=f"工具调用失败: {tool_result.get('tool_name', 'unknown')}",
                    context={
                        "tool_name": tool_result.get("tool_name", ""),
                        "error": tool_result.get("error", ""),
                        "input": tool_result.get("input", {}),
                    },
                    session_id=session_id,
                    agent_id=agent_id,
                )
                signals.append(signal)

        trajectory_signals = self._detect_trajectory_issues(session_data, session_id, agent_id)
        signals.extend(trajectory_signals)

        for turn in session_data.get("turns", []):
            user_msg = turn.get("user", "")
            if user_msg:
                signal = self._detect_intent_from_message(user_msg, session_id, agent_id)
                if signal:
                    signals.append(signal)

        self._record_signals(signals)
        return signals

    def detect_from_error(self, error: Exception, context: dict) -> Optional[EvolutionSignal]:
        """从异常中检测进化信号

        Args:
            error: 异常对象
            context: 上下文信息

        Returns:
            检测到的进化信号，或None
        """
        error_msg = str(error)
        error_type = type(error).__name__
        severity = SignalSeverity.MEDIUM

        if isinstance(error, (PermissionError, OSError)):
            severity = SignalSeverity.HIGH
        elif isinstance(error, TimeoutError):
            severity = SignalSeverity.LOW
        elif isinstance(error, (ValueError, TypeError)):
            severity = SignalSeverity.MEDIUM

        for pattern in _EXECUTION_FAILURE_PATTERNS:
            if pattern.lower() in error_msg.lower():
                severity = SignalSeverity.HIGH
                break

        signal = EvolutionSignal(
            signal_type=EvolutionSignalType.EXECUTION_FAILURE,
            severity=severity,
            source="exception",
            description=f"{error_type}: {error_msg[:200]}",
            context={
                "error_type": error_type,
                "error_message": error_msg[:500],
                **context,
            },
            session_id=context.get("session_id", ""),
            agent_id=context.get("agent_id", ""),
        )
        self._record_signals([signal])
        return signal

    def detect_from_user_feedback(self, feedback: str) -> Optional[EvolutionSignal]:
        """从用户反馈中检测进化信号

        Args:
            feedback: 用户反馈文本

        Returns:
            检测到的进化信号，或None
        """
        signal = self._detect_intent_from_message(feedback, "", "")
        if signal:
            self._record_signals([signal])
        return signal

    def _detect_execution_error(self, error_data: dict, session_id: str, agent_id: str) -> Optional[EvolutionSignal]:
        """从执行错误中检测信号"""
        error_msg = error_data.get("message", "") or error_data.get("error", "")
        if not error_msg:
            return None

        severity = SignalSeverity.MEDIUM
        for pattern in _EXECUTION_FAILURE_PATTERNS:
            if pattern.lower() in error_msg.lower():
                severity = SignalSeverity.HIGH
                break

        return EvolutionSignal(
            signal_type=EvolutionSignalType.EXECUTION_FAILURE,
            severity=severity,
            source="session_error",
            description=error_msg[:200],
            context=error_data,
            session_id=session_id,
            agent_id=agent_id,
        )

    def _detect_intent_from_message(self, message: str, session_id: str, agent_id: str) -> Optional[EvolutionSignal]:
        """从用户消息中检测意图信号"""
        for pattern, intent_type in _USER_INTENT_PATTERNS:
            if re.search(pattern, message):
                severity = SignalSeverity.MEDIUM
                if intent_type == "efficiency_complaint":
                    severity = SignalSeverity.HIGH
                elif intent_type == "failure_inquiry":
                    severity = SignalSeverity.HIGH

                return EvolutionSignal(
                    signal_type=EvolutionSignalType.USER_INTENT,
                    severity=severity,
                    source="user_message",
                    description=f"用户意图({intent_type}): {message[:100]}",
                    context={"intent_type": intent_type, "message": message[:500]},
                    session_id=session_id,
                    agent_id=agent_id,
                )
        return None

    def _detect_trajectory_issues(self, session_data: dict, session_id: str, agent_id: str) -> list[EvolutionSignal]:
        """检测轨迹异常"""
        signals: list[EvolutionSignal] = []
        turns = session_data.get("turns", [])

        retry_count = 0
        for turn in turns:
            if turn.get("is_retry", False):
                retry_count += 1

        if retry_count >= 3:
            signals.append(EvolutionSignal(
                signal_type=EvolutionSignalType.TRAJECTORY_ISSUE,
                severity=SignalSeverity.HIGH,
                source="trajectory_retry",
                description=f"轨迹重试次数过多: {retry_count}次",
                context={"retry_count": retry_count},
                session_id=session_id,
                agent_id=agent_id,
            ))

        loop_patterns = session_data.get("loop_patterns", [])
        for pattern in loop_patterns:
            signals.append(EvolutionSignal(
                signal_type=EvolutionSignalType.TRAJECTORY_ISSUE,
                severity=SignalSeverity.MEDIUM,
                source="trajectory_loop",
                description=f"检测到循环模式: {pattern.get('description', '')}",
                context=pattern,
                session_id=session_id,
                agent_id=agent_id,
            ))

        return signals

    def _record_signals(self, signals: list[EvolutionSignal]):
        """记录信号到历史"""
        self._signal_history.extend(signals)
        if len(self._signal_history) > self._max_history:
            self._signal_history = self._signal_history[-self._max_history:]

    def get_signal_history(self, signal_type: Optional[EvolutionSignalType] = None, limit: int = 50) -> list[EvolutionSignal]:
        """获取信号历史"""
        if signal_type:
            filtered = [s for s in self._signal_history if s.signal_type == signal_type]
        else:
            filtered = self._signal_history
        return filtered[-limit:]

    def get_signal_stats(self) -> dict:
        """获取信号统计"""
        stats: dict[str, int] = {}
        for sig_type in EvolutionSignalType:
            stats[sig_type.value] = sum(1 for s in self._signal_history if s.signal_type == sig_type)
        severity_stats: dict[str, int] = {}
        for sev in SignalSeverity:
            severity_stats[sev.value] = sum(1 for s in self._signal_history if s.severity == sev)
        return {
            "total": len(self._signal_history),
            "by_type": stats,
            "by_severity": severity_stats,
        }


__all__ = [
    "SignalDetector",
    "EvolutionSignal",
    "EvolutionSignalType",
    "SignalSeverity",
]