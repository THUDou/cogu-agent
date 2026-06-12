from __future__ import annotations

import time
from typing import Optional

from cogu.core.runner import Runner
from cogu.core.session import Session
from cogu.app._schema._session import SessionInfo


class SessionService:
    def __init__(self):
        self._sessions: dict[str, dict] = {}

    def create(self, session_id: str = "", user_id: str = "anonymous") -> dict:
        import uuid
        sid = session_id or uuid.uuid4().hex[:12]
        now = time.time()
        info = {
            "session_id": sid,
            "user_id": user_id,
            "message_count": 0,
            "tool_calls_count": 0,
            "created_at": now,
            "updated_at": now,
        }
        self._sessions[sid] = info
        return info

    def get(self, session_id: str) -> Optional[SessionInfo]:
        info = self._sessions.get(session_id)
        if info:
            runner_session = Runner.get_session(session_id)
            if runner_session:
                info["message_count"] = len(runner_session.conversation)
                info["tool_calls_count"] = runner_session.state.tool_calls_count
                info["updated_at"] = runner_session.state.updated_at
            return SessionInfo(**info)
        return None

    def list_sessions(self, limit: int = 50) -> list[SessionInfo]:
        runner_sessions = {s["session_id"]: s for s in Runner.list_sessions()}
        result = []
        for sid, info in list(self._sessions.items())[:limit]:
            if sid in runner_sessions:
                info["message_count"] = runner_sessions[sid].get("msgs", 0)
            result.append(SessionInfo(**info))
        return result

    def delete(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            Runner.release_session(session_id)
            return True
        return False

    def touch(self, session_id: str) -> None:
        if session_id in self._sessions:
            self._sessions[session_id]["updated_at"] = time.time()
