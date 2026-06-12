from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from cogu.core.runner import Runner
from cogu.config.settings import Settings
from cogu.app._service._chat import ChatService
from cogu.app._service._session import SessionService
from cogu.app._service._agent import AgentService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def app_lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings.default()
    await Runner.start(settings)
    logger.info("COGU Runner started")

    app.state.chat_service = ChatService()
    app.state.session_service = SessionService()
    app.state.agent_service = AgentService()

    yield

    await Runner.stop()
    logger.info("COGU Runner stopped")
