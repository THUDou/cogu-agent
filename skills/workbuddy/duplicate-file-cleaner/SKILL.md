---
name: duplicate-file-cleaner
description: 智能文件管家：扫描识别重复文件、风险评估、智能整理与安全清理；当用户需要清理重复文件、释放磁盘空间、整理照片库或规范化文件管理时使用
---

# 智能文件管家

## 任务目标
- 本 Skill 用于：从多个维度扫描识别重复文件，提供风险评估和智能整理建议，确保安全清理
- 能力包含：
  - 多维度重复识别（内容、元数据、综合）
  - 智能风险评估与分级建议
  - 多策略文件整理（按类型、日期、大小）
  - 四重安全保障（备份、确认、日志、撤销）
  - OpenClaw SDK 标准化接口
- 触发条件：用户提到"重复文件"、"清理磁盘"、"整理照片"、"释放空间"、"文件分类"等需求

## 操作步骤

### 1. 扫描阶段
- 调用 `scripts/duplicate_scanner.py` 执行扫描：
  ```bash
  python /workspace/projects/duplicate-file-cleaner/scripts/duplicate_scanner.py \
    --directory <扫描目录> \
    --strategy comprehensive \
    --output scan_report.json
  ```
- 参数说明：
  - `--directory`：必填，要扫描的目录
  - `--strategy`：识别策略（comprehensive/综合、content/内容、metadata/元数据）
  - `--output`：输出报告文件路径
  - `--min-size`：最小文件大小（字节），默认 1024
  - `--extensions`：文件扩展名过滤（如 jpg,png,pdf）

### 2. 风险评估阶段
- 调用 `scripts/risk_assessor.py` 评估操作风险：
  ```bash
  python /workspace/projects/duplicate-file-cleaner/scripts/risk_assessor.py \
    --input scan_report.json \
    --output risk_report.json
  ```
- 输出包含：
  - 风险等级（low/medium/high）
  - 风险评分（0-100）
  - 风险因素列表
  - 操作建议

### 3. 智能整理阶段（可选）
- 根据需要调用 `scripts/file_organizer.py` 整理文件：
  ```bash
  python /workspace/projects/duplicate-file-cleaner/scripts/file_organizer.py \
    --directory <源目录> \
    --output <目标目录> \
    --strategy type \
    --dry-run
  ```
- 整理策略：
  - `type`：按文件类型（图片、文档、音频等）
  - `date`：按创建/修改日期
  - `size`：按文件大小（小、中、大、超大）

### 4. 安全清理阶段
- 调用 `scripts/safety_manager.py` 执行安全删除：
  ```bash
  python /workspace/projects/duplicate-file-cleaner/scripts/safety_manager.py \
    --delete \
    --files <文件列表> \
    --backup-first
  ```
- 安全功能：
  - 删除前自动备份
  - 支持一键恢复
  - 操作日志记录
  - 旧备份自动清理

### 5. 智能体分析阶段
- 智能体解读报告，提供个性化建议：
  - 基于风险等级推荐清理策略
  - 识别高价值文件建议保留
  - 生成删除清单（标注高风险文件）
  - 提供文件分类整理建议

## 资源索引
- 核心扫描：[scripts/duplicate_scanner.py](scripts/duplicate_scanner.py)（用途：多维度重复文件扫描）
- 风险评估：[scripts/risk_assessor.py](scripts/risk_assessor.py)（用途：评估清理操作风险）
- 文件整理：[scripts/file_organizer.py](scripts/file_organizer.py)（用途：按策略整理文件）
- 安全管理：[scripts/safety_manager.py](scripts/safety_manager.py)（用途：备份、恢复、安全删除）
- 参考指南：[references/file-organization-guide.md](references/file-organization-guide.md)（何时读取：需要了解文件整理最佳实践）

## 注意事项
- ⚠️ 高风险操作时，建议用户先使用 `--dry-run` 预览模式
- ⚠️ 系统目录（Windows/System32、Program Files）建议谨慎操作
- ⚠️ 删除操作默认启用备份功能，支持30天内撤销
- 扫描策略选择：
  - `comprehensive`：最准确，速度较慢（推荐）
  - `content`：仅识别内容完全相同的文件
  - `metadata`：速度快，可能包含误报
- 智能体会基于文件路径、修改时间、类型提供保留建议

## 使用示例

### 示例1：扫描照片库并评估风险
```bash
# 综合扫描照片
python scripts/duplicate_scanner.py \
  --directory ~/Pictures \
  --strategy comprehensive \
  --output photos_report.json

# 评估风险
python scripts/risk_assessor.py \
  --input photos_report.json \
  --output photos_risk.json
```
智能体分析后建议保留拍摄时间最早的版本，并标注可能的重要照片。

### 示例2：安全清理下载目录
```bash
# 扫描下载目录
python scripts/duplicate_scanner.py \
  --directory ~/Downloads \
  --strategy content \
  --output downloads_report.json

# 安全删除（先备份）
python scripts/safety_manager.py \
  --delete \
  --files duplicate1.jpg,duplicate2.pdf \
  --backup-first
```
智能体会识别重复下载的资源文件，推荐删除多余副本，并保留原始文件。

### 示例3：整理工作文档
```bash
# 按文件类型预览整理
python scripts/file_organizer.py \
  --directory ~/Documents/Work \
  --output ~/Organized/Work \
  --strategy type \
  --dry-run

# 确认后执行
python scripts/file_organizer.py \
  --directory ~/Documents/Work \
  --output ~/Organized/Work \
  --strategy type \
  --execute
```
智能体会按文档、表格、演示文稿等分类整理，并提供文件移动预览。

### 示例4：全盘快速扫描
```bash
# 使用元数据策略快速扫描
python scripts/duplicate_scanner.py \
  --directory ~ \
  --strategy metadata \
  --min-size 102400 \
  --output full_scan.json
```
智能体会提示可能需要较长时间，并建议优先处理大文件和高风险目录。

## OpenClaw SDK 兼容性
- 所有脚本输出 JSON 格式符合 OpenClaw SDK 2.0.0 规范
- 标准化状态码和错误处理
- 支持通过命令行参数集成
- 完整的参数文档和使用示例

## 安全保障机制
1. **三级风险评估**：low/medium/high 分级，动态调整确认流程
2. **智能备份**：默认备份删除文件，支持自定义备份位置
3. **操作追溯**：完整记录所有操作，支持一键恢复
4. **撤销能力**：30天内可随时撤销清理操作
