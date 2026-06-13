"""
COGU Evolution — 自进化系统
融合 Hermes Self-Evolution (DSPy+GEPA反射式进化) + LoongFlow MAP-Elites + X-OmniClaw Memory Evolution
"""

from cogu.evolution.config import EvolutionConfig
from cogu.evolution.fitness import FitnessEvaluator
from cogu.evolution.constraints import ConstraintValidator
from cogu.evolution.dataset_builder import DatasetBuilder
from cogu.evolution.trace_analyzer import TraceAnalyzer

__all__ = [
    "EvolutionConfig",
    "FitnessEvaluator",
    "ConstraintValidator",
    "DatasetBuilder",
    "TraceAnalyzer",
]
