from cogu.core.skills_system import BaseSkill, SkillManifest, SkillCategory, SkillLevel


class LoopBudgetSkill(BaseSkill):
    manifest = SkillManifest(
        name="loop-budget",
        version="0.1.0",
        category=SkillCategory.CUSTOM,
        level=SkillLevel.BASIC,
        description="Runtime budget guard: reads loop-budget.md, checks 80%/100% thresholds, enforces early exit when over budget or no actionable work",
        author="COGU LOOP Engineering",
        tags=["loop", "budget", "safety"],
    )

    async def execute(self, **kwargs) -> dict:
        return {
            "success": True,
            "skill_type": "prompt",
            "name": "loop-budget",
            "instructions": LOOP_BUDGET_PROMPT,
            "message": "Loop budget skill: enforce token budget thresholds and early exit",
        }


LOOP_BUDGET_PROMPT = """# Loop Budget Guard

Run at the **start** and **end** of every loop iteration.

## Start of run

1. Read `loop-budget.md` for daily caps and kill-switch flags.
2. Read recent entries in `loop-run-log.md` (last 24h).
3. Sum `tokens_estimate` for the active pattern today.
4. If spend >= 80% of the pattern's daily cap -> **report-only mode** (no sub-agents, no auto-fix).
5. If spend >= 100% or `loop-pause-all` is set -> **exit immediately** with a one-line note in STATE.md.
6. If watchlist/state has no actionable items -> **exit in <5k tokens** (do not spawn sub-agents).

## End of run

Append one JSON object to `loop-run-log.md`:

```json
{
  "run_id": "<ISO8601>",
  "pattern": "<pattern-id>",
  "duration_s": <number>,
  "items_found": <number>,
  "actions_taken": <number>,
  "escalations": <number>,
  "tokens_estimate": <number>,
  "outcome": "no-op | report-only | fix-proposed | escalated"
}
```

## Rules

- Never exceed `max sub-agent spawns/run` from `loop-budget.md`.
- High-cadence patterns (CI Sweeper, PR Babysitter) **must** early-exit when nothing is actionable.
- On self-throttle, append a line to `loop-budget.md` under **Alerts This Period**.
"""
