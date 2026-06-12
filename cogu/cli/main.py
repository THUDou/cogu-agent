import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from cogu import __version__
from cogu.core.runner import Runner
from cogu.core.runner import Runner
from cogu.core.agent import ReActAgent
from cogu.core.session import Session
from cogu.config.settings import Settings
from cogu.memory import EnhancedSuperMemory, EnhancedMemoryConfig, RecallStrategy
from cogu.debate import DebateOrchestrator, DebateConfig, DebateMode
from cogu.skills import SkillRegistry, SkillExecutor
from cogu.api.client import DeepSeekClient, MultiProviderClient
from cogu.tools.base import ToolRegistry
from cogu.tools.builtin.file import register_builtin_tools


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cogu",
        description="COGU AGENT - Cognitive Unified Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  cogu run "Write a sorting algorithm in Python"
  cogu debate "Should we use async or sync architecture?"
  cogu skills list
  cogu skills install /path/to/skill
  cogu serve --port 8080
        """,
    )
    parser.add_argument("--version", action="version", version=f"cogu {__version__}")
    parser.add_argument("--workspace", "-w", default=os.getcwd(), help="Workspace directory")
    parser.add_argument("--model", "-m", default="deepseek-chat", help="Model to use")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    sub = parser.add_subparsers(dest="command", help="Commands")

    run_parser = sub.add_parser("run", help="Run the agent with a prompt")
    run_parser.add_argument("prompt", nargs="+", help="The prompt to run")
    run_parser.add_argument("--strategy", default="hybrid", choices=["fts", "semantic", "hybrid", "comprehensive"], help="Memory recall strategy")
    run_parser.add_argument("--no-memory", action="store_true", help="Disable memory")
    run_parser.add_argument("--skills", nargs="*", help="Skills to load")

    debate_parser = sub.add_parser("debate", help="Run expert debate")
    debate_parser.add_argument("topic", nargs="+", help="Debate topic")
    debate_parser.add_argument("--mode", default="standard", choices=["standard", "swarm", "court", "dialectic"], help="Debate mode")
    debate_parser.add_argument("--rounds", type=int, default=2, help="Debate rounds")
    debate_parser.add_argument("--experts", type=int, default=5, help="Number of experts")

    skills_parser = sub.add_parser("skills", help="Manage skills")
    skills_sub = skills_parser.add_subparsers(dest="skills_command")
    skills_sub.add_parser("list", help="List installed skills")
    install_parser = skills_sub.add_parser("install", help="Install a skill")
    install_parser.add_argument("source", help="Path or URL to skill")
    skills_sub.add_parser("discover", help="Discover skills from search paths")
    info_parser = skills_sub.add_parser("info", help="Show skill info")
    info_parser.add_argument("name", help="Skill name")

    memory_parser = sub.add_parser("memory", help="Memory operations")
    memory_sub = memory_parser.add_subparsers(dest="memory_command")
    memory_sub.add_parser("stats", help="Show memory statistics")
    search_parser = memory_sub.add_parser("search", help="Search memory")
    search_parser.add_argument("query", help="Search query")
    reconcile_parser = memory_sub.add_parser("reconcile", help="Reconcile memory stores")
    reconcile_parser = memory_sub.add_parser("reconcile", help="Reconcile memory stores")

    serve_parser = sub.add_parser("serve", help="Start API server")
    serve_parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host to bind")

    sub.add_parser("version", help="Show version")

    tui_parser = sub.add_parser("tui", help="Launch interactive TUI")
    tui_parser.add_argument("--workspace", "-w", default=os.getcwd(), help="Workspace directory")

    return parser


class CLI:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.workspace = args.workspace
        self.settings = Settings.load(self.workspace)
        self._init_memory()
        self._init_skills()
        self._init_debate()
        self._init_agent()

    def _init_memory(self):
        db_dir = os.path.join(self.workspace, ".cogu", "memory")
        file_root = os.path.join(self.workspace, ".cogu", "memory_files")
        config = EnhancedMemoryConfig(
            db_dir=db_dir,
            file_root=file_root,
            auto_compress=True,
            auto_entity_extract=False,
        )
        self.memory = EnhancedSuperMemory(config)

    def _init_skills(self):
        self.skill_registry = SkillRegistry(workspace=self.workspace)
        self.skill_registry.discover()

    def _init_debate(self):
        self.debate = DebateOrchestrator(
            config=DebateConfig(max_rounds=getattr(self.args, "rounds", 2)),
        )

    def _init_agent(self):
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        client = DeepSeekClient(
            api_key=api_key,
            model=self.args.model,
        )
        tool_registry = ToolRegistry()
        register_builtin_tools(tool_registry)
        self.agent = ReActAgent(
            settings=self.settings,
            client=client,
            tool_registry=tool_registry,
            session=Session(workspace=self.workspace),
        )

    async def cmd_run(self) -> int:
        prompt = " ".join(self.args.prompt)
        if self.args.verbose:
            print(f"COGU v{__version__} | model={self.args.model} | workspace={self.workspace}")
            stats = await self.memory.get_stats()
            print(f"Memory: {stats}")
            skills = self.args.skills or []
            if skills:
                print(f"Skills: {skills}")

        strategy_map = {
            "fts": RecallStrategy.FTS_ONLY,
            "semantic": RecallStrategy.SEMANTIC_ONLY,
            "hybrid": RecallStrategy.HYBRID,
            "comprehensive": RecallStrategy.COMPREHENSIVE,
        }
        strategy = strategy_map.get(self.args.strategy, RecallStrategy.HYBRID)

        if not self.args.no_memory:
            recall_results = await self.memory.recall(query=prompt, strategy=strategy, limit=5)
            if recall_results:
                memory_context = "\n".join([r.content[:500] for r in recall_results[:3]])
                self.agent.session.add_message("system", f"Relevant memory:\n{memory_context}")

        if self.args.skills:
            skill_context = self.skill_registry.build_context(self.args.skills)
            if skill_context:
                self.agent.session.add_message("system", f"Loaded skills:\n{skill_context}")

        result = await self.agent.invoke(user_message=prompt)
        print(result.content)
        return 0

    async def cmd_debate(self) -> int:
        topic = " ".join(self.args.topic)
        mode_map = {
            "standard": DebateMode.STANDARD,
            "swarm": DebateMode.SWARM,
            "court": DebateMode.COURT,
            "dialectic": DebateMode.DIALECTIC,
        }
        mode = mode_map.get(self.args.mode, DebateMode.STANDARD)

        self.debate.build_default_team("cli_debate_team")
        consensus = await self.debate.debate(
            topic=topic,
            mode=mode,
            rounds=self.args.rounds,
        )

        print(f"\n{'='*60}")
        print(f"DEBATE: {topic}")
        print(f"Mode: {mode.value} | Rounds: {consensus.debate_rounds} | Confidence: {consensus.confidence:.2f}")
        print(f"{'='*60}\n")

        if consensus.main_proposal:
            print(consensus.main_proposal.content)

        if consensus.minority_reports:
            print(f"\n--- Minority Reports ({len(consensus.minority_reports)}) ---")
            for mr in consensus.minority_reports[:3]:
                print(f"\n[{mr.expert_name}] {mr.content[:200]}...")

        return 0

    async def cmd_skills(self) -> int:
        sc = self.args.skills_command
        if sc == "list":
            names = self.skill_registry.list_all()
            if names:
                print(f"Installed skills ({len(names)}):")
                for name in names:
                    spec = self.skill_registry.load(name)
                    desc = spec.description[:60] if spec and spec.description else ""
                    print(f"  - {name}: {desc}")
            else:
                print("No skills installed. Use 'cogu skills discover' or 'cogu skills install <path>'")
        elif sc == "discover":
            found = self.skill_registry.discover()
            print(f"Discovered {len(found)} skills:")
            for s in found:
                print(f"  - {s.name}: {s.description[:60]}")
        elif sc == "install":
            source = self.args.source
            spec = self.skill_registry.install_skill(source)
            if spec:
                print(f"Installed: {spec.name}")
            else:
                print(f"Failed to install from: {source}")
                return 1
        elif sc == "info":
            spec = self.skill_registry.load(self.args.name)
            if spec:
                print(json.dumps(spec.to_dict(), indent=2, ensure_ascii=False))
                print(f"\nBody preview: {spec.body[:200]}...")
            else:
                print(f"Skill not found: {self.args.name}")
                return 1
        return 0

    async def cmd_memory(self) -> int:
        mc = self.args.memory_command
        if mc == "stats":
            stats = await self.memory.get_stats()
            print(json.dumps(stats, indent=2, ensure_ascii=False))
        elif mc == "search":
            results = await self.memory.recall(query=self.args.query, strategy=RecallStrategy.HYBRID, limit=10)
            for r in results:
                print(f"[{r.source}:{r.level.value}] score={r.score:.3f}")
                print(f"  {r.content[:200]}")
                print()
        elif mc == "reconcile":
            result = await self.memory.reconcile()
            print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    async def cmd_serve(self) -> int:
        print(f"Starting COGU API server on {self.args.host}:{self.args.port}")
        print("(API server not yet implemented)")
        return 0

    async def cmd_tui(self) -> int:
        try:
            from cogu.tui.app import run_tui
        except ImportError:
            print("TUI requires textual. Install with: pip install textual")
            return 1
        run_tui(workspace=self.workspace, model=self.args.model)
        return 0

    async def cmd_version(self) -> int:
        print(f"cogu v{__version__}")
        return 0

    async def run(self) -> int:
        if not self.args.command:
            print("COGU AGENT v{__version__}")
            print("Use --help for available commands")
            return 0

        handlers = {
            "run": self.cmd_run,
            "debate": self.cmd_debate,
            "skills": self.cmd_skills,
            "memory": self.cmd_memory,
            "serve": self.cmd_serve,
            "tui": self.cmd_tui,
            "version": self.cmd_version,
        }

        handler = handlers.get(self.args.command)
        if handler:
            return await handler()
        print(f"Unknown command: {self.args.command}")
        return 1


def main():
    parser = create_parser()
    args = parser.parse_args()
    cli = CLI(args)
    exit_code = asyncio.run(cli.run())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
