from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import yaml

from cogu.topology.spec import (
    TopologySpec,
    TeamSpec,
    AgentNode,
    AgentRole,
    ChannelPolicy,
    DeployBackend,
)

logger = logging.getLogger(__name__)


class TopologyManager:
    def __init__(self, storage_path: str = ""):
        self._storage_path = Path(storage_path) if storage_path else Path.home() / ".cogu" / "topologies"
        self._topologies: dict[str, TopologySpec] = {}
        self._active_teams: dict[str, dict] = {}
        self._load()

    def _load(self):
        if not self._storage_path.exists():
            return
        for f in self._storage_path.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                spec = TopologySpec(**data)
                self._topologies[f.stem] = spec
            except Exception as e:
                logger.warning(f"Failed to load topology {f.stem}: {e}")
        for f in self._storage_path.glob("*.yaml"):
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
                spec = TopologySpec(**data)
                self._topologies[f.stem] = spec
            except Exception as e:
                logger.warning(f"Failed to load topology {f.stem}: {e}")
        for f in self._storage_path.glob("*.yml"):
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
                spec = TopologySpec(**data)
                self._topologies[f.stem] = spec
            except Exception as e:
                logger.warning(f"Failed to load topology {f.stem}: {e}")

    def _save(self, topology_id: str, spec: TopologySpec):
        self._storage_path.mkdir(parents=True, exist_ok=True)
        out = (self._storage_path / f"{topology_id}.json")
        out.write_text(spec.model_dump_json(indent=2), encoding="utf-8")

    def apply(self, spec: TopologySpec) -> TopologySpec:
        duplicates = spec.validate_unique_names()
        if duplicates:
            raise ValueError(f"Duplicate agent names: {duplicates}")

        topology_id = spec.name
        self._topologies[topology_id] = spec
        self._save(topology_id, spec)

        for team in spec.teams:
            self._materialize_team(team, topology_id)

        for agent in spec.agents:
            self._materialize_agent(agent, topology_id)

        return spec

    def apply_yaml(self, yaml_content: str) -> TopologySpec:
        data = yaml.safe_load(yaml_content)
        spec = TopologySpec(**data)
        return self.apply(spec)

    def apply_file(self, path: str) -> TopologySpec:
        p = Path(path)
        if p.suffix in (".yaml", ".yml"):
            content = p.read_text(encoding="utf-8")
            return self.apply_yaml(content)
        elif p.suffix == ".json":
            data = json.loads(p.read_text(encoding="utf-8"))
            spec = TopologySpec(**data)
            return self.apply(spec)
        else:
            raise ValueError(f"Unsupported file format: {p.suffix}")

    def _materialize_team(self, team: TeamSpec, topology_id: str):
        team_key = f"{topology_id}/{team.name}"
        self._active_teams[team_key] = {
            "team": team.name,
            "topology": topology_id,
            "hash": team.spec_hash(),
            "leader": team.leader.name,
            "workers": [w.name for w in team.workers],
        }
        logger.info(f"Team {team.name}: leader={team.leader.name}, workers={len(team.workers)}, hash={team.spec_hash()[:8]}")

    def _materialize_agent(self, agent: AgentNode, topology_id: str):
        logger.info(f"Standalone agent {agent.name}: model={agent.model}")

    def get(self, topology_id: str) -> Optional[TopologySpec]:
        return self._topologies.get(topology_id)

    def get_team(self, topology_id: str, team_name: str) -> Optional[dict]:
        return self._active_teams.get(f"{topology_id}/{team_name}")

    def list_topologies(self) -> list[dict]:
        return [
            {
                "id": tid,
                "name": spec.name,
                "teams": len(spec.teams),
                "agents": len(spec.agents),
                "hash": spec.spec_hash()[:8],
            }
            for tid, spec in self._topologies.items()
        ]

    def list_teams(self, topology_id: str) -> list[dict]:
        return [
            {"team": k.split("/")[-1], **v}
            for k, v in self._active_teams.items()
            if k.startswith(topology_id)
        ]

    def delete(self, topology_id: str) -> bool:
        if topology_id not in self._topologies:
            return False
        del self._topologies[topology_id]
        self._active_teams = {
            k: v for k, v in self._active_teams.items()
            if not k.startswith(f"{topology_id}/")
        }
        f = self._storage_path / f"{topology_id}.json"
        if f.exists():
            f.unlink()
        return True

    def diff(self, old_spec: TopologySpec, new_spec: TopologySpec) -> dict:
        changes = {"added_teams": [], "removed_teams": [], "modified_teams": [], "unchanged_teams": []}

        old_team_names = {t.name for t in old_spec.teams}
        new_team_names = {t.name for t in new_spec.teams}

        for name in new_team_names - old_team_names:
            changes["added_teams"].append(name)
        for name in old_team_names - new_team_names:
            changes["removed_teams"].append(name)
        for name in old_team_names & new_team_names:
            old_t = next(t for t in old_spec.teams if t.name == name)
            new_t = next(t for t in new_spec.teams if t.name == name)
            if old_t.spec_hash() != new_t.spec_hash():
                changes["modified_teams"].append(name)
            else:
                changes["unchanged_teams"].append(name)

        return changes
