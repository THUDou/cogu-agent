# 文件整理最佳实践指南

## 目录
1. 概览
2. 文件保留策略
3. 风险评估与防范
4. 整理策略选择
5. 常见场景处理建议
6. 批量操作与自动化
7. OpenClaw 集成指南

## 概览
本指南提供智能文件管理的最佳实践，帮助用户安全、高效地整理文件并释放磁盘空间。

升级版技能包含以下核心能力：
- 多维度重复识别
- 智能风险评估
- 多策略文件整理
- 四重安全保障

## 文件保留策略

### 1. 基于文件路径
- **优先保留规则**：
  - 主目录 > 子目录 > 临时目录
  - 原始文件夹 > 备份文件夹 > 下载文件夹
  - Documents/Personal > Downloads/Desktop
  - 摄影师应保留原始文件夹而非临时文件夹

### 2. 基于修改时间
- **原则**：
  - 对于照片：保留拍摄时间最早的原始文件
  - 对于文档：保留修改时间最新的版本（除非有特殊版本控制需求）
  - 对于媒体文件：保留编辑过的版本（如有明显后期处理）
- **智能判断**：
  - 系统会自动分析文件命名模式
  - 识别可能的编辑版本（如 photo_edited.jpg）

### 3. 基于文件名
- **推荐保留**：
  - 原始文件名（如 IMG_20240101_120000.jpg）
  - 描述性文件名（如 vacation-beach.jpg）
  - 包含日期或地点信息的文件名
- **可删除**：
  - 包含 copy、duplicate、副本 等字样的文件名
  - 包含数字后缀且无明显规律的文件名（如 file (1).txt）
  - 临时文件名（如 ~$file.docx）

### 4. 基于文件类型
- **高风险文件**：
  - 办公文档（.docx, .xlsx, .pdf）：建议人工确认
  - 可执行文件（.exe, .app）：需特别谨慎
  - 系统文件（.dll, .so）：禁止自动删除
- **低风险文件**：
  - 媒体文件（.jpg, .mp3, .mp4）：可安全删除重复文件
  - 压缩包（.zip, .rar）：确认内容后可删除
  - 临时文件（.tmp, .cache）：可安全清理

## 风险评估与防范

### 风险等级说明
- **High（高风险）**：
  - 重复文件超过1000个
  - 包含办公文档或可执行文件
  - 扫描系统目录或重要工作目录
  - 建议操作：手动选择，严格备份

- **Medium（中等风险）**：
  - 重复文件100-1000个
  - 扫描用户文档目录
  - 可释放空间超过1GB
  - 建议操作：谨慎清理，备份后操作

- **Low（低风险）**：
  - 重复文件少于100个
  - 主要为媒体文件
  - 扫描下载目录或临时目录
  - 建议操作：可安全清理，建议预览

### 备份策略
1. **自动备份**：
   - 使用 `safety_manager.py --delete --backup-first`
   - 备份文件默认保存在 `~/.file_cleaner_backup/`
   - 支持自定义备份目录

2. **操作前备份**：
   - 对于重要文件夹，先创建完整备份
   - 可使用外部硬盘、云存储进行备份
   - 记录备份位置和恢复方法

3. **渐进式清理**：
   - 先从低风险目录开始（Downloads, Desktop）
   - 再处理中等风险目录（Documents, Pictures）
   - 最后处理高风险目录（系统目录、项目文件）

### 禁止操作的目录
- Windows:
  - `C:\Windows\System32`
  - `C:\Program Files`
  - `C:\Program Files (x86)`
  - `C:\Windows\System32\drivers`
- macOS:
  - `/System`
  - `/Library`
  - `/usr/bin`
  - `/System/Library`
- Linux:
  - `/usr/bin`
  - `/etc`
  - `/var`
  - `/opt`

## 整理策略选择

### 按文件类型整理（type）
**适用场景**：
- 杂乱的下载目录
- 多种格式混合的文件夹
- 需要按类型归档的文件

**分类类别**：
- Images：图片（.jpg, .png, .gif, .svg）
- Documents：文档（.docx, .pdf, .txt）
- Spreadsheets：表格（.xlsx, .csv）
- Presentations：演示文稿（.pptx）
- Audio：音频（.mp3, .wav, .flac）
- Video：视频（.mp4, .avi, .mkv）
- Archives：压缩包（.zip, .rar）
- Code：代码文件（.py, .js, .html）

### 按日期整理（date）
**适用场景**：
- 照片库整理
- 按时间归档的文档
- 需要按月份或年份分类的文件

**分类方式**：
- 按修改日期：`YYYY-MM` 格式
- 按创建日期：`YYYY-MM` 格式
- 示例：2024-01/, 2024-02/, ...

### 按文件大小整理（size）
**适用场景**：
- 需要清理大文件释放空间
- 分析磁盘占用情况
- 归档小文件到单独目录

**分类类别**：
- Small：小于 1MB
- Medium：1MB - 100MB
- Large：100MB - 1GB
- Very Large：大于 1GB

## 常见场景处理建议

### 照片整理
**保留策略**：
- 保留拍摄时间最早的原始文件
- 保留编辑过的版本（如有明显后期处理）
- 保留文件夹结构更规范的文件

**删除策略**：
- 删除屏幕截图的重复版本
- 删除社交媒体缓存的图片副本
- 删除临时文件夹中的照片

**风险提示**：中等风险，建议备份后操作

### 文档整理
**保留策略**：
- 保留修改时间最新的版本（除非有特殊版本控制需求）
- 保留原始文件夹中的文件
- 保留有明确命名规范的文件

**删除策略**：
- 删除"~$"开头的临时文件（Office自动生成的副本）
- 删除Downloads中的重复文档
- 删除 `.tmp` 临时文件

**风险提示**：高风险，必须人工确认

### 媒体文件整理
**保留策略**：
- 保留质量更高的版本（可通过文件名中的标识判断，如 1080p, 4K, FLAC）
- 保留播放列表中的引用位置
- 保留元数据完整的文件

**删除策略**：
- 删除预览文件或缓存文件
- 删除重复下载的相同文件
- 删除低质量转码文件

**风险提示**：低风险，可安全清理

### 代码和配置文件
**警告**：⚠️ 特别谨慎，可能影响系统或项目运行

**建议**：
- 不建议自动删除，需人工确认每个文件
- 优先保留项目根目录的文件
- 保留有明确版本控制的文件
- 使用版本控制系统（Git）而非文件删除

**风险提示**：极高风险，必须人工确认

## 批量操作与自动化

### 预览模式
所有整理和删除操作都支持预览模式：
```bash
# 预览整理
python scripts/file_organizer.py --directory ~/Downloads --output ~/Organized --strategy type --dry-run

# 查看预览结果后再执行
python scripts/file_organizer.py --directory ~/Downloads --output ~/Organized --strategy type --execute
```

### 批量删除脚本生成
智能体可根据扫描报告生成删除脚本：
1. 分析扫描报告和风险评估
2. 生成删除清单（标注高风险文件）
3. 生成批量删除命令或脚本
4. 建议逐批执行，每批处理后验证系统运行

### 分批处理建议
- 按文件大小分批：先处理大文件（释放更多空间）
- 按文件类型分批：先处理媒体文件，再处理文档
- 按目录分批：一次处理一个目录，降低风险

### 自动化工作流
```bash
# 1. 扫描
python scripts/duplicate_scanner.py --directory ~/Downloads --output scan.json

# 2. 评估风险
python scripts/risk_assessor.py --input scan.json --output risk.json

# 3. 查看结果（人工确认）
cat risk.json

# 4. 安全删除（低风险文件可自动执行）
python scripts/safety_manager.py --delete --files file1.txt,file2.jpg --backup-first
```

## OpenClaw 集成指南

### SDK 兼容性
- 所有脚本输出符合 OpenClaw SDK 2.0.0 规范
- 标准化 JSON 输出格式
- 统一的状态码和错误处理

### 集成示例
```python
import json
import subprocess

# 扫描重复文件
result = subprocess.run(
    ['python', 'scripts/duplicate_scanner.py',
     '--directory', '~/Pictures',
     '--output', 'scan.json'],
    capture_output=True,
    text=True
)

# 解析结果
scan_data = json.loads(result.stdout)

# 风险评估
risk_result = subprocess.run(
    ['python', 'scripts/risk_assessor.py',
     '--input', 'scan.json'],
    capture_output=True,
    text=True
)

risk_data = json.loads(risk_result.stdout)

# 根据风险等级决定操作
if risk_data['risk_level'] == 'low':
    # 安全删除
    pass
else:
    # 人工确认
    pass
```

### 输出格式规范
所有脚本输出 JSON 包含以下字段：
- `status`：操作状态（success/error）
- `timestamp`：操作时间
- 错误信息：`error` 字段
- 详细数据：根据具体脚本而定

## 注意事项

1. **文件名编码**：某些特殊字符可能导致脚本执行失败
2. **权限问题**：系统文件可能需要管理员权限才能删除
3. **符号链接**：注意区分实际文件和符号链接，避免误删原始文件
4. **隐藏文件**：检查隐藏文件（以.开头）是否需要处理
5. **跨平台兼容**：注意不同操作系统的路径分隔符
6. **性能考虑**：大规模目录扫描可能需要较长时间

## 示例场景

### 场景1：清理Downloads目录
```
扫描策略: content（内容识别）
最小文件: 10KB
文件类型: 全部
风险等级: low
建议: 直接清理，建议先备份
```

### 场景2：整理照片库
```
扫描策略: comprehensive（综合识别）
最小文件: 50KB
文件类型: jpg, png, heic, raw
风险等级: medium
建议: 备份后操作，保留拍摄时间最早的版本
```

### 场景3：整理工作文档
```
扫描策略: comprehensive（综合识别）
最小文件: 1KB
文件类型: docx, xlsx, pptx, pdf
风险等级: high
建议: 必须人工确认，保留修改时间最新的版本
```

### 场景4：全盘扫描
```
扫描策略: metadata（元数据识别，速度更快）
最小文件: 100KB
文件类型: 全部
风险等级: 取决于扫描目录
建议: 分批处理，先处理Downloads，再处理Documents
```
