from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Optional

from cogu.comm.backend import CommBackend, CommMessage, TransportType
from cogu.gateway.wire_protocol import WireMessage, WireEvent, parse_wire_line

logger = logging.getLogger(__name__)


class WebSocketBackend(CommBackend):
    def __init__(self, host: str = "127.0.0.1", port: int = 8081):
        super().__init__(name="websocket", transport_type=TransportType.WEBSOCKET)
        self.host = host
        self.port = port
        self._server: Optional[asyncio.Server] = None
        self._peers: dict[str, Any] = {}
        self._peer_metadata: dict[str, dict] = {}

    async def send(self, target: str, msg: WireMessage) -> None:
        ws = self._peers.get(target)
        if ws is None:
            return
        try:
            data = msg.to_json()
            await ws.send(data)
        except Exception:
            logger.debug("WebSocketBackend send to %s failed", target)
            await self._cleanup_peer(target)

    async def broadcast(self, msg: WireMessage, exclude: Optional[str] = None) -> None:
        dead: list[str] = []
        data = msg.to_json()
        for peer_id, ws in list(self._peers.items()):
            if peer_id == exclude:
                continue
            try:
                await ws.send(data)
            except Exception:
                dead.append(peer_id)
        for peer_id in dead:
            await self._cleanup_peer(peer_id)

    async def start(self) -> None:
        try:
            import websockets
        except ImportError:
            raise ImportError(
                "websockets package is required for WebSocketBackend. "
                "Install with: pip install cogu-agent[websocket]"
            )
        self._running = True
        self._server = await websockets.serve(
            self._handle_ws,
            self.host,
            self.port,
            ping_interval=20,
            ping_timeout=10,
            max_size=2**20,
        )
        logger.info("WebSocketBackend listening on ws://%s:%s", self.host, self.port)

    async def stop(self) -> None:
        self._running = False
        for writer in list(self._peers.values()):
            try:
                writer.close()
            except Exception:
                pass
        self._peers.clear()
        self._peer_metadata.clear()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        logger.info("WebSocketBackend stopped")

    async def _handle_ws(self, websocket, path: str = "") -> None:
        try:
            import websockets
        except ImportError:
            return

        peer_id = uuid.uuid4().hex[:12]
        self._peers[peer_id] = websocket
        self._peer_metadata[peer_id] = {"path": path, "connected_at": time.time()}
        logger.debug("WebSocket peer connected: %s", peer_id)

        try:
            async for message in websocket:
                if not self._running:
                    break
                try:
                    obj = json.loads(message) if isinstance(message, str) else json.loads(message.decode())
                except json.JSONDecodeError:
                    continue

                wire_msg = WireMessage(
                    method=obj.get("method", ""),
                    params=obj.get("params", {}),
                    id=obj.get("id"),
                    jsonrpc=obj.get("jsonrpc", "2.0"),
                )

                comm_msg = CommMessage(
                    payload=wire_msg,
                    transport=TransportType.WEBSOCKET,
                    session_id=obj.get("params", {}).get("session_id", peer_id),
                    raw=websocket,
                    metadata={"peer_id": peer_id, **self._peer_metadata.get(peer_id, {})},
                )
                await self._dispatch(comm_msg)
        except Exception:
            logger.debug("WebSocket peer %s disconnected", peer_id)
        finally:
            await self._cleanup_peer(peer_id)
            await self._dispatch_disconnect(peer_id)

    async def _cleanup_peer(self, peer_id: str) -> None:
        self._peers.pop(peer_id, None)
        self._peer_metadata.pop(peer_id, None)
