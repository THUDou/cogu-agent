import json
import logging
import os
import shutil
import subprocess


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
AGGREGATE = os.path.join(ROOT, 'scripts', 'aggregate.js')


def test_aggregate_only_requires_background_images(tmp_path):
    structure = {
        "file": "demo.pptx",
        "slide_count": 3,
        "slide_size": {
            "width_px": 1280,
            "height_px": 720,
            "width_cm": 33.87,
            "height_cm": 19.05,
            "aspect_ratio": "16:9",
        },
        "colors": {"accent1": "#112233", "accent2": "#445566"},
        "actual_colors": {},
        "fonts": {},
        "font_sizes": {},
        "para_alignment": {},
        "layouts": [],
        "master": {},
        "component_styles": {},
        "content_layout_styles": [
            {
                "id": "content-style-01",
                "name": "image text content",
                "subtype": "content-text-image",
                "description": "text blocks plus a right-side visual area",
                "usage_rule": "use when content includes explanation plus a visual",
            }
        ],
    }
    structure_path = tmp_path / "template_data.json"
    image_map_path = tmp_path / "image-map.json"
    output_path = tmp_path / "style.md"
    structure_path.write_text(json.dumps(structure, ensure_ascii=False), encoding="utf-8")
    image_map = {
        "asset_roles": {
            "background": [
                {"path": "images/bg_images/bg-high.png", "role": "background", "confidence": "high"},
                {"path": "images/bg_images/bg-medium.png", "role": "background", "confidence": "medium_high"},
            ],
            "style_assets": [
                {"path": "images/assets/corner-high.png", "role": "edge_decoration", "confidence": "high"},
                {"path": "images/assets/texture-low.png", "role": "decorative_texture", "confidence": "low"},
            ],
        }
    }
    image_map_path.write_text(json.dumps(image_map, ensure_ascii=False), encoding="utf-8")

    node_path = shutil.which('node')
    if node_path is None:
        logging.warning('node not found, skip')
        return
    subprocess.run(
        [
            node_path,
            AGGREGATE,
            str(structure_path),
            str(output_path),
            "--name=Test Style",
            f"--image-map={image_map_path}",
        ],
        check=True,
    )

    md = output_path.read_text(encoding="utf-8")
    assert "source page" not in md.lower()
    assert "#112233" not in md
    assert "#445566" not in md
    assert "content-text-image" in md
    assert "images/bg_images" in md
    assert "bg-high.png" in md
    assert "bg-medium.png" not in md
    assert "corner-high.png" not in md
    assert "texture-low.png" not in md
