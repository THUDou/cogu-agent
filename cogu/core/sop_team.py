"""SOP驱动Team — Role观察思考行动 + ActionNode结构化输出

融合自MetaGPT metagpt/roles/role.py + metagpt/actions/action.py + metagpt/team.py
核心架构: SOP驱动的多智能体协作
- SOPRole: observe→think→act循环, 消息订阅/发布, cause_by路由
- ActionNode: 结构化输出模板, 支持JSON/Markdown/代码生成
- SOPTeam: hire/invest/run, SOP编排与序列化
"""
import json
import logging
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger("cogu.core.sop_team")


@dataclass
class SOPMessage:
    """SOP消息 — cause_by/send_to路由"""
    msg_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    cause_by: str = ""
    send_to: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    sender: str = ""


class ActionNode:
    """结构化输出节点

    融合MetaGPT ActionNode:
    定义输出格式, 指导LLM生成结构化内容
    """

    def __init__(
        self,
        key: str = "",
        expected_type: type = str,
        instruction: str = "",
        example: str = "",
        children: Optional[List["ActionNode"]] = None,
    ):
        self.key = key
        self.expected_type = expected_type
        self.instruction = instruction
        self.example = example
        self.children = children or []

    def compile_to(self, format_type: str = "json") -> str:
        """编译为prompt指令"""
        if format_type == "json":
            return self._compile_json()
        elif format_type == "markdown":
            return self._compile_markdown()
        return self._compile_json()

    def _compile_json(self) -> str:
        schema = self._build_schema()
        return f"Output a valid JSON object with the following schema:\n{json.dumps(schema, indent=2, ensure_ascii=False)}"

    def _compile_markdown(self) -> str:
        lines = [f"## {self.key}" if self.key else ""]
        if self.instruction:
            lines.append(self.instruction)
        for child in self.children:
            lines.append(f"### {child.key}")
            if child.instruction:
                lines.append(child.instruction)
            if child.example:
                lines.append(f"Example: {child.example}")
        return "\n".join(lines)

    def _build_schema(self) -> Dict:
        schema = {}
        if self.children:
            for child in self.children:
                type_name = child.expected_type.__name__
                schema[child.key] = {"type": type_name}
                if child.instruction:
                    schema[child.key]["description"] = child.instruction
                if child.example:
                    schema[child.key]["example"] = child.example
        else:
            type_name = self.expected_type.__name__
            schema[self.key] = {"type": type_name}
            if self.instruction:
                schema[self.key]["description"] = self.instruction
        return schema


class SOPRole:
    """SOP角色 — observe→think→act循环

    融合MetaGPT Role核心:
    - _observe: 从消息队列获取相关消息
    - _think: 决定下一步行动
    - _act: 执行行动, 产生新消息
    - cause_by路由: 消息按cause_by字段分发到对应Action
    """

    def __init__(
        self,
        name: str = "",
        profile: str = "",
        goal: str = "",
        constraints: str = "",
        actions: Optional[Dict[str, Callable]] = None,
        watch: Optional[Set[str]] = None,
        llm_client=None,
    ):
        self.name = name
        self.profile = profile
        self.goal = goal
        self.constraints = constraints
        self._actions = actions or {}
        self._watch = watch or set()
        self._message_queue: deque = deque(maxlen=100)
        self._state: Dict[str, Any] = {}
        self._history: List[SOPMessage] = []
        self.llm_client = llm_client

    def put_message(self, message: SOPMessage):
        """接收消息"""
        if not self._watch or message.cause_by in self._watch:
            self._message_queue.append(message)

    def _observe(self) -> List[SOPMessage]:
        """观察: 获取待处理消息"""
        messages = list(self._message_queue)
        self._message_queue.clear()
        return messages

    def _think(self, messages: List[SOPMessage]) -> Optional[str]:
        """思考: 决定下一步行动"""
        if not messages:
            return None
        latest = messages[-1]
        if latest.cause_by in self._actions:
            return latest.cause_by
        if self._actions:
            return next(iter(self._actions))
        return None

    def _act(self, action_key: str, messages: List[SOPMessage]) -> SOPMessage:
        """行动: 执行对应Action"""
        action = self._actions.get(action_key)
        if not action:
            return SOPMessage(content=f"No action for key: {action_key}", cause_by=action_key, sender=self.name)

        context = "\n".join(m.content for m in messages)
        try:
            result = action(context, self._state)
        except Exception as e:
            result = f"Action failed: {e}"

        msg = SOPMessage(
            content=str(result),
            cause_by=f"{self.name}.{action_key}",
            sender=self.name,
        )
        self._history.append(msg)
        return msg

    async def run(self) -> Optional[SOPMessage]:
        """执行一轮 observe→think→act"""
        messages = self._observe()
        action_key = self._think(messages)
        if action_key is None:
            return None
        return self._act(action_key, messages)

    def build_system_prompt(self) -> str:
        parts = []
        if self.profile:
            parts.append(f"You are {self.profile}.")
        if self.goal:
            parts.append(f"Goal: {self.goal}")
        if self.constraints:
            parts.append(f"Constraints: {self.constraints}")
        return "\n\n".join(parts)


class SOPTeam:
    """SOP驱动Team

    融合MetaGPT Team核心:
    - hire: 招募角色
    - invest: 注入资源
    - run: 执行SOP流程
    - 消息路由: cause_by→watch匹配
    """

    def __init__(self, llm_client=None):
        self._roles: Dict[str, SOPRole] = {}
        self._message_bus: deque = deque(maxlen=500)
        self._llm_client = llm_client
        self._history: List[SOPMessage] = []

    def hire(self, role: SOPRole):
        """招募角色"""
        if self._llm_client and not role.llm_client:
            role.llm_client = self._llm_client
        self._roles[role.name] = role
        logger.info("Team招募: %s (%s)", role.name, role.profile)

    def invest(self, idea: str) -> SOPMessage:
        """注入初始需求"""
        msg = SOPMessage(content=idea, cause_by="UserRequirement", sender="User")
        self._message_bus.append(msg)
        return msg

    def run(self, max_rounds: int = 10) -> List[SOPMessage]:
        """执行SOP流程"""
        all_messages = []

        for round_num in range(max_rounds):
            round_messages = list(self._message_bus)
            self._message_bus.clear()

            if not round_messages and round_num > 0:
                break

            new_messages = []
            for msg in round_messages:
                for role in self._roles.values():
                    role.put_message(msg)

            for role in self._roles.values():
                try:
                    result = role.run()
                    if result:
                        new_messages.append(result)
                except Exception as e:
                    logger.error("Role '%s' 执行失败: %s", role.name, e)

            for msg in new_messages:
                self._message_bus.append(msg)
                self._history.append(msg)
                all_messages.append(msg)

            if not new_messages:
                break

            logger.info("Round %d: %d messages produced", round_num + 1, len(new_messages))

        return all_messages

    def get_history(self) -> List[SOPMessage]:
        return list(self._history)