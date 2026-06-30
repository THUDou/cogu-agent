"""图像处理引擎 — smart_resize缩放 + base64编码

融合自EvoCUA mm_agents/utils/qwen_vl_utils.py + mm_agents/evocua/utils.py
核心算法: smart_resize保证长宽被factor整除, 像素数在[min_pixels, max_pixels]内,
         最长边限制, 保持长宽比不变
"""
import base64
import math
import logging
from io import BytesIO
from typing import Tuple

from PIL import Image

logger = logging.getLogger("cogu.gui.image_processor")


def _round_by_factor(number: int, factor: int) -> int:
    return round(number / factor) * factor


def _ceil_by_factor(number: int, factor: int) -> int:
    return math.ceil(number / factor) * factor


def _floor_by_factor(number: int, factor: int) -> int:
    return math.floor(number / factor) * factor


def smart_resize(
    height: int,
    width: int,
    factor: int = 28,
    min_pixels: int = 56 * 56,
    max_pixels: int = 14 * 14 * 4 * 1280,
    max_long_side: int = 8192,
) -> Tuple[int, int]:
    """智能缩放算法 — 保证ViT兼容性

    规则:
    1. 长宽能被factor整除
    2. pixels总数在[min_pixels, max_pixels]内
    3. 最长边限制在max_long_side内
    4. 保持长宽比基本不变
    """
    if height < 2 or width < 2:
        raise ValueError(f"height:{height} or width:{width} must be larger than factor:{factor}")
    if max(height, width) / min(height, width) > 200:
        raise ValueError(f"aspect ratio must be < 200, got {height}/{width}")

    if max(height, width) > max_long_side:
        beta = max(height, width) / max_long_side
        height, width = int(height / beta), int(width / beta)

    h_bar = _round_by_factor(height, factor)
    w_bar = _round_by_factor(width, factor)

    if h_bar * w_bar > max_pixels:
        beta = math.sqrt((height * width) / max_pixels)
        h_bar = _floor_by_factor(int(height / beta), factor)
        w_bar = _floor_by_factor(int(width / beta), factor)
    elif h_bar * w_bar < min_pixels:
        beta = math.sqrt(min_pixels / (height * width))
        h_bar = _ceil_by_factor(int(height * beta), factor)
        w_bar = _ceil_by_factor(int(width * beta), factor)

    return h_bar, w_bar


class ImageProcessor:
    """VL模型图像预处理引擎"""

    def __init__(
        self,
        factor: int = 32,
        max_pixels: int = 16 * 16 * 4 * 12800,
        min_pixels: int = 56 * 56,
        max_long_side: int = 8192,
    ):
        self.factor = factor
        self.max_pixels = max_pixels
        self.min_pixels = min_pixels
        self.max_long_side = max_long_side

    def process(self, image_bytes: bytes) -> Tuple[str, int, int]:
        """处理图像: 缩放 + base64编码

        Returns:
            (base64_str, resized_width, resized_height)
        """
        image = Image.open(BytesIO(image_bytes))
        width, height = image.size

        resized_height, resized_width = smart_resize(
            height=height,
            width=width,
            factor=self.factor,
            min_pixels=self.min_pixels,
            max_pixels=self.max_pixels,
            max_long_side=self.max_long_side,
        )

        image = image.resize((resized_width, resized_height))

        buffer = BytesIO()
        image.save(buffer, format="PNG")
        processed_bytes = buffer.getvalue()

        return base64.b64encode(processed_bytes).decode("utf-8"), resized_width, resized_height

    @staticmethod
    def encode_image(image_bytes: bytes) -> str:
        """直接base64编码, 不缩放"""
        return base64.b64encode(image_bytes).decode("utf-8")

    def get_resize_dims(self, height: int, width: int) -> Tuple[int, int]:
        """仅计算缩放后尺寸, 不执行缩放"""
        return smart_resize(
            height=height,
            width=width,
            factor=self.factor,
            min_pixels=self.min_pixels,
            max_pixels=self.max_pixels,
            max_long_side=self.max_long_side,
        )