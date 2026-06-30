
import sys
import re
import argparse
from pathlib import Path
from typing import Any, Tuple
from xml.etree import ElementTree as ET


def rect_to_rounded_path(
    x: float,
    y: float,
    width: float,
    height: float,
    rx: float,
    ry: float,
) -> str:
    rx = min(rx, width / 2)
    ry = min(ry, height / 2)
    
    x1 = x + rx
    x2 = x + width - rx
    y1 = y + ry
    y2 = y + height - ry
    
    path = (
        f"M{x1:.2f},{y:.2f} "
        f"H{x2:.2f} "
        f"A{rx:.2f},{ry:.2f} 0 0 1 {x + width:.2f},{y1:.2f} "
        f"V{y2:.2f} "
        f"A{rx:.2f},{ry:.2f} 0 0 1 {x2:.2f},{y + height:.2f} "
        f"H{x1:.2f} "
        f"A{rx:.2f},{ry:.2f} 0 0 1 {x:.2f},{y2:.2f} "
        f"V{y1:.2f} "
        f"A{rx:.2f},{ry:.2f} 0 0 1 {x1:.2f},{y:.2f} "
        f"Z"
    )
    
    path = re.sub(r'\.00(?=\s|,|[A-Za-z]|$)', '', path)
    
    return path


def parse_float(val: str, default: float = 0.0) -> float:
    if not val:
        return default
    try:
        val = re.sub(r'(px|pt|em|%|rem)$', '', val.strip())
        return float(val)
    except ValueError:
        return default


def process_svg(content: str, verbose: bool = False) -> Tuple[str, int]:
    converted_count = 0
    
    xml_declaration = ''
    if content.strip().startswith('<?xml'):
        match = re.match(r'(<\?xml[^?]*\?>)', content)
        if match:
            xml_declaration = match.group(1) + '\n'
    
    ET.register_namespace('', 'http://www.w3.org/2000/svg')
    ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')
    
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        if verbose:
            print(f"    XML parse error: {e}")
        return content, 0
    
    ns = ''
    if root.tag.startswith('{'):
        ns = root.tag.split('}')[0] + '}'
    
    def get_tag_name(tag: str) -> str:
        if tag.startswith('{'):
            return tag.split('}')[1]
        return tag
    
    def process_element(elem: ET.Element) -> None:
        nonlocal converted_count
        tag_name = get_tag_name(elem.tag)
        
        if tag_name == 'rect':
            rx = parse_float(elem.get('rx', '0'))
            ry = parse_float(elem.get('ry', '0'))
            
            if rx == 0 and ry > 0:
                rx = ry
            elif ry == 0 and rx > 0:
                ry = rx
            
            if rx > 0 or ry > 0:
                x = parse_float(elem.get('x', '0'))
                y = parse_float(elem.get('y', '0'))
                width = parse_float(elem.get('width', '0'))
                height = parse_float(elem.get('height', '0'))
                
                if width > 0 and height > 0:
                    path_d = rect_to_rounded_path(x, y, width, height, rx, ry)
                    
                    rect_attrs = {'x', 'y', 'width', 'height', 'rx', 'ry'}
                    
                    elem.tag = ns + 'path' if ns else 'path'
                    elem.set('d', path_d)
                    
                    for attr in rect_attrs:
                        if attr in elem.attrib:
                            del elem.attrib[attr]
                    
                    converted_count += 1
                    if verbose:
                        print(f"    Converted rounded rect: rx={rx}, ry={ry}")
        
        for child in elem:
            process_element(child)
    
    process_element(root)
    
    result = ET.tostring(root, encoding='unicode')
    
    if xml_declaration:
        result = xml_declaration + result
    
    return result, converted_count


def process_svg_file(input_path: Path, output_path: Path, verbose: bool = False) -> tuple[bool, int]:
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        processed, count = process_svg(content, verbose)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(processed)
        
        return True, count
        
    except Exception as e:
        if verbose:
            print(f"  Error: {e}")
        return False, 0


def find_svg_files(project_path: Path, source: str = 'output') -> tuple[list[Path], str]:
    dir_map = {
        'output': 'svg_output',
        'final': 'svg_final',
        'flat': 'svg_output_flattext',
        'final_flat': 'svg_final_flattext',
    }
    
    dir_name = dir_map.get(source, source)
    svg_dir = project_path / dir_name
    
    if not svg_dir.exists():
        if (project_path / 'svg_output').exists():
            dir_name = 'svg_output'
            svg_dir = project_path / dir_name
        elif project_path.is_dir():
            svg_dir = project_path
            dir_name = project_path.name
    
    if not svg_dir.exists():
        return [], ''
    
    return sorted(svg_dir.glob('*.svg')), dir_name


def main() -> None:
    parser = argparse.ArgumentParser(
        description='PPT Master - SVG Rounded Rectangle to Path Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
    %(prog)s examples/ppt169_demo
    %(prog)s examples/ppt169_demo -s final
    %(prog)s examples/ppt169_demo/svg_output/01_cover.svg

What it does:
    Converts <rect> elements with rx/ry to equivalent <path> elements.
    Processed SVGs preserve rounded corners when using "Convert to Shape" in PowerPoint.
