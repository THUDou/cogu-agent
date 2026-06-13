import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SemanticSegment:
    role: str = ""
    content: str = ""
    token_count: int = 0
    is_user_boundary: bool = False
    summary: str = ""


@dataclass
class CompressionResult:
    original_tokens: int = 0
    compressed_tokens: int = 0
    ratio: float = 0.0
    segments_removed: int = 0
    summaries_injected: int = 0


class SemanticCompressor:
    def __init__(self, llm_client=None, max_tokens: int = 8000, keep_recent: int = 3):
        self.llm = llm_client
        self.max_tokens = max_tokens
        self.keep_recent = keep_recent

    def compress(self, messages: list[dict]) -> tuple[list[dict], CompressionResult]:
        result = CompressionResult()
        total = sum(self._estimate_tokens(m.get("content", "")) for m in messages)
        result.original_tokens = total

        if total <= self.max_tokens:
            result.compressed_tokens = total
            result.ratio = 1.0
            return messages, result

        segments = self._segment_by_user_boundary(messages)
        recent = segments[-self.keep_recent:] if len(segments) > self.keep_recent else segments
        to_compress = segments[:-self.keep_recent] if len(segments) > self.keep_recent else []

        compressed_segments = []
        for seg in to_compress:
            if seg.role == "system":
                compressed_segments.append(seg)
            elif seg.role == "user":
                compressed_segments.append(seg)
            else:
                summary = self._summarize_segment(seg)
                if summary:
                    compressed_segments.append(SemanticSegment(
                        role="user",
                        content=f"[Execution Summary]\n{summary}",
                        token_count=self._estimate_tokens(summary),
                        summary=summary,
                    ))
                    result.summaries_injected += 1
                else:
                    compressed_segments.append(seg)

        all_segments = compressed_segments + recent
        output = [self._segment_to_message(s) for s in all_segments]
        result.compressed_tokens = sum(s.token_count for s in all_segments)
        result.ratio = result.compressed_tokens / max(result.original_tokens, 1)
        result.segments_removed = len(to_compress) - result.summaries_injected
        return output, result

    def _segment_by_user_boundary(self, messages: list[dict]) -> list[SemanticSegment]:
        segments = []
        current = SemanticSegment()
        for msg in messages:
            role = msg.get("role", "assistant")
            content = msg.get("content", "")
            tokens = self._estimate_tokens(content)

            if role == "user":
                if current.content:
                    segments.append(current)
                current = SemanticSegment(
                    role=role,
                    content=content,
                    token_count=tokens,
                    is_user_boundary=True,
                )
            elif role == "system":
                if current.content:
                    segments.append(current)
                current = SemanticSegment(role=role, content=content, token_count=tokens)
                segments.append(current)
                current = SemanticSegment()
            else:
                if not current.content:
                    current = SemanticSegment(role=role, content=content, token_count=tokens)
                elif current.role == role:
                    current.content += f"\n{content}"
                    current.token_count += tokens
                else:
                    segments.append(current)
                    current = SemanticSegment(role=role, content=content, token_count=tokens)

        if current.content:
            segments.append(current)
        return segments

    def _summarize_segment(self, segment: SemanticSegment) -> str:
        if self.llm:
            return self._llm_summarize(segment)
        return self._rule_summarize(segment)

    def _llm_summarize(self, segment: SemanticSegment) -> str:
        prompt = (
            "Summarize this assistant execution segment concisely.\n"
            "Preserve: key actions taken, tool calls, results, and decisions.\n"
            "Drop: verbose output, repeated content, formatting.\n\n"
            f"Segment:\n{segment.content[:4000]}\n\n"
            "Concise summary:"
        )
        try:
            return self.llm.complete(prompt)
        except Exception:
            return self._rule_summarize(segment)

    def _rule_summarize(self, segment: SemanticSegment) -> str:
        lines = segment.content.split('\n')
        important = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if any(kw in stripped.lower() for kw in ['error', 'success', 'result', 'completed', 'tool', 'executed']):
                important.append(stripped)
            elif stripped.startswith(('```', '>>>', 'def ', 'class ', 'import ')):
                important.append(stripped[:100])
        if not important:
            important = [lines[0][:200]] if lines else ["[empty]"]
        return " | ".join(important[:5])

    def _segment_to_message(self, seg: SemanticSegment) -> dict:
        return {"role": seg.role, "content": seg.content}

    def _estimate_tokens(self, text: str) -> int:
        if not text:
            return 0
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_chars = len(text) - chinese_chars
        return chinese_chars + (english_chars + 3) // 4
