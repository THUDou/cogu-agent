"""
COGU GUI Agent — 参考 CogAgent (清华KEG+智谱AI) 的 Action Space 设计

Action Space 定义:
  鼠标操作: CLICK, DOUBLE_CLICK, RIGHT_CLICK, HOVER
  文本输入: TYPE
  滚动操作: SCROLL_UP, SCROLL_DOWN, SCROLL_LEFT, SCROLL_RIGHT
  键盘按键: KEY_PRESS
  组合键:   GESTURE (KEY_DOWN + KEY_PRESS + KEY_UP)
  启动应用: LAUNCH
  引用文本: QUOTE_TEXT (OCR)
  引用剪贴板: QUOTE_CLIPBOARD
  调用LLM:  LLM (嵌套推理)
  截图:     SCREENSHOT
  结束:     END

坐标系统: box=[[x1,y1,x2,y2]], 值范围 000-999 (归一化坐标 * 1000)
"""

import asyncio
import base64
import io
import os
import platform
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from cogu.tools.base import FunctionTool, ToolRegistry, ToolCapability


class GUIAction(Enum):
    CLICK = "CLICK"
    DOUBLE_CLICK = "DOUBLE_CLICK"
    RIGHT_CLICK = "RIGHT_CLICK"
    HOVER = "HOVER"
    TYPE = "TYPE"
    SCROLL_UP = "SCROLL_UP"
    SCROLL_DOWN = "SCROLL_DOWN"
    SCROLL_LEFT = "SCROLL_LEFT"
    SCROLL_RIGHT = "SCROLL_RIGHT"
    KEY_PRESS = "KEY_PRESS"
    GESTURE = "GESTURE"
    LAUNCH = "LAUNCH"
    QUOTE_TEXT = "QUOTE_TEXT"
    QUOTE_CLIPBOARD = "QUOTE_CLIPBOARD"
    SCREENSHOT = "SCREENSHOT"
    END = "END"


@dataclass
class GUIOperation:
    action: GUIAction
    box: Optional[List[int]] = None
    text: Optional[str] = None
    key: Optional[str] = None
    element_type: Optional[str] = None
    element_info: Optional[str] = None
    step_count: int = 3
    app: Optional[str] = None
    url: Optional[str] = None
    output_var: Optional[str] = None
    sensitive: bool = False

    def box_to_screen_coords(self, screen_width: int = None, screen_height: int = None) -> Optional[Tuple[int, int]]:
        if self.box is None or screen_width is None:
            return None
        if screen_height is None:
            screen_height = screen_width
        x1, y1, x2, y2 = [v / 1000 for v in self.box]
        px1 = int(x1 * screen_width)
        py1 = int(y1 * screen_height)
        px2 = int(x2 * screen_width)
        py2 = int(y2 * screen_height)
        return ((px1 + px2) // 2, (py1 + py2) // 2)


@dataclass
class GUIActionResult:
    success: bool
    action: GUIAction
    message: str = ""
    data: Any = None
    screenshot_path: Optional[str] = None


def _identify_os() -> str:
    os_detail = platform.platform().lower()
    if "mac" in os_detail or "darwin" in os_detail:
        return "Mac"
    elif "windows" in os_detail or "win" in os_detail:
        return "Win"
    elif "linux" in os_detail:
        return "Linux"
    return "Unknown"


def _get_screen_size() -> Tuple[int, int]:
    try:
        import pyautogui
        return pyautogui.size()
    except ImportError:
        return (1920, 1080)


def _parse_grounded_operation(text: str) -> Optional[GUIOperation]:
    if not text or "(" not in text:
        return None

    try:
        op_name, detail = text.split("(", 1)
        detail = "(" + detail
        op_name = op_name.strip()

        action = None
        for a in GUIAction:
            if a.value == op_name:
                action = a
                break
        if action is None:
            return None

        kwargs = {}

        box_pattern = __import__("re").findall(r"box=\[\[(.*?)\]\]", detail)
        if box_pattern:
            kwargs["box"] = list(map(int, box_pattern[0].split(",")))

        text_pattern = __import__("re").findall(r"text='(.*?)'", detail)
        if text_pattern:
            kwargs["text"] = text_pattern[0]

        key_pattern = __import__("re").findall(r"key='(.*?)'", detail)
        if key_pattern:
            kwargs["key"] = key_pattern[0]

        et_pattern = __import__("re").findall(r"element_type='(.*?)'", detail)
        if et_pattern:
            kwargs["element_type"] = et_pattern[0]

        ei_pattern = __import__("re").findall(r"element_info='(.*?)'", detail)
        if ei_pattern:
            kwargs["element_info"] = ei_pattern[0]

        sc_pattern = __import__("re").findall(r"step_count=(\d+)", detail)
        if sc_pattern:
            kwargs["step_count"] = int(sc_pattern[0])

        app_pattern = __import__("re").findall(r"app='(.*?)'", detail)
        if app_pattern:
            kwargs["app"] = app_pattern[0]

        url_pattern = __import__("re").findall(r"url='(.*?)'", detail)
        if url_pattern:
            kwargs["url"] = url_pattern[0]

        out_pattern = __import__("re").findall(r"output='(.*?)'", detail)
        if out_pattern:
            kwargs["output_var"] = out_pattern[0]

        return GUIOperation(action=action, **kwargs)
    except Exception:
        return None


class GUIAgentExecutor:
    def __init__(self):
        self._os = _identify_os()
        self._variables: Dict[str, str] = {}

    def _resolve_variables(self, text: str) -> str:
        import re
        def replace_var(match):
            var_name = match.group(1)
            return self._variables.get(var_name, match.group(0))
        return re.sub(r"__CogName_(\w+)__", replace_var, text)

    async def execute(self, operation: GUIOperation) -> GUIActionResult:
        try:
            import pyautogui
            pyautogui.FAILSAFE = True
            pyautogui.PAUSE = 0.3
        except ImportError:
            return GUIActionResult(
                success=False, action=operation.action,
                message="pyautogui not installed. Run: pip install pyautogui"
            )

        handler = {
            GUIAction.CLICK: self._click,
            GUIAction.DOUBLE_CLICK: self._double_click,
            GUIAction.RIGHT_CLICK: self._right_click,
            GUIAction.HOVER: self._hover,
            GUIAction.TYPE: self._type,
            GUIAction.SCROLL_UP: self._scroll_up,
            GUIAction.SCROLL_DOWN: self._scroll_down,
            GUIAction.KEY_PRESS: self._key_press,
            GUIAction.LAUNCH: self._launch,
            GUIAction.SCREENSHOT: self._screenshot,
            GUIAction.QUOTE_CLIPBOARD: self._quote_clipboard,
            GUIAction.END: self._end,
        }.get(operation.action)

        if handler is None:
            return GUIActionResult(
                success=False, action=operation.action,
                message=f"Action {operation.action.value} not implemented yet"
            )

        return await handler(operation)

    async def _click(self, op: GUIOperation) -> GUIActionResult:
        import pyautogui
        w, h = _get_screen_size()
        coords = op.box_to_screen_coords(w, h)
        if coords:
            pyautogui.click(coords[0], coords[1])
            return GUIActionResult(success=True, action=op.action, message=f"Clicked at {coords}")
        return GUIActionResult(success=False, action=op.action, message="No box coordinates")

    async def _double_click(self, op: GUIOperation) -> GUIActionResult:
        import pyautogui
        w, h = _get_screen_size()
        coords = op.box_to_screen_coords(w, h)
        if coords:
            pyautogui.doubleClick(coords[0], coords[1])
            return GUIActionResult(success=True, action=op.action, message=f"Double-clicked at {coords}")
        return GUIActionResult(success=False, action=op.action, message="No box coordinates")

    async def _right_click(self, op: GUIOperation) -> GUIActionResult:
        import pyautogui
        w, h = _get_screen_size()
        coords = op.box_to_screen_coords(w, h)
        if coords:
            pyautogui.rightClick(coords[0], coords[1])
            return GUIActionResult(success=True, action=op.action, message=f"Right-clicked at {coords}")
        return GUIActionResult(success=False, action=op.action, message="No box coordinates")

    async def _hover(self, op: GUIOperation) -> GUIActionResult:
        import pyautogui
        w, h = _get_screen_size()
        coords = op.box_to_screen_coords(w, h)
        if coords:
            pyautogui.moveTo(coords[0], coords[1])
            return GUIActionResult(success=True, action=op.action, message=f"Hovered at {coords}")
        return GUIActionResult(success=False, action=op.action, message="No box coordinates")

    async def _type(self, op: GUIOperation) -> GUIActionResult:
        import pyautogui
        if op.text is None:
            return GUIActionResult(success=False, action=op.action, message="No text provided")
        resolved_text = self._resolve_variables(op.text)
        w, h = _get_screen_size()
        coords = op.box_to_screen_coords(w, h)
        if coords:
            pyautogui.click(coords[0], coords[1])
            time.sleep(0.2)
        pyautogui.write(resolved_text, interval=0.02)
        return GUIActionResult(success=True, action=op.action, message=f"Typed: {resolved_text[:50]}")

    async def _scroll_up(self, op: GUIOperation) -> GUIActionResult:
        import pyautogui
        w, h = _get_screen_size()
        coords = op.box_to_screen_coords(w, h)
        if coords:
            pyautogui.moveTo(coords[0], coords[1])
        pyautogui.scroll(op.step_count * 3)
        return GUIActionResult(success=True, action=op.action, message=f"Scrolled up {op.step_count} steps")

    async def _scroll_down(self, op: GUIOperation) -> GUIActionResult:
        import pyautogui
        w, h = _get_screen_size()
        coords = op.box_to_screen_coords(w, h)
        if coords:
            pyautogui.moveTo(coords[0], coords[1])
        pyautogui.scroll(-op.step_count * 3)
        return GUIActionResult(success=True, action=op.action, message=f"Scrolled down {op.step_count} steps")

    async def _key_press(self, op: GUIOperation) -> GUIActionResult:
        import pyautogui
        if op.key is None:
            return GUIActionResult(success=False, action=op.action, message="No key provided")
        pyautogui.press(op.key)
        return GUIActionResult(success=True, action=op.action, message=f"Pressed key: {op.key}")

    async def _launch(self, op: GUIOperation) -> GUIActionResult:
        if op.url and op.url.lower() not in ("none", ""):
            import webbrowser
            webbrowser.open(op.url)
            return GUIActionResult(success=True, action=op.action, message=f"Opened URL: {op.url}")
        if op.app and op.app.lower() not in ("none", ""):
            if self._os == "Mac":
                os.system(f"open -a '{op.app}'")
            elif self._os == "Win":
                os.startfile(op.app)
            elif self._os == "Linux":
                os.system(f"xdg-open '{op.app}'")
            return GUIActionResult(success=True, action=op.action, message=f"Launched: {op.app}")
        return GUIActionResult(success=False, action=op.action, message="No app or URL provided")

    async def _screenshot(self, op: GUIOperation) -> GUIActionResult:
        try:
            import pyautogui
            from PIL import Image
            img = pyautogui.screenshot()
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            return GUIActionResult(
                success=True, action=op.action,
                message="Screenshot captured",
                data=f"data:image/png;base64,{b64}"
            )
        except ImportError:
            return GUIActionResult(success=False, action=op.action, message="PIL not installed")

    async def _quote_clipboard(self, op: GUIOperation) -> GUIActionResult:
        try:
            import pyperclip
            content = pyperclip.paste()
            if op.output_var:
                self._variables[op.output_var] = content
            return GUIActionResult(success=True, action=op.action, message=f"Clipboard: {content[:100]}", data=content)
        except ImportError:
            return GUIActionResult(success=False, action=op.action, message="pyperclip not installed")

    async def _end(self, op: GUIOperation) -> GUIActionResult:
        return GUIActionResult(success=True, action=op.action, message="Task completed")


_gui_executor = GUIAgentExecutor()


async def _gui_click(box: str, element_type: str = "", element_info: str = "") -> str:
    nums = [int(x.strip()) for x in box.replace("[[", "").replace("]]", "").split(",")]
    op = GUIOperation(action=GUIAction.CLICK, box=nums, element_type=element_type, element_info=element_info)
    result = await _gui_executor.execute(op)
    return result.message


async def _gui_type(box: str, text: str, element_type: str = "", element_info: str = "") -> str:
    nums = [int(x.strip()) for x in box.replace("[[", "").replace("]]", "").split(",")]
    op = GUIOperation(action=GUIAction.TYPE, box=nums, text=text, element_type=element_type, element_info=element_info)
    result = await _gui_executor.execute(op)
    return result.message


async def _gui_scroll(box: str, direction: str = "down", step_count: int = 3) -> str:
    nums = [int(x.strip()) for x in box.replace("[[", "").replace("]]", "").split(",")]
    action = GUIAction.SCROLL_DOWN if direction == "down" else GUIAction.SCROLL_UP
    op = GUIOperation(action=action, box=nums, step_count=step_count)
    result = await _gui_executor.execute(op)
    return result.message


async def _gui_key_press(key: str) -> str:
    op = GUIOperation(action=GUIAction.KEY_PRESS, key=key)
    result = await _gui_executor.execute(op)
    return result.message


async def _gui_screenshot() -> str:
    op = GUIOperation(action=GUIAction.SCREENSHOT)
    result = await _gui_executor.execute(op)
    if result.success:
        return f"Screenshot captured (base64, {len(result.data)} chars)"
    return result.message


async def _gui_launch(app: str = "", url: str = "") -> str:
    op = GUIOperation(action=GUIAction.LAUNCH, app=app, url=url)
    result = await _gui_executor.execute(op)
    return result.message


async def _gui_parse_and_execute(operation_text: str) -> str:
    op = _parse_grounded_operation(operation_text)
    if op is None:
        return f"Failed to parse operation: {operation_text}"
    result = await _gui_executor.execute(op)
    status = "OK" if result.success else "FAIL"
    return f"[{status}] {result.action.value}: {result.message}"


def register_gui_tools(registry: ToolRegistry):
    registry.register(
        FunctionTool(_gui_click, name="gui_click",
                     description="Click at screen position. box format: 'x1,y1,x2,y2' (000-999 normalized coords * 1000). Ref: CogAgent Action Space.")
        .with_capability(ToolCapability.EXECUTES_CODE).with_group("gui")
    )
    registry.register(
        FunctionTool(_gui_type, name="gui_type",
                     description="Type text at screen position. box format: 'x1,y1,x2,y2'. Supports __CogName_xxx__ variables.")
        .with_capability(ToolCapability.EXECUTES_CODE).with_group("gui")
    )
    registry.register(
        FunctionTool(_gui_scroll, name="gui_scroll",
                     description="Scroll at screen position. direction: up/down. box format: 'x1,y1,x2,y2'.")
        .with_capability(ToolCapability.EXECUTES_CODE).with_group("gui")
    )
    registry.register(
        FunctionTool(_gui_key_press, name="gui_key_press",
                     description="Press a keyboard key. Supports: Return, Space, Tab, Up, Down, Left, Right, F1-F12, etc.")
        .with_capability(ToolCapability.EXECUTES_CODE).with_group("gui")
    )
    registry.register(
        FunctionTool(_gui_screenshot, name="gui_screenshot",
                     description="Capture current screen screenshot. Returns base64 encoded PNG image.")
        .with_capability(ToolCapability.READ_ONLY).with_group("gui")
    )
    registry.register(
        FunctionTool(_gui_launch, name="gui_launch",
                     description="Launch an application or open a URL in browser.")
        .with_capability(ToolCapability.EXECUTES_CODE).with_group("gui")
    )
    registry.register(
        FunctionTool(_gui_parse_and_execute, name="gui_execute",
                     description="Parse and execute a CogAgent-style grounded operation string, e.g. CLICK(box=[[387,248,727,317]], element_type='button')")
        .with_capability(ToolCapability.EXECUTES_CODE).with_group("gui")
    )