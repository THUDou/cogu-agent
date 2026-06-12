import asyncio
import json
import os
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class MemoryMessage:
    id: str = ""
    role: str = "user"
    content: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryMessage":
        return cls(
            id=data.get("id", uuid.uuid4().hex[:12]),
            role=data.get("role", "user"),
            content=data.get("content", ""),
            timestamp=data.get("timestamp", time.time()),
            metadata=data.get("metadata", {}),
        )


class MemoryStorage(ABC):
    @abstractmethod
    async def add(self, messages: list[MemoryMessage]) -> None: ...
    @abstractmethod
    async def get(self, message_id: str) -> Optional[MemoryMessage]: ...
    @abstractmethod
    async def get_all(self) -> list[MemoryMessage]: ...
    @abstractmethod
    async def remove(self, message_id: str) -> bool: ...
    @abstractmethod
    async def clear(self) -> None: ...
    @abstractmethod
    async def size(self) -> int: ...


class InMemoryStorage(MemoryStorage):
    def __init__(self):
        self._messages: dict[str, MemoryMessage] = {}

    async def add(self, messages: list[MemoryMessage]) -> None:
        for msg in messages:
            self._messages[msg.id] = msg

    async def get(self, message_id: str) -> Optional[MemoryMessage]:
        return self._messages.get(message_id)

    async def get_all(self) -> list[MemoryMessage]:
        return sorted(self._messages.values(), key=lambda m: m.timestamp)

    async def remove(self, message_id: str) -> bool:
        return self._messages.pop(message_id, None) is not None

    async def clear(self) -> None:
        self._messages.clear()

    async def size(self) -> int:
        return len(self._messages)


class FileStorage(MemoryStorage):
    def __init__(self, file_path: str):
        self._file_path = file_path

    async def add(self, messages: list[MemoryMessage]) -> None:
        existing = await self.get_all()
        existing_dict = {m.id: m for m in existing}
        for msg in messages:
            existing_dict[msg.id] = msg
        all_messages = sorted(existing_dict.values(), key=lambda m: m.timestamp)
        await self._save(all_messages)

    async def get(self, message_id: str) -> Optional[MemoryMessage]:
        all_msgs = await self.get_all()
        for msg in all_msgs:
            if msg.id == message_id:
                return msg
        return None

    async def get_all(self) -> list[MemoryMessage]:
        if not os.path.exists(self._file_path):
            return []
        with open(self._file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [MemoryMessage.from_dict(d) for d in data]

    async def remove(self, message_id: str) -> bool:
        all_msgs = await self.get_all()
        filtered = [m for m in all_msgs if m.id != message_id]
        if len(filtered) < len(all_msgs):
            await self._save(filtered)
            return True
        return False

    async def clear(self) -> None:
        await self._save([])

    async def size(self) -> int:
        return len(await self.get_all())

    async def _save(self, messages: list[MemoryMessage]) -> None:
        os.makedirs(os.path.dirname(self._file_path), exist_ok=True)
        with open(self._file_path, "w", encoding="utf-8") as f:
            json.dump([m.to_dict() for m in messages], f, ensure_ascii=False, indent=2)


class BaseCompressor(ABC):
    @abstractmethod
    async def compress(self, messages: list[MemoryMessage]) -> list[MemoryMessage]: ...


class SimpleCompressor(BaseCompressor):
    def __init__(self, max_output_messages: int = 5):
        self._max_output = max_output_messages

    async def compress(self, messages: list[MemoryMessage]) -> list[MemoryMessage]:
        if len(messages) <= self._max_output:
            return messages

        system_msgs = [m for m in messages if m.role == "system"]
        other_msgs = [m for m in messages if m.role != "system"]

        if len(other_msgs) <= self._max_output:
            return messages

        keep_recent = other_msgs[-self._max_output // 2:]
        older = other_msgs[: -self._max_output // 2]

        summary_parts = []
        for msg in older:
            summary_parts.append(f"[{msg.role}]: {msg.content[:100]}...")
        summary = "Summary of earlier conversation:\n" + "\n".join(summary_parts)

        compressed = [MemoryMessage(
            id=uuid.uuid4().hex[:12],
            role="system",
            content=summary,
            metadata={"compressed": True, "original_count": len(older)},
        )]

        return system_msgs + compressed + keep_recent


class TokenCounter:
    def __init__(self, chars_per_token: float = 4.0):
        self._chars_per_token = chars_per_token

    async def count(self, messages: list[MemoryMessage]) -> int:
        total_chars = sum(len(m.content) for m in messages)
        return int(total_chars / self._chars_per_token)


@dataclass
class GradeMemoryConfig:
    token_threshold: int = 65536
    auto_compress: bool = True
    compressor_model: str = ""


class ShortTermMemory:
    def __init__(self, storage: MemoryStorage = None):
        self._storage = storage or InMemoryStorage()

    async def add(self, messages) -> None:
        if isinstance(messages, MemoryMessage):
            messages = [messages]
        await self._storage.add(messages)

    async def get(self, message_id: str) -> Optional[MemoryMessage]:
        return await self._storage.get(message_id)

    async def get_memory(self) -> list[MemoryMessage]:
        return await self._storage.get_all()

    async def remove(self, message_id: str) -> bool:
        return await self._storage.remove(message_id)

    async def clear(self) -> None:
        await self._storage.clear()

    async def get_size(self) -> int:
        return await self._storage.size()


class MediumTermMemory:
    def __init__(self, storage: MemoryStorage = None, compressor: BaseCompressor = None):
        self._storage = storage or InMemoryStorage()
        self._compressor = compressor or SimpleCompressor()

    async def add(self, messages) -> None:
        if isinstance(messages, MemoryMessage):
            messages = [messages]
        await self._storage.add(messages)

    async def get(self, message_id: str) -> Optional[MemoryMessage]:
        return await self._storage.get(message_id)

    async def get_memory(self) -> list[MemoryMessage]:
        return await self._storage.get_all()

    async def remove(self, message_id: str) -> bool:
        return await self._storage.remove(message_id)

    async def clear(self) -> None:
        await self._storage.clear()

    async def get_size(self) -> int:
        return await self._storage.size()

    async def compress(self, messages: list[MemoryMessage]) -> list[MemoryMessage]:
        return await self._compressor.compress(messages)


class LongTermMemory:
    def __init__(self, storage: MemoryStorage = None):
        self._storage = storage or FileStorage(f"./ltm_{uuid.uuid4().hex[:8]}.json")

    async def add(self, messages) -> None:
        if isinstance(messages, MemoryMessage):
            messages = [messages]
        await self._storage.add(messages)

    async def get(self, message_id: str) -> Optional[MemoryMessage]:
        return await self._storage.get(message_id)

    async def get_memory(self) -> list[MemoryMessage]:
        return await self._storage.get_all()

    async def remove(self, message_id: str) -> bool:
        return await self._storage.remove(message_id)

    async def clear(self) -> None:
        await self._storage.clear()

    async def get_size(self) -> int:
        return await self._storage.size()


class GradeMemory:
    def __init__(
        self,
        stm: ShortTermMemory,
        mtm: MediumTermMemory,
        ltm: LongTermMemory,
        token_counter: TokenCounter,
        config: GradeMemoryConfig,
    ):
        self.stm = stm
        self.mtm = mtm
        self.ltm = ltm
        self.token_counter = token_counter
        self.config = config
        self._current_tokens: int = 0

    @classmethod
    def create_default(cls, ltm_path: str = "") -> "GradeMemory":
        stm = ShortTermMemory(InMemoryStorage())
        mtm = MediumTermMemory(InMemoryStorage(), SimpleCompressor())
        ltm_path = ltm_path or f"./ltm_{uuid.uuid4().hex[:8]}.json"
        ltm = LongTermMemory(FileStorage(ltm_path))
        return cls(
            stm=stm,
            mtm=mtm,
            ltm=ltm,
            token_counter=TokenCounter(),
            config=GradeMemoryConfig(),
        )

    async def add(self, messages) -> None:
        if messages is None:
            return

        await self.stm.add(messages)

        if not self.config.auto_compress:
            return

        if isinstance(messages, MemoryMessage):
            messages = [messages]

        await self._update_token_count(messages)

        if self._current_tokens > self.config.token_threshold:
            messages_to_compress = await self.mtm.get_memory() + await self.stm.get_memory()
            compressed = await self.mtm.compress(messages_to_compress)
            await self.clear()
            await self.mtm.add(compressed)
            await self._update_token_count(await self.get_memory())

    async def remove(self, message_id: str) -> bool:
        if not self.config.auto_compress:
            return (
                await self.stm.remove(message_id)
                or await self.mtm.remove(message_id)
                or await self.ltm.remove(message_id)
            )

        if msg := await self.stm.get(message_id):
            self._current_tokens -= await self.token_counter.count([msg])
            await self.stm.remove(message_id)
            return True
        if msg := await self.mtm.get(message_id):
            self._current_tokens -= await self.token_counter.count([msg])
            await self.mtm.remove(message_id)
            return True
        if msg := await self.ltm.get(message_id):
            self._current_tokens -= await self.token_counter.count([msg])
            await self.ltm.remove(message_id)
            return True
        return False

    async def get_memory(self) -> list[MemoryMessage]:
        relevant_ltm = await self.ltm.get_memory()
        relevant_mtm = await self.mtm.get_memory()
        current_stm = await self.stm.get_memory()

        final_context = []
        seen_ids = set()
        for msg in relevant_ltm + relevant_mtm + current_stm:
            if msg.id not in seen_ids:
                final_context.append(msg)
                seen_ids.add(msg.id)
        return final_context

    async def get_size(self) -> int:
        return await self.stm.get_size() + await self.mtm.get_size() + await self.ltm.get_size()

    async def commit_to_ltm(self, messages) -> None:
        if messages is None:
            return
        await self.ltm.add(messages)
        if not self.config.auto_compress:
            return
        if isinstance(messages, MemoryMessage):
            messages = [messages]
        await self._update_token_count(messages)

    async def clear(self) -> None:
        await self.stm.clear()
        await self.mtm.clear()
        self._current_tokens = 0

    async def _update_token_count(self, new_messages: list[MemoryMessage]) -> None:
        count = await self.token_counter.count(new_messages)
        self._current_tokens += count
