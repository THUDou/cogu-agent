---
name: docx-craft
description: >
  创建和编辑专业 DOCX 文档，集成深度研究能力。
  两条流水线：(A) 从零创建新文档，可选通过 deepresearch-writer 子技能进行深度研究，
  基于模板样式和 docx-js 生成；(B) 用 HTML 模板 + node-html-parser + docx-js 生成会议纪要文档（决策类、日常例会、研讨主题），
  支持 safeJsonParse 容错解析和自动修复 fontTable 关系引用。
  当用户需要生成或修改 Word 文档时必须使用本技能——包括"写报告""起草方案""创建备忘录"
  "编辑文档""生成文档""会议纪要"，或任何最终输出为 .docx 文件的任务。
  即使用户未明确提及"docx"，只要任务隐含可打印/正式文档的需求，就应使用本技能。
metadata:
  dependencies:
    - "./deepresearch-writer/SKILL.md"
triggers:
  - Word
  - docx
  - document
  - 文档
  - Word文档
  - 报告
  - 合同
  - 公文
  - 排版
  - 创建文档
  - 编辑文档
  - 备忘录
  - 信函
---

# docx-craft

创建和编辑专业 DOCX 文档，集成深度研究能力。
两条流水线：
- **流水线 A**（docx-js 路径）：从零创建文档，支持深度研究集成
- **流水线 B**（HTML 模板路径）：用 HTML 模板 + node-html-parser + docx-js 生成会议纪要文档

## 环境准备

```bash
# 安装依赖
npm install

# 验证
node -e "require('docx')" && echo "docx-js OK"
```

可选：安装 `LibreOffice`（.doc 转换）。

## 快速参考

| 任务 | 方式 |
|------|------|
| 创建新文档（无需研究） | 使用 docx-js — 参见流水线 A（简单路径） |
| 创建新文档（需要研究） | 子技能 → deepresearch-writer → 模板 → docx-js — 参见流水线 A（研究路径） |
| **创建会议纪要** | 使用 HTML 模板 + docx-js — 参见流水线 B |
| 读取/分析内容 | 解包查看原始 XML |

## 流水线路由

```
用户任务
├─ 无输入文件，非会议纪要 → 流水线 A：创建
│   ├─ 用户已提供完整内容 → 简单路径（跳过研究）
│   └─ 主题需要研究 → 研究路径（子技能 → deepresearch-writer）
│   → 阅读 references/scenario_a_create.md
│
├─ recipe 以 meeting_ 开头 → 流水线 B：会议纪要
    │  自动路由：create.js --recipe meeting_* → create_html.js
    ├─ meeting_decision → 决策类会议纪要
    ├─ meeting_daily → 日常例会会议纪要
    └─ meeting_seminar → 研讨主题会议纪要
    → 参数参考：--engine mammoth（默认走 HTML模板路径）| docx（强制 docx-js 路径）
```

---

## 流水线 A：创建

### 步骤 1：研究决策

判断主题是否需要深度研究。这是 LLM 的认知决策，无需脚本。

| 信号 | 决策 |
|------|------|
| 用户提供了完整内容/大纲 | **跳过研究** |
| 纯格式化/模板填充（数据已有） | **跳过研究** |
| 简单通知/备忘录/信函 | **跳过研究** |
| 行业/市场分析 | **需要研究** |
| 学术论文需要文献支撑 | **需要研究** |
| 技术报告需要最新数据 | **需要研究** |
| 竞品分析/对比研究 | **需要研究** |
| 政策/法规解读 | **需要研究** |

### 步骤 2：研究（需要时）

使用 Agent 工具创建子技能调用 **deepresearch-writer**：

#### 2.1 准备输出目录

流水线执行研究前，先创建时间戳输出目录：

```bash
node {skill_root}/docx-craft/scripts/utils/generate_timestamp_dir.js output/
```

> 如 `generate_timestamp_dir.js` 不存在，手动创建目录：`output/YYYYMMDD_HHMMSS_000/`

脚本返回完整路径，如：`output/20260317_143052_000/`，赋值给 `{output_dir}`。

**用户指定路径时**：如用户明确指定输出目录，则使用用户指定路径，不自动添加时间戳子目录。

#### 2.2 搜索模式判定

| 场景 | search_mode | 说明 |
|------|-------------|------|
| 用户要求"最新数据""趋势""市场分析""竞品对比" | `force_search` | 强制完整研究流程 |
| 用户主题宽泛、缺少结构化材料 | `auto` | deepresearch-writer 自动判断 |
| 用户上传了内容充实的文档 | `auto` | deepresearch-writer 自动判断（素材充实则跳过搜索） |
| 用户明确要求"不搜索""只按给定材料" | `no_search` | 禁止搜索，纯素材模式 |
| 用户提供了完整内容/大纲 | `no_search` | 无需外部研究 |

#### 2.3 研究深度判定

| 场景 | research_depth | 说明 |
|------|---------------|------|
| 简报/通知/备忘录 | `L1` | 快速研究，≥3000字 |
| 标准商业报告/方案 | `L2` | 深度研究，≥5000字 |
| 学术论文/深度行业报告 | `L3` | 专家级研究，≥8000字 |

#### 2.4 创建研究子技能

```
Agent({
  "subagent_type": "general-purpose",
  "description": "为文档内容进行深度研究",
  "prompt": "{research_prompt}"
})
```

**研究提示词模板**（替换 `{变量}` 为实际值）：

```
请基于以下信息执行深度内容研究，生成研究报告。

主题：{topic}
研究深度：{research_depth}
搜索模式：{search_mode}
研究方向：{directions}

<!-- 【有文档素材时保留此段落，无素材时删除】 -->
**用户提供的文档资料**：
<uploaded_document>
{doc_content}
</uploaded_document>

搜索模式说明：
- auto：根据素材充裕度自动决定是否搜索
- no_search：禁止搜索，纯素材模式
- force_search：强制完整研究流程

**输出路径**：

- 输出目录：{output_dir}
- 研究报告：research.md

使用 deepresearch-writer 技能执行。将产物写入 {output_dir}/ 目录下。
```

#### 2.5 验证研究产物

研究子技能完成后，检查 `{output_dir}/research.md` 是否存在且非空。

**失败处理**：如产物缺失，重试一次（创建新子技能，在提示词末尾追加失败原因）。仍失败则告知用户。

#### 2.6 整合研究内容

读取 `{output_dir}/research.md`，将研究结果转化为 `content.json` 格式：

- `## 建议文档结构` → 标题层级结构
- `#### 研究分析` → 正文段落
- `关键数据清单` → 表格数据
- `时序数据` → 表格数据
- `对比数据` → 表格数据
- `## 来源汇总` → 参考文献

可使用 `python scripts/research.py` 中的 `convert_research_to_content()` 作为参考。

### 步骤 3：模板选择

根据文档类型匹配配方：

| 文档类型 | 配方 | 引擎 | 关键样式 |
|----------|------|------|----------|
| 学术论文/综述 | `academic` | docx-js | Times New Roman / SimSun，12磅，双倍行距 |
| 商业报告/分析 | `report` | docx-js | Calibri / 微软雅黑，11磅，1.15倍行距 |
| 公文/通知/函件 | `government` | docx-js | 方正小标宋 / 仿宋_GB2312，GB/T 9704 |
| 备忘录 | `memo` | docx-js | Arial，11磅，1.15倍行距 |
| 信函 | `letter` | docx-js | Calibri，11磅，单倍行距 |
| **决策类会议纪要** | `meeting_decision` | HTML模板 | Arial，12pt，带结论/讨论/任务表格 |
| **日常例会会议纪要** | `meeting_daily` | HTML模板 | 黑体/宋体，多级议程，任务跟踪表 |
| **研讨主题会议纪要** | `meeting_seminar` | HTML模板 | 黑体/宋体，分组讨论结构 |

### 步骤 4：使用 docx-js 生成

**简单路径**（用户已有内容）：

```bash
node scripts/create.js --recipe report --content content.json --output out.docx --title "标题" --author "作者"
```

**研究路径**（deepresearch-writer 完成后）：

1. 将 research.md 结果转换为 `content.json` 格式
2. 运行 `node scripts/create.js --recipe report --content content.json --output out.docx`

#### content.json 格式

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
        { "type": "heading", "text": "第一章 概述", "level": 1 },
        { "type": "paragraph", "text": "正文内容..." },
        { "type": "heading", "text": "1.1 背景", "level": 2 },
        { "type": "paragraph", "text": "背景内容..." },
        { "type": "bullet_list", "items": ["要点1", "要点2"] },
        { "type": "table", "headers": ["指标", "数值"], "rows": [["营收", "100亿"]] },
        { "type": "pagebreak" }
      ]
    }
  ]
}
```

### 步骤 5：验证

验证生成的文档可正常打开。

---

## 流水线 B：用 HTML 模板生成会议纪要

用于生成具有复杂表格和多级结构的会议纪要文档（决策类、日常例会、研讨主题）。
通过 create.js 的 `--recipe meeting_*` 自动路由到 `create_html.js`。

### 原理

1. **HTML 模板**：在 `scripts/html-templates/` 下维护手写的 HTML 模板，包含 CSS 样式和 `{{placeholder}}` 占位符
2. **模板引擎**（`renderBlock`）：三遍处理 — `{{#each list}}` → `{{#if var}}` → `{{variable}}`
3. **运行时**：`create.js` 自动路由 → `create_html.js` 填充模板 → `node-html-parser` 解析 DOM → `docx-js` 直接生成 DOCX

### 引擎特性

`create_html.js` 内置以下自愈能力：
- **`safeJsonParse`**：JSON 解析时自动修复字符串值中未转义的双引号和控制字符，避免中文引号导致的解析失败
- **`fixFontTableRelationship`**：自动补全 docx-js 遗漏的 `fontTable.xml` Relationship 引用，确保 `validate.py` 通过

### 环境要求

```bash
npm install node-html-parser      # DOM 解析
npm install docx jszip             # DOCX 生成 + zip 处理（已安装）
npm install mammoth                # 仅用于模板提取（可选）
```

### 使用方式

```bash
# 方式一：通过 create.js 自动路由（推荐）
node scripts/create.js --recipe meeting_decision --content data.json --output out.docx

# 方式二：直接调用 create_html.js
node scripts/create_html.js --template meeting_decision --data data.json --output out.docx

# 方式三：指定引擎（强制使用 docx-js）
node scripts/create.js --recipe meeting_decision --content data.json --output out.docx --engine docx
```

### 验证

create_html.js 生成的文档自带 fontTable 修复，验证应直接通过。

### 会议数据格式

每种会议纪要模板有独立的数据结构，详见 `scripts/html-templates/` 下的模板对应的 JSON 字段。

**决策类会议纪要示例**：
```json
{
  "title_year": "2025",
  "title_month": "03",
  "title_day": "15",
  "meeting_name": "第三次战略规划会",
  "time": "2025年3月15日 14:00-16:00",
  "location": "3楼第一会议室",
  "convener": "张总",
  "attendance": "李XX、王XX、赵XX",
  "reporter": "王XX",
  "recorder": "李XX",
  "reviewer": "张总",
  "main_content": "本次会议主要围绕2025年战略规划进行讨论。",
  "conclusions": [{ "number": 1, "content": "确认三大战略方向" }],
  "discussions": [{ "number": 1, "content": "张博士建议：第一阶段采用\"旁路辅助\"模式" }],
  "tasks": [{ "number": 1, "description": "完成市场调研", "deadline": "3月22日", "owner": "王XX" }],
  "attachments": [{ "name": "附件1：市场分析报告" }],
  "department": "战略规划部",
  "doc_date": "二〇二五年三月十五日"
}
```

> **提示**：`safeJsonParse` 会自动处理 JSON 中未转义的双引号，以上 `\"旁路辅助\"` 也可直接写为 `"旁路辅助"` 而不报错。

## 产物目录结构

每次流水线 A（研究路径）调用自动创建时间戳子目录，实现调用隔离：

```
output/                           # 基础输出目录
├── 20260317_143052_000/          # 第一次调用的时间戳目录
│   ├── research.md               # 研究子技能产出：按章节映射研究报告
│   ├── content.json              # 转换后的内容结构（供 create.js 使用）
│   └── {sanitized_topic}.docx    # 最终 DOCX 文件
├── 20260317_143052_001/          # 同一秒内的第二次调用
│   └── ...
└── ...
```

**时间戳格式**：`YYYYMMDD_HHMMSS_XXX`

- 前 14 位：年月日时分秒
- 后 3 位：序号（000-999），解决同一秒内并发调用冲突

**用户指定路径时**：如用户在需求中明确指定了输出目录，则使用用户指定路径，不自动添加时间戳子目录。

---

## 关键规则

### docx-js 规则（创建模式）

1. **表格需要双重宽度设置** — 同时设置表格的 `columnWidths` 和每个单元格的 `width`
2. **表格宽度 = columnWidths 之和** — DXA 单位下必须精确相等
3. **使用 `WidthType.DXA`** — 禁止使用 `WidthType.PERCENTAGE`（在 Google Docs 中会出错）
4. **使用 `ShadingType.CLEAR`** — 禁止使用 `SOLID`（会导致黑色背景）
5. **列表使用 `LevelFormat`** — 禁止使用 Unicode 项目符号字符
6. **图片必须指定 `type`** — 始终标明 png/jpg 等格式
7. **分页符放在段落内** — 独立使用会生成无效 XML
8. **显式设置页面尺寸** — docx-js 默认为 A4
9. **禁止使用 `\n`** — 使用独立的段落元素
10. **覆盖内置标题样式** — 使用精确 ID："Heading1"、"Heading2"
11. **包含 `outlineLevel`** — 目录所需（0=H1，1=H2，以此类推）
12. **字号** — `size` = 磅值 × 2（12磅 → size: 24）
13. **边距/间距单位为 DXA** — 1英寸 = 1440 DXA，1厘米 ≈ 567 DXA
14. **CJK 字体回退** — 在 RunFonts 中设置 `eastAsia` 字体

---

## 命令行参考

### create.js — 文档生成

```bash
node scripts/create.js \
  --recipe <academic|report|government|memo|letter|meeting_decision|meeting_daily|meeting_seminar> \
  --content <content.json|data.json> \
  --output <output.docx> \
  [--title "标题"] \
  [--author "作者"] \
  [--page-size <letter|a4|legal|a3>] \
  [--margins <standard|narrow|wide>] \
  [--no-toc] \
  [--no-cover] \
  [--engine <docx|mammoth|auto>]
```

| 参数 | 说明 |
|------|------|
| `--recipe` | 模板配方名，meeting_* 自动走 HTML模板引擎 |
| `--engine` | 可选，强制指定引擎（auto=自动检测，docx=旧 docx-js 路径，mammoth=HTML模板路径） |
| `--content` | docx-js 路径：content.json；HTML模板路径：data.json |

### create_html.js — 会议纪要专用生成

```bash
node scripts/create_html.js \
  --template <meeting_decision|meeting_daily|meeting_seminar> \
  --data <data.json> \
  --output <output.docx>
```

---

## 页面尺寸与单位参考

### 常用页面尺寸（DXA）

| 纸张 | 宽度 | 高度 | 内容宽度（1英寸边距） |
|------|------|------|---------------------|
| US Letter | 12,240 | 15,840 | 9,360 |
| A4 | 11,906 | 16,838 | 9,026 |
| Legal | 12,240 | 20,160 | 9,360 |
| A3 | 16,838 | 23,811 | 13,978 |

### 边距预设（DXA）

| 预设 | 上 | 下 | 左 | 右 |
|------|----|----|----|----|
| 标准（1英寸） | 1440 | 1440 | 1440 | 1440 |
| 窄（0.5英寸） | 720 | 720 | 720 | 720 |
| 宽（1英寸/1.5英寸） | 1440 | 1440 | 2160 | 2160 |

### 单位换算

- 1英寸 = 1440 DXA = 914400 EMU = 72磅
- 1厘米 ≈ 567 DXA = 360000 EMU
- 字号：`w:sz` = 磅值 × 2（12磅 → sz="24"）

---

## 变量说明

| 变量 | 说明 | 示例 |
|------|------|------|
| `{topic}` | 用户确认的文档主题 | "2025年中国AI大模型市场分析" |
| `{output_dir}` | 产物输出目录（绝对路径），由流水线自动生成时间戳子目录或用户指定 | "/path/to/output/20260317_143052_000" |
| `{research_depth}` | 研究深度级别 | "L1"、"L2"、"L3" |
| `{search_mode}` | 搜索模式 | "auto"、"no_search"、"force_search" |
| `{directions}` | 研究方向/焦点领域 | "市场规模,竞争格局,趋势预测" |
| `{doc_content}` | 用户提供的文档素材内容 | 文档原文内容 |
| `{skill_root}` | skills 目录路径 | skills 目录的绝对路径 |

---

## 错误处理与重试

| 失败场景 | 检测方式 | 处理策略 |
|----------|---------|----------|
| 研究子技能未生成 research.md | 检查文件是否存在 | 重试一次（创建新子技能，附加失败原因），仍失败则告知用户 |
| research.md 内容为空 | 检查文件是否非空 | 重试一次，在提示词末尾追加失败原因 |
| DOCX 转换失败 | 脚本报错或输出文件不存在 | 检查依赖安装状态，重试 1 次 |

**重试机制**：每个子技能最多重试 1 次（总共 2 次机会）。重试时创建新的子技能，在提示词末尾追加失败原因。

---

## 参考资料

按需加载，不要一次性全部加载。

### 场景指南

| 文件 | 使用时机 |
|------|---------|
| `references/scenario_a_create.md` | 流水线 A：从零创建文档 |

### 技术参考

| 文件 | 使用时机 |
|------|---------|
| `references/docx_js_rules.md` | docx-js API 模式和 14 条关键规则 |
| `references/typography_guide.md` | 字体搭配、字号、间距、页面布局 |
| `references/cjk_typography.md` | CJK 字体、字号尺寸、RunFonts 映射 |
| `references/openxml_element_order.md` | XML 元素排序规则 |
| `references/openxml_units.md` | 单位换算：DXA、EMU、半磅 |
| `references/track_changes_guide.md` | 修订标记深入指南 |
| `references/troubleshooting.md` | 基于症状的问题排查 |

### 模板配方

| 文件 | 文档类型 | 引擎 |
|------|---------|------|
| `recipes/academic.json` | 学术论文/综述 | docx-js |
| `recipes/report.json` | 商业报告/分析 | docx-js |
| `recipes/government.json` | 公文（GB/T 9704） | docx-js |
| `recipes/memo.json` | 备忘录 | docx-js |
| `recipes/letter.json` | 信函 | docx-js |
| `recipes/meeting_decision.json` | 决策类会议纪要 | HTML模板 |
| `recipes/meeting_daily.json` | 日常例会会议纪要 | HTML模板 |
| `recipes/meeting_seminar.json` | 研讨主题会议纪要 | HTML模板 |
