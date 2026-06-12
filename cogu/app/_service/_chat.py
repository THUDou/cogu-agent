from __future__ import annotations

import asyncio
import time
import uuid
from typing import Optional

from cogu.core.runner import Runner
from cogu.core.session import Session, StreamFrame


class ChatService:
    def __init__(self):
        self._cancel_events: dict[str, asyncio.Event] = {}
        self._run_tasks: dict[str, asyncio.Task] = {}

    def create_request_id(self) -> str:
        return uuid.uuid4().hex[:12]

    async def run_chat(
        self,
        message: str,
        session_id: str = "",
        system_prompt: str = "",
        model: str = "",
        user_id: str = "anonymous",
    ) -> dict:
        request_id = self.create_request_id()
        effective_sid = session_id or f"http:{user_id}:{request_id}"

        cancel_event = asyncio.Event()
        self._cancel_events[request_id] = cancel_event

        try:
            t0 = time.monotonic()
            task = asyncio.create_task(
                Runner.run_agent(
                    user_message=message,
                    session=None,
                    model=model,
                    system_prompt=system_prompt,
                )
            )
            self._run_tasks[request_id] = task

            done, pending = await asyncio.wait(
                [task, asyncio.ensure_future(cancel_event.wait())],
                return_when=asyncio.FIRST_COMPLETED,
            )

            if cancel_event.is_set():
                for p in pending:
                    p.cancel()
                return {
                    "session_id": effective_sid,
                    "request_id": request_id,
                    "status": "canceled",
                }

            result = task.result()
            elapsed_ms = (time.monotonic() - t0) * 1000
            return {
                "session_id": effective_sid,
                "request_id": request_id,
                "status": "completed",
                "reply": result.content,
                "thinking": getattr(result, "thinking", ""),
                "iterations": getattr(result, "iteration", 0),
                "elapsed_ms": elapsed_ms,
            }
        except Exception as e:
            return {
                "session_id": effective_sid,
                "request_id": request_id,
                "status": "error",
                "error": str(e),
            }
        finally:
            self._cancel_events.pop(request_id, None)
            self._run_tasks.pop(request_id, None)

    async def run_chat_stream(
        self,
        message: str,
        session_id: str = "",
        system_prompt: str = "",
        model: str = "",
        user_id: str = "anonymous",
    ):
        request_id = self.create_request_id()
        effective_sid = session_id or f"http:{user_id}:{request_id}"

        cancel_event = asyncio.Event()
        self._cancel_events[request_id] = cancel_event

        yield {"type": "run.started", "session_id": effective_sid, "request_id": request_id}

        try:
            turn_id = uuid.uuid4().hex[:12]
            yield {"type": "turn.begin", "turn_id": turn_id, "session_id": effective_sid}

            stream_task = asyncio.create_task(self._collect_stream(
                message, system_prompt, model
            ))
            self._run_tasks[request_id] = stream_task

            async for frame, done_flag in self._stream_with_cancel(stream_task, cancel_event):
                if done_flag:
                    yield {"type": "run.canceled", "request_id": request_id}
                    return

                event = self._frame_to_event(frame, turn_id)
                if event:
                    yield event

            yield {"type": "turn.end", "turn_id": turn_id, "finish_reason": "stop"}
            yield {"type": "run.completed", "session_id": effective_sid, "request_id": request_id}
        except Exception as e:
            yield {"type": "run.error", "error": str(e)}
        finally:
            self._cancel_events.pop(request_id, None)
            self._run_tasks.pop(request_id, None)

    async def _collect_stream(self, message: str, system_prompt: str, model: str) -> list[StreamFrame]:
        frames = []
        async for frame in Runner.run_agent_streaming(
            user_message=message,
            session=None,
            model=model,
            system_prompt=system_prompt,
        ):
            frames.append(frame)
        return frames

    async def _stream_with_cancel(self, task: asyncio.Task, cancel_event: asyncio.Event):
        frames = await task
        for frame in frames:
            if cancel_event.is_set():
                yield frame, True
                return
            yield frame, False

    def _frame_to_event(self, frame: StreamFrame, turn_id: str) -> Optional[dict]:
        if frame.type == "text":
            return {"type": "text.delta", "content": frame.content, "turn_id": turn_id}
        elif frame.type == "thinking":
            return {"type": "thinking.delta", "content": frame.content, "turn_id": turn_id}
        elif frame.type == "tool_start":
            return {
                "type": "tool.start",
                "tool_name": frame.tool_name,
                "tool_args": frame.tool_args,
                "turn_id": turn_id,
            }
        elif frame.type == "tool_result":
            return {
                "type": "tool.result",
                "tool_name": frame.tool_name,
                "content": frame.tool_result,
                "turn_id": turn_id,
            }
        return None

    def request_cancel(self, request_id: str) -> bool:
        event = self._cancel_events.get(request_id)
        if event:
            event.set()
            return True
        return False
