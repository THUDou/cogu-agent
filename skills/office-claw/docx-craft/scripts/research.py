#!/usr/bin/env python3
"""
docx-craft research helper.

This script provides a utility to convert deepresearch-writer output (research.md)
into content.json format for create.js. It is NOT the research execution engine —
the actual research is performed by the deepresearch-writer subskill via the Claude
Agent tool.

Usage (by Claude agent):
    1. Spawn deepresearch-writer subagent via Agent tool
    2. Read {output_dir}/research.md
    3. Convert to content.json using this script or manual mapping

Research direction hints by document type:
    行业报告 → 市场规模/竞争格局/趋势预测
    学术论文 → 文献综述/方法论/最新进展
    技术报告 → 技术现状/对比分析/案例数据
    政策解读 → 政策原文/影响范围/合规要求

deepresearch-writer output (research.md) structure:
    - ## 研究概述 → cover subtitle
    - ## 逐章节研究成果 → body sections
      - #### 研究分析 → paragraphs
      - 关键数据清单 → tables
      - 时序数据 → tables
      - 对比数据 → tables
    - ## 建议文档结构 → heading hierarchy
    - ## 来源汇总 → references section

After converting research.md to content.json, use:
    node scripts/create.js --recipe <type> --content content.json --output out.docx
"""

import datetime
import json
import logging
import sys
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def convert_research_to_content(research_md_path, title="", author="", recipe="report"):
    """
    Convert deepresearch-writer output (research.md) to content.json format for create.js.

    Args:
        research_md_path: Path to research.md file
        title: Document title
        author: Document author
        recipe: Recipe name

    Returns:
        Dict in content.json format
    """
    research_text = Path(research_md_path).read_text(encoding="utf-8")

    content = {
        "title": title,
        "author": author,
        "sections": [
            {
                "type": "cover",
                "content": [
                    {"type": "title", "text": title},
                    {"type": "subtitle", "text": f"{author} | {datetime.date.today()}"},
                ],
            },
            {"type": "body", "content": []},
        ],
    }

    body = content["sections"][1]["content"]

    # Extract suggested document structure
    structure_match = re.search(r"## 建议文档结构\s*\n(.*?)(?=\n## |\Z)", research_text, re.DOTALL)
    if structure_match:
        for line in structure_match.group(1).strip().split("\n"):
            line = line.strip()
            if line and re.match(r"^\d+\.", line):
                text = re.sub(r"^\d+\.\s*", "", line)
                # Split on Chinese colon for description
                parts = re.split(r"[：:]", text, maxsplit=1)
                heading_text = parts[0].strip()
                if heading_text:
                    body.append({"type": "heading", "text": heading_text, "level": 1})

    # Extract research analysis sections
    sections = re.split(r"### (.+?)(?=\n)", research_text)
    for i in range(1, len(sections), 2):
        section_title = sections[i].strip()
        section_content = sections[i + 1] if i + 1 < len(sections) else ""

        body.append({"type": "heading", "text": section_title, "level": 2})

        # Extract key findings
        analysis_match = re.search(r"#### 研究分析\s*\n(.*?)(?=\n#### |\n### |\Z)", section_content, re.DOTALL)
        if analysis_match:
            for line in analysis_match.group(1).strip().split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    body.append({"type": "paragraph", "text": line})

        # Extract data tables
        table_matches = re.findall(r"\|(.+)\|\n\|[-\s|]+\|\n((?:\|.+\|\n)*)", section_content)
        for header_line, rows_block in table_matches:
            headers = [h.strip() for h in header_line.split("|") if h.strip()]
            rows = []
            for row_line in rows_block.strip().split("\n"):
                cells = [c.strip() for c in row_line.split("|") if c.strip() and c.strip() != "-"]
                if cells:
                    rows.append(cells)
            if headers and rows:
                body.append({"type": "table", "headers": headers, "rows": rows})

    # Extract sources
    sources_match = re.search(r"### 外部研究\s*\n\|(.+)\|\n\|[-\s|]+\|\n((?:\|.+\|\n)*)", research_text, re.DOTALL)
    if sources_match:
        body.append({"type": "heading", "text": "参考文献", "level": 1})
        items = []
        for row_line in sources_match.group(2).strip().split("\n"):
            cells = [c.strip() for c in row_line.split("|") if c.strip() and c.strip() != "-"]
            if len(cells) >= 3:
                items.append(f"{cells[1]} - {cells[3] if len(cells) > 3 else cells[2]}")
        if items:
            body.append({"type": "bullet_list", "items": items})

    return content


if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.info(__doc__)
        sys.exit(0)

    research_path = sys.argv[1]
    title = sys.argv[2] if len(sys.argv) > 2 else ""
    author = sys.argv[3] if len(sys.argv) > 3 else ""

    result = convert_research_to_content(research_path, title=title, author=author)
    logger.info(json.dumps(result, ensure_ascii=False, indent=2))
