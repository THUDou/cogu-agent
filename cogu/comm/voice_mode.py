from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class VoiceConfig:
    stt_provider: str = "whisper"
    tts_provider: str = "edge-tts"
    language: str = "zh-CN"
    sample_rate: int = 16000
    enabled: bool = False


class VoiceMode:

    def __init__(self, config: VoiceConfig | None = None):
        self.config = config or VoiceConfig()
        self._stt_handler: Optional[Callable] = None
        self._tts_handler: Optional[Callable] = None

    def set_stt_handler(self, handler: Callable) -> None:
        self._stt_handler = handler

    def set_tts_handler(self, handler: Callable) -> None:
        self._tts_handler = handler

    async def speech_to_text(self, audio_data: bytes) -> str:
        if self._stt_handler:
            if hasattr(self._stt_handler, '__call__'):
                import asyncio
                if asyncio.iscoroutinefunction(self._stt_handler):
                    return await self._stt_handler(audio_data)
                return self._stt_handler(audio_data)
        return ""

    async def text_to_speech(self, text: str) -> bytes:
        if self._tts_handler:
            import asyncio
            if asyncio.iscoroutinefunction(self._tts_handler):
                return await self._tts_handler(text)
            return self._tts_handler(text)
        return b""

    @property
    def is_available(self) -> bool:
        return self.config.enabled and (self._stt_handler is not None or self._tts_handler is not None)


__all__ = ["VoiceMode", "VoiceConfig"]
