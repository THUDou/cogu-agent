# COGU AGENT

**Cognitive Unified Agent** — 自进化认知智能体框架

> 152 Python 文件 · 20,867 行代码 · 完全原创 · 零外部框架依赖

## 项目定位

COGU AGENT 是一个**完全原创**的 Python Agent 框架，融合了 33 个国内外开源智能体项目的**设计灵感**（非代码依赖），形成了独立的架构体系。核心竞争力是**自进化系统**——Agent 能够自动优化自身的技能、记忆和 Prompt。

## 架构总览

```
cogu/
├── core/           ← 核心引擎 (ReAct Agent, 4级护栏, 推理链, 二级规划)
├── memory/         ← 超级记忆 (FTS5 + 向量 + 图 + 分级压缩 + Dream)
├── evolution/      ← 自进化 (技能/Prompt/记忆进化, 适应度评估)
├── debate/         ← 思辨团队 (6种专家, 5种协调, PES引擎, 超图编排)
├── tools/          ← 工具系统 (可插拔注册, MCP协议, 原子进化)
├── skills/         ← 技能系统 (Markdown规范, 自动发现, 行为克隆)
├── mcp/            ← MCP全栈 (Schema归一化, 安全认证, 多传输)
├── comm/           ← 通信层 (HTTP/WebSocket/Matrix/gRPC)
├── state/          ← 共享状态 (内存/本地/S3 三后端)
├── permission/     ← 权限引擎 (RBAC, Fernet加密, 4级认证)
├── middleware/      ← 洋葱中间件 (6种内置)
├── observability/  ← 可观测性 (OTLP全链路追踪)
├── api/            ← LLM接入 (DeepSeek/OpenAI/Claude/7家供应商)
├── config/         ← 配置管理 (API Key, 多供应商)
├── app/            ← Web服务 (FastAPI, REST + SSE)
├── sdk/            ← Python SDK
├── gateway/        ← 网关 (Wire Protocol, JSONRPC2)
├── tui/            ← 终端UI (Textual, Chat/Debate/Memory三面板)
├── topology/       ← 声明式拓扑
├── orchestrator/   ← 多Agent编排
├── compression/    ← 上下文压缩
├── desktop/        ← Windows桌面 (pywebview)
└── mini_engine/    ← 盘古小模型 (隐藏功能)
```

## 核心特性

### P0 — 自进化系统 `cogu/evolution/`

| 模块 | 功能 | 灵感来源 |
|------|------|---------|
| `evolve_skill.py` | 技能文本自动进化 (LLM变异 + 规则变异) | Hermes Self-Evolution |
| `evolve_memory.py` | 记忆整合 / 用户画像提取 / 每日沉淀 | X-OmniClaw Memory Evolution |
| `evolve_prompt.py` | 系统 Prompt 段落进化 | Hermes DSPy+GEPA |
| `fitness.py` | 适应度评估 (LLM-as-judge + 规则双路径) | Hermes GEPA |
| `constraints.py` | 约束验证 (大小/语义保持/去重) | Hermes Guardrails |
| `trace_analyzer.py` | 执行轨迹分析 → 变异提示 | Hermes Reflective Evolution |
| `pr_builder.py` | 自动生成改进 PR + 指标对比 | Hermes PR-based Deployment |

### P0 — 语义压缩 + Token 监控

| 模块 | 功能 |
|------|------|
| `memory/semantic_compressor.py` | 按用户消息边界分段 → LLM/规则摘要 → Token预算压缩 |
| `core/token_monitor.py` | tiktoken本地 + API返回双重检测，超限预警 |
| `core/cancellation.py` | asyncio.Event安全取消 + 不完整消息清理 |

### P1 — MCP 全栈 + 超图编排

| 模块 | 功能 |
|------|------|
| `mcp/schema.py` | OpenAI兼容 Schema 归一化 (type+nullable) |
| `mcp/safety.py` | command_hash(sha256) + boot_validate 安全认证 |
| `mcp/session.py` | MCP 会话生命周期 (stdio/SSE/HTTP) |
| `debate/orchestrate.py` | 超图编排 (SEQUENTIAL/HANDOFF/BACKBONE) |
| `core/retry.py` | 优雅重试装饰器 (指数退避) |

### P2 — 追踪 + Dream + 原子进化

| 模块 | 功能 |
|------|------|
| `observability/tracing.py` | OTLP 全链路追踪 (Span/Trace/导出) |
| `memory/dream.py` | 空闲记忆整理 + 遗忘机制 + 重要性提升 |
| `tools/atom_evolver.py` | 原子工具拆解 → 重组 → 进化 |

## 已有核心能力

| 层级 | 模块 | 功能 |
|------|------|------|
| **核心** | `ReActAgent` | async generator 主循环, 964行 |
| | `ToolGuardEngine` | 4级安全护栏 (LOW→CRITICAL) |
| | `ReasoningChain` | PanguAgent式内在/外在推理 + BFS/DFS/MCTS/Beam |
| | `TwoLevelPlanner` | Work→Task 两级规划 + DAG执行器 |
| | `WorkSpace` | 隔离容器 (文件+记忆+技能) + 白盒记忆 |
| **记忆** | `MemoryPyramid` | L0对话→L1原子→L2场景→L3人设 |
| | `SuperMemory` | SQLite FTS5 + 向量混合搜索 |
| | `MemoryGraph` | 加权嵌入图 (强化/衰减/路径采样) |
| | `GradeMemory` | STM→MTM→LTM 自动分级压缩 |
| | `CompressionPipeline` | 3级压缩 (micro/compact/reactive) |
| | `RRFRanker` | BM25 + Vector RRF 混合排序 |
| **思辨** | `DebateOrchestrator` | 4种辩论模式, Consensus含少数报告 |
| | `Expert` | 6种专家角色, 三阶段意见形成 |
| | `PESEngine` | Plan→Execute→Summarize 循环 |
| **工具** | `ToolRegistry` | 可插拔注册, 读写分离调度 |
| | `MCPTool` | MCP 协议适配器 |
| | `GUIAgent` | CogAgent式16种GUI动作, 000-999坐标 |
| **技能** | `SkillRegistry` | Markdown规范, 自动发现/安装/执行 |
| | `BuiltinSkillRegistry` | 9个内置技能 |
| | `BehaviorCloner` | 录制→回放→导出管线 |
| **通信** | `CommManager` | HTTP/WebSocket/Matrix/gRPC 四后端 |
| **状态** | `StateManager` | 内存/本地JSONL/S3 三后端 |
| **权限** | `PermissionEngine` | RBAC + Fernet加密 + 4级认证 |
| **中间件** | `MiddlewareChain` | 洋葱模型, 6种内置中间件 |

## 安装

```bash
# 基础安装
pip install -e .

# 开发模式
pip install -e ".[dev]"

# 完整功能
pip install -e ".[comm,s3,server]"
```

## 使用

```bash
# CLI
cogu run "帮我分析这段代码"
cogu debate "量子计算的未来"
cogu skills list
cogu memory search "关键词"
cogu config list

# TUI 终端界面
cogu tui

# Web 服务
cogu serve --port 8000
```

## 技术栈

- **语言**: Python 3.11+
- **构建**: Hatchling
- **核心依赖**: httpx, pydantic, openai, rich, textual, sqlite-fts4, tiktoken
- **可选依赖**: fastapi, websockets, matrix-nio, grpcio, boto3
- **协议**: JSONRPC2, SSE, MCP, OTLP

## 版本历史

| 版本 | 日期 | 内容 |
|------|------|------|
| **v1.0.0** | 2026-06-14 | 自进化系统 + 9大增量升级 (24 files, +2593 lines) |
| v0.9.1 | 2026-06-13 | Windows桌面版 (pywebview + Inno Setup) |
| v0.9.0 | 2026-06-12 | 完整模块系统发布 |
| v0.8.2 | 2026-06-12 | 模块完整性扫描与导出修复 |
| v0.5.0 | 2026-06-12 | WorkSpace + 推理链 + 二级规划 |
| v0.3.0 | 2026-06-12 | P0架构升级 (async generator + 记忆RAG) |
| v0.1.0 | 2026-06-12 | 初始版本 (41 files, 6194 lines) |

## 融合记录

COGU AGENT 的设计灵感来自 33 个开源项目，但**代码完全原创**，零运行时依赖。

| 灵感来源 | 贡献的设计模式 |
|---------|--------------|
| Hermes Self-Evolution | DSPy+GEPA 反射式进化 |
| LoongFlow | MAP-Elites 进化记忆, PES引擎 |
| X-OmniClaw | 记忆自动进化, 每日沉淀 |
| Mini-Agent (MiniMax) | 双重Token监控, LLM语义摘要, MCP适配 |
| Syll (清华) | MCP全栈安全, Schema归一化 |
| LangCrew (01.AI) | 超图编排 (HANDOFF/BACKBONE) |
| AstronAgent (讯飞) | OTLP全链路追踪 |
| JoyAgent (京东) | 2级规划, DAG执行, 原子工具进化 |
| PilotDeck (清华面壁) | WorkSpace隔离, 白盒记忆, 智能路由 |
| PanguAgent (华为) | 内在/外在推理链, MCTS树搜索 |
| AgentOrchestra (昆仑万维) | 指挥家-乐手编排 |
| AstrBot (北邮) | IM适配器模式 |
| MiMo-Code (小米) | FTS5记忆, 分级压缩 |
| M3-Agent (字节) | 加权嵌入图 |
| DeepSeek-TUI | ReAct循环, 流式SSE |
| OpenClaw | 4级护栏, 工具白名单 |
| LobsterAI (网易) | 可插拔工具注册 |
| Claude Code | SKILL.md规范, 技能注册 |
| Kimi Agent SDK | Wire Protocol |
| CogAgent (清华) | GUI动作空间 |
| JiuwenCLAW (华为) | Runner单例, 会话管理 |

## 许可证

MIT License
