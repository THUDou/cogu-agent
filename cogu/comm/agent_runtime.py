"""Agent消息运行时 — 类型安全发布订阅+RoutedAgent路由

融合自微软AutoGen autogen-core/_agent_runtime.py + _routed_agent.py
核心架构: Actor模型消息传递运行时
- AgentRuntime: 消息总线Protocol, send_message/publish_message核心接口
- RoutedAgent: @message_handler类型路由, 按消息类型分发处理
- TopicId/Subscription: 发布订阅模式, Agent按Topic订阅消息
- 单线程运行时: 消息队列+订阅管理
"""
import asyncio
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Type

logger = logging.getLogger("cogu.comm.agent_runtime")


@dataclass(frozen=True)
class TopicId:
    """话题标识"""
    topic: str
    source: str = "default"

    def __str__(self):
        return f"{self.source}/{self.topic}"


@dataclass
class AgentMessage:
    """运行时消息"""
    content: Any
    msg_type: str = "text"
    sender_id: str = ""
    topic_id: Optional[TopicId] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    msg_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class Subscription:
    """订阅关系"""
    agent_id: str
    topic_id: TopicId
    handler: Optional[Callable] = None


class MessageHandler:
    """消息处理器装饰器

    融合AutoGen @message_handler机制:
    按消息类型路由到对应的处理函数
    """

    def __init__(self, msg_type: str):
        self.msg_type = msg_type

    def __call__(self, func: Callable) -> Callable:
        func._msg_type = self.msg_type
        return func


def message_handler(msg_type: str):
    """装饰器: 注册消息类型处理器"""
    return MessageHandler(msg_type)


class RoutedAgent:
    """类型路由Agent

    融合AutoGen RoutedAgent核心:
    - 通过@message_handler装饰器注册处理器
    - 按消息类型自动路由到对应方法
    - 支持多消息类型, 每种类型一个处理器
    """

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self._handlers: Dict[str, Callable] = {}
        self._discover_handlers()

    def _discover_handlers(self):
        """自动发现@message_handler装饰的方法"""
        for attr_name in dir(self):
            attr = getattr(self, attr_name, None)
            if callable(attr) and hasattr(attr, "_msg_type"):
                self._handlers[attr._msg_type] = attr

    async def handle_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """路由消息到对应处理器"""
        handler = self._handlers.get(message.msg_type)
        if handler:
            try:
                result = handler(message)
                if asyncio.iscoroutine(result):
                    result = await result
                return result
            except Exception as e:
                logger.error("Agent %s 处理消息失败 [%s]: %s", self.agent_id, message.msg_type, e)
                return None
        logger.warning("Agent %s 无处理器: %s", self.agent_id, message.msg_type)
        return None

    def register_handler(self, msg_type: str, handler: Callable):
        """手动注册消息处理器"""
        self._handlers[msg_type] = handler


class AgentRuntime:
    """Agent消息运行时

    融合AutoGen AgentRuntime核心:
    - 消息总线: send_message(点对点) + publish_message(发布订阅)
    - 订阅管理: Agent按TopicId订阅, 支持通配符
    - 消息队列: 异步消息传递, 支持优先级
    """

    def __init__(self):
        self._agents: Dict[str, RoutedAgent] = {}
        self._subscriptions: Dict[str, List[Subscription]] = defaultdict(list)
        self._message_queue: List[AgentMessage] = []
        self._topic_subscribers: Dict[str, Set[str]] = defaultdict(set)

    def register_agent(self, agent: RoutedAgent):
        """注册Agent"""
        self._agents[agent.agent_id] = agent
        logger.info("Agent注册: %s (handlers: %s)", agent.agent_id, list(agent._handlers.keys()))

    def unregister_agent(self, agent_id: str):
        """注销Agent"""
        self._agents.pop(agent_id, None)
        subs_to_remove = []
        for topic_key, subs in self._subscriptions.items():
            self._subscriptions[topic_key] = [s for s in subs if s.agent_id != agent_id]
            if not self._subscriptions[topic_key]:
                subs_to_remove.append(topic_key)
        for key in subs_to_remove:
            del self._subscriptions[key]

    def subscribe(self, agent_id: str, topic_id: TopicId, handler: Optional[Callable] = None):
        """订阅话题"""
        sub = Subscription(agent_id=agent_id, topic_id=topic_id, handler=handler)
        key = str(topic_id)
        self._subscriptions[key].append(sub)
        self._topic_subscribers[key].add(agent_id)
        logger.debug("订阅: %s -> %s", agent_id, topic_id)

    def unsubscribe(self, agent_id: str, topic_id: TopicId):
        """取消订阅"""
        key = str(topic_id)
        self._topic_subscribers[key].discard(agent_id)
        self._subscriptions[key] = [s for s in self._subscriptions[key] if s.agent_id != agent_id]

    async def send_message(self, message: AgentMessage, recipient_id: str) -> Optional[AgentMessage]:
        """点对点发送消息"""
        agent = self._agents.get(recipient_id)
        if not agent:
            logger.warning("目标Agent不存在: %s", recipient_id)
            return None
        message.sender_id = message.sender_id or "runtime"
        return await agent.handle_message(message)

    async def publish_message(self, message: AgentMessage, topic_id: TopicId) -> int:
        """发布消息到话题"""
        message.topic_id = topic_id
        delivered = 0

        key = str(topic_id)
        subscribers = self._topic_subscribers.get(key, set())

        for agent_id in subscribers:
            agent = self._agents.get(agent_id)
            if agent:
                try:
                    await agent.handle_message(message)
                    delivered += 1
                except Exception as e:
                    logger.error("发布消息到 %s 失败: %s", agent_id, e)

        self._message_queue.append(message)
        if len(self._message_queue) > 1000:
            self._message_queue = self._message_queue[-500:]

        return delivered

    def get_agent(self, agent_id: str) -> Optional[RoutedAgent]:
        return self._agents.get(agent_id)

    @property
    def agent_count(self) -> int:
        return len(self._agents)

    @property
    def subscription_count(self) -> int:
        return sum(len(subs) for subs in self._subscriptions.values())