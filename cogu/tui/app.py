import asyncio
import os
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Footer, TabbedContent, TabPane, Static
from textual.binding import Binding

from cogu.tui.widgets.chat import ChatPanel
from cogu.tui.widgets.header import HeaderBar
from cogu.tui.widgets.memory_view import MemoryPanel
from cogu.tui.widgets.debate_view import DebatePanel
from cogu.config.settings import Settings
from cogu.memory import EnhancedSuperMemory, EnhancedMemoryConfig, RecallStrategy
from cogu.debate import DebateOrchestrator, DebateConfig, DebateMode
from cogu.skills import SkillRegistry
from cogu.core.agent import ReActAgent
from cogu.core.session import Session
from cogu.core.runner import Runner
from cogu.api.client import DeepSeekClient
from cogu.tools.base import ToolRegistry
from cogu.tools.builtin.file import register_file_tools


class CoguTUI(App):
    TITLE = "COGU AGENT"
    SUB_TITLE = "Cognitive Unified Agent"

    CSS = """
    CoguTUI {
        layout: vertical;
    }
    TabbedContent {
        height: 1fr;
    }
    TabPane {
        padding: 0;
    }
