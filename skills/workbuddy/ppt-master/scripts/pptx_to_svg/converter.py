
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from .color_resolver import ColorPalette
from .emu_units import NS
from .ooxml_loader import OoxmlPackage, PartRef, SlideRef
from .slide_to_svg import assemble_part_solo, assemble_slide


def _extract_theme_info(
    theme: PartRef,
    palette: ColorPalette,
) -> tuple[dict[str, str], dict[str, str]]:
    from .color_resolver import find_color_elem, resolve_color

    colors: dict[str, str] = {}
    fonts: dict[str, str] = {}

    scheme = theme.xml.find(".//a:clrScheme", NS)
    if scheme is not None:
        for child in list(scheme):
            if not isinstance(child.tag, str):
                continue
            name = child.tag.split("}", 1)[-1]
            color_elem = find_color_elem(child)
            hex_, _ = resolve_color(color_elem, palette)
            if hex_:
                colors[name] = hex_

    font_scheme = theme.xml.find(".//a:fontScheme", NS)
    if font_scheme is not None:
        for slot in ("majorFont", "minorFont"):
            fnt = font_scheme.find(f"a:{slot}", NS)
            if fnt is None:
                continue
            role_prefix = "major" if slot == "majorFont" else "minor"
            latin = fnt.find("a:latin", NS)
            if latin is not None and latin.attrib.get("typeface"):
                fonts[f"{role_prefix}Latin"] = latin.attrib["typeface"]
            ea = fnt.find("a:ea", NS)
            if ea is not None and ea.attrib.get("typeface"):
                fonts[f"{role_prefix}EastAsia"] = ea.attrib["typeface"]
            cs = fnt.find("a:cs", NS)
            if cs is not None and cs.attrib.get("typeface"):
                fonts[f"{role_prefix}ComplexScript"] = cs.attrib["typeface"]

    return colors, fonts


@dataclass
class ConvertOptions:

    media_subdir: str = "assets"
    embed_images: bool = False
    keep_hidden: bool = False
    inheritance_mode: str = "both"
    asset_name_map: dict[str, str] = field(default_factory=dict)


@dataclass
class PartArtifact:

    role: str  # "master" | "layout"
    part_path: str  # OOXML part path, e.g. "ppt/slideLayouts/slideLayout3.xml"
    filename: str  # output svg filename, e.g. "layout_03_title.xml.svg"
    svg: str
    media_files: dict[str, bytes] = field(default_factory=dict)
    parent_master_part_path: str | None = None
    theme_part_path: str | None = None


@dataclass
class SlideArtifact:

    index: int  # 1-based
    svg: str
    media_files: dict[str, bytes] = field(default_factory=dict)
    layout_part_path: str | None = None
    master_part_path: str | None = None


@dataclass
class ConvertResult:

    slides: list[SlideArtifact] = field(default_factory=list)
    canvas_px: tuple[float, float] = (1280.0, 720.0)
    theme_colors: dict[str, str] = field(default_factory=dict)
    theme_fonts: dict[str, str] = field(default_factory=dict)
    layouts: list[PartArtifact] = field(default_factory=list)
    masters: list[PartArtifact] = field(default_factory=list)
    flat_slides: list[SlideArtifact] = field(default_factory=list)
    master_themes: dict[str, dict[str, object]] = field(default_factory=dict)



def convert_pptx_to_svg(
    pptx_path: Path,
    output_dir: Path | None = None,
    options: ConvertOptions | None = None,
) -> ConvertResult:
    options = options or ConvertOptions()
    if options.inheritance_mode not in {"flat", "layered", "both"}:
        raise ValueError(
            f"inheritance_mode must be 'flat', 'layered', or 'both', "
            f"got {options.inheritance_mode!r}"
        )
    emit_layered = options.inheritance_mode in {"layered", "both"}
    emit_flat = options.inheritance_mode in {"flat", "both"}
    result = ConvertResult()

    with OoxmlPackage(pptx_path) as pkg:
        result.canvas_px = pkg.slide_size_px

        first_slide = pkg.get_slide(1)
        default_master = first_slide.master if first_slide else None
        default_theme = pkg.resolve_theme(default_master)
        palette = ColorPalette(default_master, default_theme)
        if default_theme is not None:
            result.theme_colors, result.theme_fonts = _extract_theme_info(default_theme, palette)

        for master in pkg.iter_all_masters():
            theme = pkg.resolve_theme(master) or default_theme
            pal = ColorPalette(master, theme)
            colors, fonts = _extract_theme_info(theme, pal) if theme is not None else ({}, {})
            result.master_themes[master.path] = {
                "themePath": theme.path if theme is not None else None,
                "colors": colors,
                "fonts": fonts,
            }

        primary_mode = "layered" if emit_layered else "flat"
        for slide in pkg.iter_slides():
            slide_theme = pkg.resolve_theme(slide.master) or default_theme
            slide_palette = ColorPalette(slide.master, slide_theme)
            _colors, slide_fonts = _extract_theme_info(slide_theme, slide_palette) if slide_theme is not None else ({}, result.theme_fonts)
            artifact = _convert_slide(
                pkg, slide, slide_palette, options, slide_fonts,
                inheritance_mode=primary_mode,
            )
            result.slides.append(artifact)
        if emit_layered and emit_flat:
            for slide in pkg.iter_slides():
                slide_theme = pkg.resolve_theme(slide.master) or default_theme
                slide_palette = ColorPalette(slide.master, slide_theme)
                _colors, slide_fonts = _extract_theme_info(slide_theme, slide_palette) if slide_theme is not None else ({}, result.theme_fonts)
                artifact = _convert_slide(
                    pkg, slide, slide_palette, options, slide_fonts,
                    inheritance_mode="flat",
                )
                result.flat_slides.append(artifact)

        if emit_layered:
            _convert_inheritance_parts(pkg, default_theme, options, result)

    if output_dir is not None:
        _write_artifacts(output_dir, result, options)

    return result


def _convert_slide(
    pkg: OoxmlPackage,
    slide: SlideRef,
    palette: ColorPalette,
    options: ConvertOptions,
    theme_fonts: dict[str, str] | None = None,
    *,
    inheritance_mode: str | None = None,
) -> SlideArtifact:
    mode = inheritance_mode or options.inheritance_mode
    if mode == "both":
        mode = "layered"  # primary view in both-mode
    svg, media = assemble_slide(
        pkg, slide, palette,
        theme_fonts=theme_fonts,
        media_subdir=options.media_subdir,
        embed_images=options.embed_images,
        keep_hidden=options.keep_hidden,
        inheritance_mode=mode,
        asset_name_map=options.asset_name_map,
    )
    return SlideArtifact(
        index=slide.index,
        svg=svg,
        media_files=media,
        layout_part_path=slide.layout.path if slide.layout else None,
        master_part_path=slide.master.path if slide.master else None,
    )


def _convert_inheritance_parts(
    pkg: OoxmlPackage,
    default_theme: PartRef | None,
    options: ConvertOptions,
    result: ConvertResult,
) -> None:
    seen_masters: dict[str, PartRef] = {}
    for master in pkg.iter_all_masters():
        if master.path not in seen_masters:
            seen_masters[master.path] = master

    layouts_with_parent: list[tuple[PartRef, PartRef]] = []
    seen_layout_paths: set[str] = set()
    for layout, parent_master in pkg.iter_all_layouts_with_parent():
        if layout.path in seen_layout_paths:
            continue
        seen_layout_paths.add(layout.path)
        layouts_with_parent.append((layout, parent_master))

    for seq, part in enumerate(seen_masters.values(), start=1):
        theme = pkg.resolve_theme(part) or default_theme
        palette = ColorPalette(part, theme)
        _colors, fonts = _extract_theme_info(theme, palette) if theme is not None else ({}, result.theme_fonts)
        result.masters.append(_render_part(
            pkg, part, palette, options, fonts,
            role="master", seq=seq, theme_part=theme,
        ))
    for seq, (layout, parent_master) in enumerate(layouts_with_parent, start=1):
        theme = pkg.resolve_theme(parent_master) or default_theme
        palette = ColorPalette(parent_master, theme)
        _colors, fonts = _extract_theme_info(theme, palette) if theme is not None else ({}, result.theme_fonts)
        result.layouts.append(_render_part(
            pkg, layout, palette, options, fonts,
            role="layout", seq=seq, parent_master=parent_master,
            theme_part=theme,
        ))


def _render_part(
    pkg: OoxmlPackage,
    part: PartRef,
    palette: ColorPalette,
    options: ConvertOptions,
    theme_fonts: dict[str, str],
    *,
    role: str,
    seq: int,
    parent_master: PartRef | None = None,
    theme_part: PartRef | None = None,
) -> PartArtifact:
    svg, media = assemble_part_solo(
        pkg, part, palette,
        role=role,
        parent_master=parent_master,
        theme_fonts=theme_fonts,
        media_subdir=options.media_subdir,
        embed_images=options.embed_images,
        keep_hidden=options.keep_hidden,
        asset_name_map=options.asset_name_map,
    )
    stem = PurePosixPath(part.path).stem  # e.g. "slideLayout3"
    safe_stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_") or role
    filename = f"{role}_{seq:02d}_{safe_stem}.svg"
    return PartArtifact(
        role=role,
        part_path=part.path,
        filename=filename,
        svg=svg,
        media_files=media,
        parent_master_part_path=parent_master.path if parent_master is not None else None,
        theme_part_path=theme_part.path if theme_part is not None else None,
    )


def _write_artifacts(output_dir: Path, result: ConvertResult,
                     options: ConvertOptions) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    svg_dir = output_dir / "svg"
    svg_dir.mkdir(exist_ok=True)
    media_dir = output_dir / options.media_subdir
    media_written: set[str] = set()

    def _write_media(media: dict[str, bytes]) -> None:
        for filename, blob in media.items():
            if filename in media_written:
                continue
            media_dir.mkdir(parents=True, exist_ok=True)
            target = media_dir / filename
            if target.exists():
                if target.read_bytes() != blob:
                    raise RuntimeError(f"Asset filename collision with different bytes: {filename}")
            else:
                target.write_bytes(blob)
            media_written.add(filename)

    for art in result.masters:
        (svg_dir / art.filename).write_text(art.svg, encoding="utf-8")
        _write_media(art.media_files)
    for art in result.layouts:
        (svg_dir / art.filename).write_text(art.svg, encoding="utf-8")
        _write_media(art.media_files)

    for art in result.slides:
        target = svg_dir / f"slide_{art.index:02d}.svg"
        target.write_text(art.svg, encoding="utf-8")
        _write_media(art.media_files)

    if options.inheritance_mode in {"layered", "both"}:
        _write_inheritance_json(svg_dir, result)

    if result.flat_slides:
        flat_dir = output_dir / "svg-flat"
        flat_dir.mkdir(exist_ok=True)
        for art in result.flat_slides:
            target = flat_dir / f"slide_{art.index:02d}.svg"
            target.write_text(art.svg, encoding="utf-8")
            _write_media(art.media_files)


def _write_inheritance_json(svg_dir: Path, result: ConvertResult) -> None:
    layout_by_path = {art.part_path: art.filename for art in result.layouts}
    master_by_path = {art.part_path: art.filename for art in result.masters}

    inheritance = {
        "masters": [
            {
                "file": art.filename,
                "partPath": art.part_path,
                "themePath": art.theme_part_path,
            }
            for art in result.masters
        ],
        "layouts": [
            {
                "file": art.filename,
                "partPath": art.part_path,
                "master": master_by_path.get(art.parent_master_part_path or ""),
                "parentPartPath": art.parent_master_part_path,
                "themePath": art.theme_part_path,
            }
            for art in result.layouts
        ],
        "slides": [
            {
                "file": f"slide_{slide.index:02d}.svg",
                "index": slide.index,
                "layout": layout_by_path.get(slide.layout_part_path or ""),
                "master": master_by_path.get(slide.master_part_path or ""),
            }
            for slide in result.slides
        ],
    }
    (svg_dir / "inheritance.json").write_text(
        json.dumps(inheritance, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
