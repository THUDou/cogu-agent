from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Optional

from cogu.comm.backend import CommBackend, CommMessage, TransportType
from cogu.gateway.wire_protocol import WireMessage, WireEvent, wire_to_sse

logger = logging.getLogger(__name__)

SSE_KEEPALIVE_INTERVAL = 15.0


class HTTPConnection:
    def __init__(self, session_id: str, writer: asyncio.StreamWriter):
        self.session_id = session_id
        self.writer = writer
        self.created_at = time.time()
        self.last_active = time.time()

    @property
    def alive(self) -> bool:
        try:
            return not self.writer.is_closing()
        except Exception:
            return False


class HTTPBackend(CommBackend):
    def __init__(self, host: str = "127.0.0.1", port: int = 8080):
        super().__init__(name="http", transport_type=TransportType.HTTP)
        self.host = host
        self.port = port
        self._server: Optional[asyncio.Server] = None
        self._connections: dict[str, HTTPConnection] = {}
        self._lane_locks: dict[str, asyncio.Lock] = {}

    def _get_or_register(self, session_id: str, writer: asyncio.StreamWriter) -> HTTPConnection:
        if session_id not in self._connections:
            self._connections[session_id] = HTTPConnection(session_id, writer)
        conn = self._connections[session_id]
        conn.last_active = time.time()
        return conn

    def _remove_connection(self, session_id: str) -> None:
        self._connections.pop(session_id, None)
        self._lane_locks.pop(session_id, None)

    def _get_lane_lock(self, session_id: str) -> asyncio.Lock:
        if session_id not in self._lane_locks:
            self._lane_locks[session_id] = asyncio.Lock()
        return self._lane_locks[session_id]

    async def send(self, target: str, msg: WireMessage) -> None:
        conn = self._connections.get(target)
        if conn is None or not conn.alive:
            return
        try:
            conn.writer.write(wire_to_sse(msg).encode())
            await conn.writer.drain()
            conn.last_active = time.time()
        except Exception:
            logger.debug("HTTPBackend send to %s failed, removing connection", target)
            self._remove_connection(target)

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._handle_connection, self.host, self.port)
        self._running = True
        logger.info("HTTPBackend listening on %s:%s", self.host, self.port)

    async def stop(self) -> None:
        self._running = False
        for conn in list(self._connections.values()):
            try:
                conn.writer.close()
            except Exception:
                pass
        self._connections.clear()
        self._lane_locks.clear()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        logger.info("HTTPBackend stopped")

    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
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
            parts = first_line.split(" ", 2)
            if len(parts) < 2:
                writer.close()
                return
            method, path = parts[0], parts[1]

            headers: dict[str, str] = {}
            body_start = 0
            for i, line in enumerate(lines[1:], 1):
                if line == "":
                    body_start = i + 1
                    break
                if ":" in line:
                    key, val = line.split(":", 1)
                    headers[key.strip().lower()] = val.strip()

            body_str = "\r\n".join(lines[body_start:]) if body_start < len(lines) else ""
            body: dict = {}
            if body_str.strip():
                try:
                    body = json.loads(body_str)
                except json.JSONDecodeError:
                    pass

            await self._route(method, path, body, headers, writer)
        except asyncio.TimeoutError:
            pass
        except Exception:
            logger.exception("HTTPBackend connection error")
        finally:
            try:
                writer.close()
            except Exception:
                pass

    async def _route(self, method: str, path: str, body: dict, headers: dict, writer: asyncio.StreamWriter) -> None:
        user_id = body.get("user_id", "anonymous")
        session_id = body.get("session_id", f"http:{user_id}:{uuid.uuid4().hex[:8]}")

        if path == "/healthz":
            self._write_json(writer, 200, {"status": "ok"})
            await writer.drain()

        elif path == "/v1/gateway/messages" and method == "POST":
            request_id = body.get("request_id", uuid.uuid4().hex[:12])
            msg = CommMessage(
                payload=WireMessage(
                    method=WireEvent.TURN_BEGIN,
                    params={
                        "turn_id": request_id,
                        "session_id": session_id,
                        "user_message": body.get("text", body.get("message", "")),
                        "system_prompt": body.get("system_prompt", ""),
                    },
                ),
                transport=TransportType.HTTP,
                session_id=session_id,
                metadata={"request_id": request_id, "user_id": user_id},
            )
            await self._dispatch(msg)
            self._write_json(writer, 200, {"session_id": session_id, "request_id": request_id, "status": "accepted"})
            await writer.drain()

        elif path == "/v1/gateway/messages:stream" and method == "POST":
            self._get_or_register(session_id, writer)
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nCache-Control: no-cache\r\nConnection: keep-alive\r\n\r\n"
            )
            await writer.drain()

            request_id = body.get("request_id", uuid.uuid4().hex[:12])
            msg = CommMessage(
                payload=WireMessage(
                    method=WireEvent.TURN_BEGIN,
                    params={
                        "turn_id": request_id,
                        "session_id": session_id,
                        "user_message": body.get("text", body.get("message", "")),
                        "system_prompt": body.get("system_prompt", ""),
                    },
                ),
                transport=TransportType.HTTP,
                session_id=session_id,
                metadata={"request_id": request_id, "user_id": user_id, "stream": True},
            )
            await self._dispatch(msg)

            keepalive_task = asyncio.create_task(self._sse_keepalive(session_id))
            try:
                reader = None
                while self._running:
                    await asyncio.sleep(0.1)
                    if session_id not in self._connections:
                        break
            finally:
                keepalive_task.cancel()
                try:
                    await keepalive_task
                except asyncio.CancelledError:
                    pass
                self._remove_connection(session_id)
                await self._dispatch_disconnect(session_id)

        elif path == "/v1/gateway/status" and method == "GET":
            active_sessions = list(self._connections.keys())
            self._write_json(writer, 200, {"active_sessions": len(active_sessions), "sessions": active_sessions})
            await writer.drain()

        elif path == "/v1/gateway/sessions" and method == "GET":
            sessions = [{"session_id": sid, "last_active": c.last_active} for sid, c in self._connections.items()]
            self._write_json(writer, 200, {"sessions": sessions})
            await writer.drain()

        else:
            self._write_json(writer, 404, {"error": "not found"})
            await writer.drain()

    async def _sse_keepalive(self, session_id: str) -> None:
        while session_id in self._connections:
            await asyncio.sleep(SSE_KEEPALIVE_INTERVAL)
            conn = self._connections.get(session_id)
            if conn and conn.alive:
                try:
                    conn.writer.write(b": keepalive\n\n")
                    await conn.writer.drain()
                except Exception:
                    self._remove_connection(session_id)
                    break

    @staticmethod
    def _write_json(writer: asyncio.StreamWriter, status: int, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=False)
        payload = body.encode()
        writer.write(
            f"HTTP/1.1 {status} OK\r\nContent-Type: application/json\r\nContent-Length: {len(payload)}\r\n\r\n".encode()
            + payload
        )

    @staticmethod
    def _write_error(writer: asyncio.StreamWriter, status: int, message: str) -> None:
        HTTPBackend._write_json(writer, status, {"error": message})
