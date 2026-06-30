"""节点自注册工厂 + Layer中间件

融合自Dify api/core/workflow/node_factory.py + workflow_entry.py
核心架构:
- NodeFactory: 节点自注册+版本化解析, register_nodes()自动发现
- Layer中间件: 可挂载到执行引擎的拦截层(限流/配额/可观测)
- VariablePool: 节点间通过变量选择器传递数据
"""
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

logger = logging.getLogger("cogu.core.node_factory")


@dataclass
class VariableSelector:
    """变量选择器 — 节点间数据传递引用"""
    node_id: str
    key: str

    def to_tuple(self) -> Tuple[str, str]:
        return (self.node_id, self.key)


class VariablePool:
    """变量池 — 节点间数据传递

    融合Dify VariablePool:
    节点通过VariableSelector引用其他节点的输出
    """

    def __init__(self):
        self._pool: Dict[Tuple[str, str], Any] = {}

    def set(self, node_id: str, key: str, value: Any):
        self._pool[(node_id, key)] = value

    def get(self, selector: VariableSelector) -> Optional[Any]:
        return self._pool.get(selector.to_tuple())

    def get_by_path(self, node_id: str, key: str) -> Optional[Any]:
        return self._pool.get((node_id, key))

    def remove(self, node_id: str):
        keys_to_remove = [k for k in self._pool if k[0] == node_id]
        for k in keys_to_remove:
            del self._pool[k]

    def clear(self):
        self._pool.clear()

    @property
    def size(self) -> int:
        return len(self._pool)


class Layer:
    """Layer中间件基类

    融合Dify Layer机制:
    可挂载到执行引擎的拦截层
    """

    def before_execute(self, node_id: str, context: Dict[str, Any]) -> bool:
        return True

    def after_execute(self, node_id: str, context: Dict[str, Any], result: Any):
        pass

    def on_error(self, node_id: str, context: Dict[str, Any], error: Exception):
        pass


class RateLimitLayer(Layer):
    """限流Layer"""

    def __init__(self, max_calls_per_second: int = 10):
        self.max_calls = max_calls_per_second
        self._timestamps: List[float] = []

    def before_execute(self, node_id: str, context: Dict[str, Any]) -> bool:
        now = time.time()
        self._timestamps = [t for t in self._timestamps if now - t < 1.0]
        if len(self._timestamps) >= self.max_calls:
            logger.warning("限流: node '%s' 被拒绝", node_id)
            return False
        self._timestamps.append(now)
        return True


class QuotaLayer(Layer):
    """配额Layer"""

    def __init__(self, max_total_calls: int = 1000):
        self.max_total = max_total_calls
        self._call_count = 0

    def before_execute(self, node_id: str, context: Dict[str, Any]) -> bool:
        if self._call_count >= self.max_total:
            logger.warning("配额耗尽: node '%s' 被拒绝", node_id)
            return False
        self._call_count += 1
        return True


class ObservabilityLayer(Layer):
    """可观测Layer"""

    def __init__(self):
        self._metrics: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"calls": 0, "errors": 0, "total_ms": 0.0})

    def before_execute(self, node_id: str, context: Dict[str, Any]) -> bool:
        context["_start_time"] = time.time()
        return True

    def after_execute(self, node_id: str, context: Dict[str, Any], result: Any):
        start = context.pop("_start_time", time.time())
        duration = (time.time() - start) * 1000
        self._metrics[node_id]["calls"] += 1
        self._metrics[node_id]["total_ms"] += duration

    def on_error(self, node_id: str, context: Dict[str, Any], error: Exception):
        self._metrics[node_id]["errors"] += 1

    def get_metrics(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._metrics)


@dataclass
class NodeTypeRegistration:
    """节点类型注册信息"""
    node_type: str
    version: str = "1.0"
    node_class: Optional[Type] = None
    factory_fn: Optional[Callable] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class NodeFactory:
    """节点自注册工厂

    融合Dify NodeFactory核心:
    - register_nodes(): 注册节点类型
    - resolve(): 按类型+版本解析节点类
    - 自动发现: 扫描已注册的节点类型
    """

    def __init__(self):
        self._registrations: Dict[str, NodeTypeRegistration] = {}

    def register(self, node_type: str, version: str = "1.0",
                 node_class: Optional[Type] = None,
                 factory_fn: Optional[Callable] = None,
                 metadata: Optional[Dict] = None):
        """注册节点类型"""
        key = f"{node_type}:v{version}"
        self._registrations[key] = NodeTypeRegistration(
            node_type=node_type,
            version=version,
            node_class=node_class,
            factory_fn=factory_fn,
            metadata=metadata or {},
        )
        logger.debug("节点注册: %s", key)

    def resolve(self, node_type: str, version: str = "1.0") -> Optional[Callable]:
        """解析节点类型"""
        key = f"{node_type}:v{version}"
        reg = self._registrations.get(key)
        if not reg:
            reg = self._registrations.get(f"{node_type}:v1.0")

        if reg:
            if reg.factory_fn:
                return reg.factory_fn
            if reg.node_class:
                return reg.node_class
        return None

    def list_types(self) -> List[str]:
        return list(set(r.node_type for r in self._registrations.values()))

    def get_registration(self, node_type: str, version: str = "1.0") -> Optional[NodeTypeRegistration]:
        key = f"{node_type}:v{version}"
        return self._registrations.get(key)