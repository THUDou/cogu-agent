
from __future__ import annotations

from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

from .emu_units import NS, Xfrm, parse_xfrm



SHAPE = "sp"
PICTURE = "pic"
CONNECTOR = "cxnSp"
GROUP = "grpSp"
GRAPHIC = "graphicFrame"


@dataclass
class PlaceholderInfo:

    type: str | None = None  # title / body / ctrTitle / subTitle / ftr / dt / ...
    idx: str | None = None
    sz: str | None = None  # full / half / quarter
    orient: str | None = None


@dataclass
class ShapeNode:

    kind: str  # one of SHAPE / PICTURE / CONNECTOR / GROUP / GRAPHIC
    xml: ET.Element  # original element
    xfrm: Xfrm  # resolved geometry in absolute slide pixel space
    name: str = ""
    spid: str = ""
    hidden: bool = False
    placeholder: PlaceholderInfo | None = None
    children: list["ShapeNode"] = field(default_factory=list)



def _read_nv_sp_pr(parent: ET.Element, nv_tag: str) -> tuple[str, str, bool, PlaceholderInfo | None]:
    container = parent.find(f"p:{nv_tag}", NS)
    name = ""
    spid = ""
    hidden = False
    ph: PlaceholderInfo | None = None
    if container is None:
        return name, spid, hidden, ph

    cnv = container.find("p:cNvPr", NS)
    if cnv is not None:
        name = cnv.attrib.get("name", "")
        spid = cnv.attrib.get("id", "")
        if cnv.attrib.get("hidden") == "1":
            hidden = True

    nv_pr = container.find("p:nvPr", NS)
    if nv_pr is not None:
        ph_elem = nv_pr.find("p:ph", NS)
        if ph_elem is not None:
            ph = PlaceholderInfo(
                type=ph_elem.attrib.get("type"),
                idx=ph_elem.attrib.get("idx"),
                sz=ph_elem.attrib.get("sz"),
                orient=ph_elem.attrib.get("orient"),
            )

    return name, spid, hidden, ph


def _resolve_xfrm(shape: ET.Element, kind: str) -> ET.Element | None:
    if kind == GROUP:
        sp_pr = shape.find("p:grpSpPr", NS)
    elif kind == GRAPHIC:
        return shape.find("p:xfrm", NS)
    else:
        sp_pr = shape.find("p:spPr", NS)
    if sp_pr is None:
        return None
    return sp_pr.find("a:xfrm", NS)


def _adjust_for_group(child_xfrm: Xfrm, group_xfrm: Xfrm) -> Xfrm:
    if (group_xfrm.ch_w is None or group_xfrm.ch_h is None
            or group_xfrm.ch_w == 0 or group_xfrm.ch_h == 0):
        return child_xfrm

    sx = group_xfrm.w / group_xfrm.ch_w if group_xfrm.ch_w else 1.0
    sy = group_xfrm.h / group_xfrm.ch_h if group_xfrm.ch_h else 1.0
    ch_x = group_xfrm.ch_x or 0.0
    ch_y = group_xfrm.ch_y or 0.0

    new_x = group_xfrm.x + (child_xfrm.x - ch_x) * sx
    new_y = group_xfrm.y + (child_xfrm.y - ch_y) * sy
    new_w = child_xfrm.w * sx
    new_h = child_xfrm.h * sy

    return Xfrm(
        x=new_x, y=new_y, w=new_w, h=new_h,
        rot=child_xfrm.rot,
        flip_h=child_xfrm.flip_h,
        flip_v=child_xfrm.flip_v,
        ch_x=child_xfrm.ch_x, ch_y=child_xfrm.ch_y,
        ch_w=child_xfrm.ch_w, ch_h=child_xfrm.ch_h,
    )


_KIND_MAP = {
    "sp": (SHAPE, "nvSpPr"),
    "pic": (PICTURE, "nvPicPr"),
    "cxnSp": (CONNECTOR, "nvCxnSpPr"),
    "grpSp": (GROUP, "nvGrpSpPr"),
    "graphicFrame": (GRAPHIC, "nvGraphicFramePr"),
}


def _walk_container(
    container: ET.Element,
    parent_group_xfrm: Xfrm | None,
    placeholder_xfrms: dict[tuple[str | None, str | None], Xfrm] | None = None,
) -> list[ShapeNode]:
    nodes: list[ShapeNode] = []
    for child in list(container):
        if not isinstance(child.tag, str):
            continue
        local = child.tag.split("}", 1)[-1]
        kind_info = _KIND_MAP.get(local)
        if kind_info is None:
            continue
        kind, nv_tag = kind_info

        name, spid, hidden, ph = _read_nv_sp_pr(child, nv_tag)
        xfrm = parse_xfrm(_resolve_xfrm(child, kind))

        if (ph is not None and placeholder_xfrms
                and (xfrm.w == 0 and xfrm.h == 0)):
            inherited = _lookup_placeholder_xfrm(ph, placeholder_xfrms)
            if inherited is not None:
                xfrm = Xfrm(
                    x=inherited.x, y=inherited.y,
                    w=inherited.w, h=inherited.h,
                    rot=xfrm.rot, flip_h=xfrm.flip_h, flip_v=xfrm.flip_v,
                    ch_x=xfrm.ch_x, ch_y=xfrm.ch_y,
                    ch_w=xfrm.ch_w, ch_h=xfrm.ch_h,
                )

        if parent_group_xfrm is not None:
            xfrm = _adjust_for_group(xfrm, parent_group_xfrm)

        node = ShapeNode(
            kind=kind, xml=child, xfrm=xfrm,
            name=name, spid=spid, hidden=hidden, placeholder=ph,
        )

        if kind == GROUP:
            node.children = _walk_container(
                child, xfrm, placeholder_xfrms=placeholder_xfrms,
            )

        nodes.append(node)
    return nodes


def _lookup_placeholder_xfrm(
    ph: PlaceholderInfo,
    table: dict[tuple[str | None, str | None], Xfrm],
) -> Xfrm | None:
    for key in (
        (ph.type, ph.idx),
        (ph.type, None),
        (None, ph.idx),
    ):
        hit = table.get(key)
        if hit is not None and (hit.w > 0 or hit.h > 0):
            return hit
    return None


def _build_placeholder_xfrm_table(
    *parts: ET.Element | None,
) -> dict[tuple[str | None, str | None], Xfrm]:
    table: dict[tuple[str | None, str | None], Xfrm] = {}
    for part_xml in parts:
        if part_xml is None:
            continue
        sp_tree = part_xml.find("p:cSld/p:spTree", NS)
        if sp_tree is None:
            continue
        for sp in sp_tree.iter():
            if not isinstance(sp.tag, str) or sp.tag.split("}", 1)[-1] != "sp":
                continue
            ph_elem = sp.find("p:nvSpPr/p:nvPr/p:ph", NS)
            if ph_elem is None:
                continue
            xfrm_elem = sp.find("p:spPr/a:xfrm", NS)
            if xfrm_elem is None:
                continue
            xfrm = parse_xfrm(xfrm_elem)
            if xfrm.w <= 0 and xfrm.h <= 0:
                continue
            ph_type = ph_elem.attrib.get("type")
            ph_idx = ph_elem.attrib.get("idx")
            for key in ((ph_type, ph_idx),
                        (ph_type, None),
                        (None, ph_idx)):
                table.setdefault(key, xfrm)
    return table


def walk_sp_tree(
    slide_xml: ET.Element,
    *,
    layout_xml: ET.Element | None = None,
    master_xml: ET.Element | None = None,
) -> list[ShapeNode]:
    sp_tree = slide_xml.find("p:cSld/p:spTree", NS)
    if sp_tree is None:
        return []
    placeholder_xfrms = _build_placeholder_xfrm_table(layout_xml, master_xml)
    return _walk_container(
        sp_tree, parent_group_xfrm=None,
        placeholder_xfrms=placeholder_xfrms or None,
    )


def get_background(slide_xml: ET.Element) -> ET.Element | None:
    return slide_xml.find("p:cSld/p:bg", NS)
