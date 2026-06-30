import sys
import os
import re
import json
import logging
import zipfile
import argparse
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, List, Tuple

NS_P_MAIN = 'http://schemas.openxmlformats.org/presentationml/2006/main'
NS = 'http://schemas.openxmlformats.org/drawingml/2006/main'
NS_R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS_PKG = 'http://schemas.openxmlformats.org/package/2006/relationships'
EMU_PER_CM = 360000

BG_MAX_Z_ORDER = 3
DECOR_REPEAT_MIN_SLIDES = 3
DECOR_STABLE_POS_TOLERANCE_CM = 0.35
SMALL_DECOR_MAX_AREA_RATIO = 0.08
TEXTURE_MIN_AREA_RATIO = 0.25

RENDERABLE_TAGS = {
    f'{{{NS_P_MAIN}}}sp',
    f'{{{NS_P_MAIN}}}pic',
    f'{{{NS_P_MAIN}}}graphicFrame',
    f'{{{NS_P_MAIN}}}cxnSp',
    f'{{{NS_P_MAIN}}}grpSp',
}


def _emu_to_cm(emu: int) -> float:
    return round(emu / EMU_PER_CM, 2)


def _resolve_media(zf: zipfile.ZipFile, rels_path: str, r_embed: str, all_files: set) -> Optional[str]:
    if rels_path not in all_files:
        return None
    rroot = ET.fromstring(zf.read(rels_path).decode('utf-8'))
    for rel in rroot.findall(f'{{{NS_PKG}}}Relationship'):
        if rel.get('Id') == r_embed:
            target = rel.get('Target', '')
            if target.startswith('../'):
                return 'ppt/' + target[3:]
            elif target.startswith('/'):
                return target.lstrip('/')
            else:
                return f'ppt/slides/{target}'
    return None


def _parse_xfrm(elem) -> Dict[str, Any]:
    xfrm = elem.find(f'.//{{{NS}}}xfrm')
    result = {'x_cm': 0.0, 'y_cm': 0.0, 'cx_cm': 0.0, 'cy_cm': 0.0,
              'rotation_deg': 0.0, 'flip_h': False, 'flip_v': False}
    if xfrm is None:
        return result
    rot = xfrm.get('rot', '0')
    result['rotation_deg'] = round(int(rot) / 60000, 2) if rot else 0.0
    result['flip_h'] = xfrm.get('flipH') == '1'
    result['flip_v'] = xfrm.get('flipV') == '1'
    off = xfrm.find(f'{{{NS}}}off')
    ext = xfrm.find(f'{{{NS}}}ext')
    if off is not None:
        result['x_cm'] = _emu_to_cm(int(off.get('x', 0)))
        result['y_cm'] = _emu_to_cm(int(off.get('y', 0)))
    if ext is not None:
        result['cx_cm'] = _emu_to_cm(int(ext.get('cx', 0)))
        result['cy_cm'] = _emu_to_cm(int(ext.get('cy', 0)))
    return result


def _get_shape_name(elem, elem_type: str) -> str:
    if elem_type == 'pic':
        cnvpr = elem.find(f'{{{NS_P_MAIN}}}nvPicPr/{{{NS_P_MAIN}}}cNvPr')
    else:
        cnvpr = elem.find(f'{{{NS_P_MAIN}}}nvSpPr/{{{NS_P_MAIN}}}cNvPr')
    return cnvpr.get('name', '') if cnvpr is not None else ''


def _area_ratio(usage: Dict[str, Any], slide_w_cm: float, slide_h_cm: float) -> float:
    if slide_w_cm <= 0 or slide_h_cm <= 0:
        return 0.0
    return (usage.get('cx_cm', 0.0) * usage.get('cy_cm', 0.0)) / (slide_w_cm * slide_h_cm)


def _is_near_edge(usage: Dict[str, Any], slide_w_cm: float, slide_h_cm: float) -> bool:
    x = usage.get('x_cm', 0.0)
    y = usage.get('y_cm', 0.0)
    w = usage.get('cx_cm', 0.0)
    h = usage.get('cy_cm', 0.0)
    margin_x = max(slide_w_cm * 0.08, 1.2)
    margin_y = max(slide_h_cm * 0.08, 1.0)
    return (
        x <= margin_x or y <= margin_y or
        (x + w) >= (slide_w_cm - margin_x) or
        (y + h) >= (slide_h_cm - margin_y) or
        x < 0 or y < 0 or (x + w) > slide_w_cm or (y + h) > slide_h_cm
    )


def _has_stable_position(usages: List[Dict[str, Any]]) -> bool:
    if len(usages) < 2:
        return False
    first = usages[0]
    keys = ('x_cm', 'y_cm', 'cx_cm', 'cy_cm')
    for usage in usages[1:]:
        for key in keys:
            if abs(usage.get(key, 0.0) - first.get(key, 0.0)) > DECOR_STABLE_POS_TOLERANCE_CM:
                return False
    return True


def _summarize_slides(usages: List[Dict[str, Any]]) -> str:
    slides = sorted({u.get('slide') for u in usages if u.get('slide') is not None})
    if not slides:
        return '-'
    if len(slides) <= 8:
        return ', '.join(str(s) for s in slides)
    return f'{slides[0]}-{slides[-1]} 等 {len(slides)} 页'


def classify_image_assets(image_map_data: Dict[str, Any]) -> Dict[str, Any]:
    slide_count = image_map_data.get('slide_count', 0) or 0
    slide_w = image_map_data.get('slide_width_cm', 0.0) or 0.0
    slide_h = image_map_data.get('slide_height_cm', 0.0) or 0.0
    roles: Dict[str, Any] = {
        'background': [],
        'style_assets': [],
        'unknown': [],
    }
    bg_originals = set()

    for name, info in image_map_data.get('bg_images', {}).items():
        if info.get('original'):
            bg_originals.add(info.get('original'))
        roles['background'].append({
            'path': info.get('saved_as', f'bg_images/{name}'),
            'role': 'background',
            'confidence': 'high',
            'migrate_required': True,
            'evidence': '背景定义或覆盖率>90%的底层形状背景',
            'sources': info.get('sources', []),
        })

    for orig_name, info in image_map_data.get('images', {}).items():
        if orig_name in bg_originals:
            continue
        usages = info.get('usages', [])
        if not usages:
            continue
        slide_set = {u.get('slide') for u in usages if u.get('slide') is not None}
        unique_slide_count = len(slide_set)
        max_area = max((_area_ratio(u, slide_w, slide_h) for u in usages), default=0.0)
        avg_area = sum(_area_ratio(u, slide_w, slide_h) for u in usages) / max(len(usages), 1)
        all_sp_fill = all(u.get('type') == 'sp_fill' for u in usages)
        any_sp_fill = any(u.get('type') == 'sp_fill' for u in usages)
        stable_pos = _has_stable_position(usages)
        near_edge_count = sum(1 for u in usages if _is_near_edge(u, slide_w, slide_h))
        low_z_count = sum(1 for u in usages if u.get('z_order', 999) <= BG_MAX_Z_ORDER)

        role = None
        confidence = None
        evidence: List[str] = []

        if max_area > 0.90 and low_z_count == len(usages):
            role = 'background_texture'
            confidence = 'high'
            evidence.append('覆盖率>90%且位于底层')
        elif any_sp_fill and avg_area >= TEXTURE_MIN_AREA_RATIO and unique_slide_count >= 2:
            role = 'large_texture'
            confidence = 'high'
            evidence.append('形状填充图片，面积较大，并在多页使用')
        elif unique_slide_count >= DECOR_REPEAT_MIN_SLIDES and stable_pos and avg_area <= SMALL_DECOR_MAX_AREA_RATIO:
            role = 'repeated_decoration'
            confidence = 'high'
            evidence.append('跨多页重复出现，位置和尺寸稳定，面积较小')
        elif (
            unique_slide_count >= DECOR_REPEAT_MIN_SLIDES
            and avg_area <= SMALL_DECOR_MAX_AREA_RATIO
            and near_edge_count == len(usages)
        ):
            role = 'edge_decoration'
            confidence = 'high'
            evidence.append('跨多页重复出现，位于边缘/角落，面积较小')
        elif all_sp_fill and avg_area >= TEXTURE_MIN_AREA_RATIO and near_edge_count == len(usages):
            role = 'decorative_texture'
            confidence = 'medium_high'
            evidence.append('形状填充图片，面积较大且贴近/超出页面边界')

        entry = {
            'path': info.get('saved_as', f'assets/{orig_name}'),
            'original': orig_name,
            'role': role or 'unknown',
            'confidence': confidence or 'low',
            'migrate_required': bool(role),
            'usage_count': len(usages),
            'slide_count': unique_slide_count,
            'slides': sorted(slide_set),
            'slides_summary': _summarize_slides(usages),
            'avg_area_ratio': round(avg_area, 4),
            'max_area_ratio': round(max_area, 4),
            'stable_position': stable_pos,
            'near_edge_count': near_edge_count,
            'evidence': '；'.join(evidence) if evidence else '源文件结构信号不足，保持未分类',
        }
        if role:
            roles['style_assets'].append(entry)
        else:
            roles['unknown'].append(entry)

    roles['summary'] = {
        'background_count': len(roles['background']),
        'style_asset_count': len(roles['style_assets']),
        'unknown_count': len(roles['unknown']),
        'method': 'source_only_high_confidence_rules',
    }
    return roles


def extract_bg_images(pptx_path: str, output_dir: str) -> Dict[str, Any]:
    bg_dir = os.path.join(output_dir, 'bg_images')
    bg_map: Dict[str, Any] = {}
    saved_media: Dict[str, str] = {}  # media_path -> saved filename

    with zipfile.ZipFile(pptx_path, 'r') as zf:
        all_files = set(zf.namelist())

        def _save_bg(media_path: str, preferred_name: str) -> Optional[str]:
            if media_path in saved_media:
                return saved_media[media_path]
            if media_path not in all_files:
                return None
            os.makedirs(bg_dir, exist_ok=True)
            ext = os.path.splitext(media_path)[1]
            out_name = preferred_name + ext
            out_path = os.path.join(bg_dir, out_name)
            counter = 1
            while os.path.exists(out_path):
                out_name = f'{preferred_name}_{counter}{ext}'
                out_path = os.path.join(bg_dir, out_name)
                counter += 1
            with open(out_path, 'wb') as f:
                f.write(zf.read(media_path))
            saved_media[media_path] = out_name
            return out_name

        def _find_bg_media(xml_path: str, rels_path: str) -> Optional[str]:
            if xml_path not in all_files:
                return None
            try:
                root = ET.fromstring(zf.read(xml_path).decode('utf-8'))
                bg_pr = root.find(f'.//{{{NS_P_MAIN}}}bgPr')
                if bg_pr is None:
                    return None
                blip_fill = bg_pr.find(f'{{{NS}}}blipFill')
                if blip_fill is None:
                    return None
                blip = blip_fill.find(f'{{{NS}}}blip')
                if blip is None:
                    return None
                r_embed = blip.get(f'{{{NS_R}}}embed', '')
                if not r_embed:
                    return None
                return _resolve_media(zf, rels_path, r_embed, all_files)
            except Exception as e:
                logging.debug('_find_bg_media 解析失败: %s', e)
                return None

        def _register(out_name: str, media_path: str, source: Dict[str, Any]) -> None:
            orig = os.path.basename(media_path)
            if out_name not in bg_map:
                bg_map[out_name] = {
                    'saved_as': f'bg_images/{out_name}',
                    'format': os.path.splitext(out_name)[1].lstrip('.').lower(),
                    'original': orig,
                    'sources': [],
                }
            bg_map[out_name]['sources'].append(source)

        master_files = sorted(
            [f for f in all_files if re.match(r'ppt/slideMasters/slideMaster\d+\.xml$', f)],
            key=lambda x: int(re.search(r'\d+', os.path.basename(x)).group())
        )
        for i, mp in enumerate(master_files, 1):
            rels = mp.replace('/slideMasters/', '/slideMasters/_rels/') + '.rels'
            media = _find_bg_media(mp, rels)
            if media:
                name = _save_bg(media, f'master_{i}')
                if name:
                    _register(name, media, {'type': 'master', 'index': i})

        layout_files = sorted(
            [f for f in all_files if re.match(r'ppt/slideLayouts/slideLayout\d+\.xml$', f)],
            key=lambda x: int(re.search(r'\d+', os.path.basename(x)).group())
        )
        for i, lp in enumerate(layout_files, 1):
            rels = lp.replace('/slideLayouts/', '/slideLayouts/_rels/') + '.rels'
            media = _find_bg_media(lp, rels)
            if media:
                name = _save_bg(media, f'layout_{i}')
                if name:
                    _register(name, media, {'type': 'layout', 'index': i})

        slide_files = sorted(
            [f for f in all_files if re.match(r'ppt/slides/slide\d+\.xml$', f)],
            key=lambda x: int(re.search(r'\d+', x).group())
        )
        for sp in slide_files:
            slide_no = int(re.search(r'\d+', os.path.basename(sp)).group())
            rels = sp.replace('/slides/', '/slides/_rels/') + '.rels'
            media = _find_bg_media(sp, rels)
            if media:
                name = _save_bg(media, f'slide_{slide_no:03d}')
                if name:
                    _register(name, media, {'type': 'slide', 'slide_no': slide_no})

    return bg_map


def extract_images(pptx_path: str, output_dir: str) -> Dict[str, Any]:
    img_dir = os.path.join(output_dir, 'assets')
    os.makedirs(img_dir, exist_ok=True)

    saved_media: Dict[str, str] = {}
    image_map: Dict[str, Any] = {}
    shape_bg_raw: Dict[str, Any] = {}  # media_path -> {data, usages}

    def _save_media(zf: zipfile.ZipFile, media_path: str) -> str:
        if media_path in saved_media:
            return saved_media[media_path]
        basename = os.path.basename(media_path)
        out_name = basename
        out_path = os.path.join(img_dir, out_name)
        if os.path.exists(out_path):
            base, ext = os.path.splitext(basename)
            out_name = f'{base}_{len(saved_media)}{ext}'
            out_path = os.path.join(img_dir, out_name)
        with open(out_path, 'wb') as f:
            f.write(zf.read(media_path))
        saved_media[media_path] = out_name
        return out_name

    with zipfile.ZipFile(pptx_path, 'r') as zf:
        all_files = set(zf.namelist())

        slide_w_cm = slide_h_cm = 0.0
        if 'ppt/presentation.xml' in all_files:
            try:
                pres_root = ET.fromstring(zf.read('ppt/presentation.xml'))
                sz = pres_root.find(f'.//{{{NS_P_MAIN}}}sldSz')
                if sz is not None:
                    slide_w_cm = _emu_to_cm(int(sz.get('cx', 0)))
                    slide_h_cm = _emu_to_cm(int(sz.get('cy', 0)))
            except Exception as e:
                logging.debug('解析 presentation.xml 失败: %s', e)

        slide_files = sorted(
            [f for f in all_files if re.match(r'ppt/slides/slide\d+\.xml', f)],
            key=lambda x: int(re.search(r'\d+', x).group())
        )

        def _process_shape(
            child: ET.Element,
            z_counter: List[int],
            rels_path: str,
            slide_no: int,
        ) -> None:
            tag = child.tag
            current_z = z_counter[0]
            z_counter[0] += 1

            if tag == f'{{{NS_P_MAIN}}}grpSp':
                for sub in child:
                    sub_tag = sub.tag
                    if sub_tag in (
                        f'{{{NS_P_MAIN}}}pic',
                        f'{{{NS_P_MAIN}}}sp',
                        f'{{{NS_P_MAIN}}}grpSp',
                    ):
                        _process_shape(sub, z_counter, rels_path, slide_no)
                return

            if tag == f'{{{NS_P_MAIN}}}pic':
                elem_type = 'pic'
                blip = child.find(f'.//{{{NS}}}blip')
            elif tag == f'{{{NS_P_MAIN}}}sp':
                blip_fill = child.find(f'{{{NS_P_MAIN}}}spPr/{{{NS}}}blipFill')
                if blip_fill is None:
                    blip_fill = child.find(f'.//{{{NS}}}blipFill')
                blip = blip_fill.find(f'{{{NS}}}blip') if blip_fill is not None else None
                elem_type = 'sp_fill'
            else:
                return

            if blip is None:
                return

            r_embed = blip.get(f'{{{NS_R}}}embed', '')
            if not r_embed:
                return

            media_path = _resolve_media(zf, rels_path, r_embed, all_files)
            if not media_path or media_path not in all_files:
                return

            out_name = _save_media(zf, media_path)
            orig_name = os.path.basename(media_path)
            geo = _parse_xfrm(child)
            shape_name = _get_shape_name(child, elem_type)

            if slide_w_cm > 0 and slide_h_cm > 0:
                coverage = (geo['cx_cm'] * geo['cy_cm']) / (slide_w_cm * slide_h_cm)
                if coverage > 0.9 and current_z <= BG_MAX_Z_ORDER:
                    if media_path not in shape_bg_raw:
                        shape_bg_raw[media_path] = {
                            'data': zf.read(media_path),
                            'usages': []
                        }
                    shape_bg_raw[media_path]['usages'].append({
                        'slide_no': slide_no,
                        'z_order': current_z,
                        'coverage_pct': round(coverage * 100, 1)
                    })

            if orig_name not in image_map:
                image_map[orig_name] = {
                    'saved_as': f'assets/{out_name}',
                    'format': os.path.splitext(orig_name)[1].lstrip('.').lower(),
                    'usages': []
                }

            image_map[orig_name]['usages'].append({
                'slide': slide_no,
                'z_order': current_z,
                'type': elem_type,
                'shape_name': shape_name,
                **geo
            })

        for slide_idx, slide_path in enumerate(slide_files):
            slide_no = slide_idx + 1
            rels_path = (slide_path
                         .replace('ppt/slides/slide', 'ppt/slides/_rels/slide')
                         .replace('.xml', '.xml.rels'))
            try:
                root = ET.fromstring(zf.read(slide_path).decode('utf-8'))
            except Exception as e:
                logging.debug('解析幻灯片 %s 失败: %s', slide_path, e)
                continue

            sp_tree = root.find(f'.//{{{NS_P_MAIN}}}spTree')
            if sp_tree is None:
                continue

            z_counter = [0]

            for child in sp_tree:
                if child.tag in RENDERABLE_TAGS:
                    _process_shape(child, z_counter, rels_path, slide_no)

    shape_bg_map: Dict[str, Any] = {}
    if shape_bg_raw:
        bg_dir_shape = os.path.join(output_dir, 'bg_images')
        os.makedirs(bg_dir_shape, exist_ok=True)
        for media_path, info in shape_bg_raw.items():
            orig = os.path.basename(media_path)
            ext = os.path.splitext(orig)[1]
            first_slide = info['usages'][0]['slide_no']
            bg_name = f'slide_{first_slide:03d}_shape_bg{ext}'
            out_path = os.path.join(bg_dir_shape, bg_name)
            counter = 1
            while os.path.exists(out_path):
                bg_name = f'slide_{first_slide:03d}_shape_bg_{counter}{ext}'
                out_path = os.path.join(bg_dir_shape, bg_name)
                counter += 1
            with open(out_path, 'wb') as f:
                f.write(info['data'])
            shape_bg_map[bg_name] = {
                'saved_as': f'bg_images/{bg_name}',
                'format': ext.lstrip('.').lower(),
                'original': orig,
                'source_method': 'shape',
                'sources': [{'type': 'slide', 'slide_no': u['slide_no'],
                              'z_order': u['z_order'],
                              'coverage_pct': u['coverage_pct']}
                             for u in info['usages']]
            }

    total_usages = sum(len(v['usages']) for v in image_map.values())
    bg_images = extract_bg_images(pptx_path, output_dir)
    bg_images.update(shape_bg_map)
    result = {
        'source_file': os.path.basename(pptx_path),
        'slide_count': len(slide_files),
        'slide_width_cm': slide_w_cm,
        'slide_height_cm': slide_h_cm,
        'unique_images': len(image_map),
        'total_usages': total_usages,
        'images': image_map,
        'bg_images': bg_images,
    }
    result['asset_roles'] = classify_image_assets(result)
    return result


def generate_md(image_map_data: Dict[str, Any]) -> str:
    src = image_map_data.get('source_file', '')
    sc = image_map_data.get('slide_count', 0)
    ui = image_map_data.get('unique_images', 0)
    tu = image_map_data.get('total_usages', 0)
    sw = image_map_data.get('slide_width_cm', 0)
    sh = image_map_data.get('slide_height_cm', 0)
    bg = image_map_data.get('bg_images', {})
    roles = image_map_data.get('asset_roles', {})

    lines = [
        '# 图片资产地图\n\n',
        f'> 来源: {src} | 幻灯片: {sc}张 | 内嵌图片: {ui}张（引用{tu}次）| 背景图片: {len(bg)}张\n',
        f'> 幻灯片尺寸: {sw} × {sh} cm\n\n',
    ]

    type_label = {'pic': '独立图片', 'sp_fill': '形状填充'}

    lines.append('## 一、风格迁移图片资产（高置信，生成模板时必须引用）\n')
    if roles:
        bg_roles = roles.get('background', [])
        style_assets = roles.get('style_assets', [])
        lines.append('| 路径 | 角色 | 置信度 | 证据 | 使用页 |')
        lines.append('|------|------|--------|------|--------|')
        for item in bg_roles:
            srcs = item.get('sources', [])
            src_text = []
            for s in srcs:
                if s.get('type') == 'master':
                    src_text.append(f'母版{s.get("index")}')
                elif s.get('type') == 'layout':
                    src_text.append(f'版式{s.get("index")}')
                elif s.get('type') == 'slide':
                    label = f'第{s.get("slide_no")}页'
                    if s.get('coverage_pct') is not None:
                        label += f'({s.get("coverage_pct")}%)'
                    src_text.append(label)
            lines.append(
                f'| `{item["path"]}` | {item["role"]} | {item["confidence"]}'
                f' | {item["evidence"]} | {" / ".join(src_text) or "-"} |'
            )
        for item in style_assets:
            lines.append(
                f'| `{item["path"]}` | {item["role"]} | {item["confidence"]}'
                f' | {item["evidence"]} | {item["slides_summary"]} |'
            )
        if not bg_roles and not style_assets:
            lines.append('| - | - | - | 未检测到高置信风格迁移图片资产 | - |')
        lines.append('\n> 仅上述高置信资产要求在新模板中迁移引用；未分类图片保留在 assets/，不强制使用。\n')
    else:
        lines.append('_未生成资产角色分类。_\n')

    lines.append('## 二、内嵌图片资产（assets/）\n')
    for orig_name, info in image_map_data.get('images', {}).items():
        usages = info['usages']
        lines.append(f'### {orig_name}')
        lines.append(f'路径: `{info["saved_as"]}` | 格式: {info["format"]} | 引用 {len(usages)} 次\n')
        lines.append('| 幻灯片 | 层次(z) | 类型 | x(cm) | y(cm) | 宽(cm) | 高(cm) | 旋转° | 翻转 |')
        lines.append('|-------|--------|------|-------|-------|-------|-------|------|------|')
        for u in usages:
            flip = []
            if u.get('flip_h'):
                flip.append('H')
            if u.get('flip_v'):
                flip.append('V')
            flip_str = '+'.join(flip) if flip else '-'
            lines.append(
                f'| 第{u["slide"]}页 | {u["z_order"]} | {type_label.get(u["type"], u["type"])} '
                f'| {u["x_cm"]} | {u["y_cm"]} | {u["cx_cm"]} | {u["cy_cm"]} '
                f'| {u["rotation_deg"]} | {flip_str} |'
            )
        lines.append('')

    lines.append('## 三、背景图片（bg_images/）\n')
    if bg:
        source_label = {'master': '母版', 'layout': '版式', 'slide': '幻灯片'}
        lines.append('| 文件名 | 来源 | 格式 | 覆盖率 |')
        lines.append('|--------|------|------|--------|')
        for name, info in bg.items():
            method = info.get('source_method', 'bgPr')
            sources_parts = []
            for s in info.get('sources', []):
                if s['type'] == 'master':
                    sources_parts.append(f'母版{s["index"]}')
                elif s['type'] == 'layout':
                    sources_parts.append(f'版式{s["index"]}')
                else:
                    label = f'第{s["slide_no"]}页'
                    if 'coverage_pct' in s:
                        label += f'({s["coverage_pct"]}%)'
                    sources_parts.append(label)
            method_tag = '形状' if method == 'shape' else '背景'
            lines.append(
                f'| `{info["saved_as"]}` | [{method_tag}] {" / ".join(sources_parts)} '
                f'| {info["format"]} | {"见来源" if method == "shape" else "-"} |'
            )
        lines.append('')
    else:
        lines.append('_未检测到背景图片。_\n')

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='提取 PPTX 图片资产')
    parser.add_argument('--input', required=True, help='PPTX 文件路径')
    parser.add_argument('--output', required=True, help='输出目录')
    args = parser.parse_args()

    if not os.path.exists(args.input):
        logging.error('文件不存在: %s', args.input)
        sys.exit(1)

    os.makedirs(args.output, exist_ok=True)

    try:
        logging.info('正在提取图片: %s', args.input)
        data = extract_images(args.input, args.output)

        json_path = os.path.join(args.output, 'image-map.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        md_path = os.path.join(args.output, 'image-map.md')
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(generate_md(data))

        bg_count = len(data.get('bg_images', {}))
        logging.info(
            '提取完成: %d 张内嵌图片（%d 次引用），%d 张背景图片',
            data['unique_images'], data['total_usages'], bg_count
        )
        logging.info('内嵌图片目录: %s', os.path.join(args.output, 'assets'))
        if bg_count:
            logging.info('背景图片目录: %s', os.path.join(args.output, 'bg_images'))
        logging.info('Map 文件: %s', json_path)
        logging.info('MD  文件: %s', md_path)
    except Exception as e:
        logging.error('提取失败: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    main()
