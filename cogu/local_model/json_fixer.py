"""JSON容错解析器

融合自KwaiAgents kwaiagents/utils/json_fix_general.py
核心能力: 括号补全, 引号修复, 非法转义修复, 尾随逗号处理
适用于小模型输出JSON格式不稳定时的自动修复
"""
import contextlib
import json
import logging
import re
from typing import Any, Optional

logger = logging.getLogger("cogu.local_model.json_fixer")


class JSONFixer:
    """JSON容错解析器

    自动修复常见JSON格式错误:
    1. 括号不匹配 — 自动补全/移除多余括号
    2. 属性名缺少引号 — 自动添加双引号
    3. 非法转义序列 — 移除无效反斜杠
    4. 尾随逗号 — 移除多余逗号
    """

    def __init__(self, max_repair_attempts: int = 3):
        self.max_repair_attempts = max_repair_attempts

    def parse(self, json_str: str) -> Optional[Any]:
        """容错解析JSON字符串

        Args:
            json_str: 可能包含格式错误的JSON字符串

        Returns:
            解析后的Python对象, 失败返回None
        """
        if not json_str or not json_str.strip():
            return None

        result = self._try_parse(json_str)
        if result is not None:
            return result

        repaired = self._repair(json_str)
        return self._try_parse(repaired)

    def _try_parse(self, json_str: str) -> Optional[Any]:
        """尝试解析JSON"""
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return None

    def _repair(self, json_str: str) -> str:
        """逐步修复JSON格式错误"""
        result = json_str

        for _ in range(self.max_repair_attempts):
            previous = result

            result = self._fix_trailing_commas(result)
            result = self._fix_invalid_escape(result)
            result = self._fix_missing_quotes(result)
            result = self._fix_unbalanced_braces(result)

            if result == previous:
                break

            if self._try_parse(result) is not None:
                break

        return result

    @staticmethod
    def _fix_trailing_commas(json_str: str) -> str:
        """移除尾随逗号"""
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        return json_str

    @staticmethod
    def _fix_invalid_escape(json_str: str) -> str:
        """修复非法转义序列"""
        try:
            json.loads(json_str)
            return json_str
        except json.JSONDecodeError as e:
            error_msg = str(e)
            if "Invalid \\escape" in error_msg:
                char_pos = _extract_char_position(error_msg)
                if char_pos is not None:
                    json_str = json_str[:char_pos] + json_str[char_pos + 1:]
            return json_str

    @staticmethod
    def _fix_missing_quotes(json_str: str) -> str:
        """为属性名添加双引号"""
        def replace_func(match):
            return f'"{match[1]}":'

        pattern = re.compile(r"(\w+):")
        result = pattern.sub(replace_func, json_str)

        try:
            json.loads(result)
            return result
        except json.JSONDecodeError:
            return json_str

    @staticmethod
    def _fix_unbalanced_braces(json_str: str) -> str:
        """补全/移除不匹配的括号"""
        open_count = json_str.count("{")
        close_count = json_str.count("}")

        while open_count > close_count:
            json_str += "}"
            close_count += 1

        while close_count > open_count:
            json_str = json_str.rstrip("}")
            close_count -= 1

        with contextlib.suppress(json.JSONDecodeError):
            json.loads(json_str)
            return json_str

        return json_str

    def extract_json_object(self, text: str) -> Optional[str]:
        """从文本中提取JSON对象"""
        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            return text[start:end]
        except ValueError:
            pass

        try:
            start = text.index("[")
            end = text.rindex("]") + 1
            return text[start:end]
        except ValueError:
            pass

        return None

    def safe_parse(self, text: str) -> Optional[Any]:
        """从任意文本中安全提取并解析JSON"""
        json_str = self.extract_json_object(text)
        if json_str is None:
            return None
        return self.parse(json_str)


def _extract_char_position(error_message: str) -> Optional[int]:
    """从JSONDecodeError消息中提取字符位置"""
    match = re.search(r"\(char (\d+)\)", error_message)
    if match:
        return int(match[1])
    return None