
import os
from datetime import datetime

COMMAND = "sign_pdf"
DESCRIPTION = "为 PDF 添加可见的数字签名（图片印章 + 文字信息）。"
CATEGORY = "security"
PARAMS = [
    {"name": "input", "type": "str", "required": True, "help": "输入 PDF 路径"},
    {"name": "output", "type": "str", "required": True, "help": "输出 PDF 路径"},
    {"name": "signature", "type": "json", "required": True, "help": '签名配置 {"image": "...", "text": "...", "position": [x, y], "width": 150, "height": 60, ...}'},
    {"name": "pages", "type": "json", "required": False, "help": "签名页码列表，不指定表示最后一页"},
]


def sign_pdf(input_path, output_path, signature, pages=None):
    import fitz  # PyMuPDF

    doc = fitz.open(input_path)
    total_pages = len(doc)

    if pages is None:
        pages = [total_pages - 1]  # 默认签在最后一页

    image_path = signature.get("image", "")
    text = signature.get("text", "")
    position = signature.get("position", [400, 100])
    width = signature.get("width", 150)
    height = signature.get("height", 60)
    font_size = signature.get("font_size", 10)
    font_color = signature.get("font_color", [0, 0, 0])
    opacity = signature.get("opacity", 1.0)

    signed_pages = 0

    for p_idx in pages:
        if p_idx < 0 or p_idx >= total_pages:
            continue
        page = doc[p_idx]
        page_rect = page.rect

        if isinstance(position, str):
            margin = 30
            pos_map = {
                "top_left": (margin, margin),
                "top_center": ((page_rect.width - width) / 2, margin),
                "top_right": (page_rect.width - width - margin, margin),
                "center": ((page_rect.width - width) / 2, (page_rect.height - height) / 2),
                "bottom_left": (margin, page_rect.height - height - margin - font_size * 3),
                "bottom_center": ((page_rect.width - width) / 2, page_rect.height - height - margin - font_size * 3),
                "bottom_right": (page_rect.width - width - margin, page_rect.height - height - margin - font_size * 3),
            }
            x, y = pos_map.get(position, (page_rect.width - width - margin, page_rect.height - height - margin - font_size * 3))
        elif isinstance(position, list) and len(position) >= 2:
            x, y = float(position[0]), float(position[1])
        else:
            x, y = 400.0, 100.0

        rect = fitz.Rect(x, y, x + width, y + height)

        if image_path and os.path.exists(image_path):
            page.insert_image(rect, filename=image_path, overlay=True)

        if text:
            text_point = fitz.Point(x, y + height + font_size + 2)
            page.insert_text(
                text_point,
                text,
                fontsize=font_size,
                color=tuple(c for c in font_color)
            )

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        time_point = fitz.Point(x, y + height + font_size * 2 + 6)
        page.insert_text(
            time_point,
            f"签署时间: {timestamp}",
            fontsize=font_size - 2,
            color=(0.5, 0.5, 0.5)
        )

        signed_pages += 1

    doc.save(output_path)
    file_size = os.path.getsize(output_path)
    doc.close()

    return {
        "success": True,
        "signed_pages": signed_pages,
        "output": output_path,
        "file_size": file_size,
        "timestamp": datetime.now().isoformat()
    }


def handler(params):
    input_path = params.get("input", "")
    output_path = params.get("output", "")
    signature = params.get("signature", {})
    pages = params.get("pages")

    if not input_path or not output_path:
        raise ValueError("'input' 和 'output' 参数必填")

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"文件不存在: {input_path}")

    return sign_pdf(input_path, output_path, signature, pages)


if __name__ == "__main__":
    from pdfkit.base import main
    main(handler, PARAMS, DESCRIPTION)
