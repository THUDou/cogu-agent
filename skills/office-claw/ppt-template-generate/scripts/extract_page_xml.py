#!/usr/bin/env python3
"""
extract_page_xml.py
Reads PPTX XML (no python-pptx needed) and outputs a JSON with slide
element geometry. Used by extract-page-skeletons.js.

Usage:
  python extract_page_xml.py <pptx_path> <output_json_path>
"""
import sys
import os
import json
import zipfile
import re
import logging
from xml.etree import ElementTree as ET

P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
C = 'http://schemas.openxmlformats.org/drawingml/2006/chart'


def _int(val, default=0):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _xfrm(sp_pr):
    xfrm = sp_pr.find(f'.//{{{A}}}xfrm')
    if xfrm is None:
        return None
    off = xfrm.find(f'{{{A}}}off')
    ext = xfrm.find(f'{{{A}}}ext')
    if off is None or ext is None:
        return None
    return {
        'x': _int(off.get('x', 0)), 'y': _int(off.get('y', 0)),
        'cx': _int(ext.get('cx', 0)), 'cy': _int(ext.get('cy', 0)),
        'rot': _int(xfrm.get('rot', 0)),
        'flip_h': xfrm.get('flipH') == '1',
        'flip_v': xfrm.get('flipV') == '1',
    }


def _fill(el):
    solid = el.find(f'.//{{{A}}}solidFill')
    if solid is None:
        return None
    rgb = solid.find(f'{{{A}}}srgbClr')
    return ('#' + rgb.get('val', '').upper()) if rgb is not None and rgb.get('val') else None


def _stroke(sp_pr):
    ln = sp_pr.find(f'{{{A}}}ln')
    if ln is None:
        return None, 0
    return _fill(ln), _int(ln.get('w', 9144))


def _geom(sp_pr):
    g = sp_pr.find(f'{{{A}}}prstGeom')
    return g.get('prst', 'rect') if g is not None else 'rect'


def parse_sp(sp, z):
    sp_pr = sp.find(f'{{{P}}}spPr')
    if sp_pr is None:
        return None
    xf = _xfrm(sp_pr)
    if xf is None:
        return None
    ph = sp.find(f'.//{{{P}}}ph')
    ph_type = ph.get('type', 'body') if ph is not None else ''
    rpr = sp.find(f'.//{{{A}}}rPr')
    font_sz = _int(rpr.get('sz', 0)) // 100 if rpr is not None else 0
    bold = (rpr.get('b', '0') == '1') if rpr is not None else False
    has_text = sp.find(f'{{{P}}}txBody') is not None
    stroke, stroke_w = _stroke(sp_pr)
    return {'type': 'text' if has_text else 'shape', **xf,
            'fill': _fill(sp_pr), 'stroke': stroke, 'stroke_width': stroke_w,
            'shape_geom': _geom(sp_pr), 'placeholder': ph_type,
            'font_size_pt': font_sz, 'bold': bold, 'z_index': z}


def parse_pic(pic, z):
    sp_pr = pic.find(f'{{{P}}}spPr')
    if sp_pr is None:
        return None
    xf = _xfrm(sp_pr)
    if xf is None:
        return None
    return {'type': 'picture', **xf, 'z_index': z}


def parse_cxn(cxn, z):
    sp_pr = cxn.find(f'{{{P}}}spPr')
    if sp_pr is None:
        return None
    xf = _xfrm(sp_pr)
    if xf is None:
        return None
    fill = _fill(sp_pr)
    stroke, stroke_w = _stroke(sp_pr)
    return {'type': 'connector', **xf, 'fill': fill,
            'stroke': stroke or fill or '#333333', 'stroke_width': stroke_w,
            'shape_geom': _geom(sp_pr), 'z_index': z}


def parse_frame(frame, z):
    xfrm_el = frame.find(f'{{{P}}}xfrm')
    if xfrm_el is None:
        return None
    off = xfrm_el.find(f'{{{A}}}off')
    ext = xfrm_el.find(f'{{{A}}}ext')
    if off is None or ext is None:
        return None
    x, y = _int(off.get('x')), _int(off.get('y'))
    cx, cy = _int(ext.get('cx')), _int(ext.get('cy'))
    tbl = frame.find(f'.//{{{A}}}tbl')
    if tbl is not None:
        rows_list = tbl.findall(f'.//{{{A}}}tr')
        rows = len(rows_list)
        cols = len(rows_list[0].findall(f'{{{A}}}tc')) if rows_list else 0
        return {'type': 'table', 'x': x, 'y': y, 'cx': cx, 'cy': cy,
                'rows': rows, 'cols': cols, 'z_index': z}
    if frame.find(f'.//{{{C}}}chart') is not None:
        return {'type': 'chart', 'x': x, 'y': y, 'cx': cx, 'cy': cy,
                'chart_type': 'unknown', 'z_index': z}
    return {'type': 'unknown_frame', 'x': x, 'y': y, 'cx': cx, 'cy': cy, 'z_index': z}


def _apply_grp_transform(el, grp_params):
    gx, gy, gcx, gcy, ch_off, ch_ext = grp_params
    if ch_off is None or ch_ext is None:
        return el
    chx, chy = _int(ch_off.get('x')), _int(ch_off.get('y'))
    ch_cx = _int(ch_ext.get('cx')) or 1
    ch_cy = _int(ch_ext.get('cy')) or 1
    return {**el,
            'x': gx + (el['x'] - chx) * gcx // ch_cx,
            'y': gy + (el['y'] - chy) * gcy // ch_cy,
            'cx': el['cx'] * gcx // ch_cx,
            'cy': el['cy'] * gcy // ch_cy}


def parse_tree(container, z_start, grp_ctx=None):
    elements, z = [], z_start
    for child in container:
        tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        el = None
        if tag == 'sp':
            el = parse_sp(child, z)
        elif tag == 'pic':
            el = parse_pic(child, z)
        elif tag == 'cxnSp':
            el = parse_cxn(child, z)
        elif tag == 'graphicFrame':
            el = parse_frame(child, z)
        elif tag == 'grpSp':
            el = parse_grp(child, z)
        if el is not None:
            if grp_ctx is not None:
                el = _apply_grp_transform(el, grp_ctx)
            elements.append(el)
        z += 1
    return elements


def parse_grp(grp, z):
    gsp_pr = grp.find(f'{{{P}}}grpSpPr')
    if gsp_pr is None:
        children = parse_tree(grp, 0, grp_ctx=None)
        return {'type': 'group', 'x': 0, 'y': 0, 'cx': 0, 'cy': 0,
                'children': children, 'z_index': z, 'warning': 'missing group transform'}
    xfrm = gsp_pr.find(f'{{{A}}}xfrm')
    if xfrm is None:
        children = parse_tree(grp, 0, grp_ctx=None)
        return {'type': 'group', 'x': 0, 'y': 0, 'cx': 0, 'cy': 0,
                'children': children, 'z_index': z, 'warning': 'missing group transform'}
    off = xfrm.find(f'{{{A}}}off')
    ext = xfrm.find(f'{{{A}}}ext')
    if off is None or ext is None:
        children = parse_tree(grp, 0, grp_ctx=None)
        return {'type': 'group', 'x': 0, 'y': 0, 'cx': 0, 'cy': 0,
                'children': children, 'z_index': z, 'warning': 'missing group transform'}
    gx, gy = _int(off.get('x')), _int(off.get('y'))
    gcx, gcy = _int(ext.get('cx')), _int(ext.get('cy'))
    ch_off = xfrm.find(f'{{{A}}}chOff')
    ch_ext = xfrm.find(f'{{{A}}}chExt')
    children = parse_tree(grp, 0, grp_ctx=(gx, gy, gcx, gcy, ch_off, ch_ext))
    return {'type': 'group', 'x': gx, 'y': gy, 'cx': gcx, 'cy': gcy,
            'children': children, 'z_index': z}


def slide_size(zf):
    try:
        root = ET.fromstring(zf.read('ppt/presentation.xml').decode('utf-8'))
        sz = root.find(f'.//{{{P}}}sldSz')
        if sz is not None:
            return {'width_emu': _int(sz.get('cx', 9144000)),
                    'height_emu': _int(sz.get('cy', 5143500))}
    except Exception:
        logging.debug('Failed to read slide size from presentation.xml, using defaults')
    return {'width_emu': 9144000, 'height_emu': 5143500}


def slide_entries(zf):
    pat = re.compile(r'^ppt/slides/slide(\d+)\.xml$')
    items = []
    for n in zf.namelist():
        m = pat.match(n)
        if m:
            items.append((int(m.group(1)), n))
    return [n for _, n in sorted(items)]


def parse_slide(zf, path, idx):
    try:
        root = ET.fromstring(zf.read(path).decode('utf-8'))
        spt = root.find(f'.//{{{P}}}spTree')
        if spt is None:
            return {'index': idx, 'elements': [], 'warning': 'no spTree'}
        return {'index': idx, 'elements': parse_tree(spt, 0)}
    except Exception as e:
        return {'index': idx, 'elements': [], 'warning': str(e)}


def extract(pptx_path):
    with zipfile.ZipFile(pptx_path, 'r') as zf:
        size = slide_size(zf)
        entries = slide_entries(zf)
        slides = [parse_slide(zf, e, i + 1) for i, e in enumerate(entries)]
    return {'schema_version': 'page-xml-v1', 'slide_size': size,
            'slide_count': len(slides), 'slides': slides}


def main():
    if len(sys.argv) < 3:
        logging.error('Usage: python extract_page_xml.py <pptx> <out.json>')
        sys.exit(1)
    pptx, out = sys.argv[1], sys.argv[2]
    if not os.path.exists(pptx):
        logging.error('Error: not found: %s', pptx)
        sys.exit(1)
    try:
        result = extract(pptx)
    except Exception as e:
        logging.error('Error: %s', e)
        sys.exit(1)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logging.info('Extracted %d slides → %s', result["slide_count"], out)


if __name__ == '__main__':
    main()
