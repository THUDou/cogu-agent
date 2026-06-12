from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from cogu.app._schema._session import SessionInfo, SessionList, CancelRequest
from cogu.app._service._session import SessionService
from cogu.app._service._chat import ChatService
from cogu.app.deps import get_session_service, get_chat_service

session_router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@session_router.get("", response_model=SessionList)
async def list_sessions(
    session_service: SessionService = Depends(get_session_service),
):
    sessions = session_service.list_sessions()
    return SessionList(sessions=sessions, total=len(sessions))


@session_router.get("/{session_id}", response_model=SessionInfo)
async def get_session(
    session_id: str,
    session_service: SessionService = Depends(get_session_service),
):
    info = session_service.get(session_id)
    if not info:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return info


@session_router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    session_service: SessionService = Depends(get_session_service),
):
    ok = session_service.delete(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return {"deleted": True, "session_id": session_id}


@session_router.post("/{session_id}/cancel")
async def cancel_session(
    session_id: str,
    body: CancelRequest,
    chat_service: ChatService = Depends(get_chat_service),
    session_service: SessionService = Depends(get_session_service),
):
    ok = chat_service.request_cancel(body.request_id)
    session_service.touch(session_id)
    return {"request_id": body.request_id, "session_id": session_id, "canceled": ok}
