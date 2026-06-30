"""统一Agent间通信协议

融合自明略Octo octo-lib/common/constant.go + octo-server/modules/bot_api/
核心能力:
- 统一频道类型(ChannelType): 个人/群组/客服/社区/话题/资讯
- 统一消息类型: 文本/图片/文件/卡片/系统/命令
- OBO代理(On-Behalf-Of): 代理克隆与扇出, 三重环路防护
- 事件队列: 长轮询机制, 支持Bot事件订阅
"""
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("cogu.comm.agent_protocol")


class ChannelType(IntEnum):
    NONE = 0
    PERSON = 1
    GROUP = 2
    CUSTOMER_SERVICE = 3
    COMMUNITY = 4
    COMMUNITY_TOPIC = 5
    INFO = 6


class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    CARD = "card"
    SYSTEM = "system"
    COMMAND = "command"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"


class MessageStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


@dataclass
class AgentMessage:
    """统一Agent消息格式"""
    msg_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    msg_type: MessageType = MessageType.TEXT
    channel_type: ChannelType = ChannelType.PERSON
    sender_id: str = ""
    receiver_id: str = ""
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    status: MessageStatus = MessageStatus.PENDING
    reply_to: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "msg_id": self.msg_id,
            "msg_type": self.msg_type.value,
            "channel_type": self.channel_type.value,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "status": self.status.value,
            "reply_to": self.reply_to,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        return cls(
            msg_id=data.get("msg_id", str(uuid.uuid4())),
            msg_type=MessageType(data.get("msg_type", "text")),
            channel_type=ChannelType(data.get("channel_type", 1)),
            sender_id=data.get("sender_id", ""),
            receiver_id=data.get("receiver_id", ""),
            content=data.get("content", ""),
            metadata=data.get("metadata", {}),
            timestamp=data.get("timestamp", time.time()),
            status=MessageStatus(data.get("status", "pending")),
            reply_to=data.get("reply_to"),
        )


@dataclass
class OBOProxy:
    """OBO代理(On-Behalf-Of)

    融合Octo obo_fanout.go核心机制:
    - 代理克隆: 一个Agent可代理多个身份
    - 扇出: 一条消息可同时发送给多个代理
    - 三重环路防护: 防止代理循环调用
    """
    principal_id: str
    proxy_id: str
    channel_type: ChannelType = ChannelType.PERSON
    max_depth: int = 3
    _call_stack: List[str] = field(default_factory=list)

    def can_act_on_behalf(self, target_id: str) -> bool:
        """检查是否可以代理目标身份(环路检测)"""
        if target_id == self.principal_id:
            return False
        if target_id in self._call_stack:
            return False
        if len(self._call_stack) >= self.max_depth:
            return False
        return True

    def push_call(self, target_id: str) -> bool:
        """压入调用栈(环路防护)"""
        if not self.can_act_on_behalf(target_id):
            return False
        self._call_stack.append(target_id)
        return True

    def pop_call(self):
        """弹出调用栈"""
        if self._call_stack:
            self._call_stack.pop()

    def create_message(self, content: str, msg_type: MessageType = MessageType.TEXT) -> AgentMessage:
        """创建代理消息"""
        return AgentMessage(
            msg_type=msg_type,
            channel_type=self.channel_type,
            sender_id=self.proxy_id,
            receiver_id=self.principal_id,
            content=content,
            metadata={"obo": True, "proxy_id": self.proxy_id},
        )


class EventQueue:
    """Agent事件队列

    融合Octo events.go长轮询机制:
    - 订阅/取消订阅事件
    - 长轮询获取事件
    - 事件过滤(按频道/类型)
    """

    def __init__(self, max_size: int = 1000, poll_timeout: float = 30.0):
        self.max_size = max_size
        self.poll_timeout = poll_timeout
        self._queue: List[AgentMessage] = []
        self._subscribers: Dict[str, Dict[str, Any]] = {}

    def publish(self, message: AgentMessage):
        """发布事件"""
        if len(self._queue) >= self.max_size:
            self._queue = self._queue[-self.max_size // 2:]

        self._queue.append(message)
        logger.debug("事件发布: %s -> %s [%s]", message.sender_id, message.receiver_id, message.msg_type.value)

    def subscribe(self, agent_id: str, filters: Optional[Dict[str, Any]] = None):
        """订阅事件"""
        self._subscribers[agent_id] = filters or {}

    def unsubscribe(self, agent_id: str):
        """取消订阅"""
        self._subscribers.pop(agent_id, None)

    def poll(self, agent_id: str, timeout: Optional[float] = None) -> List[AgentMessage]:
        """长轮询获取事件"""
        if agent_id not in self._subscribers:
            return []

        filters = self._subscribers[agent_id]
        results = []

        for msg in self._queue:
            if self._matches_filter(msg, agent_id, filters):
                results.append(msg)

        if results:
            self._queue = [m for m in self._queue if m not in results]

        return results

    @staticmethod
    def _matches_filter(msg: AgentMessage, agent_id: str, filters: Dict[str, Any]) -> bool:
        """检查消息是否匹配过滤条件"""
        if msg.receiver_id != agent_id and msg.receiver_id != "*":
            return False

        if "channel_type" in filters:
            if msg.channel_type.value != filters["channel_type"]:
                return False

        if "msg_type" in filters:
            if msg.msg_type.value != filters["msg_type"]:
                return False

        if "sender_id" in filters:
            if msg.sender_id != filters["sender_id"]:
                return False

        return True

    @property
    def size(self) -> int:
        return len(self._queue)


class AgentProtocol:
    """统一Agent间通信协议

    融合Octo核心通信能力:
    - 统一消息格式(AgentMessage)
    - 频道类型(ChannelType)
    - OBO代理与扇出
    - 事件队列长轮询
    """

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.event_queue = EventQueue()
        self._obo_proxies: Dict[str, OBOProxy] = {}
        self._message_handlers: Dict[MessageType, Callable] = {}

    def register_handler(self, msg_type: MessageType, handler: Callable):
        """注册消息处理器"""
        self._message_handlers[msg_type] = handler

    def send(self, message: AgentMessage) -> bool:
        """发送消息"""
        message.sender_id = self.agent_id
        message.status = MessageStatus.SENT

        if message.msg_type in self._message_handlers:
            try:
                self._message_handlers[message.msg_type](message)
            except Exception as e:
                logger.error("消息处理失败: %s", e)
                message.status = MessageStatus.FAILED
                return False

        self.event_queue.publish(message)
        return True

    def receive(self, timeout: Optional[float] = None) -> List[AgentMessage]:
        """接收消息"""
        return self.event_queue.poll(self.agent_id, timeout)

    def create_obo_proxy(
        self, principal_id: str, channel_type: ChannelType = ChannelType.PERSON
    ) -> OBOProxy:
        """创建OBO代理"""
        proxy_id = f"{self.agent_id}:obo:{principal_id}"
        proxy = OBOProxy(
            principal_id=principal_id,
            proxy_id=proxy_id,
            channel_type=channel_type,
        )
        self._obo_proxies[principal_id] = proxy
        return proxy

    def fanout(self, message: AgentMessage, target_ids: List[str]) -> Dict[str, bool]:
        """扇出: 将消息发送给多个目标"""
        results = {}
        for target_id in target_ids:
            msg = AgentMessage(
                msg_type=message.msg_type,
                channel_type=message.channel_type,
                sender_id=self.agent_id,
                receiver_id=target_id,
                content=message.content,
                metadata=message.metadata,
            )
            results[target_id] = self.send(msg)
        return results