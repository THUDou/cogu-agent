# COGU Agent 端口管理说明

本文档详细说明 COGU Agent 各服务使用的端口，帮助用户避免端口冲突并正确配置。

---

## 📊 端口总览

| 服务名称 | 默认端口 | 配置参数 | 协议 | 说明 |
|---------|---------|----------|------|------|
| **Gateway (Web API)** | `8080` | `cogu serve --port <PORT>` | HTTP + SSE | FastAPI 后端服务，提供 REST API 和 SSE 流式接口 |
| **Studio UI (前端)** | `5174` | `cogu studio --port <PORT>` | HTTP | Vite 开发服务器，React 前端界面 |
| **Studio UI (后端 API)** | `8080` | `cogu studio --api-port <PORT>` | HTTP | Studio UI 连接的后端 API 端口 |
| **桌面应用 (后端)** | `8198` | 硬编码（暂不支持配置） | HTTP | pywebview 桌面应用的后端 FastAPI 服务 |
| **Pangu Mini (本地模型)** | `8199` | `cogu pangu-mini serve --port <PORT>` | HTTP | openPangu-Embedded-1B 本地推理服务 |

---

## 🚀 常见启动场景与端口配置

### 场景 1：只启动 CLI 模式

```bash
cogu run "你好，COGU！"
```

- **端口使用**：❌ 不使用任何端口
- **适用场景**：命令行快速交互、脚本集成

---

### 场景 2：启动 TUI 终端界面

```bash
cogu tui
```

- **端口使用**：❌ 不使用任何端口
- **适用场景**：终端界面交互、本地使用

---

### 场景 3：启动 Web API 服务

```bash
# 启动后端 API 服务（默认端口 8080）
cogu serve

# 自定义端口
cogu serve --port 8081
```

- **端口使用**：✅ `8080`（或自定义端口）
- **访问地址**：
  - Swagger UI: http://127.0.0.1:8080/docs
  - 健康检查: http://127.0.0.1:8080/healthz
- **适用场景**：HTTP API 调用、远程访问、前端集成

---

### 场景 4：启动 Studio UI（可视化工作流编辑器）

```bash
# 第一步：启动后端 API 服务（新终端窗口）
cogu serve --port 8080

# 第二步：启动 Studio UI 前端（会自动打开浏览器）
cogu studio --port 5174 --api-port 8080
```

- **端口使用**：✅ `5174` (前端) + `8080` (后端 API)
- **访问地址**：
  - Studio UI: http://localhost:5174
  - 后端 API: http://127.0.0.1:8080/docs
- **适用场景**：可视化工作流编辑、团队协作、工作流调试

---

### 场景 5：启动桌面应用

```bash
# 从源码启动
python -m cogu.desktop.loong

# 或双击运行打包的 EXE
COGU-Loong.exe
```

- **端口使用**：✅ `8198` (后端 FastAPI)
- **访问地址**：桌面应用窗口自动打开，无需手动访问端口
- **适用场景**：类原生桌面体验、最方便的日常使用

---

## 🚨 端口冲突排查

### 问题：端口已被占用

**错误信息**：
```
OSError: [Errno 98] Address already in use
```

**解决方案**：

#### 方案 1：更换端口

```bash
# Web API 服务改用端口 8081
cogu serve --port 8081

# Studio UI 前端改用端口 5175
cogu studio --port 5175 --api-port 8081
```

#### 方案 2：查找并关闭占用端口的进程

**Windows**:
```bash
# 查找占用端口 8080 的进程
netstat -ano | findstr :8080

# 结束进程（替换 <PID> 为实际进程 ID）
taskkill /PID <PID> /F
```

**macOS / Linux**:
```bash
# 查找占用端口 8080 的进程
lsof -i :8080

# 结束进程（替换 <PID> 为实际进程 ID）
kill -9 <PID>
```

---

## 🔧 端口配置最佳实践

### 1. 开发环境推荐配置

| 服务 | 推荐端口 | 原因 |
|------|---------|------|
| Gateway (Web API) | `8080` | 默认配置，与文档一致 |
| Studio UI (前端) | `5174` | Vite 默认端口，避免冲突 |
| 桌面应用 (后端) | `8198` | 与 Gateway 区分，互不干扰 |
| Pangu Mini | `8199` | 与桌面应用后端相邻，便于记忆 |

### 2. 生产环境推荐配置

| 服务 | 推荐端口 | 原因 |
|------|---------|------|
| Gateway (Web API) | `80` / `443` | HTTP / HTTPS 标准端口 |
| Studio UI (前端) | `3000` / `8443` | 反向代理到标准端口 |
| 桌面应用 (后端) | 不暴露 | 仅本地访问，无需对外暴露 |
| Pangu Mini | `8199` | 仅本地访问，无需对外暴露 |

### 3. 多实例部署

如果需要同时运行多个 COGU Agent 实例，使用不同端口：

```bash
# 实例 1（默认端口）
cogu serve --port 8080 &

# 实例 2（自定义端口）
cogu serve --port 8081 &

# 实例 3（自定义端口）
cogu serve --port 8082 &
```

---

## 📋 端口快速参考表

| 如果你想要... | 使用的命令 | 需要的端口 |
|-------------|------------|---------|
| 命令行快速交互 | `cogu run "..."` | 无需端口 |
| 终端界面交互 | `cogu tui` | 无需端口 |
| 启动 Web API | `cogu serve` | `8080` |
| 使用 Studio UI | `cogu studio` | `5174` + `8080` |
| 启动桌面应用 | `python -m cogu.desktop.loong` | `8198` |
| 启动本地模型 | `cogu pangu-mini serve` | `8199` |

---

## 💡 常见问题

### Q1：可以同时启动多个服务吗？

**答案**：✅ 可以！但需要确保端口不冲突。

**推荐启动顺序**：
```bash
# 终端窗口 1：启动 Gateway
cogu serve --port 8080

# 终端窗口 2：启动 Studio UI（连接已有的 Gateway）
cogu studio --port 5174 --api-port 8080

# 终端窗口 3：启动桌面应用（独立运行，不影响其他服务）
python -m cogu.desktop.loong
```

---

### Q2：如何查看当前哪些端口正在被使用？

**A2**：使用以下命令：

**Windows**:
```bash
netstat -ano | findstr :8080
netstat -ano | findstr :5174
```

**macOS / Linux**:
```bash
lsof -i :8080
lsof -i :5174
```

---

### Q3：可以修改桌面应用的端口吗？

**A3**：当前版本（v1.3.0）桌面应用后端端口 `8198` 是硬编码的，暂不支持通过命令行参数修改。

**未来版本**：计划增加配置选项：
```bash
python -m cogu.desktop.loong --port 8199
```

---

## 📚 相关文档

- [README.md](../README.md) - 项目概览与快速开始
- [配置 API 令牌](#配置-api-令牌) - 如何配置 LLM 提供商
- [五种使用模式](#五种使用模式) - 详细说明每种模式的使用方法

---

**最后更新**：2026-06-15  
**对应版本**：COGU Agent v1.3.0
