from textual.containers import Container, VerticalScroll, Horizontal
from textual.widgets import Static, Input, Button, Label, Select, RadioSet, RadioButton
from textual.binding import Binding
from textual.message import Message


class DebatePanel(Container):
    DEFAULT_CSS = """
    DebatePanel {
        height: 1fr;
        layout: vertical;
        border: solid $warning;
        padding: 0 1;
    }
    DebatePanel #debate-config {
        height: auto;
        padding: 0 1;
        background: $panel-darken-1;
    }
    DebatePanel #debate-results {
        height: 1fr;
        overflow-y: auto;
    }
    DebatePanel #debate-controls {
        dock: bottom;
        height: auto;
        padding: 1 0;
    }
    """

    BINDINGS = [
        Binding("ctrl+r", "run_debate", "Run Debate"),
    ]

    class DebateStartRequested(Message):
        def __init__(self, topic: str, mode: str = "standard", rounds: int = 2, experts: int = 5):
            self.topic = topic
            self.mode = mode
            self.rounds = rounds
            self.experts = experts
            super().__init__()

    def compose(self):
        with Container(id="debate-config"):
            yield Static("[bold]Debate Configuration[/]", id="debate-title")
            yield Input(placeholder="Enter debate topic...", id="debate-topic")
            with Horizontal(id="debate-options"):
                yield Select(
                    [("Standard", "standard"), ("Swarm", "swarm"), ("Court", "court"), ("Dialectic", "dialectic")],
                    prompt="Mode", id="debate-mode", value="standard",
                )
                yield Select(
                    [(str(i), i) for i in range(1, 6)],
                    prompt="Rounds", id="debate-rounds", value=2,
                )
                yield Select(
                    [(str(i), i) for i in [3, 5, 7]],
                    prompt="Experts", id="debate-experts", value=5,
                )
                yield Button("Start Debate", id="debate-start-btn", variant="warning")

        yield VerticalScroll(id="debate-results")
        with Horizontal(id="debate-controls"):
            yield Button("Clear Results", id="debate-clear-btn")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "debate-start-btn":
            self._start_debate()
        elif event.button.id == "debate-clear-btn":
            self.query_one("#debate-results", VerticalScroll).remove_children()

    def _start_debate(self):
        topic = self.query_one("#debate-topic", Input).value.strip()
        if not topic:
            return
        mode = self.query_one("#debate-mode", Select).value or "standard"
        rounds = int(self.query_one("#debate-rounds", Select).value or 2)
        experts = int(self.query_one("#debate-experts", Select).value or 5)
        self.post_message(self.DebateStartRequested(topic, mode, rounds, experts))

    def add_section(self, title: str, content: str):
        results = self.query_one("#debate-results", VerticalScroll)
        results.mount(Static(f"\n[bold yellow]== {title} ==[/]\n"))
        results.mount(Static(content))

    def show_consensus(self, main_proposal: str, confidence: float, rounds: int):
        results = self.query_one("#debate-results", VerticalScroll)
        results.mount(Static(f"\n[bold green]== CONSENSUS (rounds={rounds}, confidence={confidence:.2f}) ==[/]\n"))
        results.mount(Static(main_proposal[:2000]))
        results.scroll_end(animate=False)

    def show_minority(self, reports: list):
        if not reports:
            return
        results = self.query_one("#debate-results", VerticalScroll)
        results.mount(Static(f"\n[bold red]-- Minority Reports ({len(reports)}) --[/]\n"))
        for mr in reports[:5]:
            name = getattr(mr, "expert_name", "unknown")
            content = getattr(mr, "content", str(mr))[:400]
            results.mount(Static(f"[{name}]\n{content}\n"))

    def action_run_debate(self):
        self._start_debate()
