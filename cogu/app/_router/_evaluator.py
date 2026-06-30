from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Optional

router = APIRouter(prefix="/api/evaluators", tags=["evaluators"])

_builtin_evaluators = None


def _get_builtin_evaluators():
    global _builtin_evaluators
    if _builtin_evaluators is None:
        from cogu.experiment.evaluator import (
            EvaluatorConfig, EvaluatorType, BUILTIN_PROMPT_TEMPLATES,
        )
        _builtin_evaluators = []
        for name in BUILTIN_PROMPT_TEMPLATES:
            _builtin_evaluators.append(EvaluatorConfig(
                evaluator_id=f"builtin_{name}", name=name,
                evaluator_type=EvaluatorType.PROMPT,
            ).to_dict())
    return _builtin_evaluators


class EvaluatorCreateRequest(BaseModel):
    name: str = ""
    evaluator_type: str = "prompt"
    content: str = ""
    min_score: float = 0.0
    max_score: float = 1.0
    pass_threshold: float = 0.6


class ExperimentRunRequest(BaseModel):
    evaluator_ids: list[str] = []
    items: list[dict[str, Any]] = []
    name: str = ""


@router.get("/builtins")
async def list_builtin_evaluators():
    return {"evaluators": _get_builtin_evaluators(), "total": len(_get_builtin_evaluators())}


@router.post("")
async def create_evaluator(req: EvaluatorCreateRequest):
    from cogu.experiment.evaluator import EvaluatorConfig, EvaluatorType
    config = EvaluatorConfig(
        evaluator_id=f"custom_{req.name}",
        name=req.name,
        evaluator_type=EvaluatorType(req.evaluator_type),
        content=req.content,
        min_score=req.min_score,
        max_score=req.max_score,
        pass_threshold=req.pass_threshold,
    )
    return config.to_dict()


@router.post("/run")
async def run_experiment(req: ExperimentRunRequest):
    from cogu.experiment.evaluator import (
        EvaluatorConfig, EvaluatorType, EvalItem, ExperimentConfig, ExperimentRunner,
    )
    evaluator_configs = []
    for eid in req.evaluator_ids:
        evaluator_configs.append(EvaluatorConfig(
            evaluator_id=eid, name=eid,
            evaluator_type=EvaluatorType.PROMPT,
        ))
    items = []
    for i, item_data in enumerate(req.items):
        items.append(EvalItem(
            item_id=item_data.get("item_id", str(i)),
            input=item_data.get("input", ""),
            output=item_data.get("output", ""),
            reference=item_data.get("reference", ""),
        ))
    config = ExperimentConfig(
        name=req.name or "experiment",
        evaluator_configs=evaluator_configs,
        items=items,
    )
    runner = ExperimentRunner(config)
    result = runner.run()
    return result.to_dict()
