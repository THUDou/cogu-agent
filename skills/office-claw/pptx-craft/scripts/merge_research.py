
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class Page:
    number: int
    heading: str
    title: str
    page_type: str
    needs_research: bool
    visual_strategy: str


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SystemExit(f"Missing file: {path}")


def parse_topic(outline: str) -> str:
    match = re.search(r"^#\s*大纲[:：]\s*(.+?)\s*$", outline, re.M)
    return match.group(1).strip() if match else "未命名主题"


def parse_meta(outline: str, name: str) -> str | None:
    match = re.search(rf"^\*\*{re.escape(name)}\*\*[:：]\s*(.+?)\s*$", outline, re.M)
    return match.group(1).strip() if match else None


def parse_pages(outline: str) -> list[Page]:
    page_matches = list(re.finditer(r"^###\s*P(\d+)\s*[:：]\s*(.+?)\s*$", outline, re.M))
    pages: list[Page] = []

    for index, match in enumerate(page_matches):
        number = int(match.group(1))
        heading = match.group(2).strip()
        start = match.end()
        end = page_matches[index + 1].start() if index + 1 < len(page_matches) else len(outline)
        block = outline[start:end]

        page_type = extract_field(block, "类型") or "unknown"
        title = extract_field(block, "标题") or heading
        needs = extract_field(block, "研究需求") or ""
        summary = extract_field(block, "内容概要") or ""

        pages.append(
            Page(
                number=number,
                heading=heading,
                title=title,
                page_type=page_type,
                needs_research="✅" in needs,
                visual_strategy=summarize_visual_strategy(summary),
            )
        )

    return pages


def extract_field(block: str, name: str) -> str | None:
    match = re.search(rf"^-\s*\*\*{re.escape(name)}\*\*[:：]\s*(.+?)\s*$", block, re.M)
    return match.group(1).strip() if match else None


def summarize_visual_strategy(summary: str) -> str:
    if not summary:
        return "-"
    summary = re.sub(r"\s+", " ", summary).strip()
    return summary if len(summary) <= 48 else f"{summary[:45]}..."


def parse_page_numbers(value: str | None) -> set[int] | None:
    if not value:
        return None
    pages: set[int] = set()
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        if not item.isdigit():
            raise SystemExit(f"Invalid page number in --pages: {item}")
        pages.add(int(item))
    return pages


def count_sources(outline: str) -> str:
    source_section = re.search(
        r"^##\s*已搜索来源\s*$([\s\S]*?)(?=^##\s+|\Z)", outline, re.M
    )
    if not source_section:
        return "待核验"

    rows = 0
    for line in source_section.group(1).splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if re.match(r"^\|\s*-+", stripped):
            continue
        if any(header in stripped for header in ("URL", "来源名称", "标题/描述")):
            continue
        rows += 1

    return str(rows) if rows else "待核验"


def normalize_research_fragment(text: str, page: Page) -> str:
    text = text.strip()
    if not text:
        raise SystemExit(f"Empty research fragment for P{page.number}")

    text = re.sub(r"^# .+?大纲研究报告\s*\n+", "", text)
    text = re.sub(r"^> 生成时间：.+?\n+", "", text)
    text = re.sub(r"^##\s*(研究概述|大纲总览|逐页研究成果|来源汇总)\s*\n+", "", text, flags=re.M)

    expected = rf"^###\s*P{page.number}\s*[:：]"
    if not re.search(expected, text):
        raise SystemExit(f"research-P{page.number}.md must start with '### P{page.number}:'")

    return text


def extract_core_points(fragments: list[str]) -> list[str]:
    points: list[str] = []
    for fragment in fragments:
        match = re.search(r"\*\*核心论点\*\*[:：]\s*(.+)", fragment)
        if match:
            point = re.sub(r"\s+", " ", match.group(1)).strip()
            points.append(point)
    return points


def build_overview(fragments: list[str], topic: str) -> str:
    points = extract_core_points(fragments)
    if not points:
        return f"本报告围绕「{topic}」展开分页深度研究，汇总各内容页的关键论点、数据线索与案例素材，供后续幻灯片设计使用。"
    selected = points[:3]
    return " ".join(selected)


def build_outline_table(pages: list[Page]) -> str:
    rows = ["| 页码 | 标题 | 类型 | 需要研究 | 视觉策略 |", "|:----:|------|------|:--------:|----------|"]
    for page in pages:
        rows.append(
            f"| P{page.number} | {escape_cell(page.title)} | {escape_cell(page.page_type)} | "
            f"{'✅' if page.needs_research else '❌'} | {escape_cell(page.visual_strategy)} |"
        )
    return "\n".join(rows)


def escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def validate_output(content: str, researched_pages: list[Page], structural_pages: list[Page]) -> None:
    required_sections = ("## 研究概述", "## 大纲总览", "## 逐页研究成果")
    missing = [section for section in required_sections if section not in content]
    if missing:
        raise SystemExit(f"Missing required sections: {', '.join(missing)}")

    for page in researched_pages:
        count = len(re.findall(rf"^###\s*P{page.number}\s*[:：]", content, re.M))
        if count != 1:
            raise SystemExit(f"Expected exactly one section for P{page.number}, found {count}")

    for page in structural_pages:
        if re.search(rf"^###\s*P{page.number}\s*[:：]", content, re.M):
            raise SystemExit(f"Structural page P{page.number} must not appear in research output")


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge research-P{N}.md files into research.md")
    parser.add_argument("--outline", required=True, type=Path, help="Path to outline.md")
    parser.add_argument("--output-dir", required=True, type=Path, help="Directory containing research-P{N}.md")
    parser.add_argument("--output", type=Path, help="Output research.md path")
    parser.add_argument("--pages", help="Comma-separated researched page numbers, e.g. 2,3,4")
    parser.add_argument("--search-mode", default=None, help="Pipeline search_mode")
    parser.add_argument("--research-depth", default="auto", help="Research depth label")
    args = parser.parse_args()

    outline_path = args.outline
    output_dir = args.output_dir
    output_path = args.output or output_dir / "research.md"

    outline = read_text(outline_path)
    pages = parse_pages(outline)
    if not pages:
        raise SystemExit(f"No pages found in outline: {outline_path}")

    requested_pages = parse_page_numbers(args.pages)
    researched_pages = [page for page in pages if page.needs_research]
    if requested_pages is not None:
        researched_pages = [page for page in researched_pages if page.number in requested_pages]

    structural_pages = [page for page in pages if not page.needs_research]
    if not researched_pages:
        raise SystemExit("No researched pages to merge")

    fragments: list[str] = []
    for page in sorted(researched_pages, key=lambda item: item.number):
        research_path = output_dir / f"research-P{page.number}.md"
        fragments.append(normalize_research_fragment(read_text(research_path), page))

    topic = parse_topic(outline)
    search_mode = args.search_mode or parse_meta(outline, "搜索模式") or "auto"
    total_sources = count_sources(outline)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    page_ratio = f"{len(researched_pages)}/{len(pages)}"

    content = "\n\n".join(
        [
            f"# {topic} — 大纲研究报告",
            f"> 生成时间：{timestamp} | 研究深度：{args.research_depth} | 搜索模式：{search_mode} | 来源总数：{total_sources} | 研究页面：{page_ratio}",
            "---",
            "## 研究概述",
            build_overview(fragments, topic),
            "---",
            "## 大纲总览",
            build_outline_table(pages),
            "---",
            "## 逐页研究成果",
            "\n\n".join(fragments),
            "",
        ]
    )

    validate_output(content, researched_pages, structural_pages)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"Merged {len(researched_pages)} research files into {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
