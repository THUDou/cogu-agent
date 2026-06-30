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
