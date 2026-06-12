import asyncio
import json
import time
import uuid
from typing import Optional

from cogu.core.runner import Runner
from cogu.core.session import StreamFrame
from cogu.gateway.wire_protocol import WireMessage, WireEvent, wire_to_sse


class GatewaySession:
    def __init__(self, session_id: str, user_id: str):
        self.session_id = session_id
        self.user_id = user_id
        self.created_at = time.time()
        self.last_active = time.time()
        self.cancel_requested = False


class GatewayServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8080):
        self.host = host
        self.port = port
        self._sessions: dict[str, GatewaySession] = {}
        self._lane_locks: dict[str, asyncio.Lock] = {}
        self._cancel_tracker: set[str] = set()

    def _get_or_create_session(self, session_id: str, user_id: str) -> GatewaySession:
        if session_id not in self._sessions:
            self._sessions[session_id] = GatewaySession(session_id, user_id)
        s = self._sessions[session_id]
        s.last_active = time.time()
        return s

    def _get_lane_lock(self, session_id: str) -> asyncio.Lock:
        if session_id not in self._lane_locks:
            self._lane_locks[session_id] = asyncio.Lock()
        return self._lane_locks[session_id]

    def _build_sse(self, event_type: str, data: dict) -> str:
        payload = json.dumps(data, ensure_ascii=False)
        return f"event: {event_type}\ndata: {payload}\n\n"

    async def _handle_messages(self, body: dict) -> dict:
        user_id = body.get("user_id", "anonymous")
        text = body.get("text", body.get("message", ""))
        session_id = body.get("session_id", f"http:dm:{user_id}")
        request_id = body.get("request_id", uuid.uuid4().hex[:12])
        system_prompt = body.get("system_prompt", "")

        gw_session = self._get_or_create_session(session_id, user_id)
        lane = self._get_lane_lock(session_id)

        async with lane:
            if request_id in self._cancel_tracker:
                self._cancel_tracker.discard(request_id)
                return {"session_id": session_id, "request_id": request_id, "reply": "", "status": "canceled"}

            try:
                result = await Runner.run_agent(text, session=None, system_prompt=system_prompt)
                return {
                    "session_id": session_id,
                    "request_id": request_id,
                    "reply": result.content,
                    "thinking": getattr(result, "thinking", ""),
                    "usage": getattr(result, "usage", {}),
                    "iterations": getattr(result, "iteration", 0),
                    "elapsed_ms": getattr(result, "elapsed_ms", 0),
                }
            except Exception as e:
                return {
                    "session_id": session_id,
                    "request_id": request_id,
                    "reply": "",
                    "error": str(e),
                }

    async def _handle_messages_stream(self, body: dict, writer: asyncio.StreamWriter):
        user_id = body.get("user_id", "anonymous")
        text = body.get("text", body.get("message", ""))
        session_id = body.get("session_id", f"http:dm:{user_id}")
        request_id = body.get("request_id", uuid.uuid4().hex[:12])
        system_prompt = body.get("system_prompt", "")

        gw_session = self._get_or_create_session(session_id, user_id)
        lane = self._get_lane_lock(session_id)

        async with lane:
            writer.write(self._build_sse("run.started", {"type": "run.started", "session_id": session_id, "request_id": request_id}).encode())
            await writer.drain()

            if request_id in self._cancel_tracker:
                self._cancel_tracker.discard(request_id)
                writer.write(self._build_sse("run.canceled", {"type": "run.canceled", "session_id": session_id, "request_id": request_id}).encode())
                await writer.drain()
                return

            try:
                turn_id = uuid.uuid4().hex[:12]
                writer.write(wire_to_sse(
                    WireMessage(method=WireEvent.TURN_BEGIN, params={"turn_id": turn_id, "session_id": session_id, "user_message": text})
                ).encode())
                await writer.drain()

                async for frame in Runner.run_agent_streaming(text, session=None, system_prompt=system_prompt):
                    if request_id in self._cancel_tracker:
                        writer.write(wire_to_sse(
                            WireMessage(method=WireEvent.RUN_CANCELED, params={"request_id": request_id})
                        ).encode())
                        await writer.drain()
                        self._cancel_tracker.discard(request_id)
                        return

                    if frame.type == "text":
                        msg = WireMessage(method=WireEvent.CONTENT_PART, params={"type": "text", "content": frame.content, "turn_id": turn_id})
                    elif frame.type == "thinking":
                        msg = WireMessage(method=WireEvent.CONTENT_PART, params={"type": "thinking", "content": frame.content, "turn_id": turn_id})
                    elif frame.type == "tool_start":
                        msg = WireMessage(method=WireEvent.TOOL_CALL_START, params={"tool_name": frame.tool_name, "turn_id": turn_id, **frame.metadata})
                    elif frame.type == "tool_result":
                        msg = WireMessage(method=WireEvent.TOOL_RESULT, params={"tool_name": frame.tool_name, "content": frame.tool_result, "turn_id": turn_id})
                    else:
                        continue

                    writer.write(wire_to_sse(msg).encode())
                    await writer.drain()

                writer.write(wire_to_sse(
                    WireMessage(method=WireEvent.TURN_END, params={"turn_id": turn_id, "finish_reason": "stop"})
                ).encode())
                await writer.drain()
                writer.write(wire_to_sse(
                    WireMessage(method=WireEvent.RUN_COMPLETED, params={"session_id": session_id, "request_id": request_id})
                ).encode())
                await writer.drain()

            except Exception as e:
                writer.write(self._build_sse("run.error", {"type": "run.error", "error": str(e)}).encode())
                await writer.drain()

    async def _handle_request(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            raw = await asyncio.wait_for(reader.read(65536), timeout=30)
            if not raw:
                writer.close()
                return

            request_text = raw.decode("utf-8", errors="replace")
            lines = request_text.split("\r\n")
            if not lines:
                writer.close()
                return

            first_line = lines[0]
            method, path, _ = first_line.split(" ", 2)

            headers = {}
            body_start = 0
            for i, line in enumerate(lines[1:], 1):
                if line == "":
                    body_start = i + 1
                    break
                if ":" in line:
                    key, val = line.split(":", 1)
                    headers[key.strip().lower()] = val.strip()

            body_str = "\r\n".join(lines[body_start:]) if body_start < len(lines) else ""
            body = {}
            if body_str.strip():
                try:
                    body = json.loads(body_str)
                except json.JSONDecodeError:
                    pass

            if path == "/healthz":
                writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{\"status\":\"ok\"}")
                await writer.drain()

            elif path == "/v1/gateway/messages" and method == "POST":
                result = await self._handle_messages(body)
                resp = json.dumps(result, ensure_ascii=False)
                writer.write(f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(resp.encode())}\r\n\r\n{resp}".encode())
                await writer.drain()

            elif path == "/v1/gateway/messages:stream" and method == "POST":
                writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nCache-Control: no-cache\r\nConnection: keep-alive\r\n\r\n")
                await writer.drain()
                await self._handle_messages_stream(body, writer)

            elif path == "/v1/gateway/status" and method == "GET":
                request_id = body.get("request_id", "")
                active = request_id not in self._cancel_tracker
                result = {"request_id": request_id, "active": active}
                resp = json.dumps(result)
                writer.write(f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(resp.encode())}\r\n\r\n{resp}".encode())
                await writer.drain()

            elif path == "/v1/gateway/cancel" and method == "POST":
                request_id = body.get("request_id", "")
                self._cancel_tracker.add(request_id)
                result = {"request_id": request_id, "canceled": True}
                resp = json.dumps(result)
                writer.write(f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(resp.encode())}\r\n\r\n{resp}".encode())
                await writer.drain()

            elif path == "/v1/gateway/sessions" and method == "GET":
                sessions = [{"session_id": s.session_id, "user_id": s.user_id, "last_active": s.last_active} for s in self._sessions.values()]
                resp = json.dumps({"sessions": sessions}, ensure_ascii=False)
                writer.write(f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(resp.encode())}\r\n\r\n{resp}".encode())
                await writer.drain()

            else:
                writer.write(b"HTTP/1.1 404 Not Found\r\nContent-Type: application/json\r\n\r\n{\"error\":\"not found\"}")
                await writer.drain()

        except asyncio.TimeoutError:
            pass
        except Exception as e:
            try:
                writer.write(f"HTTP/1.1 500 Internal Server Error\r\nContent-Type: application/json\r\n\r\n{{\"error\":\"{str(e)}\"}}".encode())
                await writer.drain()
            except Exception:
                pass
        finally:
            try:
                writer.close()
            except Exception:
                pass

    async def start(self):
        self._server = await asyncio.start_server(self._handle_request, self.host, self.port)
        print(f"COGU Gateway running at http://{self.host}:{self.port}")
        print(f"  REST:   POST http://{self.host}:{self.port}/v1/gateway/messages")
        print(f"  SSE:    POST http://{self.host}:{self.port}/v1/gateway/messages:stream")
        print(f"  Status: GET  http://{self.host}:{self.port}/v1/gateway/status")
        print(f"  Cancel: POST http://{self.host}:{self.port}/v1/gateway/cancel")
        print(f"  Health: GET  http://{self.host}:{self.port}/healthz")

        async with self._server:
            await self._server.serve_forever()

    async def stop(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()


_GATEWAY: Optional[GatewayServer] = None


def get_gateway(host: str = "127.0.0.1", port: int = 8080) -> GatewayServer:
    global _GATEWAY
    if _GATEWAY is None:
        _GATEWAY = GatewayServer(host, port)
    return _GATEWAY
