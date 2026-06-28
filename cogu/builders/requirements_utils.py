from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


@dataclass
class RequirementLine:
    name: str
    specifier: str
    original: str
    is_comment: bool = False
    is_empty: bool = False


_REQUIREMENT_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?)"
    r"(?P<specifier>.*)?$"
)

_EXTRAS_RE = re.compile(r"\[.*?\]")


def _normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_requirements_text(text: str) -> list[RequirementLine]:
    results: list[RequirementLine] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            results.append(RequirementLine(name="", specifier="", original=raw_line, is_empty=True))
            continue
        if stripped.startswith("#"):
            results.append(RequirementLine(name="", specifier="", original=raw_line, is_comment=True))
            continue
        if stripped.startswith("-") or stripped.startswith("--"):
            results.append(RequirementLine(name="", specifier=stripped, original=raw_line))
            continue
        cleaned = _EXTRAS_RE.sub("", stripped)
        match = _REQUIREMENT_RE.match(cleaned.strip())
        if match:
            name = match.group("name")
            specifier = (match.group("specifier") or "").strip()
            results.append(RequirementLine(name=name, specifier=specifier, original=raw_line))
        else:
            results.append(RequirementLine(name="", specifier="", original=raw_line))
    return results


def merge_requirement_lists(
    *lists: Iterable[str],
    prefer_first: bool = True,
) -> list[str]:
    seen: dict[str, RequirementLine] = {}
    for req_list in lists:
        parsed = parse_requirements_text("\n".join(req_list) if isinstance(req_list, (list, tuple)) else req_list)
        for req in parsed:
            if req.is_comment or req.is_empty or not req.name:
                continue
            norm = _normalize_name(req.name)
            if norm in seen:
                existing = seen[norm]
                if prefer_first:
                    continue
                if req.specifier and not existing.specifier:
                    seen[norm] = req
            else:
                seen[norm] = req
    return [req.original for req in seen.values()]


def exclude_requirement_names(
    requirements: list[str],
    exclude_names: Iterable[str],
) -> list[str]:
    exclude_set = {_normalize_name(n) for n in exclude_names}
    result: list[str] = []
    for req_text in requirements:
        parsed = parse_requirements_text(req_text)
        for req in parsed:
            if req.is_comment or req.is_empty:
                result.append(req_text)
                break
            if not req.name:
                result.append(req_text)
                break
            if _normalize_name(req.name) not in exclude_set:
                result.append(req_text)
            break
    return result