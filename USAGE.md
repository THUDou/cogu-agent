# COGU AGENT 使用手册 v1.4.0

> Cognitive Unified Agent — 融合华为盘古 + 千问Qwen + 小米MIClaw + 腾讯WorkBuddy 的国产 AGENT 框架

---

## 一、环境要求

| 项目 | 要求 |
|------|------|
| Python | >= 3.11 |
| Node.js | >= 16 (Studio UI 需要) |
| 操作系统 | Windows / Linux / macOS |
| GPU | 可选（NVIDIA CUDA 用于本地模型加速） |
| LLM | 云端API Key（推荐）或 Ollama 或 内置MINI模型 |

---

## 二、安装

### 方式 1：从源码安装（推荐）

```bash
git clone https://github.com/THUDou/cogu-agent.git
cd cogu-agent/cogu_agent
pip install -e .
```

### 方式 2：从 ZIP 包安装

```bash
# 解压 COGU-AGENT-v1.4.0-Full.zip
cd cogu_agent
pip install -e .
```

### 方式 3：安装可选依赖

```bash
# 完整功能
pip install -e ".[comm,s3,server]"

# 仅 TUI
pip install -e ".[tui]"

# 开发模式
pip install -e ".[dev]"
```

### 配置 LLM 提供商

COGU 支持三种 LLM 接入方式，按优先级自动选择：

**1. 云端 API（推荐，质量最高）**

```bash
# DeepSeek（推荐，性价比最高）
cogu config set deepseek sk-your-api-key-here

# 华为云 MaaS（盘古云端）
cogu config set huawei_cloud sk-your-api-key-here

# 腾讯云混元
cogu config set tencent_cloud sk-your-api-key-here

# 其他：openai / claude / qwen / zhipu / moonshot / minimax / doubao
cogu config set openai sk-your-api-key-here
```

**2. Ollama 本地模型（需先安装 Ollama）**

```bash
# 安装 Ollama 后拉取模型
ollama pull qwen3
ollama pull llama3

# COGU 自动检测 Ollama（localhost:11434），无需额外配置
# 或手动指定：
cogu config set ollama
```

**3. 内置 MINI 模型（零配置，无需联网）**

COGU 内置两个本地模型，无云端 API 时自动启动：

| 模型 | 格式 | 大小 | 推理引擎 | 质量 |
|------|------|------|---------|------|
| Qwen3.5-0.8B | GGUF (Q5_K_M) | ~585MB | llama-cpp-python | 可用 |
| openPangu-Embedded-1B | safetensors | ~2.78GB | transformers 4.53.2 (独立venv) | 可用 |

```bash
# 手动启动本地模型服务
cogu pangu-mini serve          # 自动选择可用模型
cogu pangu-mini serve --local-model qwen   # 指定 Qwen
cogu pangu-mini serve --local-model pangu  # 指定盘古
cogu pangu-mini status         # 查看状态
```

> **注意**：盘古模型使用独立 venv（transformers 4.53.2），首次使用需运行 `build_windows.bat` 或手动创建：
> ```bash
> python -m venv pangu-env
> pangu-env\Scripts\pip install torch transformers==4.53.2 accelerate sentencepiece safetensors
> ```

---

## 三、五种交互模式

### 模式 1：CLI 命令行（最快上手）

```bash
# 直接对话
cogu run "帮我写一个 Python 快速排序"

# 指定模型
cogu run -m deepseek-chat "解释 ReAct 模式"

# 专家辩论
cogu debate "AI 会取代程序员吗" --mode standard --rounds 3

# 技能管理
cogu skills list --all          # 查看所有内置技能
cogu skills run hello-world     # 运行技能

# 记忆操作
cogu memory stats               # 记忆统计
cogu memory search "相关代码"    # 搜索记忆

# 配置管理
cogu config list                # 查看所有配置
cogu config set deepseek sk-xxx # 设置 API Key
```

### 模式 2：TUI 终端界面（交互式）

```bash
cogu tui
```

界面分三个面板：
- **F1** — 聊天面板（与 Agent 对话）
- **F2** — 辩论面板（专家思辨）
- **F3** — 记忆面板（搜索/查看记忆）
- **Ctrl+Q** — 退出

### 模式 3：Web API 服务（HTTP 接口）

```bash
# 启动服务
cogu serve --port 8080

# 浏览器访问
# Swagger UI:  http://127.0.0.1:8080/docs
# 健康检查:    http://127.0.0.1:8080/healthz
# 工作流 API:  http://127.0.0.1:8080/api/workflows
```

主要 API 端点：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat` | 发送消息（SSE 流式响应） |
| GET | `/api/agents` | 列出所有 Agent |
| GET | `/api/sessions` | 列出会话 |
| GET | `/api/memory/search?q=xxx` | 搜索记忆 |
| GET | `/api/workflows` | 列出工作流 |
| POST | `/api/workflows` | 创建工作流 |
| POST | `/api/workflows/{id}/run` | 运行工作流 |
| GET | `/api/workflows/{id}/mermaid` | 导出 Mermaid 图 |

### 模式 4：Studio UI 可视化编辑器（React 前端）

```bash
# 终端 1：启动后端 API
cogu serve --port 8080

# 终端 2：启动 Studio UI
cd studio-ui
npm install
npm run dev

# 浏览器访问 http://localhost:5174
```

Studio UI 功能：
- **可视化画布** — 拖拽节点、连线、缩放
- **8 种节点** — 开始 / 结束 / LLM 调用 / 工具调用 / 条件判断 / 代码执行 / 并行 / 人工输入
- **属性编辑** — 选中节点编辑 Prompt、工具名、条件表达式
- **保存/运行/验证** — 一键操作
- **Mermaid 导出** — 工作流 → 图表代码

### 模式 5：桌面应用（pywebview）

```bash
python -m cogu.desktop.loong
```

或直接运行 `COGU-Loong.exe`（Windows 安装包）。

---

## 四、核心功能详解

### 4.1 自进化系统

Agent 能自动优化自身的技能、记忆和 Prompt：

```python
from cogu.evolution import FitnessEvaluator, TraceAnalyzer, Trajectory

# 执行轨迹记录
traj = Trajectory(source="session_1")
traj.add_llm_call(model="deepseek-chat", messages=[...], usage={"input_tokens": 100})
traj.add_tool_call(tool_name="web_search", call_result="found results")

# 适应度评估
evaluator = FitnessEvaluator()
result = evaluator.evaluate(candidate="新版本技能", baseline="旧版本", test_cases=[...])
print(f"分数: {result.composite}")
```

### 4.2 超级记忆

多层记忆系统，支持 FTS5 全文搜索 + 向量检索 + 图记忆：

```python
from cogu.memory import TaskMemoryService, CodingMemory

# 任务记忆
tm = TaskMemoryService(workspace_dir="./workspace")
tm.add(content="修复 Python 导入错误的方法", title="Import Fix", label="python")
results = tm.retrieve("python import error", limit=5)

# 代码记忆
cm = CodingMemory(workspace_dir="./workspace", project_dir="/my/project")
cm.write("api-notes", "# API 笔记\n使用 REST 接口")
results = cm.search("REST API")
```

### 4.3 专家思辨

6 种专家角色进行多轮辩论：

```bash
cogu debate "量子计算的未来" --mode standard --rounds 3
```

专家角色：Proponent（支持者）、Critic（批评者）、Synthesizer（综合者）、FactChecker（事实核查）、DevilsAdvocate（魔鬼辩护）

### 4.4 A2A 协议

Agent-to-Agent 通信：

```python
from cogu.mcp import A2AClient, A2AServer, A2ATask, A2AAgentCard

# 客户端调用远程 Agent
client = A2AClient(agent_url="http://remote:8000")
card = await client.discover()
response = await client.send_task("帮我分析这段代码")

# 服务端暴露本 Agent
card = A2AAgentCard(name="code-analyzer", url="http://localhost:8000")
server = A2AServer(card=card, executor=my_executor)
```

### 4.5 深度搜索

知识增强的深度研究引擎：

```python
from cogu.search import DeepSearchEngine, WebSearchBackend

engine = DeepSearchEngine(search_backends=[WebSearchBackend()])
report = await engine.research("2025年 AI Agent 发展趋势", max_steps=5)
print(report.to_markdown())
```

### 4.6 工作流引擎

可视化工作流编排：

```python
from cogu.studio import WorkflowEngine, WorkflowDefinition, WorkflowNode, NodeType

wf = WorkflowDefinition(name="数据处理流水线")
wf.add_node(WorkflowNode(type=NodeType.START, label="开始"))
wf.add_node(WorkflowNode(type=NodeType.LLM, label="分析数据", config={"prompt": "分析以下数据..."}))
wf.add_node(WorkflowNode(type=NodeType.TOOL, label="保存结果", config={"tool": "file_write"}))
wf.add_node(WorkflowNode(type=NodeType.END, label="结束"))

engine = WorkflowEngine()
engine.save_workflow(wf)
state = await engine.run(wf, initial_vars={"data": "..."})
```

### 4.7 心跳唤醒 + 定时任务

```python
from cogu.core import HeartbeatService, HeartbeatConfig

# 心跳唤醒
config = HeartbeatConfig(interval_seconds=3600)  # 每小时
hs = HeartbeatService(config=config, workspace_dir=".", agent_handler=my_handler)
await hs.start()
```

```python
from cogu.core.rituals import CronJob, CronJobStore, ChannelType, ChannelTarget

# 定时任务
store = CronJobStore()
job = CronJob(
    name="日报生成",
    cron_expr="0 9 * * *",  # 每天 9 点
    targets=[ChannelTarget(channel_type=ChannelType.WEB, channel_id="main")],
)
store.create_job(job)
```

---

## 五、项目结构

```
cogu/
├── core/              ← 核心引擎 (ReAct Agent, 护栏, 推理链, 心跳, 定时任务)
├── memory/            ← 超级记忆 (FTS5 + 向量 + 图 + 任务记忆 + 代码记忆)
├── evolution/         ← 自进化 (技能/Prompt/记忆进化, 执行轨迹)
├── debate/            ← 思辨团队 (6 种专家, PES 引擎, 超图编排)
├── tools/             ← 工具系统 (可插拔注册, MCP, 原子进化, GUI Agent)
├── skills/            ← 技能系统 (Markdown 规范, 行为克隆)
├── mcp/               ← MCP 全栈 + A2A Agent-to-Agent 协议
├── search/            ← DeepSearch 知识增强深度搜索
├── studio/            ← AgentStudio 可视化工作流引擎
├── compression/       ← 上下文压缩 + ContextEngine 处理器链
├── comm/              ← 通信层 (HTTP/WebSocket/Matrix/gRPC/DingTalk)
├── state/             ← 共享状态 (内存/本地/S3 三后端)
├── permission/        ← 权限引擎 (RBAC, Fernet 加密)
├── middleware/         ← 洋葱中间件 (6 种内置)
├── observability/     ← 可观测性 (OTLP 追踪)
├── api/               ← LLM 接入 (DeepSeek/OpenAI/Claude/7 家)
├── config/            ← 配置管理
├── app/               ← Web 服务 (FastAPI + REST + SSE)
├── sdk/               ← Python SDK
├── gateway/           ← 网关 (Wire Protocol, JSONRPC2)
├── tui/               ← 终端 UI (Textual)
├── topology/          ← 声明式拓扑
├── orchestrator/      ← 多 Agent 编排 (指挥家-乐手)
├── desktop/           ← Windows 桌面 (pywebview)
└── mini_engine/       ← 盘古小模型 (本地推理)

studio-ui/             ← React + Vite 工作流可视化前端
```

---

## 六、端口管理

| 服务 | 默认端口 | 启动命令 |
|------|---------|---------|
| Web API | 8080 | `cogu serve --port 8080` |
| Studio UI | 5174 | `cd studio-ui && npm run dev` |
| 桌面应用 | 8198 | `python -m cogu.desktop.loong` |
| 盘古小模型 | 8199 | `cogu pangu-mini serve --port 8199` |

端口冲突时用 `--port` 参数更换。

---

## 七、常见问题

### Q: 启动报错 "API key not found"

```bash
cogu config set deepseek sk-your-key-here
# 或
set DEEPSEEK_API_KEY=sk-your-key
```

### Q: Studio UI 无法访问

1. 确认后端已启动：`cogu serve --port 8080`
2. 确认前端已启动：`cd studio-ui && npm run dev`
3. 浏览器访问 `http://localhost:5174`

### Q: 如何同时使用多种模式

```bash
# 终端 1：Web API
cogu serve --port 8080

# 终端 2：Studio UI
cd studio-ui && npm run dev

# 终端 3：CLI
cogu run "帮我写代码"

# 终端 4：TUI
cogu tui
```

### Q: 如何查看所有可用命令

```bash
cogu --help
cogu run --help
cogu debate --help
```

---

## 八、版本历史

| 版本 | 日期 | 主要更新 |
|------|------|---------|
| **v1.3.0** | 2026-06-14 | Studio UI 前端 + Workflow REST API + CLI studio 命令 |
| **v1.2.0** | 2026-06-14 | A2A 协议 + DeepSearch + ContextEngine + 工作流引擎 |
| **v1.1.0** | 2026-06-14 | Heartbeat + TaskMemory + CodingMemory + Trajectory + CronJob |
| **v1.0.0** | 2026-06-14 | 自进化系统 + 9 大增量升级 |

---

## 九、许可证

MIT License
