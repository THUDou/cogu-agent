"""COGU Local Model — 小模型适配层

融合自快手KwaiAgents (7B模型经MAT超越GPT-3.5)
核心能力: Memory-Aware Prompt截断, JSON容错解析, 小模型推理参数优化
"""
from cogu.local_model.prompt_truncator import PromptTruncator
from cogu.local_model.json_fixer import JSONFixer
from cogu.local_model.small_model_adapter import SmallModelAdapter

__all__ = ["PromptTruncator", "JSONFixer", "SmallModelAdapter"]