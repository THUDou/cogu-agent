from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from cogu.comm.backend import CommBackend, CommMessage, TransportType
from cogu.gateway.wire_protocol import WireMessage, WireEvent

logger = logging.getLogger(__name__)


class GRPCBackend(CommBackend):
    def __init__(self, host: str = "127.0.0.1", port: int = 50051):
        super().__init__(name="grpc", transport_type=TransportType.GRPC)
        self.host = host
        self.port = port
        self._server = None
        self._channels: dict[str, object] = {}

    async def send(self, target: str, msg: WireMessage) -> None:
        channel = self._channels.get(target)
        if channel is None:
            logger.debug("GRPCBackend no channel for target %s", target)
            return
        logger.debug("GRPCBackend send to %s: %s", target, msg.method)

    async def start(self) -> None:
        self._running = True
        logger.warning(
            "GRPCBackend is a stub. gRPC transport is not yet implemented. "
            "Install grpcio and compile protobuf definitions to enable."
        )

    async def stop(self) -> None:
        self._running = False
        self._channels.clear()
        logger.info("GRPCBackend stopped")
