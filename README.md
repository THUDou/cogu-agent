# COGU Loong

> **Cognitive Unified Agent** — 国产原创全栈 Agent 框架，融合盘古推理 + 千问知识 + 小米技能生态 + 腾讯办公自动化

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/version-1.4.0-orange.svg" alt="Version">
  <img src="https://img.shields.io/badge/models-Pangu%20%2B%20Qwen-red.svg" alt="Models">
</p>

---

## 为什么选择 COGU？

COGU Loong 是一个**从零构建**的原创 Agent 框架，不是任何现有框架的 fork。它将认知推理、超级记忆、自进化、专家辩论、安全护栏、多模型推理统一在一个架构中。

| 维度 | COGU 的创新 |
|------|-------------|
| **推理引擎** | Intrinsic/Extrinsic 函数分离 + MCTS/Beam Search 树搜索推理 |
| **记忆系统** | 六系统融合（FTS5+语义+图+实体+分级+经验KB）+ Dream 整理 + Instinct 持续学习 |
| **自进化** | Skill/Prompt/Trajectory 三路进化 + CoEvolution 共生反馈环 |
| **专家辩论** | PES 三阶段引擎 + 5 专家角色 + 4 种辩论模式 + 共识/少数派报告 |
| **安全护栏** | Guardian 独立审查 + SkillScanner 恶意检测 + RBAC 权限引擎 + ToolGuard |
| **本地推理** | 盘古 Pangu + 千问 Qwen 双后端 + GGUF/Transformers 自动选择 |
| **Agent 互操作** | A2A（完整 Client/Server）+ ACP 双协议 |

---

## 核心架构

```
┌─────────────────────────────────────────────────────┐
│                   COGU Loong v1.4.0                  │
├──────────┬──────────┬──────────┬──────────┬─────────┤
│  CLI/TUI │ Desktop  │  Studio  │ Gateway  │  Mini   │
│  终端界面 │ 桌面应用  │ 可视化    │ API网关  │ 本地模型 │
├──────────┴──────────┴──────────┴──────────┴─────────┤
│                    ReAct Agent Core                   │
│  ┌─────────┐ ┌──────────┐ ┌────────┐ ┌───────────┐ │
│  │  Rails  │ │ 2-Level  │ │  Ego   │ │   Stuck   │ │
│  │  护栏   │ │ Planner  │ │ 证据环 │ │  Detector │ │
│  └─────────┘ └──────────┘ └────────┘ └───────────┘ │
├──────────────────────────────────────────────────────┤
│  Reasoning Chain (Intrinsic/Extrinsic + Tree Search) │
├───────┬───────┬──────────┬──────────┬──────────────┤
│Memory │Evolve │ Debate   │ Security │  Orchestrate │
│ 6合1  │自进化 │ PES引擎  │ Guardian │ Conductor    │
├───────┴───────┴──────────┴──────────┴──────────────┤
│              Skills Ecosystem (94 skills)             │
├──────────────────────────────────────────────────────┤
│        Multi-Provider LLM (Cloud/Ollama/Local)       │
│  DeepSeek · OpenAI · Claude · 华为云 · 腾讯云 · Ollama │
│  盘古 Pangu 1.39B (transformers) · Qwen3.5-0.8B (GGUF)│
└──────────────────────────────────────────────────────┘
```

---

## 五种使用模式

| 模式 | 启动命令 | 说明 |
|------|----------|------|
| **CLI** | `cogu run "提示词"` | 命令行快速交互、脚本集成 |
| **TUI** | `cogu tui` | Textual 终端界面，Chat/Debate/Memory 三面板 |
| **Desktop** | `python -m cogu.desktop.loong` | pywebview 原生桌面应用 |
| **Studio UI** | `cogu studio` | React + Vite 可视化工作流编辑器 |
| **Gateway** | `cogu serve` | FastAPI HTTP API 服务 |

---

## 三级 LLM 策略

COGU 按优先级自动选择 LLM 提供商，无需手动切换：

```
云端 API (DeepSeek/OpenAI/Claude/华为云/腾讯云/...)
    ↓ 无 API Key
Ollama 本地模型 (localhost:11434)
    ↓ 无 Ollama
内置 MINI 模型 (Qwen3.5 GGUF / Pangu transformers)
```

### 内置本地模型

| 模型 | 格式 | 大小 | 引擎 | 说明 |
|------|------|------|------|------|
| Qwen3.5-0.8B | GGUF Q5_K_M | 585MB | llama-cpp-python | 千问社区蒸馏版，零配置可用 |
| openPangu-Embedded-1B | safetensors | 2.78GB | transformers 4.53.2 | 华为盘古端侧模型，独立 venv 隔离 |

```bash
# 零配置启动本地模型
cogu pangu-mini serve              # 自动选择
cogu pangu-mini serve --local-model qwen   # 指定 Qwen
cogu pangu-mini serve --local-model pangu  # 指定盘古
```

---

## 快速开始

### 安装

```bash
git clone https://github.com/THUDou/cogu-agent.git
cd cogu-agent/cogu_agent
pip install -e .
```

### 配置 LLM

```bash
# 方式 1: 云端 API（推荐）
cogu config set deepseek sk-your-key

# 方式 2: Ollama（需先安装 Ollama 并拉取模型）
ollama pull qwen3

# 方式 3: 内置 MINI 模型（零配置，无需联网）
# 无需任何配置，自动启动
```

### 运行

```bash
# CLI 模式
cogu run "帮我分析这段代码的性能瓶颈"

# TUI 模式
cogu tui

# 启动 API 服务
cogu serve

# 查看技能列表
cogu skills list

# 专家辩论
cogu debate "微服务 vs 单体的取舍"

# 查看版本
cogu version
```

---

## 核心模块详解

### 1. 推理链 (Reasoning Chain)

运算符重载组合推理步骤：`>>` 串行、`|` 并行

```python
from cogu.core.reasoning_chain import ReactReasoning, SwiftSageReasoning

# ReAct 模式
chain = ThinkStep >> ActionStep >> ObserveStep

# SwiftSage 模式（规划-评估-执行）
chain = PlanStep | EvaluateStep >> ExecuteStep
```

内置 4 种搜索算法：BFS / DFS / MCTS / Beam Search

### 2. 超级记忆 (Enhanced Super Memory)

```python
from cogu.memory import EnhancedSuperMemory, RecallStrategy

memory = EnhancedSuperMemory(workspace="./data")
await memory.store("用户偏好: 喜欢简洁的代码风格", level="LTM")
results = await memory.recall("代码风格", strategy=RecallStrategy.COMPREHENSIVE)

# Dream 整理：自动整合、遗忘、提升
await memory.dream()
```

- **FTS5** 全文搜索 + **Embedding** 语义搜索 + **RRF** 融合排序
- **MemoryPyramid**: L0(原始) → L1(原子知识) → L2(场景) → L3(人格)
- **EntityGraph**: 实体-关系知识图谱 + BFS 邻居查询
- **ExperienceKB**: 工作流经验存储与检索

### 3. 自进化 (Self-Evolution)

```python
from cogu.evolution.evolve_skill import SkillEvolver

evolver = SkillEvolver(skill_dir="./skills/my-skill")
result = await evolver.evolve(trace=usage_trace, generations=3)
```

- **SkillEvolver**: 基线评估 → 变异生成 → 约束验证 → 适应度评估 → 安全部署
- **PromptEvolver**: System Prompt 分节进化
- **CoEvolutionEngine**: Curriculum + Executor 共生反馈环

### 4. 专家辩论 (PES Debate Engine)

```python
from cogu.debate import DebateOrchestrator, DebateConfig, DebateMode

orchestrator = DebateOrchestrator(DebateConfig(mode=DebateMode.COURT))
consensus = await orchestrator.debate("是否应该采用微服务架构？")
# consensus.proposal, consensus.supporting, consensus.dissenting
```

4 种辩论模式：STANDARD / SWARM / COURT / DIALECTIC

### 5. 安全系统

```python
from cogu.security.skill_scanner import SkillScanner

scanner = SkillScanner()
report = scanner.scan("./skills/untrusted-skill/")
# report.risk_level: high/medium/low
# report.findings: [PatternMatch(...), ...]
```

- **Guardian**: 工具输出交付前独立审查
- **SkillScanner**: 8 种危险模式检测（os.system/subprocess/eval/exec/...）
- **PermissionEngine**: RBAC + 四级认证 + 凭证保险库

### 6. Agent 互操作 (A2A Protocol)

```python
from cogu.mcp.a2a_adapter import A2AClient, A2AAgentCard

client = A2AClient(base_url="http://other-agent:8080")
card = await client.discover()  # 获取远端 Agent 能力
task = await client.send_task({"prompt": "分析数据"})
```

完整 A2A Client/Server 实现，支持 SSE 流式响应。

---

## 技能生态 (94 Skills)

| 来源 | 数量 | 说明 |
|------|------|------|
| 内置 Python Skill | 9 | 推理/视觉/代码/浏览器/数据/搜索/Shell/金融/网关 |
| 小米 MIClaw | 51 | 前端设计/代码生成/文档处理/数据分析/... |
| 华为 OfficeClaw | 12 | Excel/Word/PPT/Verilog/Android/... |
| 腾讯 WorkBuddy | 24 | PPT大师/法律/专利/简历/Android/... |
| 字节 Doubao | 4 | DOCX/XLSX 本地脚本/技能创建器 |

```bash
cogu skills list          # 查看所有技能
cogu skills install ./my-skill  # 安装技能
cogu skills discover      # 发现新技能
```

---

## 项目结构

```
cogu_agent/
├── cogu/
│   ├── core/           # 核心：ReActAgent, Rails, ReasoningChain, Ego, Planner
│   ├── memory/         # 记忆：SuperMemory, EntityGraph, Dream, Instinct, ExperienceKB
│   ├── evolution/      # 进化：SkillEvolver, PromptEvolver, CoEvolution
│   ├── debate/         # 辩论：PESEngine, Expert, Team, DebateOrchestrator
│   ├── skills/         # 技能：Registry, Executor, Spec, BehaviorCloner, IM适配
│   ├── tools/          # 工具：Registry, MCP适配, 浏览器视觉, 多文件编辑
│   ├── mini_engine/    # 本地模型：PanguEngine, Qwen GGUF, LocalServer
│   ├── api/            # LLM接入：MultiProviderClient, OpenAI/Claude适配
│   ├── config/         # 配置：Settings, ConfigManager
│   ├── gateway/        # 网关：HTTP Server, Wire Protocol
│   ├── app/            # Web应用：FastAPI路由, Schema, Service
│   ├── desktop/        # 桌面：pywebview, 托盘, 更新检查
│   ├── tui/            # TUI：Textual终端界面
│   ├── mcp/            # 协议：A2A Client/Server, ACP
│   ├── security/       # 安全：Guardian, SkillScanner
│   ├── permission/     # 权限：RBAC, CredentialVault
│   ├── orchestrator/   # 编排：Conductor-Musician
│   ├── comm/           # 通信：9种渠道, 零成本模式
│   ├── compression/    # 压缩：ContextEngine处理器链
│   ├── studio/         # 工作流：AgentStudio引擎
│   ├── search/         # 搜索：DeepSearch深度搜索
│   └── sdk/            # SDK：Python客户端
├── skills/             # 94个技能包（MIClaw/OfficeClaw/WorkBuddy/Doubao）
├── pangu-model/        # 盘古模型（safetensors + 推理脚本）
├── pangu-env/          # 盘古独立venv（transformers 4.53.2）
├── studio-ui/          # React + Vite 前端
├── pyproject.toml      # 构建配置
└── build_windows.bat   # Windows构建脚本
```

---

## 技术栈

| 层 | 技术 |
|----|------|
| Agent 核心 | Python 3.11+, asyncio, ReAct, MCTS |
| 本地推理 | PyTorch 2.6 + transformers 4.53.2 (Pangu), llama-cpp-python 0.3.31 (Qwen GGUF) |
| Web 服务 | FastAPI, Uvicorn, SSE |
| 桌面应用 | pywebview, System Tray |
| TUI | Textual |
| Studio UI | React 18, Vite, @xyflow/react |
| 数据库 | SQLite + FTS5 |
| 安全 | cryptography (Fernet), RBAC |
| 协议 | A2A, ACP, MCP, OpenAI Compatible API |

---

## 端口管理

| 端口 | 服务 | 说明 |
|------|------|------|
| 8080 | Gateway | HTTP API 网关 |
| 8198 | Desktop | 桌面应用内嵌服务 |
| 8199 | Mini Engine | 本地模型 OpenAI 兼容 API |
| 5174 | Studio UI | Vite 开发服务器 |

---

## 许可证

MIT License

---

## 致谢

- [华为盘古 openPangu-Embedded-1B](https://ai.gitcode.com/ascend-tribe/openpangu-embedded-1b-model) — 端侧推理模型
- [PIKA665/openPangu-Embedded-1B](https://huggingface.co/PIKA665/openPangu-Embedded-1B) — GPU 版本
- [Qwen3.5](https://huggingface.co/Qwen) — 千问社区蒸馏模型
- [llama.cpp](https://github.com/ggerganov/llama.cpp) — GGUF 推理引擎
- 小米 MIClaw — 技能生态规范
- 华为 OfficeClaw — 办公自动化技能
- 腾讯 WorkBuddy — 办公技能精选
