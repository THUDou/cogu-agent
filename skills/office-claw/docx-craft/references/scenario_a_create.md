# Pipeline A: 创建新文档场景指南

## 适用场景

- 用户要求从零创建一个 Word 文档
- 用户提供了主题和/或内容，需要生成 .docx 文件
- 信号: "写一份报告", "创建文档", "生成文档", "draft a proposal"

## 决策流程

### 1. 判断是否需要检索

**不需要检索**:
- 用户提供了完整内容或完整大纲
- 纯格式转换/排版任务（数据已有）
- 简单通知/备忘录/信函
- 填充模板（数据已有）

**需要检索**:
- 涉及行业/市场分析 → 需要最新数据和趋势
- 学术论文需要文献支撑 → 需要引用和综述素材
- 技术报告需要最新数据 → 需要最新技术动态
- 竞品分析/对比研究 → 需要对比数据
- 政策/法规解读 → 需要政策原文和解读

### 2. 准备输出目录

Pipeline 执行研究前，先创建时间戳输出目录：

```bash
node {skill_root}/docx-craft/scripts/utils/generate_timestamp_dir.js output/
```

> 如脚本不存在，手动创建目录：`output/YYYYMMDD_HHMMSS_000/`

脚本返回完整路径，如：`output/20260317_143052_000/`，赋值给 `{output_dir}`。

**用户指定路径时**：如用户明确指定输出目录，则使用用户指定路径。

### 3. 执行检索（需要时）

通过 Agent tool 启动 subagent 调用 **deepresearch-writer** skill:

```
Agent({
  "subagent_type": "general-purpose",
  "description": "Deep research for document content",
  "prompt": "请基于以下信息执行深度内容研究，生成研究报告。\n\n主题: {topic}\n研究深度: {research_depth}\n搜索模式: {search_mode}\n研究方向: {directions}\n\n<!-- 【有文档素材时保留此段落，无素材时删除】 -->\n**用户提供的文档资料**：\n<uploaded_document>\n{doc_content}\n</uploaded_document>\n\n搜索模式说明：\n- auto：根据素材充裕度自动决定是否搜索\n- no_search：禁止搜索，纯素材模式\n- force_search：强制完整研究流程\n\n**输出路径**：\n\n- 输出目录：{output_dir}\n- 研究报告：research.md\n\n使用 deepresearch-writer 技能执行。将产物写入 {output_dir}/ 目录下。"
})
```

**search_mode 选择**:

| 场景 | search_mode |
|------|-------------|
| 用户要求"最新数据""趋势""市场分析" | `force_search` |
| 用户主题宽泛、缺少材料 | `auto` |
| 用户上传了内容充实的文档 | `auto` |
| 用户明确要求"不搜索""只按给定材料" | `no_search` |
| 用户提供了完整内容/大纲 | `no_search` |

**research_depth 选择**:

| 场景 | research_depth |
|------|---------------|
| 简报/通知/备忘录 | `L1` |
| 标准商业报告/方案 | `L2` |
| 学术论文/深度行业报告 | `L3` |

**研究方向提示**:
- 行业报告 → 市场规模/竞争格局/趋势预测
- 学术论文 → 文献综述/方法论/最新进展
- 技术报告 → 技术现状/对比分析/案例数据
- 政策解读 → 政策原文/影响范围/合规要求

### 4. 验证研究产物

研究 subagent 完成后，检查 `{output_dir}/research.md` 是否存在且非空。如缺失，重试一次。

### 5. 整合研究内容

读取 `{output_dir}/research.md`，将研究结果转化为 `content.json` 格式：

- `## 建议文档结构` → Heading 层级结构
- `#### 研究分析` → 正文段落
- `关键数据清单` → 表格数据
- `时序数据` → 表格数据
- `对比数据` → 表格数据
- `## 来源汇总` → 参考文献

可使用 `python scripts/research.py` 中的 `convert_research_to_content()` 作为参考。

### 6. 选择模板配方

| 文档类型 | 配方 | 关键特征 |
|----------|------|----------|
| 学术论文/综述 | academic | Times New Roman/SimSun, 12pt, 双倍行距, A4 |
| 商业报告/分析 | report | Calibri/微软雅黑, 11pt, 1.15行距, 蓝色标题 |
| 公文/通知/函件 | government | 仿宋/小标宋, 三号字(16pt), GB/T 9704 |
| 备忘录 | memo | Arial, 11pt, 1.15行距 |
| 信函 | letter | Calibri, 11pt, 单倍行距 |

用 `python scripts/template_match.py --type "描述"` 辅助匹配。

### 7. 生成文档

```bash
node scripts/create.js \
  --recipe <配方名> \
  --content <content.json> \
  --output <输出路径> \
  [--title "标题"] \
  [--author "作者"] \
  [--page-size a4|letter] \
  [--margins standard|narrow|wide] \
  [--no-toc] \
  [--no-cover]
```

### 8. 验证

```bash
python scripts/office/validate.py output.docx
```

若验证失败:
1. 解包: `python scripts/office/unpack.py output.docx unpacked/`
2. 按 validate 报告修复 XML
3. 重新打包: `python scripts/office/pack.py unpacked/ output.docx`

## content.json 编写规范

### 完整结构

```json
{
  "title": "文档标题",
  "author": "作者",
  "sections": [
    {
      "type": "cover",
      "content": [
        { "type": "title", "text": "主标题" },
        { "type": "subtitle", "text": "副标题" },
        { "type": "paragraph", "text": "作者 | 日期" }
      ]
    },
    {
      "type": "body",
      "content": [
        { "type": "heading", "text": "第一章", "level": 1 },
        { "type": "paragraph", "text": "正文段落..." },
        { "type": "heading", "text": "1.1 子节", "level": 2 },
        { "type": "paragraph", "text": "支持**加粗**和*斜体*和`代码`内联格式" },
        { "type": "bullet_list", "items": ["要点1", "要点2", "要点3"] },
        { "type": "numbered_list", "items": ["步骤1", "步骤2", "步骤3"] },
        { "type": "table", "headers": ["列1", "列2", "列3"], "rows": [["值1", "值2", "值3"]] },
        { "type": "pagebreak" },
        { "type": "image", "path": "image.png", "width": 400, "height": 300, "type": "png" },
        { "type": "hyperlink", "text": "链接文字", "link": "https://example.com" }
      ]
    }
  ]
}
```

### 内容类型说明

| type | 必填字段 | 说明 |
|------|---------|------|
| `title` | `text` | 文档标题（大号居中） |
| `subtitle` | `text` | 副标题 |
| `heading` | `text`, `level` (1-4) | 章节标题 |
| `paragraph` | `text` | 正文段落，支持 `**粗体**` `*斜体*` `` `代码` `` |
| `bullet_list` | `items` (数组) | 无序列表 |
| `numbered_list` | `items` (数组) | 有序列表 |
| `table` | `headers`, `rows` | 表格（headers 列名, rows 行数据） |
| `pagebreak` | — | 分页符 |
| `image` | `path`, `width`, `height` | 图片（type 可选，默认从扩展名推断） |
| `hyperlink` | `text`, `link` | 外部超链接 |

## 常见问题

### Q: 用户只给了主题，没有给大纲？
先判断是否需要检索。如需要，调用 deepresearch-writer 获取研究报告（含建议文档结构）；如不需要，根据主题直接生成大纲。

### Q: 需要中英文混排？
在配方中设置 `fonts.body.eastAsia` 为中文字体，docx-js 会自动根据字符范围选择字体。

### Q: 生成后验证失败？
解包 → 按验证报告修复 XML → 重新打包。大多数 docx-js 生成的文档验证都会通过。
