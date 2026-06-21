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
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+t", "show_tab('chat')", "Chat", show=False),
        Binding("ctrl+d", "show_tab('debate')", "Debate", show=False),
        Binding("ctrl+m", "show_tab('memory')", "Memory", show=False),
        Binding("f1", "show_tab('chat')", "Chat Tab"),
        Binding("f2", "show_tab('debate')", "Debate Tab"),
        Binding("f3", "show_tab('memory')", "Memory Tab"),
    ]

    def __init__(self, workspace: str = "", model: str = "deepseek-chat"):
        super().__init__()
        self.workspace = workspace or os.getcwd()
        self.model_name = model
        self._agent: ReActAgent = None
        self._memory: EnhancedSuperMemory = None
        self._debate: DebateOrchestrator = None
        self._skills: SkillRegistry = None

    def compose(self) -> ComposeResult:
        yield HeaderBar()
        with TabbedContent(initial="chat"):
            with TabPane("Chat", id="chat"):
                yield ChatPanel()
            with TabPane("Debate", id="debate"):
                yield DebatePanel()
            with TabPane("Memory", id="memory"):
                yield MemoryPanel()
        yield Footer()

    async def on_mount(self):
        self._header = self.query_one(HeaderBar)
        self._header.model = self.model_name

        try:
            self._init_backend()
        except Exception as e:
            self._header.status = f"init error: {e}"
            self.notify(str(e), severity="error")

    def _init_backend(self):
        settings = Settings.load(self.workspace)

        db_dir = os.path.join(self.workspace, ".cogu", "memory")
        file_root = os.path.join(self.workspace, ".cogu", "memory_files")
        mem_config = EnhancedMemoryConfig(
            db_dir=db_dir,
            file_root=file_root,
            auto_compress=True,
            auto_entity_extract=False,
        )
        self._memory = EnhancedSuperMemory(mem_config)

        self._skills = SkillRegistry(workspace=self.workspace)
        self._skills.discover()

        self._debate = DebateOrchestrator(
            config=DebateConfig(max_rounds=3),
        )
        self._debate.build_default_team("tui_debate_team")

        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        client = DeepSeekClient(
            api_key=api_key,
            model=self.model_name,
        )
        tool_registry = ToolRegistry()
        register_file_tools(tool_registry)

        self._agent = ReActAgent(
            settings=settings,
            client=client,
            tool_registry=tool_registry,
            session=Session(workspace=self.workspace),
        )

        self._header.status = "ready"

    async def on_chat_panel_message_sent(self, event: ChatPanel.MessageSent):
        chat = self.query_one(ChatPanel)
        self._header.status = "thinking..."
        self._header.increment_turn()

        if not self._agent:
            chat.add_message("system", "Agent not initialized. Check DEEPSEEK_API_KEY.")
            self._header.status = "error: no agent"
            return

        try:
            result = await self._agent.invoke(user_message=event.text)

            if result.thinking:
                chat.add_message("thinking", result.thinking[:500])

            if result.tool_calls:
                for tc in result.tool_calls:
                    chat.add_message("tool", f"[{tc.get('name', 'tool')}]\n{tc.get('arguments', '{}')}")

            chat.add_message("assistant", result.content or "(no response)")

            if self._memory and result.content:
                await self._memory.remember(result.content, metadata={"source": "tui_chat"})

            self._header.status = "ready"
        except Exception as e:
            chat.add_message("system", f"Error: {e}")
            self._header.status = f"error: {e}"

    async def on_debate_panel_debate_start_requested(self, event: DebatePanel.DebateStartRequested):
        chat = self.query_one(ChatPanel)
        debate = self.query_one(DebatePanel)
        self._header.status = "debating..."

        mode_map = {
            "standard": DebateMode.STANDARD,
            "swarm": DebateMode.SWARM,
            "court": DebateMode.COURT,
            "dialectic": DebateMode.DIALECTIC,
        }
        mode = mode_map.get(event.mode, DebateMode.STANDARD)

        chat.add_message("debate", f"Starting debate: {event.topic} (mode={event.mode}, rounds={event.rounds})")

        try:
            self._debate.build_default_team("tui_debate_team")
            consensus = await self._debate.debate(
                topic=event.topic,
                mode=mode,
                rounds=event.rounds,
            )

            chat.add_message("debate",
                f"Debate complete: rounds={consensus.debate_rounds}, confidence={consensus.confidence:.2f}")

            debate.show_consensus(
                consensus.main_proposal.content if consensus.main_proposal else "No consensus",
                consensus.confidence,
                consensus.debate_rounds,
            )

            if consensus.minority_reports:
                debate.show_minority([
                    type("MR", (), {"expert_name": mr.expert_name, "content": mr.content})
                    for mr in consensus.minority_reports
                ])

            self._header.status = "ready"
        except Exception as e:
            chat.add_message("system", f"Debate error: {e}")
            self._header.status = f"debate error: {e}"

    async def on_memory_panel_search_requested(self, event: MemoryPanel.SearchRequested):
        memory_panel = self.query_one(MemoryPanel)
        self._header.status = f"searching memory: {event.query[:30]}..."

        try:
            stats = await self._memory.get_stats()
            memory_panel.update_stats(stats)

            results = await self._memory.recall(
                query=event.query,
                strategy=RecallStrategy.HYBRID,
                limit=10,
            )
            memory_panel.show_results(results)
            self._header.status = "ready"
        except Exception as e:
            self.notify(f"Memory search error: {e}", severity="error")
            self._header.status = f"memory error: {e}"

    def action_show_tab(self, tab_id: str):
        try:
            tabs = self.query_one(TabbedContent)
            tabs.active = tab_id
        except Exception:
            pass


def run_tui(workspace: str = "", model: str = "deepseek-chat"):
    app = CoguTUI(workspace=workspace, model=model)
    app.run()


if __name__ == "__main__":
    run_tui()
