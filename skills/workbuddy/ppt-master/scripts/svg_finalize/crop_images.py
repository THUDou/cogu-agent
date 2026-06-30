
import os
import re
import hashlib
import sys
import argparse
from pathlib import Path
from xml.etree import ElementTree as ET
from urllib.parse import unquote

try:
    from PIL import Image
except ImportError:
    print("Error: PIL (Pillow) is required. Run: pip install Pillow")
    exit(1)


def parse_preserve_aspect_ratio(attr: str) -> tuple[str, str]:
    if not attr:
        return ('xMidYMid', 'meet')  # Default value
    
    parts = attr.strip().split()
    align = parts[0] if parts else 'xMidYMid'
    meet_or_slice = parts[1] if len(parts) > 1 else 'meet'
    
    return (align, meet_or_slice)


def get_crop_anchor(align: str) -> tuple[float, float]:
    x_map = {'xMin': 0.0, 'xMid': 0.5, 'xMax': 1.0}
    y_map = {'YMin': 0.0, 'YMid': 0.5, 'YMax': 1.0}
    
    x_anchor = 0.5
    y_anchor = 0.5
    
    for key, val in x_map.items():
        if key in align:
            x_anchor = val
            break
    
    for key, val in y_map.items():
        if key in align:
            y_anchor = val
            break
    
    return (x_anchor, y_anchor)


def crop_image_to_size(
    img: Image.Image,
    target_width: int,
    target_height: int,
    x_anchor: float = 0.5,
    y_anchor: float = 0.5,
) -> Image.Image:
    img_width, img_height = img.size
    
    target_ratio = target_width / target_height
    img_ratio = img_width / img_height
    
    if img_ratio > target_ratio:
        crop_height = img_height
        crop_width = int(img_height * target_ratio)
    else:
        crop_width = img_width
        crop_height = int(img_width / target_ratio)
    
    extra_width = img_width - crop_width
    extra_height = img_height - crop_height
    
    left = int(extra_width * x_anchor)
    top = int(extra_height * y_anchor)
    right = left + crop_width
    bottom = top + crop_height
    
    return img.crop((left, top, right, bottom))


def process_svg_images(
    svg_file: str,
    output_dir: str | Path | None = None,
    dry_run: bool = False,
    verbose: bool = True,
) -> tuple[int, int]:
    svg_path = Path(svg_file)
    svg_dir = svg_path.parent
    
    if output_dir is None:
        project_dir = svg_dir.parent
        output_dir = project_dir / 'images' / 'cropped'
    else:
        output_dir = Path(output_dir)
    
    try:
        ET.register_namespace('', 'http://www.w3.org/2000/svg')
        ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')
        tree = ET.parse(str(svg_path))
        root = tree.getroot()
    except Exception as e:
        if verbose:
            print(f"  [ERROR] Failed to parse SVG: {e}")
        return (0, 1)
    
    ns = {'svg': 'http://www.w3.org/2000/svg', 'xlink': 'http://www.w3.org/1999/xlink'}
    
    processed_count = 0
    error_count = 0
    modified = False
    
    for image in root.iter('{http://www.w3.org/2000/svg}image'):
        href = image.get('{http://www.w3.org/1999/xlink}href') or image.get('href')
        if not href:
            continue
        
        if href.startswith('data:'):
            continue
        
        par = image.get('preserveAspectRatio', '')
        align, mode = parse_preserve_aspect_ratio(par)
        
        if mode != 'slice':
            continue
        
        try:
            target_width = int(float(image.get('width', 0)))
            target_height = int(float(image.get('height', 0)))
        except (ValueError, TypeError):
            continue
        
        if target_width <= 0 or target_height <= 0:
            continue
        
        href_decoded = unquote(href)
        if href_decoded.startswith('../'):
            img_path = (svg_dir / href_decoded).resolve()
        else:
            img_path = (svg_dir / href_decoded).resolve()
        
        if not img_path.exists():
            if verbose:
                print(f"    [SKIP] Image not found: {href}")
            continue
        
        x_anchor, y_anchor = get_crop_anchor(align)
        
        if dry_run:
            if verbose:
                print(f"    [DRY] {img_path.name} -> {target_width}x{target_height} "
                      f"(align: {align}, anchor: {x_anchor},{y_anchor})")
            processed_count += 1
            continue
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            img = Image.open(img_path)
            output_is_png = img_path.suffix.lower() == '.png'

            if output_is_png:
                if img.mode == 'P':
                    img = img.convert('RGBA')
                elif img.mode not in ('RGBA', 'LA', 'RGB', 'L'):
                    img = img.convert('RGBA' if 'A' in img.getbands() else 'RGB')
            else:
                if img.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    alpha = img.getchannel('A')
                    background.paste(img.convert('RGB'), mask=alpha)
                    img = background
                elif img.mode == 'P':
                    img = img.convert('RGB')
                elif img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')
            
            cropped = crop_image_to_size(img, target_width, target_height, x_anchor, y_anchor)
            
            output_filename = img_path.name
            output_path = output_dir / output_filename
            
            if output_is_png:
                cropped.save(output_path, 'PNG', optimize=True)
            else:
                cropped.save(output_path, 'JPEG', quality=90, optimize=True)
            
            if verbose:
                print(f"    [OK] {img_path.name}: {img.size} -> {target_width}x{target_height} "
                      f"({align})")
            
            new_href = f"../images/cropped/{output_filename}"
            if image.get('{http://www.w3.org/1999/xlink}href'):
                image.set('{http://www.w3.org/1999/xlink}href', new_href)
            else:
                image.set('href', new_href)
            
            if 'preserveAspectRatio' in image.attrib:
                del image.attrib['preserveAspectRatio']
            
            modified = True
            processed_count += 1
            
        except Exception as e:
            if verbose:
                print(f"    [ERROR] {img_path.name}: {e}")
            error_count += 1
    
    if modified and not dry_run:
        tree.write(str(svg_path), encoding='unicode', xml_declaration=False)
    
    return (processed_count, error_count)


def process_directory(directory: str, dry_run: bool = False, verbose: bool = True) -> tuple[int, int]:
    directory_path = Path(directory)
    total_processed = 0
    total_errors = 0
    
    for svg_file in directory_path.glob('*.svg'):
        if verbose:
            print(f"  Processing: {svg_file.name}")
        processed, errors = process_svg_images(str(svg_file), dry_run=dry_run, verbose=verbose)
        total_processed += processed
        total_errors += errors
    
    return (total_processed, total_errors)


def main() -> None:
    parser = argparse.ArgumentParser(
        description='PPT Master - Smart Image Cropping Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s projects/my_project/svg_output
  %(prog)s page_01.svg --dry-run

preserveAspectRatio usage:
  xMidYMid slice   Center crop (default)
  xMidYMin slice   Keep top
  xMidYMax slice   Keep bottom
  xMinYMid slice   Keep left
  xMaxYMid slice   Keep right
  xMidYMid meet    Display fully, no cropping
