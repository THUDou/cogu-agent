"""COGU Experiment — 实验评估框架
基于源码: EvoMaster core/playground.py (BasePlayground 1891行)
         + EvoMaster core/exp.py (BaseExp + extract_agent_response)
"""
from cogu.experiment.playground import (
    BasePlayground, ExperimentRunner, TaskInstance, StepRecord, ExperimentResult,
)

__all__ = [
    "BasePlayground", "ExperimentRunner", "TaskInstance", "StepRecord", "ExperimentResult",
]
