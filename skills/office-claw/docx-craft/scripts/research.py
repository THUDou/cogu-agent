
import datetime
import json
import logging
import sys
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def convert_research_to_content(research_md_path, title="", author="", recipe="report"):
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

    structure_match = re.search(r"## 建议文档结构\s*\n(.*?)(?=\n## |\Z)", research_text, re.DOTALL)
    if structure_match:
        for line in structure_match.group(1).strip().split("\n"):
            line = line.strip()
            if line and re.match(r"^\d+\.", line):
                text = re.sub(r"^\d+\.\s*", "", line)
                parts = re.split(r"[：:]", text, maxsplit=1)
                heading_text = parts[0].strip()
                if heading_text:
                    body.append({"type": "heading", "text": heading_text, "level": 1})

    sections = re.split(r"### (.+?)(?=\n)", research_text)
    for i in range(1, len(sections), 2):
        section_title = sections[i].strip()
        section_content = sections[i + 1] if i + 1 < len(sections) else ""

        body.append({"type": "heading", "text": section_title, "level": 2})

        analysis_match = re.search(r"#### 研究分析\s*\n(.*?)(?=\n#### |\n### |\Z)", section_content, re.DOTALL)
        if analysis_match:
            for line in analysis_match.group(1).strip().split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    body.append({"type": "paragraph", "text": line})

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
