from textual.widgets import Header, Static
from textual.reactive import reactive
from datetime import datetime


class HeaderBar(Header):
    DEFAULT_CSS = """
    HeaderBar {
        dock: top;
        background: $surface;
        color: $text;
        text-style: bold;
    }
    """

    model: reactive[str] = reactive("deepseek-chat")
    status: reactive[str] = reactive("ready")
    turn_count: reactive[int] = reactive(0)

    def __init__(self):
        super().__init__()
        self.tally = 0

    def render(self) -> str:
        return f" COGU AGENT  [{self.model}]  {self.status}  turns:{self.turn_count}"

    def update_status(self, status: str):
        self.status = status
        self.refresh()

    def increment_turn(self):
        self.turn_count += 1
        self.refresh()
