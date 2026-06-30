
from __future__ import annotations

from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

from .color_resolver import ColorPalette, find_color_elem, resolve_color
from .emu_units import NS, emu_to_px, fmt_num


@dataclass
class StrokeResult:

    attrs: dict[str, str] = field(default_factory=dict)
    defs: list[str] = field(default_factory=list)


PRST_DASH_TO_ARRAY = {
    "solid": None,           # no dasharray
    "dot": "1 3",
    "dash": "4 4",
    "lgDash": "8 4",
    "dashDot": "4 4 1 4",
    "lgDashDot": "8 4 2 4",
    "lgDashDotDot": "8 4 2 4 2 4",
    "sysDash": "3 3",
    "sysDot": "1 3",
    "sysDashDot": "3 3 1 3",
    "sysDashDotDot": "3 3 1 3 1 3",
}

CAP_MAP = {
    "rnd": "round",
    "sq": "square",
    "flat": "butt",
}


def resolve_stroke(
    sp_pr: ET.Element | None,
    palette: ColorPalette | None,
    *,
    id_prefix: str = "m",
    id_seq: list[int] | None = None,
    style_stroke_default: str | None = None,
) -> StrokeResult:
    if sp_pr is None:
        return StrokeResult()

    ln = sp_pr.find("a:ln", NS)
    if ln is None:
        return StrokeResult()

    attrs: dict[str, str] = {}
    defs: list[str] = []

    width_emu = ln.attrib.get("w")
    if width_emu is not None:
        try:
            width_px = emu_to_px(int(width_emu))
            attrs["stroke-width"] = fmt_num(width_px, 3)
        except (ValueError, TypeError):
            pass

    cap = ln.attrib.get("cap")
    if cap and cap in CAP_MAP:
        attrs["stroke-linecap"] = CAP_MAP[cap]

    no_fill = ln.find("a:noFill", NS)
    if no_fill is not None:
        attrs["stroke"] = "none"
    else:
        solid = ln.find("a:solidFill", NS)
        if solid is not None:
            color_elem = find_color_elem(solid)
            hex_, alpha = resolve_color(color_elem, palette)
            if hex_:
                attrs["stroke"] = hex_
                if alpha < 1.0:
                    attrs["stroke-opacity"] = fmt_num(alpha, 4)
        else:
            grad = ln.find("a:gradFill", NS)
            if grad is not None:
                first_gs = grad.find("a:gsLst/a:gs", NS)
                if first_gs is not None:
                    color_elem = find_color_elem(first_gs)
                    hex_, alpha = resolve_color(color_elem, palette)
                    if hex_:
                        attrs["stroke"] = hex_
                        if alpha < 1.0:
                            attrs["stroke-opacity"] = fmt_num(alpha, 4)

    prst_dash = ln.find("a:prstDash", NS)
    if prst_dash is not None:
        preset = prst_dash.attrib.get("val", "")
        dasharray = PRST_DASH_TO_ARRAY.get(preset)
        if dasharray:
            attrs["stroke-dasharray"] = dasharray
    else:
        cust_dash = ln.find("a:custDash", NS)
        if cust_dash is not None:
            ds_parts: list[str] = []
            sw = float(attrs.get("stroke-width", "1") or "1") or 1.0
            for ds in cust_dash.findall("a:ds", NS):
                try:
                    d_pct = int(ds.attrib.get("d", "0"))
                    sp_pct = int(ds.attrib.get("sp", "0"))
                except ValueError:
                    continue
                ds_parts.append(fmt_num(d_pct / 100000.0 * sw, 2))
                ds_parts.append(fmt_num(sp_pct / 100000.0 * sw, 2))
            if ds_parts:
                attrs["stroke-dasharray"] = " ".join(ds_parts)

    if ln.find("a:round", NS) is not None:
        attrs["stroke-linejoin"] = "round"
    elif ln.find("a:bevel", NS) is not None:
        attrs["stroke-linejoin"] = "bevel"
    elif ln.find("a:miter", NS) is not None:
        attrs["stroke-linejoin"] = "miter"

    if id_seq is None:
        id_seq = [0]
    for which, attr in (("headEnd", "marker-start"), ("tailEnd", "marker-end")):
        end_elem = ln.find(f"a:{which}", NS)
        if end_elem is None:
            continue
        marker_color = attrs.get("stroke") or style_stroke_default or "#000000"
        marker_id, marker_def = _build_arrow_marker(
            end_elem,
            marker_color,
            id_prefix=id_prefix,
            seq=id_seq,
            reversed_=(which == "headEnd"),
        )
        if marker_id is None:
            continue
        defs.append(marker_def)
        attrs[attr] = f"url(#{marker_id})"

    return StrokeResult(attrs=attrs, defs=defs)



SIZE_BUCKET = {"sm": 3.0, "med": 5.0, "lg": 7.0}


def _build_arrow_marker(
    end_elem: ET.Element,
    stroke_color: str,
    *,
    id_prefix: str,
    seq: list[int],
    reversed_: bool,
) -> tuple[str | None, str]:
    typ = end_elem.attrib.get("type", "")
    if typ in ("none", ""):
        return None, ""

    w_b = end_elem.attrib.get("w", "med")
    l_b = end_elem.attrib.get("len", "med")
    mw = SIZE_BUCKET.get(l_b, 2.5)
    mh = SIZE_BUCKET.get(w_b, 2.5)

    seq[0] += 1
    marker_id = f"{id_prefix}arrow{seq[0]}"

    if typ == "triangle":
        path = "M 0 0 L 10 5 L 0 10 z"
    elif typ == "stealth":
        path = "M 0 0 L 10 5 L 0 10 L 3 5 z"
    elif typ == "arrow":
        path = "M 0 0 L 10 5 L 0 10"
    elif typ == "diamond":
        path = "M 0 5 L 5 0 L 10 5 L 5 10 z"
    elif typ == "oval":
        path = ""  # use circle below
    else:
        path = "M 0 0 L 10 5 L 0 10 z"

    if typ == "oval":
        body = f'<circle cx="5" cy="5" r="4" fill="{stroke_color}"/>'
    else:
        body = f'<path d="{path}" fill="{stroke_color}"/>'

    orient = "auto-start-reverse" if reversed_ else "auto"
    fill_attr = "" if typ == "arrow" else ""  # no extra
    marker_def = (
        f'<marker id="{marker_id}" viewBox="0 0 10 10" '
        f'refX="{"0" if reversed_ else "10"}" refY="5" '
        f'markerWidth="{fmt_num(mw, 2)}" markerHeight="{fmt_num(mh, 2)}" '
        f'orient="{orient}" markerUnits="strokeWidth">'
        f"{body}</marker>"
    )
    return marker_id, marker_def
