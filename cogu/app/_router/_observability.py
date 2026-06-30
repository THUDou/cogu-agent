from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Optional

router = APIRouter(prefix="/api/observability", tags=["observability"])


@router.get("/traces")
async def list_traces(trace_id: str = "", span_type: str = "",
                      limit: int = 100, offset: int = 0):
    from cogu.observability.span_collector import TracingContext
    ctx = TracingContext.get_instance()
    exporter = ctx.get_exporter()
    if not exporter:
        return {"spans": [], "total": 0}
    spans = exporter.query_traces(trace_id=trace_id, span_type=span_type,
                                   limit=limit, offset=offset)
    return {"spans": spans, "total": len(spans)}


@router.get("/traces/{trace_id}")
async def get_trace_tree(trace_id: str):
    from cogu.observability.span_collector import TracingContext
    ctx = TracingContext.get_instance()
    exporter = ctx.get_exporter()
    if not exporter:
        return {"trace_id": trace_id, "spans": [], "total": 0}
    return exporter.query_trace_tree(trace_id)


@router.get("/metrics/summary")
async def get_metrics_summary(hours: int = 24):
    from cogu.observability.span_collector import TracingContext
    ctx = TracingContext.get_instance()
    exporter = ctx.get_exporter()
    if not exporter:
        return {"metrics": {}}
    return {"metrics": exporter.get_metrics_summary(hours)}


@router.get("/metrics/query")
async def query_metrics(name: str = "", agg: str = "avg",
                        since_hours: float = 24):
    from cogu.observability.metrics import MetricRegistry, Aggregation
    reg = MetricRegistry.get_instance()
    since = __import__("time").time() - since_hours * 3600
    try:
        aggregation = Aggregation(agg)
    except ValueError:
        aggregation = Aggregation.AVG
    if name:
        value = reg.query(name, aggregation, since=since)
        return {"name": name, "agg": agg, "value": value}
    results = reg.query_all(name_prefix="", agg=aggregation, since=since)
    return {"metrics": results, "agg": agg}


@router.get("/metrics/model")
async def get_model_metrics(model: str = "", since_hours: float = 1):
    from cogu.observability.metrics import ModelMetrics
    since = __import__("time").time() - since_hours * 3600
    mm = ModelMetrics()
    return {
        "qpm": mm.get_qpm(model, since),
        "success_ratio": mm.get_success_ratio(model, since),
        "avg_latency_s": mm.get_avg_latency(model, since),
        "ttft_avg_s": mm.get_ttft(model, since=since),
    }


@router.get("/metrics/service")
async def get_service_metrics(service: str = "", since_hours: float = 1):
    from cogu.observability.metrics import ServiceMetrics
    since = __import__("time").time() - since_hours * 3600
    sm = ServiceMetrics()
    return {
        "qps": sm.get_qps(service, since),
        "success_ratio": sm.get_success_ratio(service, since),
    }


@router.get("/metrics/tool")
async def get_tool_metrics(tool_name: str = "", since_hours: float = 1):
    from cogu.observability.metrics import ToolMetrics
    since = __import__("time").time() - since_hours * 3600
    tm = ToolMetrics()
    return {
        "avg_latency_s": tm.get_avg_latency(tool_name, since),
        "success_ratio": tm.get_success_ratio(tool_name, since),
    }


@router.get("/metrics/agent")
async def get_agent_metrics(agent: str = "", since_hours: float = 1):
    from cogu.observability.metrics import AgentMetrics
    since = __import__("time").time() - since_hours * 3600
    am = AgentMetrics()
    return {
        "step_avg_duration_s": am.get_step_avg(agent, since=since),
        "step_avg_model_s": am.get_step_avg(agent, step_type="model", since=since),
        "step_avg_tool_s": am.get_step_avg(agent, step_type="tool", since=since),
    }


@router.get("/pipeline/stats")
async def get_pipeline_stats():
    from cogu.observability.span_collector import TracingContext
    ctx = TracingContext.get_instance()
    if ctx._pipeline:
        return ctx._pipeline.stats
    return {"received": 0, "processed": 0, "exported": 0, "errors": 0}
