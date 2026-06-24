import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class OrchestrationMode(Enum):
    SEQUENTIAL = "sequential"
    HANDOFF = "handoff"
    BACKBONE = "backbone"
    MAKER_CHECKER = "maker_checker"


@dataclass
class OrchestrateNode:
    name: str = ""
    agent_fn: Callable = None
    description: str = ""
    is_backbone: bool = False
    handoff_destinations: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)


@dataclass
class OrchestrateResult:
    mode: OrchestrationMode = OrchestrationMode.SEQUENTIAL
    node_results: dict[str, Any] = field(default_factory=dict)
    execution_order: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)
    total_time: float = 0.0


class GraphOrchestrator:
    def __init__(self, mode: OrchestrationMode = OrchestrationMode.SEQUENTIAL):
        self.mode = mode
        self._nodes: dict[str, OrchestrateNode] = {}
        self._router: Optional[Callable] = None

    def add_node(self, node: OrchestrateNode):
        self._nodes[node.name] = node

    def set_router(self, router_fn: Callable):
        self._router = router_fn

    def build_dag(self) -> list[list[str]]:
        if self.mode == OrchestrationMode.SEQUENTIAL:
            return self._build_sequential_dag()
        elif self.mode == OrchestrationMode.HANDOFF:
            return self._build_handoff_dag()
        elif self.mode == OrchestrationMode.BACKBONE:
            return self._build_backbone_dag()
        return [[]]

    async def execute(self, initial_input: Any = None) -> OrchestrateResult:
        import time
        start = time.time()
        result = OrchestrateResult(mode=self.mode)
        layers = self.build_dag()
        current_input = initial_input
        for layer in layers:
            if len(layer) == 1:
                node_name = layer[0]
                node = self._nodes.get(node_name)
                if node and node.agent_fn:
                    try:
                        output = await self._execute_node(node, current_input)
                        result.node_results[node_name] = output
                        result.execution_order.append(node_name)
                        current_input = output
                    except Exception as e:
                        result.errors[node_name] = str(e)
            else:
                tasks = {}
                for node_name in layer:
                    node = self._nodes.get(node_name)
                    if node and node.agent_fn:
                        tasks[node_name] = self._execute_node(node, current_input)
                if tasks:
                    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
                    for name, res in zip(tasks.keys(), results):
                        if isinstance(res, Exception):
                            result.errors[name] = str(res)
                        else:
                            result.node_results[name] = res
                            result.execution_order.append(name)
                    merged = {}
                    for name, res in result.node_results.items():
                        if isinstance(res, dict):
                            merged.update(res)
                    current_input = merged if merged else current_input

        if self.mode == OrchestrationMode.HANDOFF and self._router:
            next_node = await self._router(current_input, list(self._nodes.keys()))
            if next_node and next_node in self._nodes:
                node = self._nodes[next_node]
                try:
                    output = await self._execute_node(node, current_input)
                    result.node_results[next_node] = output
                    result.execution_order.append(next_node)
                except Exception as e:
                    result.errors[next_node] = str(e)

        result.total_time = time.time() - start
        return result

    async def _execute_node(self, node: OrchestrateNode, input_data: Any) -> Any:
        if asyncio.iscoroutinefunction(node.agent_fn):
            return await node.agent_fn(input_data)
        return node.agent_fn(input_data)

    def _build_sequential_dag(self) -> list[list[str]]:
        visited = set()
        order = []
        for name in self._topological_sort():
            if name not in visited:
                order.append([name])
                visited.add(name)
        return order

    def _build_handoff_dag(self) -> list[list[str]]:
        sources = [n for n, node in self._nodes.items() if not node.dependencies]
        return [sources] if sources else [[]]

    def _build_backbone_dag(self) -> list[list[str]]:
        backbone = [n for n, node in self._nodes.items() if node.is_backbone]
        non_backbone = [n for n in self._nodes if n not in backbone]
        layers = []
        if backbone:
            layers.append(backbone)
        if non_backbone:
            layers.append(non_backbone)
        return layers if layers else [[]]

    def _topological_sort(self) -> list[str]:
        in_degree = {n: 0 for n in self._nodes}
        for node in self._nodes.values():
            for dep in node.dependencies:
                if dep in in_degree:
                    in_degree[node.name] += 1
        queue = [n for n, d in in_degree.items() if d == 0]
        order = []
        while queue:
            n = queue.pop(0)
            order.append(n)
            for node in self._nodes.values():
                if n in node.dependencies:
                    in_degree[node.name] -= 1
                    if in_degree[node.name] == 0:
                        queue.append(node.name)
        return order


class MakerCheckerVerdict(Enum):
    APPROVE = "approve"
    REJECT = "reject"
    ESCALATE_HUMAN = "escalate_human"


@dataclass
class MakerCheckerResult:
    verdict: MakerCheckerVerdict = MakerCheckerVerdict.REJECT
    maker_output: Any = None
    checker_output: Any = None
    evidence: dict = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    suggested_next_step: str = ""
    total_iterations: int = 0
    total_time: float = 0.0


class MakerCheckerOrchestrator:
    def __init__(
        self,
        maker_fn: Callable[[Any], Any],
        checker_fn: Callable[[Any, Any], MakerCheckerVerdict],
        max_checker_iterations: int = 3,
    ):
        self.maker_fn = maker_fn
        self.checker_fn = checker_fn
        self.max_checker_iterations = max_checker_iterations
        self._denylist_paths: list[str] = [
            ".env", "auth/", "payments/", "secrets/", "credentials/",
        ]

    def set_denylist(self, paths: list[str]) -> None:
        self._denylist_paths = paths

    async def execute(self, target: str, initial_context: Any = None) -> MakerCheckerResult:
        import time
        start = time.time()
        result = MakerCheckerResult()

        for iteration in range(1, self.max_checker_iterations + 1):
            result.total_iterations = iteration

            maker_output = await self._run_maker(target, initial_context, result.reasons)
            result.maker_output = maker_output

            checker_verdict, evidence, reasons = await self._run_checker(
                target, maker_output, initial_context
            )
            result.checker_output = {"verdict": checker_verdict.value, "evidence": evidence}
            result.evidence = evidence

            if checker_verdict == MakerCheckerVerdict.APPROVE:
                result.verdict = MakerCheckerVerdict.APPROVE
                break
            elif checker_verdict == MakerCheckerVerdict.ESCALATE_HUMAN:
                result.verdict = MakerCheckerVerdict.ESCALATE_HUMAN
                result.reasons = reasons
                break
            else:
                result.reasons = reasons
                result.verdict = MakerCheckerVerdict.REJECT
                if iteration >= self.max_checker_iterations:
                    result.suggested_next_step = (
                        f"Max checker iterations ({self.max_checker_iterations}) reached. "
                        "Human review required."
                    )
                    result.verdict = MakerCheckerVerdict.ESCALATE_HUMAN

        result.total_time = time.time() - start
        return result

    async def _run_maker(self, target: str, context: Any, previous_reasons: list[str]) -> Any:
        if asyncio.iscoroutinefunction(self.maker_fn):
            return await self.maker_fn(target, context, previous_reasons)
        return self.maker_fn(target, context, previous_reasons)

    async def _run_checker(
        self, target: str, maker_output: Any, context: Any
    ) -> tuple[MakerCheckerVerdict, dict, list[str]]:
        try:
            from cogu.loop.maker_checker import MakerChecker

            if asyncio.iscoroutinefunction(self.checker_fn):
                verdict, evidence, reasons = await self.checker_fn(target, maker_output, context)
            else:
                verdict, evidence, reasons = self.checker_fn(target, maker_output, context)

            mc_verdict = MakerCheckerVerdict(verdict.value) if hasattr(verdict, "value") else MakerCheckerVerdict.REJECT
            return mc_verdict, evidence, reasons
        except ImportError:
            if asyncio.iscoroutinefunction(self.checker_fn):
                output = await self.checker_fn(target, maker_output)
            else:
                output = self.checker_fn(target, maker_output)

            if isinstance(output, dict):
                verdict_str = output.get("verdict", "reject")
                evidence = output.get("evidence", {})
                reasons = output.get("reasons", [])
                try:
                    return MakerCheckerVerdict(verdict_str), evidence, reasons
                except ValueError:
                    return MakerCheckerVerdict.REJECT, evidence, reasons
            return MakerCheckerVerdict.REJECT, {}, ["Checker returned ambiguous result"]
