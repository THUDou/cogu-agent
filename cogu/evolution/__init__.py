"""
COGU Evolution — 自进化系统
融合 Hermes Self-Evolution + LoongFlow MAP-Elites + X-OmniClaw Memory Evolution
+ openJiuwen agent_evolving Trajectory
+ Agent0 Curriculum/CoEvolution/ADPO + Youtu-Agent Training-Free GRPO + OpenSkill Verifier
基于源码: EvoMaster playground.py/evolution/ + Yantu-Agent practice/ + CognitiveKernel-Pro
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
from cogu.evolution.curriculum import Curriculum, AdaptiveCurriculum, FixedCurriculum, CurriculumTask, DifficultyLevel
from cogu.evolution.practice import PracticeBank, PracticeRunner, PracticeTask, PracticeResult, ExperienceUpdater, Experience
from cogu.evolution.coevolution import CoEvolutionEngine, ExecutorAgent, EvolutionMetrics
from cogu.evolution.adpo import ADPOTrainer, PreferencePair, ADPOConfig
from cogu.evolution.grpo import TokenPriorBank, GuidedSampler, GRPOConfig
from cogu.evolution.verifier import VirtualVerifier, LeakageBarrier, VerificationResult

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
    "Curriculum",
    "AdaptiveCurriculum",
    "FixedCurriculum",
    "CurriculumTask",
    "DifficultyLevel",
    "PracticeBank",
    "PracticeRunner",
    "PracticeTask",
    "PracticeResult",
    "ExperienceUpdater",
    "Experience",
    "CoEvolutionEngine",
    "ExecutorAgent",
    "EvolutionMetrics",
    "ADPOTrainer",
    "PreferencePair",
    "ADPOConfig",
    "TokenPriorBank",
    "GuidedSampler",
    "GRPOConfig",
    "VirtualVerifier",
    "LeakageBarrier",
    "VerificationResult",
]
