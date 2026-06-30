"""小模型适配层 — 推理参数优化 + NoTool/FinishTool双出口

融合自KwaiAgents kwaiagents/agents/kagent.py + kwaiagents/tools/commons.py + kwaiagents/llms/clients.py
核心能力:
- 步数限制: 小模型推理能力有限, 限制最大步数防止死循环
- 简化Schema: 减少工具参数复杂度, 降低小模型理解负担
- NoTool/FinishTool: 双出口机制, 无合适工具时优雅退出, 任务完成时主动终止
- 推理参数优化: temperature/top_p/max_tokens针对小模型调优
"""
import json
import logging
from typing import Any, Dict, List, Optional

from cogu.local_model.json_fixer import JSONFixer
from cogu.local_model.prompt_truncator import PromptTruncator

logger = logging.getLogger("cogu.local_model.small_model_adapter")

NO_TOOL_RESULT = {"action": "no_tool", "reason": "No suitable tool found for this query"}

FINISH_TOOL_RESULT = {"action": "task_complete", "reason": ""}


class NoTool:
    """无合适工具时的出口

    当小模型判断当前查询无法匹配任何可用工具时,
    返回此结果而非强行调用不相关工具
    """
    name = "do_nothing"
    description = "Do nothing when no suitable tool is available"

    def __call__(self):
        return NO_TOOL_RESULT


class FinishTool:
    """任务完成出口

    当小模型判断任务已完成, 不需要继续调用工具时,
    返回此结果终止推理循环
    """
    name = "task_complete"
    description = "Indicate task completion without further tool calls"

    def __init__(self, reason: str = ""):
        self.reason = reason

    def __call__(self):
        result = dict(FINISH_TOOL_RESULT)
        result["reason"] = self.reason
        return result


class SmallModelAdapter:
    """小模型适配层

    为Qwen3.5-4.6B等小模型提供推理优化:
    - 简化工具Schema(减少参数数量和嵌套层级)
    - 限制最大推理步数
    - NoTool/FinishTool双出口防死循环
    - 推理参数自动调优
    """

    SMALL_MODEL_CONFIGS = {
        "qwen3.5-4.6b": {
            "max_steps": 8,
            "temperature": 0.1,
            "top_p": 0.85,
            "max_tokens": 2048,
            "simplify_schema": True,
            "max_tool_params": 5,
        },
        "pangu-1.39b": {
            "max_steps": 5,
            "temperature": 0.2,
            "top_p": 0.80,
            "max_tokens": 1024,
            "simplify_schema": True,
            "max_tool_params": 3,
        },
        "default": {
            "max_steps": 10,
            "temperature": 0.0,
            "top_p": 0.9,
            "max_tokens": 4096,
            "simplify_schema": False,
            "max_tool_params": 10,
        },
    }

    def __init__(
        self,
        model_name: str = "qwen3.5-4.6b",
        max_tokens: Optional[int] = None,
        tokenizer=None,
    ):
        self.model_name = model_name
        config = self.SMALL_MODEL_CONFIGS.get(
            model_name, self.SMALL_MODEL_CONFIGS["default"]
        )
        self.max_steps = config["max_steps"]
        self.temperature = config["temperature"]
        self.top_p = config["top_p"]
        self.max_tokens = max_tokens or config["max_tokens"]
        self.simplify_schema = config["simplify_schema"]
        self.max_tool_params = config["max_tool_params"]

        self.json_fixer = JSONFixer()
        self.prompt_truncator = PromptTruncator(
            tokenizer=tokenizer,
            max_tokens=self.max_tokens,
        )
        self.no_tool = NoTool()
        self.finish_tool = FinishTool()

    def simplify_tool_schema(self, tools: List[Dict]) -> List[Dict]:
        """简化工具Schema, 降低小模型理解负担

        - 限制参数数量
        - 移除description中的冗余信息
        - 简化嵌套结构
        """
        if not self.simplify_schema:
            return tools

        simplified = []
        for tool in tools:
            func = tool.get("function", tool)
            params = func.get("parameters", {})

            props = params.get("properties", {})
            if len(props) > self.max_tool_params:
                required = set(params.get("required", []))
                kept = {}
                for k, v in props.items():
                    if k in required or len(kept) < self.max_tool_params:
                        kept[k] = v
                params = dict(params)
                params["properties"] = kept
                params["required"] = [r for r in params.get("required", []) if r in kept]

            simplified_tool = {
                "name": func.get("name", ""),
                "description": func.get("description", "")[:200],
                "parameters": params,
            }
            simplified.append({"type": "function", "function": simplified_tool})

        simplified.append({
            "type": "function",
            "function": {
                "name": "do_nothing",
                "description": "Do nothing when no suitable tool is available",
                "parameters": {"type": "object", "properties": {}},
            },
        })
        simplified.append({
            "type": "function",
            "function": {
                "name": "task_complete",
                "description": "Indicate task completion",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reason": {"type": "string", "description": "Reason for completion"},
                    },
                },
            },
        })

        return simplified

    def parse_tool_call(self, text: str) -> Optional[Dict]:
        """容错解析工具调用

        使用JSONFixer处理小模型输出的格式错误
        """
        return self.json_fixer.safe_parse(text)

    def should_stop(self, step: int, tool_call: Optional[Dict]) -> bool:
        """判断是否应停止推理

        - 达到max_steps
        - 调用了do_nothing
        - 调用了task_complete
        """
        if step >= self.max_steps:
            logger.warning("达到最大步数 %d, 强制停止", self.max_steps)
            return True

        if tool_call is None:
            return False

        name = tool_call.get("name", "")
        if name == "do_nothing":
            logger.info("NoTool出口: 无合适工具")
            return True
        if name == "task_complete":
            logger.info("FinishTool出口: 任务完成")
            return True

        return False

    def get_inference_params(self) -> Dict[str, Any]:
        """获取优化后的推理参数"""
        return {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
        }

    def truncate_prompt(self, prompt: str, memory: Optional[str] = None) -> str:
        """截断prompt到小模型可处理的长度"""
        return self.prompt_truncator.truncate(prompt, memory)