import json
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AtomTool:
    name: str = ""
    description: str = ""
    parameters: dict = field(default_factory=dict)
    implementation: str = ""
    source_tool: str = ""


@dataclass
class EvolutionResult:
    original_tools: list[str] = field(default_factory=list)
    atoms: list[AtomTool] = field(default_factory=list)
    compositions: list[dict] = field(default_factory=list)
    iterations: int = 0


class AtomToolEvolver:
    def __init__(self, llm_client=None):
        self.llm = llm_client

    async def decompose(self, tool_name: str, tool_description: str, tool_code: str) -> list[AtomTool]:
        if self.llm:
            return await self._llm_decompose(tool_name, tool_description, tool_code)
        return self._rule_decompose(tool_name, tool_description)

    async def compose(self, atoms: list[AtomTool], goal: str) -> list[dict]:
        if self.llm:
            return await self._llm_compose(atoms, goal)
        return self._rule_compose(atoms, goal)

    async def evolve(self, tools: list[dict], goal: str, iterations: int = 3) -> EvolutionResult:
        result = EvolutionResult(original_tools=[t.get("name", "") for t in tools])
        all_atoms = []
        for tool in tools:
            atoms = await self.decompose(
                tool.get("name", ""),
                tool.get("description", ""),
                tool.get("code", ""),
            )
            all_atoms.extend(atoms)
        result.atoms = all_atoms

        for i in range(iterations):
            compositions = await self.compose(all_atoms, goal)
            result.compositions.extend(compositions)
        result.iterations = iterations
        return result

    async def _llm_decompose(self, name: str, desc: str, code: str) -> list[AtomTool]:
        prompt = (
            f"Decompose this tool into atomic operations.\n\n"
            f"Tool: {name}\nDescription: {desc}\nCode:\n{code[:2000]}\n\n"
            f"Return a JSON array of atomic tools, each with name, description, parameters."
        )
        try:
            response = self.llm.complete(prompt)
            atoms_data = json.loads(response)
            return [
                AtomTool(
                    name=a.get("name", ""),
                    description=a.get("description", ""),
                    parameters=a.get("parameters", {}),
                    source_tool=name,
                )
                for a in atoms_data
            ]
        except Exception:
            return self._rule_decompose(name, desc)

    def _rule_decompose(self, name: str, desc: str) -> list[AtomTool]:
        parts = desc.split('.')
        atoms = []
        for i, part in enumerate(parts):
            part = part.strip()
            if part:
                atoms.append(AtomTool(
                    name=f"{name}_step_{i+1}",
                    description=part,
                    source_tool=name,
                ))
        return atoms if atoms else [AtomTool(name=f"{name}_core", description=desc, source_tool=name)]

    async def _llm_compose(self, atoms: list[AtomTool], goal: str) -> list[dict]:
        atom_list = "\n".join(f"- {a.name}: {a.description}" for a in atoms)
        prompt = (
            f"Given these atomic tools:\n{atom_list}\n\n"
            f"Goal: {goal}\n\n"
            f"Compose a sequence of atoms to achieve the goal. "
            f"Return a JSON array of {atom_name} sequences."
        )
        try:
            response = self.llm.complete(prompt)
            return json.loads(response)
        except Exception:
            return self._rule_compose(atoms, goal)

    def _rule_compose(self, atoms: list[AtomTool], goal: str) -> list[dict]:
        goal_words = set(goal.lower().split())
        scored = []
        for atom in atoms:
            desc_words = set(atom.description.lower().split())
            overlap = len(goal_words & desc_words)
            scored.append((overlap, atom))
        scored.sort(key=lambda x: -x[0])
        return [{"sequence": [a.name for _, a in scored[:5]], "goal": goal}]
