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
