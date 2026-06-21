---
name: pptx-content-summarizer
description: "当需要读取、分析或总结已有 PPT/PPTX（幻灯片、胶片）文件并输出可直接呈现的 Markdown 内容简报时使用；适用于从 PPTX 源文件提取元数据、文字、表格、备注，先生成逐页内容卡片，再生成文档信息、一句话总结、核心发现、详细展开、关键数据/决策点和行动启示。不要用于创建、编辑或改写 PPTX 文件。"
---

# PPTX 内容总结技能

## 概览

本技能用于从已有 `.pptx` 源文件中提取可读文本内容，并总结成一份可直接交付给读者的中文 Markdown 内容简报。它不依赖截图、OCR 或视觉模型，只使用 PPTX 文件内部的核心属性、文本框、表格、备注和基础结构信息。

最终 Markdown 是面向读者的正式产物，不要写入处理日志、源文件路径、覆盖率、诊断说明、内部不确定性或“需人工复核”等工作底稿内容。

## 执行顺序

1. 验证输入文件存在且格式为 `.pptx`。
2. 创建或确认本次任务的独立输出目录。
3. 使用 `scripts/extract_pptx_text.py` 提取 PPTX 核心属性、每页标题、文本、表格、备注和基础媒体信息，用 `--slide-inputs` 输出每页独立输入文件。
4. **并行**生成 page cards：在同一条消息中发起所有 N 个 Agent tool call，每个 call 只读取自己负责的 `slide_inputs/slide_XXX_input.json`，写出对应的 `page_cards/slide_XXX.json`；每批最多 5 个，超过 5 页分批发起。
5. 使用 `scripts/build_page_cards_index.py` 生成 `page_cards/index.json`，记录页数和每页卡片文件顺序。
6. 使用 `scripts/validate_page_cards.py` 校验逐页卡片完整性。
7. 使用 `scripts/aggregate_page_cards.py` 生成 `page_cards_aggregate.md`。
8. [Step 1] 读取 `page_cards_aggregate.md`，重整逻辑块分组，确定核心发现、关键数据和行动启示，写出 `outline.md`。
9. [Step 2] 依据 `outline.md` 逐逻辑块写出最终 Markdown 内容简报，串行追加到输出文件。
10. Agent 对照 QA 自查清单审查草稿，并直接修正文档。
11. **必须运行格式化脚本**（步骤 10 的直接延续）：
    - 使用 `scripts/format_summary_markdown.py --in-place <run-dir>/<PPT文件名>-summary.md` 统一空行和关键数据格式。
    - 使用 `scripts/format_summary_markdown.py --check <run-dir>/<PPT文件名>-summary.md` 校验格式；通过后再交付。
    - 如果校验失败，根据错误信息修正，重新运行 formatter 直到通过。

如果源文件中的文字是图片、截图、扫描件或不可解析图表的一部分，本技能不会尝试识别，只基于 PPTX 源结构中可提取的内容进行总结。

## 输出目录约束

默认输出根目录为仓库根目录下的 `pptx-summary/`。每次处理一个 PPTX 都必须使用一个独立运行目录，推荐格式：

```text
pptx-summary/<PPT文件名>-<YYYYMMDD-HHMMSS>/
```

如果用户明确说明了输出目录，可以使用用户指定目录，但该目录必须是本次任务专用目录。

运行目录只保存本次任务需要的文本提取结果和最终文档：

```text
<run-dir>/
  slide_text.json
  slide_inputs/
    slide_001_input.json
    slide_002_input.json
    ...
  page_cards/
    index.json
    slide_001.json
    slide_002.json
    ...
  page_cards_aggregate.md
  outline.md
  <PPT文件名>-summary.md
```

目录规则：

- 不要把多个 PPT 的产物混在同一个运行目录。
- 不要把中间产物散落到源 PPT 目录或技能目录。
- 不要复用已有非空目录；若目标目录已存在且非空，创建带时间戳或序号的新目录。
- 本技能不创建 `temp/`、`slides/` 或截图目录；`slide_inputs/` 和 `page_cards/` 是正式中间产物，不属于临时目录。
- 如果运行目录里出现临时目录，交付前必须清理。
- 最终 Markdown 默认写入同一运行目录，命名为 `<PPT文件名>-summary.md`；只有用户明确指定最终文件路径时，才写到指定路径。
- 最终 Markdown 中不要暴露上述目录结构或源路径。

## 命令

从仓库根目录运行，或使用绝对路径：

```bash
python skills/pptx-content-summarizer/scripts/extract_pptx_text.py "deck.pptx" --output "pptx-summary/<run-dir>/slide_text.json" --slide-inputs "pptx-summary/<run-dir>/slide_inputs"
```

`extract_pptx_text.py` 支持未展开的 glob 模式和疑似 UTF-8 mojibake 路径。Windows PowerShell 默认不会展开 `test_docs/*AI RPA*.pptx` 这类通配符，因此可以直接把模式作为参数传给脚本，不要为了展开 glob 另写临时脚本：

```bash
python skills/pptx-content-summarizer/scripts/extract_pptx_text.py "test_docs/*AI RPA*.pptx" --output "pptx-summary/<run-dir>/slide_text.json" --slide-inputs "pptx-summary/<run-dir>/slide_inputs"
```

如果环境中的 `python` 不在 PATH 中，优先使用 Codex 工作区依赖路径，或在本技能目录创建 `.venv` 并安装 `python-pptx`。

生成每页 page card 时，只读取对应的 `slide_inputs/slide_XXX_input.json`，不要读取 `slide_text.json` 或其他任何文件。每个 `slide_XXX_input.json` 已包含该页的 `slide` 数据、全局 `document_properties` 和 `slide_count`，是 page card 生成的完整且唯一输入。`slide_text.json` 保留为详细中间产物，仅在需要追踪具体文本框、表格结构或调试提取问题时读取。

逐页卡片全部生成后先创建 index：

```bash
python skills/pptx-content-summarizer/scripts/build_page_cards_index.py "pptx-summary/<run-dir>/page_cards"
```

逐页卡片生成完成后运行：

```bash
python skills/pptx-content-summarizer/scripts/validate_page_cards.py "pptx-summary/<run-dir>/page_cards"
```

只有 `page_cards/` 校验通过后，才能进入最终 Markdown 汇总。

逐页卡片校验通过后运行聚合脚本：

```bash
python skills/pptx-content-summarizer/scripts/aggregate_page_cards.py "pptx-summary/<run-dir>/page_cards" --slide-inputs "pptx-summary/<run-dir>/slide_inputs" --output "pptx-summary/<run-dir>/page_cards_aggregate.md"
```

最终 Markdown 写作和内容 QA 完成后，必须运行 formatter：

```bash
python skills/pptx-content-summarizer/scripts/format_summary_markdown.py "pptx-summary/<run-dir>/<PPT文件名>-summary.md" --in-place
python skills/pptx-content-summarizer/scripts/format_summary_markdown.py "pptx-summary/<run-dir>/<PPT文件名>-summary.md" --check
```

`format_summary_markdown.py` 使用 `config/summary_format.json` 控制章节名、标题空行和关键数据格式。后续章节名变化时优先修改配置，不要硬改脚本。

## 可提取内容

`extract_pptx_text.py` 会尽量提取：

- PPTX 核心属性：标题、作者、主题、分类、关键词、备注、创建时间、修改时间、最后修改人、修订版本等。
- 每页页码和标题猜测。
- 文本框中的正文和段落层级。
- 表格单元格文字。
- 演讲者备注。
- 图片数量、图表数量等基础结构信息。

限制：

- 不能读取嵌在图片、截图或扫描件里的文字。
- 不能理解图片、图标、页面视觉层级或非文本图表含义。
- 对不可解析的图表，只能保留图表数量等结构线索，不要编造具体数据。

## 总结规则

逐页生成 page cards 时，读取对应的 `slide_inputs/slide_XXX_input.json`，优先使用其中的证据：

- `slide.document_properties` 用于后续生成文档信息，包括作者、版本、日期等；文档类型、目标读者和核心主题需要结合标题、封面页、正文线索和 page cards 推断。
- `slide.title` 用于判断页面主题和内容逻辑。
- `slide.content` 用于提炼主题、发现、逻辑块和行动启示。
- `slide.tables` 用于补充指标、对比、清单和结构化信息。
- `slide.speaker_notes` 用于补充演讲者备注中的上下文。
- `slide.image_count` 和 `slide.chart_count` 只能作为”本页含有图片/图表”的结构线索，不要推断其具体视觉内容。

处理原则：

- 优先保留源 PPT 中明确出现的概念、数据、判断和结论。
- 将重复、装饰性或页脚类文本合并或忽略。
- 不要粘贴大段原始文本，除非用户明确要求做全文提取。
- 不要臆测图片、截图、图标或图表中没有被文本提取出来的信息。
- 文档类型、目标读者和核心主题可以基于标题、封面页、元数据、正文语气和 page cards 合理推断。
- 作者、版本、日期等字段如果无法从元数据、封面页或正文中判断，统一写“未知”，不要省略字段，也不要写成内部诊断。
- 指标、金额、比例、时间、数量、排名、规模、增长率等数字必须优先进入每页 `metrics`，并在全局汇总时进入“核心发现”和“关键数据/决策点”；不要改写数字单位，不要编造不存在的数字。

## 逐页内容卡片

每页 PPT 必须先生成一个独立 JSON 文件，作为最终汇总前的中间理解结果。逐页卡片不直接展示给最终读者，但用于确保每一页都被处理过，并支持后续追踪。

单页卡片文件命名：

```text
page_cards/slide_001.json
page_cards/slide_002.json
page_cards/slide_003.json
```

单页卡片结构：

```json
{
  "schema_version": "pptx-content-summarizer-page-card-v1",
  "slide_number": 1,
  "title": "页面标题",
  "one_sentence": "本页一句话总结。",
  "key_points": [
    "本页关键要点 1",
    "本页关键要点 2"
  ],
  "metrics": [
    {
      "value": "42%",
      "meaning": "该数字代表的含义"
    }
  ],
  "decision_points": [
    "本页涉及的判断、选择或决策点"
  ],
  "logic_block": "建议归属的逻辑块",
  "source_evidence": {
    "content": "用于支撑本页总结的精简文本",
    "tables": [],
    "speaker_notes": ""
  }
}
```

`page_cards/index.json` 结构：

```json
{
  "schema_version": "pptx-content-summarizer-page-cards-index-v1",
  "slide_count": 20,
  "cards": [
    "slide_001.json",
    "slide_002.json"
  ]
}
```

生成规则：

- 每页必须生成且只生成一个 `slide_XXX.json`。
- `slide_number` 必须与文件序号一致。
- `source_evidence` 只能放精简证据，不要放完整 `slide_text.json` 中的大段调试结构。
- `logic_block` 是本页对最终“详细展开”章节的建议归属，可以在最终汇总时合并或重命名。
- 数字、金额、比例、时间、数量、排名、规模、增长率等优先写入 `metrics`。
- 决策、判断、选择、路线、建议等优先写入 `decision_points`。
- 如果某页文本很少，也必须生成卡片；字段可以简洁，但不要缺字段。

## 并行处理规则

逐页内容卡片**必须并行生成**，最终汇总必须串行执行。

**⚠️ 并行创建规则（必须遵守）**：

- **在同一条消息中发起所有 N 个 Agent tool call**，每个 call 负责一页的 page card 生成
- **禁止逐页创建**：不要等前一个完成再创建下一个，必须一次性全部发出
- 分批启动：每批最多 5 个；PPT 超过 5 页时分批发起，等第一批全部完成后再发下一批

每个子 Agent 的任务规范：

- 只读取 `slide_inputs/slide_XXX_input.json`（自己负责的那页）
- 只写出 `page_cards/slide_XXX.json`（对应页码）
- 不读取其他页的输入文件，不改写其他页的卡片

并行阶段完成后（所有页卡片写出后），依次执行：

1. 使用 `scripts/build_page_cards_index.py` 统一生成 `page_cards/index.json`
2. 运行 `validate_page_cards.py` 校验完整性，通过后才能继续
3. 运行 `aggregate_page_cards.py` 生成 `page_cards_aggregate.md`
4. Step 1 读取聚合文件规划 `outline.md`，Step 2 逐逻辑块串行写出最终 Markdown，不能把单页卡片机械拼接成最终报告

## Step 1 规则

Step 1 在 `validate_page_cards.py` 校验通过且 `aggregate_page_cards.py` 运行完成后执行。

- 只读 `page_cards_aggregate.md`，不读任何 page card 原文件或 `slide_text.json`。
- 重整 logic_block 分组：将命名相近的碎片化分组合并，统一命名。
- `outline.md` 的逻辑块划分**必须写出明确页码范围**（如"第4-10页"），Step 2 依赖此信息决定读哪些 page cards。
- 目录页、封面页、空白页在对应逻辑块中标注，Step 2 写作时跳过这些页。
- **不写任何 Markdown 正文内容**，只输出规划结构。

`outline.md` 必须包含以下章节，顺序固定：

```markdown
# 文档规划

## 文档信息
类型：（文档类型）
作者：（或"未知"）
日期：（或"未知"）
目标读者：（推断）
总页数：N

## 一句话总结
（整份 PPT 最核心的一句话）

## 核心发现
1. （带数字）
2. （带数字）
3. （发现）
...（共 3-5 条）

## 逻辑块划分
### （逻辑块名称）（第X-X页）
涵盖：（页面列举）

### （逻辑块名称）（第X-X页）
涵盖：（页面列举）

## 关键数据/决策点
- 数字/指标：含义

## 行动启示
- （建议或待回答问题）
```

## Step 2 规则

Step 2 在 `outline.md` 写出后执行，串行处理，不可并行。

执行顺序：

1. 创建最终 Markdown 文件（`<PPT文件名>-summary.md`），从 `outline.md` 提取固定章节写入：
   - `# <PPT标题>摘要`
   - `## 文档信息`
   - `## 一句话总结`
   - `## 核心发现`
   - `## 详细展开`（只写章节标题，内容由后续循环填入）
2. 循环 `outline.md` 中每个逻辑块：
   - 读 `outline.md`（结构参考）
   - 读该块页码范围对应的 `page_cards/slide_XXX.json`
   - 将该块内容作为 `### 【逻辑块名称】` 追加到"详细展开"
3. 从 `outline.md` 提取尾部章节，追加到最终文件：
   - `## 关键数据/决策点`
   - `## 行动启示/待回答问题`

写作规范：

- 每次迭代只读当前逻辑块的 page cards，不一次性读取全部 page cards。
- 用 `key_points` 理解细节，`source_evidence` 在需要时核实原文。
- 写**散文段落**，融合多页内容，不逐页罗列。
- 可自然引用页码，但不做"第X页说了……第X+1页说了……"式机械复述。
- 最终 Markdown 必须遵守“Markdown 输出”章节的模板和规则。
- 不产生额外中间文件，直接追加到 `<PPT文件名>-summary.md`。

## Windows 与路径处理

- 命令参数中的 PPTX 路径、输出路径和目录路径都必须加引号，尤其是包含空格、中文、括号或通配符时。
- 不要依赖 PowerShell 自动展开 glob；`extract_pptx_text.py` 会处理 `*.pptx`、`*AI RPA*.pptx` 等模式。
- 如果终端显示中文文件名为乱码，优先继续使用原始路径或 glob 模式；脚本会尝试修复常见 UTF-8 mojibake 路径。
- 不要为了路径转义、glob 展开或 index 生成另写一次性 Python 胶水脚本；优先使用本技能内置脚本。
- 如果需要从 Python 调用脚本，使用 `subprocess.run([...], check=True)` 的参数列表形式，不要把包含空格的路径拼接成一个 shell 字符串。

## Markdown 输出

最终报告必须是可直接呈现的中文 Markdown，除非用户指定其他语言。默认不输出逐页说明；如果用户明确要求逐页说明，再基于 `page_cards/` 追加独立的“分页说明”附录。

### 输出模板

```markdown
# <PPT标题>摘要

## 文档信息
战略分析类PPT，作者未知，版本未知，日期为2026年5月，面向产品决策层，共10页。以XX框架论证XXXX策略。

## 一句话总结
用一句话写出整份 PPT 最核心的内容、观点或结论。

## 核心发现
1. <发现 1：优先包含明确数字、指标或结论>
2. <发现 2：优先包含明确数字、指标或结论>
3. <发现 3：优先包含明确数字、指标或结论>

## 详细展开
### 【逻辑块名称】
用散文段落展开说明，把多页内容融合成一个连贯观点；必要时可以自然引用页码，但不要机械逐页复述。多个段落之间直接相连，不留空行。

### 【逻辑块名称】
继续展开另一组内容逻辑，说明背景、原因、过程、影响或结论。同样，段落之间不留空行。

## 关键数据/决策点
- 30%：该指标代表的含义
- 2026年5月：该时间节点代表的含义

## 行动启示/待回答问题
1. <行动启示或后续需要决策的问题>
2. <行动启示或后续需要决策的问题>
```

### 格式规则

- 主标题写成 `# <PPT标题>摘要`；如果标题已含”摘要”，不要重复。
- 主标题后空一行，再写 `## 文档信息`。
- 六个 `##` 章节标题固定为：`文档信息`、`一句话总结`、`核心发现`、`详细展开`、`关键数据/决策点`、`行动启示/待回答问题`；标题前不要加序号。
- `##` 和 `###` 标题下一行直接接正文或列表，不留空行。
- 内容与下一个标题之间保留一个空行。
- **”详细展开”章节特殊规则**：`###` 子标题下的散文内容多个段落之间不留空行；只在 `###` 子标题之间保留空行。
- **⚠️ Agent 写作时不需要手写精确的空行，步骤 11 的 formatter 会自动调整所有空行至一致。**

### 章节规则

- `文档信息`：一到两句话，包含文档类型、作者、版本、日期、目标读者、页数和核心主题；作者、版本、日期无法判断时写“未知”。页数必须来自 `page_cards/index.json.slide_count` 或任意 `slide_inputs/slide_XXX_input.json.slide_count`。
- `文档类型`：使用概括性分类，例如“战略分析类PPT”“述职汇报类PPT”“产品方案类PPT”“项目复盘类PPT”“培训材料类PPT”“市场分析类PPT”“技术方案类PPT”“经营汇报类PPT”。
- `一句话总结`：只写一个核心句子。
- `核心发现`：3-5 条，使用数字序号，优先纳入源 PPT 中明确出现的数字、指标或结论。
- `详细展开`：使用多个 `### 【逻辑块】` 小节，每个逻辑块用散文段落融合若干页内容，不机械逐页复述。
- `关键数据/决策点`：每项写成 `- 数字/指标：含义`，列表符号后直接以阿拉伯数字开头，不给数字或指标加 `【】`；纯文字决策点放到“详细展开”或“行动启示/待回答问题”。
- `行动启示/待回答问题`：1-3 点，使用数字序号，面向后续行动、判断或需要补充的信息。
- 不要出现 `Coverage`、源文件路径、截图路径、视觉分析状态、处理日志、诊断说明、内部复核任务或不确定性说明。

## QA 审查与纠正

最终 Markdown 必须由 agent 自行完成 QA 审查和修正。QA 不依赖脚本硬卡规则，而是对照规范判断最终文档是否像一份可直接交付的正式内容简报。

Agent 自查分三类：

- 结构与格式：6 个章节齐全且顺序正确；标题、空行、列表和 `关键数据/决策点` 格式符合”Markdown 输出”规则。
- 内容完整：`文档信息` 字段齐全且页数准确；`核心发现` 为 3-5 条；`详细展开` 覆盖主要逻辑块；关键数字保留源单位。
- 交付洁净：不出现源路径、日志、Coverage、复核提示、视觉分析、处理过程说明或”需人工复核”等内部内容。

纠正规则：

- 如果自查发现问题，必须直接修正 Markdown，并再次对照清单复查。
- 不要把 QA 发现、修正记录或内部判断写进最终 Markdown。
- 不要通过删除重要内容来规避 QA；如果核心发现超出 5 条，应合并和分层，把次级数字移动到”关键数据/决策点”。
- 如果某个主要 `logic_block` 未覆盖，应在”详细展开”中补充该逻辑块，或合并到已有逻辑块并明确写出相关内容。
- 自查和修正过程只作为内部工作，不额外写入单独的 QA 记录文件。

**⚠️ QA 修正完成后必须立即运行 formatter（见步骤 11），不要手写空行，让脚本保证一致性。**

## 内部质量检查

交付前在内部确认：

- `slide_inputs/` 目录存在，且文件数量与 PPT 页数一致。
- `page_cards/index.json` 存在，且 `slide_count` 与 PPT 页数一致。
- 每页都存在对应的 `page_cards/slide_XXX.json`。
- `scripts/validate_page_cards.py` 校验通过。
- `scripts/format_summary_markdown.py --check` 校验通过。
- 最终 Markdown 符合“Markdown 输出”的模板、格式规则和章节规则。
- 最终运行目录中没有 `temp/`、`slides/`、截图文件或视觉分析文件。
- 最终 Markdown 没有占位标题、空章节、编造的图片/视觉细节、处理痕迹或内部复核措辞。
- `page_cards_aggregate.md` 存在，且包含所有页的摘要条目。
- `outline.md` 存在，且每个逻辑块都有明确页码范围。
- 最终 Markdown 的"详细展开"章节数与 `outline.md` 逻辑块数一致。

## 资源

- `scripts/extract_pptx_text.py`：从 PPTX 源文件提取核心属性、每页文本、表格、备注和基础媒体信息为 JSON（`slide_text.json`），并通过 `--slide-inputs` 参数输出每页独立输入文件 `slide_inputs/slide_XXX_input.json`。
- `scripts/build_page_cards_index.py`：扫描 `page_cards/slide_XXX.json` 并生成排序后的 `page_cards/index.json`。
- `scripts/validate_page_cards.py`：校验 `page_cards/index.json` 和每页 `slide_XXX.json` 的完整性，确保最终汇总前没有漏页或缺字段。
- `scripts/aggregate_page_cards.py`：读取所有 `page_cards/slide_XXX.json`，提取轻量字段，结合 `slide_inputs/` 中的 `document_properties`，输出 `page_cards_aggregate.md` 供 Step 1 使用。
- `scripts/format_summary_markdown.py`：按 `config/summary_format.json` 对最终 Markdown 做确定性格式化和检查，统一标题空行与关键数据格式。
- `config/summary_format.json`：最终 Markdown 格式配置，包含章节名、标题空行和关键数据格式规则。
