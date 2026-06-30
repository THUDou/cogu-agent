"""坐标映射引擎 — relative(0-999) ↔ absolute坐标转换

融合自EvoCUA mm_agents/evocua/evocua_agent.py + mm_agents/evocua/utils.py
核心: relative坐标系(0-999虚拟网格)实现跨分辨率泛化,
      absolute坐标系按缩放比例映射, qwen25模式适配ViT
"""
import ast
import logging
import re
from typing import Dict, List, Optional, Tuple

from cogu.gui.image_processor import smart_resize

logger = logging.getLogger("cogu.gui.coordinate_mapper")


class CoordinateMapper:
    """多坐标系映射引擎

    支持三种坐标系:
    - relative: 0-999虚拟网格, 跨分辨率泛化(EvoCUA S2默认)
    - absolute: 像素坐标, 按缩放比例映射
    - qwen25: Qwen2.5-VL专用, 基于smart_resize后的像素坐标
    """

    def __init__(
        self,
        coordinate_type: str = "relative",
        screen_size: Tuple[int, int] = (1920, 1080),
        resize_factor: int = 28,
    ):
        self.coordinate_type = coordinate_type
        self.screen_size = screen_size
        self.resize_factor = resize_factor

    def to_absolute(
        self,
        x: float,
        y: float,
        original_width: Optional[int] = None,
        original_height: Optional[int] = None,
        processed_width: Optional[int] = None,
        processed_height: Optional[int] = None,
    ) -> Tuple[int, int]:
        """将模型预测坐标转换为屏幕绝对坐标"""
        if not (original_width and original_height):
            original_width, original_height = self.screen_size

        if self.coordinate_type == "relative":
            x_scale = original_width / 999
            y_scale = original_height / 999
            return int(x * x_scale), int(y * y_scale)

        elif self.coordinate_type == "absolute":
            if processed_width and processed_height:
                x_scale = original_width / processed_width
                y_scale = original_height / processed_height
                return int(x * x_scale), int(y * y_scale)
            return int(x), int(y)

        elif self.coordinate_type == "qwen25":
            resized_h, resized_w = smart_resize(
                height=original_height,
                width=original_width,
                factor=self.resize_factor,
            )
            if 0 <= x <= 1 and 0 <= y <= 1:
                return int(round(x * resized_w)), int(round(y * resized_h))
            return int(x / resized_w * original_width), int(y / resized_h * original_height)

        raise ValueError(f"未知坐标系: {self.coordinate_type}")

    def from_absolute(
        self,
        x: int,
        y: int,
        original_width: Optional[int] = None,
        original_height: Optional[int] = None,
    ) -> Tuple[float, float]:
        """将屏幕绝对坐标转换为模型坐标系"""
        if not (original_width and original_height):
            original_width, original_height = self.screen_size

        if self.coordinate_type == "relative":
            return x / original_width * 999, y / original_height * 999

        elif self.coordinate_type == "absolute":
            return float(x), float(y)

        elif self.coordinate_type == "qwen25":
            resized_h, resized_w = smart_resize(
                height=original_height,
                width=original_width,
                factor=self.resize_factor,
            )
            return x / resized_w, y / resized_h

        raise ValueError(f"未知坐标系: {self.coordinate_type}")

    def rewrite_code_coordinates(
        self,
        pyautogui_code: str,
        original_width: Optional[int] = None,
        original_height: Optional[int] = None,
    ) -> str:
        """重写pyautogui代码中的坐标为绝对坐标

        解析pyautogui调用, 提取x/y参数, 投影到绝对坐标系后替换
        """
        if not (original_width and original_height):
            original_width, original_height = self.screen_size

        function_parameters = {
            "click": ["x", "y", "clicks", "interval", "button", "duration", "pause"],
            "rightClick": ["x", "y", "duration", "tween", "pause"],
            "middleClick": ["x", "y", "duration", "tween", "pause"],
            "doubleClick": ["x", "y", "interval", "button", "duration", "pause"],
            "tripleClick": ["x", "y", "interval", "button", "duration", "pause"],
            "moveTo": ["x", "y", "duration", "tween", "pause"],
            "dragTo": ["x", "y", "duration", "button", "mouseDownUp", "pause"],
        }

        pattern = r"(pyautogui\.\w+)\((.*)\)"
        new_code = pyautogui_code

        for full_call in re.findall(r"(pyautogui\.\w+\([^\)]*\))", pyautogui_code):
            func_match = re.match(pattern, full_call, re.DOTALL)
            if not func_match:
                continue

            func_name = func_match.group(1)
            args_str = func_match.group(2)

            try:
                parsed = ast.parse(f"func({args_str})").body[0].value
            except SyntaxError:
                continue

            func_base = func_name.split(".")[-1]
            param_names = function_parameters.get(func_base, [])
            if not param_names:
                continue

            args = {}
            for idx, arg in enumerate(parsed.args):
                if idx < len(param_names):
                    try:
                        args[param_names[idx]] = ast.literal_eval(arg)
                    except Exception:
                        pass

            try:
                for kw in parsed.keywords:
                    args[kw.arg] = ast.literal_eval(kw.value)
            except Exception:
                continue

            if "x" in args and "y" in args:
                try:
                    x_abs, y_abs = self.to_absolute(
                        float(args["x"]), float(args["y"]),
                        original_width, original_height,
                    )
                    args["x"] = x_abs
                    args["y"] = y_abs
                except (ValueError, TypeError):
                    continue

                reconstructed = []
                for idx, pname in enumerate(param_names):
                    if pname in args:
                        val = args[pname]
                        reconstructed.append(f"'{val}'" if isinstance(val, str) else str(val))
                    else:
                        break

                used = set(param_names[:len(reconstructed)])
                for kw in parsed.keywords:
                    if kw.arg not in used:
                        val = args[kw.arg]
                        reconstructed.append(f"{kw.arg}='{val}'" if isinstance(val, str) else f"{kw.arg}={val}")

                new_call = f"{func_name}({', '.join(reconstructed)})"
                new_code = new_code.replace(full_call, new_call)

        return new_code