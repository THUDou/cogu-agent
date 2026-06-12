from __future__ import annotations

import asyncio
import logging
from typing import Optional

from cogu.comm.backend import CommBackend, CommMessage, TransportType
from cogu.gateway.wire_protocol import WireMessage

logger = logging.getLogger(__name__)

HEALTH_CHECK_INTERVAL = 30.0


class CommManager:
    def __init__(self):
        self._backends: dict[str, CommBackend] = {}
        self._running = False
        self._health_task: Optional[asyncio.Task] = None

    def register(self, backend: CommBackend) -> None:
        if backend.name in self._backends:
            logger.warning("CommManager replacing existing backend %s", backend.name)
        self._backends[backend.name] = backend
        backend.on_message(self._on_any_message)
        logger.debug("CommManager registered backend %s (%s)", backend.name, backend.transport_type)

    def unregister(self, name: str) -> Optional[CommBackend]:
        return self._backends.pop(name, None)

    def get(self, name: str) -> Optional[CommBackend]:
        return self._backends.get(name)

    def list_transports(self) -> list[str]:
        return list(self._backends.keys())

    def list_active(self) -> list[str]:
        return [name for name, b in self._backends.items() if b.running]

    async def start_all(self) -> None:
        self._running = True
        tasks = []
        for backend in self._backends.values():
            tasks.append(asyncio.create_task(backend.start(), name=f"comm-{backend.name}"))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for name, result in zip(self._backends.keys(), results):
            if isinstance(result, Exception):
                logger.error("CommManager failed to start backend %s: %s", name, result)
        self._health_task = asyncio.create_task(self._health_loop())
        logger.info("CommManager started %d/%d backends", self.list_active(), len(self._backends))

    async def stop_all(self) -> None:
        self._running = False
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
        tasks = []
        for backend in self._backends.values():
            tasks.append(asyncio.create_task(backend.stop(), name=f"comm-stop-{backend.name}"))
        await asyncio.gather(*tasks, return_exceptions=True)
        self._backends.clear()
        logger.info("CommManager stopped all backends")

    async def send(self, backend_name: str, target: str, msg: WireMessage) -> bool:
        backend = self._backends.get(backend_name)
        if backend is None or not backend.running:
            logger.debug("CommManager send: backend %s unavailable", backend_name)
            return False
        try:
            await backend.send(target, msg)
            return True
        except Exception:
            logger.exception("CommManager send failed via %s", backend_name)
            return False

    async def broadcast(self, msg: WireMessage, exclude: Optional[str] = None) -> int:
        sent = 0
        for name, backend in self._backends.items():
            if name == exclude or not backend.running:
                continue
            try:
                await backend.send("", msg)
                sent += 1
            except Exception:
                pass
        return sent

    async def _on_any_message(self, msg: CommMessage) -> None:
        logger.debug(
            "CommManager received message via %s: method=%s session=%s",
            msg.transport.value,
            msg.payload.method,
            msg.session_id,
        )

    async def _health_loop(self) -> None:
        while self._running:
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            for name, backend in list(self._backends.items()):
                if not backend.running:
                    logger.warning("CommManager health: backend %s is not running", name)

    @property
    def running(self) -> bool:
        return self._running

    @property
    def backend_count(self) -> int:
        return len(self._backends)

    def __repr__(self) -> str:
        transports = ", ".join(self.list_transports()) or "none"
        return f"<CommManager transports=[{transports}] active={len(self.list_active())}>"
