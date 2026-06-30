from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Static, Input, RichLog, Label, Button
from textual.reactive import reactive
from textual.binding import Binding
from textual.message import Message
from datetime import datetime


class MessageRow(Container):
    DEFAULT_CSS = """
    MessageRow {
        padding: 1 2;
        width: 100%;
    }
    MessageRow.user {
        background: $surface;
        border-left: solid $primary;
    }
    MessageRow.assistant {
        background: $panel;
        border-left: solid $success;
    }
    MessageRow.system {
        background: $panel-darken-1;
        border-left: solid $warning;
    }
    ChatPanel {
        height: 1fr;
        layout: vertical;
    }
    ChatPanel VerticalScroll {
        height: 1fr;
        border: solid $primary;
        padding: 0 1;
    }
    ChatPanel #chat-input-container {
        height: auto;
        dock: bottom;
        padding: 1 0;
    }
    ChatPanel #chat-input {
        width: 1fr;
    }
