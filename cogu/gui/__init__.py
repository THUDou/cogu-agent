"""COGU GUI — 桌面GUI自动化操作引擎

融合自美团EvoCUA (OSWorld 56.7%开源第一)
核心能力: 截图捕获+光标叠加, smart_resize图像缩放, relative(0-999)坐标映射,
         S2动作空间14种操作, 逐字符type展开, 滑动窗口历史管理
"""
from cogu.gui.screen_capture import ScreenCapture
from cogu.gui.image_processor import ImageProcessor
from cogu.gui.coordinate_mapper import CoordinateMapper
from cogu.gui.action_executor import ActionExecutor
from cogu.gui.gui_agent import EvoCUAAgent

__all__ = [
    "ScreenCapture",
    "ImageProcessor",
    "CoordinateMapper",
    "ActionExecutor",
    "EvoCUAAgent",
]