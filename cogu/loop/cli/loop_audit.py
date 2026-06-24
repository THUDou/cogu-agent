import json
from pathlib import Path
from datetime import datetime, timezone


def register_loop_audit_parser(subparsers):
    audit_parser = subparsers.add_parser(
        "loop-audit",
        help="Audit loop run history, readiness, and budget status",
    )
    audit_parser.add_argument(
        "--state-dir", default="", help="State/log persistence directory"
    )
    audit_parser.add_argument(
        "--json", action="store_true", help="Output in JSON format"
    )
    audit_parser.add_argument(
        "--days", type=int, default=7, help="Days of history to show"
    )
    return audit_parser


async def cmd_loop_audit(args, workspace: str, settings) -> int:
    from cogu.loop.readiness import ReadinessEvaluator
    from cogu.loop.patterns import LoopPatternRegistry
    from cogu.loop.state_file import StateFile

    state_dir = args.state_dir or str(Path(workspace) / ".cogu" / "loop")
    state_path = Path(state_dir)
    state_path.mkdir(parents=True, exist_ok=True)

    evaluator = ReadinessEvaluator()

    if args.json:
        return await _audit_json(args, workspace, state_dir, evaluator)

    print("\n=== COGU LOOP AUDIT ===")
    print(f"Workspace: {workspace}")
    print(f"State Dir: {state_dir}")
    print()

    readiness = evaluator.evaluate("auto", workspace)
    print(f"Readiness Level: {readiness.level.value}")
    print(f"Readiness Score: {readiness.score}/100")
    print(f"Detected Signals: {len(readiness.active_signals)}")
    if readiness.missing_signals:
        print(f"Missing Signals: {', '.join(readiness.missing_signals[:5])}")
    print()

    patterns = LoopPatternRegistry.list_all()
    print(f"Available Patterns: {len(patterns)}")
    for p in patterns:
        status = "ENABLED" if evaluator.is_pattern_ready(p.pattern_id, workspace) else "BLOCKED"
        print(f"  [{status}] {p.name:25s} ({p.pattern_id:20s}) L:{p.safety_level.value} {p.cadence.value}")

    run_log_path = state_path / "loop-run-log.jsonl"
    if run_log_path.exists():
        entries = _read_recent_entries(run_log_path, args.days)
        if entries:
            print(f"\nRecent Runs ({min(args.days, len(entries))} entries):")
            for entry in entries[-10:]:
                outcome = entry.get("outcome", "unknown")
                ts = entry.get("run_id", "")[:19]
                print(f"  [{ts}] {entry.get('pattern', 'manual'):20s} {outcome:15s} {entry.get('tokens_estimate', 0):>10,} tokens")

    state_file = state_path / "STATE.md"
    if state_file.exists():
        content = state_file.read_text(encoding="utf-8")[:2000]
        print(f"\nSTATE.md Preview ({len(content)} chars):")
        print(content[:500])

    print("\nAudit complete.")
    return 0


async def _audit_json(args, workspace: str, state_dir: str, evaluator) -> int:
    from cogu.loop.patterns import LoopPatternRegistry

    readiness = evaluator.evaluate("auto", workspace)
    patterns = LoopPatternRegistry.list_all()

    run_log_path = Path(state_dir) / "loop-run-log.jsonl"
    entries = _read_recent_entries(run_log_path, args.days) if run_log_path.exists() else []

    output = {
        "workspace": workspace,
        "state_dir": state_dir,
        "readiness": {
            "level": readiness.level.value,
            "score": readiness.score,
            "active_signals": readiness.active_signals,
            "missing_signals": readiness.missing_signals,
        },
        "patterns": [
            {
                "id": p.pattern_id,
                "name": p.name,
                "ready": evaluator.is_pattern_ready(p.pattern_id, workspace),
                "safety": p.safety_level.value,
                "cadence": p.cadence.value,
            }
            for p in patterns
        ],
        "recent_runs": entries[-20:],
    }

    print(json.dumps(output, indent=2, default=str))
    return 0


def _read_recent_entries(log_path: Path, days: int) -> list[dict]:
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
                if ts >= cutoff or days <= 0:
                    entries.append(entry)
            except (json.JSONDecodeError, ValueError):
                pass
    except FileNotFoundError:
        pass
    return entries
