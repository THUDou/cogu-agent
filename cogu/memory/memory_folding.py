"""自主记忆折叠引擎

融合自小红书+人大DeepAgent src/prompts/prompts_deepagent.py
核心机制: fold_thought标记触发上下文压缩 + 推理重启
当推理历史过长/工具调用失败过多/需要改变方向时:
1. Agent输出 <fold_thought> 标记
2. 系统暂停推理, 总结当前交互历史和任务进度
3. 清除旧上下文, 以总结为起点开始新一轮推理

防止无限上下文膨胀, 同时保留关键任务进展
"""
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("cogu.memory.memory_folding")

FOLD_THOUGHT_MARKER = "<fold_thought>"
FOLD_SUMMARY_START = "<fold_summary>"
FOLD_SUMMARY_END = "</fold_summary>"


@dataclass
class FoldRecord:
    step: int
    summary: str
    tools_called: List[str] = field(default_factory=list)
    tools_failed: List[str] = field(default_factory=list)
    key_findings: List[str] = field(default_factory=list)


class MemoryFolding:
    """自主记忆折叠引擎

    融合DeepAgent核心能力:
    - fold_thought标记检测: 当Agent输出此标记时触发折叠
    - 上下文压缩: 将完整交互历史总结为紧凑摘要
    - 推理重启: 清除旧上下文, 以摘要为起点重新开始
    - 折叠历史: 保留所有折叠记录, 防止重复犯错
    """

    def __init__(
        self,
        max_context_tokens: int = 4096,
        max_folds: int = 5,
        llm_summarizer=None,
    ):
        self.max_context_tokens = max_context_tokens
        self.max_folds = max_folds
        self.llm_summarizer = llm_summarizer

        self.fold_history: List[FoldRecord] = []
        self.current_context: List[Dict] = []
        self.fold_count = 0

    def check_fold_request(self, text: str) -> bool:
        """检测Agent是否请求折叠"""
        return FOLD_THOUGHT_MARKER in text

    def fold(
        self,
        question: str,
        interaction_history: List[Dict],
        current_step: int = 0,
    ) -> Tuple[str, List[Dict]]:
        """执行记忆折叠

        Args:
            question: 原始问题/任务
            interaction_history: 完整交互历史
            current_step: 当前步数

        Returns:
            (summary, new_context) — 折叠摘要和新上下文
        """
        if self.fold_count >= self.max_folds:
            logger.warning("达到最大折叠次数 %d, 不再折叠", self.max_folds)
            return "", interaction_history

        self.fold_count += 1

        tools_called = self._extract_tools_called(interaction_history)
        tools_failed = self._extract_tools_failed(interaction_history)
        key_findings = self._extract_key_findings(interaction_history)

        if self.llm_summarizer:
            summary = self.llm_summarizer(question, self._history_to_text(interaction_history))
        else:
            summary = self._default_summarize(
                question, interaction_history, tools_called, tools_failed, key_findings
            )

        record = FoldRecord(
            step=current_step,
            summary=summary,
            tools_called=tools_called,
            tools_failed=tools_failed,
            key_findings=key_findings,
        )
        self.fold_history.append(record)

        new_context = self._build_post_fold_context(question, summary)

        logger.info(
            "记忆折叠 #%d: step=%d, tools=%d, failed=%d, findings=%d, summary_len=%d",
            self.fold_count, current_step,
            len(tools_called), len(tools_failed), len(key_findings),
            len(summary),
        )

        return summary, new_context

    def _default_summarize(
        self,
        question: str,
        history: List[Dict],
        tools_called: List[str],
        tools_failed: List[str],
        key_findings: List[str],
    ) -> str:
        """默认折叠摘要(无LLM时使用)"""
        parts = [f"原始任务: {question}"]

        if tools_called:
            parts.append(f"已调用工具: {', '.join(tools_called[-10:])}")
        if tools_failed:
            parts.append(f"失败工具: {', '.join(tools_failed[-5:])}")
        if key_findings:
            parts.append(f"关键发现: {'; '.join(key_findings[-5:])}")

        fold_summaries = [f.summary for f in self.fold_history]
        if fold_summaries:
            parts.append(f"之前折叠摘要: {'; '.join(fold_summaries[-2:])}")

        return "\n".join(parts)

    def _build_post_fold_context(self, question: str, summary: str) -> List[Dict]:
        """构建折叠后的新上下文"""
        return [
            {
                "role": "system",
                "content": (
                    f"以下是之前推理的折叠摘要。请基于此摘要继续推理, "
                    f"不要重复之前已尝试且失败的方法。\n\n"
                    f"{FOLD_SUMMARY_START}\n{summary}\n{FOLD_SUMMARY_END}"
                ),
            },
            {
                "role": "user",
                "content": question,
            },
        ]

    @staticmethod
    def _extract_tools_called(history: List[Dict]) -> List[str]:
        """提取已调用的工具列表"""
        tools = []
        for msg in history:
            content = msg.get("content", "")
            if isinstance(content, str):
                matches = re.findall(r'"name":\s*"(\w+)"', content)
                tools.extend(matches)
        return tools

    @staticmethod
    def _extract_tools_failed(history: List[Dict]) -> List[str]:
        """提取失败的工具调用"""
        failed = []
        for i, msg in enumerate(history):
            if msg.get("role") == "tool" and "error" in str(msg.get("content", "")).lower():
                if i > 0:
                    prev = history[i - 1].get("content", "")
                    matches = re.findall(r'"name":\s*"(\w+)"', str(prev))
                    failed.extend(matches)
        return failed

    @staticmethod
    def _extract_key_findings(history: List[Dict]) -> List[str]:
        """提取关键发现(简化版: 取工具结果的前100字符)"""
        findings = []
        for msg in history:
            if msg.get("role") == "tool":
                content = str(msg.get("content", ""))
                if content and len(content) > 10:
                    findings.append(content[:100])
        return findings

    @staticmethod
    def _history_to_text(history: List[Dict]) -> str:
        """将交互历史转为文本"""
        lines = []
        for msg in history:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(str(c) for c in content)
            lines.append(f"[{role}] {str(content)[:200]}")
        return "\n".join(lines)

    def get_fold_summary_for_prompt(self) -> str:
        """获取所有折叠摘要, 用于注入到prompt中"""
        if not self.fold_history:
            return ""
        parts = []
        for i, record in enumerate(self.fold_history, 1):
            parts.append(f"折叠#{i} (step={record.step}): {record.summary[:300]}")
        return "\n\n".join(parts)

    def reset(self):
        """重置折叠状态"""
        self.fold_history = []
        self.current_context = []
        self.fold_count = 0