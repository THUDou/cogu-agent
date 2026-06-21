from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "build_page_cards_index.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("build_page_cards_index", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_card(path: Path, slide_number: int) -> None:
    path.write_text(
        json.dumps({
            "schema_version": "pptx-content-summarizer-page-card-v1",
            "slide_number": slide_number,
            "title": f"Slide {slide_number}",
            "one_sentence": f"Slide {slide_number}",
            "key_points": [],
            "metrics": [],
            "decision_points": [],
            "logic_block": "Example",
            "source_evidence": {
                "content": "",
                "tables": [],
                "speaker_notes": "",
            },
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_build_page_cards_index_sorts_slide_files_numerically(tmp_path):
    module = load_module()
    page_cards_dir = tmp_path / "page_cards"
    page_cards_dir.mkdir()
    write_card(page_cards_dir / "slide_002.json", 2)
    write_card(page_cards_dir / "slide_001.json", 1)

    index = module.build_index(page_cards_dir)

    assert index == {
        "schema_version": "pptx-content-summarizer-page-cards-index-v1",
        "slide_count": 2,
        "cards": ["slide_001.json", "slide_002.json"],
    }


def test_write_index_writes_index_json(tmp_path):
    module = load_module()
    page_cards_dir = tmp_path / "page_cards"
    page_cards_dir.mkdir()
    write_card(page_cards_dir / "slide_001.json", 1)

    index_path = module.write_index(page_cards_dir)

    assert index_path == page_cards_dir / "index.json"
    assert json.loads(index_path.read_text(encoding="utf-8"))["cards"] == ["slide_001.json"]
