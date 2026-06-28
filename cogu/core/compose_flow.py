"""Spec→Plan→Build三阶段工作流 — 参考MiMo-Code Compose模式

结构化开发工作流:
  - SPEC: 需求规格化，明确目标和约束
  - PLAN: 拆解任务，生成执行计划
  - BUILD: 按计划逐步构建
  - REVIEW: 审查构建结果
  - VERIFY: 验证最终产出
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ComposePhase(str, Enum):
    SPEC = "spec"
    PLAN = "plan"
    BUILD = "build"
    REVIEW = "review"
    VERIFY = "verify"


@dataclass
class PhaseResult:
    """阶段执行结果"""
    phase: ComposePhase = ComposePhase.SPEC
    status: str = "pending"
    output: dict[str, Any] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "phase": self.phase.value,
            "status": self.status,
            "output": self.output,
            "artifacts": self.artifacts,
            "errors": self.errors,
            "elapsed_seconds": self.elapsed_seconds,
            "metadata": self.metadata,
        }


@dataclass
class ComposeResult:
    """Compose工作流完整结果"""
    spec: Optional[PhaseResult] = None
    plan: Optional[PhaseResult] = None
    build: Optional[PhaseResult] = None
    review: Optional[PhaseResult] = None
    verify: Optional[PhaseResult] = None
    overall_status: str = "pending"
    total_elapsed: float = 0.0

    def to_dict(self) -> dict:
        return {
            "spec": self.spec.to_dict() if self.spec else None,
            "plan": self.plan.to_dict() if self.plan else None,
            "build": self.build.to_dict() if self.build else None,
            "review": self.review.to_dict() if self.review else None,
            "verify": self.verify.to_dict() if self.verify else None,
            "overall_status": self.overall_status,
            "total_elapsed": self.total_elapsed,
        }


@dataclass
class TaskNode:
    """计划中的任务节点"""
    task_id: str = ""
    title: str = ""
    description: str = ""
    dependencies: list[str] = field(default_factory=list)
    status: str = "pending"
    artifact: str = ""
    order: int = 0


class ComposeFlow:
    """Specs驱动的结构化开发工作流

    参考MiMo-Code Compose模式:
      - Spec阶段: 将自然语言需求转为结构化规格
      - Plan阶段: 拆解为有序任务节点
      - Build阶段: 逐步执行任务
      - Review阶段: 审查产出质量
      - Verify阶段: 验证最终结果
    """

    def __init__(self, llm_client: Any = None, workspace: str = ""):
        self.llm = llm_client
        self.workspace = workspace
        self._phase_history: list[PhaseResult] = []

    async def run(self, spec: str, workspace: str = "") -> ComposeResult:
        """执行完整Compose工作流

        Args:
            spec: 自然语言需求描述
            workspace: 工作空间路径

        Returns:
            完整工作流结果
        """
        ws = workspace or self.workspace
        result = ComposeResult()
        start = time.time()

        spec_result = await self._spec_phase(spec)
        result.spec = spec_result
        if spec_result.status != "completed":
            result.overall_status = "failed_at_spec"
            result.total_elapsed = time.time() - start
            return result

        plan_result = await self._plan_phase(spec_result.output)
        result.plan = plan_result
        if plan_result.status != "completed":
            result.overall_status = "failed_at_plan"
            result.total_elapsed = time.time() - start
            return result

        build_result = await self._build_phase(plan_result.output)
        result.build = build_result
        if build_result.status != "completed":
            result.overall_status = "failed_at_build"
            result.total_elapsed = time.time() - start
            return result

        review_result = await self._review_phase(build_result.output)
        result.review = review_result

        verify_result = await self._verify_phase(review_result.output)
        result.verify = verify_result

        result.overall_status = "completed" if verify_result.status == "completed" else "completed_with_issues"
        result.total_elapsed = time.time() - start
        return result

    async def _spec_phase(self, spec: str) -> PhaseResult:
        """Spec阶段 — 需求规格化"""
        start = time.time()
        result = PhaseResult(phase=ComposePhase.SPEC)

        try:
            if self.llm:
                prompt = (
                    "将以下需求转为结构化规格，包含:\n"
                    "1. 目标(objective)\n"
                    "2. 约束(constraints)\n"
                    "3. 验收标准(acceptance_criteria)\n"
                    "4. 技术栈(tech_stack)\n"
                    f"\n需求:\n{spec}\n\n"
                    "返回JSON格式。"
                )
                try:
                    if hasattr(self.llm, 'complete'):
                        import asyncio
                        if asyncio.iscoroutinefunction(self.llm.complete):
                            response = await self.llm.complete(prompt)
                        else:
                            response = self.llm.complete(prompt)
                    else:
                        response = str(self.llm(prompt))
                    spec_data = self._parse_json_response(response)
                except Exception as e:
                    spec_data = {"raw_spec": spec, "parse_error": str(e)}
            else:
                spec_data = {
                    "objective": spec,
                    "constraints": [],
                    "acceptance_criteria": [f"满足需求: {spec[:100]}"],
                    "tech_stack": [],
                }

            result.output = spec_data
            result.status = "completed"
        except Exception as e:
            result.status = "failed"
            result.errors.append(str(e))
        finally:
            result.elapsed_seconds = time.time() - start
            self._phase_history.append(result)
        return result

    async def _plan_phase(self, spec_result: dict) -> PhaseResult:
        """Plan阶段 — 任务拆解"""
        start = time.time()
        result = PhaseResult(phase=ComposePhase.PLAN)

        try:
            if self.llm:
                prompt = (
                    "根据以下规格，拆解为有序任务列表，每个任务包含:\n"
                    "1. task_id\n2. title\n3. description\n4. dependencies\n5. order\n"
                    f"\n规格:\n{json.dumps(spec_result, ensure_ascii=False)[:3000]}\n\n"
                    "返回JSON数组。"
                )
                try:
                    if hasattr(self.llm, 'complete'):
                        import asyncio
                        if asyncio.iscoroutinefunction(self.llm.complete):
                            response = await self.llm.complete(prompt)
                        else:
                            response = self.llm.complete(prompt)
                    else:
                        response = str(self.llm(prompt))
                    tasks_data = self._parse_json_response(response)
                except Exception as e:
                    tasks_data = {"tasks": [], "parse_error": str(e)}
            else:
                tasks_data = {
                    "tasks": [
                        {
                            "task_id": "task_1",
                            "title": spec_result.get("objective", "实现需求")[:50],
                            "description": spec_result.get("objective", ""),
                            "dependencies": [],
                            "order": 1,
                        }
                    ]
                }

            if isinstance(tasks_data, list):
                tasks = tasks_data
            else:
                tasks = tasks_data.get("tasks", [])

            task_nodes = []
            for t in tasks:
                node = TaskNode(
                    task_id=t.get("task_id", f"task_{len(task_nodes)+1}"),
                    title=t.get("title", ""),
                    description=t.get("description", ""),
                    dependencies=t.get("dependencies", []),
                    order=t.get("order", len(task_nodes) + 1),
                )
                task_nodes.append(node)

            result.output = {
                "tasks": [t.__dict__ for t in task_nodes],
                "total_tasks": len(task_nodes),
            }
            result.status = "completed"
        except Exception as e:
            result.status = "failed"
            result.errors.append(str(e))
        finally:
            result.elapsed_seconds = time.time() - start
            self._phase_history.append(result)
        return result

    async def _build_phase(self, plan_result: dict) -> PhaseResult:
        """Build阶段 — 按计划逐步构建"""
        start = time.time()
        result = PhaseResult(phase=ComposePhase.BUILD)

        try:
            tasks = plan_result.get("tasks", [])
            completed_tasks: list[dict] = []
            build_errors: list[str] = []

            for task_data in tasks:
                task_result = {
                    "task_id": task_data.get("task_id", ""),
                    "title": task_data.get("title", ""),
                    "status": "completed",
                    "output": f"执行: {task_data.get('title', '')}",
                }

                if self.llm:
                    try:
                        prompt = f"执行以下任务:\n{json.dumps(task_data, ensure_ascii=False)}"
                        if hasattr(self.llm, 'complete'):
                            import asyncio
                            if asyncio.iscoroutinefunction(self.llm.complete):
                                response = await self.llm.complete(prompt)
                            else:
                                response = self.llm.complete(prompt)
                        else:
                            response = str(self.llm(prompt))
                        task_result["output"] = str(response)[:500]
                    except Exception as e:
                        task_result["status"] = "failed"
                        task_result["error"] = str(e)
                        build_errors.append(f"{task_data.get('task_id', '')}: {e}")

                completed_tasks.append(task_result)

            result.output = {
                "completed_tasks": completed_tasks,
                "total": len(tasks),
                "succeeded": sum(1 for t in completed_tasks if t["status"] == "completed"),
                "failed": sum(1 for t in completed_tasks if t["status"] == "failed"),
            }
            result.errors = build_errors
            result.status = "completed" if not build_errors else "completed_with_errors"
        except Exception as e:
            result.status = "failed"
            result.errors.append(str(e))
        finally:
            result.elapsed_seconds = time.time() - start
            self._phase_history.append(result)
        return result

    async def _review_phase(self, build_result: dict) -> PhaseResult:
        """Review阶段 — 审查构建结果"""
        start = time.time()
        result = PhaseResult(phase=ComposePhase.REVIEW)

        try:
            review_output = {
                "quality_score": 0.0,
                "issues": [],
                "suggestions": [],
            }

            if self.llm:
                prompt = (
                    "审查以下构建结果，评估质量并给出改进建议:\n"
                    f"{json.dumps(build_result, ensure_ascii=False)[:3000]}\n\n"
                    "返回JSON，包含quality_score(0-1), issues, suggestions。"
                )
                try:
                    if hasattr(self.llm, 'complete'):
                        import asyncio
                        if asyncio.iscoroutinefunction(self.llm.complete):
                            response = await self.llm.complete(prompt)
                        else:
                            response = self.llm.complete(prompt)
                    else:
                        response = str(self.llm(prompt))
                    review_output = self._parse_json_response(response)
                except Exception:
                    pass
            else:
                succeeded = build_result.get("succeeded", 0)
                total = build_result.get("total", 1)
                review_output["quality_score"] = succeeded / max(total, 1)
                if build_result.get("failed", 0) > 0:
                    review_output["issues"].append(f"{build_result['failed']}个任务失败")

            result.output = review_output
            result.status = "completed"
        except Exception as e:
            result.status = "failed"
            result.errors.append(str(e))
        finally:
            result.elapsed_seconds = time.time() - start
            self._phase_history.append(result)
        return result

    async def _verify_phase(self, review_result: dict) -> PhaseResult:
        """Verify阶段 — 验证最终产出"""
        start = time.time()
        result = PhaseResult(phase=ComposePhase.VERIFY)

        try:
            verify_output = {
                "verified": True,
                "acceptance_results": [],
                "overall_pass": True,
            }

            quality_score = review_result.get("quality_score", 0.0)
            issues = review_result.get("issues", [])

            verify_output["acceptance_results"] = [
                {"criterion": "质量分数", "passed": quality_score >= 0.6, "value": quality_score},
                {"criterion": "无阻塞性问题", "passed": len(issues) == 0, "value": len(issues)},
            ]

            verify_output["overall_pass"] = all(r["passed"] for r in verify_output["acceptance_results"])
            verify_output["verified"] = True

            result.output = verify_output
            result.status = "completed" if verify_output["overall_pass"] else "completed_with_issues"
        except Exception as e:
            result.status = "failed"
            result.errors.append(str(e))
        finally:
            result.elapsed_seconds = time.time() - start
            self._phase_history.append(result)
        return result

    @staticmethod
    def _parse_json_response(response: str) -> dict:
        """解析LLM返回的JSON"""
        text = response.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            import re
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            return {"raw_response": text}

    def get_phase_history(self, phase: Optional[ComposePhase] = None) -> list[PhaseResult]:
        """获取阶段执行历史"""
        if phase:
            return [r for r in self._phase_history if r.phase == phase]
        return self._phase_history


__all__ = [
    "ComposeFlow",
    "ComposePhase",
    "ComposeResult",
    "PhaseResult",
    "TaskNode",
]