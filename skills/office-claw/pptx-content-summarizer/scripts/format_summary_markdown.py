#!/usr/bin/env python3
"""Format final summary Markdown using configurable spacing rules."""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


LOGGER = logging.getLogger(__name__)
DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "summary_format.json"
)
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
KEY_DATA_BRACKET_PATTERN = re.compile(r"^(\s*[-*]\s*)【([^】]+)】\s*[:：]\s*(.*)$")
KEY_DATA_COLON_PATTERN = re.compile(r"^(\s*[-*]\s*)([^:：]+)\s*[:：]\s*(.*)$")


def load_config(config_path: Optional[Path | str] = None) -> Dict[str, Any]:
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_lines(text: str) -> List[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return [line.rstrip() for line in normalized.split("\n")]


def heading_level(line: str) -> int:
    match = HEADING_PATTERN.match(line)
    return len(match.group(1)) if match else 0


def strip_trailing_blanks(lines: List[str]) -> None:
    while lines and lines[-1] == "":
        lines.pop()


def int_config_value(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def blank_lines_before_heading(level: int, config: Dict[str, Any]) -> int:
    if level <= 1:
        return 0
    spacing = config.get("heading_spacing", {})
    key = f"h{level}_blank_lines_before"
    return int_config_value(spacing.get(key, 1), 1)


def blank_lines_after_heading(level: int, config: Dict[str, Any]) -> int:
    title_config = config.get("title", {})
    title_level = int_config_value(title_config.get("level", 1), 1)
    if level == title_level:
        return int_config_value(title_config.get("blank_lines_after", 1), 1)
    spacing = config.get("heading_spacing", {})
    key = f"h{level}_blank_lines_after"
    return int_config_value(spacing.get(key, 0), 0)


def remove_blanks_in_detail_section(text: str) -> str:
    """在'详细展开'章节内，删除内容段落之间的空行，但保留 h3 子标题前的空行。"""
    lines = text.split("\n")
    output: List[str] = []
    in_detail_section = False
    in_h3_subsection = False

    for i, line in enumerate(lines):
        # 检查是否进入/离开"详细展开"章节
        if line.strip() == "## 详细展开":
            in_detail_section = True
            in_h3_subsection = False
            output.append(line)
            continue

        # 检查是否离开"详细展开"（遇到下一个 ## 标题）
        if in_detail_section and line.startswith("##") and not line.startswith("###"):
            in_detail_section = False
            in_h3_subsection = False

        # 在"详细展开"内，检查 h3 标题
        if in_detail_section and line.startswith("### "):
            in_h3_subsection = True
            output.append(line)
            continue

        # 在 h3 子标题下的内容：删除空行
        if in_detail_section and in_h3_subsection:
            if line == "":
                # 跳过空行，除非下一行是 h3 标题
                next_idx = i + 1
                while next_idx < len(lines) and lines[next_idx] == "":
                    next_idx += 1
                if next_idx < len(lines) and lines[next_idx].startswith("### "):
                    # 下一行是 h3，保留空行
                    output.append(line)
                # 否则跳过此空行
                continue
            elif line.startswith("### "):
                # 遇到下一个 h3，保留它
                output.append(line)
                continue

        output.append(line)

    return "\n".join(output)


def normalize_heading_spacing(text: str, config: Dict[str, Any]) -> str:
    lines = normalize_lines(text)
    output: List[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        level = heading_level(line)

        if level:
            # 查找前面最后一个非空行
            last_non_blank_idx = len(output) - 1
            while last_non_blank_idx >= 0 and output[last_non_blank_idx] == "":
                last_non_blank_idx -= 1

            prev_level = (
                heading_level(output[last_non_blank_idx])
                if last_non_blank_idx >= 0
                else 0
            )
            prev_is_heading = prev_level > 0

            strip_trailing_blanks(output)

            # 只有当前面不是标题，或前面是 h1（h1 后有特殊空行处理），才添加标题前的空行
            title_level = int_config_value(config.get("title", {}).get("level", 1), 1)
            should_add_blank = (
                output
                and (
                    not prev_is_heading
                    or (prev_is_heading and prev_level == title_level)
                )
            )
            if should_add_blank:
                output.extend([""] * blank_lines_before_heading(level, config))

            output.append(line)
            index += 1

            while index < len(lines) and lines[index] == "":
                index += 1

            output.extend([""] * blank_lines_after_heading(level, config))
            continue

        if line == "":
            if output and output[-1] != "":
                output.append("")
            index += 1
            continue

        output.append(line)
        index += 1

    strip_trailing_blanks(output)
    return "\n".join(output) + "\n"


def current_h2_section(line: str) -> Optional[str]:
    match = HEADING_PATTERN.match(line)
    if match and len(match.group(1)) == 2:
        return match.group(2).strip()
    return None


def normalize_key_data_item(line: str) -> str:
    bracket_match = KEY_DATA_BRACKET_PATTERN.match(line)
    if bracket_match:
        prefix, value, meaning = bracket_match.groups()
        return f"{prefix}{value.strip()}：{meaning.strip()}"

    colon_match = KEY_DATA_COLON_PATTERN.match(line)
    if colon_match:
        prefix, value, meaning = colon_match.groups()
        return f"{prefix}{value.strip()}：{meaning.strip()}"

    return line


def normalize_key_data_section(text: str, config: Dict[str, Any]) -> str:
    key_data_config = config.get("key_data", {})
    section_name = key_data_config.get("section", "关键数据/决策点")
    should_strip_brackets = bool(key_data_config.get("strip_metric_brackets", True))
    lines = text.split("\n")
    output: List[str] = []
    in_key_data_section = False

    for line in lines:
        section = current_h2_section(line)
        if section is not None:
            in_key_data_section = section == section_name

        if in_key_data_section and should_strip_brackets and line.lstrip().startswith(("-", "*")):
            output.append(normalize_key_data_item(line))
        else:
            output.append(line)

    return "\n".join(output)


def format_markdown(text: str, config: Optional[Dict[str, Any]] = None) -> str:
    active_config = config or load_config()
    formatted = remove_blanks_in_detail_section(text)
    formatted = normalize_heading_spacing(formatted, active_config)
    formatted = normalize_key_data_section(formatted, active_config)
    if not formatted.endswith("\n"):
        formatted += "\n"
    return formatted


def key_data_errors(text: str, config: Dict[str, Any]) -> List[str]:
    key_data_config = config.get("key_data", {})
    section_name = key_data_config.get("section", "关键数据/决策点")
    require_digit_prefix = bool(key_data_config.get("require_digit_prefix", True))
    lines = normalize_lines(text)
    errors: List[str] = []
    in_key_data_section = False

    for line in lines:
        section = current_h2_section(line)
        if section is not None:
            in_key_data_section = section == section_name
            continue

        if not in_key_data_section or not line.lstrip().startswith(("-", "*")):
            continue

        content = line.lstrip()[1:].strip()
        if not content:
            continue
        if content.startswith("【"):
            errors.append(f"{section_name} 条目不要给数字或指标加【】: {line}")
        if require_digit_prefix and not re.match(r"^\d", content):
            errors.append(f"{section_name} 条目必须以阿拉伯数字开头: {line}")

    return errors


def validate_markdown(text: str, config: Optional[Dict[str, Any]] = None) -> List[str]:
    active_config = config or load_config()
    errors: List[str] = []
    normalized = "\n".join(normalize_lines(text)).rstrip() + "\n"
    if format_markdown(text, active_config) != normalized:
        errors.append("Markdown 空行或关键数据格式未按 formatter 规范整理")
    errors.extend(key_data_errors(text, active_config))
    return errors


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("markdown_path", help="Summary Markdown file to format")
    parser.add_argument("--config", help="Optional summary format config JSON path")
    parser.add_argument("--in-place", action="store_true", help="Rewrite the input file")
    parser.add_argument("--output", "-o", help="Write formatted Markdown to this file")
    parser.add_argument("--check", action="store_true", help="Validate without writing")
    args = parser.parse_args()

    markdown_path = Path(args.markdown_path)
    config = load_config(args.config)
    source = markdown_path.read_text(encoding="utf-8")

    if args.check:
        errors = validate_markdown(source, config)
        if errors:
            for error in errors:
                LOGGER.error(error)
            return 1
        LOGGER.info("Summary Markdown format check passed: %s", markdown_path.resolve())
        return 0

    formatted = format_markdown(source, config)
    if args.in_place:
        markdown_path.write_text(formatted, encoding="utf-8")
        LOGGER.info("Formatted summary Markdown: %s", markdown_path.resolve())
        return 0

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(formatted, encoding="utf-8")
        LOGGER.info("Wrote formatted summary Markdown: %s", output_path.resolve())
        return 0

    LOGGER.error(
        "Please specify --in-place to modify the file or --output to write to a new file"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
