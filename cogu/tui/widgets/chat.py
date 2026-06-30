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
    """

    def __init__(self, role: str, content: str, timestamp: str = ""):
        super().__init__(classes=role)
        self.role = role

    def compose(self):
        yield Static(self.content, id="msg-content")


class ChatPanel(Container):
    DEFAULT_CSS = """
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
    """

    BINDINGS = [
        Binding("ctrl+n", "new_chat", "New Chat"),
        Binding("ctrl+l", "clear", "Clear"),
        Binding("escape", "focus_input", "Focus"),
    ]

    class MessageSent(Message):
        def __init__(self, text: str):
            self.text = text
            super().__init__()

    def compose(self):
        yield VerticalScroll(id="chat-log")
        with Horizontal(id="chat-input-container"):
            yield Input(placeholder="Type your message... (Ctrl+N=new, Ctrl+L=clear)", id="chat-input")
            yield Button("Send", id="send-btn", variant="primary")

    def on_mount(self):
        self.query_one("#chat-input", Input).focus()
        self.query_one("#send-btn", Button).can_focus = True

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "send-btn":
            self._send()

    def on_input_submitted(self, event: Input.Submitted):
        self._send()

    def _send(self):
        inp = self.query_one("#chat-input", Input)
        text = inp.value.strip()
        if text:
            inp.value = ""
            self.add_message("user", text)
            self.post_message(self.MessageSent(text))

    def add_message(self, role: str, content: str):
        ts = datetime.now().strftime("%H:%M:%S")
        log = self.query_one("#chat-log", VerticalScroll)
        if role == "user":
            log.mount(Static(f"[bold]You[/] [{ts}]\n{content}", classes="user-msg"))
        elif role == "assistant":
            log.mount(Static(f"[bold green]COGU[/] [{ts}]\n{content}", classes="asst-msg"))
        elif role == "system":
            log.mount(Static(f"[italic yellow]System[/] [{ts}]\n{content}", classes="sys-msg"))
        elif role == "thinking":
            log.mount(Static(f"[italic dim]Thinking[/] [{ts}]\n{content}", classes="think-msg"))
        elif role == "tool":
            log.mount(Static(f"[bold blue]Tool[/] [{ts}]\n{content}", classes="tool-msg"))
        elif role == "debate":
            log.mount(Static(f"[bold magenta]Debate[/] [{ts}]\n{content}", classes="debate-msg"))
        log.scroll_end(animate=False)

    def action_new_chat(self):
        log = self.query_one("#chat-log", VerticalScroll)
        log.remove_children()
        self.add_message("system", "New session started.")

    def action_clear(self):
        self.action_new_chat()

    def action_focus_input(self):
        self.query_one("#chat-input", Input).focus()
