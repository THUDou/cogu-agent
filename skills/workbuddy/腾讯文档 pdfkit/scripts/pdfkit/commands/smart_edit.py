
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from font_manager import resolve_font, find_system_cjk_font, BUNDLED_FONT

COMMAND = "smart_edit"
DESCRIPTION = "PDF 智能编辑，自动判断 PDF 类型（文字层/扫描件/混合），选择最优编辑方案。"
CATEGORY = "edit"
PARAMS = [
    {"name": "input", "type": "str", "required": True, "help": "源 PDF 文件路径"},
    {"name": "output", "type": "str", "required": True, "help": "输出 PDF 文件路径"},
    {"name": "edits", "type": "json", "required": True, "help": "编辑操作列表 JSON 数组"},
    {"name": "dry_run", "type": "bool", "required": False, "default": False, "help": "是否为预览模式（只评估不执行）"},
]


def _is_cjk(char):
    cp = ord(char)
    return (
        (0x4E00 <= cp <= 0x9FFF) or      # CJK 统一汉字
        (0x3400 <= cp <= 0x4DBF) or      # CJK 统一汉字扩展 A
        (0x20000 <= cp <= 0x2A6DF) or    # CJK 统一汉字扩展 B
        (0x2A700 <= cp <= 0x2B73F) or    # CJK 统一汉字扩展 C
        (0x2B740 <= cp <= 0x2B81F) or    # CJK 统一汉字扩展 D
        (0x3000 <= cp <= 0x303F) or      # CJK 符号和标点
        (0x3040 <= cp <= 0x309F) or      # 日文平假名
        (0x30A0 <= cp <= 0x30FF) or      # 日文片假名
        (0xAC00 <= cp <= 0xD7AF) or      # 韩文音节
        (0xFF00 <= cp <= 0xFFEF)         # 全角字符
    )


def _check_tesseract_langs(lang):
    import subprocess
    import platform
    try:
        result = subprocess.run(
            ['tesseract', '--list-langs'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"tesseract --list-langs 执行失败: {result.stderr.strip()}。"
                "请确认 tesseract 已正确安装"
            )
        lines = result.stdout.strip().splitlines()
        available = [l.strip() for l in lines[1:] if l.strip()]

        missing = []
        for l in lang.split('+'):
            l = l.strip()
            if l and l not in available:
                missing.append(l)

        if missing:
            plat = platform.system()
            if plat == "Darwin":
                install_hint = "brew install tesseract-lang"
            elif plat == "Windows":
                install_hint = (
                    "从 https://github.com/UB-Mannheim/tesseract/wiki 下载安装包，"
                    "安装时勾选所需语言包"
                )
            else:
                install_cmds = [f"apt install tesseract-ocr-{m.replace('_', '-')}" for m in missing]
                install_hint = ' && '.join(install_cmds)
            raise RuntimeError(
                f"Tesseract 语言包缺失: {', '.join(missing)}。"
                f"可用语言包: {', '.join(available[:20])}{'...' if len(available) > 20 else ''}。"
                f"请安装: {install_hint}"
            )
    except FileNotFoundError:
        plat = platform.system()
        if plat == "Darwin":
            install_hint = "brew install tesseract"
        elif plat == "Windows":
            install_hint = "从 https://github.com/UB-Mannheim/tesseract/wiki 下载安装"
        else:
            install_hint = "apt install tesseract-ocr"
        raise RuntimeError(
            f"未找到 tesseract 命令。请安装: {install_hint}"
        )


def _preprocess_for_ocr(img):
    try:
        import numpy as np
        from PIL import ImageFilter

        gray = img.convert('L')

        arr = np.array(gray)
        threshold = np.mean(arr)
        binary = np.where(arr > threshold, 255, 0).astype(np.uint8)

        from PIL import Image
        binary_img = Image.fromarray(binary, mode='L')
        denoised = binary_img.filter(ImageFilter.MedianFilter(size=3))

        return denoised.convert('RGB')
    except Exception as e:
        print(f"[WARN] 图像预处理失败，使用原图: {e}", file=sys.stderr)
        return img


def _ocr_paddleocr(img, lang="ch"):
    from paddleocr import PaddleOCR
    import numpy as np

    ocr = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)

    img_array = np.array(img)
    result = ocr.ocr(img_array, cls=True)

    ocr_data = {
        'text': [],
        'left': [],
        'top': [],
        'width': [],
        'height': [],
        'conf': [],
        'line_num': [],
        'block_num': [],
    }

    if not result or not result[0]:
        return ocr_data

    for line_idx, line in enumerate(result[0]):
        if not line:
            continue
        bbox_points = line[0]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        text = line[1][0]
        confidence = line[1][1]

        x_coords = [p[0] for p in bbox_points]
        y_coords = [p[1] for p in bbox_points]
        x = int(min(x_coords))
        y = int(min(y_coords))
        w = int(max(x_coords) - x)
        h = int(max(y_coords) - y)

        for char_idx, char in enumerate(text):
            if not char.strip():
                continue
            char_w = max(1, w // max(1, len(text)))
            char_x = x + char_idx * char_w

            ocr_data['text'].append(char)
            ocr_data['left'].append(char_x)
            ocr_data['top'].append(y)
            ocr_data['width'].append(char_w)
            ocr_data['height'].append(h)
            ocr_data['conf'].append(str(int(confidence * 100)))
            ocr_data['line_num'].append(line_idx + 1)
            ocr_data['block_num'].append(1)

    return ocr_data


def _ocr_tesseract(img, lang="eng+chi_sim"):
    import pytesseract
    return pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)


def _ocr_page(img, lang="eng+chi_sim", engine="auto", preprocess=True):
    processed_img = _preprocess_for_ocr(img) if preprocess else img

    if engine == "auto":
        try:
            paddle_lang = "ch" if "chi" in lang else "en"
            result = _ocr_paddleocr(processed_img, paddle_lang)
            if result and len(result.get('text', [])) > 0:
                print(f"[OCR] 使用 PaddleOCR 引擎 (lang={paddle_lang})", file=sys.stderr)
                return result
        except ImportError:
            pass
        except Exception as e:
            print(f"[WARN] PaddleOCR 失败，回退 Tesseract: {e}", file=sys.stderr)

        print(f"[OCR] 使用 Tesseract 引擎 (lang={lang})", file=sys.stderr)
        return _ocr_tesseract(processed_img, lang)

    elif engine == "paddleocr":
        paddle_lang = "ch" if "chi" in lang else "en"
        return _ocr_paddleocr(processed_img, paddle_lang)

    else:  # tesseract
        return _ocr_tesseract(processed_img, lang)


_ocr_cache = {}  # {(input_path, page_num, lang): (img, ocr_data)}


def _get_page_ocr(doc, page, page_num, input_path, lang="eng+chi_sim", ocr_engine="auto"):
    import fitz
    from PIL import Image
    import io

    cache_key = (input_path, page_num, lang)
    if cache_key in _ocr_cache:
        return _ocr_cache[cache_key]

    zoom = 300.0 / 72.0  # 300 DPI
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    img_data = pix.tobytes("png")
    img = Image.open(io.BytesIO(img_data))

    ocr_data = _ocr_page(img, lang=lang, engine=ocr_engine, preprocess=True)

    _ocr_cache[cache_key] = (img.copy(), ocr_data)
    return img, ocr_data


def _clear_ocr_cache():
    global _ocr_cache
    _ocr_cache = {}


def _prefilter_scanned_pages(doc, page_types, edits, total_pages, skip_set, input_path):
    import fitz
    import pytesseract
    from PIL import Image
    import io

    find_texts = set()
    scanned_pages = set()
    for edit in edits:
        edit_type = edit.get("type", "replace_text")
        if edit_type not in ("replace_text", "delete_text"):
            continue
        find_text = edit.get("find", "").strip()
        if not find_text:
            continue
        find_texts.add(find_text.lower())

        page_num = edit.get("page", -1)
        if page_num == -1:
            for pg in range(total_pages):
                if page_types.get(pg) == "scanned":
                    scanned_pages.add(pg)
        else:
            if page_types.get(page_num) == "scanned":
                scanned_pages.add(page_num)

    if not find_texts or not scanned_pages:
        return

    lang = "eng+chi_sim"
    for ft in find_texts:
        if any(_is_cjk(c) for c in ft):
            if 'chi' not in lang:
                lang = lang + '+chi_sim'
            break

    find_chars = set()
    for ft in find_texts:
        for c in ft:
            if _is_cjk(c):
                find_chars.add(c)

    t0 = time.time()

    def _quick_ocr_page(pg):
        try:
            page = doc[pg]
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            text = pytesseract.image_to_string(img, lang=lang).lower()
            return pg, text
        except Exception:
            return pg, None

    workers = min(3, len(scanned_pages))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_quick_ocr_page, pg): pg for pg in scanned_pages}
        for future in as_completed(futures):
            pg, text = future.result()
            if text is None:
                continue  # 预筛选失败，不跳过

            has_full_match = any(ft in text for ft in find_texts)
            has_char_match = any(c in text for c in find_chars) if find_chars else False

            if not has_full_match and not has_char_match:
                skip_set.add(pg)

    elapsed = time.time() - t0
    if skip_set:
        import sys
        print(f"[P3 预筛选] {elapsed:.2f}s, 扫描 {len(scanned_pages)} 页, "
              f"跳过 {len(skip_set)} 页: {sorted(skip_set)}", file=sys.stderr)


def _parallel_ocr_warmup(doc, page_types, edit_page_pairs, skip_pages, input_path):
    page_edits = {}  # {page_num: [edit1, edit2, ...]}
    for edit, pg in edit_page_pairs:
        edit_type = edit.get("type", "replace_text")
        if edit_type not in ("replace_text", "delete_text"):
            continue
        if page_types.get(pg) != "scanned":
            continue
        if pg in skip_pages:
            continue
        if pg not in page_edits:
            page_edits[pg] = []
        page_edits[pg].append(edit)

    if len(page_edits) <= 1:
        return

    t0 = time.time()

    lang = "eng+chi_sim"
    for edit, _ in edit_page_pairs:
        find_text = edit.get("find", "")
        if any(_is_cjk(c) for c in find_text):
            if 'chi' not in lang:
                lang = lang + '+chi_sim'
            break

    def _process_one_page(pg):
        try:
            page = doc[pg]
            img, ocr_data = _get_page_ocr(doc, page, pg, input_path, lang)

            edits_for_page = page_edits[pg]
            from PIL import ImageDraw
            import numpy as np

            img_modified = img.copy()
            draw = ImageDraw.Draw(img_modified)
            total_replaced = 0

            for edit in edits_for_page:
                find_text = edit.get("find", "")
                replace_text = edit.get("replace", "")
                if not find_text:
                    continue

                found_regions = _merge_ocr_texts(ocr_data, find_text)
                for region in found_regions:
                    x, y, w, h = region['x'], region['y'], region['w'], region['h']

                    img_array = np.array(img_modified)
                    padding = 3
                    bg_region = img_array[max(0, y - padding):y, max(0, x):x + w]
                    if bg_region.size > 0:
                        bg_color = tuple(np.median(bg_region.reshape(-1, 3), axis=0).astype(int))
                    else:
                        bg_color = (255, 255, 255)

                    draw.rectangle([x - padding, y - padding, x + w + padding, y + h + padding], fill=bg_color)

                    font_size_px = max(10, h)
                    font = _get_pil_font(edit.get("font"), font_size_px, replace_text)
                    text_color = (0, 0, 0) if sum(bg_color[:3]) > 384 else (255, 255, 255)
                    draw.text((x, y), replace_text, fill=text_color, font=font)
                    total_replaced += 1

            if total_replaced > 0:
                import io
                img_bytes = io.BytesIO()
                img_modified.save(img_bytes, format="PNG")
                _processed_images[pg] = (img_bytes.getvalue(), total_replaced)
            else:
                _processed_images[pg] = (None, 0)

            return pg, total_replaced
        except Exception as e:
            import sys
            print(f"[P2] Page {pg} 处理失败: {e}", file=sys.stderr)
            return pg, -1

    workers = min(3, len(page_edits))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_process_one_page, pg): pg for pg in sorted(page_edits.keys())}
        for future in as_completed(futures):
            pg, replaced = future.result()

    elapsed = time.time() - t0
    processed_count = sum(1 for v in _processed_images.values() if v[1] > 0)
    print(f"[P2 并行处理] {elapsed:.2f}s, {len(page_edits)} 页并行完成, "
          f"{processed_count} 页有替换", file=sys.stderr)


_processed_images = {}


def _clear_processed_images():
    global _processed_images
    _processed_images = {}


def _is_same_region(region_a, region_b, tolerance=2):
    if region_a.get("text", "").strip().lower() != region_b.get("text", "").strip().lower():
        return False

    for key in ("x", "y", "w", "h"):
        if abs(region_a.get(key, 0) - region_b.get(key, 0)) > tolerance:
            return False

    return True


def _merge_ocr_texts(ocr_data, find_text, max_gap=20):
    n_boxes = len(ocr_data['text'])

    valid_blocks = []
    for i in range(n_boxes):
        text = ocr_data['text'][i].strip()
        if not text:
            continue
        conf = int(ocr_data['conf'][i]) if ocr_data['conf'][i] != '' else -1
        if conf < 0:
            continue
        valid_blocks.append({
            'index': i,
            'text': text,
            'left': ocr_data['left'][i],
            'top': ocr_data['top'][i],
            'width': ocr_data['width'][i],
            'height': ocr_data['height'][i],
            'line_num': ocr_data['line_num'][i],
            'block_num': ocr_data['block_num'][i],
        })

    if not valid_blocks:
        return []

    lines = {}
    for blk in valid_blocks:
        key = (blk['block_num'], blk['line_num'])
        if key not in lines:
            lines[key] = []
        lines[key].append(blk)

    found_regions = []
    find_lower = find_text.lower()

    for line_key in sorted(lines.keys()):
        line_blocks = sorted(lines[line_key], key=lambda b: b['left'])

        merged_text = ""
        char_map = []  # 记录 merged_text 中每个字符对应的 block 索引

        for idx, blk in enumerate(line_blocks):
            if merged_text:
                last_char = merged_text[-1] if merged_text else ''
                first_char = blk['text'][0] if blk['text'] else ''

                prev_blk = line_blocks[idx - 1]
                gap = blk['left'] - (prev_blk['left'] + prev_blk['width'])

                if _is_cjk(last_char) or _is_cjk(first_char):
                    if gap > max_gap:
                        merged_text += " "
                        char_map.append(None)
                else:
                    if gap > 3:  # 英文单词间距阈值
                        merged_text += " "
                        char_map.append(None)

            for ch in blk['text']:
                merged_text += ch
                char_map.append(idx)

        merged_lower = merged_text.lower()
        search_start = 0
        while True:
            pos = merged_lower.find(find_lower, search_start)
            if pos == -1:
                break

            match_end = pos + len(find_text)

            involved_indices = set()
            for ci in range(pos, min(match_end, len(char_map))):
                if char_map[ci] is not None:
                    involved_indices.add(char_map[ci])

            if involved_indices:
                involved_blocks = [line_blocks[i] for i in sorted(involved_indices)]
                x = involved_blocks[0]['left']
                y = min(b['top'] for b in involved_blocks)
                x_end = max(b['left'] + b['width'] for b in involved_blocks)
                y_end = max(b['top'] + b['height'] for b in involved_blocks)

                candidate_region = {
                    'x': x,
                    'y': y,
                    'w': x_end - x,
                    'h': y_end - y,
                    'text': merged_text[pos:match_end],
                    'char_boxes': involved_blocks,
                }

                if not any(_is_same_region(existing, candidate_region) for existing in found_regions):
                    found_regions.append(candidate_region)

            search_start = match_end

    return found_regions


def _is_full_page_image(img_rect, page_rect, threshold=0.85):
    if not img_rect or not page_rect:
        return False
    img_area = abs(img_rect.width * img_rect.height)
    page_area = abs(page_rect.width * page_rect.height)
    if page_area == 0:
        return False
    return (img_area / page_area) >= threshold


def _detect_page_types(doc):
    page_types = {}
    for i in range(len(doc)):
        page = doc[i]
        text = page.get_text("text").strip()
        images = page.get_images()

        has_text = len(text) > 10
        has_images = len(images) > 0

        if has_text and not has_images:
            page_types[i] = "text"
        elif not has_text and has_images:
            page_types[i] = "scanned"
        elif has_text and has_images:
            is_scanned_with_ocr = False
            for img_info in images:
                xref = img_info[0]
                try:
                    img_rects = page.get_image_rects(xref)
                    if img_rects:
                        for img_rect in img_rects:
                            if _is_full_page_image(img_rect, page.rect):
                                is_scanned_with_ocr = True
                                break
                except Exception:
                    pass
                if is_scanned_with_ocr:
                    break

            if is_scanned_with_ocr:
                page_types[i] = "scanned_with_ocr"
            else:
                page_types[i] = "mixed"
        else:
            page_types[i] = "empty"

    return page_types


def _fuzzy_search(page, find_text):
    import fitz

    normalized_find = find_text.replace(" ", "").replace("\u3000", "")

    text_dict = page.get_text("dict")
    results = []

    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            line_text = ""
            span_info = []  # [(start_idx, end_idx, span_rect, span_data)]
            for span in line.get("spans", []):
                span_text = span.get("text", "")
                start = len(line_text)
                line_text += span_text
                end = len(line_text)
                span_rect = fitz.Rect(span["bbox"])
                span_info.append((start, end, span_rect, span))

            line_normalized = line_text.replace(" ", "").replace("\u3000", "")
            search_start = 0
            while True:
                pos = line_normalized.lower().find(normalized_find.lower(), search_start)
                if pos == -1:
                    break

                orig_start = _normalized_to_original_pos(line_text, pos)
                orig_end = _normalized_to_original_pos(line_text, pos + len(normalized_find))

                x0 = float('inf')
                y0 = float('inf')
                x1 = float('-inf')
                y1 = float('-inf')
                found_spans = False

                for s_start, s_end, s_rect, s_data in span_info:
                    if s_end > orig_start and s_start < orig_end:
                        x0 = min(x0, s_rect.x0)
                        y0 = min(y0, s_rect.y0)
                        x1 = max(x1, s_rect.x1)
                        y1 = max(y1, s_rect.y1)
                        found_spans = True

                if found_spans:
                    results.append(fitz.Rect(x0, y0, x1, y1))

                search_start = pos + len(normalized_find)

    return results


def _find_text_instances_precise(page, find_text):
    import fitz

    if not find_text:
        return []

    raw = page.get_text("rawdict")
    matched_rects = []
    find_lower = find_text.lower()

    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue

        for line in block.get("lines", []):
            line_chars = []
            line_text_parts = []

            for span in line.get("spans", []):
                for ch in span.get("chars", []):
                    char_text = ch.get("c", "")
                    bbox = ch.get("bbox")
                    if not char_text or not bbox:
                        continue
                    line_chars.append({"c": char_text, "bbox": bbox})
                    line_text_parts.append(char_text)

            if not line_chars:
                continue

            line_text = "".join(line_text_parts)
            line_lower = line_text.lower()
            search_start = 0

            while True:
                pos = line_lower.find(find_lower, search_start)
                if pos == -1:
                    break

                end = pos + len(find_text)
                matched_chars = line_chars[pos:end]
                if matched_chars:
                    x0 = min(ch["bbox"][0] for ch in matched_chars)
                    y0 = min(ch["bbox"][1] for ch in matched_chars)
                    x1 = max(ch["bbox"][2] for ch in matched_chars)
                    y1 = max(ch["bbox"][3] for ch in matched_chars)
                    matched_rects.append(fitz.Rect(x0, y0, x1, y1))

                search_start = end

    return matched_rects


def _normalized_to_original_pos(original_text, normalized_pos):
    count = 0
    for i, ch in enumerate(original_text):
        if ch != ' ' and ch != '\u3000':
            if count == normalized_pos:
                return i
            count += 1
    return len(original_text)


def _edit_replace_text(doc, page, page_num, page_type, edit):
    import fitz

    find_text = edit.get("find", "")
    replace_text = edit.get("replace", "")
    font_path = edit.get("font")
    color = edit.get("color", [0, 0, 0])

    if not find_text:
        return {"page": page_num, "type": "replace_text", "success": False, "error": "find 不能为空"}

    if page_type in ("scanned", "scanned_with_ocr"):
        return _replace_text_scanned(doc, page, page_num, edit)

    instances = _find_text_instances_precise(page, find_text)
    match_method = "rawdict_char_search"

    if not instances:
        instances = page.search_for(find_text)
        if instances:
            match_method = "pymupdf_search"

    if not instances:
        instances = _fuzzy_search(page, find_text)
        if instances:
            match_method = "fuzzy_search"
            print(f"[INFO] 精确匹配失败，模糊匹配成功: '{find_text}' → {len(instances)} 处", file=sys.stderr)

    if not instances:
        return {
            "page": page_num,
            "type": "replace_text",
            "success": False,
            "error": f"未找到文本: {find_text}",
            "method": "pymupdf_search+fuzzy",
        }

    original_font_size = 12
    original_font_name = None
    text_dict = page.get_text("dict")
    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                span_text = span.get("text", "")
                normalized_span = span_text.replace(" ", "").replace("\u3000", "")
                normalized_find = find_text.replace(" ", "").replace("\u3000", "")
                if find_text in span_text or normalized_find in normalized_span:
                    original_font_size = span.get("size", 12)
                    original_font_name = span.get("font", None)
                    break

    if original_font_size < 4 or original_font_size > 200:
        if instances:
            rect_h = instances[0].y1 - instances[0].y0
            original_font_size = max(6, rect_h * 0.85)

    replaced = 0
    for rect in instances:
        page.add_redact_annot(rect, fill=(1, 1, 1))

    page.apply_redactions()

    tw = fitz.TextWriter(page.rect)
    font = _get_font(font_path, original_font_name, doc, page, find_text, replace_text)

    for rect in instances:
        try:
            tw.append(
                fitz.Point(rect.x0, rect.y1 - 2),
                replace_text,
                font=font,
                fontsize=original_font_size,
            )
            replaced += 1
        except Exception as e:
            print(f"[WARN] TextWriter.append failed: {e}", file=sys.stderr)

    tw.write_text(page, color=color)

    return {
        "page": page_num,
        "type": "replace_text",
        "success": replaced > 0,
        "replaced": replaced,
        "method": f"pymupdf_redact({match_method})",
        "page_type": page_type,
        "font_size": original_font_size,
    }


def _edit_add_text(doc, page, page_num, edit):
    import fitz

    text = edit.get("text", "")
    x = edit.get("x", 50)
    y = edit.get("y", 50)
    font_size = edit.get("font_size", 12)
    font_path = edit.get("font")
    color = edit.get("color", [0, 0, 0])

    if not text:
        return {"page": page_num, "type": "add_text", "success": False, "error": "text 不能为空"}

    from pdfkit.commands.watermark_enhanced import normalize_mediabox
    normalize_mediabox(page)

    tw = fitz.TextWriter(page.rect)
    font = _get_font(font_path)

    try:
        tw.append(
            fitz.Point(x, y),
            text,
            font=font,
            fontsize=font_size,
        )
        tw.write_text(page, color=color)
        return {
            "page": page_num,
            "type": "add_text",
            "success": True,
            "position": [x, y],
            "font_size": font_size,
        }
    except Exception as e:
        return {
            "page": page_num,
            "type": "add_text",
            "success": False,
            "error": str(e),
        }


def _edit_delete_text(doc, page, page_num, page_type, edit):
    import fitz

    find_text = edit.get("find", "")
    if not find_text:
        return {"page": page_num, "type": "delete_text", "success": False, "error": "find 不能为空"}

    instances = page.search_for(find_text)
    if not instances:
        return {
            "page": page_num,
            "type": "delete_text",
            "success": False,
            "error": f"未找到文本: {find_text}",
        }

    for rect in instances:
        page.add_redact_annot(rect, fill=(1, 1, 1))

    page.apply_redactions()

    return {
        "page": page_num,
        "type": "delete_text",
        "success": True,
        "deleted": len(instances),
    }


def _edit_replace_image(doc, page, page_num, edit):
    import fitz

    image_index = edit.get("image_index", 0)
    new_image_path = edit.get("new_image")

    if not new_image_path or not os.path.exists(new_image_path):
        return {
            "page": page_num,
            "type": "replace_image",
            "success": False,
            "error": f"新图片文件不存在: {new_image_path}",
        }

    images = page.get_images(full=True)
    if image_index >= len(images):
        return {
            "page": page_num,
            "type": "replace_image",
            "success": False,
            "error": f"图片索引超出范围: {image_index} >= {len(images)}",
        }

    try:
        image_info = images[image_index]
        xref = image_info[0]
        image_name = image_info[7] if len(image_info) > 7 else xref
        xref_uses = 0
        for doc_page in doc:
            for doc_img in doc_page.get_images(full=True):
                if doc_img[0] == xref:
                    xref_uses += 1

        if xref_uses == 1:
            page.replace_image(xref, filename=new_image_path)
            return {
                "page": page_num,
                "type": "replace_image",
                "success": True,
                "image_index": image_index,
                "xref": xref,
                "method": "pymupdf_replace_image",
            }

        rects = page.get_image_rects(image_name)
        if not rects:
            rects = page.get_image_rects(xref)
        if not rects:
            return {
                "page": page_num,
                "type": "replace_image",
                "success": False,
                "error": f"未找到图片实例矩形: image_index={image_index}, xref={xref}",
            }

        target_rect = rects[0]
        page.add_redact_annot(target_rect, fill=(1, 1, 1))
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_REMOVE, text=fitz.PDF_REDACT_TEXT_NONE)
        page.insert_image(target_rect, filename=new_image_path, overlay=True)

        return {
            "page": page_num,
            "type": "replace_image",
            "success": True,
            "image_index": image_index,
            "xref": xref,
            "rect": [round(target_rect.x0, 2), round(target_rect.y0, 2), round(target_rect.x1, 2), round(target_rect.y1, 2)],
        }
    except Exception as e:
        return {
            "page": page_num,
            "type": "replace_image",
            "success": False,
            "error": str(e),
        }


def _replace_text_scanned(doc, page, page_num, edit):
    find_text = edit.get("find", "")
    replace_text = edit.get("replace", "")
    lang = edit.get("lang", "eng+chi_sim")

    try:
        from PIL import Image, ImageDraw, ImageFont
        import fitz
        import io
        import numpy as np

        if page_num in _processed_images:
            img_data, replaced_count = _processed_images[page_num]
            if replaced_count > 0:
                rect = page.rect
                page.clean_contents()
                page.insert_image(rect, stream=img_data)
                del _processed_images[page_num]
                return {
                    "page": page_num,
                    "type": "replace_text",
                    "success": True,
                    "replaced": replaced_count,
                    "method": "ocr_image",
                    "page_type": "scanned",
                    "parallel": True,
                }
            else:
                del _processed_images[page_num]
                return {
                    "page": page_num,
                    "type": "replace_text",
                    "success": False,
                    "error": f"OCR 未找到文本: {find_text}",
                    "method": "ocr_image",
                    "parallel": True,
                }

        effective_lang = lang
        if any(_is_cjk(c) for c in find_text):
            if 'chi' not in lang:
                effective_lang = lang + '+chi_sim'
        _check_tesseract_langs(effective_lang)

        input_path = edit.get("_input_path", doc.name)
        img, ocr_data = _get_page_ocr(doc, page, page_num, input_path, effective_lang)

        found_regions = _merge_ocr_texts(ocr_data, find_text)

        if not found_regions:
            return {
                "page": page_num,
                "type": "replace_text",
                "success": False,
                "error": f"OCR 未找到文本: {find_text}",
                "method": "ocr_image",
                "lang": effective_lang,
            }

        draw = ImageDraw.Draw(img)
        replaced_count = 0

        for region in found_regions:
            x, y, w, h = region['x'], region['y'], region['w'], region['h']

            img_array = np.array(img)
            padding = 3
            bg_region = img_array[max(0, y - padding):y, max(0, x):x + w]
            if bg_region.size > 0:
                bg_color = tuple(np.median(bg_region.reshape(-1, 3), axis=0).astype(int))
            else:
                bg_color = (255, 255, 255)

            draw.rectangle([x - padding, y - padding, x + w + padding, y + h + padding], fill=bg_color)

            font_size_px = max(10, h)
            font = _get_pil_font(edit.get("font"), font_size_px, replace_text)

            text_color = (0, 0, 0) if sum(bg_color[:3]) > 384 else (255, 255, 255)
            draw.text((x, y), replace_text, fill=text_color, font=font)
            replaced_count += 1

        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)

        rect = page.rect
        page.clean_contents()

        page.insert_image(rect, stream=img_bytes.getvalue())

        return {
            "page": page_num,
            "type": "replace_text",
            "success": replaced_count > 0,
            "replaced": replaced_count,
            "method": "ocr_image",
            "page_type": "scanned",
            "lang": effective_lang,
        }

    except ImportError as e:
        return {
            "page": page_num,
            "type": "replace_text",
            "success": False,
            "error": f"缺少依赖: {e}。请安装: pip install pytesseract Pillow numpy",
            "method": "ocr_image",
        }
    except RuntimeError as e:
        return {
            "page": page_num,
            "type": "replace_text",
            "success": False,
            "error": str(e),
            "method": "ocr_image",
        }
    except Exception as e:
        return {
            "page": page_num,
            "type": "replace_text",
            "success": False,
            "error": str(e),
            "method": "ocr_image",
        }


def _dry_run_preview(doc, page_types, edits, total_pages):
    import time
    start_time = time.time()

    preview_results = []
    affected_pages = set()
    overall_risk = "low"

    for edit in edits:
        edit_type = edit.get("type", "replace_text")
        page_num = edit.get("page", -1)

        if page_num == -1:
            target_pages = list(range(total_pages))
        else:
            target_pages = [page_num]

        for pg in target_pages:
            if pg >= total_pages:
                continue

            page = doc[pg]
            pg_type = page_types.get(pg, "text")
            result = {
                "page": pg,
                "edit_type": edit_type,
                "page_type": pg_type,
                "matches": 0,
                "method": "unknown",
                "risk": "low",
                "warnings": [],
            }

            if edit_type == "replace_text":
                find_text = edit.get("find", "")
                if find_text:
                    if pg_type == "scanned":
                        result["method"] = "ocr_image"
                        result["risk"] = "medium"
                        result["warnings"].append("扫描件需要 OCR 处理，识别可能不准确")
                        result["matches"] = -1  # 无法预知匹配数
                        overall_risk = "medium"
                    else:
                        instances = page.search_for(find_text)
                        result["matches"] = len(instances)
                        result["method"] = "pymupdf_redact"
                        if len(instances) == 0:
                            result["risk"] = "low"
                            result["warnings"].append(f"未找到文本: {find_text}")
                        elif len(instances) > 10:
                            result["risk"] = "medium"
                            result["warnings"].append(f"匹配数量较多({len(instances)}处)，请确认是否全部替换")

                    if result["matches"] != 0:
                        affected_pages.add(pg)

            elif edit_type == "add_text":
                result["method"] = "pymupdf_textwriter"
                result["risk"] = "low"
                result["matches"] = 1
                affected_pages.add(pg)

            elif edit_type == "delete_text":
                find_text = edit.get("find", "")
                if find_text:
                    instances = page.search_for(find_text)
                    result["matches"] = len(instances)
                    result["method"] = "pymupdf_redact"
                    if len(instances) > 0:
                        affected_pages.add(pg)

            elif edit_type == "replace_image":
                images = page.get_images()
                image_index = edit.get("image_index", 0)
                if image_index < len(images):
                    result["matches"] = 1
                    result["method"] = "pymupdf_replace_image"
                    affected_pages.add(pg)
                else:
                    result["matches"] = 0
                    result["warnings"].append(f"图片索引超出范围: {image_index} >= {len(images)}")

            preview_results.append(result)

    scanned_pages = sum(1 for pg in affected_pages if page_types.get(pg) == "scanned")
    text_pages = len(affected_pages) - scanned_pages
    estimated_seconds = text_pages * 0.5 + scanned_pages * 12.0

    elapsed = time.time() - start_time

    return {
        "success": True,
        "dry_run": True,
        "preview": preview_results,
        "summary": {
            "total_edits": len(preview_results),
            "affected_pages": sorted(affected_pages),
            "affected_page_count": len(affected_pages),
            "total_pages": total_pages,
            "page_types": page_types,
            "overall_risk": overall_risk,
            "estimated_time": f"{estimated_seconds:.1f}s",
            "preview_time": f"{elapsed:.3f}s",
        },
        "recommendations": _generate_recommendations(page_types, preview_results, affected_pages),
    }


def _generate_recommendations(page_types, preview_results, affected_pages):
    recommendations = []

    scanned_pages = [pg for pg in affected_pages if page_types.get(pg) == "scanned"]
    if scanned_pages:
        recommendations.append(
            f"第 {', '.join(str(p+1) for p in scanned_pages)} 页为扫描件，"
            "建议先使用 pdf_ocr_locate 确认 OCR 识别结果"
        )

    no_match = [r for r in preview_results if r.get("matches", 0) == 0 and r["edit_type"] in ("replace_text", "delete_text")]
    if no_match:
        recommendations.append(
            f"有 {len(no_match)} 个编辑操作未找到匹配文本，"
            "建议检查查找文本是否正确（注意空格和特殊字符）"
        )

    many_matches = [r for r in preview_results if r.get("matches", 0) > 10]
    if many_matches:
        recommendations.append(
            "部分编辑操作匹配数量较多，建议指定具体页码范围以避免误替换"
        )

    return recommendations


_BUNDLED_CJK_FONT = BUNDLED_FONT


def _find_cjk_font_path():
    return resolve_font(require_full_cjk=True)


def _is_subset_font(font_name):
    import re
    return bool(re.match(r'^[A-Z]{6}\+', font_name))


def _get_base_font_name(font_name):
    import re
    match = re.match(r'^[A-Z]{6}\+(.+)$', font_name)
    return match.group(1) if match else font_name


def _check_font_has_glyphs(font_data, text):
    try:
        from fontTools.ttLib import TTFont
        from io import BytesIO

        font = TTFont(BytesIO(font_data))
        cmap = font.getBestCmap()
        if not cmap:
            return False
        for char in text:
            if ord(char) > 127 and ord(char) not in cmap:  # 只检查非 ASCII 字符
                return False
        return True
    except Exception:
        return False


def _extract_embedded_font(doc, page, find_text):
    import fitz

    text_dict = page.get_text("dict")
    target_font_name = None

    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                span_text = span.get("text", "")
                normalized_span = span_text.replace(" ", "").replace("\u3000", "")
                normalized_find = find_text.replace(" ", "").replace("\u3000", "")
                if find_text in span_text or normalized_find in normalized_span:
                    target_font_name = span.get("font", "")
                    break
            if target_font_name:
                break
        if target_font_name:
            break

    if not target_font_name:
        return None

    try:
        page_fonts = doc.get_page_fonts(page.number, full=True)
        for font_info in page_fonts:
            xref = font_info[0]
            font_name_in_pdf = font_info[3] if len(font_info) > 3 else ""

            base_target = _get_base_font_name(target_font_name)
            base_pdf = _get_base_font_name(font_name_in_pdf)

            if base_target in base_pdf or base_pdf in base_target or target_font_name == font_name_in_pdf:
                font_data = doc.extract_font(xref)
                if font_data and len(font_data) >= 4 and font_data[3]:
                    font_buffer = font_data[3]
                    font_ext = font_data[1]  # "ttf", "otf", "cff" 等
                    actual_name = font_data[0]
                    print(f"[INFO] 提取嵌入字体: {actual_name} ({font_ext}, {len(font_buffer)} bytes, "
                          f"subset={_is_subset_font(target_font_name)})", file=sys.stderr)
                    return font_buffer, actual_name, font_ext
    except Exception as e:
        print(f"[WARN] 提取嵌入字体失败: {e}", file=sys.stderr)

    return None


def _find_system_font_by_name(font_name):
    import subprocess

    base_name = _get_base_font_name(font_name)

    font_aliases = {
        "SimSun": ["SimSun", "simsun", "NSimSun", "宋体"],
        "SimHei": ["SimHei", "simhei", "黑体"],
        "FangSong": ["FangSong", "fangsong", "仿宋"],
        "KaiTi": ["KaiTi", "kaiti", "楷体"],
        "Microsoft YaHei": ["Microsoft YaHei", "msyh", "微软雅黑"],
        "STSong": ["STSong", "STSong-Light", "华文宋体"],
        "STHeiti": ["STHeiti", "STHeiti-Light", "华文黑体"],
        "STFangsong": ["STFangsong", "华文仿宋"],
        "STKaiti": ["STKaiti", "华文楷体"],
    }

    search_names = [base_name]
    for key, aliases in font_aliases.items():
        if base_name.lower() in [a.lower() for a in [key] + aliases]:
            search_names.extend(aliases)
            break

    for name in search_names:
        try:
            result = subprocess.run(
                ['fc-match', '-f', '%{file}', name],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                path = result.stdout.strip()
                if os.path.exists(path):
                    if name.lower() in path.lower() or base_name.lower() in path.lower():
                        return path
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass

    return None


_FONT_FAMILY_MAP = [
    ("fangsong", ["FangSong", "STFangsong", "仿宋"]),
    ("kai", ["Kai", "STKaiti", "楷"]),
    ("sans", ["Hei", "Gothic", "Sans", "SimHei", "STHeiti", "NotoSans", "Droid", "WenQuanYi"]),
    ("serif", ["Song", "Ming", "Serif", "Times", "SimSun", "STSong", "NotoSerif"]),
]


def _get_font_family(font_name):
    base_name = _get_base_font_name(font_name).lower()
    for family, keywords in _FONT_FAMILY_MAP:
        if any(kw.lower() in base_name for kw in keywords):
            return family
    return "unknown"


def _find_family_font_path(font_family):
    family_paths = {
        "serif": [
            "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSerifCJK-Regular.ttc",
            "/usr/share/fonts/noto-cjk/NotoSerifCJK-Regular.ttc",
        ],
        "sans": [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
            "/usr/share/fonts/truetype/droid/DroidSansFallback.ttf",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        ],
        "fangsong": [
            "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
        ],
        "kai": [
            "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
        ],
    }

    paths = family_paths.get(font_family, [])
    for p in paths:
        if os.path.exists(p):
            return p
    return None


def _get_font(font_path=None, original_font_name=None, doc=None, page=None, find_text=None, replace_text=None):
    import fitz
    import tempfile

    if font_path and os.path.exists(font_path):
        print(f"[FONT] 使用用户指定字体: {font_path}", file=sys.stderr)
        from pdfkit.font_manager import make_fitz_font
        return make_fitz_font(font_path)

    if doc and page and find_text:
        extracted = _extract_embedded_font(doc, page, find_text)
        if extracted:
            font_buffer, font_name, font_ext = extracted
            is_subset = _is_subset_font(font_name) if font_name else False

            if is_subset and replace_text:
                has_glyphs = _check_font_has_glyphs(font_buffer, replace_text)
                if not has_glyphs:
                    print(f"[FONT] 子集字体 {font_name} 缺少 '{replace_text}' 的字形，跳过", file=sys.stderr)
                else:
                    try:
                        return fitz.Font(fontbuffer=font_buffer)
                    except Exception as e:
                        print(f"[FONT] 加载子集字体失败: {e}", file=sys.stderr)
            elif not is_subset:
                try:
                    return fitz.Font(fontbuffer=font_buffer)
                except Exception as e:
                    print(f"[FONT] 加载嵌入字体失败: {e}", file=sys.stderr)

    if original_font_name:
        system_font = _find_system_font_by_name(original_font_name)
        if system_font:
            try:
                print(f"[FONT] 使用系统同名字体: {system_font}", file=sys.stderr)
                from pdfkit.font_manager import make_fitz_font
                return make_fitz_font(system_font)
            except Exception as e:
                print(f"[FONT] 加载系统同名字体失败: {e}", file=sys.stderr)

    if original_font_name:
        family = _get_font_family(original_font_name)
        if family != "unknown":
            family_path = _find_family_font_path(family)
            if family_path:
                try:
                    print(f"[FONT] 使用同族字体 ({family}): {family_path}", file=sys.stderr)
                    from pdfkit.font_manager import make_fitz_font
                    return make_fitz_font(family_path)
                except Exception as e:
                    print(f"[FONT] 加载同族字体失败: {e}", file=sys.stderr)

    if original_font_name:
        try:
            font_lower = original_font_name.lower()
            cjk_keywords = ["song", "sim", "hei", "kai", "ming", "gothic",
                           "noto", "cjk", "droid", "wqy", "fang"]
            if any(kw in font_lower for kw in cjk_keywords):
                try:
                    return fitz.Font("china-s")
                except Exception:
                    pass
        except Exception:
            pass

    cjk_path = _find_cjk_font_path()
    if cjk_path:
        try:
            print(f"[FONT] 使用通用 CJK 字体: {cjk_path}", file=sys.stderr)
            from pdfkit.font_manager import make_fitz_font
            return make_fitz_font(cjk_path)
        except Exception:
            pass

    print(f"[FONT] 回退到 Helvetica", file=sys.stderr)
    return fitz.Font("helv")


def _get_pil_font(font_path, font_size, text="", doc=None, page=None, find_text=None):
    from PIL import ImageFont

    if font_path and os.path.exists(font_path):
        try:
            from pdfkit.font_manager import make_pil_font
            return make_pil_font(font_path, font_size)
        except (IOError, OSError):
            pass

    needs_cjk = any(_is_cjk(c) for c in text) if text else False

    if needs_cjk and doc and page and find_text:
        try:
            extracted = _extract_embedded_font(doc, page, find_text)
            if extracted:
                font_buffer, font_name, font_ext = extracted
                is_subset = _is_subset_font(font_name) if font_name else False
                can_use = True
                if is_subset and text:
                    can_use = _check_font_has_glyphs(font_buffer, text)
                if can_use:
                    from io import BytesIO
                    return ImageFont.truetype(BytesIO(font_buffer), font_size)
        except Exception as e:
            print(f"[WARN] PIL 加载嵌入字体失败: {e}", file=sys.stderr)

    if needs_cjk:
        cjk_path = _find_cjk_font_path()
        if cjk_path:
            try:
                from pdfkit.font_manager import make_pil_font
                return make_pil_font(cjk_path, font_size)
            except (IOError, OSError):
                pass

        print(
            f"[WARN] 未找到 CJK 中文字体，中文文字可能显示为方框（□）。"
            f"请安装中文字体: "
            f"Ubuntu/Debian: apt install fonts-noto-cjk 或 fonts-wqy-zenhei | "
            f"CentOS/RHEL: yum install google-droid-sans-fonts 或 google-noto-cjk-fonts | "
            f"或将中文字体文件放入 {os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')} 目录",
            file=sys.stderr
        )

    _win_fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    fallback_paths = [
        os.path.join(_win_fonts, "arial.ttf"),
        os.path.join(_win_fonts, "segoeui.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ]
    for dp in fallback_paths:
        try:
            if os.path.exists(dp):
                return ImageFont.truetype(dp, font_size)
        except (IOError, OSError):
            pass
    return ImageFont.load_default()


def handler(params):
    import fitz

    input_path = params["input"]
    output_path = params["output"]
    edits = params.get("edits", [])
    dry_run = params.get("dry_run", False)

    if not edits:
        raise ValueError("edits 列表不能为空")

    doc = fitz.open(input_path)
    total_pages = len(doc)

    page_types = _detect_page_types(doc)

    if dry_run:
        preview = _dry_run_preview(doc, page_types, edits, total_pages)
        doc.close()
        return preview

    _clear_ocr_cache()
    _clear_processed_images()

    edit_page_pairs = []
    for edit in edits:
        edit_type = edit.get("type", "replace_text")
        page_num = edit.get("page", -1)

        if page_num == -1:
            target_pages = list(range(total_pages))
        else:
            target_pages = [page_num]

        for pg in target_pages:
            if pg >= total_pages:
                continue
            edit_page_pairs.append((edit, pg))

    scanned_ocr_pages = set()
    scanned_ocr_edit_counts = {}
    for edit, pg in edit_page_pairs:
        edit_type = edit.get("type", "replace_text")
        if edit_type in ("replace_text", "delete_text") and page_types.get(pg) == "scanned":
            scanned_ocr_pages.add(pg)
            scanned_ocr_edit_counts[pg] = scanned_ocr_edit_counts.get(pg, 0) + 1

    has_multi_edit_scanned_page = any(count > 1 for count in scanned_ocr_edit_counts.values())
    if len(scanned_ocr_pages) > 1 and not has_multi_edit_scanned_page:
        _parallel_ocr_warmup(doc, page_types, edit_page_pairs, set(), input_path)
    elif has_multi_edit_scanned_page:
        print("[INFO] 跳过扫描页并行预热：存在同页多条 OCR 编辑，避免重复处理", file=sys.stderr)

    results = []
    for edit, pg in edit_page_pairs:
        edit_type = edit.get("type", "replace_text")
        page = doc[pg]
        pg_type = page_types.get(pg, "text")

        if edit_type == "replace_text":
            result = _edit_replace_text(doc, page, pg, pg_type, edit)
        elif edit_type == "add_text":
            result = _edit_add_text(doc, page, pg, edit)
        elif edit_type == "delete_text":
            result = _edit_delete_text(doc, page, pg, pg_type, edit)
        elif edit_type == "replace_image":
            result = _edit_replace_image(doc, page, pg, edit)
        else:
            result = {
                "page": pg,
                "type": edit_type,
                "success": False,
                "error": f"不支持的编辑类型: {edit_type}",
            }

        results.append(result)

    _clear_ocr_cache()
    _clear_processed_images()

    doc.save(output_path, garbage=4, deflate=True)
    doc.close()

    success_count = sum(1 for r in results if r.get("success", False))
    fail_count = len(results) - success_count

    return {
        "success": True,
        "output": output_path,
        "total_edits": len(results),
        "success_count": success_count,
        "fail_count": fail_count,
        "page_types": page_types,
        "results": results,
        "file_size": os.path.getsize(output_path),
    }


if __name__ == "__main__":
    from pdfkit.base import main
    main(handler, params_schema=PARAMS, description=DESCRIPTION)
