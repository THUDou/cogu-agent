"""
COGU Evolution — 自进化系统
融合 Hermes Self-Evolution (DSPy+GEPA反射式进化) + LoongFlow MAP-Elites + X-OmniClaw Memory Evolution
+ openJiuwen agent_evolving Trajectory 数据模型
"""

from cogu.evolution.config import EvolutionConfig
from cogu.evolution.fitness import FitnessEvaluator
from cogu.evolution.constraints import ConstraintValidator
from cogu.evolution.dataset_builder import DatasetBuilder
from cogu.evolution.trace_analyzer import TraceAnalyzer
from cogu.evolution.trajectory import (
    Trajectory,
    TrajectoryStep,
    TrajectoryRegistry,
    LLMCallDetail,
    ToolCallDetail,
    StepKind,
)

__all__ = [
    "EvolutionConfig",
    "FitnessEvaluator",
    "ConstraintValidator",
    "DatasetBuilder",
    "TraceAnalyzer",
    "Trajectory",
    "TrajectoryStep",
    "TrajectoryRegistry",
    "LLMCallDetail",
    "ToolCallDetail",
    "StepKind",
]
