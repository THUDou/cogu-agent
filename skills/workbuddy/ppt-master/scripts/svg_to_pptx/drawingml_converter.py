
from __future__ import annotations

import math
import re
from pathlib import Path
from xml.etree import ElementTree as ET

from .drawingml_context import ConvertContext, ShapeResult
from .drawingml_utils import (
    SVG_NS, EMU_PER_PX,
    _extract_inheritable_styles, parse_transform_matrix, resolve_url_id,
)
from .drawingml_styles import build_effect_xml
from .drawingml_elements import (
    convert_rect, convert_circle, convert_ellipse,
    convert_line, convert_path,
    convert_polygon, convert_polyline,
    convert_text, convert_image, convert_nested_svg,
)


class SvgNativeConversionError(RuntimeError):



_CHROME_ID_TOKENS = frozenset({
    'background', 'bg',
    'decoration', 'decorations', 'decor',
    'header', 'footer',
    'chrome', 'watermark',
    'pagenumber', 'pagenum',
})


def _is_chrome_id(elem_id: str | None) -> bool:
    if not elem_id:
        return False
    lower = elem_id.lower()
    if lower.replace('-', '').replace('_', '') in _CHROME_ID_TOKENS:
        return True
    tokens = re.split(r'[-_]', lower)
    return any(t in _CHROME_ID_TOKENS for t in tokens if t)



def parse_transform(transform_str: str) -> tuple[float, float, float, float, float]:
    if not transform_str:
        return 0.0, 0.0, 1.0, 1.0, 0.0

    a, b, c, d, e, f = parse_transform_matrix(transform_str)

    if abs(b) < 1e-9 and abs(c) < 1e-9:
        sx = a if a != 0 else 1.0
        sy = d if d != 0 else 1.0
        return e, f, sx, sy, 0.0

    sx = math.hypot(a, b)
    sy = math.hypot(c, d)
    if sx == 0:
        sx = 1.0
    if sy == 0:
        sy = 1.0

    angle_deg = math.degrees(math.atan2(b, a))
    return e, f, sx, sy, angle_deg


_ROTATE_RE = re.compile(
    r'rotate\(\s*([-\d.eE+]+)(?:[\s,]+([-\d.eE+]+)[\s,]+([-\d.eE+]+))?\s*\)'
)


def _extract_rotate_pivot(transform_str: str) -> tuple[float, float] | None:
    if not transform_str:
        return None
    ops = [op for op in re.findall(r'(\w+)\s*\(', transform_str) if op]
    if ops != ['rotate']:
        return None
    match = _ROTATE_RE.search(transform_str)
    if not match:
        return None
    cx = float(match.group(2)) if match.group(2) is not None else 0.0
    cy = float(match.group(3)) if match.group(3) is not None else 0.0
    return cx, cy



def convert_g(elem: ET.Element, ctx: ConvertContext) -> ShapeResult | None:
    transform = elem.get('transform', '')
    dx, dy, sx, sy, angle_deg = parse_transform(transform)

    filter_id = resolve_url_id(elem.get('filter', ''))
    style_overrides = _extract_inheritable_styles(elem)

    elem_id = elem.get('id')
    should_animate_group = ctx.depth == 0 and elem_id and not _is_chrome_id(elem_id)
    visual_children = [
        child for child in elem
        if child.tag.replace(f'{{{SVG_NS}}}', '') not in _NON_VISUAL_TAGS
    ]
    matrix_supported = bool(transform) and visual_children and all(
        _supports_matrix_transform(child) for child in visual_children
    )
    rotate_pivot = _extract_rotate_pivot(transform) if not matrix_supported else None
    if matrix_supported:
        child_ctx = ctx.child(
            0, 0, 1.0, 1.0,
            transform_matrix=parse_transform_matrix(transform),
            filter_id=filter_id,
            style_overrides=style_overrides,
        )
    elif rotate_pivot is not None:
        child_ctx = ctx.child(
            0, 0, 1.0, 1.0,
            filter_id=filter_id,
            style_overrides=style_overrides,
        )
    else:
        child_ctx = ctx.child(dx, dy, sx, sy, filter_id=filter_id, style_overrides=style_overrides)

    child_results: list[ShapeResult] = []
    for child in elem:
        result = convert_element(child, child_ctx)
        if result:
            child_results.append(result)

    ctx.sync_from_child(child_ctx)

    if not child_results:
        return None

    if len(child_results) == 1 and not should_animate_group:
        return child_results[0]

    min_x = min_y = float('inf')
    max_x = max_y = float('-inf')

    for child_result in child_results:
        bounds = child_result.bounds_emu
        if bounds is None:
            continue
        min_x = min(min_x, bounds[0])
        min_y = min(min_y, bounds[1])
        max_x = max(max_x, bounds[2])
        max_y = max(max_y, bounds[3])

    if min_x == float('inf'):
        return ShapeResult(xml='\n'.join(result.xml for result in child_results))

    group_x = int(min_x)
    group_y = int(min_y)
    group_w = max(int(max_x - min_x), 1)
    group_h = max(int(max_y - min_y), 1)

    off_x = group_x
    off_y = group_y
    if rotate_pivot is not None and angle_deg:
        cx_svg, cy_svg = rotate_pivot
        pivot_ex = (cx_svg + ctx.translate_x) * EMU_PER_PX
        pivot_ey = (cy_svg + ctx.translate_y) * EMU_PER_PX
        bbox_cx = group_x + group_w / 2
        bbox_cy = group_y + group_h / 2
        theta = math.radians(angle_deg)
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        delta_x = (bbox_cx - pivot_ex) * cos_t - (bbox_cy - pivot_ey) * sin_t + pivot_ex - bbox_cx
        delta_y = (bbox_cx - pivot_ex) * sin_t + (bbox_cy - pivot_ey) * cos_t + pivot_ey - bbox_cy
        off_x = int(round(group_x + delta_x))
        off_y = int(round(group_y + delta_y))

    shapes_xml = '\n'.join(result.xml for result in child_results)
    group_id = ctx.next_id()

    if should_animate_group:
        ctx.anim_targets.append((group_id, elem_id))

    group_effect = ''
    if filter_id and filter_id in ctx.defs:
        group_effect = build_effect_xml(ctx.defs[filter_id])

    rot_emu = 0 if matrix_supported else int(angle_deg * 60000)
    rot_attr = f' rot="{rot_emu}"' if rot_emu else ''

    return ShapeResult(xml=f'''<p:grpSp>
<p:nvGrpSpPr>
<p:cNvPr id="{group_id}" name="Group {group_id}"/>
<p:cNvGrpSpPr/>
<p:nvPr/>
</p:nvGrpSpPr>
<p:grpSpPr>
<a:xfrm{rot_attr}>
<a:off x="{off_x}" y="{off_y}"/>
<a:ext cx="{group_w}" cy="{group_h}"/>
<a:chOff x="{group_x}" y="{group_y}"/>
<a:chExt cx="{group_w}" cy="{group_h}"/>
</a:xfrm>
{group_effect}
</p:grpSpPr>
{shapes_xml}
</p:grpSp>''', bounds_emu=(group_x, group_y, group_x + group_w, group_y + group_h))



_NON_VISUAL_TAGS = frozenset(('defs', 'title', 'desc', 'metadata', 'style'))


def _supports_matrix_transform(elem: ET.Element) -> bool:
    tag = elem.tag.replace(f'{{{SVG_NS}}}', '')
    if tag == 'image':
        return True
    if tag == 'svg':
        visual_children = [
            child for child in elem
            if child.tag.replace(f'{{{SVG_NS}}}', '') not in _NON_VISUAL_TAGS
        ]
        return len(visual_children) == 1 and (
            visual_children[0].tag.replace(f'{{{SVG_NS}}}', '') == 'image'
        )
    if tag == 'g':
        visual_children = [
            child for child in elem
            if child.tag.replace(f'{{{SVG_NS}}}', '') not in _NON_VISUAL_TAGS
        ]
        return bool(visual_children) and all(
            _supports_matrix_transform(child) for child in visual_children
        )
    return False

_CONVERTERS = {
    'rect': convert_rect,
    'circle': convert_circle,
    'ellipse': convert_ellipse,
    'line': convert_line,
    'path': convert_path,
    'polygon': convert_polygon,
    'polyline': convert_polyline,
    'text': convert_text,
    'image': convert_image,
    'g': convert_g,
    'svg': convert_nested_svg,
}

_SUPPORTED_VISUAL_CHILD_TAGS = frozenset(('tspan',))


def collect_defs(root: ET.Element) -> dict[str, ET.Element]:
    defs: dict[str, ET.Element] = {}
    for defs_elem in root.iter(f'{{{SVG_NS}}}defs'):
        for child in defs_elem:
            elem_id = child.get('id')
            if elem_id:
                defs[elem_id] = child
    for defs_elem in root.iter('defs'):
        for child in defs_elem:
            elem_id = child.get('id')
            if elem_id:
                defs[elem_id] = child
    return defs


def convert_element(elem: ET.Element, ctx: ConvertContext) -> ShapeResult | None:
    tag = elem.tag.replace(f'{{{SVG_NS}}}', '')

    converter = _CONVERTERS.get(tag)
    if converter:
        try:
            return converter(elem, ctx)
        except Exception as e:
            raise SvgNativeConversionError(f'Failed to convert <{tag}>: {e}') from e

    if tag in _NON_VISUAL_TAGS:
        return None

    raise SvgNativeConversionError(f'Unsupported visual SVG element <{tag}>')


def _local_tag(elem: ET.Element) -> str:
    return elem.tag.split('}', 1)[-1] if isinstance(elem.tag, str) and '}' in elem.tag else str(elem.tag)


def _collect_unsupported_visuals(root: ET.Element) -> list[str]:
    issues: list[str] = []

    def walk(elem: ET.Element, path: str, in_defs: bool = False) -> None:
        tag = _local_tag(elem)
        current = f'{path}/{tag}'
        if in_defs:
            return
        if tag in _NON_VISUAL_TAGS:
            return
        if (tag not in _CONVERTERS
                and tag not in _NON_VISUAL_TAGS
                and tag not in _SUPPORTED_VISUAL_CHILD_TAGS):
            issues.append(current)
        for idx, child in enumerate(list(elem), start=1):
            walk(child, f'{current}[{idx}]', in_defs=(tag == 'defs'))

    for idx, child in enumerate(list(root), start=1):
        walk(child, f'/svg[{idx}]')
    return issues


def convert_svg_to_slide_shapes(
    svg_path: Path,
    slide_num: int = 1,
    verbose: bool = False,
) -> tuple[str, dict[str, bytes], list[dict[str, str]], list]:
    tree = ET.parse(str(svg_path))
    root = tree.getroot()

    icons_dir = Path(__file__).resolve().parent.parent.parent / 'templates' / 'icons'
    if icons_dir.exists():
        from .use_expander import expand_use_data_icons
        expanded = expand_use_data_icons(root, icons_dir)
        if verbose and expanded:
            print(f'  Expanded {expanded} <use data-icon="..."/> placeholder(s)')

    from .tspan_flattener import flatten_positional_tspans
    if flatten_positional_tspans(tree) and verbose:
        print('  Flattened positional <tspan> into independent <text>')

    unsupported = _collect_unsupported_visuals(root)
    if unsupported:
        preview = '; '.join(unsupported[:8])
        suffix = '' if len(unsupported) <= 8 else f'; +{len(unsupported) - 8} more'
        raise SvgNativeConversionError(
            f'{svg_path.name}: unsupported visual SVG element(s): {preview}{suffix}'
        )

    defs = collect_defs(root)
    ctx = ConvertContext(defs=defs, slide_num=slide_num, svg_dir=Path(svg_path).parent)

    shapes: list[str] = []
    converted = 0
    skipped = 0
    fallback_targets: list = []

    for child in root:
        tag = child.tag.replace(f'{{{SVG_NS}}}', '')
        if tag == 'defs':
            continue
        result = convert_element(child, ctx)
        if result:
            shapes.append(result.xml)
            converted += 1
            m = re.search(r'<p:cNvPr id="(\d+)"', result.xml)
            if m:
                fallback_targets.append((int(m.group(1)), tag))
        else:
            if tag not in _NON_VISUAL_TAGS:
                skipped += 1

    _ANIM_FALLBACK_CAP = 8
    if not ctx.anim_targets and 0 < len(fallback_targets) <= _ANIM_FALLBACK_CAP:
        ctx.anim_targets = fallback_targets

    if verbose:
        print(f'  Converted {converted} elements, skipped {skipped}')

    shapes_xml = '\n'.join(shapes)

    slide_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
       xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
       xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
<p:cSld>
<p:spTree>
<p:nvGrpSpPr>
<p:cNvPr id="1" name=""/>
<p:cNvGrpSpPr/><p:nvPr/>
</p:nvGrpSpPr>
<p:grpSpPr>
<a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>
<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm>
</p:grpSpPr>
{shapes_xml}
</p:spTree>
</p:cSld>
<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>'''

    return slide_xml, ctx.media_files, ctx.rel_entries, ctx.anim_targets
