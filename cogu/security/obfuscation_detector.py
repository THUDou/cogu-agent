"""命令混淆检测器

融合自蚂蚁agent-aegis src/command-obfuscation.ts
检测14类命令混淆模式:
- base64管道执行, hex管道执行, printf管道执行
- eval解码执行, 命令替换解码执行
- 进程替换远程执行, source进程替换
- shell heredoc执行, 八进制转义, 十六进制转义
- Python/Node/PowerShell编码执行
- curl管道shell, 变量展开混淆
- 不可见Unicode字符检测
"""
import re
import logging
from dataclasses import dataclass
from typing import List

logger = logging.getLogger("cogu.security.obfuscation_detector")

MAX_COMMAND_CHARS = 10_000

INVISIBLE_UNICODE_CODE_POINTS = frozenset({
    0x00ad, 0x034f, 0x061c,
    0x180b, 0x180c, 0x180d, 0x180e, 0x180f,
    0x200b, 0x200c, 0x200d, 0x200e, 0x200f,
    0x202a, 0x202b, 0x202c, 0x202d, 0x202e,
    0x2060, 0x2061, 0x2062, 0x2063, 0x2064,
    0x2066, 0x2067, 0x2068, 0x2069,
    0xfeff,
})

OBFUSCATION_PATTERNS = [
    ("base64-pipe-exec", re.compile(
        r"base64\s+(?:-d|--decode)\b.*\|\s*(?:sh|bash|zsh|dash|ksh|fish)\b", re.I
    )),
    ("hex-pipe-exec", re.compile(
        r"xxd\s+-r\b.*\|\s*(?:sh|bash|zsh|dash|ksh|fish)\b", re.I
    )),
    ("printf-pipe-exec", re.compile(
        r"printf\s+.*\\x[0-9a-f]{2}.*\|\s*(?:sh|bash|zsh|dash|ksh|fish)\b", re.I
    )),
    ("eval-decode", re.compile(
        r"eval\s+.*(?:base64|xxd|printf|decode|frombase64string)", re.I
    )),
    ("command-substitution-decode-exec", re.compile(
        r"(?:sh|bash|zsh|dash|ksh|fish)\s+-c\s+[\"'][^\"']*\$\([^)]*"
        r"(?:base64\s+(?:-d|--decode)|xxd\s+-r|printf\s+.*\\x[0-9a-f]{2})"
        r"[^)]*\)[^\"']*[\"']", re.I
    )),
    ("process-substitution-remote-exec", re.compile(
        r"(?:sh|bash|zsh|dash|ksh|fish)\s+<\(\s*(?:curl|wget)\b", re.I
    )),
    ("source-process-substitution-remote", re.compile(
        r"(?:^|[;&\s])(?:source|\.)\s+<\(\s*(?:curl|wget)\b", re.I
    )),
    ("shell-heredoc-exec", re.compile(
        r"(?:sh|bash|zsh|dash|ksh|fish)\s+<<-?\s*['\" ]?[a-zA-Z_][\w-]*['\" ]?", re.I
    )),
    ("octal-escape", re.compile(
        r"\$'(?:[^']*\\[0-7]{3}){2,}"
    )),
    ("hex-escape", re.compile(
        r"\$'(?:[^']*\\x[0-9a-fA-F]{2}){2,}"
    )),
    ("python-exec-encoded", re.compile(
        r"python[23]?\s+-[ec]\s+.*(?:base64|b64decode|decode|exec|eval)", re.I
    )),
    ("node-exec-encoded", re.compile(
        r"node\s+-[ec]\s+.*(?:buffer\.from\s*\(.*(?:base64|hex)|atob\s*\(|eval\s*\(|new\s+function)", re.I
    )),
    ("powershell-encoded", re.compile(
        r"(?:pwsh|powershell)\b.*\s-(?:enc|encodedcommand)\s+[A-Za-z0-9+/=_-]{8,}", re.I
    )),
    ("curl-pipe-shell", re.compile(
        r"(?:curl|wget)\s+.*\|\s*(?:sh|bash|zsh|dash|ksh|fish)\b", re.I
    )),
    ("var-expansion-obfuscation", re.compile(
        r"(?:[a-zA-Z_]\w{0,2}=[^;\s]+\s*;\s*){2,}[^$]*\$(?:[a-zA-Z_]|\{[a-zA-Z_])"
    )),
]


@dataclass
class ObfuscationResult:
    detected: bool
    matched_patterns: List[str]


def _strip_invisible_unicode(command: str) -> str:
    """移除不可见Unicode字符"""
    return "".join(
        char for char in command
        if char not in INVISIBLE_UNICODE_CODE_POINTS
        or not (cp := ord(char)) or cp not in INVISIBLE_UNICODE_CODE_POINTS
    )


class ObfuscationDetector:
    """命令混淆检测器

    融合蚂蚁agent-aegis核心检测能力:
    - 14类混淆模式正则匹配
    - 不可见Unicode字符剥离
    - NFKC Unicode正规化
    - 命令长度限制
    """

    def detect(self, command: str) -> ObfuscationResult:
        """检测命令中的混淆模式

        Args:
            command: 待检测的命令字符串

        Returns:
            ObfuscationResult(detected, matched_patterns)
        """
        if not command or not command.strip():
            return ObfuscationResult(detected=False, matched_patterns=[])

        if len(command) > MAX_COMMAND_CHARS:
            return ObfuscationResult(detected=True, matched_patterns=["command-too-long"])

        normalized = _strip_invisible_unicode(command)
        try:
            normalized = normalized.normalize("NFKC")
        except (AttributeError, UnicodeError):
            pass

        matched = []
        for pattern_id, pattern_regex in OBFUSCATION_PATTERNS:
            if pattern_regex.search(normalized):
                matched.append(pattern_id)

        return ObfuscationResult(
            detected=len(matched) > 0,
            matched_patterns=matched,
        )