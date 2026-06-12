from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class MusicianRole(str, Enum):
    PLANNER = "planner"
    CRITIC = "critic"
    RESEARCHER = "researcher"
    CODER = "coder"
    WRITER = "writer"
    ANALYST = "analyst"
    SUMMARIZER = "summarizer"


@dataclass
class MusicianResult:
    content: str
    role: MusicianRole
    success: bool = True
    error: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class Musician:
    name: str
    role: MusicianRole
    system_prompt: str = ""
    llm: Optional[Callable] = None
    tools: list = field(default_factory=list)
    max_retries: int = 2

    async def perform(self, task: str, context: str = "") -> MusicianResult:
        if not self.llm:
            return self._simulate(task, context)

        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        if context:
            messages.append({"role": "user", "content": f"Context:\n{context}\n\nTask: {task}"})
        else:
            messages.append({"role": "user", "content": task})

        for attempt in range(self.max_retries + 1):
            try:
                response = await self.llm(messages, tools=self.tools or None)
                content = response if isinstance(response, str) else response.get("content", str(response))
                return MusicianResult(content=content, role=self.role)
            except Exception as e:
                if attempt == self.max_retries:
                    return MusicianResult(content="", role=self.role, success=False, error=str(e))

        return MusicianResult(content="", role=self.role, success=False, error="max retries exceeded")

    def _simulate(self, task: str, context: str = "") -> MusicianResult:
        summary = task[:200] if task else "no task"
        if context:
            summary = f"[context: {context[:100]}] {summary}"
        return MusicianResult(
            content=f"[{self.role.value}] {summary}",
            role=self.role,
        )
