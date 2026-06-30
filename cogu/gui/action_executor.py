"""动作执行引擎 — S2动作空间14种操作 + pyautogui执行 + 逐字符type

融合自EvoCUA mm_agents/evocua/evocua_agent.py + mm_agents/evocua/utils.py
S2动作空间: key, type, mouse_move, left_click, left_click_drag, right_click,
           middle_click, double_click, triple_click, scroll, wait, terminate,
           key_down, key_up
逐字符type展开: 解决pyautogui.write不支持特殊字符的问题
"""
import ast
import json
import logging
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("cogu.gui.action_executor")

S2_ACTION_DESCRIPTION = """
* `key`: Performs key down presses on the arguments passed in order, then performs key releases in reverse order.
* `key_down`: Press and HOLD the specified key(s) down in order (no release).
* `key_up`: Release the specified key(s) in reverse order.
* `type`: Type a string of text on the keyboard.
* `mouse_move`: Move the cursor to a specified (x, y) pixel coordinate on the screen.
* `left_click`: Click the left mouse button at a specified (x, y) pixel coordinate on the screen.
* `left_click_drag`: Click and drag the cursor to a specified (x, y) pixel coordinate on the screen.
* `right_click`: Click the right mouse button at a specified (x, y) pixel coordinate on the screen.
* `middle_click`: Click the middle mouse button at a specified (x, y) pixel coordinate on the screen.
* `double_click`: Double-click the left mouse button at a specified (x, y) pixel coordinate on the screen.
* `triple_click`: Triple-click the left mouse button at a specified (x, y) pixel coordinate on the screen.
* `scroll`: Performs a scroll of the mouse scroll wheel.
* `wait`: Wait specified seconds for the change to happen.
* `terminate`: Terminate the current task and report its completion status.
"""

S2_TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "computer_use",
        "description": "Use a mouse and keyboard to interact with a computer.",
        "parameters": {
            "properties": {
                "action": {
                    "description": S2_ACTION_DESCRIPTION,
                    "enum": [
                        "key", "type", "mouse_move", "left_click", "left_click_drag",
                        "right_click", "middle_click", "double_click", "triple_click",
                        "scroll", "wait", "terminate", "key_down", "key_up",
                    ],
                    "type": "string",
                },
                "keys": {"description": "Required only by action=key.", "type": "array"},
                "text": {"description": "Required only by action=type.", "type": "string"},
                "coordinate": {"description": "The x,y coordinates for mouse actions.", "type": "array"},
                "pixels": {"description": "The amount of scrolling.", "type": "number"},
                "time": {"description": "The seconds to wait.", "type": "number"},
                "status": {"description": "The status of the task.", "type": "string", "enum": ["success", "failure"]},
            },
            "required": ["action"],
            "type": "object",
        },
    },
}


def _clean_keys(raw_keys) -> List[str]:
    """清洗按键参数"""
    keys = raw_keys if isinstance(raw_keys, list) else [raw_keys]
    cleaned = []
    for key in keys:
        if isinstance(key, str):
            if key.startswith("keys=["):
                key = key[6:]
            if key.endswith("]"):
                key = key[:-1]
            if key.startswith("['") or key.startswith('["'):
                key = key[2:] if len(key) > 2 else key
            if key.endswith("']") or key.endswith('"]'):
                key = key[:-2] if len(key) > 2 else key
            key = key.strip()
            cleaned.append(key)
        else:
            cleaned.append(key)
    return cleaned


def expand_type_to_presses(text: str) -> str:
    """逐字符展开type操作为pyautogui.press调用

    解决pyautogui.write不支持特殊字符(换行/引号/反斜杠等)的问题
    """
    result = ""
    for char in text:
        if char == "\n":
            result += "pyautogui.press('enter')\n"
        elif char == "'":
            result += 'pyautogui.press("\'")\n'
        elif char == "\\":
            result += "pyautogui.press('\\\\')\n"
        elif char == '"':
            result += "pyautogui.press('\"')\n"
        else:
            result += f"pyautogui.press('{char}')\n"
    return result


def rewrite_pyautogui_text_inputs(code: str) -> str:
    """将pyautogui.write/typewrite展开为逐字符press调用(AST模式)"""
    try:
        tree = ast.parse(code)

        class _TextCallRewriter(ast.NodeTransformer):
            def _extract_text(self, call: ast.Call):
                if not (
                    isinstance(call.func, ast.Attribute)
                    and isinstance(call.func.value, ast.Name)
                    and call.func.value.id == "pyautogui"
                    and call.func.attr in ("write", "typewrite")
                ):
                    return None
                message_node = call.args[0] if call.args else None
                if message_node is None:
                    for kw in call.keywords:
                        if kw.arg in ("message", "text"):
                            message_node = kw.value
                            break
                if isinstance(message_node, ast.Constant) and isinstance(message_node.value, str):
                    return message_node.value
                return None

            def visit_Expr(self, node):
                self.generic_visit(node)
                if isinstance(node.value, ast.Call):
                    text = self._extract_text(node.value)
                    if text is not None:
                        new_nodes = []
                        for char in text:
                            press_value = "enter" if char == "\n" else char
                            press_call = ast.Expr(
                                value=ast.Call(
                                    func=ast.Attribute(
                                        value=ast.Name(id="pyautogui", ctx=ast.Load()),
                                        attr="press",
                                        ctx=ast.Load(),
                                    ),
                                    args=[ast.Constant(value=press_value)],
                                    keywords=[],
                                )
                            )
                            new_nodes.append(press_call)
                        return new_nodes if new_nodes else node
                return node

        tree = _TextCallRewriter().visit(tree)
        tree = ast.fix_missing_locations(tree)
        return ast.unparse(tree)

    except (SyntaxError, Exception):
        return _fallback_rewrite(code)


def _fallback_rewrite(code: str) -> str:
    """Regex回退: 展开pyautogui.write/typewrite"""
    def _replacer(match):
        call_content = match.group(0)
        m = re.search(r"pyautogui\.(?:write|typewrite)\s*\(", call_content)
        if not m:
            return call_content
        args_part = call_content[m.end():].strip()
        args_part = re.sub(r"^(?:message|text)\s*=\s*", "", args_part)

        text_content = ""
        if args_part.startswith(("'''", '"""')):
            quote_type = args_part[:3]
            content = args_part[3:]
            end_idx = content.rfind(quote_type)
            text_content = content[:end_idx] if end_idx != -1 else content
        elif args_part.startswith(("'", '"')):
            quote_type = args_part[0]
            content = args_part[1:]
            if content.endswith(quote_type + ")"):
                text_content = content[:-2]
            elif content.endswith(")"):
                text_content = content[:-1]
            else:
                text_content = content
        else:
            text_content = args_part[:-1] if args_part.endswith(")") else args_part

        new_cmds = []
        for char in text_content:
            p = "enter" if char == "\n" else char
            p_esc = p.replace("'", "\\'")
            new_cmds.append(f"pyautogui.press('{p_esc}')")
        return "; ".join(new_cmds)

    pattern = r"pyautogui\.(?:write|typewrite)\s*\(.*?(?=\s*;|\s*$|\n)"
    new_code = re.sub(pattern, _replacer, code)
    if new_code == code and ("pyautogui.write" in code or "pyautogui.typewrite" in code):
        new_code = re.sub(r"pyautogui\.(?:write|typewrite)\s*\(.*", _replacer, code)
    return new_code


class ActionExecutor:
    """S2动作空间解析与执行引擎"""

    def __init__(self, coordinate_mapper=None):
        self.coordinate_mapper = coordinate_mapper

    def parse_response(
        self,
        response: str,
        original_width: int = 1920,
        original_height: int = 1080,
        processed_width: Optional[int] = None,
        processed_height: Optional[int] = None,
    ) -> Tuple[str, List[str]]:
        """解析LLM响应为低级动作指令和pyautogui代码

        Returns:
            (low_level_instruction, pyautogui_code_list)
        """
        low_level_instruction = ""
        pyautogui_code: List[str] = []

        if response is None or not response.strip():
            return low_level_instruction, pyautogui_code

        def adjust_coordinates(x: float, y: float) -> Tuple[int, int]:
            if self.coordinate_mapper:
                return self.coordinate_mapper.to_absolute(
                    x, y, original_width, original_height,
                    processed_width, processed_height,
                )
            return int(x), int(y)

        def process_tool_call(json_str: str) -> None:
            try:
                tool_call = json.loads(json_str)
                if tool_call.get("name") != "computer_use":
                    return
                args = tool_call["arguments"]
                action = args["action"]

                if action in ("left_click", "click"):
                    if "coordinate" in args:
                        x, y = args["coordinate"]
                        adj_x, adj_y = adjust_coordinates(x, y)
                        pyautogui_code.append(f"pyautogui.click({adj_x}, {adj_y})")
                    else:
                        pyautogui_code.append("pyautogui.click()")

                elif action == "right_click":
                    if "coordinate" in args:
                        x, y = args["coordinate"]
                        adj_x, adj_y = adjust_coordinates(x, y)
                        pyautogui_code.append(f"pyautogui.rightClick({adj_x}, {adj_y})")
                    else:
                        pyautogui_code.append("pyautogui.rightClick()")

                elif action == "middle_click":
                    if "coordinate" in args:
                        x, y = args["coordinate"]
                        adj_x, adj_y = adjust_coordinates(x, y)
                        pyautogui_code.append(f"pyautogui.middleClick({adj_x}, {adj_y})")
                    else:
                        pyautogui_code.append("pyautogui.middleClick()")

                elif action == "double_click":
                    if "coordinate" in args:
                        x, y = args["coordinate"]
                        adj_x, adj_y = adjust_coordinates(x, y)
                        pyautogui_code.append(f"pyautogui.doubleClick({adj_x}, {adj_y})")
                    else:
                        pyautogui_code.append("pyautogui.doubleClick()")

                elif action == "triple_click":
                    if "coordinate" in args:
                        x, y = args["coordinate"]
                        adj_x, adj_y = adjust_coordinates(x, y)
                        pyautogui_code.append(f"pyautogui.tripleClick({adj_x}, {adj_y})")
                    else:
                        pyautogui_code.append("pyautogui.tripleClick()")

                elif action == "type":
                    text = args.get("text", "")
                    pyautogui_code.append(expand_type_to_presses(text))

                elif action == "key":
                    keys = _clean_keys(args.get("keys", []))
                    keys_str = ", ".join([f"'{key}'" for key in keys])
                    if len(keys) > 1:
                        pyautogui_code.append(f"pyautogui.hotkey({keys_str})")
                    else:
                        pyautogui_code.append(f"pyautogui.press({keys_str})")

                elif action == "key_down":
                    keys = _clean_keys(args.get("keys", []))
                    for k in keys:
                        pyautogui_code.append(f"pyautogui.keyDown('{k}')")

                elif action == "key_up":
                    keys = _clean_keys(args.get("keys", []))
                    for k in reversed(keys):
                        pyautogui_code.append(f"pyautogui.keyUp('{k}')")

                elif action == "scroll":
                    pixels = args.get("pixels", 0)
                    pyautogui_code.append(f"pyautogui.scroll({pixels})")

                elif action == "wait":
                    pyautogui_code.append("WAIT")

                elif action == "terminate":
                    status = args.get("status", "success")
                    pyautogui_code.append("FAIL" if str(status).lower() == "failure" else "DONE")

                elif action == "mouse_move":
                    if "coordinate" in args:
                        x, y = args["coordinate"]
                        adj_x, adj_y = adjust_coordinates(x, y)
                        pyautogui_code.append(f"pyautogui.moveTo({adj_x}, {adj_y})")
                    else:
                        pyautogui_code.append("pyautogui.moveTo(0, 0)")

                elif action == "left_click_drag":
                    if "coordinate" in args:
                        x, y = args["coordinate"]
                        adj_x, adj_y = adjust_coordinates(x, y)
                        duration = args.get("duration", 0.5)
                        pyautogui_code.append(f"pyautogui.dragTo({adj_x}, {adj_y}, duration={duration})")
                    else:
                        pyautogui_code.append("pyautogui.dragTo(0, 0)")

            except (json.JSONDecodeError, KeyError) as e:
                logger.error("工具调用解析失败: %s", e)

        lines = response.split("\n")
        inside_tool_call = False
        current_tool_call: List[str] = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.lower().startswith("action:"):
                if not low_level_instruction:
                    low_level_instruction = line.split("Action:")[-1].strip()
                continue

            if line.startswith("<tool_call>"):
                inside_tool_call = True
                continue
            elif line.startswith("</tool_call>"):
                if current_tool_call:
                    process_tool_call("\n".join(current_tool_call))
                    current_tool_call = []
                inside_tool_call = False
                continue

            if inside_tool_call:
                current_tool_call.append(line)
                continue

            if line.startswith("{") and line.endswith("}"):
                try:
                    json_obj = json.loads(line)
                    if "name" in json_obj and "arguments" in json_obj:
                        process_tool_call(line)
                except json.JSONDecodeError:
                    pass

        if current_tool_call:
            process_tool_call("\n".join(current_tool_call))

        if not low_level_instruction and pyautogui_code:
            first_action = pyautogui_code[0]
            if "." in first_action:
                action_type = first_action.split(".", 1)[1].split("(", 1)[0]
            else:
                action_type = first_action.lower()
            low_level_instruction = f"Performing {action_type} action"

        return low_level_instruction, pyautogui_code

    @staticmethod
    def execute(code_list: List[str]) -> List[bool]:
        """执行pyautogui代码列表"""
        import pyautogui

        results = []
        for code in code_list:
            try:
                if code in ("DONE", "FAIL", "WAIT"):
                    results.append(True)
                    continue
                exec(code, {"pyautogui": pyautogui})
                results.append(True)
            except Exception as e:
                logger.error("执行失败 [%s]: %s", code[:80], e)
                results.append(False)
        return results