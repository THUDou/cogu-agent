"""Memory-Aware Prompt截断引擎

融合自KwaiAgents kwaiagents/agents/prompts.py
核心算法: tokenizer精确计数 + memory首尾保留策略
当prompt超过max_tokens时:
1. 如果memory在prompt中, 先保留memory首尾各半, 其余部分首尾截断
2. 如果memory不在prompt中, 整体首尾各半截断
"""
import logging
from typing import Optional

logger = logging.getLogger("cogu.local_model.prompt_truncator")


class PromptTruncator:
    """Memory-Aware Prompt截断器

    使用tokenizer精确计数, 优先保留memory内容,
    防止关键上下文在截断中丢失
    """

    def __init__(self, tokenizer=None, max_tokens: int = 4096):
        """
        Args:
            tokenizer: HuggingFace/自定义tokenizer, 需支持encode/decode方法
            max_tokens: 最大token数限制
        """
        self.tokenizer = tokenizer
        self.max_tokens = max_tokens

    def truncate(self, prompt: str, memory: Optional[str] = None) -> str:
        """截断prompt到max_tokens以内

        Args:
            prompt: 完整prompt文本
            memory: 记忆文本(如果存在, 优先保留首尾)

        Returns:
            截断后的prompt
        """
        if self.tokenizer is None:
            return self._char_level_truncate(prompt, memory)

        kwargs = dict(add_special_tokens=False)
        prompt_tokens = self.tokenizer.encode(prompt, **kwargs)

        if len(prompt_tokens) <= self.max_tokens:
            return prompt

        if memory is None or memory not in prompt:
            half = self.max_tokens // 2
            prompt_tokens = prompt_tokens[:half] + prompt_tokens[-half:]
        else:
            memory_tokens = self.tokenizer.encode(memory, add_special_tokens=False)
            sublst_len = len(memory_tokens)

            start_index = self._find_sublist(prompt_tokens, memory_tokens)

            if start_index is None:
                half = self.max_tokens // 2
                prompt_tokens = prompt_tokens[:half] + prompt_tokens[-half:]
            else:
                other_len = len(prompt_tokens) - sublst_len
                if self.max_tokens > other_len:
                    max_memory_len = self.max_tokens - other_len
                    memory_half = max_memory_len // 2
                    memory_tokens = memory_tokens[:memory_half] + memory_tokens[-memory_half:]
                    prompt_tokens = (
                        prompt_tokens[:start_index]
                        + memory_tokens
                        + prompt_tokens[start_index + sublst_len:]
                    )
                else:
                    half = self.max_tokens // 2
                    prompt_tokens = prompt_tokens[:half] + prompt_tokens[-half:]

        return self.tokenizer.decode(prompt_tokens, skip_special_tokens=True)

    @staticmethod
    def _find_sublist(tokens: list, sub_tokens: list) -> Optional[int]:
        """在token列表中查找子列表的起始位置"""
        sublst_len = len(sub_tokens)
        for i in range(len(tokens) - sublst_len + 1):
            if tokens[i:i + sublst_len] == sub_tokens:
                return i
        return None

    def _char_level_truncate(self, prompt: str, memory: Optional[str] = None) -> str:
        """字符级截断(无tokenizer时的回退方案)"""
        char_limit = self.max_tokens * 2
        if len(prompt) <= char_limit:
            return prompt

        if memory and memory in prompt:
            memory_len = len(memory)
            other_len = len(prompt) - memory_len
            if char_limit > other_len:
                max_memory_len = char_limit - other_len
                memory_half = max_memory_len // 2
                truncated_memory = memory[:memory_half] + memory[-memory_half:]
                prompt = prompt.replace(memory, truncated_memory, 1)
            else:
                half = char_limit // 2
                prompt = prompt[:half] + prompt[-half:]
        else:
            half = char_limit // 2
            prompt = prompt[:half] + prompt[-half:]

        return prompt

    def count_tokens(self, text: str) -> int:
        """计算文本的token数"""
        if self.tokenizer is None:
            return len(text) // 2
        return len(self.tokenizer.encode(text, add_special_tokens=False))