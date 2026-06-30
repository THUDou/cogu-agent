"""GoalJudge — 独立目标完成度评估器

借鉴小米 MiMo-Code 的 Goal+Judge 机制，防止 Agent "乐观停止"：
Agent 声称完成但实际未达成目标时，GoalJudge 独立评估并决定是否继续循环。

核心流程：
1. Agent 检测到终止信号（声称目标达成）
2. GoalJudge 独立评估：目标 + 成功标准 + 对话摘要 + Agent声明
3. ACHIEVED → 真正终止；NOT_ACHIEVED/PARTIAL → 继续循环
4. 最多重试 max_judge_retries 次
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from cogu.api.client import DeepSeekClient
    from cogu.core.api_config import MultiProviderClient

logger = logging.getLogger(__name__)


class JudgeVerdict(Enum):
    ACHIEVED = "ACHIEVED"
    NOT_ACHIEVED = "NOT_ACHIEVED"
    PARTIAL = "PARTIAL"
    UNCLEAR = "UNCLEAR"


@dataclass
class GoalCondition:
    goal_text: str
    success_criteria: list[str] = field(default_factory=list)
    max_judge_retries: int = 3
    judge_model: str = "Qwen3.5-0.8B"


@dataclass
class JudgeResult:
    verdict: JudgeVerdict
    confidence: float = 0.0
    reasoning: str = ""
    missing_criteria: list[str] = field(default_factory=list)

    @property
    def is_achieved(self) -> bool:
        return self.verdict == JudgeVerdict.ACHIEVED and self.confidence >= 0.7

    @property
    def should_continue(self) -> bool:
        return self.verdict in (JudgeVerdict.NOT_ACHIEVED, JudgeVerdict.PARTIAL)

    def summary(self) -> str:
        lines = [
            f"[JUDGE] {self.verdict.value} (confidence={self.confidence:.2f})",
            f"  Reasoning: {self.reasoning[:300]}",
        ]
        if self.missing_criteria:
            lines.append("  Missing criteria:")
            for c in self.missing_criteria:
                lines.append(f"    - {c}")
        return "\n".join(lines)


_JUDGE_PROMPT_TEMPLATE = """你是一个目标完成度评估专家。你需要独立判断Agent是否真正完成了用户设定的目标。

## 目标
{goal_text}

## 成功标准
{success_criteria}

## Agent的最终声明
{agent_claim}

## 对话摘要
{conversation_summary}

## 评估要求
1. 逐条检查每个成功标准是否被满足
2. 不要仅凭Agent的声明判断，要基于实际对话内容
3. 如果Agent声称完成但对话中没有证据支持，判定为NOT_ACHIEVED
4. 给出你的判定：ACHIEVED / NOT_ACHIEVED / PARTIAL
5. 给出置信度（0.0-1.0）
6. 列出未达成的标准

请以JSON格式回复：
{{"verdict": "ACHIEVED|NOT_ACHIEVED|PARTIAL", "confidence": 0.0-1.0, "reasoning": "...", "missing_criteria": [...]}}"""


class GoalJudge:
    def __init__(
        self,
        client: Optional["DeepSeekClient"] = None,
        multi_provider: Optional["MultiProviderClient"] = None,
    ):
        self._client = client
        self._multi_provider = multi_provider
        self._local_llm = None

    def bind_client(self, client: "DeepSeekClient") -> None:
        self._client = client

    def bind_multi_provider(self, mp: "MultiProviderClient") -> None:
        self._multi_provider = mp

    async def judge(
        self,
        goal: GoalCondition,
        conversation: list[dict],
        agent_final_message: str,
    ) -> JudgeResult:
        conversation_summary = self.summarize_conversation(conversation)
        prompt = self.build_judge_prompt(
            goal=goal,
            conversation_summary=conversation_summary,
            agent_claim=agent_final_message,
        )

        judge_response = await self._call_judge_model(goal.judge_model, prompt)
        return self.extract_verdict(judge_response)

    def build_judge_prompt(
        self,
        goal: GoalCondition,
        conversation_summary: str,
        agent_claim: str,
    ) -> str:
        criteria_text = "\n".join(
            f"  {i+1}. {c}" for i, c in enumerate(goal.success_criteria)
        ) if goal.success_criteria else "  （无显式成功标准，根据目标描述判断）"

        return _JUDGE_PROMPT_TEMPLATE.format(
            goal_text=goal.goal_text,
            success_criteria=criteria_text,
            agent_claim=agent_claim[:3000],
            conversation_summary=conversation_summary[:4000],
        )

    def extract_verdict(self, judge_response: str) -> JudgeResult:
        json_match = re.search(
            r'\{[^{}]*"verdict"[^{}]*\}',
            judge_response,
            re.DOTALL,
        )
        if json_match:
            try:
                data = json.loads(json_match.group())
                verdict_str = data.get("verdict", "UNCLEAR").upper().strip()
                verdict = JudgeVerdict(verdict_str) if verdict_str in [v.value for v in JudgeVerdict] else JudgeVerdict.UNCLEAR
                confidence = float(data.get("confidence", 0.5))
                confidence = max(0.0, min(1.0, confidence))
                reasoning = data.get("reasoning", "")
                missing = data.get("missing_criteria", [])
                if isinstance(missing, str):
                    missing = [missing]
                return JudgeResult(
                    verdict=verdict,
                    confidence=confidence,
                    reasoning=reasoning,
                    missing_criteria=missing,
                )
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                logger.warning(f"goal_judge.parse_json_failed: {e}")

        verdict = JudgeVerdict.UNCLEAR
        resp_upper = judge_response.upper()
        if "ACHIEVED" in resp_upper and "NOT_ACHIEVED" not in resp_upper:
            verdict = JudgeVerdict.ACHIEVED
        elif "NOT_ACHIEVED" in resp_upper:
            verdict = JudgeVerdict.NOT_ACHIEVED
        elif "PARTIAL" in resp_upper:
            verdict = JudgeVerdict.PARTIAL

        return JudgeResult(
            verdict=verdict,
            confidence=0.3,
            reasoning=judge_response[:500],
            missing_criteria=[],
        )

    def summarize_conversation(
        self,
        messages: list[dict],
        max_tokens: int = 2000,
    ) -> str:
        if not messages:
            return "（无对话记录）"

        char_budget = max_tokens * 2

        system_msgs = []
        tool_msgs = []
        core_msgs = []
        for m in messages:
            role = m.get("role", "")
            content = str(m.get("content", ""))[:500]
            if role == "system":
                system_msgs.append(content[:200])
            elif role == "tool":
                tool_msgs.append(f"[Tool Result] {content[:200]}")
            elif role in ("user", "assistant"):
                core_msgs.append(f"[{role}] {content}")

        if not core_msgs:
            all_text = " | ".join(system_msgs + tool_msgs)
            return all_text[:char_budget]

        if len(core_msgs) <= 6:
            return "\n".join(core_msgs)[:char_budget]

        first_two = core_msgs[:2]
        last_three = core_msgs[-3:]
        middle_count = len(core_msgs) - 5
        middle_summary = f"  ... ({middle_count} messages omitted) ..."

        parts = first_two + [middle_summary] + last_three
        return "\n".join(parts)[:char_budget]

    async def _call_judge_model(self, model: str, prompt: str) -> str:
        local_response = await self._try_local_model(prompt)
        if local_response is not None:
            return local_response

        provider_response = await self._try_provider_model(model, prompt)
        if provider_response is not None:
            return provider_response

        client_response = await self._try_client_model(prompt)
        if client_response is not None:
            return client_response

        logger.error("goal_judge.all_models_failed: no LLM available for judging")
        return '{"verdict": "UNCLEAR", "confidence": 0.0, "reasoning": "No judge model available", "missing_criteria": []}'

    async def _try_local_model(self, prompt: str) -> Optional[str]:
        try:
            from llama_cpp import Llama
        except ImportError:
            return None

        if self._local_llm is None:
            try:
                import os
                model_path = os.environ.get(
                    "COGU_LOCAL_MODEL_PATH",
                    "",
                )
                if not model_path:
                    return None
                self._local_llm = Llama(
                    model_path=model_path,
                    n_ctx=4096,
                    n_threads=4,
                    verbose=False,
                )
            except Exception as e:
                logger.debug(f"goal_judge.local_model_init_failed: {e}")
                return None

        try:
            result = self._local_llm.create_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
                temperature=0.3,
            )
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            logger.debug(f"goal_judge.local_model_inference_failed: {e}")
            return None

    async def _try_provider_model(self, model: str, prompt: str) -> Optional[str]:
        if not self._multi_provider:
            return None
        try:
            client = self._multi_provider.get_client("local_qwen")
            if client is None:
                client = self._multi_provider.get_client("ollama")
            if client is None:
                for provider_name in ("qwen", "deepseek", "openai"):
                    client = self._multi_provider.get_client(provider_name)
                    if client is not None:
                        break
            if client is None:
                return None

            original_model = getattr(client, "model", "")
            if model:
                client.model = model

            try:
                response = await client.chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=1024,
                )
                return response.content
            finally:
                if original_model:
                    client.model = original_model
        except Exception as e:
            logger.debug(f"goal_judge.provider_model_failed: {e}")
            return None

    async def _try_client_model(self, prompt: str) -> Optional[str]:
        if not self._client:
            return None
        try:
            response = await self._client.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1024,
            )
            return response.content
        except Exception as e:
            logger.debug(f"goal_judge.client_model_failed: {e}")
            return None


__all__ = [
    "GoalJudge",
    "GoalCondition",
    "JudgeVerdict",
    "JudgeResult",
]