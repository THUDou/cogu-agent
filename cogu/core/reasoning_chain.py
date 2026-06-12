import asyncio
import math
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Optional


class ChainStepType(str, Enum):
    INTRINSIC = "intrinsic"
    EXTRINSIC = "extrinsic"
    COMPOSITE = "composite"


class SearchAlgorithm(str, Enum):
    BFS = "bfs"
    DFS = "dfs"
    MCTS = "mcts"
    BEAM = "beam"


@dataclass
class ChainContext:
    memory: dict = field(default_factory=dict)
    observations: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    thoughts: list[str] = field(default_factory=list)
    step_count: int = 0
    max_steps: int = 0
    metadata: dict = field(default_factory=dict)

    def observe(self, text: str):
        self.observations.append(text)

    def act(self, action: str):
        self.actions.append(action)
        self.step_count += 1

    def think(self, thought: str):
        self.thoughts.append(thought)

    @property
    def trace(self) -> list[dict]:
        result = []
        for t, o, a in zip(self.thoughts, self.observations + [""], self.actions + [""]):
            result.append({"thought": t, "observation": o, "action": a})
        return result

    @property
    def exceeded(self) -> bool:
        return self.max_steps > 0 and self.step_count >= self.max_steps


class IntrinsicFunction(ABC):

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self._children: list["IntrinsicFunction"] = []
        self._parent: Optional["IntrinsicFunction"] = None

    @abstractmethod
    async def apply(self, ctx: ChainContext, **kwargs) -> str:
        ...

    def __rshift__(self, other: "IntrinsicFunction") -> "IntrinsicFunction":
        return CompositeIntrinsic(f"{self.name}→{other.name}", [self, other])

    def __or__(self, other: "IntrinsicFunction") -> "IntrinsicFunction":
        return ParallelIntrinsic(f"{self.name}∥{other.name}", [self, other])


class CompositeIntrinsic(IntrinsicFunction):

    def __init__(self, name: str, functions: list[IntrinsicFunction]):
        super().__init__(name, f"Composite of {len(functions)} functions")
        self._functions = functions

    async def apply(self, ctx: ChainContext, **kwargs) -> str:
        output = ""
        for fn in self._functions:
            try:
                output = await fn.apply(ctx, **kwargs)
                ctx.think(f"[{fn.name}] {output[:200]}")
            except Exception as e:
                output = f"Error in {fn.name}: {e}"
        return output


class ParallelIntrinsic(IntrinsicFunction):

    def __init__(self, name: str, functions: list[IntrinsicFunction]):
        super().__init__(name, f"Parallel of {len(functions)} functions")
        self._functions = functions

    async def apply(self, ctx: ChainContext, **kwargs) -> str:
        tasks = [fn.apply(ctx, **kwargs) for fn in self._functions]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        outputs = []
        for fn, r in zip(self._functions, results):
            if isinstance(r, Exception):
                outputs.append(f"[{fn.name}] Error: {r}")
            else:
                outputs.append(f"[{fn.name}] {str(r)[:200]}")
        return "\n".join(outputs)


class LLMThinkFn(IntrinsicFunction):

    def __init__(self, name: str, client: Any, prompt_template: str):
        super().__init__(name, "LLM-based reasoning step")
        self._client = client
        self._prompt = prompt_template

    async def apply(self, ctx: ChainContext, **kwargs) -> str:
        prompt = self._prompt.format(
            observations="\n".join(ctx.observations[-5:]),
            thoughts="\n".join(ctx.thoughts[-5:]),
            actions="\n".join(ctx.actions[-3:]),
            **ctx.memory,
            **kwargs,
        )
        try:
            response = await self._client.complete(prompt)
            return response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            return f"LLM error: {e}"


class LLMActFn(IntrinsicFunction):

    def __init__(self, name: str, client: Any, action_schema: dict = None):
        super().__init__(name, "LLM-based action selection")
        self._client = client
        self._action_schema = action_schema or {}

    async def apply(self, ctx: ChainContext, **kwargs) -> str:
        thought_summary = ctx.thoughts[-3:] if ctx.thoughts else ["no prior thoughts"]
        prompt = (
            "You must decide the next action.\n"
            f"Previous thoughts: {'; '.join(thought_summary)}\n"
            "Respond with ONLY the action name and arguments."
        )
        try:
            response = await self._client.complete(prompt)
            return response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            return f"Action error: {e}"


class ExtrinsicFunction:

    def __init__(self, name: str, executor: Callable[..., Coroutine]):
        self.name = name
        self._executor = executor

    async def execute(self, ctx: ChainContext, action: str, **kwargs) -> str:
        try:
            result = await self._executor(action, ctx, **kwargs)
            ctx.observe(str(result)[:1000])
            ctx.act(action)
            return str(result)
        except Exception as e:
            error_msg = f"Action failed: {e}"
            ctx.observe(error_msg)
            return error_msg


@dataclass
class SearchNode:
    state: ChainContext
    action: str = ""
    parent: Optional["SearchNode"] = None
    children: list["SearchNode"] = field(default_factory=list)
    visits: int = 0
    value: float = 0.0
    depth: int = 0
    is_terminal: bool = False

    @property
    def ucb_score(self, exploration: float = 1.414) -> float:
        if self.visits == 0 or self.parent is None or self.parent.visits == 0:
            return float("inf")
        exploitation = self.value / self.visits
        exploration_term = exploration * math.sqrt(
            math.log(self.parent.visits) / self.visits
        )
        return exploitation + exploration_term


class TreeSearchEngine:

    def __init__(self, intrinsic: IntrinsicFunction, extrinsic: ExtrinsicFunction,
                 value_fn: Callable[[ChainContext], float] = None,
                 max_depth: int = 10, max_iterations: int = 100):
        self._intrinsic = intrinsic
        self._extrinsic = extrinsic
        self._value_fn = value_fn or (lambda ctx: 0.0)
        self._max_depth = max_depth
        self._max_iterations = max_iterations

    async def search(self, root_ctx: ChainContext,
                     algorithm: SearchAlgorithm = SearchAlgorithm.MCTS,
                     beam_width: int = 3) -> tuple[list[str], float]:

        if algorithm == SearchAlgorithm.BFS:
            return await self._bfs(root_ctx)
        elif algorithm == SearchAlgorithm.DFS:
            return await self._dfs(root_ctx)
        elif algorithm == SearchAlgorithm.MCTS:
            return await self._mcts(root_ctx)
        elif algorithm == SearchAlgorithm.BEAM:
            return await self._beam_search(root_ctx, beam_width)
        return [], 0.0

    async def _bfs(self, ctx: ChainContext) -> tuple[list[str], float]:
        from collections import deque
        queue = deque([(ctx, [], 0.0)])
        best_actions = []
        best_value = -float("inf")

        while queue:
            current_ctx, actions, cumulative_value = queue.popleft()
            if current_ctx.exceeded or current_ctx.step_count >= self._max_depth:
                if cumulative_value > best_value:
                    best_value = cumulative_value
                    best_actions = actions
                continue

            thought = await self._intrinsic.apply(current_ctx)
            action = thought.strip()
            if not action:
                continue

            new_ctx = ChainContext(
                memory=dict(current_ctx.memory),
                max_steps=current_ctx.max_steps,
            )
            new_ctx.thoughts = list(current_ctx.thoughts)
            new_ctx.observations = list(current_ctx.observations)
            new_ctx.actions = list(current_ctx.actions)
            new_ctx.step_count = current_ctx.step_count

            result = await self._extrinsic.execute(new_ctx, action)
            step_value = self._value_fn(new_ctx)
            new_actions = actions + [action]
            new_cumulative = cumulative_value + step_value
            queue.append((new_ctx, new_actions, new_cumulative))

        return best_actions, best_value

    async def _dfs(self, ctx: ChainContext) -> tuple[list[str], float]:
        best_actions = []
        best_value = -float("inf")

        async def dfs(current_ctx: ChainContext, actions: list[str],
                      cumulative_value: float, depth: int):
            nonlocal best_actions, best_value

            if depth >= self._max_depth or current_ctx.exceeded:
                if cumulative_value > best_value:
                    best_value = cumulative_value
                    best_actions = list(actions)
                return

            thought = await self._intrinsic.apply(current_ctx)
            if not thought.strip():
                return

            new_ctx = ChainContext(
                memory=dict(current_ctx.memory),
                max_steps=current_ctx.max_steps,
            )
            new_ctx.thoughts = list(current_ctx.thoughts)
            new_ctx.observations = list(current_ctx.observations)
            new_ctx.actions = list(current_ctx.actions)
            new_ctx.step_count = current_ctx.step_count

            result = await self._extrinsic.execute(new_ctx, thought.strip())
            step_value = self._value_fn(new_ctx)
            await dfs(new_ctx, actions + [thought.strip()],
                     cumulative_value + step_value, depth + 1)

        await dfs(ctx, [], 0.0, 0)
        return best_actions, best_value

    async def _mcts(self, ctx: ChainContext) -> tuple[list[str], float]:
        root = SearchNode(state=ctx, depth=0)

        for iteration in range(self._max_iterations):
            node = self._select(root)
            if not node.is_terminal and node.depth < self._max_depth:
                expanded = await self._expand(node)
                if expanded:
                    node = expanded
            value = await self._simulate(node)
            self._backpropagate(node, value)

        if not root.children:
            return [], 0.0

        best_child = max(root.children, key=lambda c: c.value / max(c.visits, 1))
        actions = []
        node = best_child
        while node.parent and node.parent != root:
            actions.insert(0, node.action)
            node = node.parent
        actions.insert(0, best_child.action)
        return actions, best_child.value / max(best_child.visits, 1)

    def _select(self, node: SearchNode) -> SearchNode:
        while node.children and not node.is_terminal:
            if not all(c.visits > 0 for c in node.children):
                unvisited = [c for c in node.children if c.visits == 0]
                return unvisited[0]
            node = max(node.children, key=lambda c: c.ucb_score)
        return node

    async def _expand(self, node: SearchNode) -> Optional[SearchNode]:
        new_ctx = ChainContext(
            memory=dict(node.state.memory),
            max_steps=node.state.max_steps,
        )
        new_ctx.thoughts = list(node.state.thoughts)
        new_ctx.observations = list(node.state.observations)
        new_ctx.actions = list(node.state.actions)
        new_ctx.step_count = node.state.step_count

        thought = await self._intrinsic.apply(new_ctx)
        action = thought.strip()
        if not action:
            return None

        result = await self._extrinsic.execute(new_ctx, action)

        child = SearchNode(
            state=new_ctx,
            action=action,
            parent=node,
            depth=node.depth + 1,
            is_terminal=new_ctx.exceeded or new_ctx.step_count >= self._max_depth,
        )
        node.children.append(child)
        return child

    async def _simulate(self, node: SearchNode) -> float:
        sim_ctx = ChainContext(
            memory=dict(node.state.memory),
            max_steps=min(3, self._max_depth - node.depth),
        )
        sim_ctx.thoughts = list(node.state.thoughts)
        sim_ctx.observations = list(node.state.observations)
        sim_ctx.actions = list(node.state.actions)
        sim_ctx.step_count = node.state.step_count

        for _ in range(3):
            if sim_ctx.exceeded:
                break
            thought = await self._intrinsic.apply(sim_ctx)
            if thought.strip():
                await self._extrinsic.execute(sim_ctx, thought.strip())

        return self._value_fn(sim_ctx)

    def _backpropagate(self, node: SearchNode, value: float):
        current = node
        while current is not None:
            current.visits += 1
            current.value += value
            current = current.parent

    async def _beam_search(self, ctx: ChainContext,
                           beam_width: int = 3) -> tuple[list[str], float]:
        beams: list[tuple[ChainContext, list[str], float]] = [(ctx, [], 0.0)]
        best_actions = []
        best_value = -float("inf")

        for _ in range(self._max_depth):
            candidates = []
            for current_ctx, actions, cumulative_value in beams:
                if current_ctx.exceeded:
                    if cumulative_value > best_value:
                        best_value = cumulative_value
                        best_actions = actions
                    continue

                thought = await self._intrinsic.apply(current_ctx)
                if not thought.strip():
                    continue

                new_ctx = ChainContext(
                    memory=dict(current_ctx.memory),
                    max_steps=current_ctx.max_steps,
                )
                new_ctx.thoughts = list(current_ctx.thoughts)
                new_ctx.observations = list(current_ctx.observations)
                new_ctx.actions = list(current_ctx.actions)
                new_ctx.step_count = current_ctx.step_count

                result = await self._extrinsic.execute(new_ctx, thought.strip())
                step_value = self._value_fn(new_ctx)
                candidates.append(
                    (new_ctx, actions + [thought.strip()],
                     cumulative_value + step_value)
                )

            if not candidates:
                break

            candidates.sort(key=lambda x: x[2], reverse=True)
            beams = candidates[:beam_width]

        if beams:
            final = beams[0]
            return final[1], final[2]
        return best_actions, best_value


class ReasoningChain:

    def __init__(self, name: str = "default"):
        self.name = name
        self._intrinsic_fns: list[IntrinsicFunction] = []
        self._extrinsic_fn: Optional[ExtrinsicFunction] = None

    def add_intrinsic(self, fn: IntrinsicFunction) -> "ReasoningChain":
        self._intrinsic_fns.append(fn)
        return self

    def set_extrinsic(self, fn: ExtrinsicFunction) -> "ReasoningChain":
        self._extrinsic_fn = fn
        return self

    async def reason(self, ctx: ChainContext, **kwargs) -> tuple[str, ChainContext]:
        thought_output = ""
        for fn in self._intrinsic_fns:
            thought_output = await fn.apply(ctx, **kwargs)
            ctx.think(f"[{fn.name}] {thought_output[:200]}")

        if self._extrinsic_fn and thought_output.strip():
            await self._extrinsic_fn.execute(ctx, thought_output.strip())

        return thought_output, ctx

    async def reason_loop(self, ctx: ChainContext, max_loops: int = 10,
                          **kwargs) -> tuple[list[str], ChainContext]:
        all_actions = []
        for _ in range(max_loops):
            if ctx.exceeded:
                break
            thought, ctx = await self.reason(ctx, **kwargs)
            if ctx.actions:
                all_actions.append(ctx.actions[-1])
            if not thought.strip():
                break
        return all_actions, ctx

    def intrinsic_count(self) -> int:
        return len(self._intrinsic_fns)


class SwiftSageReasoning(ReasoningChain):

    def __init__(self, planner_client: Any, executor_client: Any,
                 extrinsic: ExtrinsicFunction):
        super().__init__("SwiftSage")
        self.add_intrinsic(LLMThinkFn(
            "plan", planner_client,
            "Plan the steps to solve: {task}\n"
            "Context: {observations}\n"
            "Output ONLY a numbered list of steps.",
        ))
        self.add_intrinsic(LLMThinkFn(
            "evaluate", planner_client,
            "Evaluate the plan against: {task}\n"
            "Observations: {observations}\n"
            "Revise if needed.",
        ))
        self.add_intrinsic(LLMActFn("execute", executor_client))
        self.set_extrinsic(extrinsic)


class ReactReasoning(ReasoningChain):

    def __init__(self, client: Any, extrinsic: ExtrinsicFunction):
        super().__init__("ReAct")
        self.add_intrinsic(LLMThinkFn(
            "thought", client,
            "Think step by step about: {observations}\n"
            "What should you do next?",
        ))
        self.add_intrinsic(LLMActFn("action", client))
        self.set_extrinsic(extrinsic)


class ReflectReasoning(ReasoningChain):

    def __init__(self, client: Any, extrinsic: ExtrinsicFunction):
        super().__init__("Reflect")
        self.add_intrinsic(LLMThinkFn(
            "reflect", client,
            "Previous actions: {actions}\n"
            "Observations: {observations}\n"
            "What went wrong? What should change?",
        ))
        self.add_intrinsic(LLMThinkFn(
            "revise", client,
            "Based on reflection, decide next action.",
        ))
        self.add_intrinsic(LLMActFn("action", client))
        self.set_extrinsic(extrinsic)
