"""Ecosystem — 12 语言生态规则

基于源码: ECC rules/ (12 语言生态系统)
COGU 实现: 语言规则 + 技能模板
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class LanguageRule:
    language: str = ""
    rules: list[str] = field(default_factory=list)
    conventions: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


ECOSYSTEM_RULES = {
    "python": LanguageRule(
        language="python",
        rules=[
            "Use type hints for all function signatures",
            "Follow PEP 8 style guide",
            "Use async/await for I/O operations",
            "Prefer pathlib over os.path",
            "Use dataclasses or Pydantic for data models",
        ],
        conventions={"indent": "4 spaces", "line_length": "88", "formatter": "black"},
    ),
    "typescript": LanguageRule(
        language="typescript",
        rules=[
            "Use strict TypeScript mode",
            "Prefer interfaces over type aliases",
            "Use async/await for promises",
            "Avoid any type",
            "Use Zod for runtime validation",
        ],
        conventions={"indent": "2 spaces", "line_length": "100", "formatter": "prettier"},
    ),
    "go": LanguageRule(
        language="go",
        rules=[
            "Follow Go conventions (gofmt)",
            "Use error handling patterns",
            "Prefer composition over inheritance",
            "Use context for cancellation",
            "Write table-driven tests",
        ],
        conventions={"indent": "tab", "line_length": "none", "formatter": "gofmt"},
    ),
    "rust": LanguageRule(
        language="rust",
        rules=[
            "Use Result<T, E> for error handling",
            "Prefer iterators over loops",
            "Use lifetimes explicitly",
            "Follow Rust API guidelines",
            "Write doc comments for public items",
        ],
        conventions={"indent": "4 spaces", "line_length": "none", "formatter": "rustfmt"},
    ),
    "java": LanguageRule(
        language="java",
        rules=[
            "Follow Google Java Style Guide",
            "Use Optional for nullable returns",
            "Prefer streams for collection operations",
            "Use try-with-resources for AutoCloseable",
            "Write Javadoc for public APIs",
        ],
        conventions={"indent": "4 spaces", "line_length": "100", "formatter": "google-java-format"},
    ),
}


class EcosystemManager:
    """12 语言生态管理器"""

    def __init__(self, rules_dir: str | Path = ".cogu/rules"):
        self._rules_dir = Path(rules_dir)
        self._rules: dict[str, LanguageRule] = dict(ECOSYSTEM_RULES)

    def get_rule(self, language: str) -> Optional[LanguageRule]:
        return self._rules.get(language.lower())

    def list_languages(self) -> list[str]:
        return list(self._rules.keys())

    def add_rule(self, rule: LanguageRule) -> None:
        self._rules[rule.language.lower()] = rule

    def get_rules_for_file(self, file_path: str) -> Optional[LanguageRule]:
        ext = Path(file_path).suffix.lower()
        lang_map = {
            ".py": "python", ".js": "javascript", ".ts": "typescript",
            ".go": "go", ".rs": "rust", ".java": "java",
            ".swift": "swift", ".kt": "kotlin", ".rb": "ruby",
            ".php": "php", ".cs": "csharp", ".cpp": "cpp",
        }
        language = lang_map.get(ext)
        return self._rules.get(language) if language else None


__all__ = ["EcosystemManager", "LanguageRule", "ECOSYSTEM_RULES"]
