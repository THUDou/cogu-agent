import re
import time
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from cogu.skills.spec import SkillSpec
from cogu.skills.registry import SkillRegistry


MAX_EVENTS_PER_RECORDING = 200
DEDUP_WINDOW_MS = 300.0


@dataclass
class RecordedAction:
    timestamp_ms: float
    action_type: str
    target: Optional[str] = None
    coordinates: Optional[tuple[float, float]] = None
    text_input: Optional[str] = None
    package_name: Optional[str] = None
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d: dict = {
            "timestamp_ms": self.timestamp_ms,
            "action_type": self.action_type,
        }
        if self.target is not None:
            d["target"] = self.target
        if self.coordinates is not None:
            d["coordinates"] = list(self.coordinates)
        if self.text_input is not None:
            d["text_input"] = self.text_input
        if self.package_name is not None:
            d["package_name"] = self.package_name
        if self.extra:
            d["extra"] = self.extra
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "RecordedAction":
        coords = data.get("coordinates")
        if coords is not None:
            coords = tuple(coords)
        return cls(
            timestamp_ms=data["timestamp_ms"],
            action_type=data["action_type"],
            target=data.get("target"),
            coordinates=coords,
            text_input=data.get("text_input"),
            package_name=data.get("package_name"),
            extra=data.get("extra", {}),
        )


@dataclass
class Bookmark:
    uri: str
    title: str
    timestamp_ms: float = 0.0


class RecordingSession:
    def __init__(self) -> None:
        self._actions: list[RecordedAction] = []
        self._bookmarks: list[Bookmark] = []
        self._active: bool = False
        self._start_time: float = 0.0

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def actions(self) -> list[RecordedAction]:
        return list(self._actions)

    @property
    def bookmarks(self) -> list[Bookmark]:
        return list(self._bookmarks)

    def start(self) -> None:
        self._actions.clear()
        self._bookmarks.clear()
        self._active = True
        self._start_time = time.time()

    def record_action(self, action: RecordedAction) -> None:
        if not self._active:
            return
        if len(self._actions) >= MAX_EVENTS_PER_RECORDING:
            return
        if self._actions:
            last = self._actions[-1]
            if (
                action.action_type == last.action_type
                and action.target == last.target
                and (action.timestamp_ms - last.timestamp_ms) < DEDUP_WINDOW_MS
            ):
                return
        self._actions.append(action)

    def stop(self) -> list[RecordedAction]:
        self._active = False
        return list(self._actions)

    def bookmark_current_page(self, uri: str, title: str) -> None:
        if not self._active:
            return
        self._bookmarks.append(Bookmark(
            uri=uri,
            title=title,
            timestamp_ms=(time.time() - self._start_time) * 1000,
        ))


class BehaviorCloner:
    def __init__(self, skills_dir: Path) -> None:
        self._skills_dir = skills_dir

    def recording_to_skill(
        self,
        events: list[RecordedAction],
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> SkillSpec:
        skill_name = name or self._generate_skill_name(events)
        body = self._build_skill_markdown(skill_name, events)
        tools = list({e.action_type for e in events})
        packages = list({e.package_name for e in events if e.package_name})
        spec = SkillSpec(
            name=skill_name,
            description=description or f"Behavior-cloned skill from {len(events)} recorded actions",
            version="0.1.0",
            author="behavior-cloner",
            tools=tools,
            dependencies=packages,
            body=body,
        )
        return spec

    def deeplink_to_skill(
        self,
        uri: str,
        package_name: str,
        title: str,
        name: Optional[str] = None,
    ) -> SkillSpec:
        skill_name = name or self._sanitize_name(f"goto_{title}")
        body = self._build_deeplink_markdown(skill_name, uri, package_name, title)
        spec = SkillSpec(
            name=skill_name,
            description=f"One-tap navigation to: {title}",
            version="0.1.0",
            author="behavior-cloner",
            tools=["deeplink"],
            dependencies=[package_name] if package_name else [],
            body=body,
        )
        return spec

    def save_skill(self, spec: SkillSpec) -> Path:
        skill_dir = self._skills_dir / spec.name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_md_path = skill_dir / "SKILL.md"
        content = self._render_skill_md(spec)
        skill_md_path.write_text(content, encoding="utf-8")
        spec.home_dir = str(skill_dir)
        spec.source = str(skill_md_path)
        return skill_dir

    def save_and_register(self, spec: SkillSpec, registry: SkillRegistry) -> Path:
        skill_dir = self.save_skill(spec)
        reloaded = SkillSpec.from_markdown(str(skill_dir / "SKILL.md"))
        if reloaded:
            registry.register(reloaded)
        return skill_dir

    def _generate_skill_name(self, events: list[RecordedAction]) -> str:
        if not events:
            return "empty_skill"
        first = events[0]
        parts: list[str] = []
        if first.package_name:
            pkg = first.package_name.split(".")[-1]
            parts.append(pkg)
        if first.action_type == "open_app" and first.package_name:
            parts.append("launch")
        elif first.action_type == "tap" and first.target:
            parts.append("tap_" + self._sanitize_name(first.target))
        elif first.action_type == "type" and first.text_input:
            parts.append("type")
        else:
            parts.append(first.action_type)
        if len(events) > 1:
            last = events[-1]
            if last.action_type != first.action_type:
                parts.append("then")
                parts.append(last.action_type)
        name = "_".join(parts)
        return self._sanitize_name(name)

    def _build_skill_markdown(self, name: str, events: list[RecordedAction]) -> str:
        lines: list[str] = []
        lines.append(f"# {name}")
        lines.append("")
        lines.append("## Recorded Actions")
        lines.append("")
        lines.append("| # | Type | Target | Input | Coordinates |")
        lines.append("|---|------|--------|-------|-------------|")
        for i, e in enumerate(events, 1):
            target = e.target or "-"
            text = e.text_input or "-"
            coords = f"({e.coordinates[0]:.0f}, {e.coordinates[1]:.0f})" if e.coordinates else "-"
            lines.append(f"| {i} | {e.action_type} | {target} | {text} | {coords} |")
        lines.append("")
        lines.append("## Replay Instructions")
        lines.append("")
        lines.append("Execute the actions above in sequence to reproduce the recorded behavior.")
        lines.append("")
        lines.append("```yaml")
        for e in events:
            lines.append(yaml.dump([e.to_dict()], allow_unicode=True, default_flow_style=False).strip())
        lines.append("```")
        return "\n".join(lines)

    def _build_deeplink_markdown(self, name: str, uri: str, package_name: str, title: str) -> str:
        lines: list[str] = []
        lines.append(f"# {name}")
        lines.append("")
        lines.append("## Deep Link Navigation")
        lines.append("")
        lines.append(f"**URI:** `{uri}`")
        lines.append(f"**Package:** `{package_name}`")
        lines.append(f"**Title:** {title}")
        lines.append("")
        lines.append("## Replay Instructions")
        lines.append("")
        lines.append("Open the URI above to navigate directly to the target page.")
        lines.append("")
        lines.append("```yaml")
        lines.append(yaml.dump({
            "action_type": "deeplink",
            "uri": uri,
            "package_name": package_name,
            "title": title,
        }, allow_unicode=True, default_flow_style=False))
        lines.append("```")
        return "\n".join(lines)

    def _render_skill_md(self, spec: SkillSpec) -> str:
        frontmatter = {
            "name": spec.name,
            "description": spec.description,
            "version": spec.version,
            "author": spec.author,
            "tools": spec.tools,
            "dependencies": spec.dependencies,
        }
        fm_str = yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False).strip()
        return f"---\n{fm_str}\n---\n\n{spec.body}\n"

    @staticmethod
    def _sanitize_name(name: str) -> str:
        sanitized = re.sub(r"[^a-zA-Z0-9_\u4e00-\u9fff]", "_", name)
        sanitized = re.sub(r"_+", "_", sanitized)
        sanitized = sanitized.strip("_")
        if not sanitized:
            sanitized = "unnamed_skill"
        return sanitized.lower()