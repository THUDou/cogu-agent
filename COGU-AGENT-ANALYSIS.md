以下是 COGU Agent 代码库的全面结构化总结。

# COGU Agent 代码库全面分析

**版本**: 1.3.0 | **Python**: >=3.11 | **许可**: MIT

## 一、项目概览

COGU (Cognitive Unified Agent) 是一个融合多家国产 AI 框架理念的统一 Agent 框架，灵感来源包括：

- 华为 JiuwenCLAW (Heartbeat/TaskMemory/CodingMemory/A2A)
- 小米 MiMo (超级记忆)
- 百度 LoongFlow (专家思辨/Debate)
- 字节 M3-Agent
- DeepSeek (TUI/优化)
- 清华 CogAgent (GUI Action Space)
- openJiuwen (DeepSearch/ContextEngine/AgentStudio)

## 二、模块详细清单（按目录组织）

### 2.1 cogu/ 根目录

| 文件 | 行数 | 说明 |
|------|------|------|
| __init__.py | 8 | 包入口，声明版本号 1.3.0 及融合来源 |
| __main__.py | 5 | 入口，调用 `cogu.cli.main:main` |

### 2.2 cogu/api/ — LLM API 客户端层

| 文件 | 行数 | 说明 |
|------|------|------|
| client.py | 359 | 核心: `DeepSeekClient` + `MultiProviderClient`，支持流式/非流式聊天、重试、SSE 解析 |
| claude.py | 349 | ClaudeClient，Anthropic API 适配，消息格式转换 + 流式解析 |

关键类:
- `DeepSeekClient`: DeepSeek API 客户端，支持 chat/chat_stream
- `MultiProviderClient`: 多供应商路由（OpenAI/Claude/DeepSeek/Qwen/Zhipu/Moonshot 等）
- `StreamEventType`: TEXT_DELTA/THINKING_DELTA/TOOL_CALL_START 等

### 2.3 cogu/app/ — FastAPI Web 应用层

| 文件 | 行数 | 说明 |
|------|------|------|
| _app.py | 44 | `create_app()` 创建 FastAPI 应用，挂载 7 个路由 |
| _lifespan.py | - | 应用生命周期管理 |
| deps.py | - | 依赖注入 |
| _router/_chat.py | - | 聊天 SSE 流式路由 |
| _router/_agent.py | - | Agent 管理路由 |
| _router/_session.py | - | 会话管理路由 |
| _router/_tool.py | - | 工具管理路由 |
| _router/_memory.py | - | 记忆搜索路由 |
| _router/_settings.py | - | 设置配置路由 |
| _router/_workflow.py | - | 工作流路由 |
| _service/_chat.py | - | 聊天业务逻辑 |
| _service/_agent.py | - | Agent 业务逻辑 |
| _service/_session.py | - | 会话业务逻辑 |

### 2.4 cogu/cli/ — 命令行接口

| 文件 | 行数 | 说明 |
|------|------|------|
| main.py | 505 | 核心 CLI: `cogu run/debate/skills/memory/serve/tui/studio/config/pangu-mini` 等子命令 |

CLI 命令:
- `cogu run` — 运行 Agent
- `cogu debate` — 专家辩论
- `cogu skills list/install/run/builtin` — 技能管理
- `cogu memory stats/search/reconcile` — 记忆操作
- `cogu serve` — 启动 API 服务器
- `cogu tui` — 启动 TUI 界面
- `cogu studio` — 启动可视化工作流编辑器
- `cogu config set/list/model/env` — 配置管理
- `cogu pangu-mini serve/status/memorial` — Pangu 本地模型

### 2.5 cogu/comm/ — 即时通讯适配器

| 文件 | 行数 | 说明 |
|------|------|------|
| dingtalk_adapter.py | 449 | 钉钉 + 飞书适配器: `DingTalkAdapter` + `FeishuAdapter`，支持 Webhook/机器人消息收发 |

### 2.6 cogu/compression/ — 上下文压缩引擎

| 文件 | 行数 | 说明 |
|------|------|------|
| context_engine.py | 261 | ContextEngine: 插件式处理器链，含滑动窗口/Token预算/摘要/去重处理器 |
| pipeline.py | - | 压缩管线 |

处理器链: DeduplicationProcessor -> SlidingWindowProcessor -> TokenBudgetProcessor -> SummaryProcessor

### 2.7 cogu/config/ — 配置系统

| 文件 | 行数 | 说明 |
|------|------|------|
| settings.py | 158 | 核心配置: `Settings` / `DeepSeekConfig` / `MemoryConfig` / `AgentConfig` / `DebateConfig` / `ToolConfig` / `PanguMiniConfig` |
| manager.py | - | ConfigManager: API Key 管理、secrets.json 读写 |

配置层级: `~/.cogu/config.json` + 环境变量 + `.env` 文件

### 2.8 cogu/core/ — 核心引擎（21 个文件，最大模块）

| 文件 | 行数 | 说明 |
|------|------|------|
| agent.py | 658+ | 核心: `ReActAgent`，ReAct 推理循环，支持 invoke/stream/query，含记忆注入/上下文压缩/工具守卫 |
| session.py | 270 | `Session` + `StreamFrame` + `Checkpointer`，会话状态管理 |
| runner.py | 255 | `Runner` 全局运行器，初始化客户端/工具/轨道/会话 |
| rails.py | 239 | `RailRegistry` + `AgentRail`，Agent 回调钩子系统（before_invoke/after_tool_call 等） |
| two_level_planner.py | 445 | `TwoLevelPlanner` + `DAGExecutor`，两层规划器（意图->任务DAG->执行） |
| query_engine.py | 551 | QueryEngine，多模式查询引擎（default/mission/plan/code） |
| reasoning_chain.py | 512 | ReasoningChain，推理链（BFS/DFS/MCTS/Beam 搜索） |
| streaming_executor.py | 159 | StreamingToolExecutor，流式工具执行器（并发安全/顺序/混合模式） |
| tool_guard.py | 204 | `ToolGuardEngine` + `ThreatClassifier`，工具安全守卫（威胁分类/审批/阻止） |
| api_config.py | 517 | `MultiProviderClient` + `Provider` 枚举，多 LLM 供应商配置（9 家国产+国际） |
| ego.py | 398 | `EgoLayer` + `EvidenceLoop` + `SideGitSnapshot`，自我意识层（证据循环/回滚/快照） |
| heartbeat.py | 256 | `HeartbeatService`，周期性 Agent 唤醒（HEARTBEAT.md 文件驱动） |
| rituals.py | 635 | `RitualScheduler` + `CronJobStore`，定时任务/Cron 调度系统 |
| sandbox.py | - | 沙箱执行环境 |
| retry.py | - | 重试策略 |
| cancellation.py | - | 取消机制 |
| token_monitor.py | - | Token 用量监控 |
| skills_system.py | 1023 | BuiltinSkillRegistry，内置技能系统（reasoning/vision/code/office/browser/gui/data/comm） |
| workspace.py | 478 | 工作区管理 + 技能记录 |

### 2.9 cogu/debate/ — 专家辩论系统

| 文件 | 行数 | 说明 |
|------|------|------|
| debate.py | 187 | `DebateOrchestrator`，4 种辩论模式（standard/swarm/court/dialectic） |
| expert.py | - | `Expert` + `ExpertRole`，专家角色定义 |
| team.py | - | `Team` + `CoordinationPattern`，团队协调模式 |
| pes_engine.py | - | `PESEngine`，PES (Plan-Evaluate-Synthesize) 引擎 |
| orchestrate.py | 149 | `GraphOrchestrator`，图编排器（sequential/handoff/backbone 模式） |

### 2.10 cogu/desktop/ — 桌面应用

| 文件 | 行数 | 说明 |
|------|------|------|
| loong.py | 225 | COGU Loong 桌面版: uvicorn + pywebview，端口 8198，含 fallback FastAPI |
| launcher.py | - | 桌面启动器 |

桌面应用架构: 后端 FastAPI (8198) + 前端 pywebview 加载 `cogu-loong.html`

### 2.11 cogu/evolution/ — Agent 自进化系统

| 文件 | 行数 | 说明 |
|------|------|------|
| trajectory.py | 295 | `Trajectory` + `TrajectoryStep`，执行轨迹数据模型（LLM/工具步骤+奖励） |
| trace_analyzer.py | - | 轨迹分析器 |
| fitness.py | - | 适应度评估 |
| constraints.py | - | 进化约束 |
| evolve_prompt.py | - | Prompt 进化 |
| evolve_memory.py | - | 记忆进化 |
| evolve_skill.py | - | 技能进化 |
| dataset_builder.py | - | 训练数据集构建 |
| pr_builder.py | - | PR 自动构建 |
| config.py | - | 进化配置（进化岛/种群/代数） |

### 2.12 cogu/gateway/ — 网关服务

| 文件 | 行数 | 说明 |
|------|------|------|
| server.py | 267 | `GatewayServer`，原始 TCP HTTP 服务器，SSE 流式推送，会话/取消/状态管理 |
| __init__.py | - | `get_gateway()` 工厂函数 |
| dashboard.html | - | 网关仪表盘 |

网关端点: `/v1/gateway/messages` (REST) + `/v1/gateway/messages:stream` (SSE) + `/v1/gateway/cancel`

### 2.13 cogu/mcp/ — Model Context Protocol 集成

| 文件 | 行数 | 说明 |
|------|------|------|
| manager.py | 86 | `MCPManager`，MCP 服务器连接管理 |
| session.py | - | `MCPSession`，stdio/HTTP 传输层 |
| tool.py | - | `MCPTool`，MCP 工具适配 |
| safety.py | - | 命令哈希 + 启动验证 |
| schema.py | - | MCP Schema 定义 |
| a2a_adapter.py | - | Agent-to-Agent 协议适配器 |

### 2.14 cogu/memory/ — 超级记忆系统（18 个文件）

| 文件 | 行数 | 说明 |
|------|------|------|
| enhanced_memory.py | 496 | 核心: `EnhancedSuperMemory`，统一记忆入口，5 种召回策略（FTS/语义/混合/图/综合） |
| super_memory.py | 282 | `SuperMemory`，SQLite + FTS5 全文检索 + 语义搜索 |
| grade_memory.py | 581 | `GradeMemory`，三级记忆（STM/MTM/LTM）+ 自动压缩 |
| entity_graph.py | 292 | `EntityGraph`，实体关系图（SQLite 存储） |
| memory_graph.py | 256 | `MemoryGraph`，记忆图谱（节点+边+衰减） |
| memory_store.py | - | `MemoryStore`，文件级记忆存储（global/project/session 三级作用域） |
| experience_kb.py | - | `AgenticKnowledgeBase`，经验知识库 |
| coding_memory.py | 200 | `CodingMemory`，项目级代码记忆（.md 文件存储） |
| task_memory.py | 223 | `TaskMemoryService`，任务经验检索（JSON 持久化） |
| dream.py | 129 | `DreamMode`，记忆整理（合并/遗忘/提升），类似"睡眠整理" |
| semantic_compressor.py | - | 语义压缩器 |
| compression_pipeline.py | - | 记忆压缩管线 |
| context_offloader.py | - | 上下文卸载器 |
| memory_pyramid.py | - | 记忆金字塔 |
| rrf_ranker.py | - | RRF (Reciprocal Rank Fusion) 排序 |
| task_canvas.py | - | 任务画布 |

记忆架构: EnhancedSuperMemory = SuperMemory(FTS) + GradeMemory(STM/MTM/LTM) + EntityGraph + MemoryGraph + MemoryStore(文件) + ExperienceKB

### 2.15 cogu/middleware/ — 中间件系统

| 文件 | 说明 |
|------|------|
| base.py | `Middleware` 基类 |
| chain.py | `MiddlewareChain`，有序中间件链 |
| builtin.py | 内置中间件 |

### 2.16 cogu/mini_engine/ — Pangu 本地模型引擎

| 文件 | 行数 | 说明 |
|------|------|------|
| pangu_engine.py | 363 | openPangu-Embedded-1B 推理引擎: 双后端（transformers+PyTorch / llama-cpp GGUF） |
| server.py | 177 | OpenAI 兼容 API 服务器（HTTP），端口 8199，支持流式 |
| __init__.py | - | 包初始化 |

纪念: `_memorial` 字段记录 "2026.6.12 — COGU 诞生日，也是华为发布 OpenPangu 2.0 的日子"

### 2.17 cogu/observability/ — 可观测性

| 文件 | 行数 | 说明 |
|------|------|------|
| tracing.py | 113 | `Span` + `Tracer`，分布式追踪（span/trace/contextmanager） |

### 2.18 cogu/orchestrator/ — 多 Agent 编排

| 文件 | 行数 | 说明 |
|------|------|------|
| conductor.py | 140 | `Conductor`，4 种调度模式（round_robin/hierarchical/parallel/vote） |
| musician.py | - | `Musician`，Agent 执行单元 |

### 2.19 cogu/permission/ — 权限系统

| 文件 | 说明 |
|------|------|
| engine.py | `PermissionEngine` + `AuthContext`，4 级认证（anonymous/authenticated/privileged/admin） |
| policy.py | `AccessPolicy` + `PolicySet`，RBAC 策略 |
| credentials.py | `CredentialVault`，凭据保险箱 |

### 2.20 cogu/search/ — 深度搜索

| 文件 | 行数 | 说明 |
|------|------|------|
| deep_search.py | 366 | `DeepSearchEngine`，查询规划->多步搜索->来源溯源->报告生成，支持 DuckDuckGo/本地知识库后端 |

### 2.21 cogu/skills/ — 技能系统

| 文件 | 行数 | 说明 |
|------|------|------|
| registry.py | 267 | `SkillRegistry`，技能发现/安装/卸载/搜索，支持 URL/本地/ZIP 安装 |
| executor.py | - | `SkillExecutor`，Markdown 技能执行器 |
| spec.py | - | `SkillSpec`，技能规格定义（SKILL.md 解析） |
| behavior_cloner.py | - | `BehaviorCloner`，行为克隆（录制->技能） |
| im_adapter.py | - | `PlatformAdapter` + `IMMessage`，IM 平台适配基类 |
| integration.py | - | 技能集成 |

### 2.22 cogu/state/ — 状态管理

| 文件 | 说明 |
|------|------|
| manager.py | `StateManager`，多后端状态管理 |
| backend.py | `StateBackend` 抽象基类 |
| local_backend.py | 本地文件后端 |
| memory_backend.py | 内存后端 |
| s3_backend.py | S3 后端 |

### 2.23 cogu/studio/ — 可视化工作流引擎

| 文件 | 行数 | 说明 |
|------|------|------|
| workflow_engine.py | 432 | `WorkflowEngine` + `WorkflowDefinition`，节点图 DSL + 执行引擎（Start/End/LLM/Tool/Condition/Code/Retry 节点），支持 Mermaid 导出 |

### 2.24 cogu/tools/ — 工具系统

| 文件 | 行数 | 说明 |
|------|------|------|
| base.py | 243 | 核心: `ToolRegistry` + `FunctionTool` + `ToolSpec`，工具注册/分组/并行执行 |
| scheduler.py | - | `ToolScheduler`，工具调度器 |
| lazy.py | - | 懒加载工具 |
| mcp_adapter.py | - | MCP 工具适配器 |
| atom_evolver.py | - | Atom 进化器 |
| builtin/gui.py | 421 | GUI Agent: CogAgent 风格 Action Space（CLICK/TYPE/SCROLL/KEY_PRESS/LAUNCH/SCREENSHOT 等），归一化坐标 000-999 |
| builtin/office.py | 234 | Office 工具: PDF 读取/合并/拆分、DOCX/XLSX/PPTX 读写 |
| builtin/__init__.py | - | 注册所有内置工具 |

### 2.25 cogu/topology/ — 拓扑管理

| 文件 | 说明 |
|------|------|
| spec.py | `AgentNode` + `ChannelPolicy`，Agent 拓扑规格（leader/worker/coordinator 角色） |
| manager.py | 拓扑管理器 |

### 2.26 cogu/tui/ — 终端 UI

| 文件 | 行数 | 说明 |
|------|------|------|
| app.py | 226 | `CoguTUI` (Textual)，3 个标签页：Chat/Debate/Memory |

### 2.27 cogu/web/ — Web UI

| 文件 | 行数 | 说明 |
|------|------|------|
| cogu-loong.html | 1099 | COGU Loong 桌面 UI: 深色主题聊天界面，侧边栏导航，SSE 流式对话，设置面板 |
| dashboard.html | - | 仪表盘页面 |
| workbuddy.html | - | WorkBuddy 页面 |

### 2.28 cogu/sdk/ — SDK 客户端

| 文件 | 行数 | 说明 |
|------|------|------|
| client.py | 367 | `CoguSDK`，HTTP SDK 客户端，支持 chat/stream/agent/session 管理 |

## 三、架构模式

```
用户交互层
├── CLI (cogu/cli/main.py)
├── TUI (cogu/tui/) — Textual
├── Desktop (cogu/desktop/loong.py) — pywebview + FastAPI
├── Web UI (cogu/web/cogu-loong.html) — SSE 流式
└── SDK (cogu/sdk/client.py) — HTTP

API 层
├── FastAPI App (cogu/app/) — 7 个 Router
└── Gateway (cogu/gateway/server.py) — 原始 TCP SSE

核心引擎层
├── ReActAgent (cogu/core/agent.py) — ReAct 推理循环
├── QueryEngine (cogu/core/query_engine.py) — 多模式查询
├── TwoLevelPlanner (cogu/core/two_level_planner.py) — 意图->任务DAG->执行
├── ReasoningChain (cogu/core/reasoning_chain.py) — MCTS/Beam
├── ToolGuard (cogu/core/tool_guard.py) — 安全守卫
├── Rails (cogu/core/rails.py) — 回调钩子
└── EgoLayer (cogu/core/ego.py) — 证据循环+回滚

LLM 客户端层
├── DeepSeekClient (cogu/api/client.py)
├── ClaudeClient (cogu/api/claude.py)
├── MultiProviderClient (cogu/core/api_config.py) — 9 家供应商
└── PanguEngine (cogu/mini_engine/) — 本地推理

记忆层
└── EnhancedSuperMemory (cogu/memory/enhanced_memory.py)
    ├── SuperMemory — SQLite FTS5
    ├── GradeMemory — STM/MTM/LTM
    ├── EntityGraph — 实体关系
    ├── MemoryGraph — 记忆图谱+衰减
    ├── MemoryStore — 文件存储
    └── ExperienceKB — 经验知识库

工具层
├── ToolRegistry (cogu/tools/base.py)
├── GUI Agent (cogu/tools/builtin/gui.py) — CogAgent
├── Office Tools (cogu/tools/builtin/office.py)
└── MCP Adapter (cogu/tools/mcp_adapter.py)

编排层
├── DebateOrchestrator (cogu/debate/)
├── Conductor (cogu/orchestrator/)
├── WorkflowEngine (cogu/studio/)
└── GraphOrchestrator (cogu/debate/orchestrate.py)

基础设施层
├── Config (cogu/config/) — Settings + ConfigManager
├── Permission (cogu/permission/) — RBAC + 凭据
├── State (cogu/state/) — 多后端状态
├── Observability (cogu/observability/) — 追踪
├── Middleware (cogu/middleware/) — 中间件链
├── Comm (cogu/comm/) — 钉钉/飞书
└── Topology (cogu/topology/) — Agent 拓扑
```

## 四、AI/LLM 集成点

- `DeepSeekClient` (`D:\COGU AGENT\cogu_agent\cogu\api\client.py`): 主力 LLM 客户端，支持 chat + chat_stream + 重试
- `ClaudeClient` (`D:\COGU AGENT\cogu_agent\cogu\api\claude.py`): Anthropic API 适配
- `MultiProviderClient` (`D:\COGU AGENT\cogu_agent\cogu\core\api_config.py`): 9 家供应商路由（OpenAI/Claude/DeepSeek/Qwen/Zhipu/Moonshot/MiniMax/Doubao/Custom）
- `PanguEngine` (`D:\COGU AGENT\cogu_agent\cogu\mini_engine\pangu_engine.py`): 本地 openPangu-Embedded-1B 推理，双后端（transformers/GGUF）
- `PanguAPI Server` (`D:\COGU AGENT\cogu_agent\cogu\mini_engine\server.py`): OpenAI 兼容 API，端口 8199

## 五、桌面应用特性

`COGU Loong` (`D:\COGU AGENT\cogu_agent\cogu\desktop\loong.py`): pywebview 桌面应用
- 后端: FastAPI (uvicorn, 端口 8198)
- 前端: `cogu-loong.html` (1099 行深色主题聊天 UI)
- 支持 fallback 模式（无 pywebview 时自动打开浏览器）
- 内置 onboarding API Key 配置流程
- 窗口: 1280x800, 最小 960x600

## 六、配置系统

`Settings` (`D:\COGU AGENT\cogu_agent\cogu\config\settings.py`): 7 大配置块
- `DeepSeekConfig`: API Key/Base URL/模型/推理力度
- `ProviderConfig`: 多供应商配置
- `MemoryConfig`: DB 路径/FTS/压缩
- `AgentConfig`: 模型/温度/最大迭代
- `DebateConfig`: 专家数/轮次/PES
- `ToolConfig`: 沙箱/审批/超时
- `PanguMiniConfig`: 本地模型开关/后端/端口

`ConfigManager` (`D:\COGU AGENT\cogu_agent\cogu\config\manager.py`): secrets.json 加密存储

加载优先级: `.cogu/config.json` -> 环境变量 -> `.env` -> 默认值

## 七、记忆系统架构

```
EnhancedSuperMemory (统一入口)
├── remember() — 写入所有子存储
├── recall() — 5 种策略: FTS_ONLY / SEMANTIC_ONLY / HYBRID / GRAPH_WALK / COMPREHENSIVE
├── forget() — 删除
├── commit_to_ltm() — STM->LTM 提升
├── reconcile() — 一致性校验
├── deposit_experience() — 经验存入
├── build_context() — 构建 Session 上下文注入
└── DreamMode (cogu/memory/dream.py) — "睡眠整理"记忆
```

## 八、工具集成

- `ToolRegistry` (`D:\COGU AGENT\cogu_agent\cogu\tools\base.py`): 注册/分组/并行执行/OpenAI 格式导出
- `GUI Agent` (`D:\COGU AGENT\cogu_agent\cogu\tools\builtin\gui.py`): CogAgent 风格，16 种 Action，归一化坐标 000-999
- `Office` (`D:\COGU AGENT\cogu_agent\cogu\tools\builtin\office.py`): PDF/DOCX/XLSX/PPTX 读写
- `MCP` (`D:\COGU AGENT\cogu_agent\cogu\mcp/`): Model Context Protocol + A2A 协议
- `ToolGuard` (`D:\COGU AGENT\cogu_agent\cogu\core\tool_guard.py`): 威胁分类(6类) + 审批机制
- `StreamingToolExecutor` (`D:\COGU AGENT\cogu_agent\cogu\core\streaming_executor.py`): 并发安全/顺序/混合执行

## 九、Web UI 特性

`cogu-loong.html` (`D:\COGU AGENT\cogu_agent\cogu\web\cogu-loong.html`, 1099 行):
- 深色主题（`--bg-root: #0d0d0d`）
- 左侧 60px 图标导航栏
- 右侧 240px 信息面板
- SSE 流式聊天（`/api/chat/stream`）
- 设置面板（API Key/Pangu Mini 开关）
- 会话管理
- 工具仪表盘

## 十、Pangu Mini Engine 集成

`pangu_engine.py` (`D:\COGU AGENT\cogu_agent\cogu\mini_engine\pangu_engine.py`, 363 行):
- `PanguTransformersBackend`: transformers + PyTorch，加载 safetensors
- `PanguGGUFBackend`: llama-cpp-python，加载 GGUF 量化格式
- `PanguEngine`: 自动选择后端（优先 GGUF）
- `to_openai_format()`: 返回 OpenAI 兼容响应

`server.py` (`D:\COGU AGENT\cogu_agent\cogu\mini_engine\server.py`, 177 行):
- `PanguAPIHandler`: 原始 HTTP 服务器
- 端点: `POST /v1/chat/completions` (支持流式) + `GET /v1/models` + `GET /healthz`
- 默认端口: 8199

