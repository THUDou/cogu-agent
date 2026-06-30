
from __future__ import annotations

import base64
import hashlib
import io
import mimetypes
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    from PIL import Image, ImageEnhance
except ImportError:  # pragma: no cover - optional visual enhancement dependency
    Image = None
    ImageEnhance = None

from .emu_units import NS, Xfrm, fmt_num
from .ooxml_loader import OoxmlPackage, PartRef


@dataclass
class PictureResult:

    svg: str = ""
    media: dict[str, bytes] = field(default_factory=dict)


class MediaResolutionError(RuntimeError):


def convert_blip_fill(
    blip_fill_elem: ET.Element,
    xfrm: Xfrm,
    slide_part: PartRef,
    pkg: OoxmlPackage,
    *,
    media_subdir: str = "assets",
    embed_inline: bool = False,
    asset_name_map: dict[str, str] | None = None,
) -> PictureResult:
    blip = blip_fill_elem.find("a:blip", NS)
    if blip is None:
        return PictureResult()

    rid = blip.attrib.get(f"{{{NS['r']}}}embed")
    linked_rid = blip.attrib.get(f"{{{NS['r']}}}link")
    if not rid:
        if linked_rid:
            raise MediaResolutionError(
                "Linked image relationships are not supported; embed the image in PowerPoint first"
            )
        return PictureResult()

    target = slide_part.resolve_rel(rid)
    if not target:
        raise MediaResolutionError(f"Image relationship {rid} cannot be resolved in {slide_part.path}")

    img_bytes = pkg.read_media(target)
    if img_bytes is None:
        raise MediaResolutionError(f"Embedded image part is missing: {target}")

    filename = (asset_name_map or {}).get(target, pkg.media_filename(target))
    filename, img_bytes = _normalize_office_media(filename, img_bytes)
    filename, img_bytes = _apply_blip_image_effects(filename, img_bytes, blip)
    href = _build_href(filename, img_bytes, media_subdir, embed_inline)

    src_rect = blip_fill_elem.find("a:srcRect", NS)
    crop = _parse_src_rect(src_rect)

    has_stretch = blip_fill_elem.find("a:stretch") is not None
    if not has_stretch:
        pass

    if crop is None:
        svg = (
            f'<image href="{href}" x="{fmt_num(xfrm.x)}" y="{fmt_num(xfrm.y)}" '
            f'width="{fmt_num(xfrm.w)}" height="{fmt_num(xfrm.h)}" '
            f'preserveAspectRatio="none"/>'
        )
    else:
        vb_l, vb_t, vb_w, vb_h = crop
        svg = (
            f'<svg x="{fmt_num(xfrm.x)}" y="{fmt_num(xfrm.y)}" '
            f'width="{fmt_num(xfrm.w)}" height="{fmt_num(xfrm.h)}" '
            f'viewBox="{fmt_num(vb_l, 5)} {fmt_num(vb_t, 5)} '
            f'{fmt_num(vb_w, 5)} {fmt_num(vb_h, 5)}" '
            f'preserveAspectRatio="none">'
            f'<image href="{href}" x="0" y="0" width="1" height="1" '
            f'preserveAspectRatio="none"/>'
            f"</svg>"
        )

    media: dict[str, bytes] = {}
    if not embed_inline:
        media[filename] = img_bytes
    return PictureResult(svg=svg, media=media)


def convert_picture(
    pic_elem: ET.Element,
    xfrm: Xfrm,
    slide_part: PartRef,
    pkg: OoxmlPackage,
    *,
    media_subdir: str = "assets",
    embed_inline: bool = False,
    asset_name_map: dict[str, str] | None = None,
) -> PictureResult:
    blip_fill = pic_elem.find("p:blipFill", NS)
    if blip_fill is None:
        return PictureResult()

    return convert_blip_fill(
        blip_fill, xfrm, slide_part, pkg,
        media_subdir=media_subdir,
        embed_inline=embed_inline,
        asset_name_map=asset_name_map,
    )



_OFFICE_VECTOR_EXTS = {".emf", ".wmf"}


def _normalize_office_media(filename: str, img_bytes: bytes) -> tuple[str, bytes]:
    suffix = Path(filename).suffix.lower()
    if suffix not in _OFFICE_VECTOR_EXTS:
        return filename, img_bytes

    converted = _convert_office_vector_to_png(filename, img_bytes)
    if converted is None:
        return filename, img_bytes
    stem = Path(filename).stem
    return f"{stem}_preview.png", converted


def _convert_office_vector_to_png(filename: str, img_bytes: bytes) -> bytes | None:
    magick = shutil.which("magick")
    if not magick:
        return None
    suffix = Path(filename).suffix.lower() or ".bin"
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        src = tmp_dir / f"source{suffix}"
        dst = tmp_dir / "preview.png"
        src.write_bytes(img_bytes)
        try:
            subprocess.run(
                [magick, str(src), str(dst)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (OSError, subprocess.CalledProcessError):
            return None
        if not dst.exists():
            return None
        return dst.read_bytes()

def _parse_src_rect(elem: ET.Element | None) -> tuple[float, float, float, float] | None:
    if elem is None:
        return None
    if not (elem.attrib.keys() & {"l", "t", "r", "b"}):
        return None
    l = _pct_attr(elem, "l")
    t = _pct_attr(elem, "t")
    r = _pct_attr(elem, "r")
    b = _pct_attr(elem, "b")
    if l == 0 and t == 0 and r == 0 and b == 0:
        return None
    vb_x = l
    vb_y = t
    vb_w = max(0.0, 1.0 - l - r)
    vb_h = max(0.0, 1.0 - t - b)
    if vb_w <= 0 or vb_h <= 0:
        return None
    return vb_x, vb_y, vb_w, vb_h


def _apply_blip_image_effects(
    filename: str,
    img_bytes: bytes,
    blip: ET.Element,
) -> tuple[str, bytes]:
    lum = blip.find("a:lum", NS)
    if lum is None:
        return filename, img_bytes

    bright = _signed_pct_attr(lum, "bright")
    contrast = _signed_pct_attr(lum, "contrast")
    if bright is None and contrast is None:
        return filename, img_bytes
    if Image is None or ImageEnhance is None:
        return filename, img_bytes

    try:
        image = Image.open(io.BytesIO(img_bytes))
        output_format = image.format or _pil_format_from_filename(filename)
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
        if bright is not None:
            image = ImageEnhance.Brightness(image).enhance(max(0.0, 1.0 + bright))
        if contrast is not None:
            image = ImageEnhance.Contrast(image).enhance(max(0.0, 1.0 + contrast))

        out = io.BytesIO()
        save_format = output_format or "PNG"
        save_kwargs = {"quality": 95} if save_format.upper() in {"JPEG", "JPG"} else {}
        image.save(out, format=save_format, **save_kwargs)
        effect_key = f"lum-{bright}-{contrast}".encode("ascii")
        digest = hashlib.sha1(effect_key).hexdigest()[:8]
        return _effect_filename(filename, digest, save_format), out.getvalue()
    except Exception:
        return filename, img_bytes


def _signed_pct_attr(elem: ET.Element, name: str) -> float | None:
    val = elem.attrib.get(name)
    if val is None:
        return None
    try:
        return float(val) / 100000.0
    except ValueError:
        return None


def _pil_format_from_filename(filename: str) -> str | None:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in {"jpg", "jpeg"}:
        return "JPEG"
    if ext == "png":
        return "PNG"
    if ext == "gif":
        return "GIF"
    if ext == "webp":
        return "WEBP"
    return None


def _effect_filename(filename: str, digest: str, image_format: str) -> str:
    stem, sep, ext = filename.rpartition(".")
    if not sep:
        ext = (image_format or "png").lower()
        stem = filename
    if ext.lower() == "jpg":
        ext = "jpeg"
    return f"{stem}_fx_{digest}.{ext}"


def _pct_attr(elem: ET.Element, name: str) -> float:
    val = elem.attrib.get(name)
    if val is None:
        return 0.0
    try:
        return float(val) / 100000.0
    except ValueError:
        return 0.0


def _build_href(filename: str, img_bytes: bytes, subdir: str, embed: bool) -> str:
    if embed:
        mime = (
            mimetypes.guess_type(filename)[0]
            or _sniff_mime(img_bytes)
            or "application/octet-stream"
        )
        encoded = base64.b64encode(img_bytes).decode("ascii")
        return f"data:{mime};base64,{encoded}"
    rel = f"../{subdir}/{filename}" if subdir else f"../{filename}"
    return rel


def _sniff_mime(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "image/gif"
    if data.startswith(b"<svg") or data.startswith(b"<?xml"):
        return "image/svg+xml"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None
