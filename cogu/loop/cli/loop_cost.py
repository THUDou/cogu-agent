import json
from pathlib import Path
from collections import defaultdict


def register_loop_cost_parser(subparsers):
    cost_parser = subparsers.add_parser(
        "loop-cost",
        help="Analyze token cost and usage across all loop runs",
    )
    cost_parser.add_argument(
        "--state-dir", default="", help="State/log persistence directory"
    )
    cost_parser.add_argument(
        "--days", type=int, default=30, help="Days of history to analyze"
    )
    cost_parser.add_argument(
        "--pattern", default="", help="Filter by pattern ID"
    )
    cost_parser.add_argument(
        "--json", action="store_true", help="Output in JSON format"
    )
    cost_parser.add_argument(
        "--budget", type=int, default=0, help="Daily budget limit for threshold analysis"
    )
    return cost_parser


async def cmd_loop_cost(args, workspace: str, settings) -> int:
    state_dir = args.state_dir or str(Path(workspace) / ".cogu" / "loop")
    run_log_path = Path(state_dir) / "loop-run-log.jsonl"

    if not run_log_path.exists():
        print("No loop run log found. Run some loops first.")
        return 0

    entries = _parse_entries(run_log_path, args.days, args.pattern)
    if not entries:
        print("No entries found in the specified time range.")
        return 0

    summary = _compute_summary(entries)

    if args.json:
        output = {
            "period_days": args.days,
            "pattern_filter": args.pattern or "all",
            "total_runs": summary["total_runs"],
            "total_tokens": summary["total_tokens"],
            "total_duration_s": summary["total_duration_s"],
            "by_pattern": summary["by_pattern"],
            "by_outcome": summary["by_outcome"],
            "daily_average_tokens": summary["total_tokens"] / max(args.days, 1),
            "daily_average_runs": summary["total_runs"] / max(args.days, 1),
        }
        print(json.dumps(output, indent=2))
        return 0

    print("\n=== LOOP COST ANALYSIS ===")
    print(f"Period:   {args.days} days")
    print(f"Pattern:  {args.pattern or 'all'}")
    print(f"Runs:     {summary['total_runs']}")
    print(f"Tokens:   {summary['total_tokens']:,}")
    print(f"Duration: {summary['total_duration_s']/3600:.1f} hours")
    print()

    daily_tokens = summary["total_tokens"] / max(args.days, 1)
    print(f"Daily Average: {daily_tokens:,.0f} tokens / {summary['total_runs']/max(args.days,1):.1f} runs")

    if args.budget > 0:
        pct = daily_tokens / args.budget * 100
        bar = "=" * int(min(pct / 5, 20))
        print(f"Budget Usage:  [{bar:<20}] {pct:.0f}% ({daily_tokens:,.0f}/{args.budget:,})")
        if pct >= 100:
            print("*** WARNING: Daily budget EXCEEDED! ***")
        elif pct >= 80:
            print("*** WARNING: Approaching budget limit (>=80%) ***")

    print("\nBy Pattern:")
    for pattern, data in sorted(summary["by_pattern"].items()):
        print(f"  {pattern:25s} {data['runs']:>5} runs  {data['tokens']:>12,} tokens  {data['duration_s']/60:>6.1f} min")

    print("\nBy Outcome:")
    for outcome, data in sorted(summary["by_outcome"].items()):
        print(f"  {outcome:15s} {data['runs']:>5} runs  {data['tokens']:>12,} tokens")

    return 0


def _parse_entries(log_path: Path, days: int, pattern_filter: str) -> list[dict]:
    from datetime import datetime, timezone
    entries = []
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    try:
        for line in log_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                run_id = entry.get("run_id", "")
                ts = datetime.fromisoformat(run_id.replace("Z", "+00:00")).timestamp() if run_id else 0
                if ts < cutoff:
                    continue
                if pattern_filter and entry.get("pattern", "") != pattern_filter:
                    continue
                entries.append(entry)
            except (json.JSONDecodeError, ValueError):
                pass
    except FileNotFoundError:
        pass
    return entries


def _compute_summary(entries: list[dict]) -> dict:
    by_pattern = defaultdict(lambda: {"runs": 0, "tokens": 0, "duration_s": 0})
    by_outcome = defaultdict(lambda: {"runs": 0, "tokens": 0})

    total_tokens = 0
    total_duration = 0.0

    for entry in entries:
        pattern = entry.get("pattern", "manual")
        outcome = entry.get("outcome", "unknown")
        tokens = entry.get("tokens_estimate", 0)
        duration = entry.get("duration_s", 0)

        by_pattern[pattern]["runs"] += 1
        by_pattern[pattern]["tokens"] += tokens
        by_pattern[pattern]["duration_s"] += duration

        by_outcome[outcome]["runs"] += 1
        by_outcome[outcome]["tokens"] += tokens

        total_tokens += tokens
        total_duration += duration

    return {
        "total_runs": len(entries),
        "total_tokens": total_tokens,
        "total_duration_s": total_duration,
        "by_pattern": dict(by_pattern),
        "by_outcome": dict(by_outcome),
    }
