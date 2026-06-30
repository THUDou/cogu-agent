
import os

COMMAND = "redact"
DESCRIPTION = "对 PDF 中的指定文本或区域进行涂黑/脱敏处理。"
CATEGORY = "security"
PARAMS = [
    {"name": "input", "type": "str", "required": True, "help": "输入 PDF 路径"},
    {"name": "output", "type": "str", "required": True, "help": "输出 PDF 路径"},
    {"name": "redactions", "type": "json", "required": True, "help": '涂黑操作列表 [{"type": "text|area|regex", "text": "...", "page": -1, "rect": [...], "pattern": "..."}]'},
    {"name": "fill_color", "type": "json", "required": False, "default": [0, 0, 0], "help": "默认填充颜色 [r, g, b]，0-1 范围"},
]


def redact_text(input_path, output_path, redactions, fill_color=(0, 0, 0)):
    import re

    import fitz  # PyMuPDF

    doc = fitz.open(input_path)
    total_redacted = 0
    redaction_details = []

    for redaction in redactions:
        r_type = redaction.get("type", "text")
        page_num = redaction.get("page", -1)
        r_fill = redaction.get("fill_color", list(fill_color))
        if isinstance(r_fill, list) and len(r_fill) == 3:
            r_fill = tuple(r_fill)
        else:
            r_fill = fill_color

        if page_num == -1:
            pages = range(len(doc))
        else:
            if page_num < 0 or page_num >= len(doc):
                continue
            pages = [page_num]

        if r_type == "text":
            search_text = redaction.get("text", "")
            if not search_text:
                continue

            for p_idx in pages:
                page = doc[p_idx]
                text_instances = page.search_for(search_text)
                for inst in text_instances:
                    annot = page.add_redact_annot(inst, fill=r_fill)
                    total_redacted += 1

                if text_instances:
                    page.apply_redactions()
                    redaction_details.append({
                        "page": p_idx,
                        "type": "text",
                        "text": search_text,
                        "count": len(text_instances)
                    })

        elif r_type == "area":
            rect = redaction.get("rect")
            if not rect or len(rect) != 4:
                continue

            for p_idx in pages:
                page = doc[p_idx]
                r = fitz.Rect(rect[0], rect[1], rect[2], rect[3])
                annot = page.add_redact_annot(r, fill=r_fill)
                page.apply_redactions()
                total_redacted += 1
                redaction_details.append({
                    "page": p_idx,
                    "type": "area",
                    "rect": rect,
                    "count": 1
                })

        elif r_type == "regex":
            pattern = redaction.get("pattern", "")
            if not pattern:
                continue

            for p_idx in pages:
                page = doc[p_idx]
                text_page = page.get_text("text")
                matches = list(re.finditer(pattern, text_page))
                match_count = 0

                for match in matches:
                    matched_text = match.group()
                    text_instances = page.search_for(matched_text)
                    for inst in text_instances:
                        page.add_redact_annot(inst, fill=r_fill)
                        match_count += 1

                if match_count > 0:
                    page.apply_redactions()
                    total_redacted += match_count
                    redaction_details.append({
                        "page": p_idx,
                        "type": "regex",
                        "pattern": pattern,
                        "count": match_count
                    })

    doc.save(output_path)
    file_size = os.path.getsize(output_path)
    doc.close()

    return {
        "success": True,
        "total_redacted": total_redacted,
        "details": redaction_details,
        "output": output_path,
        "file_size": file_size
    }


def handler(params):
    input_path = params.get("input", "")
    output_path = params.get("output", "")
    redactions = params.get("redactions", [])

    if not input_path or not output_path:
        raise ValueError("'input' 和 'output' 参数必填")

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"文件不存在: {input_path}")

    if not redactions:
        raise ValueError("'redactions' 参数不能为空")

    fill_color = tuple(params.get("fill_color", [0, 0, 0]))

    return redact_text(input_path, output_path, redactions, fill_color)


if __name__ == "__main__":
    from pdfkit.base import main
    main(handler, PARAMS, DESCRIPTION)
