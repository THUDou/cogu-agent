from cogu.core.skills_system import BaseSkill, SkillManifest, SkillCategory, SkillLevel


class LoopTriageSkill(BaseSkill):
    manifest = SkillManifest(
        name="loop-triage",
        version="0.1.0",
        category=SkillCategory.CUSTOM,
        level=SkillLevel.INTERMEDIATE,
        description="Triage recent CI failures, issues, commits, and conversations into a prioritized STATE.md report for autonomous loop consumption",
        author="COGU LOOP Engineering",
        tags=["loop", "triage", "automation"],
    )

    async def execute(self, **kwargs) -> dict:
        return {
            "success": True,
            "skill_type": "prompt",
            "name": "loop-triage",
            "instructions": LOOP_TRIAGE_PROMPT,
            "message": "Loop triage skill: scan CI/issues/commits and produce structured triage report",
        }


LOOP_TRIAGE_PROMPT = """# Loop Triage Skill

You are an expert engineering triage agent. Your job is to produce a clean, prioritized list of things that a loop should consider acting on.

- Recent CI / test failures (last 24h)
- Open issues / tickets assigned to the team
- Recent commits on main (last 24-48h)
- Any chat threads the loop has visibility into
- The current state file (what the loop already knows about)


Produce a markdown report with these sections:

- Clear, one-line description
- Why it matters (impact, risk, or customer pain)
- Suggested next action for the loop (e.g. "draft minimal fix in isolated worktree")
- Rough effort estimate

- Same format but lower urgency

- Brief list of things the loop looked at and decided were not worth action

- Any facts the loop should remember for the next run (e.g. "PR #1234 now has 2 approvals")


- Be brutally concise. The loop (and the human reading the state) will thank you.
- Only put something in "High-Priority" if a reasonable engineer would want to know about it today.
- When in doubt, put it in Watch or Noise rather than creating work.
- Never propose architectural overhauls during triage - this skill is for signal, not invention.
- Respect the project's existing skills and conventions (they will be provided in context).
