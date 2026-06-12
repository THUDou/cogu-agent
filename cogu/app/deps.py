from __future__ import annotations

from fastapi import Request

from cogu.app._service._chat import ChatService
from cogu.app._service._session import SessionService
from cogu.app._service._agent import AgentService


def get_chat_service(request: Request) -> ChatService:
    return request.app.state.chat_service


def get_session_service(request: Request) -> SessionService:
    return request.app.state.session_service


def get_agent_service(request: Request) -> AgentService:
    return request.app.state.agent_service
