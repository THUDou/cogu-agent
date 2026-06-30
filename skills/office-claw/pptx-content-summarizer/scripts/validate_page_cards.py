
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List


LOGGER = logging.getLogger(__name__)
INDEX_SCHEMA_VERSION = "pptx-content-summarizer-page-cards-index-v1"
CARD_SCHEMA_VERSION = "pptx-content-summarizer-page-card-v1"
CARD_REQUIRED_FIELDS = [
    "schema_version",
    "slide_number",
    "title",
    "one_sentence",
    "key_points",
    "metrics",
    "decision_points",
    "logic_block",
    "source_evidence",
]
SOURCE_EVIDENCE_REQUIRED_FIELDS = [
    "content",
    "tables",
    "speaker_notes",
]


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def is_safe_card_name(card_name: str) -> bool:
    path = Path(card_name)
    return not path.is_absolute() and ".." not in path.parts and path.name == card_name


def validate_index(index: Dict[str, Any]) -> List[str]:
    errors = []

    if index.get("schema_version") != INDEX_SCHEMA_VERSION:
        errors.append(
            "index.json schema_version must be "
            f"{INDEX_SCHEMA_VERSION}"
        )

    slide_count = index.get("slide_count")
    if not isinstance(slide_count, int) or slide_count < 0:
        errors.append("index.json slide_count must be a non-negative integer")

    cards = index.get("cards")
    if not isinstance(cards, list):
        errors.append("index.json cards must be a list")
    elif isinstance(slide_count, int) and len(cards) != slide_count:
        errors.append("index.json cards length must match slide_count")

    return errors


def validate_source_evidence(
    card_name: str,
    source_evidence: Any,
) -> List[str]:
    errors = []
    if not isinstance(source_evidence, dict):
        return [f"{card_name} source_evidence must be an object"]

    for field in SOURCE_EVIDENCE_REQUIRED_FIELDS:
        if field not in source_evidence:
            errors.append(f"{card_name} source_evidence missing field: {field}")

    return errors


def validate_card(card_name: str, card: Dict[str, Any], expected_slide_number: int) -> List[str]:
    errors = []

    for field in CARD_REQUIRED_FIELDS:
        if field not in card:
            errors.append(f"{card_name} missing required field: {field}")

    if card.get("schema_version") != CARD_SCHEMA_VERSION:
        errors.append(
            f"{card_name} schema_version must be {CARD_SCHEMA_VERSION}"
        )

    if card.get("slide_number") != expected_slide_number:
        errors.append(
            f"{card_name} slide_number must be {expected_slide_number}"
        )

    list_fields = ["key_points", "metrics", "decision_points"]
    for field in list_fields:
        if field in card and not isinstance(card[field], list):
            errors.append(f"{card_name} {field} must be a list")

    string_fields = ["title", "one_sentence", "logic_block"]
    for field in string_fields:
        if field in card and not isinstance(card[field], str):
            errors.append(f"{card_name} {field} must be a string")

    if "source_evidence" in card:
        errors.extend(validate_source_evidence(card_name, card["source_evidence"]))

    return errors


def validate_page_cards(page_cards_dir: Path | str) -> List[str]:
    page_cards_path = Path(page_cards_dir)
    errors = []

    if not page_cards_path.exists():
        return [f"Page cards directory not found: {page_cards_path}"]
    if not page_cards_path.is_dir():
        return [f"Page cards path is not a directory: {page_cards_path}"]

    index_path = page_cards_path / "index.json"
    if not index_path.exists():
        return ["Missing page cards index: index.json"]

    try:
        index = load_json(index_path)
    except json.JSONDecodeError as exc:
        return [f"Invalid JSON in index.json: {exc}"]

    errors.extend(validate_index(index))
    cards = index.get("cards", [])
    if not isinstance(cards, list):
        return errors

    for expected_slide_number, card_name in enumerate(cards, start=1):
        if not isinstance(card_name, str) or not is_safe_card_name(card_name):
            errors.append(f"Unsafe page card filename: {card_name}")
            continue

        card_path = page_cards_path / card_name
        if not card_path.exists():
            errors.append(f"Missing page card file: {card_name}")
            continue

        try:
            card = load_json(card_path)
        except json.JSONDecodeError as exc:
            errors.append(f"Invalid JSON in {card_name}: {exc}")
            continue

        errors.extend(validate_card(card_name, card, expected_slide_number))

    return errors


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("page_cards_dir", help="Directory containing index.json and slide_XXX.json files")
    args = parser.parse_args()

    errors = validate_page_cards(args.page_cards_dir)
    if errors:
        for error in errors:
            LOGGER.error(error)
        return 1

    LOGGER.info("Page cards validation passed: %s", Path(args.page_cards_dir).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
