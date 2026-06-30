"""COGU Experiment — 实验评估框架
基于源码: EvoMaster core/playground.py (BasePlayground 1891行)
         + EvoMaster core/exp.py (BaseExp + extract_agent_response)
         + Coze Loop 评估器系统 (Prompt/Code/CustomRPC/Agent四种评估器)
         + Coze Loop Prompt Playground (模板引擎+变量系统+单步调试)
"""
from cogu.experiment.playground import (
    BasePlayground, ExperimentRunner, TaskInstance, StepRecord, ExperimentResult,
)
from cogu.experiment.evaluator import (
    EvaluatorType, ScoreMode, EvaluatorConfig, ScoreResult, EvalItem,
    BaseEvaluator, PromptEvaluator, CodeEvaluator, CustomRPCEvaluator, AgentEvaluator,
    ExperimentConfig, ExperimentResult as EvalExperimentResult, ExperimentRunner as EvalExperimentRunner,
    create_evaluator, BUILTIN_PROMPT_TEMPLATES,
)
from cogu.experiment.prompt_playground import (
    PromptPlayground, PromptDraft, DebugContext, DebugLog, DebugStep,
    TemplateFormatter, TemplateType, SnippetParser,
    VariableDef, VariableVal, VariableType, ToolDef, MessageDef,
)

__all__ = [
    "BasePlayground", "ExperimentRunner", "TaskInstance", "StepRecord", "ExperimentResult",
    "EvaluatorType", "ScoreMode", "EvaluatorConfig", "ScoreResult", "EvalItem",
    "BaseEvaluator", "PromptEvaluator", "CodeEvaluator", "CustomRPCEvaluator", "AgentEvaluator",
    "ExperimentConfig", "EvalExperimentResult", "EvalExperimentRunner",
    "create_evaluator", "BUILTIN_PROMPT_TEMPLATES",
    "PromptPlayground", "PromptDraft", "DebugContext", "DebugLog", "DebugStep",
    "TemplateFormatter", "TemplateType", "SnippetParser",
    "VariableDef", "VariableVal", "VariableType", "ToolDef", "MessageDef",
]
