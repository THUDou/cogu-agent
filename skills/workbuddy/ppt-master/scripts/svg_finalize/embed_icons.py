
import os
import re
import sys
import argparse
from pathlib import Path
from xml.etree import ElementTree as ET


DEFAULT_ICONS_DIR = Path(__file__).parent.parent.parent / 'templates' / 'icons'

ICON_BASE_SIZES = {
    'chunk-filled': 16,
    'chunk': 16,          # backward compat alias → chunk-filled/
    'tabler-filled': 24,
    'tabler-outline': 24,
    'phosphor-duotone': 256,
    'simple-icons': 24,
}
DEFAULT_ICON_BASE_SIZE = 24


def _get_viewbox_size(content: str) -> float:
    m = re.search(r'viewBox=["\']0 0 ([\d.]+)', content)
    if m:
        return float(m.group(1))
    return 0


def _detect_icon_style(content: str) -> str:
    if 'stroke="currentColor"' in content and 'fill="none"' in content:
        return 'stroke'
    return 'fill'


def _extract_shape_elements(content: str, color: str) -> list[str]:
    shape_tags = ('path', 'circle', 'rect', 'line', 'polyline', 'polygon', 'ellipse')
    pattern = r'<(' + '|'.join(shape_tags) + r')(\s[^>]*)?(?:/>|></\1>)'
    matches = re.findall(pattern, content, re.DOTALL)

    elements = []
    for tag, attrs in matches:
        attrs_clean = re.sub(r'\s*fill="(?:currentColor|#[0-9a-fA-F]{3,6}|none)"', '', attrs)
        attrs_clean = re.sub(r'\s*stroke="(?:currentColor|#[0-9a-fA-F]{3,6}|none)"', '', attrs_clean)
        attrs_clean = re.sub(r'\s*stroke-width="[^"]*"', '', attrs_clean)
        elements.append(f'<{tag}{attrs_clean}/>')

    return elements


def resolve_icon_path(icon_name: str, icons_dir: Path) -> tuple[Path, float]:
    _LIB_ALIASES = {'chunk': 'chunk-filled'}

    if '/' in icon_name:
        lib, name = icon_name.split('/', 1)
        lib = _LIB_ALIASES.get(lib, lib)  # resolve aliases
        icon_path = icons_dir / lib / f'{name}.svg'
        base_size = ICON_BASE_SIZES.get(lib, 24)
    else:
        icon_path = icons_dir / 'chunk-filled' / f'{icon_name}.svg'
        base_size = 16
        if not icon_path.exists():
            icon_path = icons_dir / f'{icon_name}.svg'  # legacy flat layout
            base_size = 16

    return icon_path, base_size


def extract_paths_from_icon(icon_path: Path, target_color: str = '#000000') -> tuple[list[str], str, float]:
    if not icon_path.exists():
        return [], 'fill', 16

    content = icon_path.read_text(encoding='utf-8')
    style = _detect_icon_style(content)
    base_size = _get_viewbox_size(content) or 16
    elements = _extract_shape_elements(content, target_color)
    return elements, style, base_size


def parse_use_element(use_match: str) -> dict[str, str | float]:
    attrs: dict[str, str | float] = {}
    
    icon_match = re.search(r'data-icon="([^"]+)"', use_match)
    if icon_match:
        attrs['icon'] = icon_match.group(1)
    
    for attr in ['x', 'y', 'width', 'height']:
        match = re.search(rf'{attr}="([^"]+)"', use_match)
        if match:
            attrs[attr] = float(match.group(1))
    
    fill_match = re.search(r'fill="([^"]+)"', use_match)
    if fill_match:
        attrs['fill'] = fill_match.group(1)

    stroke_width_match = re.search(r'stroke-width="([^"]+)"', use_match)
    if stroke_width_match:
        attrs['stroke-width'] = stroke_width_match.group(1)

    return attrs


def generate_icon_group(attrs: dict[str, str | float], elements: list[str], style: str, base_size: float) -> str:
    x = attrs.get('x', 0)
    y = attrs.get('y', 0)
    width = attrs.get('width', base_size)
    height = attrs.get('height', base_size)
    color = attrs.get('fill', '#000000')
    icon_name = attrs.get('icon', 'unknown')

    scale_x = width / base_size
    scale_y = height / base_size

    if abs(scale_x - 1) < 1e-6 and abs(scale_y - 1) < 1e-6:
        transform = f'translate({x}, {y})'
    elif abs(scale_x - scale_y) < 1e-6:
        transform = f'translate({x}, {y}) scale({scale_x})'
    else:
        transform = f'translate({x}, {y}) scale({scale_x}, {scale_y})'

    elements_str = '\n    '.join(elements)

    if style == 'stroke':
        stroke_width = attrs.get('stroke-width', '2')
        color_attrs = f'fill="none" stroke="{color}" stroke-width="{stroke_width}"'
    else:
        color_attrs = f'fill="{color}"'

    return f'''<!-- icon: {icon_name} -->
  <g transform="{transform}" {color_attrs}>
    {elements_str}
  </g>'''


def process_svg_file(svg_path: Path, icons_dir: Path, dry_run: bool = False, verbose: bool = False) -> int:
    if not svg_path.exists():
        print(f"[ERROR] File not found: {svg_path}")
        return 0
    
    content = svg_path.read_text(encoding='utf-8')
    
    use_pattern = r'<use\s+[^>]*data-icon="[^"]*"[^>]*/>'
    matches = list(re.finditer(use_pattern, content))
    
    if not matches:
        if verbose:
            print(f"[SKIP] No icon placeholders: {svg_path}")
        return 0
    
    replaced_count = 0
    new_content = content
    
    for match in reversed(matches):
        use_str = match.group(0)
        attrs = parse_use_element(use_str)
        
        icon_name = attrs.get('icon')
        if not icon_name:
            continue

        icon_path, _ = resolve_icon_path(str(icon_name), icons_dir)
        color = str(attrs.get('fill', '#000000'))
        elements, style, base_size = extract_paths_from_icon(icon_path, color)
        
        if not elements:
            print(f"[WARN] Icon not found: {icon_name} (in {svg_path.name})")
            continue
        
        replacement = generate_icon_group(attrs, elements, style, base_size)
        
        if verbose or dry_run:
            print(f"  [*] {icon_name}: x={attrs.get('x', 0)}, y={attrs.get('y', 0)}, "
                  f"size={attrs.get('width', base_size)}, fill={color}, style={style}")
        
        new_content = new_content[:match.start()] + replacement + new_content[match.end():]
        replaced_count += 1
    
    if not dry_run and replaced_count > 0:
        svg_path.write_text(new_content, encoding='utf-8')
    
    status = "[PREVIEW]" if dry_run else "[OK]"
    print(f"{status} {svg_path.name} ({replaced_count} icons)")
    
    return replaced_count


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Replace icon placeholders in SVG files with actual icon code',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python3 scripts/svg_finalize/embed_icons.py svg_output/01_cover.svg
  python3 scripts/svg_finalize/embed_icons.py svg_output/*.svg
  python3 scripts/svg_finalize/embed_icons.py --dry-run svg_output/*.svg
  python3 scripts/svg_finalize/embed_icons.py --icons-dir my_icons/ output.svg
