from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from cogu.evolution.models import RunMetrics, TraceDigest

_ISSUE_PATTERNS = [
    re.compile(r"traceback|exception|error|failed|timeout|exit code|segmentation fault|oom|out of memory", re.IGNORECASE),
]


class TraceCollector:

    def __init__(self, run_dir: str | Path):
        self.run_dir = Path(run_dir)

    def collect(self, task_description: str = "") -> TraceDigest:
        digest = TraceDigest(
            run_dir=str(self.run_dir),
            task_description=task_description,
        )

        trajectory_files = list(self.run_dir.rglob("trajectory*.json"))
        all_steps: list[dict[str, Any]] = []
        tool_calls: dict[str, int] = {}
        tool_errors: dict[str, int] = {}
        issues: list[str] = []
        llm_calls = 0

        for tf in trajectory_files:
            try:
                data = json.loads(tf.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for run in data:
                        traj = run.get("trajectory", {})
                        steps = traj.get("steps", [])
                        all_steps.extend(steps)
                        for step in steps:
                            assistant = step.get("assistant_message", {})
                            tool_msgs = step.get("tool_responses", [])
                            if assistant:
                                llm_calls += 1
                            for tm in tool_msgs:
                                tool_name = tm.get("tool_name", "unknown")
                                tool_calls[tool_name] = tool_calls.get(tool_name, 0) + 1
                                if tm.get("is_error"):
                                    tool_errors[tool_name] = tool_errors.get(tool_name, 0) + 1
            except Exception:
                continue

        for step in all_steps[:120]:
            summary = {"step_id": step.get("step_id", 0)}
            assistant = step.get("assistant_message", {})
            if assistant:
                content = assistant.get("content", "")
                summary["content_preview"] = content[:200] if content else ""
            digest.step_summaries.append(summary)

        for step in all_steps:
            assistant = step.get("assistant_message", {})
            content = assistant.get("content", "")
            if content:
                for pattern in _ISSUE_PATTERNS:
                    matches = pattern.findall(content)
                    for m in matches:
                        if m not in issues:
                            issues.append(m)
                            if len(issues) >= 160:
                                break

        log_files = list(self.run_dir.rglob("*.log"))
        log_excerpt = ""
        for lf in log_files:
            try:
                text = lf.read_text(encoding="utf-8", errors="replace")
                log_excerpt += text[-4000:]
            except Exception:
                continue

        manifest = []
        for f in sorted(self.run_dir.rglob("*")):
            if f.is_file():
                manifest.append(str(f.relative_to(self.run_dir)))
            if len(manifest) >= 200:
                break

        total_steps = len(all_steps)
        completed = sum(1 for s in all_steps if "completed" in str(s.get("status", "")))
        status = "completed" if completed == total_steps and total_steps > 0 else "unknown"

        digest.metrics = RunMetrics(
            status=status,
            step_count=total_steps,
            llm_call_count=llm_calls,
            tool_call_count=sum(tool_calls.values()),
            tool_error_count=sum(tool_errors.values()),
            issue_count=len(issues),
        )
        digest.tool_call_counts = tool_calls
        digest.tool_error_counts = tool_errors
        digest.issues = issues
        digest.workspace_manifest = manifest
        digest.log_excerpt = log_excerpt

        return digest
