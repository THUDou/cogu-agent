
import os
import base64
import re
import sys
import argparse


def get_mime_type(filename: str, file_bytes: bytes | None = None) -> str:
    if file_bytes:
        if file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            return 'image/png'
        if file_bytes.startswith(b"\xff\xd8\xff"):
            return 'image/jpeg'
        if file_bytes.startswith((b"GIF87a", b"GIF89a")):
            return 'image/gif'
        if file_bytes.startswith(b"RIFF") and file_bytes[8:12] == b"WEBP":
            return 'image/webp'
        if file_bytes.lstrip().startswith(b"<svg"):
            return 'image/svg+xml'

    ext = filename.lower().split('.')[-1]
    mime_map = {
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'gif': 'image/gif',
        'webp': 'image/webp',
        'svg': 'image/svg+xml',
    }
    return mime_map.get(ext, 'application/octet-stream')

def get_file_size_str(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"

def _optimize_image_bytes(img_bytes: bytes, mime_type: str,
                          compress: bool = False,
                          max_dimension: int | None = None) -> bytes:
    if not compress and not max_dimension:
        return img_bytes

    try:
        from PIL import Image as PILImage
        import io
    except ImportError:
        return img_bytes

    try:
        img = PILImage.open(io.BytesIO(img_bytes))
    except Exception:
        return img_bytes

    changed = False

    if max_dimension:
        w, h = img.size
        if w > max_dimension or h > max_dimension:
            ratio = min(max_dimension / w, max_dimension / h)
            new_w, new_h = int(w * ratio), int(h * ratio)
            img = img.resize((new_w, new_h), PILImage.LANCZOS)
            changed = True

    if compress or changed:
        buf = io.BytesIO()
        if mime_type == 'image/jpeg':
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            img.save(buf, format='JPEG', quality=85, optimize=True)
        elif mime_type == 'image/png':
            img.save(buf, format='PNG', optimize=True)
        else:
            fmt = img.format or 'PNG'
            img.save(buf, format=fmt)

        optimized = buf.getvalue()
        if len(optimized) < len(img_bytes):
            return optimized

    return img_bytes


def embed_images_in_svg(svg_path: str, dry_run: bool = False,
                        compress: bool = False,
                        max_dimension: int | None = None) -> tuple[int, int]:
    svg_dir = os.path.dirname(os.path.abspath(svg_path))
    
    with open(svg_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_size = len(content.encode('utf-8'))
    
    pattern = r'href="(?!data:)([^"]+\.(png|jpg|jpeg|gif|webp))"'
    
    images_found = []
    images_embedded = 0
    
    def replace_with_base64(match):
        nonlocal images_embedded
        img_path = match.group(1)
        
        import html
        img_path_decoded = html.unescape(img_path)
        
        if not os.path.isabs(img_path_decoded):
            full_path = os.path.join(svg_dir, img_path_decoded)
        else:
            full_path = img_path_decoded
        
        if not os.path.exists(full_path):
            print(f"  [WARN] Image not found: {img_path}")
            images_found.append((img_path, "NOT FOUND", 0, None))
            return match.group(0)

        img_size = os.path.getsize(full_path)

        if dry_run:
            images_found.append((img_path, "WILL EMBED", img_size, None))
            return match.group(0)
        
        with open(full_path, 'rb') as img_file:
            img_bytes = img_file.read()

        mime_type = get_mime_type(img_path, img_bytes)
        optimized_bytes = _optimize_image_bytes(
            img_bytes, mime_type, compress=compress, max_dimension=max_dimension)
        b64_data = base64.b64encode(optimized_bytes).decode('utf-8')

        images_embedded += 1
        saved = len(img_bytes) - len(optimized_bytes)
        if saved > 0 and (compress or max_dimension):
            pct = saved / len(img_bytes) * 100
            images_found.append((img_path, "EMBEDDED", img_size,
                                 f"{get_file_size_str(len(img_bytes))} → {get_file_size_str(len(optimized_bytes))}, saved {pct:.0f}%"))
        else:
            images_found.append((img_path, "EMBEDDED", img_size, None))

        return f'href="data:{mime_type};base64,{b64_data}"'
    
    new_content = re.sub(pattern, replace_with_base64, content)
    
    new_size = len(new_content.encode('utf-8'))
    
    if images_found:
        print(f"\n[FILE] {os.path.basename(svg_path)}")
        for img_path, status, size, opt_info in images_found:
            size_str = get_file_size_str(size) if size > 0 else ""
            if status == "EMBEDDED":
                if opt_info:
                    print(f"   [OK] {img_path} ({opt_info})")
                else:
                    print(f"   [OK] {img_path} ({size_str})")
            elif status == "WILL EMBED":
                print(f"   [PREVIEW] {img_path} ({size_str}) [dry-run]")
            else:
                print(f"   [FAIL] {img_path} ({status})")
        
        print(f"   [SIZE] {get_file_size_str(original_size)} -> {get_file_size_str(new_size)}")
    
    if not dry_run and images_embedded > 0:
        with open(svg_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
    
    return (images_embedded, new_size)

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Convert externally referenced images in SVG files to Base64 inline format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s 01_cover.svg                # Process a single file
  %(prog)s *.svg                       # Process all SVGs in current directory
  %(prog)s --dry-run *.svg             # Preview files to be processed
