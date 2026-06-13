## COGU Loong v0.9.1 — Windows Desktop Release

### 新增功能
- **Windows 桌面 EXE**：单文件可执行程序，双击即用
- **首次使用引导**：启动后自动检测 API 令牌，未配置则弹出引导界面
- **自定义服务商**：支持 DeepSeek / OpenAI / Claude / 智谱 / 通义 / Moonshot / 自定义
- **自定义 API 地址**：可配置任意 OpenAI 兼容 API 端点
- **Dashboard**：内置 Web Desktop 界面，Chat/Memory/Agents/Tools/Settings 五大面板
- **Memory Search API**：支持 Hybrid/FTS/Graph/Comprehensive 四种搜索策略
- **Settings API**：完整的 API 令牌管理、模型配置、盘古小模型隐藏设置
- **隐藏盘古小模型**：设置页三击版本号可展开盘古 Mini 配置区（不推荐启用）

### 使用方法
1. 下载 `COGU-Loong.exe`
2. 双击运行
3. 首次启动自动打开浏览器，按引导配置 API 令牌
4. 开始对话

### 技术栈
- Python 3.13 + FastAPI + Uvicorn + PyInstaller
- 暗色主题 WorkBuddy 风格 UI
- SSE 流式对话
- SQLite FTS5 记忆搜索