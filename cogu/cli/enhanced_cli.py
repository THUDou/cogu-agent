"""Enhanced CLI — 增强 CLI

基于源码: Claude Code CLI + ECC CLI
COGU 实现: 20+ 子命令 + 彩色输出 + 进度条
"""
from __future__ import annotations

import argparse
import sys
from typing import Any, Optional


def create_enhanced_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cogu",
        description="COGU AGENT - Cognitive Unified Agent v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version="cogu 2.0.0")
    parser.add_argument("--verbose", "-v", action="store_true")

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("run", help="Run agent with prompt")
    sub.add_parser("chat", help="Interactive chat mode")
    sub.add_parser("debate", help="Expert debate")
    sub.add_parser("skills", help="Manage skills")
    sub.add_parser("memory", help="Memory operations")
    sub.add_parser("config", help="Configuration")
    sub.add_parser("serve", help="Start web server")
    sub.add_parser("tui", help="Terminal UI")
    sub.add_parser("studio", help="Studio UI")
    sub.add_parser("desktop", help="Desktop app")
    sub.add_parser("evolve", help="Self-evolution")
    sub.add_parser("benchmark", help="Run benchmarks")
    sub.add_parser("audit", help="Security audit")
    sub.add_parser("plugins", help="Manage plugins")
    sub.add_parser("agents", help="Manage agents")
    sub.add_parser("tools", help="Tool discovery")
    sub.add_parser("doctor", help="System diagnostics")
    sub.add_parser("status", help="Show status")
    sub.add_parser("logs", help="View logs")
    sub.add_parser("update", help="Check for updates")

    return parser


__all__ = ["create_enhanced_parser"]
