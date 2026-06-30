import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    for _env_path in [Path(".env"), Path.home() / ".cogu" / ".env"]:
        if _env_path.exists():
            load_dotenv(_env_path)
except ImportError:
    pass

from cogu import __version__
from cogu.core.runner import Runner
from cogu.core.agent import ReActAgent
from cogu.core.session import Session
from cogu.config.settings import Settings
from cogu.config.manager import ConfigManager
from cogu.memory import EnhancedSuperMemory, EnhancedMemoryConfig, RecallStrategy
from cogu.debate import DebateOrchestrator, DebateConfig, DebateMode
from cogu.skills import SkillRegistry, SkillExecutor, SkillExecStatus
from cogu.core.skills_system import get_builtin_skill_registry
from cogu.loop.goal_runner import GoalRunner, GoalRunnerConfig, GoalResult, GoalStatus
from cogu.loop.cli import (
    register_goal_parser,
    register_loop_start_parser,
    register_loop_audit_parser,
    register_loop_cost_parser,
)
from cogu.loop.cli.loop_start import cmd_loop_start
from cogu.loop.cli.loop_audit import cmd_loop_audit
from cogu.loop.cli.loop_cost import cmd_loop_cost
from cogu.config.settings import LoopConfig
from cogu.api.client import DeepSeekClient, MultiProviderClient
from cogu.tools.base import ToolRegistry
from cogu.tools.builtin import register_builtin_tools


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cogu",
        description="COGU AGENT - Cognitive Unified Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  cogu run "Write a sorting algorithm in Python"
  cogu goal "Make all tests pass"
  cogu loop start daily-triage --once
  cogu loop start ci-sweeper --level L2
  cogu loop-audit --days 7
  cogu loop-cost --days 30 --budget 500000
  cogu debate "Should we use async or sync architecture?"
  cogu skills list --all
  cogu skills install /path/to/skill
  cogu skills install https://github.com/user/skill/archive/main.zip
  cogu skills run hello-world --input '{"name":"World"}'
  cogu skills uninstall hello-world
  cogu config set deepseek sk-xxxx
  cogu config list
  cogu serve --port 8080
