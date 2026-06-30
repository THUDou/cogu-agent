
from __future__ import annotations

import posixpath
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Iterator
from xml.etree import ElementTree as ET

from .emu_units import NS, emu_attr_to_px



REL_NS = NS["rel"]
PACKAGE_REL = "_rels/.rels"
PRESENTATION_REL_PREFIX = "ppt/_rels/presentation.xml.rels"


def _normalize_part_path(target: str, base: str | None = None) -> str:
    target = target.replace("\\", "/")
    if target.startswith("/"):
        return target.lstrip("/")
    if base is None:
        return target
    base_dir = posixpath.dirname(base.rstrip("/"))
    joined = posixpath.normpath(posixpath.join(base_dir, target))
    return joined.lstrip("/")


def _rels_path_for(part_path: str) -> str:
    parent, name = posixpath.split(part_path)
    if not parent:
        return f"_rels/{name}.rels"
    return f"{parent}/_rels/{name}.rels"


def _parse_rels(zf: zipfile.ZipFile, rels_path: str) -> dict[str, dict[str, str]]:
    if rels_path not in zf.namelist():
        return {}
    try:
        root = ET.fromstring(zf.read(rels_path))
    except ET.ParseError:
        return {}

    base = rels_path.replace("/_rels/", "/")  # source part path
    base = base[:-len(".rels")]  # strip .rels suffix
    rels: dict[str, dict[str, str]] = {}
    for child in root.findall(f"{{{REL_NS}}}Relationship"):
        rid = child.attrib.get("Id", "")
        rtype = child.attrib.get("Type", "")
        target = child.attrib.get("Target", "")
        target_mode = child.attrib.get("TargetMode", "")
        if target_mode == "External":
            rels[rid] = {"type": rtype, "target": target, "external": "1"}
            continue
        absolute = _normalize_part_path(target, base)
        rels[rid] = {"type": rtype, "target": absolute}
    return rels


def _load_xml(zf: zipfile.ZipFile, part_path: str) -> ET.Element | None:
    if part_path not in zf.namelist():
        return None
    try:
        return ET.fromstring(zf.read(part_path))
    except ET.ParseError:
        return None



@dataclass
class PartRef:

    path: str
    xml: ET.Element
    rels: dict[str, dict[str, str]] = field(default_factory=dict)

    def resolve_rel(self, rid: str) -> str | None:
        info = self.rels.get(rid)
        if info is None:
            return None
        if info.get("external"):
            return None
        return info.get("target")


@dataclass
class SlideRef:

    index: int  # 1-based
    part: PartRef
    layout: PartRef | None
    master: PartRef | None



REL_TYPES = {
    "presentation": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument",
    "slide": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide",
    "slideLayout": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout",
    "slideMaster": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster",
    "theme": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme",
    "image": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
    "media": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/media",
}


class OoxmlPackage:

    def __init__(self, pptx_path: Path) -> None:
        self.path = pptx_path
        self.zip: zipfile.ZipFile | None = None
        self.presentation: PartRef | None = None
        self.slide_size_px: tuple[float, float] = (1280.0, 720.0)
        self.slide_size_emu: tuple[int, int] = (12192000, 6858000)
        self._slides: list[SlideRef] = []
        self._layouts: dict[str, PartRef] = {}
        self._masters: dict[str, PartRef] = {}
        self._themes: dict[str, PartRef] = {}


    def __enter__(self) -> "OoxmlPackage":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def open(self) -> None:
        if self.zip is not None:
            return
        self.zip = zipfile.ZipFile(self.path, "r")
        self._load_presentation()
        self._load_slides()

    def close(self) -> None:
        if self.zip is not None:
            self.zip.close()
            self.zip = None


    def _load_part(self, part_path: str) -> PartRef | None:
        assert self.zip is not None
        xml = _load_xml(self.zip, part_path)
        if xml is None:
            return None
        rels = _parse_rels(self.zip, _rels_path_for(part_path))
        return PartRef(path=part_path, xml=xml, rels=rels)

    def read_media(self, part_path: str) -> bytes | None:
        assert self.zip is not None
        if part_path not in self.zip.namelist():
            return None
        return self.zip.read(part_path)

    def media_filename(self, part_path: str) -> str:
        return PurePosixPath(part_path).name


    def _load_presentation(self) -> None:
        assert self.zip is not None
        package_rels = _parse_rels(self.zip, PACKAGE_REL)
        pres_path = None
        for info in package_rels.values():
            if info.get("type") == REL_TYPES["presentation"]:
                pres_path = info["target"]
                break
        if pres_path is None:
            pres_path = "ppt/presentation.xml"

        self.presentation = self._load_part(pres_path)
        if self.presentation is None:
            raise RuntimeError(f"presentation.xml missing in {self.path}")

        size = self.presentation.xml.find("p:sldSz", NS)
        if size is not None:
            cx = int(size.attrib.get("cx", "12192000"))
            cy = int(size.attrib.get("cy", "6858000"))
            self.slide_size_emu = (cx, cy)
            self.slide_size_px = (cx / 9525.0, cy / 9525.0)

    def _load_slides(self) -> None:
        assert self.zip is not None and self.presentation is not None
        sld_id_lst = self.presentation.xml.find("p:sldIdLst", NS)
        if sld_id_lst is None:
            return

        for index, sld_id in enumerate(sld_id_lst.findall("p:sldId", NS), start=1):
            rid = sld_id.attrib.get(f"{{{NS['r']}}}id")
            if not rid:
                continue
            slide_path = self.presentation.resolve_rel(rid)
            if not slide_path:
                continue
            slide_part = self._load_part(slide_path)
            if slide_part is None:
                continue
            layout = self._resolve_layout(slide_part)
            master = self._resolve_master(layout) if layout else None
            self._slides.append(SlideRef(
                index=index, part=slide_part, layout=layout, master=master,
            ))

    def _resolve_layout(self, slide: PartRef) -> PartRef | None:
        for info in slide.rels.values():
            if info.get("type") == REL_TYPES["slideLayout"]:
                target = info["target"]
                cached = self._layouts.get(target)
                if cached is None:
                    cached = self._load_part(target)
                    if cached is not None:
                        self._layouts[target] = cached
                return cached
        return None

    def _resolve_master(self, layout: PartRef) -> PartRef | None:
        for info in layout.rels.values():
            if info.get("type") == REL_TYPES["slideMaster"]:
                target = info["target"]
                cached = self._masters.get(target)
                if cached is None:
                    cached = self._load_part(target)
                    if cached is not None:
                        self._masters[target] = cached
                return cached
        return None

    def resolve_theme(self, master: PartRef | None) -> PartRef | None:
        if master is None:
            return None
        for info in master.rels.values():
            if info.get("type") == REL_TYPES["theme"]:
                target = info["target"]
                cached = self._themes.get(target)
                if cached is None:
                    cached = self._load_part(target)
                    if cached is not None:
                        self._themes[target] = cached
                return cached
        return None


    def iter_slides(self) -> Iterator[SlideRef]:
        yield from self._slides

    @property
    def slide_count(self) -> int:
        return len(self._slides)

    def get_slide(self, index: int) -> SlideRef | None:
        if 1 <= index <= len(self._slides):
            return self._slides[index - 1]
        return None

    def iter_all_masters(self) -> Iterator[PartRef]:
        if self.presentation is None:
            return
        master_id_lst = self.presentation.xml.find("p:sldMasterIdLst", NS)
        if master_id_lst is None:
            return
        for master_id in master_id_lst.findall("p:sldMasterId", NS):
            rid = master_id.attrib.get(f"{{{NS['r']}}}id")
            if not rid:
                continue
            target = self.presentation.resolve_rel(rid)
            if not target:
                continue
            cached = self._masters.get(target)
            if cached is None:
                cached = self._load_part(target)
                if cached is None:
                    continue
                self._masters[target] = cached
            yield cached

    def iter_all_layouts(self) -> Iterator[PartRef]:
        for layout, _master in self.iter_all_layouts_with_parent():
            yield layout

    def iter_all_layouts_with_parent(self) -> Iterator[tuple[PartRef, PartRef]]:
        seen: set[str] = set()
        for master in self.iter_all_masters():
            layout_id_lst = master.xml.find("p:sldLayoutIdLst", NS)
            if layout_id_lst is None:
                continue
            for layout_id in layout_id_lst.findall("p:sldLayoutId", NS):
                rid = layout_id.attrib.get(f"{{{NS['r']}}}id")
                if not rid:
                    continue
                target = master.resolve_rel(rid)
                if not target or target in seen:
                    continue
                seen.add(target)
                cached = self._layouts.get(target)
                if cached is None:
                    cached = self._load_part(target)
                    if cached is None:
                        continue
                    self._layouts[target] = cached
                yield cached, master
