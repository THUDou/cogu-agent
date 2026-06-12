from textual.containers import Container, VerticalScroll, Horizontal
from textual.widgets import Static, Input, Button, Label, RichLog
from textual.binding import Binding
from textual.message import Message
from typing import Optional


class MemoryPanel(Container):
    DEFAULT_CSS = """
    MemoryPanel {
        height: 1fr;
        layout: vertical;
        border: solid $secondary;
        padding: 0 1;
    }
    MemoryPanel #memory-stats {
        height: auto;
        padding: 0 1;
        background: $panel-darken-1;
        color: $text-muted;
    }
    MemoryPanel #memory-results {
        height: 1fr;
        overflow-y: auto;
    }
    MemoryPanel #memory-search {
        dock: bottom;
        height: auto;
        padding: 1 0;
    }
    """

    BINDINGS = [
        Binding("ctrl+f", "focus_search", "Search Memory"),
    ]

    class SearchRequested(Message):
        def __init__(self, query: str, strategy: str = "hybrid"):
            self.query = query
            self.strategy = strategy
            super().__init__()

    def compose(self):
        yield Static("Memory: idle", id="memory-stats")
        yield VerticalScroll(id="memory-results")
        with Horizontal(id="memory-search"):
            yield Input(placeholder="Search memory...", id="mem-query")
            yield Button("Search", id="mem-search-btn", variant="primary")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "mem-search-btn":
            inp = self.query_one("#mem-query", Input)
            if inp.value.strip():
                self.post_message(self.SearchRequested(inp.value.strip()))

    def on_input_submitted(self, event: Input.Submitted):
        if event.input.id == "mem-query" and event.value.strip():
            self.post_message(self.SearchRequested(event.value.strip()))

    def update_stats(self, stats: dict):
        label = self.query_one("#memory-stats", Static)
        fts = stats.get("fts_count", 0)
        graph = stats.get("graph_nodes", 0)
        files = stats.get("file_count", 0)
        label.update(f"Memory: {fts} FTS entries | {graph} graph nodes | {files} files")

    def show_results(self, results: list):
        container = self.query_one("#memory-results", VerticalScroll)
        container.remove_children()
        if not results:
            container.mount(Static("[dim]No results found.[/]"))
            return
        for r in results:
            score = getattr(r, "score", 0)
            content = getattr(r, "content", str(r))[:300]
            source = getattr(r, "source", "memory")
            container.mount(Static(
                f"[bold]{source}[/] (score: {score:.3f})\n{content}\n"
            ))

    def action_focus_search(self):
        self.query_one("#mem-query", Input).focus()
