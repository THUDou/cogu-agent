from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_page_cards.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("validate_page_cards", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def valid_card(slide_number: int) -> dict:
    return {
        "schema_version": "pptx-content-summarizer-page-card-v1",
        "slide_number": slide_number,
        "title": f"Slide {slide_number}",
        "one_sentence": f"Slide {slide_number} explains the main point.",
        "key_points": ["Main point"],
        "metrics": [{"value": "42%", "meaning": "Example metric"}],
        "decision_points": ["Example decision"],
        "logic_block": "Example block",
        "source_evidence": {
            "content": "Source text",
            "tables": [],
            "speaker_notes": "",
        },
    }


def write_valid_page_cards(page_cards_dir: Path, slide_count: int = 2) -> None:
    cards = []
    for slide_number in range(1, slide_count + 1):
        filename = f"slide_{slide_number:03d}.json"
        cards.append(filename)
        write_json(page_cards_dir / filename, valid_card(slide_number))
    write_json(page_cards_dir / "index.json", {
        "schema_version": "pptx-content-summarizer-page-cards-index-v1",
        "slide_count": slide_count,
        "cards": cards,
    })


def test_validate_page_cards_accepts_complete_page_cards(tmp_path):
    module = load_module()
    page_cards_dir = tmp_path / "page_cards"
    write_valid_page_cards(page_cards_dir)

    assert module.validate_page_cards(page_cards_dir) == []


def test_validate_page_cards_reports_missing_card_file(tmp_path):
    module = load_module()
    page_cards_dir = tmp_path / "page_cards"
    write_valid_page_cards(page_cards_dir)
    (page_cards_dir / "slide_002.json").unlink()

    errors = module.validate_page_cards(page_cards_dir)

    assert errors == ["Missing page card file: slide_002.json"]


def test_validate_page_cards_reports_missing_required_field(tmp_path):
    module = load_module()
    page_cards_dir = tmp_path / "page_cards"
    write_valid_page_cards(page_cards_dir)
    card = valid_card(1)
    del card["one_sentence"]
    write_json(page_cards_dir / "slide_001.json", card)

    errors = module.validate_page_cards(page_cards_dir)

    assert "slide_001.json missing required field: one_sentence" in errors
