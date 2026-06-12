from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sse_starlette.sse import EventSourceResponse

from cogu.app._schema._chat import ChatRequest, ChatResponse
from cogu.app._service._chat import ChatService
from cogu.app.deps import get_chat_service

chat_router = APIRouter(prefix="/api/chat", tags=["chat"])


@chat_router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
):
    result = await chat_service.run_chat(
        message=body.message,
        session_id=body.session_id,
        system_prompt=body.system_prompt,
        model=body.model,
        user_id=body.user_id,
    )
    return result


async def _sse_event_generator(chat_service: ChatService, body: ChatRequest):
    request_id = chat_service.create_request_id()
    async for event in chat_service.run_chat_stream(
        message=body.message,
        session_id=body.session_id,
        system_prompt=body.system_prompt,
        model=body.model,
        user_id=body.user_id,
    ):
        yield {
            "event": event.get("type", "message"),
            "data": json.dumps(event, ensure_ascii=False),
        }


@chat_router.post("/stream")
async def chat_stream(
    body: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
):
    return EventSourceResponse(_sse_event_generator(chat_service, body))


@chat_router.post("/cancel")
async def cancel_chat(
    body: dict,
    chat_service: ChatService = Depends(get_chat_service),
):
    request_id = body.get("request_id", "")
    if not request_id:
        return JSONResponse({"error": "request_id required"}, status_code=400)
    ok = chat_service.request_cancel(request_id)
    return {"request_id": request_id, "canceled": ok}


@chat_router.get("/status/{request_id}")
async def chat_status(
    request_id: str,
    chat_service: ChatService = Depends(get_chat_service),
):
    active = request_id in chat_service._cancel_events
    return {"request_id": request_id, "active": active}
