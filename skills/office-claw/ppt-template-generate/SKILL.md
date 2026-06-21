---
name: ppt-template-generate
description: "从现有 PPT（幻灯片）文件逆向工程生成模板规范文件，结合工具提取和视觉大模型分析，输出完整的样式规范文档。请注意某些场景下，幻灯片也被称为胶片。"
---

# PPT 模板规范生成技能

---

## ⚠️ Agent 执行规范

### 路径选择（首先执行）

在开始执行之前，判断你当前是否具备**图片理解工具**（即能直接理解图片文件内容的工具，工具必须为visual_question_answering）：

- **具备** → 走 **A 路径：Agent 视觉分析路径**（见下方）
- **不具备** → 走 **B 路径：VLM API 路径**（见"B 路径"小节，现有流程不变）

---

### A 路径：Agent 视觉分析路径

**步骤 1：运行脚本（跳过 VLM API 调用）**

```
node skills/ppt-template-generate/scripts/index.js <pptx路径> --skip-vlm [--name=<风格名>] [--output-dir=<输出根目录>] [--max-slides=N]
```

产出：`<输出根目录>/<临时目录>/`（默认 `ppt-template-hub/<临时目录>/`）含结构数据、幻灯片截图（`slides/`）、无 VLM 的基础聚合结果。若未传 `--name`，脚本完成后会在输出中打印 `NAMING_HINT` 块（格式见 B 路径"风格命名后处理"小节），进入步骤 2。

**步骤 2：命名后处理（未传 `--name` 时执行）**

若步骤 1 未传 `--name` 参数，脚本会输出 `NAMING_HINT` 块（格式见 B 路径"风格命名后处理"小节）。读取其中的配色数据，推断风格名，执行重命名：

```
node skills/ppt-template-generate/scripts/rename-template.js rename <临时目录> <新风格名>
node skills/ppt-template-generate/scripts/rename-template.js check <输出根目录>/<新风格名>
```

命名规则同 B 路径"风格命名后处理"小节。完成后目录变为 `<输出根目录>/<风格名>/`，后续步骤均使用此路径。

**步骤 3：Agent 视觉分析**

**3a. 读取分析指令**

读取 `skills/ppt-template-generate/vlm-config.json`，取 `prompts.analysisPrompt` 字段作为分析指令。若该字段缺失，参照本文档"Stage 4: VLM 视觉分析"节的分析要求（固定构图、版式语义、配色方案、纠偏规则等）自行组织分析指令。

**3b. 读取幻灯片截图**

读取 `<输出根目录>/<风格名>/slides/` 下的所有幻灯片截图，按文件名排序，最多读取 `vlm-config.json` 中 `analysis.maxImagesPerRequest` 张（默认 5 张）。

**3c. 执行视觉分析**

使用图片理解工具，按分析指令对截图进行视觉分析，得到 JSON 格式的分析结果。

**3d. 写入 `vlm_analysis.json`**

将分析结果包装为以下标准格式，写入 `<输出根目录>/<风格名>/temp/vlm_analysis.json`：

```json
{
  "totalImages": <实际分析的截图张数>,
  "batches": 1,
  "analyses": [
    {
      "schema_version": "ppt-template-vlm-enhanced-v1",
      "fixed_composition": [...],
      "layout_semantics": [...],
      "page_roles": [...],
      "visual_assets": [...],
      "corrections": [...],
      "replication_rules": [...],
      "overlay_policy": null
    }
  ]
}
```

> **分析失败处理**：若视觉分析失败或无法写出有效 JSON，在步骤 4 中省略 `--vlm` 参数，以无 VLM 模式聚合；Stage 5.5 检查文件不存在时跳过装饰合成。

**步骤 4：重新聚合（注入视觉结果）**

分析成功时：

```
node skills/ppt-template-generate/scripts/aggregate.js \
  "<输出根目录>/<风格名>/temp/template_data.json" \
  "<输出根目录>/<风格名>/<风格名>.md" \
  --name="<风格名>" \
  --vlm="<输出根目录>/<风格名>/temp/vlm_analysis.json" \
  --image-map="<输出根目录>/<风格名>/images/image-map.json" \
  --template-spec="<输出根目录>/<风格名>/template-spec.json"
```

分析失败时（省略 `--vlm`）：

```
node skills/ppt-template-generate/scripts/aggregate.js \
  "<输出根目录>/<风格名>/temp/template_data.json" \
  "<输出根目录>/<风格名>/<风格名>.md" \
  --name="<风格名>" \
  --image-map="<输出根目录>/<风格名>/images/image-map.json" \
  --template-spec="<输出根目录>/<风格名>/template-spec.json"
```

**步骤 5：装饰合成 + HTML 模板生成**

检查 `<输出根目录>/<风格名>/temp/vlm_analysis.json` 是否存在：

- **存在** → 执行 Stage 5.5（装饰合成），写入 `temp/decoration-map.json`，再运行：
  ```
  node skills/ppt-template-generate/scripts/generate-html-templates.js <输出根目录>/<风格名>
  ```
- **不存在** → 跳过装饰合成，直接运行上述 `generate-html-templates.js` 命令（输出无装饰最小骨架）

---

### B 路径：VLM API 路径（不具备图片理解工具时走此路径）

### 执行流程

```
运行脚本（默认执行图片转换，并启用 VLM）：
  node skills/ppt-template-generate/scripts/index.js <pptx路径> [--output-dir=<输出根目录>] [其他参数]

跳过 VLM，仅使用工具提取：
  node skills/ppt-template-generate/scripts/index.js <pptx路径> --skip-vlm

观察结果：
  ├── 脚本输出包含 "VLM_UNAVAILABLE_FALLBACK" → VLM 不可用，已自动降级为工具提取模式；继续执行风格命名后处理
  ├── 脚本输出包含 "VLM_DEPENDENCY_MISSING" → 仅在传入 --strict-vlm 时终止任务，将错误原文展示给用户
  └── 脚本正常完成 → 执行风格命名后处理（见下方）
      └── 脚本正常完成且 temp/vlm_analysis.json 存在 → 完成命名后处理后，执行 Stage 5.5 装饰合成，
          然后重新生成 HTML 模板：
            node skills/ppt-template-generate/scripts/generate-html-templates.js <输出目录>
          （此步骤使 decoration-map.json 注入装饰效果；跳过此步则 HTML 为无装饰最小骨架）
```

### 风格命名后处理（未传 `--name` 时必须执行）

脚本完成后，输出中会包含一个 `=== NAMING_HINT ===` 块，格式如下：

```
=== NAMING_HINT ===
文件名: <原始文件名>
临时目录: <输出根目录>/<原始文件名>/
主要配色（按使用频率）:
  1. 中国红(#D02227) × 110次 [主色]
  2. 深色(#1A1A1A) × 45次 [背景]
  3. 科技蓝(#5B9BD5) × 9次 [点缀]
背景色: 深色(#1A1A1A) × 18张
整体色调: 暗底暖色
===================
```

#### NAMING_HINT 不清晰时的兜底流程

`NAMING_HINT` 的命名线索可能为 `clear`、`weak` 或 `missing`。当状态不是 `clear`，或终端输出缺失、截断、配色明显不完整时，必须按以下顺序兜底：

1. 读取 `<临时目录>/temp/naming-hint.json`。这是脚本输出的结构化命名线索，包含 `status`、`reasons`、`colors` 和 `fallback_context`。
2. 若 `naming-hint.json` 不存在或不可读，再读取 `<临时目录>/temp/template_data.json`，参考 `actual_colors`、`bg_text_mapping`、`colors`、`slide_count`、`slide_roles`。
3. 若结构化配色仍为空或不明确，**禁止读取 `slides/` 截图，禁止调用 VLM，禁止做图片理解**；只结合原始文件名、页面数量、页面角色、是否存在背景图元数据等文本/结构化信息，生成保守中性风格名。
4. 保守命名示例：`通用简约`、`商务汇报`、`图片背景商务`、`浅色通用`、`深色通用`、`教育课件`、`产品介绍`、`党政汇报`。
5. 完成命名后仍必须执行 `rename-template.js rename` 和 `rename-template.js check`。

不清晰判定包括但不限于：

- `NAMING_HINT` 块不存在或被截断
- `命名线索状态` 为 `weak` 或 `missing`
- 主要配色为空
- 背景色为图片背景或未解析背景
- 主色只有黑/白/灰等中性色
- `actual_colors` 中没有 `fill_count > 0` 的颜色
- 颜色主要来自 `text_count`，缺少可代表视觉风格的填充色

> ⚠️ **严禁直接使用原始文件名作为风格名。** 脚本创建的临时目录名仅为占位符。**Agent 必须主动根据配色特征、整体色调、使用场景推断出描述性风格名，并完成重命名。不命名 = 任务未完成。**

**命名思路**：以颜色数据为核心，结合文件名透露的场景信息，综合推断出一个有识别度的中文风格名。要有发散和判断，不要套公式：

- **颜色是主角**：先看颜色特征——主色是什么、背景深浅、整体冷暖、是否有明显的亮色点缀。这些决定风格的基调
- **文件名是辅助线索**：从文件名中读取使用场景（汇报/宣传/教育/党建/产品介绍等）、行业（医疗/科技/教育/政务等）、受众等背景信息。**不能把文件名直接用作风格名，也不能截取文件名关键词拼凑**
- **综合生成名称**：将色彩感受和场景理解合并，起一个自然、有识别度的中文名。可以是"暗底科技蓝"、"红色党政简约"、"浅色教育清新"、"深蓝金融商务"等，也可以更有创意

**示例思路**（仅参考，不要照搬格式）：
- 文件名"2024Q3销售业绩" + 主色深红 → 联想到业绩、数据、商务氛围 → `深红商务汇报`
- 文件名"充电桩项目介绍" + 主色科技蓝+暗底 → 联想到新能源、科技感 → `暗底新能源科技`
- 文件名"小学语文课件" + 主色橙黄+明亮 → 联想到活泼、教育 → `亮色活泼教育`
- 文件名"ppt模板" + 主色深蓝+白 → 没有场景信息，只靠颜色 → `深蓝简约商务`

**操作步骤**：
1. 确定最终风格名（2-8字中文）
2. 读取 `NAMING_HINT` 中的 `临时目录` 路径（即脚本以原始文件名创建的目录）
3. 优先使用命名工具同步目录、文件和标题：
   `node skills/ppt-template-generate/scripts/rename-template.js rename <临时目录> <新风格名>`
4. 用校验命令确认一致：
   `node skills/ppt-template-generate/scripts/rename-template.js check <输出根目录>/<新风格名>`
5. 若目标目录已存在，先调整新风格名或追加 `_01`、`_02` 序号

> 注意：如果用户已通过 `--name` 参数指定了风格名，脚本不会输出 `NAMING_HINT`，跳过此后处理步骤。

### VLM 行为说明

| 参数 | 行为 |
|------|------|
| 不传参数（默认） | 启用 VLM 视觉分析增强模板内容；命名流程不依赖 VLM；若 `NAMING_HINT` 不清晰，按结构化命名兜底流程处理。脚本以原始文件名作为**临时**目录名（仅占位），Agent 必须完成命名并重命名 |
| `--skip-vlm` | 跳过 VLM，仅使用工具提取；命名流程不依赖 VLM；若 `NAMING_HINT` 不清晰，按结构化命名兜底流程处理 |
| `--enable-vlm` | 兼容旧用法；当前默认已启用 VLM |
| `--strict-vlm` | 严格要求 VLM 可用；若 API 未配置、连接失败或分析失败，则输出 `VLM_DEPENDENCY_MISSING` 并终止 |

---

## 功能说明

从现有 PowerPoint 文件逆向工程生成模板规范文件，支持：

- ✅ **工具提取**：解析 PPTX 内部结构，提取颜色方案、字体、布局等元数据
- ✅ **图片转换**：使用 Spire.Presentation.Free 将幻灯片转为 PNG（默认最多 10 页，可用 `--max-slides=N` 调整）
- ✅ **视觉分析**：默认使用视觉大模型分析幻灯片截图，提取设计风格、固定构图、页面类型、复刻规则和视觉纠偏建议
- ✅ **规范生成**：聚合两种结果，生成结构化的样式规范文件（Markdown 格式）

## 使用方式

### 基础用法

在 Claude Code 中执行：

```
/ppt-template-generate <PPT文件路径>
```

**示例：**
```
/ppt-template-generate ./my-presentation.pptx
/ppt-template-generate D:/templates/company-template.pptx
```

### 指定风格名称

```
/ppt-template-generate <PPT文件路径> --name=<风格名称>
```

**示例：**
```
/ppt-template-generate ./template.pptx --name="企业蓝"
```

### 指定输出目录

```
/ppt-template-generate <PPT文件路径> --output-dir=<输出目录路径>
```

**示例：**
```
/ppt-template-generate ./template.pptx --output-dir=D:/my-templates
/ppt-template-generate ./template.pptx --name="企业蓝" --output-dir=./custom-hub
```

> 若未指定 `--output-dir`，输出目录默认为 `ppt-template-hub`。以下文档中所有 `<输出根目录>` 均代表此值，指定后替换为实际路径。

---

## 工作流程

### Stage 1: 输入验证

1. 检查输入的 PPTX 文件是否存在
2. 验证文件格式是否为有效的 PowerPoint 文件
3. 确定输出路径：若传入 `--name`，直接使用该风格名；否则脚本先以原始文件名创建**临时目录**，Agent 读取 `NAMING_HINT` 后完成命名和重命名，见上方"风格命名后处理"

### Stage 2: 工具提取（Tool Extraction）

使用 python-pptx 解析 PPTX 内部结构：

#### 2.1 结构初始化与元数据加载
- 加载 Presentation 对象
- 访问 `prs.slide_masters` 获取母版信息

#### 2.2 全局"视觉基因"提取 (Theme Extraction)
- 读取 `ppt/theme/theme1.xml`
- **颜色提取**：扫描 `<a:clrScheme>` 节点
  - dk1 (深色1)、lt1 (浅色1)
  - accent1 到 accent6 (强调色)
  - 输出十六进制色值
- **字体提取**：扫描 `<a:fontScheme>`
  - Major Font (主标题字体)
  - Minor Font (正文字体)

#### 2.3 版式层级与占位符映射 (Layout Mapping)
- **母版扫描**：遍历 slide_masters，记录背景属性
- **版式定义**：遍历每个 slide_layout
  - 类型识别（标题、正文、图片、日期等）
  - 几何坐标（left, top, width, height）
  - 样式覆盖（字体、对齐方式）

#### 2.4 坐标与尺寸归一化 (Normalization)
- 将 EMU 单位转换为 cm 或 px
- 计算占位符相对位置（百分比）

#### 2.5 输出结构化数据
- 生成 `template_data.json` 中间文件

### Stage 3: PPT 转图片

**默认启用**，先用 python-pptx 将 PPTX 拆分为单页临时文件，再逐个通过 Spire.Presentation.Free 导出为 PNG，绕过免费版每文件最多 3 页的限制。

- **Step 2a**：`split_pptx.py` 拆分原始 PPTX → `temp/single_ppt/slide_001.pptx`、`slide_002.pptx`...
- **Step 2b**：逐个调用 Spire 转换 → `slides/slide-001.png`、`slide-002.png`...
- 转换工具：**Spire.Presentation.Free**（跨平台 Python 库）
- 转换数量：默认前 10 页（`--max-slides=N` 可调整）
- 可用 `--skip-convert` 跳过此步骤

**依赖检测**：
- 检查 `spire.presentation` 是否可用
- 不可用 → 脚本抛出错误，提示执行：`pip install spire.presentation.free`

**VLM 配置检测**（默认执行；传入 `--skip-vlm` 时跳过）：
- 检查 `vlm-config.json` 中 API 密钥是否已配置
- 配置缺失或 API 不可用 → 默认输出 `VLM_UNAVAILABLE_FALLBACK` 并自动降级为工具提取模式继续生成
- 传入 `--strict-vlm` 时，配置缺失或 API 不可用 → 脚本输出 `VLM_DEPENDENCY_MISSING`（Agent 终止任务并将错误原文展示给用户）

### Stage 4: VLM 视觉分析（默认启用）

将图片输入视觉大模型，提取：
- **规范配色**：只输出源 PPT 实际使用过、可复用于新 PPT 的颜色；主题文件中未使用的颜色仅保留在中间数据中，不写入最终模板规范
- **固定构图**：提取影响复刻相似度的页面骨架，如封面年份水印、中心边框、底部波浪、折角卡片、点阵等
- **版式语义**：识别版式适合表达的内容关系，如递进、分列/并列、对比、总分、流程、时间轴、矩阵、案例、数据强调等，并输出适用场景、信息关系、内容槽位和选择规则
- **风格偏好**：设计风格特征（极简、商务、创意等）
- **字体风格**：字体特征和排版风格
- **元素样式**：边框、阴影、圆角等细节

### Stage 5: 聚合生成 (Aggregation)

#### 数据合并
- 合并工具提取的结构化数据
- 仅针对内容页抽取版式样式元素，按结构指纹去重，生成可复用的内容页样式库；模板规范正文不输出逐页页面类型识别表
- **VLM 启用时**：合并 VLM 分析的视觉特征
- **VLM 跳过时**：仅使用工具提取数据

#### 规范文件生成
按照“执行规范”格式生成 Markdown，优先保留能指导后续生成的结论，避免输出分析过程、逐页观察和工具细节。若 VLM 已提供语义版式，工具抽取的内容页几何样式只作为中间数据保留，不重复写入正文。

```markdown
# PPT 模板样式规范

## 一、模板固定构图
## 二、写作基础
## 三、字体与字号
## 四、配色方案
## 五、页面与版式选择
  - 版式选择库（按内容关系选择）
## 六、母版固定元素
## 七、组件样式
## 八、视觉纠偏规则（仅存在 high/medium 纠偏时输出）
## 九、生成新 PPT 的硬约束
```

### 可复用风格图片资产

启用 VLM 时，技能会在整页截图分析之后执行"页面上下文 + 局部配图"复核：

- 先用 `images/image-map.json` 筛出疑似背景、纹理、边角装饰、标题装饰等候选资产。
- 再将完整页截图和候选局部图片一起发送给 VLM 判断资产角色。
- 只有被确认为 `must_reuse_for_style` 或 `optional_style_asset` 的背景/装饰类图片会写入 `temp/reusable-style-assets.json` 和 `template-spec.json`。
- 校园照片、人物照片、实验室照片、图表截图、品牌/校徽等内容或组织绑定图片不得作为通用 HTML 模板固定引用。

### 预设风格匹配与执行字号归一化

- 在生成最终 Markdown、`template-spec.json` 和 `html-templates/` 前，必须执行预设风格匹配。
- 匹配对象来自本技能内置的 `preset-style-profiles.json`，该文件是 `ppt-template-generate` 自有的预设参数快照，运行时不得依赖或读取 `pptx-craft`。
- 匹配信号包括源 PPT 实际颜色、组件特征、版式描述、VLM 风格语义、模板名称和图片资产角色。
- 当匹配置信度为 high 时，`execution_font_scale` 和 `execution_tokens.typography_scale` 使用匹配预设的字号、字重、行高、字距。
- 源 PPT 抽取得到的原始字号必须保留在 `font_scale` / `source_font_scale` 中，作为复刻证据，不直接作为下游生成字号。
- 超大封面字、章节展示字和装饰型文字必须进入 `typography_normalization.display_title_reference`，只作为视觉参考，不作为正文或页面标题的执行字号。
- 当匹配为 medium、low 或 ambiguous 时，不强制套用完整预设，只对超过 72px 的执行标题字号进行保护性收敛。

### Stage 5.5: Agent 装饰合成（仅当 VLM 已运行时）

检查 `temp/vlm_analysis.json` 是否存在（路径相对于当前风格的输出目录，如 `<输出根目录>/{风格名}/`）：

- **不存在** → 跳过此步骤。`generate-html-templates.js` 将输出无装饰最小骨架，流程不中断。
- **存在** → 执行以下操作：

1. 读取 `temp/vlm_analysis.json`，提取每个 `fixed_composition` 条目的 `required_elements`（装饰元素列表）和 `layout_rule`（版式规则说明）作为装饰判断依据
2. 读取 `slides/` 目录下已生成的幻灯片 PNG，视觉确认每个装饰元素的外观、位置、颜色关系
3. 对每个识别出的装饰元素生成如下字段：
   - `id`：kebab-case 命名（如 `decor-wave-bottom`、`decor-ink-edge`）
   - `css`：完整 CSS 规则字符串，使用 `var(--color-primary)` / `var(--color-background)` 引用颜色，不写死色值；使用 `position: absolute` 不影响文档流
   - `html`：对应的 `<div>` 或 `<img>` HTML 片段（含 `class="decor <id>"`）
   - `source_description`：一句话说明取自哪张截图的哪个区域（调试用）
4. 根据 `fixed_composition` 的 `page_type` 字段填写 `page_role_map`：`page_type` 含"封面" → `cover`，含"内容" → `content`，含"章节"/"目录"/"过渡" → `section`，含"结尾"/"结束"/"致谢" → `closing`
5. 将结果写入 `temp/decoration-map.json`，格式如下：

````json
{
  "schema_version": "decoration-map-v1",
  "decorations": [
    {
      "id": "decor-wave-bottom",
      "css": ".decor-wave-bottom { position: absolute; ... background: var(--color-primary); }",
      "html": "<div class=\"decor decor-wave-bottom\"></div>",
      "source_description": "底部水墨波浪，取自 slide-003.png 底部弧形装饰"
    }
  ],
  "page_role_map": {
    "cover":   ["decor-ink-edge", "decor-wave-bottom"],
    "content": ["decor-wave-bottom"],
    "section": [],
    "closing": []
  }
}
````

**约束（必须遵守）：**
- CSS 只用 `position: absolute`，不影响文档流
- 颜色只引用 CSS 变量，不写十六进制色值
- 背景图只引用 `../images/bg_images/` 路径，不引用 `slides/` 截图
- 截图中找不到视觉证据的装饰元素不生成，宁缺毋滥

---

## 输出产物

```
<输出根目录>/                           # 输出根目录（默认 ppt-template-hub，可通过 --output-dir 指定）
└── {风格名}/                           # 任务专用目录（重名时自动加序号，如 中国风_01）
    ├── {风格名}.md                     # 生成的样式规范文件
    ├── template-spec.json              # 机器可读模板规范，供下游技能稳定解析
    ├── slides/                         # PPT 转换的幻灯片截图（全部页面）
    │   ├── slide-001.png
    │   ├── slide-002.png
    │   └── slide-003.png
    ├── images/                         # 提取的所有原始图片及索引（去重）
    │   ├── image1.png
    │   ├── ...
    │   ├── image-map.json              # 机器可读图片属性地图（位置、层次、尺寸、asset_roles 高置信分类等）
    │   └── image-map.md                # 人类可读图片地图摘要；仅 bg_images 背景图进入强制迁移范围
    └── temp/                           # 临时文件
        ├── template_data.json          # 工具提取的结构化数据，含 slide_roles 与 content_layout_styles；规范正文仅写入 content_layout_styles
        ├── single_ppt/                 # 单页拆分临时文件（slide_001.pptx...）
        ├── vlm_analysis.json           # VLM 分析结果（启用 VLM 时）
        ├── decoration-map.json         # Agent 装饰合成产物（启用 VLM 时）
        └── quality_report.json         # 质量诊断：VLM 字段完整性、过滤色值、资产策略等
```

---

## 内容页样式抽取规则（仅源文件）

`template_data.json` 会输出：

- `slide_roles`：中间数据，仅用于判断哪些页属于内容页；不要写入生成模板 `.md`。
- `content_layout_styles`：只从 `content` 页抽取并去重的内容版式样式库，包含正文区域、图片区/视觉区、排版描述和选择规则；生成正文不得出现源 PPT 的页码或“来源页”分析。
- 无 VLM 或 VLM 未返回语义版式时，工具会为内容页样式补充轻量语义猜测：`semantic_type_guess`、`information_relation`、`selection_rule`。该猜测只使用高置信结构规则，无法判断时使用 `unknown`。

生成模板 `.md` 写入抽象化的「版式选择库」：

- 内容页必须从去重后的样式库中选择；选择依据包括内容丰富度、内容性质、是否包含图片、流程、对比、多模块展示等。
- VLM 启用时，优先使用「版式选择库」中的语义类型选择版式：先判断当前页内容关系是递进、并列、对比、总分、流程、矩阵、案例还是数据强调，再匹配对应版式。
- 封面页、章节页、内容页、结束页只给整体使用建议，不列出源 PPT 第几页对应什么角色。
- 例如「双段正文 + 右侧/右上配图」「多段正文两列排布」「时间轴/流程节点」「多模块图文面板」会作为不同内容页样式保留。
- 去重只合并结构相同或高度相似的内容页。

---

## 图片资产分类规则（仅源文件，高置信）

`image-map.json` 会输出 `asset_roles`，仅根据 PPTX 源文件结构做保守分类：

- `background`：正式背景图，或覆盖率 >90% 且位于底层的形状背景图。
- `large_texture` / `decorative_texture`：大面积形状填充纹理，常用于风格氛围。
- `repeated_decoration`：跨多页重复出现、位置尺寸稳定、面积较小的装饰图。
- `edge_decoration`：跨多页重复出现、位于边缘/角落、面积较小的装饰图。
- `unknown`：源文件结构信号不足，可能是内容配图，也可能是装饰；保留原样，不强制迁移。

聚合生成的模板 `.md` 只会把 `confidence = high` 的 `background` / `images/bg_images/` 正式背景图列为需要迁移的图片资产。`style_assets`、`images/assets/` 中的局部图片、纹理、点缀图只作为素材索引和视觉参考保留，当前不要求下游技能使用。

### 整页截图策略

- `slides/slide-xxx.png` 是整页视觉参考图，策略为 `reference_only`。
- 命名兜底流程**禁止读取 `slides/` 截图**；截图只用于已明确要求的 Agent 视觉分析或人工视觉参考，不作为降级命名依据。
- 后续生成新 PPT 时不得直接把 `slides/` 下的整页截图作为页面背景，否则会把源 PPT 的旧文字和旧内容一起带入。
- 可复用图片素材仅来自 `images/bg_images/` 中的正式背景图；`images/assets/` 中的局部图片、纹理、点缀图暂不作为复刻要求。

## 机器可读模板规范

`template-spec.json` 与 Markdown 同步生成，供下游技能读取，避免从自然语言正文中解析规则。当前结构包括：

- `schema_version`: 当前为 `ppt-template-spec-v1`
- `style_name`
- `slide_size`
- `colors`: `primary`、`background`、`text`、`allowed`
- `fonts` 与 `font_scale`
- `fixed_composition`
- `layout_library`: 优先来自 VLM 的 `layout_semantics`；缺失时使用工具兜底语义
- `visual_assets`: 仅包含 `image-map.json` 中高置信的正式背景图；VLM 识别出的装饰、纹理、点缀不写入强制复用资产
- `asset_policy`: `slides=reference_only`、`images_assets=optional_reference`、`bg_images=reuse_when_present`
- `hard_constraints`

`template-spec.json` 字号相关字段约定：

- `font_scale`: 兼容旧消费者的源字号字段。
- `source_font_scale`: 源 PPT 抽取字号，保留证据。
- `execution_font_scale`: 下游生成 PPT 时应优先使用的执行字号。
- `preset_style_match`: 预设风格匹配结果。
- `typography_normalization`: 字号归一化诊断，包括执行策略和展示型字号参考。
- `execution_tokens.typography_scale`: 与 `execution_font_scale` 保持一致，供严格执行型消费者读取。

## 环境要求

### 必需

- Node.js 18+
- Python 3.8+
- python-pptx（结构提取）

### 图片转换（默认启用）

| 软件 | 用途 | 安装 |
|------|------|------|
| `spire.presentation.free` | PPTX → PNG（跨平台） | `pip install spire.presentation.free` |

### 安装依赖

```bash
# 进入技能目录
cd skills/ppt-template-generate

# 创建虚拟环境（推荐使用 uv）
uv venv --python 3.11
uv pip install python-pptx spire.presentation.free

# 或使用 pip
pip install python-pptx spire.presentation.free
```

---

## 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--name` | 风格名称 | 指定时直接使用；不指定时脚本以原始文件名作**临时**目录名，并输出 `NAMING_HINT`，由 Agent 根据配色数据自主命名后重命名目录 |
| `--output-dir` | 输出根目录路径 | `ppt-template-hub`（相对于项目根目录，或绝对路径） |
| `--skip-convert` | 跳过 PPT 转图片 | 默认执行（前 10 页） |
| `--max-slides` | 最多转换页数 | 10 |
| `--skip-vlm` | 跳过 VLM 视觉分析 | 默认不跳过；显式传入才关闭 |
| `--enable-vlm` | 启用 VLM 视觉分析 | 兼容旧用法；当前默认已启用 |
| `--strict-vlm` | 严格要求 VLM 可用，不允许自动降级 | 默认关闭；VLM API 未配置或不可用时自动降级 |
| `--test-vlm` | 测试 VLM API 连接 | - |

---

## VLM 配置说明

### 配置文件位置

VLM 配置文件位于 `skills/ppt-template-generate/vlm-config.json`

### 配置选项

```json
{
  "enabled": true,
  "provider": "anthropic",
  "model": "claude-sonnet-4-6",
  "api": {
    "anthropic": {
      "apiKey": "${ANTHROPIC_API_KEY}",
      "baseUrl": "https://api.anthropic.com",
      "model": "claude-sonnet-4-6"
    },
    "openai": {
      "apiKey": "${OPENAI_API_KEY}",
      "baseUrl": "https://api.openai.com/v1",
      "model": "gpt-4o"
    }
  }
}
```

### 配置说明

| 配置项 | 说明 | 可选值 |
|--------|------|--------|
| `enabled` | 是否启用 VLM 分析 | `true` / `false` |
| `provider` | VLM 提供商 | `anthropic` / `openai` |
| `model` | 模型名称 | 取决于 provider |
| `api.anthropic.apiKey` | Anthropic API 密钥 | 支持环境变量 `${ANTHROPIC_API_KEY}` |
| `api.openai.apiKey` | OpenAI API 密钥 | 支持环境变量 `${OPENAI_API_KEY}` |

### 设置 API 密钥

**方式 1：使用环境变量（推荐）**

```bash
export ANTHROPIC_API_KEY="your-anthropic-api-key"
# 或
export OPENAI_API_KEY="your-openai-api-key"
```

**方式 2：直接编辑配置文件**

编辑 `vlm-config.json`，将 `${ANTHROPIC_API_KEY}` 替换为实际的 API 密钥。

### 测试 VLM 配置

```bash
node skills/ppt-template-generate/scripts/index.js --test-vlm
```

### 支持的模型

**Anthropic (Claude)**:
- `claude-opus-4-6` (推荐)
- `claude-sonnet-4-6`
- `claude-haiku-4-5`

**OpenAI**:
- `gpt-4o` (推荐)
- `gpt-4o-mini`

---

## 故障排查

### 问题 1：python-pptx 未安装

**错误信息：**
```
ModuleNotFoundError: No module named 'pptx'
```

**解决方案：**
```bash
pip install python-pptx
```

### 问题 2：Spire.Presentation.Free 未安装（PPT 转图片失败）

**错误信息：**
```
Spire.Presentation.Free 未安装，PPT 转图片无法执行。
```

**解决方案：**
```bash
pip install spire.presentation.free
# 或在 venv 中：
uv pip install spire.presentation.free
```

如暂时不需要图片转换，可传入 `--skip-convert` 跳过此步骤。

### 问题 3：PPT 文件损坏或格式不支持

**错误信息：**
```
ValueError: File is not a PPTX file
```

**解决方案：**
- 确保文件是 `.pptx` 格式（不是 `.ppt`）
- 使用 PowerPoint 修复文件后再尝试

### 问题 4：视觉大模型 API 不可用

**现象：** 默认情况下脚本输出 `VLM_UNAVAILABLE_FALLBACK` 并继续生成；传入 `--strict-vlm` 时输出 `VLM_DEPENDENCY_MISSING` 并终止

**解决方案：**
- 检查 `vlm-config.json` 中 `enabled` 是否为 `true`
- 检查 API 密钥是否已配置（环境变量或配置文件）
- 如 VLM 无法启用，可直接依赖默认自动降级，或显式传入 `--skip-vlm` 仅使用工具提取模式
- 如任务必须使用视觉分析，传入 `--strict-vlm` 让脚本在 VLM 不可用时失败即停

---

## 技术栈

### 工具提取
- **python-pptx**: PowerPoint 文件解析

### 图片转换（默认启用）
- **Spire.Presentation.Free**: 跨平台 PPTX → PNG（`pip install spire.presentation.free`）

### 视觉分析（默认启用，可用 `--skip-vlm` 关闭）
- **视觉大模型**: 图像理解和风格分析（Anthropic Claude / OpenAI GPT-4o）

### 产物生成
- **Node.js**: 流程编排
- **Markdown**: 规范文件格式

---

## 与其他技能配合

### 作为 pptx-craft 的上游

生成的样式规范文件可直接被 `pptx-craft` 使用：

```
ppt-template-generate → <输出根目录>/科技蓝/科技蓝.md
        ↓
pptx-craft 使用 --style=<输出根目录>/科技蓝/科技蓝.md 生成新 PPT
```

### 工作流示例

```bash
# 1. 从现有 PPT 提取风格
/ppt-template-generate company-template.pptx --name="company"

# 2. 使用提取的风格生成新 PPT
/pptx-craft "Q3 季度汇报" --style=company --pages=10
```

---

## 限制说明

- 仅支持 `.pptx` 格式，不支持旧版 `.ppt`
- 母版和版式的某些高级效果可能无法完全提取
- VLM 分析依赖模型能力，结果可能需要人工校验
- 复杂动画和交互效果无法在规范中体现
- Spire.Presentation.Free 免费版每个 PPTX 会在转换图片中添加水印

---

## 开发者信息

- **源码位置**: `skills/ppt-template-generate/`
- **核心脚本**:
  - `scripts/extract_structure.py` - 结构提取（python-pptx + zipfile）
  - `scripts/convert_to_images.js` - 图片转换调度（Node.js）
  - `scripts/convert_to_images_spire.py` - Spire 转换实现（Python）
  - `scripts/aggregate.js` - 结果聚合与规范生成
  - `scripts/vlm-analyzer.js` - VLM 视觉分析
  - `scripts/index.js` - 主流程入口
## HTML Template Skeletons

The script also writes `template-manifest.json` and `html-templates/` next to the Markdown style file. These files are for downstream `pptx-craft` template-replica mode: choose a skeleton first, then fill `data-slot` content.

- A fallback content template is always available, either as `content-default.html` or as an alias of an equivalent generated content layout in `template-manifest.json`.
- `cover.html`, `section.html`, and `closing.html` are generated only when `fixed_composition` identifies those roles.
- Dynamic content templates such as `layout-01.html` come from `template-spec.json.layout_library`, capped at 8 layouts. They are abstracted from the source PPT layout library, not fixed presets.
- Every skeleton must include `meta name="template-id"`, `data-template-id`, a `template-{id}` root class, and one or more `data-slot` placeholders.
- Skeletons must not contain old source PPT text, old content images, or `images/assets/` decorations. If a formal background is present, only `images/bg_images/` may be referenced. `decoration-map.json` fragments that use hardcoded colors, `slides/`, `images/assets/`, scripts, event handlers, or non-absolute CSS are ignored by the generator.
