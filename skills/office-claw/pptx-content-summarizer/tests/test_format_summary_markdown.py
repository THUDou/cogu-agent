from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "format_summary_markdown.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("format_summary_markdown", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_format_summary_adds_single_blank_line_after_h1():
    module = load_module()
    source = "# 示例摘要\n## 文档信息\n内容\n"

    result = module.format_markdown(source)

    assert result.startswith("# 示例摘要\n\n## 文档信息\n内容\n")


def test_format_summary_removes_blank_lines_after_h2_and_h3():
    module = load_module()
    source = (
        "# 示例摘要\n\n"
        "## 核心发现\n\n\n"
        "1. 发现\n\n"
        "## 详细展开\n"
        "### 【背景】\n\n"
        "正文\n"
    )

    result = module.format_markdown(source)

    assert "## 核心发现\n1. 发现" in result
    assert "### 【背景】\n正文" in result


def test_format_summary_adds_blank_line_before_headings():
    module = load_module()
    source = "# 示例摘要\n\n## 文档信息\n内容\n## 一句话总结\n总结\n"

    result = module.format_markdown(source)

    assert "内容\n\n## 一句话总结" in result


def test_format_summary_strips_metric_brackets_in_key_data_section():
    module = load_module()
    source = (
        "# 示例摘要\n\n"
        "## 关键数据/决策点\n"
        "- 【80%】：金融机构占比\n"
        "- 【2026年5月】：时间节点\n\n"
        "## 行动启示/待回答问题\n"
        "1. 行动\n"
    )

    result = module.format_markdown(source)

    assert "- 80%：金融机构占比" in result
    assert "- 2026年5月：时间节点" in result
    assert "【80%】" not in result


def test_validate_summary_reports_non_digit_key_data_item():
    module = load_module()
    source = (
        "# 示例摘要\n\n"
        "## 关键数据/决策点\n"
        "- 决策点：需要确认预算\n"
    )

    errors = module.validate_markdown(source)

    assert any("关键数据/决策点" in error and "阿拉伯数字" in error for error in errors)


def test_format_summary_is_idempotent():
    module = load_module()
    source = (
        "# 示例摘要\n"
        "## 文档信息\n\n"
        "内容\n"
        "## 关键数据/决策点\n"
        "- 【30%】：指标含义\n"
    )

    once = module.format_markdown(source)
    twice = module.format_markdown(once)

    assert once == twice


def test_format_summary_honors_custom_heading_spacing_config():
    module = load_module()
    config = module.load_config()
    config["heading_spacing"]["h2_blank_lines_after"] = 1
    source = "# Demo摘要\n\n## 文档信息\n内容\n"

    result = module.format_markdown(source, config)

    assert "## 文档信息\n\n内容" in result
