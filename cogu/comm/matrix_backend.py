from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable, Optional

from cogu.comm.backend import CommBackend, CommMessage, TransportType
from cogu.gateway.wire_protocol import WireMessage, WireEvent

logger = logging.getLogger(__name__)

MATRIX_SYNC_TIMEOUT_MS = 30000


class MatrixBackend(CommBackend):
    def __init__(
        self,
        homeserver_url: str,
        user_id: str,
        access_token: str,
        room_ids: Optional[list[str]] = None,
    ):
        super().__init__(name="matrix", transport_type=TransportType.MATRIX)
        self.homeserver_url = homeserver_url
        self.user_id = user_id
        self.access_token = access_token
        self.room_ids = room_ids or []
        self._client = None
        self._sync_task: Optional[asyncio.Task] = None
        self._txn_id_counter = 0

    async def send(self, target: str, msg: WireMessage) -> None:
        if self._client is None:
            return
        try:
            from nio import RoomSendResponse
        except ImportError:
            raise ImportError(
                "matrix-nio package is required for MatrixBackend. "
                "Install with: pip install cogu-agent[matrix]"
            )
        body = msg.params.get("content", msg.to_json())
        self._txn_id_counter += 1
        txn_id = f"cogu_{int(time.time())}_{self._txn_id_counter}"
        await self._client.room_send(
            room_id=target,
            message_type="m.room.message",
            content={"msgtype": "m.text", "body": body},
            tx_id=txn_id,
        )

    async def start(self) -> None:
        try:
            from nio import AsyncClient, AsyncClientConfig
        except ImportError:
            raise ImportError(
                "matrix-nio package is required for MatrixBackend. "
                "Install with: pip install cogu-agent[matrix]"
            )

        config = AsyncClientConfig(store_sync_tokens=True)
        self._client = AsyncClient(
            homeserver=self.homeserver_url,
            user=self.user_id,
            config=config,
        )
        self._client.access_token = self.access_token

        resp = await self._client.login("")
        if hasattr(resp, "access_token"):
            self.access_token = resp.access_token
            self._client.access_token = resp.access_token

        for room_id in self.room_ids:
            try:
                await self._client.join(room_id)
            except Exception:
                logger.debug("MatrixBackend could not join room %s", room_id)

        self._running = True
        self._sync_task = asyncio.create_task(self._sync_loop())
        logger.info("MatrixBackend connected to %s as %s", self.homeserver_url, self.user_id)

    async def stop(self) -> None:
        self._running = False
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
        if self._client:
            try:
                await self._client.close()
            except Exception:
                pass
            self._client = None
        logger.info("MatrixBackend stopped")

    async def _sync_loop(self) -> None:
        since_token: Optional[str] = None
        while self._running and self._client:
            try:
                from nio import SyncResponse
            except ImportError:
                break

            try:
                sync_resp = await self._client.sync(timeout=MATRIX_SYNC_TIMEOUT_MS, since=since_token)
                if isinstance(sync_resp, SyncResponse):
                    since_token = sync_resp.next_batch
                    await self._handle_sync_events(sync_resp)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("MatrixBackend sync error")
                await asyncio.sleep(5)

    async def _handle_sync_events(self, sync_resp) -> None:
        try:
            from nio import RoomMessageText
        except ImportError:
            return

        for room_id, room_info in sync_resp.rooms.join.items():
            for event in room_info.timeline.events:
                if not isinstance(event, RoomMessageText):
                    continue
                if event.sender == self.user_id:
                    continue

                wire_msg = WireMessage(
                    method=WireEvent.TURN_BEGIN,
                    params={
                        "turn_id": event.event_id,
                        "session_id": f"matrix:{room_id}",
                        "user_message": event.body,
                        "room_id": room_id,
                        "sender": event.sender,
                    },
                )

                comm_msg = CommMessage(
                    payload=wire_msg,
                    transport=TransportType.MATRIX,
                    session_id=f"matrix:{room_id}",
                    metadata={"room_id": room_id, "sender": event.sender, "event_id": event.event_id},
                )
                await self._dispatch(comm_msg)
