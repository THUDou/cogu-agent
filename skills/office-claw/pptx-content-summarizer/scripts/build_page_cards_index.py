
from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple


LOGGER = logging.getLogger(__name__)
INDEX_SCHEMA_VERSION = "pptx-content-summarizer-page-cards-index-v1"
SLIDE_CARD_PATTERN = re.compile(r"^slide_(\d{3,})\.json$")


def slide_sort_key(path: Path) -> Tuple[int, str]:
    match = SLIDE_CARD_PATTERN.match(path.name)
    if not match:
        return (10**9, path.name)
    return (int(match.group(1)), path.name)


def find_slide_cards(page_cards_dir: Path) -> List[Path]:
    return sorted(
        [
            path
            for path in page_cards_dir.glob("slide_*.json")
            if SLIDE_CARD_PATTERN.match(path.name)
        ],
        key=slide_sort_key,
    )


def build_index(page_cards_dir: Path | str) -> Dict[str, Any]:
    page_cards_path = Path(page_cards_dir)
    if not page_cards_path.exists():
        raise FileNotFoundError(f"Page cards directory not found: {page_cards_path}")
    if not page_cards_path.is_dir():
        raise NotADirectoryError(f"Page cards path is not a directory: {page_cards_path}")

    cards = find_slide_cards(page_cards_path)
    if not cards:
        raise FileNotFoundError(f"No slide_XXX.json files found in: {page_cards_path}")

    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "slide_count": len(cards),
        "cards": [card.name for card in cards],
    }


def write_index(page_cards_dir: Path | str) -> Path:
    page_cards_path = Path(page_cards_dir)
    index = build_index(page_cards_path)
    index_path = page_cards_path / "index.json"
    index_path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    LOGGER.info("Wrote page cards index: %s", index_path.resolve())
    return index_path


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("page_cards_dir", help="Directory containing slide_XXX.json files")
    args = parser.parse_args()

    write_index(args.page_cards_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
