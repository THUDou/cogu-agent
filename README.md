# COGU AGENT

**Cognitive Unified Agent** — 融合国内顶级开源智能体框架的 Python Agent 框架。

## 融合架构

| 层级 | 参考项目 | 功能 |
|------|----------|------|
| 基座引擎 | 华为 JiuwenCLAW | Agent Studio, 零代码可视化开发, 工作流编排 |
| 超级记忆 | 小米 MiMo-Code, 字节 M3-Agent | 5层混合记忆系统 (FTS5 + 嵌入图 + 实体关系图 + 分级压缩) |
| 思辨团队 | 百度 LoongFlow, AgentScope CoPaw | 专家思辨团 (6种角色), 5种协调模式, PES引擎 |
| 核心代理 | DeepSeek-TUI, OpenClaw | ReAct Agent, 4级护栏系统 |
| 工具系统 | 网易 LobsterAI | 可插拔工具注册, 内置6种文件/Shell工具 |
| 技能系统 | Claude Code | Skill Registry, 自动发现与加载 |
| TUI | DeepSeek-TUI, OpenClaw | Textual 终端 UI, Chat/Debate/Memory 三面板 |

## 安装

```bash
pip install -e .
```

## 使用

```bash
cogu run "your prompt"
cogu debate "your topic"
cogu skills list
cogu memory search "keyword"
cogu tui
```

## 开发

```bash
pip install -e ".[dev]"
ruff check cogu/
```
