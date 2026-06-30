
import os
import sys

COMMAND = "overlay_text"
DESCRIPTION = "PDF 文本覆盖工具，在指定 bbox 区域执行白色覆盖 + 新文字写入。"
CATEGORY = "edit"
PARAMS = [
    {"name": "input", "type": "str", "required": True, "help": "源 PDF 文件路径"},
    {"name": "output", "type": "str", "required": True, "help": "输出 PDF 文件路径"},
    {"name": "overlays", "type": "json", "required": True, "help": "覆盖操作列表 JSON 数组"},
]


def handler(params):
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from io import BytesIO
    from pdfkit.commands.smart_edit import _find_cjk_font_path, _is_cjk, _extract_embedded_font, _is_subset_font, _check_font_has_glyphs

    input_path = params["input"]
    output_path = params["output"]
    overlays = params.get("overlays", [])

    if not overlays:
        return {"success": False, "error": "overlays 列表不能为空"}

    reader = PdfReader(input_path)
    writer = PdfWriter()

    extracted_font_path = None
    try:
        import fitz
        fitz_doc = fitz.open(input_path)
        first_ov = overlays[0]
        first_page_num = first_ov.get("page", 0)
        if first_page_num < len(fitz_doc):
            fitz_page = fitz_doc[first_page_num]
            bbox = first_ov.get("bbox", [0, 0, 100, 20])
            search_rect = fitz.Rect(float(bbox[0]) - 10, float(bbox[1]) - 10,
                                     float(bbox[2]) + 10, float(bbox[3]) + 10)
            text_dict = fitz_page.get_text("dict", clip=search_rect)
            find_text_for_font = ""
            for block in text_dict.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        if span.get("text", "").strip():
                            find_text_for_font = span["text"]
                            break
                    if find_text_for_font:
                        break
                if find_text_for_font:
                    break

            if find_text_for_font:
                extracted = _extract_embedded_font(fitz_doc, fitz_page, find_text_for_font)
                if extracted:
                    font_buffer, font_name, font_ext = extracted
                    new_text = first_ov.get("text", "")
                    is_subset = _is_subset_font(font_name) if font_name else False
                    can_use = True
                    if is_subset and new_text:
                        can_use = _check_font_has_glyphs(font_buffer, new_text)

                    if can_use and font_ext in ("ttf", "otf", "ttc"):
                        import tempfile
                        tmp = tempfile.NamedTemporaryFile(suffix=f".{font_ext}", delete=False)
                        tmp.write(font_buffer)
                        tmp.close()
                        extracted_font_path = tmp.name
                        print(f"[FONT] overlay 提取嵌入字体: {font_name} → {extracted_font_path}",
                              file=sys.stderr)

        fitz_doc.close()
    except Exception as e:
        print(f"[WARN] 提取嵌入字体失败: {e}", file=sys.stderr)

    try:
        font_name = "Helvetica"
        needs_cjk = any(
            any(_is_cjk(c) for c in ov.get("text", ""))
            for ov in overlays
        )
        if needs_cjk:
            cjk_path = None
            for ov in overlays:
                if ov.get("font_path") and os.path.exists(ov["font_path"]):
                    cjk_path = ov["font_path"]
                    break
            if not cjk_path and extracted_font_path:
                cjk_path = extracted_font_path
            if not cjk_path:
                cjk_path = _find_cjk_font_path()

            if cjk_path:
                font_name = "CJKFont"
                registered = False
                if cjk_path.endswith((".ttc", ".TTC")):
                    for idx in range(10):
                        try:
                            pdfmetrics.registerFont(TTFont(font_name, cjk_path, subfontIndex=idx))
                            registered = True
                            break
                        except Exception:
                            continue
                if not registered:
                    try:
                        pdfmetrics.registerFont(TTFont(font_name, cjk_path))
                        registered = True
                    except Exception as e:
                        print(f"[WARN] 注册 CJK 字体失败: {e}", file=sys.stderr)
                        font_name = "Helvetica"

        page_overlays = {}
        for ov in overlays:
            pg = ov.get("page", 0)
            if pg not in page_overlays:
                page_overlays[pg] = []
            page_overlays[pg].append(ov)

        total_overlaid = 0

        for page_idx in range(len(reader.pages)):
            base_page = reader.pages[page_idx]

            if page_idx not in page_overlays:
                writer.add_page(base_page)
                continue

            media_box = base_page.mediabox
            page_w = float(media_box.width)
            page_h = float(media_box.height)

            packet = BytesIO()
            c = canvas.Canvas(packet, pagesize=(page_w, page_h))

            for ov in page_overlays[page_idx]:
                bbox = ov.get("bbox", [0, 0, 100, 20])
                text = ov.get("text", "")
                x0, y0, x1, y1 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])

                rl_y0 = page_h - y1  # PyMuPDF 的 y1（下边）→ reportlab 的 y0（下边）
                rl_y1 = page_h - y0  # PyMuPDF 的 y0（上边）→ reportlab 的 y1（上边）

                rect_w = x1 - x0
                rect_h = rl_y1 - rl_y0

                font_size = ov.get("font_size", 0)
                if font_size <= 0:
                    font_size = max(6, rect_h * 0.9)

                bg = ov.get("bg_color", [1, 1, 1])
                fg = ov.get("color", [0, 0, 0])

                pad = max(0.8, rect_h * 0.08)

                c.setFillColorRGB(bg[0], bg[1], bg[2])
                c.setStrokeColorRGB(bg[0], bg[1], bg[2])
                c.rect(x0 - pad, rl_y0 - pad, rect_w + 2 * pad, rect_h + 2 * pad, fill=1, stroke=0)

                c.setFillColorRGB(fg[0], fg[1], fg[2])
                ov_font = font_name
                if ov.get("font_path") and os.path.exists(ov["font_path"]):
                    try:
                        from pdfkit.font_manager import register_reportlab_font
                        custom_name = f"CustomFont_{page_idx}"
                        if register_reportlab_font(custom_name, ov["font_path"]):
                            ov_font = custom_name
                    except Exception:
                        pass
                c.setFont(ov_font, font_size)
                c.drawString(x0, rl_y0 + rect_h * 0.05, text)
                total_overlaid += 1

            c.save()
            packet.seek(0)

            overlay_reader = PdfReader(packet)
            if len(overlay_reader.pages) > 0:
                base_page.merge_page(overlay_reader.pages[0])

            writer.add_page(base_page)

        with open(output_path, "wb") as f:
            writer.write(f)

        return {
            "success": True,
            "output": output_path,
            "total_overlaid": total_overlaid,
            "method": "pdfplumber_reportlab_overlay",
            "file_size": os.path.getsize(output_path),
        }
    finally:
        if extracted_font_path and os.path.exists(extracted_font_path):
            try:
                os.unlink(extracted_font_path)
            except Exception:
                pass


if __name__ == "__main__":
    from pdfkit.base import main
    main(handler, params_schema=PARAMS, description=DESCRIPTION)
