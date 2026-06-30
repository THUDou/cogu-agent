
from __future__ import annotations

import sys
from pathlib import Path
from xml.etree import ElementTree as ET


SVG_NS = 'http://www.w3.org/2000/svg'


def _import_embed_icons():
    scripts_dir = Path(__file__).resolve().parent.parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from svg_finalize import embed_icons  # type: ignore
    return embed_icons


def _build_replacement_g(
    use_elem: ET.Element,
    icons_dir: Path,
    embed_icons_mod,
) -> ET.Element | None:
    use_str = ET.tostring(use_elem, encoding='unicode')
    attrs = embed_icons_mod.parse_use_element(use_str)
    if 'icon' not in attrs:
        return None

    icon_path, _base_size = embed_icons_mod.resolve_icon_path(
        attrs['icon'], icons_dir,
    )
    if not icon_path.exists():
        return None

    color = attrs.get('fill', '#000000')
    elements, style, base_size = embed_icons_mod.extract_paths_from_icon(
        icon_path, color,
    )
    if not elements:
        return None

    g_xml = embed_icons_mod.generate_icon_group(attrs, elements, style, base_size)

    wrapped = f'<svg xmlns="{SVG_NS}">{g_xml}</svg>'
    try:
        parsed_root = ET.fromstring(wrapped)
    except ET.ParseError:
        return None

    for child in parsed_root:
        local = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        if local == 'g':
            return child
    return None


def expand_use_data_icons(root: ET.Element, icons_dir: Path) -> int:
    if not icons_dir.exists():
        return 0

    embed_icons_mod = _import_embed_icons()

    parent_of: dict[ET.Element, ET.Element] = {}
    for parent in root.iter():
        for child in parent:
            parent_of[child] = parent

    targets: list[ET.Element] = []
    for elem in root.iter():
        local = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
        if local == 'use' and elem.get('data-icon'):
            targets.append(elem)

    expanded = 0
    for use_elem in targets:
        parent = parent_of.get(use_elem)
        if parent is None:
            continue
        replacement = _build_replacement_g(use_elem, icons_dir, embed_icons_mod)
        if replacement is None:
            continue
        idx = list(parent).index(use_elem)
        parent.remove(use_elem)
        parent.insert(idx, replacement)
        expanded += 1

    return expanded
