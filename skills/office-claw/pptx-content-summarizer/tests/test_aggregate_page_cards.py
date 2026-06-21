from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "aggregate_page_cards.py"
)


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("aggregate_page_cards", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def make_card(tmp_path: Path, slide_number: int, logic_block: str = "分析", metrics=None, decision_points=None) -> Path:
    card = {
        "schema_version": "pptx-content-summarizer-page-card-v1",
        "slide_number": slide_number,
        "title": f"第{slide_number}页标题",
        "one_sentence": f"第{slide_number}页一句话总结。",
        "key_points": ["要点A", "要点B"],
        "metrics": metrics or [],
        "decision_points": decision_points or [],
        "logic_block": logic_block,
        "source_evidence": {"content": "原始文本", "tables": [], "speaker_notes": ""},
    }
    path = tmp_path / f"slide_{slide_number:03d}.json"
    path.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
    return path


def make_slide_input(tmp_path: Path, slide_number: int, doc_props: dict) -> Path:
    data = {
        "schema_version": "pptx-content-summarizer-slide-input-v1",
        "document_properties": doc_props,
        "slide_count": 3,
        "slide": {"slide_number": slide_number, "title": f"第{slide_number}页", "content": ""},
    }
    path = tmp_path / f"slide_{slide_number:03d}_input.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_find_slide_cards_returns_sorted_paths(mod, tmp_path):
    make_card(tmp_path, 3)
    make_card(tmp_path, 1)
    make_card(tmp_path, 2)
    result = mod.find_slide_cards(tmp_path)
    assert [p.name for p in result] == ["slide_001.json", "slide_002.json", "slide_003.json"]


def test_find_slide_cards_ignores_index(mod, tmp_path):
    make_card(tmp_path, 1)
    (tmp_path / "index.json").write_text("{}")
    result = mod.find_slide_cards(tmp_path)
    assert len(result) == 1


def test_load_document_properties_reads_first_slide_input(mod, tmp_path):
    doc_props = {"author": "张三", "title": "测试报告"}
    make_slide_input(tmp_path, 1, doc_props)
    make_slide_input(tmp_path, 2, {"author": "李四"})
    result = mod.load_document_properties(tmp_path)
    assert result["author"] == "张三"


def test_load_document_properties_returns_empty_when_no_inputs(mod, tmp_path):
    result = mod.load_document_properties(tmp_path)
    assert result == {}


def test_format_metrics_empty(mod):
    assert mod.format_metrics([]) == "无"


def test_format_metrics_single(mod):
    result = mod.format_metrics([{"value": "42%", "meaning": "市场占有率"}])
    assert result == "42%（市场占有率）"


def test_format_metrics_multiple(mod):
    metrics = [
        {"value": "42%", "meaning": "市场占有率"},
        {"value": "3.2亿", "meaning": "年收入"},
    ]
    result = mod.format_metrics(metrics)
    assert "42%（市场占有率）" in result
    assert "3.2亿（年收入）" in result


def test_format_decision_points_empty(mod):
    assert mod.format_decision_points([]) == "无"


def test_format_decision_points_single(mod):
    result = mod.format_decision_points(["是否进入XX市场"])
    assert result == "是否进入XX市场"


def test_build_aggregate_markdown_contains_slide_count(mod, tmp_path):
    make_card(tmp_path, 1)
    make_card(tmp_path, 2)
    cards = [json.loads(p.read_text(encoding="utf-8")) for p in mod.find_slide_cards(tmp_path)]
    md = mod.build_aggregate_markdown(cards, {"author": "张三"})
    assert "总页数：2" in md
    assert "张三" in md


def test_build_aggregate_markdown_contains_all_pages(mod, tmp_path):
    make_card(tmp_path, 1, logic_block="背景")
    make_card(tmp_path, 2, logic_block="分析")
    cards = [json.loads(p.read_text(encoding="utf-8")) for p in mod.find_slide_cards(tmp_path)]
    md = mod.build_aggregate_markdown(cards, {})
    assert "第1页" in md
    assert "第2页" in md
    assert "背景" in md
    assert "分析" in md


def test_build_aggregate_markdown_collects_global_metrics(mod, tmp_path):
    make_card(tmp_path, 1, metrics=[{"value": "42%", "meaning": "占有率"}])
    make_card(tmp_path, 2, metrics=[{"value": "3.2亿", "meaning": "收入"}])
    cards = [json.loads(p.read_text(encoding="utf-8")) for p in mod.find_slide_cards(tmp_path)]
    md = mod.build_aggregate_markdown(cards, {})
    assert "全局指标汇总" in md
    assert "42%" in md
    assert "3.2亿" in md


def test_build_aggregate_markdown_collects_global_decision_points(mod, tmp_path):
    make_card(tmp_path, 1, decision_points=["是否进入XX市场"])
    cards = [json.loads(p.read_text(encoding="utf-8")) for p in mod.find_slide_cards(tmp_path)]
    md = mod.build_aggregate_markdown(cards, {})
    assert "全局决策点汇总" in md
    assert "是否进入XX市场" in md


def test_build_aggregate_markdown_excludes_source_evidence(mod, tmp_path):
    make_card(tmp_path, 1)
    cards = [json.loads(p.read_text(encoding="utf-8")) for p in mod.find_slide_cards(tmp_path)]
    md = mod.build_aggregate_markdown(cards, {})
    assert "source_evidence" not in md
    assert "key_points" not in md


def test_aggregate_raises_when_page_cards_dir_missing(mod, tmp_path):
    with pytest.raises(FileNotFoundError):
        mod.aggregate(tmp_path / "nonexistent", None)


def test_aggregate_raises_when_no_cards(mod, tmp_path):
    cards_dir = tmp_path / "page_cards"
    cards_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        mod.aggregate(cards_dir, None)


def test_aggregate_end_to_end(mod, tmp_path):
    cards_dir = tmp_path / "page_cards"
    inputs_dir = tmp_path / "slide_inputs"
    cards_dir.mkdir()
    inputs_dir.mkdir()
    make_card(cards_dir, 1, logic_block="背景", metrics=[{"value": "10%", "meaning": "增速"}])
    make_card(cards_dir, 2, logic_block="分析", decision_points=["路线A还是路线B"])
    make_slide_input(inputs_dir, 1, {"author": "王五", "modified": "2026-05-01T00:00:00"})
    md = mod.aggregate(cards_dir, inputs_dir)
    assert "总页数：2" in md
    assert "王五" in md
    assert "背景" in md
    assert "10%（增速）" in md
    assert "路线A还是路线B" in md
