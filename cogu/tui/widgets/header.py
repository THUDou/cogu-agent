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
