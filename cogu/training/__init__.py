"""COGU Training — 训练适配层
基于源码: SEAgent src/r1-v/ (GRPO训练GUI Agent)
         + SEAgent src/distill_r1/ (R1蒸馏管线)
         + Agent0 executor_train/verl_tool/ (Ray PPO训练)
"""
from cogu.evolution.curriculum import Curriculum, AdaptiveCurriculum, CurriculumTask, DifficultyLevel

__all__ = ["Curriculum", "AdaptiveCurriculum", "CurriculumTask", "DifficultyLevel"]
