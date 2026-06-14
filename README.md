# COGU AGENT

> **Cognitive Unified Agent** — 融合华为 JiuwenCLAW 基座、小米 MiMo 超级记忆、百度 LoongFlow 专家思辨、DeepSeek 优化的国产 AGENT 框架

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/version-1.3.0-orange.svg" alt="Version">
</p>

## ✨ 特性

- 🧠 **自进化系统** - 技能、记忆、Prompt 自动进化
- 📚 **超级记忆** - FTS5 + 向量 + 图 + 分级压缩 + Dream
- 💬 **专家思辨** - 6 种专家、5 种协调、PES 引擎、超图编排
- 🔧 **工具系统** - 可插拔注册、MCP 协议、原子进化
- 🤝 **A2A 协议** - Agent-to-Agent 通信协议
- 🔍 **深度搜索** - 查询规划 → 多步搜索 → 来源溯源 → 报告生成
- 🎨 **可视化工作流** - AgentStudio 工作流引擎
- 💓 **心跳唤醒** - 周期性 Agent 唤醒
- 📝 **任务记忆** - 任务级经验检索与存储
- 🖥️ **五种模式** - CLI / TUI / WEB / Studio UI / 原生桌面应用

## 🚀 快速开始

### 方式一：从源码安装

```bash
# 克隆项目
git clone https://github.com/your-username/cogu-agent.git
cd cogu-agent

# 安装依赖
pip install -e .

# 配置 API 密钥
cogu config set deepseek sk-your-api-key-here

# 开始使用！
cogu run "你好，COGU！"
```

### 方式二：使用安装包（Windows）

下载最新的 `COGU-Loong-Setup.exe`，双击安装即可。

## 🎯 五种使用模式

### 📟 CLI 命令行模式

```bash
# 直接对话
cogu run "帮我写一个 Python 排序算法"

# 专家辩论
cogu debate "AI 会取代程序员吗" --mode standard --rounds 3

# 技能管理
cogu skills list --all
cogu skills install /path/to/skill

# 记忆搜索
cogu memory search "相关代码"

# 查看配置
cogu config list
```

### 🖥️ TUI 终端界面（类似 DeepSeek-TUI）

```bash
cogu tui
```

快捷键：
- `Ctrl+Q` - 退出
- `F1` - 聊天
- `F2` - 辩论
- `F3` - 记忆

### 🌐 WEB API 服务

```bash
cogu serve --port 8080
```

- Swagger UI: http://127.0.0.1:8080/docs
- 健康检查: http://127.0.0.1:8080/healthz

### 🎨 Studio UI 前端（React + Vite）

```bash
cogu studio --port 5174
```

访问: http://localhost:5174

### 💻 CLAW 类原生桌面应用

```bash
# 从源码启动
python -m cogu.desktop.loong

# 或运行打包的 EXE
# COGU-Loong.exe
```

## 🔧 配置 API 令牌

### 支持的 AI 提供商

| 提供商 | 环境变量 | 默认模型 | 配置命令 |
|--------|----------|----------|----------|
| DeepSeek | `DEEPSEEK_API_KEY` | deepseek-chat | `cogu config set deepseek sk-xxx` |
| OpenAI | `OPENAI_API_KEY` | gpt-4o | `cogu config set openai sk-xxx` |
| Claude | `CLAUDE_API_KEY` | claude-sonnet-4 | `cogu config set claude sk-xxx` |
| 智谱 GLM | `ZHIPU_API_KEY` | glm-4-plus | `cogu config set zhipu sk-xxx` |
| 通义千问 | `QWEN_API_KEY` | qwen-max | `cogu config set qwen sk-xxx` |
| Moonshot | `MOONSHOT_API_KEY` | moonshot-v1-128k | `cogu config set moonshot sk-xxx` |
| SiliconFlow | `SILICONFLOW_API_KEY` | DeepSeek-V3 | `cogu config set siliconflow sk-xxx` |

### 盘古小模型（隐藏功能）

在设置中启用盘古小模型（本地模型）：

```bash
# 查看状态
cogu pangu-mini status

# 启动服务
cogu pangu-mini serve --port 8199
```

## 📁 项目结构

```
cogu/
├── core/              # 核心引擎 (ReAct Agent, 护栏, 推理链)
├── memory/            # 超级记忆 (FTS5 + 向量 + 图)
├── evolution/         # 自进化 (技能/Prompt/记忆进化)
├── debate/            # 思辨团队 (专家, PES, 超图编排)
├── tools/             # 工具系统 (MCP, 原子进化)
├── skills/            # 技能系统 (Markdown 规范)
├── mcp/               # MCP 全栈 + A2A 协议
├── search/            # 深度搜索
├── studio/            # 工作流引擎
├── compression/       # 上下文压缩
├── app/               # Web 服务 (FastAPI + REST)
├── tui/               # 终端界面 (Textual)
└── desktop/           # 桌面应用 (pywebview)
```

## 🏗️ 架构总览

### v1.3.0 新增模块
- 🎨 **Studio UI** - React + Vite 前端界面
- 🔧 **Workflow API** - 工作流 REST API
- 📊 **Mermaid 导出** - 工作流可视化导出

### v1.2.0 新增模块
- 🤝 **A2A 协议** - Agent-to-Agent 通信
- 🔍 **深度搜索** - 知识增强搜索
- ⚡ **上下文引擎** - 处理器链
- 🎨 **工作流引擎** - AgentStudio 可视化

### v1.1.0 新增模块
- 💓 **心跳唤醒** - 周期性 Agent 唤醒
- 📝 **任务记忆** - 任务级经验检索
- 💻 **代码记忆** - 项目级代码记忆
- 📈 **执行轨迹** - 完整执行轨迹记录
- ⏰ **CronJob** - 持久化定时任务

## 📦 构建安装包

### Windows EXE 构建

```bash
cd cogu_agent
build_windows.bat
```

### 制作安装包

使用 Inno Setup 打开 `installer-inno.iss` 编译。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 🙏 致谢

项目设计灵感来自：
- 华为 JiuwenCLAW / OpenPangu
- 小米 MiMo
- 百度 LoongFlow
- DeepSeek
- Claude Code
- OpenClaw
- 以及其他优秀开源项目

---

**Made with ❤️ by COGU Team**
