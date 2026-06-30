from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class ScanResult:
    safe: bool = True
    risks: list[dict[str, Any]] = field(default_factory=list)
    score: float = 1.0

    @property
    def risk_count(self) -> int:
        return len(self.risks)


class SkillScanner:

    DANGEROUS_PATTERNS = [
        (r"os\.system\(", "high", "System command execution"),
        (r"subprocess\.call\(.*shell\s*=\s*True", "high", "Shell injection"),
        (r"eval\(", "medium", "Dynamic code evaluation"),
        (r"exec\(", "medium", "Dynamic code execution"),
        (r"__import__\(", "medium", "Dynamic import"),
        (r"requests\.get\(.*http", "low", "HTTP request (potential data exfiltration)"),
        (r"socket\.", "medium", "Socket usage"),
        (r"open\(.*['\"]w", "low", "File write operation"),
    ]

    def scan_code(self, code: str) -> ScanResult:
        result = ScanResult()
        for pattern, severity, description in self.DANGEROUS_PATTERNS:
            matches = re.findall(pattern, code)
            if matches:
                result.risks.append({
                    "pattern": pattern,
                    "severity": severity,
                    "description": description,
                    "count": len(matches),
                })
                result.safe = False

        if result.risks:
            high_count = sum(1 for r in result.risks if r["severity"] == "high")
            result.score = max(0, 1.0 - high_count * 0.3 - len(result.risks) * 0.1)

        return result

    def scan_file(self, file_path: str) -> ScanResult:
        try:
            content = Path(file_path).read_text(encoding="utf-8", errors="replace")
            return self.scan_code(content)
        except Exception:
            return ScanResult(safe=False, risks=[{"error": "Cannot read file"}])

    def scan_directory(self, dir_path: str) -> list[dict[str, Any]]:
        results = []
        for py_file in Path(dir_path).rglob("*.py"):
            scan = self.scan_file(str(py_file))
            if not scan.safe:
                results.append({"file": str(py_file), "risks": scan.risks, "score": scan.score})
        return results


__all__ = ["SkillScanner", "ScanResult"]
