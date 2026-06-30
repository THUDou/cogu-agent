
from __future__ import annotations

import math
from xml.etree import ElementTree as ET

from .emu_units import NS, Xfrm, emu_to_px, fmt_num


def convert_custom_geom(
    cust_geom: ET.Element,
    xfrm: Xfrm,
) -> str | None:
    path_lst = cust_geom.find("a:pathLst", NS)
    if path_lst is None:
        return None

    paths = path_lst.findall("a:path", NS)
    if not paths:
        return None

    d_segments: list[str] = []
    for path_elem in paths:
        d = _convert_one_path(path_elem, xfrm)
        if d:
            d_segments.append(d)

    if not d_segments:
        return None
    return " ".join(d_segments)


def _convert_one_path(path_elem: ET.Element, xfrm: Xfrm) -> str:
    try:
        path_w_emu = int(path_elem.attrib.get("w", "0"))
        path_h_emu = int(path_elem.attrib.get("h", "0"))
    except ValueError:
        return ""
    path_w_px = emu_to_px(path_w_emu) if path_w_emu else xfrm.w
    path_h_px = emu_to_px(path_h_emu) if path_h_emu else xfrm.h
    if path_w_px <= 0 or path_h_px <= 0:
        return ""
    sx = xfrm.w / path_w_px if path_w_px else 1.0
    sy = xfrm.h / path_h_px if path_h_px else 1.0

    def map_pt(x_emu: float, y_emu: float) -> tuple[float, float]:
        x = emu_to_px(x_emu) * sx + xfrm.x
        y = emu_to_px(y_emu) * sy + xfrm.y
        return x, y

    cx, cy = 0.0, 0.0  # slide-absolute pixels

    parts: list[str] = []
    for child in list(path_elem):
        if not isinstance(child.tag, str):
            continue
        local = child.tag.split("}", 1)[-1]
        if local == "moveTo":
            pt = child.find("a:pt", NS)
            if pt is None:
                continue
            x, y = _read_pt(pt, map_pt)
            parts.append(f"M {fmt_num(x)} {fmt_num(y)}")
            cx, cy = x, y
        elif local == "lnTo":
            pt = child.find("a:pt", NS)
            if pt is None:
                continue
            x, y = _read_pt(pt, map_pt)
            parts.append(f"L {fmt_num(x)} {fmt_num(y)}")
            cx, cy = x, y
        elif local == "cubicBezTo":
            pts = child.findall("a:pt", NS)
            if len(pts) < 3:
                continue
            p1 = _read_pt(pts[0], map_pt)
            p2 = _read_pt(pts[1], map_pt)
            p3 = _read_pt(pts[2], map_pt)
            parts.append(
                f"C {fmt_num(p1[0])} {fmt_num(p1[1])} "
                f"{fmt_num(p2[0])} {fmt_num(p2[1])} "
                f"{fmt_num(p3[0])} {fmt_num(p3[1])}"
            )
            cx, cy = p3
        elif local == "quadBezTo":
            pts = child.findall("a:pt", NS)
            if len(pts) < 2:
                continue
            p1 = _read_pt(pts[0], map_pt)
            p2 = _read_pt(pts[1], map_pt)
            parts.append(
                f"Q {fmt_num(p1[0])} {fmt_num(p1[1])} "
                f"{fmt_num(p2[0])} {fmt_num(p2[1])}"
            )
            cx, cy = p2
        elif local == "arcTo":
            arc_d, end_x, end_y = _arc_to_svg(child, cx, cy, sx, sy)
            if arc_d:
                parts.append(arc_d)
                cx, cy = end_x, end_y
        elif local == "close":
            parts.append("Z")

    return " ".join(parts)


def _read_pt(pt_elem: ET.Element, mapper) -> tuple[float, float]:
    try:
        x = float(pt_elem.attrib.get("x", "0"))
        y = float(pt_elem.attrib.get("y", "0"))
    except ValueError:
        x = 0.0
        y = 0.0
    return mapper(x, y)


def _arc_to_svg(
    arc_elem: ET.Element,
    cx: float, cy: float,
    sx: float, sy: float,
) -> tuple[str, float, float]:
    try:
        wR_emu = float(arc_elem.attrib.get("wR", "0"))
        hR_emu = float(arc_elem.attrib.get("hR", "0"))
        st_ang = float(arc_elem.attrib.get("stAng", "0"))
        sw_ang = float(arc_elem.attrib.get("swAng", "0"))
    except ValueError:
        return "", cx, cy

    if wR_emu <= 0 or hR_emu <= 0:
        return "", cx, cy

    rx = emu_to_px(wR_emu) * sx
    ry = emu_to_px(hR_emu) * sy
    st_rad = math.radians(st_ang / 60000.0)
    sw_rad = math.radians(sw_ang / 60000.0)
    end_rad = st_rad + sw_rad

    arc_cx = cx - rx * math.cos(st_rad)
    arc_cy = cy - ry * math.sin(st_rad)
    end_x = arc_cx + rx * math.cos(end_rad)
    end_y = arc_cy + ry * math.sin(end_rad)

    abs_sw = abs(sw_ang) / 60000.0
    large_arc = 1 if abs_sw > 180.0 else 0
    sweep = 1 if sw_ang >= 0 else 0

    return (
        f"A {fmt_num(rx)} {fmt_num(ry)} 0 {large_arc} {sweep} "
        f"{fmt_num(end_x)} {fmt_num(end_y)}",
        end_x,
        end_y,
    )
