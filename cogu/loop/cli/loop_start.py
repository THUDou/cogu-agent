import asyncio
import subprocess
import sys
from pathlib import Path


def register_loop_start_parser(subparsers):
    loop_parser = subparsers.add_parser(
        "loop",
        help="Loop management commands (start/audit/cost)",
    )
    loop_sub = loop_parser.add_subparsers(dest="loop_action", help="Loop action")

    start_parser = loop_sub.add_parser("start", help="Start a loop pattern")
    start_parser.add_argument(
        "pattern",
        choices=[
            "daily-triage", "pr-babysitter", "ci-sweeper",
            "dep-sweeper", "changelog", "post-merge", "issue-triage",
        ],
        help="Loop pattern to run",
    )
    start_parser.add_argument(
        "--once", action="store_true", help="Run once and exit (no cron scheduling)"
    )
    start_parser.add_argument(
        "--level",
        default="",
        choices=["L0", "L1", "L2", "L3"],
        help="Override safety level",
    )
    start_parser.add_argument(
        "--max-tokens", type=int, default=0, help="Override max tokens"
    )
    start_parser.add_argument(
        "--max-iterations", type=int, default=0, help="Override max iterations"
    )
    start_parser.add_argument(
        "--state-dir", default="", help="State/log persistence directory"
    )
    return start_parser


async def cmd_loop_start(args, workspace: str, settings) -> int:
    from cogu.loop.patterns import LoopPatternRegistry, LoopPattern
    from cogu.loop.readiness import ReadinessEvaluator, ReadinessLevel

    pattern = LoopPatternRegistry.get(args.pattern)
    if not pattern:
        print(f"Unknown pattern: {args.pattern}")
        return 1

    state_dir = args.state_dir or str(Path(workspace) / ".cogu" / "loop")
    Path(state_dir).mkdir(parents=True, exist_ok=True)

    evaluator = ReadinessEvaluator()
    readiness = evaluator.evaluate(args.pattern, workspace)

    print(f"\nLOOP START: {pattern.name} ({pattern.pattern_id})")
    print(f"  Safety:     {pattern.safety_level.value}")
    print(f"  Cadence:    {pattern.cadence.value}")
    print(f"  Write Mode: {pattern.write_mode}")
    print(f"  Readiness:  {readiness.level.value} ({readiness.score}/100)")

    if readiness.level == ReadinessLevel.L0:
        print("\n*** WARNING: Readiness L0 — loop may not be suitable for this workspace ***")
        print("    Missing signals:", readiness.missing_signals)

    if not args.once:
        from cogu.loop.automation import AutomationScheduler, AutomationDef, AutomationTrigger
        scheduler = AutomationScheduler()

        auto_def = AutomationDef(
            name=f"loop-{args.pattern}",
            goal_text=pattern.goal_template,
            trigger=AutomationTrigger.CRON,
            cron_expr=f"*/{pattern.min_interval_minutes} * * * *",
            interval_seconds=pattern.min_interval_minutes * 60,
            max_iterations=args.max_iterations or pattern.max_iterations,
            max_tokens=args.max_tokens or pattern.max_tokens,
            max_wall_seconds=pattern.max_wall_seconds,
        )
        scheduler.add(auto_def)
        print(f"  Scheduled:  Every {pattern.min_interval_minutes} minutes")
        print("\nLoop scheduled. Use 'cogu loop audit' to check status.")

    print(f"\n  Goal: {pattern.goal_template}")

    if args.once:
        print("\nRunning single iteration...")
        return await _run_single_loop(pattern, state_dir, args, settings)

    return 0


async def _run_single_loop(pattern, state_dir: str, args, settings) -> int:
    from cogu.loop.goal_runner import GoalRunner, GoalRunnerConfig, GoalStatus

    config = GoalRunnerConfig(
        max_tokens=args.max_tokens or pattern.max_tokens,
        max_iterations=args.max_iterations or pattern.max_iterations,
        max_wall_seconds=pattern.max_wall_seconds,
        state_dir=state_dir,
        log_enabled=True,
        checkpoint_enabled=True,
    )

    runner = GoalRunner(config=config)
    result = await runner.run(pattern.goal_template)

    print(f"\nLoop complete: {result.status.value}")
    print(f"  Iterations: {result.total_iterations}")
    print(f"  Tokens:     {result.tokens_used:,}")
    return 0 if result.status == GoalStatus.COMPLETED else 0
