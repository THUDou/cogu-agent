
from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


LOGGER = logging.getLogger(__name__)
SLIDE_CARD_PATTERN = re.compile(r"^slide_(\d{3,})\.json$")


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_slide_cards(page_cards_dir: Path) -> List[Path]:
    return sorted(
        [p for p in page_cards_dir.glob("slide_*.json") if SLIDE_CARD_PATTERN.match(p.name)],
        key=lambda p: int(SLIDE_CARD_PATTERN.match(p.name).group(1)),
    )


def load_document_properties(slide_inputs_dir: Path) -> Dict[str, Any]:
    candidates = sorted(slide_inputs_dir.glob("slide_*_input.json"))
    if not candidates:
        return {}
    data = load_json(candidates[0])
    return data.get("document_properties", {})


def format_metrics(metrics: List[Any]) -> str:
    if not metrics:
        return "无"
    parts = []
    for m in metrics:
        if isinstance(m, dict):
            value = m.get("value", "")
            meaning = m.get("meaning", "")
            if value and meaning:
                parts.append(f"{value}（{meaning}）")
            elif value:
                parts.append(value)
    return "、".join(parts) if parts else "无"


def format_decision_points(decision_points: List[Any]) -> str:
    if not decision_points:
        return "无"
    points = [str(dp) for dp in decision_points if dp]
    return "、".join(points) if points else "无"


def build_aggregate_markdown(
    cards: List[Dict[str, Any]],
    document_properties: Dict[str, Any],
) -> str:
    lines: List[str] = []

    lines.append("# 文档概要")
    lines.append("")
    lines.append(f"- 总页数：{len(cards)}")

    author = document_properties.get("author") or "未知"
    lines.append(f"- 作者：{author}")

    modified = document_properties.get("modified") or document_properties.get("created") or ""
    if modified:
        lines.append(f"- 日期：{str(modified)[:7]}")

    last_modified_by = document_properties.get("last_modified_by") or ""
    if last_modified_by:
        lines.append(f"- 最后修改人：{last_modified_by}")

    lines.append("")
    lines.append("# 各页摘要")
    lines.append("")

    all_metrics: List[Dict[str, Any]] = []
    all_decision_points: List[Dict[str, Any]] = []

    for card in cards:
        slide_number = card.get("slide_number", "?")
        title = card.get("title", "")
        logic_block = card.get("logic_block", "未分类")
        one_sentence = card.get("one_sentence", "")
        metrics = card.get("metrics", [])
        decision_points = card.get("decision_points", [])

        lines.append(f"## 第{slide_number}页 — {title}（逻辑块：{logic_block}）")
        lines.append(f"一句话：{one_sentence}")
        lines.append(f"指标：{format_metrics(metrics)}")
        lines.append(f"决策点：{format_decision_points(decision_points)}")
        lines.append("")

        for m in metrics:
            if isinstance(m, dict) and (m.get("value") or m.get("meaning")):
                all_metrics.append({"slide_number": slide_number, **m})

        for dp in decision_points:
            if dp:
                all_decision_points.append({"slide_number": slide_number, "point": str(dp)})

    lines.append("# 全局指标汇总")
    lines.append("")
    if all_metrics:
        for m in all_metrics:
            value = m.get('value', '')
            meaning = m.get('meaning', '')
            if meaning:
                lines.append(f"- 第{m['slide_number']}页：{value}（{meaning}）")
            else:
                lines.append(f"- 第{m['slide_number']}页：{value}")
    else:
        lines.append("- 无")
    lines.append("")

    lines.append("# 全局决策点汇总")
    lines.append("")
    if all_decision_points:
        for dp in all_decision_points:
            lines.append(f"- 第{dp['slide_number']}页：{dp['point']}")
    else:
        lines.append("- 无")
    lines.append("")

    return "\n".join(lines)


def aggregate(page_cards_dir: Path, slide_inputs_dir: Optional[Path]) -> str:
    if not page_cards_dir.exists():
        raise FileNotFoundError(f"Page cards directory not found: {page_cards_dir}")

    card_paths = find_slide_cards(page_cards_dir)
    if not card_paths:
        raise FileNotFoundError(f"No slide cards found in: {page_cards_dir}")

    cards = [load_json(p) for p in card_paths]

    document_properties: Dict[str, Any] = {}
    if slide_inputs_dir and slide_inputs_dir.exists():
        document_properties = load_document_properties(slide_inputs_dir)

    return build_aggregate_markdown(cards, document_properties)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("page_cards_dir", help="Directory containing slide_XXX.json files")
    parser.add_argument(
        "--slide-inputs",
        help="Directory containing slide_XXX_input.json files (for document_properties)",
    )
    parser.add_argument("--output", "-o", required=True, help="Output Markdown path")
    args = parser.parse_args()

    slide_inputs_dir = Path(args.slide_inputs) if args.slide_inputs else None
    markdown = aggregate(Path(args.page_cards_dir), slide_inputs_dir)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    LOGGER.info("Wrote aggregate Markdown: %s", output_path.resolve())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
