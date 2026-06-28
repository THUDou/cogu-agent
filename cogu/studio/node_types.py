"""节点类型体系 — 30+ 可视化工作流节点

参考: Coze Studio backend/domain/workflow/entity/node_meta.go
      30+ 节点类型: Entry/Exit/LLM/Plugin/SubWorkflow/CodeRunner/Selector/Loop/Batch/
      KnowledgeRetriever/KnowledgeIndexer/DatabaseCustomSQL/QuestionAnswer/IntentDetector/
      HTTPRequester/TextProcessor/VariableAssigner/VariableAggregator/JsonSerialization 等

每个节点类型定义: display_key, category, input/output schema, config schema
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional


class NodeCategory(Enum):
    INPUT_OUTPUT = "input_output"
    CORE = "core"
    LOGIC = "logic"
    DATA = "data"
    DATABASE = "database"
    UTILITIES = "utilities"
    CONVERSATION = "conversation"


@dataclass
class ParamSchema:
    key: str = ""
    label: str = ""
    type: str = "string"
    description: str = ""
    required: bool = False
    default: Any = None
    options: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {"key": self.key, "label": self.label, "type": self.type,
             "description": self.description, "required": self.required}
        if self.default is not None:
            d["default"] = self.default
        if self.options:
            d["options"] = self.options
        return d


@dataclass
class ConfigField:
    key: str = ""
    label: str = ""
    type: str = "string"
    description: str = ""
    required: bool = False
    default: Any = None
    options: list[dict] = field(default_factory=list)
    group: str = "basic"

    def to_dict(self) -> dict:
        d = {"key": self.key, "label": self.label, "type": self.type,
             "description": self.description, "required": self.required,
             "group": self.group}
        if self.default is not None:
            d["default"] = self.default
        if self.options:
            d["options"] = self.options
        return d


@dataclass
class NodeTypeDefinition:
    type: str = ""
    display_key: str = ""
    category: NodeCategory = NodeCategory.UTILITIES
    description: str = ""
    icon: str = ""
    color: str = "#666"
    is_composite: bool = False
    max_instances: int = -1
    input_params: list[ParamSchema] = field(default_factory=list)
    output_params: list[ParamSchema] = field(default_factory=list)
    config_fields: list[ConfigField] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "type": self.type, "display_key": self.display_key,
            "category": self.category.value, "description": self.description,
            "icon": self.icon, "color": self.color,
            "is_composite": self.is_composite,
            "max_instances": self.max_instances,
            "input_params": [p.to_dict() for p in self.input_params],
            "output_params": [p.to_dict() for p in self.output_params],
            "config_fields": [c.to_dict() for c in self.config_fields],
        }


NODE_TYPE_DEFINITIONS: dict[str, NodeTypeDefinition] = {}


def _register(definition: NodeTypeDefinition) -> NodeTypeDefinition:
    NODE_TYPE_DEFINITIONS[definition.type] = definition
    return definition


_register(NodeTypeDefinition(
    type="entry", display_key="Start", category=NodeCategory.INPUT_OUTPUT,
    description="工作流起始节点，定义输入参数",
    icon="play", color="#52c41a", max_instances=1,
    output_params=[
        ParamSchema(key="query", label="用户输入", type="string", description="用户查询内容"),
    ],
))

_register(NodeTypeDefinition(
    type="exit", display_key="End", category=NodeCategory.INPUT_OUTPUT,
    description="工作流结束节点，定义输出结果",
    icon="stop", color="#ff4d4f", max_instances=1,
    input_params=[
        ParamSchema(key="output", label="输出结果", type="string", description="工作流最终输出"),
    ],
))

_register(NodeTypeDefinition(
    type="llm", display_key="LLM", category=NodeCategory.CORE,
    description="大模型调用节点，支持 Function Calling 和 ReAct",
    icon="robot", color="#1677ff",
    input_params=[
        ParamSchema(key="prompt", label="提示词", type="string", required=True),
        ParamSchema(key="system_prompt", label="系统提示词", type="string"),
        ParamSchema(key="context", label="上下文", type="array"),
    ],
    output_params=[
        ParamSchema(key="text", label="模型输出", type="string"),
        ParamSchema(key="tool_calls", label="工具调用", type="array"),
    ],
    config_fields=[
        ConfigField(key="model", label="模型", type="string", required=True, default="qwen3.5-4.6b",
                    options=[{"label": "Qwen3.5-4.6B", "value": "qwen3.5-4.6b"},
                             {"label": "Pangu-1.39B", "value": "pangu-1.39b"}]),
        ConfigField(key="temperature", label="温度", type="float", default=0.7, group="advanced"),
        ConfigField(key="max_tokens", label="最大Token", type="integer", default=4096, group="advanced"),
        ConfigField(key="enable_fc", label="启用FC", type="boolean", default=False, group="advanced"),
        ConfigField(key="enable_react", label="ReAct模式", type="boolean", default=False, group="advanced"),
        ConfigField(key="output_format", label="输出格式", type="string", default="text",
                    options=[{"label": "文本", "value": "text"},
                             {"label": "Markdown", "value": "markdown"},
                             {"label": "JSON", "value": "json"}], group="advanced"),
    ],
))

_register(NodeTypeDefinition(
    type="plugin", display_key="API", category=NodeCategory.CORE,
    description="插件/API调用节点，基于OpenAPI 3.0规范",
    icon="api", color="#722ed1",
    input_params=[
        ParamSchema(key="plugin_id", label="插件ID", type="string", required=True),
        ParamSchema(key="tool_id", label="工具ID", type="string", required=True),
    ],
    output_params=[
        ParamSchema(key="response", label="API响应", type="object"),
    ],
    config_fields=[
        ConfigField(key="plugin_version", label="插件版本", type="string"),
        ConfigField(key="timeout", label="超时(秒)", type="integer", default=30),
        ConfigField(key="retry_count", label="重试次数", type="integer", default=0),
    ],
))

_register(NodeTypeDefinition(
    type="sub_workflow", display_key="Workflow", category=NodeCategory.CORE,
    description="子工作流调用，支持工作流嵌套组合",
    icon="branch", color="#13c2c2",
    input_params=[
        ParamSchema(key="workflow_id", label="工作流ID", type="string", required=True),
    ],
    output_params=[
        ParamSchema(key="output", label="子工作流输出", type="object"),
    ],
))

_register(NodeTypeDefinition(
    type="code_runner", display_key="Code", category=NodeCategory.LOGIC,
    description="代码执行节点，支持Python沙箱运行",
    icon="code", color="#fa8c16",
    input_params=[
        ParamSchema(key="code", label="代码", type="string", required=True),
        ParamSchema(key="variables", label="输入变量", type="object"),
    ],
    output_params=[
        ParamSchema(key="result", label="执行结果", type="object"),
        ParamSchema(key="stdout", label="标准输出", type="string"),
    ],
    config_fields=[
        ConfigField(key="language", label="语言", type="string", default="python",
                    options=[{"label": "Python", "value": "python"},
                             {"label": "JavaScript", "value": "javascript"}]),
        ConfigField(key="timeout", label="超时(秒)", type="integer", default=60),
    ],
))

_register(NodeTypeDefinition(
    type="selector", display_key="If", category=NodeCategory.LOGIC,
    description="条件分支节点，根据条件选择不同路径",
    icon="fork", color="#eb2f96",
    input_params=[
        ParamSchema(key="condition", label="条件表达式", type="string", required=True),
    ],
    output_params=[
        ParamSchema(key="true_branch", label="True分支", type="any"),
        ParamSchema(key="false_branch", label="False分支", type="any"),
    ],
))

_register(NodeTypeDefinition(
    type="loop", display_key="Loop", category=NodeCategory.LOGIC,
    description="循环节点，支持迭代执行子流程",
    icon="reload", color="#fa541c", is_composite=True,
    input_params=[
        ParamSchema(key="items", label="迭代列表", type="array", required=True),
    ],
    output_params=[
        ParamSchema(key="results", label="迭代结果", type="array"),
    ],
    config_fields=[
        ConfigField(key="max_iterations", label="最大迭代", type="integer", default=100),
        ConfigField(key="break_condition", label="中断条件", type="string"),
    ],
))

_register(NodeTypeDefinition(
    type="batch", display_key="Batch", category=NodeCategory.LOGIC,
    description="批处理节点，并行处理数据批次",
    icon="thunderbolt", color="#f5222d", is_composite=True,
    input_params=[
        ParamSchema(key="items", label="批处理数据", type="array", required=True),
    ],
    output_params=[
        ParamSchema(key="results", label="批处理结果", type="array"),
    ],
    config_fields=[
        ConfigField(key="batch_size", label="批次大小", type="integer", default=10),
        ConfigField(key="max_concurrency", label="最大并发", type="integer", default=5),
    ],
))

_register(NodeTypeDefinition(
    type="knowledge_retriever", display_key="Dataset", category=NodeCategory.DATA,
    description="知识库检索节点，支持向量/全文/混合检索",
    icon="search", color="#2f54eb",
    input_params=[
        ParamSchema(key="query", label="查询", type="string", required=True),
        ParamSchema(key="knowledge_id", label="知识库ID", type="string", required=True),
    ],
    output_params=[
        ParamSchema(key="documents", label="检索结果", type="array"),
        ParamSchema(key="scores", label="相关度分数", type="array"),
    ],
    config_fields=[
        ConfigField(key="top_k", label="返回数量", type="integer", default=5),
        ConfigField(key="score_threshold", label="分数阈值", type="float", default=0.5),
        ConfigField(key="retrieval_mode", label="检索模式", type="string", default="hybrid",
                    options=[{"label": "向量", "value": "vector"},
                             {"label": "全文", "value": "fulltext"},
                             {"label": "混合", "value": "hybrid"}]),
    ],
))

_register(NodeTypeDefinition(
    type="knowledge_indexer", display_key="DatasetWrite", category=NodeCategory.DATA,
    description="知识库写入节点，将数据索引到知识库",
    icon="database", color="#597ef7",
    input_params=[
        ParamSchema(key="documents", label="文档列表", type="array", required=True),
        ParamSchema(key="knowledge_id", label="知识库ID", type="string", required=True),
    ],
    output_params=[
        ParamSchema(key="indexed_count", label="索引数量", type="integer"),
    ],
))

_register(NodeTypeDefinition(
    type="database_custom_sql", display_key="Database", category=NodeCategory.DATABASE,
    description="自定义SQL查询节点",
    icon="table", color="#9254de",
    input_params=[
        ParamSchema(key="sql", label="SQL语句", type="string", required=True),
        ParamSchema(key="params", label="参数", type="object"),
    ],
    output_params=[
        ParamSchema(key="rows", label="查询结果", type="array"),
        ParamSchema(key="affected", label="影响行数", type="integer"),
    ],
    config_fields=[
        ConfigField(key="database_id", label="数据库ID", type="string", required=True),
        ConfigField(key="read_only", label="只读模式", type="boolean", default=True),
    ],
))

_register(NodeTypeDefinition(
    type="question_answer", display_key="Question", category=NodeCategory.UTILITIES,
    description="人机问答节点，中断工作流等待人工输入",
    icon="question", color="#ffc53d",
    input_params=[
        ParamSchema(key="question", label="问题", type="string", required=True),
    ],
    output_params=[
        ParamSchema(key="answer", label="用户回答", type="string"),
    ],
    config_fields=[
        ConfigField(key="timeout", label="超时(秒)", type="integer", default=300),
        ConfigField(key="options", label="预设选项", type="array"),
    ],
))

_register(NodeTypeDefinition(
    type="intent_detector", display_key="Intent", category=NodeCategory.LOGIC,
    description="意图识别节点，使用LLM识别用户意图",
    icon="aim", color="#36cfc9",
    input_params=[
        ParamSchema(key="query", label="用户输入", type="string", required=True),
        ParamSchema(key="intents", label="意图列表", type="array", required=True),
    ],
    output_params=[
        ParamSchema(key="detected_intent", label="识别意图", type="string"),
        ParamSchema(key="confidence", label="置信度", type="float"),
    ],
))

_register(NodeTypeDefinition(
    type="http_requester", display_key="HTTP", category=NodeCategory.UTILITIES,
    description="HTTP请求节点，支持GET/POST/PUT/DELETE",
    icon="global", color="#40a9ff",
    input_params=[
        ParamSchema(key="url", label="URL", type="string", required=True),
        ParamSchema(key="body", label="请求体", type="object"),
    ],
    output_params=[
        ParamSchema(key="status_code", label="状态码", type="integer"),
        ParamSchema(key="response", label="响应体", type="object"),
    ],
    config_fields=[
        ConfigField(key="method", label="方法", type="string", default="GET",
                    options=[{"label": "GET", "value": "GET"}, {"label": "POST", "value": "POST"},
                             {"label": "PUT", "value": "PUT"}, {"label": "DELETE", "value": "DELETE"}]),
        ConfigField(key="headers", label="请求头", type="object"),
        ConfigField(key="timeout", label="超时(秒)", type="integer", default=30),
    ],
))

_register(NodeTypeDefinition(
    type="text_processor", display_key="Text", category=NodeCategory.UTILITIES,
    description="文本处理节点，支持模板/拼接/截取/正则",
    icon="font-size", color="#b37feb",
    input_params=[
        ParamSchema(key="input", label="输入文本", type="string", required=True),
    ],
    output_params=[
        ParamSchema(key="output", label="输出文本", type="string"),
    ],
    config_fields=[
        ConfigField(key="operation", label="操作", type="string", default="template",
                    options=[{"label": "模板", "value": "template"},
                             {"label": "拼接", "value": "concat"},
                             {"label": "截取", "value": "slice"},
                             {"label": "正则替换", "value": "regex_replace"}]),
        ConfigField(key="template", label="模板字符串", type="string"),
        ConfigField(key="regex_pattern", label="正则表达式", type="string"),
    ],
))

_register(NodeTypeDefinition(
    type="variable_assigner", display_key="AssignVariable", category=NodeCategory.DATA,
    description="变量赋值节点，修改工作流变量",
    icon="edit", color="#95de64",
    input_params=[
        ParamSchema(key="variable_name", label="变量名", type="string", required=True),
        ParamSchema(key="value", label="赋值", type="any", required=True),
    ],
    output_params=[
        ParamSchema(key="assigned_value", label="赋值结果", type="any"),
    ],
))

_register(NodeTypeDefinition(
    type="variable_aggregator", display_key="Aggregate", category=NodeCategory.LOGIC,
    description="变量聚合节点，合并多个分支的输出",
    icon="merge", color="#73d13d",
    input_params=[
        ParamSchema(key="inputs", label="输入列表", type="array", required=True),
    ],
    output_params=[
        ParamSchema(key="aggregated", label="聚合结果", type="any"),
    ],
    config_fields=[
        ConfigField(key="mode", label="聚合模式", type="string", default="merge",
                    options=[{"label": "合并", "value": "merge"},
                             {"label": "覆盖", "value": "override"},
                             {"label": "取最新", "value": "latest"}]),
    ],
))

_register(NodeTypeDefinition(
    type="input_receiver", display_key="Input", category=NodeCategory.INPUT_OUTPUT,
    description="中间输入节点，用于复合节点内部",
    icon="login", color="#95de64",
    input_params=[
        ParamSchema(key="value", label="输入值", type="any"),
    ],
    output_params=[
        ParamSchema(key="value", label="传递值", type="any"),
    ],
))

_register(NodeTypeDefinition(
    type="output_emitter", display_key="Message", category=NodeCategory.INPUT_OUTPUT,
    description="中间输出节点，流式输出中间结果",
    icon="logout", color="#ff7a45",
    input_params=[
        ParamSchema(key="message", label="消息内容", type="string", required=True),
    ],
    output_params=[
        ParamSchema(key="emitted", label="已发送", type="boolean"),
    ],
))

_register(NodeTypeDefinition(
    type="json_serialization", display_key="JSON Serialize", category=NodeCategory.UTILITIES,
    description="JSON序列化/反序列化",
    icon="file-text", color="#69c0ff",
    input_params=[
        ParamSchema(key="input", label="输入", type="any", required=True),
    ],
    output_params=[
        ParamSchema(key="output", label="输出", type="any"),
    ],
    config_fields=[
        ConfigField(key="direction", label="方向", type="string", default="serialize",
                    options=[{"label": "序列化", "value": "serialize"},
                             {"label": "反序列化", "value": "deserialize"}]),
    ],
))


def get_node_type_definition(node_type: str) -> Optional[NodeTypeDefinition]:
    return NODE_TYPE_DEFINITIONS.get(node_type)


def list_node_type_definitions(category: NodeCategory | None = None) -> list[NodeTypeDefinition]:
    defs = list(NODE_TYPE_DEFINITIONS.values())
    if category:
        defs = [d for d in defs if d.category == category]
    return defs


def get_node_type_registry() -> dict[str, dict]:
    return {k: v.to_dict() for k, v in NODE_TYPE_DEFINITIONS.items()}