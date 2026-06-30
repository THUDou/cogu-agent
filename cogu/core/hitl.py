from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class QuestionType(str, Enum):
    TEXT = "text"
    CHOICE = "choice"
    APPROVAL = "approval"
    CONFIRMATION = "confirmation"


class QuestionStatus(str, Enum):
    PENDING = "pending"
    ANSWERED = "answered"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class Question:
    question_id: str = ""
    question_type: QuestionType = QuestionType.TEXT
    question: str = ""
    options: list[str] = field(default_factory=list)
    default: str = ""
    risk_level: str = "low"
    context: dict[str, Any] = field(default_factory=dict)
    status: QuestionStatus = QuestionStatus.PENDING
    answer: str = ""
    created_at: float = field(default_factory=time.time)
    answered_at: float = 0.0
    timeout_seconds: float = 300.0

    def to_dict(self) -> dict:
        return {
            "question_id": self.question_id,
            "question_type": self.question_type.value,
            "question": self.question,
            "options": self.options,
            "default": self.default,
            "risk_level": self.risk_level,
            "context": self.context,
            "status": self.status.value,
            "answer": self.answer,
            "created_at": self.created_at,
            "answered_at": self.answered_at,
            "timeout_seconds": self.timeout_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Question":
        q_type = QuestionType(data.get("question_type", "text"))
        status = QuestionStatus(data.get("status", "pending"))
        return cls(
            question_id=data.get("question_id", ""),
            question_type=q_type,
            question=data.get("question", ""),
            options=data.get("options", []),
            default=data.get("default", ""),
            risk_level=data.get("risk_level", "low"),
            context=data.get("context", {}),
            status=status,
            answer=data.get("answer", ""),
            created_at=data.get("created_at", time.time()),
            answered_at=data.get("answered_at", 0.0),
            timeout_seconds=data.get("timeout_seconds", 300.0),
        )


@dataclass
class ApprovalRequest:
    request_id: str = ""
    action: str = ""
    risk_level: str = "low"
    details: str = ""
    auto_approve: bool = False
    status: QuestionStatus = QuestionStatus.PENDING
    approved: bool = False
    reason: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "action": self.action,
            "risk_level": self.risk_level,
            "details": self.details,
            "auto_approve": self.auto_approve,
            "status": self.status.value,
            "approved": self.approved,
            "reason": self.reason,
            "created_at": self.created_at,
        }


class HITLManager:

    def __init__(self, event_callback: Optional[Callable] = None, auto_approve_low_risk: bool = False):
        self._event_callback = event_callback
        self._auto_approve_low_risk = auto_approve_low_risk
        self._pending_questions: dict[str, asyncio.Future] = {}
        self._pending_approvals: dict[str, asyncio.Future] = {}
        self._question_history: list[Question] = []
        self._approval_history: list[ApprovalRequest] = []

    async def ask_human(
        self,
        question: str,
        options: list[str] | None = None,
        timeout: float = 300.0,
    ) -> str:
        question_id = f"q_{uuid.uuid4().hex[:12]}"
        q_type = QuestionType.CHOICE if options else QuestionType.TEXT

        q = Question(
            question_id=question_id,
            question_type=q_type,
            question=question,
            options=options or [],
            timeout_seconds=timeout,
        )

        event = self.create_question_event(question_id, question, options or [])
        if self._event_callback:
            try:
                if asyncio.iscoroutinefunction(self._event_callback):
                    await self._event_callback(event)
                else:
                    self._event_callback(event)
            except Exception:
                pass

        answer = await self.wait_for_reply(question_id, timeout)
        return answer

    async def ask_approval(
        self,
        action: str,
        risk_level: str = "low",
        details: str = "",
    ) -> bool:
        request_id = f"apr_{uuid.uuid4().hex[:12]}"

        if self._auto_approve_low_risk and risk_level == "low":
            approval = ApprovalRequest(
                request_id=request_id,
                action=action,
                risk_level=risk_level,
                details=details,
                auto_approve=True,
                status=QuestionStatus.ANSWERED,
                approved=True,
                reason="低风险自动审批",
            )
            self._approval_history.append(approval)
            return True

        approval = ApprovalRequest(
            request_id=request_id,
            action=action,
            risk_level=risk_level,
            details=details,
        )

        event = self._create_approval_event(request_id, action, risk_level, details)
        if self._event_callback:
            try:
                if asyncio.iscoroutinefunction(self._event_callback):
                    await self._event_callback(event)
                else:
                    self._event_callback(event)
            except Exception:
                pass

        loop = asyncio.get_event_loop()
        future: asyncio.Future[bool] = loop.create_future()
        self._pending_approvals[request_id] = future

        try:
            approved = await asyncio.wait_for(future, timeout=300.0)
            approval.status = QuestionStatus.ANSWERED
            approval.approved = approved
        except asyncio.TimeoutError:
            approval.status = QuestionStatus.TIMEOUT
            approval.approved = False
            approval.reason = "审批超时"
        finally:
            self._pending_approvals.pop(request_id, None)
            self._approval_history.append(approval)

        return approval.approved

    def create_question_event(
        self,
        question_id: str,
        question: str,
        options: list[str] | None = None,
    ) -> dict:
        return {
            "event": "hitl_question",
            "data": {
                "question_id": question_id,
                "question": question,
                "options": options or [],
                "timestamp": time.time(),
            },
        }

    async def wait_for_reply(self, question_id: str, timeout: float = 300.0) -> str:
        loop = asyncio.get_event_loop()
        future: asyncio.Future[str] = loop.create_future()
        self._pending_questions[question_id] = future

        try:
            answer = await asyncio.wait_for(future, timeout=timeout)
            return answer
        except asyncio.TimeoutError:
            return ""
        finally:
            self._pending_questions.pop(question_id, None)

    def submit_reply(self, question_id: str, answer: str) -> bool:
        future = self._pending_questions.get(question_id)
        if future and not future.done():
            future.set_result(answer)
            return True
        return False

    def submit_approval(self, request_id: str, approved: bool, reason: str = "") -> bool:
        future = self._pending_approvals.get(request_id)
        if future and not future.done():
            future.set_result(approved)
            return True
        return False

    def _create_approval_event(
        self,
        request_id: str,
        action: str,
        risk_level: str,
        details: str,
    ) -> dict:
        return {
            "event": "hitl_approval",
            "data": {
                "request_id": request_id,
                "action": action,
                "risk_level": risk_level,
                "details": details,
                "timestamp": time.time(),
            },
        }

    def get_pending_questions(self) -> list[dict]:
        return [
            q.to_dict() for q in self._question_history
            if q.status == QuestionStatus.PENDING
        ]

    def get_pending_approvals(self) -> list[dict]:
        return [
            a.to_dict() for a in self._approval_history
            if a.status == QuestionStatus.PENDING
        ]

    def get_stats(self) -> dict:
        return {
            "questions_asked": len(self._question_history),
            "questions_answered": sum(1 for q in self._question_history if q.status == QuestionStatus.ANSWERED),
            "questions_timeout": sum(1 for q in self._question_history if q.status == QuestionStatus.TIMEOUT),
            "approvals_requested": len(self._approval_history),
            "approvals_granted": sum(1 for a in self._approval_history if a.approved),
            "approvals_rejected": sum(1 for a in self._approval_history if not a.approved and a.status == QuestionStatus.ANSWERED),
            "pending_questions": len(self._pending_questions),
            "pending_approvals": len(self._pending_approvals),
        }


__all__ = [
    "HITLManager",
    "Question",
    "QuestionType",
    "QuestionStatus",
    "ApprovalRequest",
]
