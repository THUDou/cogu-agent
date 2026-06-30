
import os
import sys

COMMAND = "layout_engine"
DESCRIPTION = "PDF 排版引擎，处理文本回写时的位置计算（reflow / batch_reflow）。"
CATEGORY = "meta"
PARAMS = [
    {"name": "action", "type": "str", "required": False, "default": "reflow", "choices": ["reflow", "batch_reflow"], "help": "操作类型"},
    {"name": "block", "type": "json", "required": False, "help": "单个布局块（reflow 时使用）"},
    {"name": "blocks", "type": "json", "required": False, "help": "布局块列表（batch_reflow 时使用）"},
    {"name": "text", "type": "str", "required": False, "help": "新文本（reflow 时使用）"},
    {"name": "texts", "type": "json", "required": False, "help": "新文本列表（batch_reflow 时使用）"},
    {"name": "constraints", "type": "json", "required": False, "help": "排版约束 {min_font_size, line_spacing, overflow_mode}"},
    {"name": "font_path", "type": "str", "required": False, "help": "字体文件路径"},
]


class LayoutEngine:

    def __init__(self, font_path=None):
        self.font_path = font_path
        self._font_cache = {}

    def reflow_text(self, block, new_text, constraints=None):
        if constraints is None:
            constraints = {}

        bbox = block.get("bbox", [0, 0, 100, 100])
        max_width = bbox[2] - bbox[0]
        max_height = bbox[3] - bbox[1]
        font_size = block.get("font_size", 12)
        min_font_size = constraints.get("min_font_size", 6)
        line_spacing = constraints.get("line_spacing", 1.2)

        lines = self._wrap_text(new_text, font_size, max_width)
        total_height = len(lines) * font_size * line_spacing

        while total_height > max_height and font_size > min_font_size:
            font_size -= 0.5
            lines = self._wrap_text(new_text, font_size, max_width)
            total_height = len(lines) * font_size * line_spacing

        overflow = total_height > max_height
        overflow_mode = constraints.get("overflow_mode", "truncate")

        if overflow:
            if overflow_mode == "truncate":
                max_lines = max(1, int(max_height / (font_size * line_spacing)))
                lines = lines[:max_lines]
                if len(lines) > 0:
                    lines[-1] = lines[-1].rstrip() + "..."
                total_height = len(lines) * font_size * line_spacing
            elif overflow_mode == "expand":
                pass

        return {
            "lines": lines,
            "font_size": round(font_size, 1),
            "total_height": round(total_height, 1),
            "overflow": overflow,
            "line_count": len(lines),
            "bbox": [
                bbox[0],
                bbox[1],
                bbox[2],
                bbox[1] + total_height if overflow_mode == "expand" else bbox[3],
            ],
        }

    def _wrap_text(self, text, font_size, max_width):
        if not text:
            return [""]

        lines = []
        paragraphs = text.split("\n")

        for para in paragraphs:
            if not para.strip():
                lines.append("")
                continue

            current_line = ""
            current_width = 0.0

            i = 0
            while i < len(para):
                ch = para[i]
                ch_width = self._char_width(ch, font_size)

                if current_width + ch_width > max_width and current_line:
                    if ch.isalpha() and current_line and current_line[-1].isalpha():
                        break_pos = len(current_line) - 1
                        while break_pos > 0 and current_line[break_pos].isalpha():
                            break_pos -= 1
                        if break_pos > 0:
                            lines.append(current_line[:break_pos + 1].rstrip())
                            remaining = current_line[break_pos + 1:]
                            current_line = remaining + ch
                            current_width = sum(
                                self._char_width(c, font_size) for c in current_line
                            )
                            i += 1
                            continue

                    lines.append(current_line)
                    current_line = ch
                    current_width = ch_width
                else:
                    current_line += ch
                    current_width += ch_width
                i += 1

            if current_line:
                lines.append(current_line)

        return lines if lines else [""]

    def _char_width(self, ch, font_size):
        code = ord(ch)
        if (0x4E00 <= code <= 0x9FFF or  # CJK 基本
            0x3400 <= code <= 0x4DBF or  # CJK 扩展 A
            0xF900 <= code <= 0xFAFF or  # CJK 兼容
            0x3000 <= code <= 0x303F or  # CJK 标点
            0xFF00 <= code <= 0xFFEF):   # 全角字符
            return font_size * 1.0
        elif ch == ' ':
            return font_size * 0.25
        elif ch in '.,;:!?':
            return font_size * 0.3
        elif ch.isupper():
            return font_size * 0.65
        else:
            return font_size * 0.5

    def compute_text_positions(self, blocks, translations, constraints=None):
        results = []
        for block, new_text in zip(blocks, translations):
            result = self.reflow_text(block, new_text, constraints)
            result["original_text"] = block.get("text", "")
            result["translated_text"] = new_text
            results.append(result)
        return results


def handler(params):
    action = params.get("action", "reflow")
    font_path = params.get("font_path")
    constraints = params.get("constraints", {})

    engine = LayoutEngine(font_path=font_path)

    if action == "reflow":
        block = params["block"]
        new_text = params["text"]
        result = engine.reflow_text(block, new_text, constraints)
        return result

    elif action == "batch_reflow":
        blocks = params["blocks"]
        texts = params["texts"]
        results = engine.compute_text_positions(blocks, texts, constraints)
        return {"results": results, "count": len(results)}

    else:
        raise ValueError(f"未知的 action: {action}")


if __name__ == "__main__":
    from pdfkit.base import main
    main(handler, params_schema=PARAMS, description=DESCRIPTION)
