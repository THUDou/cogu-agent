import asyncio
from pathlib import Path


def register_goal_parser(subparsers):
    goal_parser = subparsers.add_parser(
        "goal",
        help="Run agent in GOAL mode (autonomous loop until done or budget exhausted)",
    )
    goal_parser.add_argument(
        "goal_text", nargs="+", help="Goal description (e.g. 'Make all tests pass')"
    )
    goal_parser.add_argument(
        "--max-tokens", type=int, default=200000, help="Max tokens before kill"
    )
    goal_parser.add_argument(
        "--max-iterations", type=int, default=50, help="Max iterations"
    )
    goal_parser.add_argument(
        "--max-wall", type=float, default=600.0, help="Max wall time in seconds"
    )
    goal_parser.add_argument(
        "--no-kill", action="store_true", help="Do not kill on budget exceed"
    )
    goal_parser.add_argument(
        "--state-dir", default="", help="State/log persistence directory"
    )
    goal_parser.add_argument(
        "--level",
        default="L2",
        choices=["L0", "L1", "L2", "L3"],
        help="Loop safety level (default: L2)",
    )
    return goal_parser


async def cmd_goal(args, workspace: str, settings) -> int:
    from cogu.loop.goal_runner import GoalRunner, GoalRunnerConfig, GoalStatus

    goal_text = " ".join(args.goal_text)
    state_dir = args.state_dir or str(Path(workspace) / ".cogu" / "loop")

    loop_config = settings.loop if hasattr(settings, 'loop') else None
    config = GoalRunnerConfig(
        max_tokens=args.max_tokens or (loop_config.max_tokens if loop_config else 200000),
        max_iterations=args.max_iterations or (loop_config.max_iterations if loop_config else 50),
        max_wall_seconds=args.max_wall or (loop_config.max_wall_seconds if loop_config else 600.0),
        warning_ratio=loop_config.warning_ratio if loop_config else 0.8,
        kill_on_exceed=not args.no_kill,
        state_dir=state_dir,
        log_enabled=True,
        checkpoint_enabled=True,
    )

    runner = GoalRunner(config=config)

    print(f"\nGOAL mode: {goal_text}")
    print(f"  Level: {args.level}")
    print(f"  Budget: {config.max_tokens:,} tokens / {config.max_iterations} iterations")
    print(f"  State:  {config.state_dir}")
    print()

    result = await runner.run(goal_text)

    print(f"\n{'='*60}")
    print(f"RESULT: {result.status.value}")
    print(f"Iterations: {result.total_iterations}")
    print(f"Tokens used: {result.tokens_used:,}")
    print(f"Duration:    {result.duration_seconds:.1f}s")
    if result.completion_note:
        print(f"Note:        {result.completion_note}")
    print(f"{'='*60}")

    return 0 if result.status == GoalStatus.COMPLETED else 1
