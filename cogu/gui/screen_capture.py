"""屏幕截图捕获 + 光标叠加

融合自EvoCUA desktop_env/server/main.py + desktop_env/controllers/python.py
支持Windows/Linux/macOS三平台截图, Windows平台自动叠加鼠标光标
PNG/JPEG magic bytes校验, 重试机制
"""
import ctypes
import logging
import os
import platform
import time
from io import BytesIO
from typing import Optional, Tuple

from PIL import Image, ImageGrab

logger = logging.getLogger("cogu.gui.screen_capture")


class ScreenCapture:
    """跨平台屏幕截图引擎, 支持光标叠加和PNG校验"""

    def __init__(self, retry_times: int = 3, retry_interval: float = 2.0):
        self.retry_times = retry_times
        self.retry_interval = retry_interval
        self._platform = platform.system()

    @staticmethod
    def is_valid_image(data: Optional[bytes]) -> bool:
        """PNG/JPEG magic bytes校验"""
        if not isinstance(data, (bytes, bytearray)) or not data:
            return False
        if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
            return True
        if len(data) >= 3 and data[:3] == b"\xff\xd8\xff":
            return True
        return False

    def capture(self) -> Optional[bytes]:
        """捕获屏幕截图(含光标), 返回PNG bytes"""
        for attempt in range(self.retry_times):
            try:
                img = self._capture_with_cursor()
                if img is not None:
                    buf = BytesIO()
                    img.save(buf, format="PNG")
                    data = buf.getvalue()
                    if self.is_valid_image(data):
                        return data
                    logger.warning("截图校验失败 (attempt %d/%d)", attempt + 1, self.retry_times)
            except Exception as e:
                logger.error("截图捕获异常 (attempt %d/%d): %s", attempt + 1, self.retry_times, e)
            time.sleep(self.retry_interval)
        logger.error("截图捕获最终失败")
        return None

    def capture_image(self) -> Optional[Image.Image]:
        """捕获屏幕截图, 返回PIL Image"""
        data = self.capture()
        if data is None:
            return None
        return Image.open(BytesIO(data))

    def _capture_with_cursor(self) -> Optional[Image.Image]:
        """平台相关的截图+光标叠加"""
        if self._platform == "Windows":
            return self._capture_windows()
        elif self._platform == "Linux":
            return self._capture_linux()
        elif self._platform == "Darwin":
            return self._capture_macos()
        else:
            logger.warning("不支持的平台: %s", self._platform)
            return None

    def _capture_windows(self) -> Optional[Image.Image]:
        """Windows截图: ImageGrab + win32gui光标叠加"""
        try:
            import win32gui
            import win32ui
        except ImportError:
            logger.warning("win32gui/win32ui不可用, 仅截图无光标")
            return ImageGrab.grab(bbox=None, include_layered_windows=True)

        img = ImageGrab.grab(bbox=None, include_layered_windows=True)

        try:
            cursor_img, (hotspotx, hotspoty) = self._get_win32_cursor()
            ratio = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100
            pos_win = win32gui.GetCursorPos()
            pos = (round(pos_win[0] * ratio - hotspotx), round(pos_win[1] * ratio - hotspoty))
            img.paste(cursor_img, pos, cursor_img)
        except Exception as e:
            logger.warning("Windows光标叠加失败: %s", e)

        return img

    @staticmethod
    def _get_win32_cursor() -> Tuple[Image.Image, Tuple[int, int]]:
        """获取Windows鼠标光标图像和热点"""
        import win32gui
        import win32ui

        hcursor = win32gui.GetCursorInfo()[1]
        hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
        hbmp = win32ui.CreateBitmap()
        hbmp.CreateCompatibleBitmap(hdc, 36, 36)
        hdc_mem = hdc.CreateCompatibleDC()
        hdc_mem.SelectObject(hbmp)
        hdc_mem.DrawIcon((0, 0), hcursor)

        bmpinfo = hbmp.GetInfo()
        bmpstr = hbmp.GetBitmapBits(True)
        cursor = Image.frombuffer(
            "RGB", (bmpinfo["bmWidth"], bmpinfo["bmHeight"]),
            bmpstr, "raw", "BGRX", 0, 1
        ).convert("RGBA")

        win32gui.DestroyIcon(hcursor)
        win32gui.DeleteObject(hbmp.GetHandle())
        hdc_mem.DeleteDC()

        pixdata = cursor.load()
        width, height = cursor.size
        for y in range(height):
            for x in range(width):
                if pixdata[x, y] == (0, 0, 0, 255):
                    pixdata[x, y] = (0, 0, 0, 0)

        hotspot = win32gui.GetIconInfo(hcursor)[1:3]
        return cursor, hotspot

    def _capture_linux(self) -> Optional[Image.Image]:
        """Linux截图: pyautogui + Xcursor光标叠加"""
        try:
            import pyautogui
            from pyxcursor import Xcursor
        except ImportError:
            logger.warning("pyautogui/pyxcursor不可用")
            return None

        cursor_obj = Xcursor()
        imgarray = cursor_obj.getCursorImageArrayFast()
        cursor_img = Image.fromarray(imgarray)
        screenshot = pyautogui.screenshot()
        cursor_x, cursor_y = pyautogui.position()
        screenshot.paste(cursor_img, (cursor_x, cursor_y), cursor_img)
        return screenshot

    def _capture_macos(self) -> Optional[Image.Image]:
        """macOS截图: screencapture命令"""
        import subprocess
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmp_path = f.name
        try:
            subprocess.run(["screencapture", "-C", tmp_path], check=True, timeout=15)
            return Image.open(tmp_path)
        except Exception as e:
            logger.error("macOS截图失败: %s", e)
            return None
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)