
import os
import re
import sys
import base64
import argparse
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("[WARN] PIL not installed. Install with: pip install Pillow")
    print("       Will try to use basic method for JPEG/PNG files.")


def get_image_dimensions_pil(image_path: str) -> tuple[int | None, int | None]:
    try:
        with Image.open(image_path) as img:
            return img.width, img.height
    except Exception as e:
        print(f"  [WARN] Cannot read image with PIL: {e}")
        return None, None


def get_image_dimensions_basic(image_path: str) -> tuple[int | None, int | None]:
    try:
        with open(image_path, 'rb') as f:
            data = f.read(64)  # Read header information
        
        if data[:8] == b'\x89PNG\r\n\x1a\n':
            w = int.from_bytes(data[16:20], 'big')
            h = int.from_bytes(data[20:24], 'big')
            return w, h
        
        if data[:2] == b'\xff\xd8':
            with open(image_path, 'rb') as f:
                f.seek(2)
                while True:
                    marker = f.read(2)
                    if not marker or len(marker) < 2:
                        break
                    if marker[0] != 0xff:
                        break
                    m = marker[1]
                    if m in (0xC0, 0xC2):
                        f.read(3)  # Skip length and precision
                        h = int.from_bytes(f.read(2), 'big')
                        w = int.from_bytes(f.read(2), 'big')
                        return w, h
                    elif m == 0xD9:  # EOI
                        break
                    elif m == 0xD8:  # SOI
                        continue
                    elif 0xD0 <= m <= 0xD7:  # RST
                        continue
                    else:
                        length = int.from_bytes(f.read(2), 'big')
                        f.seek(length - 2, 1)
        
        return None, None
    except Exception as e:
        print(f"  [WARN] Cannot read image dimensions: {e}")
        return None, None


def get_image_dimensions_from_base64(data_uri: str) -> tuple[int | None, int | None]:
    import io
    try:
        match = re.match(r'data:image/(\w+);base64,(.+)', data_uri)
        if not match:
            return None, None
        
        img_format = match.group(1)
        b64_data = match.group(2)
        img_bytes = base64.b64decode(b64_data)
        
        if HAS_PIL:
            with Image.open(io.BytesIO(img_bytes)) as img:
                return img.width, img.height
        else:
            if img_bytes[:8] == b'\x89PNG\r\n\x1a\n':
                w = int.from_bytes(img_bytes[16:20], 'big')
                h = int.from_bytes(img_bytes[20:24], 'big')
                return w, h
        
        return None, None
    except Exception as e:
        print(f"  [WARN] Cannot parse base64 image: {e}")
        return None, None


def get_image_dimensions(href: str, svg_dir: str) -> tuple[int | None, int | None]:
    if href.startswith('data:'):
        return get_image_dimensions_from_base64(href)
    
    if not os.path.isabs(href):
        full_path = os.path.join(svg_dir, href)
    else:
        full_path = href
    
    if not os.path.exists(full_path):
        print(f"  [WARN] Image not found: {href}")
        return None, None
    
    if HAS_PIL:
        return get_image_dimensions_pil(full_path)
    else:
        return get_image_dimensions_basic(full_path)


def calculate_fitted_dimensions(
    img_width: int,
    img_height: int,
    box_width: float,
    box_height: float,
    mode: str = 'meet',
) -> tuple[float, float, float, float]:
    img_ratio = img_width / img_height
    box_ratio = box_width / box_height
    
    if mode == 'meet':
        if img_ratio > box_ratio:
            new_width = box_width
            new_height = box_width / img_ratio
        else:
            new_height = box_height
            new_width = box_height * img_ratio
    else:  # slice
        if img_ratio > box_ratio:
            new_height = box_height
            new_width = box_height * img_ratio
        else:
            new_width = box_width
            new_height = box_width / img_ratio

    offset_x = (box_width - new_width) / 2
    offset_y = (box_height - new_height) / 2
    
    return new_width, new_height, offset_x, offset_y


def fix_image_aspect_in_svg(svg_path: str, dry_run: bool = False, verbose: bool = True) -> int:
    svg_dir = os.path.dirname(os.path.abspath(svg_path))
    
    with open(svg_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    namespaces = {
        '': 'http://www.w3.org/2000/svg',
        'xlink': 'http://www.w3.org/1999/xlink',
        'svg': 'http://www.w3.org/2000/svg',
        'sodipodi': 'http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd',
        'inkscape': 'http://www.inkscape.org/namespaces/inkscape',
    }
    
    for prefix, uri in namespaces.items():
        if prefix:
            ET.register_namespace(prefix, uri)
        else:
            ET.register_namespace('', uri)
    
    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"  [ERROR] Cannot parse SVG: {e}")
        return 0
    
    fixed_count = 0
    
    for ns_prefix in ['', '{http://www.w3.org/2000/svg}']:
        for image_elem in root.iter(f'{ns_prefix}image'):
            href = image_elem.get('{http://www.w3.org/1999/xlink}href')
            if href is None:
                href = image_elem.get('href')
            if href is None:
                continue
            
            try:
                x = float(image_elem.get('x', 0))
                y = float(image_elem.get('y', 0))
                width = float(image_elem.get('width', 0))
                height = float(image_elem.get('height', 0))
            except (ValueError, TypeError):
                continue
            
            if width <= 0 or height <= 0:
                continue
            
            par = image_elem.get('preserveAspectRatio', 'xMidYMid meet')
            
            par_parts = par.split()
            align = par_parts[0] if par_parts else 'xMidYMid'
            meet_or_slice = par_parts[1] if len(par_parts) > 1 else 'meet'
            
            if align == 'none':
                continue
            
            img_width, img_height = get_image_dimensions(href, svg_dir)
            if img_width is None or img_height is None:
                continue
            
            mode = 'slice' if meet_or_slice == 'slice' else 'meet'
            new_width, new_height, offset_x, offset_y = calculate_fitted_dimensions(
                img_width, img_height, width, height, mode
            )
            
            tolerance = 0.5  # Allowed tolerance
            if (abs(new_width - width) < tolerance and 
                abs(new_height - height) < tolerance):
                continue
            
            if verbose:
                img_name = os.path.basename(href.split('?')[0][:50] if not href.startswith('data:') else '[base64]')
                print(f"  [FIX] {img_name}")
                print(f"        Original image: {img_width}x{img_height} (ratio: {img_width/img_height:.3f})")
                print(f"        Original box: {width}x{height} @ ({x}, {y})")
                print(f"        New box: {new_width:.1f}x{new_height:.1f} @ ({x + offset_x:.1f}, {y + offset_y:.1f})")
            
            if not dry_run:
                image_elem.set('x', f'{x + offset_x:.1f}')
                image_elem.set('y', f'{y + offset_y:.1f}')
                image_elem.set('width', f'{new_width:.1f}')
                image_elem.set('height', f'{new_height:.1f}')
                if 'preserveAspectRatio' in image_elem.attrib:
                    del image_elem.attrib['preserveAspectRatio']
            
            fixed_count += 1
    
    if not dry_run and fixed_count > 0:
        tree.write(svg_path, encoding='unicode', xml_declaration=True)
    
    return fixed_count


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Fix image aspect ratios in SVG to prevent stretching when PowerPoint converts to shapes',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s slide_01.svg                    # Process a single file
  %(prog)s *.svg                           # Process all SVGs in current directory
  %(prog)s --dry-run *.svg                 # Preview files to be processed
  %(prog)s projects/xxx/svg_output/*.svg   # Process project directory
