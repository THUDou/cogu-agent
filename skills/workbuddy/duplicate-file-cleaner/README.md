# Duplicate File Cleaner - 智能文件管家

## 安装说明

本技能包包含完整的智能文件管理功能。

## 文件清单

- `duplicate-file-cleaner.skill` - 主技能包文件
  - SKILL.md - 技能入口与使用指南
  - scripts/ - 可执行脚本目录
    - duplicate_scanner.py - 重复文件扫描器（多维度识别）
    - risk_assessor.py - 风险评估引擎
    - file_organizer.py - 智能文件整理器
    - safety_manager.py - 安全管理器
  - references/ - 参考文档目录
    - file-organization-guide.md - 文件整理最佳实践指南

## 核心功能

1. **多维度重复识别**
   - 内容识别（基于文件哈希）
   - 元数据识别（基于文件名、大小、修改时间）
   - 综合识别（合并两种策略）

2. **智能风险评估**
   - 三级风险等级（low/medium/high）
   - 多维度评分系统
   - 个性化操作建议

3. **智能文件整理**
   - 按文件类型整理（12大类）
   - 按日期整理（年月分类）
   - 按文件大小整理（4个等级）

4. **四重安全保障**
   - 智能备份（删除前自动备份）
   - 多级确认（根据风险等级调整）
   - 操作日志（完整记录历史）
   - 撤销恢复（一键恢复文件）

## OpenClaw SDK 兼容性

- SDK 版本：2.0.0
- 输出格式：标准化 JSON
- 状态码：统一错误处理
- 集成方式：命令行接口

## 快速开始

### 1. 扫描重复文件

```bash
python scripts/duplicate_scanner.py \
  --directory ~/Downloads \
  --strategy comprehensive \
  --output scan_report.json
```

### 2. 评估风险

```bash
python scripts/risk_assessor.py \
  --input scan_report.json \
  --output risk_report.json
```

### 3. 整理文件

```bash
python scripts/file_organizer.py \
  --directory ~/Documents \
  --output ~/Organized \
  --strategy type \
  --execute
```

### 4. 安全删除

```bash
python scripts/safety_manager.py \
  --delete \
  --files file1.txt,file2.jpg \
  --backup-first
```

## 使用场景

- 清理重复文件释放磁盘空间
- 整理照片库和文档
- 按类型、日期、大小分类文件
- 安全删除重要文件（带备份）
- 批量文件整理和归档

## 技术要求

- Python 3.7+
- 仅使用 Python 标准库，无需额外安装依赖

## 版本信息

- 版本：2.0.0
- 更新日期：2024-04-21
- OpenClaw SDK：2.0.0

## 注意事项

1. 首次使用建议先运行 `--dry-run` 预览模式
2. 系统目录建议谨慎操作
3. 删除操作默认启用备份功能
4. 建议定期清理旧备份文件

## 支持

详细文档请参考 SKILL.md 和 references/file-organization-guide.md
