from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class IntegrationDomain(str, Enum):
    REASONING = "reasoning"
    GUI = "gui"
    OFFICE = "office"
    GENERAL = "general"


@dataclass
class IntegrationResult:
    content: str
    domain: IntegrationDomain
    success: bool = True
    error: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class SkillIntegrationHub:
    reasoner: Optional[Callable] = None
    gui_handler: Optional[Callable] = None
    office_handler: Optional[Callable] = None
    _routes: dict[str, Callable] = field(default_factory=dict)

    def route(self, skill_name: str, domain: IntegrationDomain):
        def decorator(func):
            self._routes[f"{domain.value}:{skill_name}"] = func
            return func
        return decorator

    async def dispatch(
        self,
        skill_name: str,
        domain: IntegrationDomain,
        input_data: dict,
        context: str = "",
    ) -> IntegrationResult:
        route_key = f"{domain.value}:{skill_name}"
        handler = self._routes.get(route_key)
        if handler:
            try:
                result = handler(input_data, context)
                if hasattr(result, "__await__"):
                    result = await result
                return IntegrationResult(
                    content=str(result) if not isinstance(result, IntegrationResult) else result.content,
                    domain=domain,
                )
            except Exception as e:
                return IntegrationResult(content="", domain=domain, success=False, error=str(e))

        if domain == IntegrationDomain.REASONING and self.reasoner:
            return await self._reason(skill_name, input_data, context)
        elif domain == IntegrationDomain.GUI and self.gui_handler:
            return await self._gui(skill_name, input_data, context)
        elif domain == IntegrationDomain.OFFICE and self.office_handler:
            return await self._office(skill_name, input_data, context)

        return IntegrationResult(
            content=f"no handler for {domain.value}:{skill_name}",
            domain=domain,
            success=False,
            error="no handler registered",
        )

    async def _reason(self, skill_name: str, input_data: dict, context: str) -> IntegrationResult:
        try:
            result = self.reasoner(
                task=skill_name,
                input=input_data,
                context=context,
            )
            if hasattr(result, "__await__"):
                result = await result
            return IntegrationResult(
                content=str(result) if not isinstance(result, dict) else result.get("content", str(result)),
                domain=IntegrationDomain.REASONING,
            )
        except Exception as e:
            return IntegrationResult(content="", domain=IntegrationDomain.REASONING, success=False, error=str(e))

    async def _gui(self, skill_name: str, input_data: dict, context: str) -> IntegrationResult:
        try:
            result = self.gui_handler(action=skill_name, params=input_data, context=context)
            if hasattr(result, "__await__"):
                result = await result
            return IntegrationResult(
                content=str(result),
                domain=IntegrationDomain.GUI,
            )
        except Exception as e:
            return IntegrationResult(content="", domain=IntegrationDomain.GUI, success=False, error=str(e))

    async def _office(self, skill_name: str, input_data: dict, context: str) -> IntegrationResult:
        try:
            result = self.office_handler(skill=skill_name, data=input_data, context=context)
            if hasattr(result, "__await__"):
                result = await result
            return IntegrationResult(
                content=str(result),
                domain=IntegrationDomain.OFFICE,
            )
        except Exception as e:
            return IntegrationResult(content="", domain=IntegrationDomain.OFFICE, success=False, error=str(e))

    def register_reasoner(self, reasoner: Callable):
        self.reasoner = reasoner

    def register_gui_handler(self, handler: Callable):
        self.gui_handler = handler

    def register_office_handler(self, handler: Callable):
        self.office_handler = handler
