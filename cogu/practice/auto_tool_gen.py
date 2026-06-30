from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolSpec:
    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    implementation_notes: str = ""
    confidence: float = 0.0
    source: str = "generated"


@dataclass
class ToolGenResult:
    tools: list[ToolSpec] = field(default_factory=list)
    success_count: int = 0
    total_count: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.total_count == 0:
            return 0.0
        return self.success_count / self.total_count


class ToolSpecSynthesizer:

    def __init__(self, llm_client: Any = None):
        self.llm = llm_client

    async def synthesize(self, description: str, context: str = "") -> ToolSpec:
        if self.llm:
            try:
                import asyncio
                prompt = (
                    f"Generate a tool specification from this description:\n{description}\n"
                    f"Context: {context}\n\n"
                    "Return JSON: {\"name\": \"...\", \"description\": \"...\", \"parameters\": {...}}"
                )
                if asyncio.iscoroutinefunction(self.llm.complete):
                    response = await self.llm.complete(prompt)
                else:
                    response = self.llm.complete(prompt)
                data = json.loads(response)
                return ToolSpec(
                    name=data.get("name", "generated_tool"),
                    description=data.get("description", description),
                    parameters=data.get("parameters", {}),
                    confidence=0.8,
                )
            except Exception:
                pass

        name = re.sub(r'[^a-z0-9_]', '_', description.lower().replace(' ', '_'))[:30]
        return ToolSpec(
            name=name,
            description=description,
            parameters={"type": "object", "properties": {}},
            confidence=0.3,
        )

    async def synthesize_batch(self, descriptions: list[str]) -> list[ToolSpec]:
        results = []
        for desc in descriptions:
            results.append(await self.synthesize(desc))
        return results


class ToolVerifier:

    def __init__(self):
        self._verified: dict[str, bool] = {}

    async def verify(self, tool_spec: ToolSpec, executor: Any = None) -> bool:
        if not tool_spec.name:
            return False

        if executor:
            try:
                import asyncio
                if asyncio.iscoroutinefunction(executor):
                    await executor(tool_spec.name, tool_spec.parameters)
                else:
                    executor(tool_spec.name, tool_spec.parameters)
                self._verified[tool_spec.name] = True
                return True
            except Exception:
                self._verified[tool_spec.name] = False
                return False

        self._verified[tool_spec.name] = True
        return True

    def get_verification_stats(self) -> dict[str, Any]:
        verified = sum(1 for v in self._verified.values() if v)
        return {
            "total": len(self._verified),
            "verified": verified,
            "success_rate": verified / max(len(self._verified), 1),
        }


class AutoToolGenerator:

    def __init__(self, llm_client: Any = None):
        self.synthesizer = ToolSpecSynthesizer(llm_client)
        self.verifier = ToolVerifier()
        self._generated_tools: list[ToolSpec] = []

    async def generate(self, descriptions: list[str], verify: bool = True) -> ToolGenResult:
        result = ToolGenResult()
        specs = await self.synthesizer.synthesize_batch(descriptions)

        for spec in specs:
            result.total_count += 1
            if verify:
                passed = await self.verifier.verify(spec)
                if passed:
                    result.success_count += 1
                    self._generated_tools.append(spec)
                else:
                    result.errors.append(f"Verification failed: {spec.name}")
            else:
                result.success_count += 1
                self._generated_tools.append(spec)
            result.tools.append(spec)

        return result

    def get_generated_tools(self) -> list[ToolSpec]:
        return list(self._generated_tools)

    def export_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": t.name, "description": t.description, "parameters": t.parameters}
            for t in self._generated_tools
        ]
