from cogu.core.skills_system import BaseSkill, SkillManifest, SkillCategory, SkillLevel


class MinimalFixSkill(BaseSkill):
    manifest = SkillManifest(
        name="minimal-fix",
        version="0.1.0",
        category=SkillCategory.CODE,
        level=SkillLevel.INTERMEDIATE,
        description="Produce the smallest possible code change that fixes a specific, well-scoped issue. One problem per invocation. Never refactor unrelated code",
        author="COGU LOOP Engineering",
        tags=["loop", "fix", "minimal", "maker-checker"],
    )

    async def execute(self, **kwargs) -> dict:
        return {
            "success": True,
            "skill_type": "prompt",
            "name": "minimal-fix",
            "instructions": MINIMAL_FIX_PROMPT,
            "message": "Minimal fix skill: smallest diff for a specific, well-scoped issue",
        }


MINIMAL_FIX_PROMPT = """# Minimal Fix Skill

You fix **one specific problem** with the **smallest diff** that could work.


- Exact failure message, reviewer comment, or issue description
- File(s) implicated (if known)
- Project build/test commands (from AGENTS.md or project skills)
- Path denylist (from loop safety policy - never edit `.env`, `auth/`, `payments/`, secrets)


1. Reproduce or confirm the failure locally if possible.
2. Identify the minimal root cause - not symptoms in distant files.
3. Change only what is required. No drive-by refactors.
4. Run tests/lint relevant to the change.
5. Summarize: what changed, why, what you ran.


```markdown

(one sentence)

(files + what changed)

(command + result)

(yes/no + why)
```


- One problem per invocation. Multiple failures -> escalate or triage first.
- Respect denylist paths - escalate instead of editing.
- Prefer worktree isolation when the loop runs unattended.
- Do not mark your own work done - the verifier decides.
