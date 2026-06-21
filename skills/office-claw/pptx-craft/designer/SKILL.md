# HTML 幻灯片生成技能

> **路径变量说明**：`{skill_root}` 指向 `skills/` 目录。本文档位于 `skills/pptx-craft/designer/SKILL.md`，所以 `{skill_root}` 指的是 `../../../` 目录。

## 路径约定

**注意**：所有输入（outline_path、本页 research_path）与输出（output_dir）路径**均由 prompt 直接指定**，本技能不自行决定路径；缺少必需路径则报错终止。

本技能内部使用的固定路径（不通过参数指定）：

| 路径                              | 说明                                 |
| --------------------------------- | ------------------------------------ |
| `{skill_root}/pptx-craft/styles/` | 风格模板目录（相对于 skills 根目录） |

---

## 角色定位

你是资深演示文稿设计师，擅长用 HTML + Tailwind CSS 生成高信息密度、专业美观、视觉冲击力强的幻灯片。

---

## 流程原则（必读）

**本技能接收 outline-planner 和 research-writer 的输出产物作为输入**：`outline.md`（结构化大纲）+ 该页研究素材 `research-P{N}.md`（按页研究报告片段，以 `### P{N}:` 开头）。

> **研究素材来源**：pipeline 模式下每页素材为独立的 `research-P{N}.md` 文件。若调用方仅提供合并版 `research.md`，则取其中对应的 `### P{N}` 段落，结构等价。**结构性页面（`研究需求：❌`，如 cover/section/chapter/ending/agenda）无 research-P{N}.md 文件，仅依据 outline.md 生成。**

1. **阶段 1：风格识别**：按 prompt 中 Main Agent 注入的风格指令读取对应风格文件
2. **阶段 2：输入验证**：确认 outline.md 与本页研究素材（`research-P{N}.md`）文件存在（解析放到阶段 3）
3. **阶段 3：HTML 幻灯片生成**：从 outline.md 提取页面结构，从 `research-P{N}.md` 提取研究内容，合并生成该页 HTML
4. **阶段 4：交付确认**：验证所有 HTML 文件已正确生成
   - 每页输出为 `{output_dir}/page-N.pptx.html`（N 为页码）

**⚠️ 关键流程警告**：

- 必须提供 `outline_path` 和 `research_path`，否则报错终止
- **禁止**在无有效输入时尝试生成或推测内容
- 所有生成工作必须严格依据输入文件执行，不得偏离

---

## 执行流程

> **本技能只生成 HTML 幻灯片，无需任何环境检测或依赖安装**：HTML 是纯文本产出，不依赖 Playwright/npm。环境检测、依赖安装、以及后续的溢出校验与 PPTX 导出（需 Playwright）均由 pptx-craft 主控在其流程中统一处理，Charlie 不要执行 `npm install` / `npx playwright install` 等命令。

### 阶段 1：风格识别

**风格文件已在 prompt 中明确指定**，由 Main Agent 根据用户选择的 `style_id` 注入风格读取指令。Charlie 无需自行猜测或匹配风格关键词，只需按 prompt 中的指令执行：

- 如果 prompt 中包含风格文件路径指令 → 读取该文件，严格遵循其中的视觉规范
- 如果 prompt 中包含「自由发挥」指令 → 根据主题自行设计配色和字体
- 如果 prompt 中包含「自定义风格」描述 → 按用户描述的风格进行设计
- 如果 prompt 中未包含任何风格指令 → 使用默认视觉方案

#### 风格遵循原则（强制）

**⚠️ 风格定义是强制性规范，不是参考建议。**

当用户指定预设风格（business-classic/tech-minimal/elegant-narrative/industrial-tech）时，必须：

1. **严格遵循配色方案**：所有颜色必须来自风格定义的调色板，禁止使用未定义颜色
2. **严格遵循字体规范**：字号、字重、行高必须与风格定义一致
3. **严格遵循组件样式**：边框、圆角、阴影必须与风格定义一致
4. **禁止混合其他风格**：不允许将不同风格的元素组合使用
5. **禁止自由发挥配色**：当指定预设风格后，不允许根据主题"自行调整"配色

**反面案例**：
- 用户选择「商务经典」，你使用了工业科技的绿色 → **违规**
- 用户选择「科技极简」，你添加了典雅叙事风格的暖色调 → **违规**

**正面案例**：
- 用户选择「商务经典」→ 仅使用红色作为强调色，其他配色严格遵循 business-classic.md 定义
- 用户选择「自由发挥」→ 可以根据主题自行设计配色（此模式无约束）

---

### 阶段 2：输入验证

**本阶段核心任务**：确认输入文件存在即可。**结构/内容的解析与字段提取放到阶段 3 进行，本阶段不重复校验**。

1. **检查 outline.md**：尝试读取 `{outline_path}`；不存在则报错终止。
2. **检查本页研究素材**：
   - 内容页（`研究需求：✅`）：尝试读取该页 `research-P{N}.md`；不存在则报错终止。
   - 结构性页面（`研究需求：❌`）：无研究素材文件，跳过此检查，仅用 outline.md。
3. **通过后**：直接进入阶段 3 生成流程（在阶段 3 读取并提取所需字段）。

### 阶段 3：HTML 幻灯片生成

**目标**：基于大纲文件生成高分辨率（1280×720）HTML 页面。

**输入数据源**：

- `outline.md`：outline-planner 输出的结构化大纲（页面类型、标题、数据需求）
- `research-P{N}.md`：research-writer 输出的本页研究报告片段（核心论点、关键数据、案例素材）；结构性页面无此文件

**内容融合策略**：

1. **解析 outline.md**（Markdown 格式）：
   - 从 `## 页面规划` 的 `### P{N}:` 子章节提取本页的类型、标题、研究需求、内容概要、数据需求

2. **解析 `research-P{N}.md`**（Markdown 格式，仅内容页）：
   - 从以 `### P{N}:` 开头的片段提取本页的研究内容
   - 提取核心论点、关键数据清单（表格）、时序数据、对比数据、案例素材

3. **页面合并**：
   - outline.md 提供页面类型和数据需求，决定页面布局和内容方向
   - `research-P{N}.md` 提供核心论点、数据、案例，决定页面具体内容
   - 合并后的本页数据 = 页面类型 + 标题 + 数据需求 + 核心论点 + 关键数据 + 案例素材

**规格**：

- 页面容器：`.ppt-slide { width: 1280px; height: 720px; overflow: hidden; box-sizing: border-box; }`
- 内容安全区：`.content-safe { width: 1220px; height: 660px; margin: 30px auto; }`
- 主要内容**必须**放置在 `content-safe` 容器内（1220×660px，四周 30px 边距）；可覆盖其 gap/padding
- 背景、装饰元素可延伸到边距区（四周 30px），但不得超出 1280×720 边界
- `overflow: hidden` 仅用于 `.ppt-slide` 画布边界或明确标记为纯装饰的容器，禁止用于正文、标题、图表标签、数据卡片等核心信息容器
- 内容容器不得依靠裁切、滚动、折叠、省略号通过验收；出现容量不足时必须提炼、重排或拆页

**每页生成前的准备**（在生成每一页之前执行）：

- **图像搜索**：搜索该页的背景图、配图；数据图表或流程图用代码生成
- **内容信息搜索**：根据 `outline.md` 中该页的类型和数据需求以及该页 `research-P{N}.md` 中的关键数据、案例等，使用 WebSearch 搜索补充详细信息
- **素材决策**：真实世界对象用搜索素材；统计图表用 ECharts；逻辑图用 HTML/CSS/Canvas

**执行方式**：

- 使用独立 subagent（Agent 工具）逐页处理
- subagent prompt 必传材料：
  a. 用户原始任务原文
  b. 该页的内容素材：`outline.md` 中该页的结构信息（类型、标题、视觉策略）+ 该页 `research-P{N}.md` 的研究成果（核心论点、关键数据、案例素材；结构性页面无此文件）
  c. 风格参考文档路径（如商务经典：`{skill_root}/pptx-craft/styles/business-classic.md`）
  d. 输出文件路径

**执行方式**：

- 使用独立 subagent（Agent 工具）逐页处理
- subagent prompt 必传材料：
  a. 用户原始任务原文
  b. 该页的内容素材：`outline.md` 中该页的结构信息（类型、标题、视觉策略）+ 该页 `research-P{N}.md` 的研究成果（核心论点、关键数据、案例素材；结构性页面无此文件）
  c. 风格参考文档路径（如商务经典：`{skill_root}/pptx-craft/styles/business-classic.md`）
  d. 输出文件路径

**内容要求**：

- 所有文字必须是真实内容
- 必须完整表达该页的核心结论、关键数据和必要论据；辅助细节可压缩、合并或移至其他页面，不要求逐条照搬 research-P{N}.md
- 若页面预算无法容纳全部核心信息，必须拆页或报告冲突，禁止通过隐藏、截断或持续缩小字号硬塞
- 数据/对比/趋势 → 使用 ECharts 绘制实际图表
- 步骤/流程 → 绘制完整节点 + 连线 + 文字标注
- 关键数字加说明注释、结论加摘要高亮
- 视觉精细化：三级字体体系（标题 36-48px、副标题 24-28px、正文 16-20px）
- 装饰增强：页面边缘/背景层加轻量几何装饰

**文件命名**：`{output_dir}/page-N.pptx.html`

### 页面内容预算契约（生成 HTML 前必须完成）

每个页面 subagent 在编写 HTML 前，必须先根据页面类型、内容长度和视觉策略制定预算。预算无需单独写入文件，但必须在内部明确后再开始生成。

```yaml
page_type: data-analysis
density: high
title_lines: 1
regions:
  - name: chart
    width_ratio: 0.68
    height_ratio: 1.0
  - name: insights
    width_ratio: 0.32
    height_ratio: 1.0
max_cards: 4
max_core_points: 6
max_body_lines: 14
min_body_font_px: 14
min_caption_font_px: 11
whitespace_target: 18%-32%
```

**预算制定规则**：

1. 先确定标题、页眉、页脚占用，再计算核心内容区的实际可用高度。
2. 每个区域必须同时给出空间比例和内容上限，禁止只画布局、不限制内容量。
3. 预算必须保留至少 8% 的高度缓冲，用于字体差异、图表标签和 PPTX 转换误差。
4. 页面类型决定密度，不再要求每页统一出现图表、固定数量卡片或固定数量图标。
5. 最小字号是硬下限，不得为了塞入内容突破风格文件或本预算的下限。

**超预算处理顺序（强制）**：

1. 删除修饰语、合并重复观点，保留结论、关键数据和因果关系。
2. 将段落改为短句、标签或图表注释，减少重复解释。
3. 调整区域比例或改用更适合内容的布局。
4. 将次要材料移动到相邻页面；核心信息仍超预算时拆页。
5. 仅允许在风格字号范围内做小幅调整，禁止裁切、滚动、折叠、省略号或低于最小字号。

**内容密度检查（每页生成后必须执行）**：

生成每一页后，必须立即执行 **"内容丰满度检查清单"**：

1. **检查项目**（详见"内容丰满度保障体系"章节）：
   - [ ] 页面结构符合生成前制定的内容预算
   - [ ] 核心结论、关键数据和必要论据均已表达
   - [ ] 可视化形式与页面类型匹配，不为满足配额强行添加图表或卡片
   - [ ] 空白率处于页面预算的目标区间，且留白有明确的层级或视觉作用
   - [ ] 数据来源：页脚有标注
   - [ ] 无大段文字：无连续 > 100 字段落
   - [ ] 视觉层级清晰
   - [ ] **布局正确**：main 的直接子元素数量由信息结构决定，不设置无意义的包裹层
   - [ ] **布局容器选择**（重要，防止 flex-row/col 混淆）：
     - 左右分列布局 → main 使用 `grid` 或 `flex-row`，子元素使用 `min-w-0 min-h-0`
     - 上下分行布局 → main 使用 `flex flex-col gap-*`，子元素使用 `flex-1 min-h-0`
   - [ ] **子元素约束**：
     - 核心内容容器不得使用 `overflow-hidden` 掩盖内容
     - 需要裁切的纯装饰层必须标记 `data-ppt-role="decorative"`

2. **不满足时的处理（含搜索补充流程）**：

   **第 1 步：分析缺失项**

   识别具体未通过的项目，明确需要补充的内容类型。

   **第 2 步：针对性搜索补充（使用 WebSearch）**

   | 缺失项           | 搜索目的                 | 搜索关键词模板                                                                                         | 预期获取内容                                        |
   | ---------------- | ------------------------ | ------------------------------------------------------------------------------------------------------ | --------------------------------------------------- |
   | **缺数据可视化** | 获取可图表化的数据       | `"{主题} 市场规模 2024 2025 数据"`<br>`"{主题} 增长率 百分比 统计"`<br>`"{主题} 渗透率 市场份额 报告"` | 至少 3 个可量化的数据点，用于生成柱状图/折线图/饼图 |
   | **缺核心论据**   | 获取支撑结论的关键发现   | `"{主题} 关键发现"`<br>`"{主题} 核心观点 洞察"`<br>`"{主题} 趋势 挑战 机遇"`                           | 在页面预算范围内补充必要论据，每条 1-2 句话         |
   | **缺视觉语义**   | 识别适合的结构或标记     | 通常无需搜索；优先使用图表、CSS 图形、内联 SVG 或文字标记                                             | 只添加能帮助理解的视觉元素                           |
   | **缺案例**       | 获取真实案例/引用        | `"{主题} 应用案例 实践"`<br>`"{公司名} {主题} 实施案例"`<br>`"{主题} 成功案例 最佳实践"`               | 1-2 个具体案例，包含公司名、数据、效果              |
   | **缺数据来源**   | 获取权威数据来源         | `"{主题} 行业报告 2024 2025"`<br>`"{主题} 研究 数据 来源"`                                             | 权威机构名称（如 IDC、Gartner、麦肯锡等）           |

   **搜索执行规范**：
   - 每次搜索使用具体的主题词，避免泛泛搜索
   - 优先获取最近 1-2 年的数据（搜索词中加年份）
   - 优先选择权威来源（知名咨询公司、研究机构、行业协会）
   - 记录搜索结果的来源，用于页脚标注

   **搜索说明**：
   - 可基于本页 `research-P{N}.md` 中已有的内容进行补充搜索，搜索关键词可从其数据点、案例中提取
   - **数据来源标注**：使用本页 `research-P{N}.md` 中的来源

   **第 3 步：内容转换与生成**

   | 获取内容                  | 转换方式                           | 示例                                                             |
   | ------------------------- | ---------------------------------- | ---------------------------------------------------------------- |
   | 时间序列数据（≥3 个点）   | 生成折线图（趋势）或柱状图（对比） | "2020-500 亿，2021-720 亿，2022-980 亿" → 折线图（展示增长趋势） |
   | 类别占比数据（总和 100%） | 生成饼图/环形图                    | "市场份额：A 公司 35%，B 公司 28%…" → 环形图                     |
   | 对比数据（2-3 类别）      | 生成条形图或对比卡片               | "中国 37% vs 美国 42%" → 条形图                                  |
   | 多类别比较（≥4 类别）     | 生成柱状图                         | "各省份销售额：广东 120 亿、江苏 98 亿…" → 柱状图                |
   | 两变量关系                | 生成散点图                         | "广告投入 vs 销售额：10 组数据点" → 散点图                       |
   | 数据分布分析              | 生成直方图/箱线图                  | "用户年龄分布：20-30 岁 35%, 30-40 岁 42%…" → 直方图             |
   | 多维数据对比              | 生成雷达图                         | "产品能力评估：性能、易用性、可靠性等 6 维度" → 雷达图           |
   | 地理数据                  | 生成地图/热力地图                  | "各省市销售密度" → 热力地图                                      |
   | 矩阵数据                  | 生成热力图                         | "相关性矩阵：5x5 变量关系" → 热力图                              |
   | 关键观点                  | 转换为带图标的列表项               | 观点 + `fa-solid fa-check-circle`                                |
   | 真实案例                  | 转换为案例卡片                     | 公司名 + 数据 + 效果，配背景色块                                 |
   | 名人名言/引用             | 转换为引用块                       | `<blockquote>` 样式，配引号图标                                  |

   **第 4 步：重新生成该页**
   - 使用补充的内容重新生成 HTML
   - 确保新增内容已正确转换为可视化元素
   - 再次执行检查清单

   **第 5 步：重试控制**
   - 最多重试 5 次
   - 每次重试必须使用不同的搜索关键词
   - 5 次后仍失败 → 报错并提示用户，保留当前 HTML 供人工排查

   **错误信息示例**：

   ```
   内容密度检查未通过（重试 5 次后）：
   - 缺失：数据可视化（尝试搜索 "{主题} 市场规模"、"{主题} 增长率" 均未获取有效数据）
   - 缺失：装饰图标（当前 1 个，要求 3 个）

   建议：
   - 手动提供相关数据或调整输入内容
   - 或检查网络连接后重新生成
   ```

3. **记录检查结果**：
   - 每页检查通过后才能继续生成下一页
   - 记录每页的搜索关键词和补充内容类型
   - 全部页面生成完成后，输出整体检查结果摘要

---

### 阶段 4：交付

生成所有 HTML 页面后，执行以下步骤：

1. **验证 HTML 输出**：
   - 检查 `{output_dir}/page-*.pptx.html` 文件数量是否与大纲页数一致
   - 验证每个文件大小 > 0

2. **向用户报告完成状态**：
   - HTML 路径：`{output_dir}/`
   - 页数：{page_count} 页

**最终产物**：

- `page-N.pptx.html` - 分页 HTML 文件

> **注意**：HTML 校验、布局修复、CDN 依赖补充等后处理工作由 Main Agent（pptx-craft）统一执行，Designer 仅负责生成。

---

## HTML 幻灯片布局要求

成品阶段（1280×720）采用完整版布局要求，聚焦视觉精细化：

### 一、弹性布局约束（强制，预防溢出/空白/遮挡）

**核心结构**：每页必须使用以下弹性布局结构，从代码层面预防布局问题：

```html
<div class="ppt-slide flex flex-col h-[720px] overflow-hidden">
  <!-- 页头：固定高度，禁止压缩 -->
  <header class="h-[60px] flex-shrink-0">
    <h1 class="text-[36px]">页面标题</h1>
  </header>

  <!-- 内容区：弹性填充，自动适应剩余空间 -->
  <main class="flex-1 min-h-0 flex flex-col gap-4">
    <div class="flex-1 min-h-0">内容区 1</div>
    <div class="flex-1 min-h-0">内容区 2</div>
  </main>

  <!-- 页脚：固定高度，禁止压缩 -->
  <footer class="h-[30px] flex-shrink-0">
    <span>页脚信息</span>
  </footer>
</div>
```

**四条强制规则**：

| 规则              | 目的         | 代码要求                                  |
| ----------------- | ------------ | ----------------------------------------- |
| **画布边界保护**  | 防止装饰越界 | 仅 `.ppt-slide` 使用 `h-[720px] overflow-hidden` |
| **页头/页脚固定** | 防止压缩变形 | `h-[60px]` / `h-[30px]` + `flex-shrink-0` |

> **仅限页头/页脚**：固定高度仅适用于页头（header）和页脚（footer）。
> 主要内容区**必须**使用 `flex-1 min-h-0` 弹性高度。
> | **内容区弹性填充** | 允许容器正确收缩 | `flex-1 min-h-0`，不得使用裁切掩盖超预算内容 |
> | **禁止滚动与折叠** | PPT 无交互滚动语义 | 禁止 `overflow-auto`、滚动条、折叠面板；超预算时提炼、重排或拆页 |
> | **main 结构服从信息结构** | 避免无意义布局层 | 可包含一个或多个直接子元素，不强制凑足数量 |

**为什么需要 `min-h-0`**：

- 在 flex 布局中，`flex-1` 默认有 `min-height: auto` 的行为
- 当内容过多时，内容区可能被压缩到 0 高度
- `min-h-0` 允许 flex/grid 子元素缩小到父容器分配的高度
- 它不会自动解决内容超量；内容是否放得下必须由页面预算和真实渲染检查保证

**避免无意义包裹层**：

```html
❌ 错误示例 - 为满足数量规则添加没有语义的空容器：
<main class="flex-1 min-h-0 flex flex-col gap-4">
  <div class="h-full">
    真实内容
  </div>
  <div class="flex-1"></div>
</main>

✅ 正确示例 - 单一主视觉页面可只有一个语义区域：
<main class="flex-1 min-h-0 flex">
  <section class="flex-1 min-h-0">主图表或主视觉</section>
</main>

✅ 正确示例 - 多区域页面按信息结构分配空间：
<main class="flex-1 min-h-0 flex flex-col gap-4">
  <section class="flex-[2] min-h-0">主内容</section>
  <aside class="flex-1 min-h-0">补充洞察</aside>
</main>
```

**规则说明**：

- `main` 的直接子元素数量由页面叙事决定
- 单一图表、单一流程或单一大结论可以使用一个语义容器
- 多区域页面使用 `gap-*` 和明确比例共同分配空间
- 参与弹性分配的子元素应设置 `min-h-0`，水平布局同时设置 `min-w-0`
- 禁止子元素使用 `h-full` 或 `h-[xxxpx]` 固定高度占满整个 `main`
- 禁止核心内容容器使用 `overflow-hidden`、line-clamp 或省略号隐藏信息

**子元素撑满父元素规则**（嵌套布局必读）：

在 Grid/Flex 嵌套布局中，子元素撑满父元素遵循以下核心原则：

```
水平布局（左右分配）→ 子元素撑满高度
垂直布局（上下分配）→ 子元素撑满宽度
```

**快速决策表格**（生成代码前必读）：

| 父容器布局类型    | 判断特征           | 子元素应使用的类                                                           |
| ----------------- | ------------------ | -------------------------------------------------------------------------- |
| **Grid 水平分列** | `grid grid-cols-*` | `min-w-0 min-h-0` + 可选 `flex flex-col gap-*` 用于内部分行 |
| **Flex 垂直分行** | `flex flex-col`    | `flex-1 min-h-0`                                            |
| **Flex 水平排列** | `flex flex-row`    | `flex-1 min-w-0 min-h-0`                                    |

**记忆口诀**：

- Grid 分列 → 子元素允许收缩 → 用 `min-w-0 min-h-0`
- Flex 分行 → 子元素要分配**高度** → 用 `flex-1`
- 无论哪种布局，核心内容都必须完整可见，不得依赖裁切

---

**Grid 子元素撑满高度**（左右分配）：

```html
<!-- 父容器：Grid 水平分列 -->
<div class="grid grid-cols-2 gap-4 min-h-0">
  <div class="min-w-0 min-h-0">左侧</div>
  <div class="min-w-0 min-h-0">右侧</div>
</div>
```

关键点：

- `min-h-0` 是**必须的**，覆盖 Grid 子元素默认的 `min-height: auto`
- Grid 子元素默认会被内容撑开，`min-h-0` 让其能被压缩
- `min-w-0` 防止长文本或图表标签把列宽撑出画布

**Flex Column 子元素撑满宽度**（上下分配）：

```html
<!-- 父容器：Flex 垂直分行 -->
<div class="flex flex-col min-h-0">
  <!-- 子元素自动撑满宽度，无需额外处理 -->
  <div class="flex-1 min-h-0">上</div>
  <div class="flex-1 min-h-0">下</div>
</div>
```

关键点：

- Flex column 子元素默认 `width: auto`，会自动撑满容器宽度
- 只需要处理高度，使用 `flex-1 min-h-0` 控制垂直空间分配

**嵌套布局示例**：

```html
<!-- 外层：Grid 左右分列 -->
<div class="grid grid-cols-2 gap-4 min-h-0">
  <!-- 左侧列 -->
  <div class="min-w-0 min-h-0">
    <!-- 内层：Flex 垂直分行 -->
    <div class="flex flex-col gap-3 h-full min-h-0">
      <div class="flex-1 min-h-0">图表区</div>
      <div class="flex-1 min-h-0">说明区</div>
    </div>
  </div>
  <!-- 右侧列 -->
  <div class="min-w-0 min-h-0">
    <!-- 内层：Flex 垂直分行 -->
    <div class="flex flex-col gap-3 h-full min-h-0">
      <div class="flex-1 min-h-0">卡片 1</div>
      <div class="flex-1 min-h-0">卡片 2</div>
      <div class="flex-1 min-h-0">卡片 3</div>
    </div>
  </div>
</div>
```

**内容区填充要求**（防空白）：

- 内容区内的图表、卡片必须设置 `w-full` 或百分比宽度
- 每页至少包含：1 个可视化图表 + 3 个数据卡片/要点
- 禁止内容区设置为固定高度（除非是内部卡片容器）

**层级规范**（防遮挡）：

```
背景装饰：z-0 或更低（使用 -z-10 等）
主要内容：不设置 z-index（默认层）
强调文字：z-50 relative
```

---

### 二、固定尺寸约束

在上述弹性布局基础上，所有内容必须在固定容器内，禁止超出 1280×720 边界：

> **注意**：`.ppt-slide` 和 `.content-safe` 的固定高度仅作为最外层容器约束。
> 内部元素**必须**使用弹性布局（flex-1, min-h-0），**禁止**对内部元素使用固定高度。

```css
.ppt-slide {
  width: 1280px; /* 固定宽度 */
  height: 720px; /* 固定高度 */
  overflow: hidden; /* 超出 1280×720 边界的内容隐藏 */
  box-sizing: border-box;
}

/* 内容安全区：核心内容容器（必须使用；间距 gap 由内容层按密度自定，容器不钉死 gap） */
.content-safe {
  width: 1220px; /* 左右各留 30px 边距 */
  height: 660px; /* 上下各留 30px 边距 */
  margin: 30px auto; /* 居中 + 边距 */
}
```

**尺寸说明**：

| 区域             | 尺寸           | 说明                                         |
| ---------------- | -------------- | -------------------------------------------- |
| **幻灯片总尺寸** | 1280px × 720px | 固定边界，任何内容不得超出                   |
| **内容安全区**   | 1220px × 660px | 核心内容区域（**必须使用**；左右/上下各 30px 边距）  |
| **边距区**       | 四周 30px      | 可被背景、装饰元素使用，但不建议放置核心内容 |

**关键规则**：

- `overflow: hidden` 隐藏的是**超出 1280×720 边界**的内容，而非 padding 区域
- 背景图、装饰元素**可以**延伸到边距区（30px padding）
- 核心文字、图表等内容**必须**在 `content-safe` 容器内（1220×660px）
- 如果需要在边距区放置内容，需自行确保不超出 1280×720 边界

**使用示例**：

```html
<div class="ppt-slide flex flex-col" type="content">
  <!-- 内容安全区：主要内容在此区域内 -->
  <div class="content-safe relative">
    <header class="h-[60px]">
      <h1 class="text-[36px]">页面标题</h1>
    </header>
    <!-- main 的结构和子元素数量由页面叙事决定 -->
    <main class="flex-1 min-h-0 flex flex-col gap-4">
      <!-- 正文内容根据叙事结构分布 -->
      <div class="flex-1 min-h-0">
        <!-- 内容区块 1 -->
      </div>
      <div class="flex-1 min-h-0">
        <!-- 内容区块 2 -->
      </div>
    </main>
    <footer class="h-[30px]">
      <span>页脚信息</span>
    </footer>
  </div>
</div>
```

**2. 空白率控制**

- 空白率目标由页面预算和页面类型决定，不使用统一 `< 30%` 的硬阈值
- 封面页、章节页、结束页允许较高留白；数据页和矩阵页通常使用更高的信息密度
- 排除项不计入空白：全屏背景、窄色条装饰线、低透明度元素、纯装饰圆圈、纯布局容器
- 空白是否需要修复，以是否破坏视觉重心、阅读路径或信息层级为判断依据

**3. 内容密度控制**

- 单页信息量必须符合生成前的页面预算
- 图文结合，优先使用最能表达结论的可视化形式
- 不强制每页同时包含图表、数据卡片和图标；元素必须服务于内容

---

### 三、文本重叠避免

- 文本元素之间的最小间距建议 16px 以上
- 使用 flex/grid 布局时确保元素不会挤压重叠
- 禁止使用绝对定位放置核心内容

### 四、元素遮挡避免

- 背景装饰：`z-0` 或更低
- 主要内容：不设置 z-index（默认层）
- 强调文字：`z-50 relative`
- 卡片、图表等容器内的文本必须清晰可见

---

## 视觉设计规范

### 色彩系统

| 类型         | 颜色      | 用途             |
| ------------ | --------- | ---------------- |
| **深色背景** | `#1A1D21` | 专业沉稳主题     |
| **浅色背景** | `#F8F7F5` | 优雅温和主题     |
| **纯黑背景** | `#0D0D0D` | 高端科技主题     |
| **主题色**   | `#4A6C8C` | 主色调，专业可信 |
| **辅助色**   | `#8D99AE` | 次级信息、过渡   |
| **强调色**   | `#D4A373` | 重点突出         |
| **深色文字** | `#2B2D42` | 浅色背景上的文字 |
| **浅色文字** | `#F8F7F5` | 深色背景上的文字 |

### 字体系统

- **商务经典 / 通用商务**：`WenYuan Sans SC`（文源黑体）- 非衬线，稳重、清晰，适合经营分析、方案汇报、公司规范类材料
- **科技极简 / 产品展示**：`NanxiXinyuanti`（南西新圆体）- 圆润非衬线，干净、有亲和力，适合轻科技、产品体验、创新主题
- **典雅叙事 / 学术报告**：`WenJin Mincho Plane 0`（文津宋体）- 衬线/宋体，书卷感强，适合学术、文化、研究型、叙事型材料；正文信息密集时可搭配 `WenYuan Sans SC`
- **工业科技 / 工程硬核**：`Frex Sans GB`（械黑 GB）- 硬朗非衬线，结构感强，适合制造、工程、AI 基建、工业科技主题
- **通用兜底**：`Noto Sans SC` - 思源黑体，稳定兼容；
- **使用约束**：同一份 PPT 最多使用 2 个字体家族；所选字体必须作为 `font-family` 的第一个具体字体名，避免只写 `serif` / `sans-serif` 等泛型字体

> **⚠️ 字号优先级（避免与风格文件冲突时反复纠结）**：当**风格文件**（如 `business-classic.md`）给出了具体字号（如标题 35px），**以风格文件为准**，覆盖本 designer 文档里的默认字号（如 32px）。本文档的字号梯度仅在风格文件未指定时作为兜底。**不要在两套字号间横跳——风格文件优先。**

---

## HTML 代码规范

> **容器类名强制要求**：HTML 页面**必须**包含 `<div class="ppt-slide flex flex-col" type="页面类型">` 容器。转换脚本通过 `.ppt-slide` 类名识别页面，缺失将导致转换失败。

### 基础模板结构（成品 HTML）

```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>演示文稿标题</title>

    <!-- Tailwind CSS（必选） -->
    <script src="https://cdn.digitalhumanai.top/slidagent/pptx-craft/assets/vendors/tailwind.js"></script>

    <!-- 字体引用：发布包内置字体均通过 fonts.css 引入，禁止写本机文件路径 -->
    <link
      href="https://cdn.digitalhumanai.top/slidagent/pptx-craft/assets/css/fonts.css"
      rel="stylesheet"
    />

    <!-- FontAwesome 图标（按需：使用了 fa-solid/fa-regular/fa-brands 等图标时引入） -->
    <link
      href="https://cdn.digitalhumanai.top/slidagent/pptx-craft/assets/vendors/fontawesome/css/all.min.css"
      rel="stylesheet"
    />

    <!-- ECharts 图表库（按需：使用了 echarts.init/echarts.setOption 时引入） -->
    <script src="https://cdn.digitalhumanai.top/slidagent/pptx-craft/assets/vendors/echarts.min.js"></script>

    <!-- MathJax 数学公式（按需：使用了 \frac/\sqrt 等数学公式时引入，不需要时删除） -->
    <script src="https://cdn.digitalhumanai.top/slidagent/pptx-craft/assets/vendors/mathjax/tex-svg.min.js"></script>

    <!-- Tailwind 配置 -->
    <script>
      tailwind.config = {
        theme: {
          extend: {
            colors: {
              primary: "#4A6C8C",
              secondary: "#8D99AE",
              accent: "#D4A373",
              bgDark: "#1A1D21",
              bgLight: "#F8F7F5",
              textDark: "#2B2D42",
              textLight: "#F8F7F5",
            },
            fontFamily: {
              sans: ["WenYuan Sans SC", "Noto Sans SC", "sans-serif"],
              rounded: ["NanxiXinyuanti", "WenYuan Sans SC", "sans-serif"],
              industrial: ["Frex Sans GB", "WenYuan Sans SC", "sans-serif"],
              serif: ["WenJin Mincho Plane 0", "Noto Serif CJK SC", "serif"],
            },
          },
        },
      };
    </script>

    <!-- 自定义样式 -->
    <style type="text/tailwindcss">
      @layer utilities {
        .ppt-slide {
          @apply relative w-[1280px] h-[720px] mx-auto box-border overflow-hidden flex flex-col;
        }
      }
    </style>

    <!-- 全局文字颜色 -->
    <style>
      body {
        color: #2b2d42; /* 根据视觉方案设置 */
      }
    </style>
  </head>

  <body class="bg-gray-50">
    <!-- 每一页都是一个独立的 ppt-slide 容器 -->
    <div class="ppt-slide flex flex-col" type="cover">
      <!-- 页面内容 -->
    </div>
  </body>
</html>
```

### 页面容器规范

#### HTML 幻灯片容器

- **必须使用** `<div class="ppt-slide flex flex-col" type="页面类型">` 作为每页的容器
- **⚠️ 所有页型一视同仁（强制）**：封面（cover）、章节分隔（section/chapter）、结束页（ending）等**结构性页面**与正文内容页**使用完全相同的容器与全局防溢出 CSS**——必须带 `class="ppt-slide flex flex-col"` 且 `<head>` 内含「防溢出硬性约束 → 全局 CSS 约束」整段。**禁止**结构页另起一套简化容器（如裸 `<div style="height:720px">` 或省略 `.ppt-slide` 类），否则全局防溢出约束失效，会导致字重叠/溢出。
- **页面尺寸**：固定为 `1280px × 720px`
- **页面边距**：`30px`
- **内容区域**：1220 × 660px
- **页面类型属性**：`type` 属性必须设置为以下值之一：
  - `cover` - 封面页
  - `table_of_contents` - 目录页
  - `chapter` - 章节过渡页
  - `content` - 正文内容页
  - `final` - 结束页

### 样式使用规范

**禁止内联样式**：

- 禁止在 HTML 元素上使用 `style="..."` 属性（图表库配置除外）
- 所有样式必须通过 Tailwind CSS 类名实现
- 图表库 (ECharts) 的配置选项不受此限制，可在 JS 配置对象中使用 `itemStyle`、`lineStyle` 等

**支持 Tailwind JIT 任意值（明确声明，无需自我怀疑）**：

- **支持**任意值语法 `xxx-[...]`，如 `text-[32px]`、`h-[660px]`、`flex-[3]`、`basis-[30%]`、`gap-[10px]` 等，可放心使用。
- **按比例分配空间的 canonical 写法**：用 `flex-[N]`（如左右栏 `flex-[3]` / `flex-[2]`）；不要在 `flex-[N]` 与 `grow + basis-[%]` 之间反复纠结，统一用 `flex-[N]`。

**HTML 语法规范（强制）**：

- `<style type="text/tailwindcss">` 必须使用 `</style>` 闭合，**严禁使用 `</script>`**
- `<script>` 必须使用 `</script>` 闭合
- 在生成 HTML 代码时，必须仔细检查标签闭合是否正确

**示例对比**：

```html
<!-- ❌ 错误：style 标签使用 script 闭合 -->
<style type="text/tailwindcss">
    ...
  </script>  <!-- 错误！应该用
</style>
-->

<!-- ✅ 正确：使用 style 闭合 -->
<style type="text/tailwindcss">
  ...
</style>
```

**标签闭合自检清单**（生成每页后自查）：

- [ ] 检查所有 `<style type="text/tailwindcss">` 是否使用 `</style>` 闭合
- [ ] 检查所有 `<script>` 是否使用 `</script>` 闭合
- [ ] 检查 `<style>` 和 `</style>` 数量是否一致
- [ ] 检查 `<script>` 和 `</script>` 数量是否一致

---

### 防溢出硬性约束（必须遵守）

**核心原则**：所有内容必须在 `1280px × 720px` 容器内，有效内容区为 `1220px × 660px`（扣除 30px 内边距）。

#### 1. 全局 CSS 约束（必须添加到每个 HTML 文件）

在 `<head>` 中的 `<style type="text/tailwindcss">` 块内，**必须**添加以下全局约束：

```html
<style type="text/tailwindcss">
  @layer utilities {
    /* 幻灯片容器 */
    .ppt-slide {
      @apply relative w-[1280px] h-[720px] mx-auto box-border overflow-hidden;
    }

    /* 全局防溢出约束 - 应用到所有子元素 */
    .ppt-slide *,
    .ppt-slide *::before,
    .ppt-slide *::after {
      @apply box-border;
      max-width: 100%;
    }

    /* 图片/视频/图表防溢出（图表容器匹配大小写不敏感，兼容 trendChart 等驼峰 id 及 .chart-container / .echarts-main class） */
    .ppt-slide img,
    .ppt-slide video,
    .ppt-slide canvas,
    .ppt-slide svg,
    .ppt-slide .echarts-main,
    .ppt-slide .chart-container,
    .ppt-slide [id*="chart" i] {
      @apply max-w-full max-h-full object-contain;
    }

    /* 图表容器高度防御：凡 id 含 "chart"（大小写不敏感，含驼峰 trendChart/compareChart）或常见图表 class，
       默认撑满父高并兜底最小高度，避免父级非 flex-col 时高度塌缩为 0 导致 ECharts 不渲染（页面看起来像纯文本） */
    .ppt-slide [id*="chart" i],
    .ppt-slide .chart-container,
    .ppt-slide .echarts-main {
      width: 100%;
      height: 100%;
      min-height: 160px;
    }

    /* 内容安全区：核心内容容器（必须使用）。注意：不钉死 gap，间距由内容层按密度自定 */
    .content-safe {
      @apply w-[1220px] h-[660px] my-[30px] mx-auto flex flex-col overflow-hidden;
    }

    /* 禁止模糊滤镜效果（PPT 渲染不一致） */
    .ppt-slide [class*="blur"],
    .ppt-slide [style*="blur"] {
      filter: none !important;
      backdrop-filter: none !important;
    }

    /* 禁止半透明渐变背景，使用纯色替代 */
    .ppt-slide [class*="gradient"] {
      background-image: none !important;
    }

    /* 禁止毛玻璃效果 */
    .ppt-slide [class*="backdrop-blur"],
    .ppt-slide [style*="backdrop-filter"] {
      backdrop-filter: none !important;
    }

    .ppt-slide {
      /* 全局字体设置：按所选风格替换首位字体，保持 Noto Sans SC 作为兜底 */
      font-family: "WenYuan Sans SC", "Noto Sans SC", sans-serif !important;
    }
  }
</style>
```

**说明**：

- `.ppt-slide` 不再设置 `padding: 40px`，而是通过 `.content-safe` 的 `my-[30px] mx-auto` 实现四周 30px 边距
- 背景、装饰元素可以使用 `.ppt-slide` 的全部 1280×720 空间
- **核心内容必须放置在 `.content-safe` 内**（1220×660px），自动获得四周 30px 边距

> **⚠️ 容器与间距的权威口径（全 skill 唯一标准，避免反复纠结）**：
> 1. **`.content-safe` 必须使用**（承载核心内容）；但**允许覆盖它的间距/内边距类**（`gap-*`/`p-*`），容器本身不再钉死 `gap`。
> 2. **gap 基准 = `gap-4`**：稀疏/常规页用 `gap-4`；**密集页（≥6 个板块）直接用 `gap-1`/`gap-2`**，无需犹豫——密度要求（空白<30%）下小 gap 是预期做法，不是违规。
> 3. 全 skill 示例的 gap 取值以此为准；示例里出现的 `gap-6` 仅为"稀疏页"演示，密集页请按上表用小 gap。

#### 2. 文本完整显示规则

| 手段 | 用途 | 约束 |
| ---- | ---- | ---- |
| `.break-words` | 长 URL、英文单词自动换行 | 可用于辅助信息 |
| `.text-balance` | 平衡标题换行 | 标题仍须完整显示 |
| 文案提炼 | 删除修饰语、合并重复表述 | 首选处理方式 |
| 拆分页面 | 核心信息超过单页预算 | 必须优先于截断或低于最小字号 |

禁止对标题、正文、图表标签、来源和数据卡片使用 `text-overflow: ellipsis`、`line-clamp` 或其他截断类。

#### 3. 布局容器约束

**内容页标准结构**（必须遵守）：

```html
<div class="ppt-slide flex flex-col" type="content">
  <!-- 内容安全区：所有主要内容必须在此容器内 -->
  <div class="content-safe">
    <!-- 页头：标题区（固定高度 ~60px） -->
    <header class="h-[60px] flex-shrink-0">
      <h1 class="text-[36px] font-bold text-balance">页面标题</h1>
    </header>

    <!-- 内容区：弹性高度，自动适应 -->
    <main class="flex-1 min-h-0 flex flex-col gap-6">
      <!-- 使用 flex/grid 布局，禁止绝对定位 -->
      <!-- 
      ⚠️ 布局方向判断规则（重要，防止 flex-row/col 混淆）：
      - grid-cols-* / flex-row → 水平布局（左右分列）→ 子元素必须使用 h-full min-h-0
      - flex-col → 垂直布局（上下分行）→ 子元素必须使用 flex-1 min-h-0
      -->
      <!-- 方案 A：Grid 水平分列（左右布局） -->
      <div class="grid grid-cols-2 gap-6 flex-1 min-h-0">
        <!-- ⚠️ grid 子元素：水平布局 → 必须使用 h-full min-h-0 撑满父元素高度 -->
        <div class="min-w-0 min-h-0 flex flex-col gap-4">
          <!-- 左列内容 -->
        </div>
        <div class="min-w-0 min-h-0 flex flex-col gap-4">
          <!-- 右列内容 -->
        </div>
      </div>

      <!-- 方案 B：Flex 垂直分行（上下布局） -->
      <!--
      <div class="flex flex-col gap-6 flex-1 min-h-0">
        <!-- ⚠️ flex-col 子元素：垂直布局 → 必须使用 flex-1 min-h-0 分配高度 -->
      <!-- <div class="flex-1 min-h-0">上部分内容</div> -->
      <!-- <div class="flex-1 min-h-0">下部分内容</div> -->
      <!-- </div> -->
    </main>

    <!-- 页脚：固定高度 ~30px -->
    <footer
      class="h-[30px] flex-shrink-0 flex justify-between items-center text-[14px] text-gray-500"
    >
      <span>页码</span>
      <span>日期</span>
    </footer>
  </div>
</div>
```

#### 4. 字体大小约束

| 元素类型          | 字号范围 | Tailwind 类   | 使用场景               |
| ----------------- | -------- | ------------- | ---------------------- |
| 页面标题          | 32px     | `text-[32px]` | 封面标题、页面标题     |
| 一级标题/卡片标题 | 20px     | `text-[20px]` | 卡片标题、二级章节标题 |
| 二级标题/内容文本 | 18px     | `text-[18px]` | 内容区块标题、图表标题 |
| 正文              | 16px     | `text-[16px]` | 正文内容、列表项       |
| 辅助文字          | 14px     | `text-[14px]` | 注释、来源、页脚、图注 |

**字体大小梯度规则**：相邻层级的字号比例应 ≥ 1.2，确保视觉层级清晰。

#### 5. 图表容器约束

<!-- ⚠️ 注意：h-full 仅在父元素有 flex flex-col 时有效 -->
<!-- 父元素必须设置 flex flex-col，否则 flex-1 无法正确计算高度 -->

**ECharts 图表安全容器**（强制：父元素必须是 flex 容器）：

```html
<!-- ✅ 正确：父元素有 flex flex-col，图表用 flex-1 min-h-0 弹性填充 -->
<div class="bg-white border p-4 flex flex-col">
  <h3 class="text-[18px] font-semibold mb-3">图表标题</h3>
  <div class="flex-1 min-h-0">
    <div id="chart-1" class="w-full h-full"></div>
  </div>
</div>

<!-- ❌ 错误：父元素缺少 flex flex-col，flex-1 无效，高度为 0 -->
<div class="bg-white border p-4">
  <h3 class="text-[18px] font-semibold mb-3">图表标题</h3>
  <div id="chart-1" class="w-full flex-1 min-h-0"></div>
</div>
```

**强制规则**：

1. 图表容器的**直接父元素**必须有 `flex flex-col` 类
2. 图表包装器使用 `flex-1 min-h-0`，内部 chart div 使用 `w-full h-full`
3. 禁止在非 flex 父元素内使用 `flex-1`
4. **必须禁用动画**：`animation: false`（PPT 是静态输出，动画会导致截图/转换时图表未渲染完成）
5. **必须使用 SVG 渲染器**：`echarts.init(document.getElementById('xxx'), null, { renderer: 'svg' })`（SVG 可被 html-to-pptx 引擎直接提取矢量图）
6. **图表容器 ID 命名规范**：ECharts 图表容器的 `id` 应包含 `chart` 子字符串（如 `chart-1`、`principle-chart`、`market-chart`、`trendChart`、`compareChart` 均可）。全局 CSS 防御规则通过**大小写不敏感**选择器 `[id*="chart" i]`（同时覆盖 `.chart-container` / `.echarts-main` class）匹配图表容器并兜底高度（撑满父高 + `min-height:160px`），因此小写、连字符、驼峰写法都能命中、不会因高度塌缩为 0 而不渲染。仍建议优先用小写 `chart`（如 `market-chart`）以保持一致
7. **禁止 ECharts 渐变填充**：不得在 `areaStyle.color`、`itemStyle.color`、`lineStyle.color`、`visualMap.inRange.color` 等配置中使用 `{ type: "linear" | "radial", colorStops: [...] }` 或 `echarts.graphic.LinearGradient/RadialGradient`。这些写法会在 SVG 中生成 `linearGradient/radialGradient` + `fill="url(#...)"`，导出 PPTX 时会被强制转成位图。需要面积色时，使用半透明纯色，例如 `areaStyle: { color: "rgba(66, 153, 225, 0.18)" }`。
8. **必须显式设置图表字体**：定义 `CHART_FONT_FAMILY`，并在 `textStyle.fontFamily`、`legend.textStyle.fontFamily`、`axisLabel.fontFamily`、`nameTextStyle.fontFamily`、`series[].label.fontFamily` 中使用同一字体栈；首位字体必须与页面所选风格一致

```html
<script>
  // ECharts 配置
  const CHART_FONT_FAMILY = "WenYuan Sans SC, Noto Sans SC, sans-serif";
  const chart = echarts.init(document.getElementById("chart-1"), null, {
    renderer: "svg",
  });
  chart.setOption({
    animation: false, // 强制：禁用动画，确保截图/转换时图表已完整渲染
    textStyle: { fontFamily: CHART_FONT_FAMILY },
    // 网格配置：预留标签空间
    grid: {
      left: "10%",
      right: "5%",
      top: "15%",
      bottom: "20%",
      containLabel: true, // 关键：确保标签在容器内
    },
    xAxis: {
      axisLabel: { fontFamily: CHART_FONT_FAMILY, fontSize: 12 },
      nameTextStyle: { fontFamily: CHART_FONT_FAMILY, fontSize: 12 },
    },
    yAxis: {
      axisLabel: { fontFamily: CHART_FONT_FAMILY, fontSize: 12 },
      nameTextStyle: { fontFamily: CHART_FONT_FAMILY, fontSize: 12 },
    },
    // ... 其他配置
  });
</script>
```

#### 6. 图片约束

```html
<!-- ✅ 正确：图片自适应容器 -->
<div class="w-full h-[300px]">
  <!-- ⚠️ 注意：h-full 要求父元素有显式高度 -->
  <img src="image.jpg" alt="说明" class="w-full h-full object-contain" />
</div>

<!-- ✅ 正确：背景图模式（使用 style 标签定义背景图） -->
<!-- ⚠️ 注意：h-full 要求父元素有 flex flex-col 或显式高度 -->
<style type="text/tailwindcss">
  .bg-image {
    background-image: url("image.jpg");
  }
</style>
<div class="w-full h-full bg-cover bg-center bg-image">
  <div class="w-full h-full bg-black/50"></div>
  <!-- 遮罩层 -->
</div>

<!-- ❌ 错误：图片可能溢出 -->
<img src="image.jpg" class="w-[800px]" />
```

#### 7. 完整示例：防溢出内容页

```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>2025 AI 产业发展报告</title>

    <script src="https://cdn.digitalhumanai.top/slidagent/pptx-craft/assets/vendors/tailwind.js"></script>

    <script src="https://cdn.digitalhumanai.top/slidagent/pptx-craft/assets/vendors/echarts.min.js"></script>

    <style type="text/tailwindcss">
      @layer utilities {
        .ppt-slide {
          @apply relative w-[1280px] h-[720px] mx-auto box-border overflow-hidden flex flex-col;
        }
        .ppt-slide *,
        .ppt-slide *::before,
        .ppt-slide *::after {
          @apply box-border;
          max-width: 100%;
        }
        .content-safe {
          @apply w-[1220px] h-[660px] my-[30px] mx-auto flex flex-col overflow-hidden;
        }
      }
    </style>
  </head>

  <body class="bg-gray-50">
    <!-- 内容页示例 -->
    <div class="ppt-slide flex flex-col" type="content">
      <div class="content-safe">
        <!-- 页头 -->
        <header class="h-[60px] flex-shrink-0 border-b border-gray-200">
          <h1 class="text-[32px] font-bold text-gray-800 text-balance">
            人工智能市场规模与增长趋势
          </h1>
        </header>

        <!-- 内容区 -->
        <main class="flex-1 min-h-0 grid grid-cols-2 gap-6">
          <!-- 左列：文字说明 -->
          <div class="min-w-0 min-h-0 flex flex-col gap-4">
            <div class="bg-white p-6 rounded-lg shadow-sm flex-1">
              <h2 class="text-[20px] font-semibold mb-4">核心发现</h2>
              <ul class="space-y-3">
                <li class="flex items-start gap-3">
                  <span class="text-[20px] font-bold">•</span>
                  <p class="text-[16px] text-gray-700">
                    2025 年全球 AI 市场规模预计达到 1.8 万亿美元，年复合增长率
                    37.3%
                  </p>
                </li>
                <li class="flex items-start gap-3">
                  <span class="text-[20px] font-bold">•</span>
                  <p class="text-[16px] text-gray-700">
                    中国市场占比将从 2023 的 14% 提升至 2025 年的 18%
                  </p>
                </li>
                <li class="flex items-start gap-3">
                  <span class="text-[20px] font-bold">•</span>
                  <p class="text-[16px] text-gray-700">
                    企业级应用成为主要增长驱动力，渗透率突破 50%
                  </p>
                </li>
              </ul>
            </div>

            <!-- 数据卡片 -->
            <div class="grid grid-cols-2 gap-4">
              <div class="bg-primary/10 p-4 rounded-lg text-center">
                <p class="text-[32px] font-bold text-primary">1.8T</p>
                <p class="text-[14px] text-gray-500 mt-1">全球市场规模</p>
              </div>
              <div class="bg-accent/10 p-4 rounded-lg text-center">
                <p class="text-[32px] font-bold text-accent">37.3%</p>
                <p class="text-[14px] text-gray-500 mt-1">年复合增长率</p>
              </div>
            </div>
          </div>

          <!-- 右列：图表 -->
          <div
            class="min-w-0 min-h-0 bg-white p-6 rounded-lg shadow-sm flex flex-col"
          >
            <h2 class="text-[18px] font-semibold mb-4 text-balance">
              市场规模增长趋势（2020-2025）
            </h2>
            <div class="flex-1 min-h-0">
              <div id="market-chart" class="w-full h-full"></div>
            </div>
          </div>
        </main>

        <!-- 页脚 -->
        <footer
          class="h-[30px] flex-shrink-0 flex justify-between items-center text-[14px] text-gray-500 border-t border-gray-200"
        >
          <span>第 3 页</span>
          <span>数据来源：IDC 2025 Q1</span>
          <span>2025.03.30</span>
        </footer>
      </div>
    </div>

    <script>
      // ECharts 图表
      (function () {
        const CHART_FONT_FAMILY = "WenYuan Sans SC, Noto Sans SC, sans-serif";
        const chart = echarts.init(
          document.getElementById("market-chart"),
          null,
          { renderer: "svg" },
        );
        chart.setOption({
          animation: false,
          textStyle: { fontFamily: CHART_FONT_FAMILY },
          grid: {
            left: "12%",
            right: "5%",
            top: "10%",
            bottom: "18%",
            containLabel: true,
          },
          xAxis: {
            type: "category",
            data: ["2020", "2021", "2022", "2023", "2024", "2025"],
            axisLabel: { fontFamily: CHART_FONT_FAMILY, fontSize: 14 },
          },
          yAxis: {
            type: "value",
            axisLabel: { fontFamily: CHART_FONT_FAMILY, fontSize: 14 },
            name: "十亿美元",
            nameTextStyle: { fontFamily: CHART_FONT_FAMILY, fontSize: 14 },
          },
          series: [
            {
              data: [500, 720, 980, 1350, 1800, 2400],
              type: "bar",
              itemStyle: { color: "#4A6C8C", borderRadius: [4, 4, 0, 0] },
            },
          ],
        });
      })();
    </script>
  </body>
</html>
```

#### 8. 溢出检查清单

生成 HTML 后，必须检查以下项目：

- [ ] 所有元素是否都在 `.ppt-slide` 容器内
- [ ] 是否使用了 `.content-safe` 容器约束内容区
- [ ] 图片/图表是否有 `max-w-full` 和 `object-contain`
- [ ] 标题、正文和标签是否完整可见，没有使用截断、滚动或折叠
- [ ] 图表容器的直接父元素是否有 `flex flex-col`（若使用 `flex-1 min-h-0` 弹性填充）
- [ ] 图表容器是否设置了明确高度（若使用固定高度方案）
- [ ] ECharts 是否设置 `containLabel: true`
- [ ] 字体大小是否符合梯度规范
- [ ] 是否避免使用绝对定位

#### 9. 多栏/对比卡片内容预算（防止等高栏超框）

并排的等高卡片（如"认知 vs 现实""左右对比"两栏、三栏要点）最易超框：每栏高度被 `flex-1 min-h-0` 平分后固定，文字一多就 13px、20px 地溢出（典型表现：底部文字被裁切或与下方元素重叠）。强制预算：

- **两栏对比**：每栏正文 ≤ 4 个要点，每点 ≤ 2 行（约 ≤ 40 字/点）；标题 + 要点合计行数按栏高反推，**宁可精简，不可溢出**。
- **三栏及以上**：每栏 ≤ 3 个要点，每点 ≤ 1-2 行。
- 卡片内统一用 `.text-truncate` / `.line-clamp-2`（见文本防溢出类）兜底，确保超量文本被截断而非溢出。
- 数字/结论优先，解释性长句移到注释或删除；与其塞满一栏导致溢出，不如减少要点数。
- 生成后自查：[ ] 每个等高栏/卡片的实际内容是否在其分得的高度内（按 660px 内容区 ÷ 行数估算）；[ ] 对比栏左右内容量是否大致均衡（避免一栏溢出、一栏空白）。

### 页面类型标记示例

```html
<!-- 封面页 -->
<div class="ppt-slide flex flex-col" type="cover">
  <div data-field="title">演示文稿标题</div>
  <div data-field="presenter">演讲者姓名</div>
  <div data-field="date">日期</div>
</div>

<!-- 目录页 -->
<div class="ppt-slide flex flex-col" type="table_of_contents">
  <!-- 目录内容 -->
</div>

<!-- 章节过渡页 -->
<div class="ppt-slide flex flex-col" type="chapter">
  <div data-field="chapter-number">1</div>
  <div data-field="chapter-title">章节标题</div>
</div>

<!-- 内容页 -->
<div class="ppt-slide flex flex-col" type="content">
  <!-- 正文内容 -->
</div>

<!-- 结束页 -->
<div class="ppt-slide flex flex-col" type="final">
  <div data-field="presenter">演讲者姓名</div>
  <div data-field="date">日期</div>
</div>
```

### 模板占位符（使用模板时）

如用户选择了模板，封面、章节、结束页只需输出占位符：

```html
<!-- 封面页占位符 -->
<div class="ppt-slide flex flex-col" type="cover">
  <div data-field="title">2025 人工智能产业发展趋势分析报告</div>
  <div data-field="presenter">Kimi</div>
  <div data-field="date">2025.11.18</div>
</div>

<!-- 章节页占位符 -->
<div class="ppt-slide flex flex-col" type="chapter">
  <div data-field="chapter-number">1</div>
  <div data-field="chapter-title">人工智能技术演进路径</div>
</div>

<!-- 结束页占位符 -->
<div class="ppt-slide flex flex-col" type="final">
  <div data-field="presenter">Kimi</div>
  <div data-field="date">2025.11.18</div>
</div>
```

---

## 页面布局规范

### 页面规格

- **尺寸**：1280px × 720px (16:9)
- **边距**：30px
- **内容区域**：1220px × 660px

### 各页面类型规范

**封面页**：

- 标题字号、字体、颜色：**严格遵循当前风格文件中的定义**（见 `styles/{style_id}.md` 中的「封面页规范」章节）
- 副标题/日期：严格遵循当前风格文件中的副标题规范
- 背景：遵循当前风格文件中的背景规范（**禁止使用风格文件中未定义的渐变或遮罩**）
- 布局：遵循当前风格文件中的布局原则
- 装饰元素：仅使用风格文件中定义的装饰样式
- 居中或左对齐（由风格文件决定）

**目录页**：

- 章节列表（4-6 个）
- 序号 + 标题 + 简介
- 网格或列表布局
- 配色、字号、背景：严格遵循当前风格文件定义

**章节过渡页**：

- 章节编号、标题：**严格遵循当前风格文件中的定义**（见 `styles/{style_id}.md` 中的「章节过渡页规范」章节）
- 背景：遵循当前风格文件中的背景规范（**禁止使用风格文件中未定义的渐变或遮罩**）
- 装饰元素：仅使用风格文件中定义的装饰样式

**内容页**：

- 页面标题（32-36px）
- 核心内容区域
- 支持多栏布局（1-3 列）
- 图表/数据可视化区域

**结束页**：

- 感谢语/总结语
- 联系方式（可选）
- 背景图 + 遮罩

---

## 内容密度与留白保障体系

**目标**：让信息密度与页面叙事匹配，避免内容过载，也避免无意义的空洞。

### 核心原则

> 每页必须遵循生成前制定的页面内容预算。
>
> 留白是层级工具，不是必须消灭的问题；只有破坏视觉重心、阅读路径或信息表达的空白才需要修复。

---

### 一、按页面类型选择元素

页面不使用统一元素配额。先确定页面意图，再选择最少且足够的视觉元素：

| 页面类型 | 推荐主元素 | 常见信息量 |
| -------- | ---------- | ---------- |
| 封面/章节 | 主标题、短副标题、单一主视觉 | 1 个核心信息 |
| 概念解释 | 结构图、流程、2-4 个要点 | 中密度 |
| 数据分析 | 1 个主图表 + 必要注释，或 3-5 个数据卡片 | 中高密度 |
| 对比/矩阵 | 2-4 个对比对象或矩阵单元 | 高密度 |
| 结论/建议 | 1 个结论 + 3-5 个行动项 | 中密度 |

图标、卡片、图表均不是配额。缺少语义价值时宁可不用，也不要为了填满页面增加重复内容。

---

### 二、自动扩展规则

生成内容时，必须根据以下规则自动判断并补充内容元素：

| 触发条件              | 扩展动作                                       | 搜索补充策略                                                        | 示例                                                                                      |
| --------------------- | ---------------------------------------------- | ------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| **文字描述 > 100 字** | 将至少 50% 文字转换为图表/卡片/列表            | 搜索 `"{主题关键词} 数据 统计"` 获取可图表化的数据                  | 将"市场规模从 2020 年的 500 亿增长到 2025 年的 1.8 万亿"转为柱状图                        |
| **包含抽象概念**      | 添加至少 1 个真实案例或引用                    | 搜索 `"{概念名} 应用案例 实践"` 或 `"{概念名} 企业案例"`            | 解释"AI 渗透率"时，搜索"AI 客服 渗透率 案例"，添加"某企业 AI 客服渗透率从 10% 提升至 60%" |
| **包含比较关系**      | 添加对比图表或对比卡片                         | 搜索 `"{A} {B} 对比 市场份额"` 或 `"{主题} 竞品对比 2024"`          | A/B 对比、今昔对比、竞品对比                                                              |
| **包含流程/步骤**     | 绘制流程图或步骤图                             | 搜索 `"{主题} 流程图 步骤"` 获取流程节点和关系                      | 使用 HTML/CSS 绘制节点 + 连线 + 标注                                                      |
| **空白破坏视觉平衡**  | 优先放大主视觉、调整区域比例或收紧布局 | 通常无需搜索 | 放大图表、调整栏宽、移动说明区；不重复已有结论 |
| **缺少数据支撑**      | 添加数据卡片或图表                             | 搜索 `"{主题} 市场规模 2024 2025"`、`"{主题} 增长率 百分比"`        | 提取 3+ 个数据点生成柱状图，或制作 3 个大数字卡片                                         |
| **缺少案例填充**      | 添加真实案例卡片                               | 搜索 `"{主题} 成功案例 最佳实践" site:cnblogs.com OR site:csdn.net` | 公司名 + 实施内容 + 量化效果                                                              |

**扩展优先级**：

```
1. 数据图表 > 2. 数据卡片 > 3. 信息图 > 4. 纯文字
```

始终优先使用可视化程度更高的方式呈现信息。

**搜索关键词构建规则**：

- 必须包含主题关键词（从 outline.md + 本页 research-P{N}.md 中提取）
- 添加年份（优先最近 2 年）获取最新数据
- 添加数据类型词（"市场规模"、"增长率"、"渗透率"、"市场份额"）
- 需要案例时添加 "案例"、"实践"、"最佳实践"

---

### 三、内容密度检查清单（生成后验证）

生成每一页后，必须执行以下检查。**核心信息不完整、预算超限或存在真实溢出时触发重试**。

#### 检查清单

- [ ] **预算符合度**：标题行数、区域比例、卡片数量、正文行数和字号是否符合页面预算？
- [ ] **核心信息**：核心结论、关键数据和必要论据是否完整？
- [ ] **可视化适配**：图表、卡片或流程是否确实提升理解，而非满足数量要求？
- [ ] **留白质量**：留白是否服务于层级、聚焦或阅读节奏？
- [ ] **数据来源**：页脚或页面末尾是否注明数据来源？
- [ ] **无大段文字**：是否没有连续超过 100 字的段落？（如有，是否已拆分为列表或小节）
- [ ] **视觉层级**：是否有清晰的 标题 → 副标题 → 正文 → 注释 层级？
- [ ] **完整显示**：核心内容是否未被裁切、滚动、折叠或省略？

#### 自动重试机制

```
IF 检查清单有 ≥ 1 项不满足 THEN
  → 分析具体缺失项
  → 执行针对性补充：

    缺失项              补充动作
    ─────────────────────────────────────────────
    预算超限        →  提炼文案、合并重复观点、调整区域比例，必要时拆页
    缺核心信息      →  恢复关键结论、关键数据或必要因果关系
    可视化不匹配    →  更换图表/流程/卡片形式，或退回简洁文字结构
    留白失衡        →  放大主视觉、调整布局比例或收紧无意义间距
    缺数据来源      →  在页脚添加"数据来源：XXX"或"参考资料：XXX"
    大段文字        →  提炼为短句、标签或图表注释
    缺视觉层级      →  添加明确的标题区、内容区、页脚区
    出现裁切        →  回到预算阶段重新分配内容，禁止添加 overflow-hidden

  → 重新生成该页 HTML
  → 再次执行检查清单
  → 最多重试 3 次

IF 3 次重试后仍不满足 THEN
  → 报错并提示用户，保留当前 HTML 供人工排查
  → 错误信息示例：
    "页面预算检查未通过（重试 3 次后）：
     - 核心内容仍超过可用高度
     - 正文字号已达到允许下限
     请拆分页面或调整大纲。"
```

---

### 四、内容创作建议

**高密度内容页的典型结构**：

```html
<div class="ppt-slide flex flex-col" type="content">
  <div class="content-safe">
    <!-- 页头：标题 + 副标题（~60px） -->
    <header>
      <h1>页面标题</h1>
      <p class="text-[16px] text-gray-600">可选副标题或核心结论</p>
    </header>

    <!-- 内容区：主体内容（~500px） -->
    <main class="flex-1 min-h-0 grid grid-cols-2 gap-6">
      <!-- 左列：文字要点 -->
      <div class="min-w-0 min-h-0 flex flex-col gap-4">
        <div class="flex items-start gap-3">
          <i class="fa-solid fa-check-circle text-primary"></i>
          <p>要点 1 说明...</p>
        </div>
        <div class="flex items-start gap-3">
          <i class="fa-solid fa-arrow-right text-primary"></i>
          <p>要点 2 说明...</p>
        </div>
        <div class="flex items-start gap-3">
          <i class="fa-solid fa-star text-accent"></i>
          <p>要点 3 说明...</p>
        </div>
      </div>

      <!-- 右列：图表或数据卡片 -->
      <div class="min-w-0 min-h-0 flex flex-col">
        <!-- 方案 A：ECharts 图表 -->
        <h3 class="text-[18px] font-semibold mb-3">图表标题</h3>
        <div class="flex-1 min-h-0">
          <div id="chart-1" class="w-full h-full"></div>
        </div>

        <!-- 方案 B：数据卡片组合 -->
        <div class="grid grid-cols-2 gap-4">
          <div class="bg-primary/10 p-4 text-center rounded">
            <p class="text-[32px] font-bold text-primary">1.8T</p>
            <p class="text-[14px] text-gray-500">市场规模</p>
          </div>
          <div class="bg-accent/10 p-4 text-center rounded">
            <p class="text-[32px] font-bold text-accent">37%</p>
            <p class="text-[14px] text-gray-500">增长率</p>
          </div>
        </div>
      </div>
    </main>

    <!-- 页脚：数据来源 + 页码（~30px） -->
    <footer class="flex justify-between text-[14px] text-gray-500">
      <span>数据来源：IDC 2025 Q1</span>
      <span>第 3 页</span>
    </footer>
  </div>
</div>
```

**内容填充技巧**：

| 技巧            | 操作                                   | 效果                       |
| --------------- | -------------------------------------- | -------------------------- |
| **大数字突出**  | 将关键数据放大到 32-48px，配以说明文字 | 视觉冲击力强，填充效果好   |
| **图标 + 文字** | 每个要点前加图标，形成视觉节奏         | 增加装饰性，提升可读性     |
| **卡片式布局**  | 将信息分组到带背景的卡片中             | 增加视觉元素，自然填充空间 |
| **分隔线/边框** | 使用 `border` 或 `hr` 分隔区域         | 增加结构感，减少空白       |
| **引用块**      | 使用 `blockquote` 展示名言/结论        | 增加变化，填充中等空间     |

---

## 内容创作规范

### 大纲结构

| 页面类型   | 必需元素                      | 说明               |
| ---------- | ----------------------------- | ------------------ |
| 封面页     | title, presenter, date        | 突出主题           |
| 目录页     | 4-6 个章节                    | 序号 + 标题 + 简介 |
| 章节过渡页 | chapter-number, chapter-title | 醒目显示           |
| 内容页     | 标题 + 核心内容               | 图表/案例支撑      |
| 结束页     | 总结语                        | 联系方式可选       |

### 页面数量控制

- **默认**：12 页以内
- **用户指定**：最多 30 页
- 封面：1 页
- 目录：1 页
- 章节过渡：仅按 `outline.md` 中已有的章节过渡页生成；内容页数 5 页及以下不得自行新增章节过渡页
- 内容页：根据信息量调整

### 内容密度分级系统

**三级密度策略**：

| 密度等级 | 关键信息点数量 | 适用场景                                  | 核心要求                           |
| -------- | -------------- | ----------------------------------------- | ---------------------------------- |
| 高密度   | 每页 4-7 个点  | 数据报告、分析总结、竞品对比              | 图文结合，数据可视化，压缩冗余描述 |
| 中密度   | 每页 2-4 个点  | 概念阐述、流程说明、方案展示              | 清晰层次，适度留白，图文平衡       |
| 低密度   | 每页 1 个核心  | 封面、章节过渡、content（强调类）、结尾页 | 视觉冲击，简洁有力，留白艺术       |

**密度选择原则**：

- **封面/结尾**：低密度，强调品牌/总结
- **章节过渡**：低密度，过渡清晰，情绪铺垫
- **核心内容页**：中高密度，信息传递为主
- **数据/分析页**：高密度，充分利用空间展示关键数据
- **概念解释页**：中密度，避免信息过载

---

### 防溢出核心策略

#### 空间预算分配（1280×720px 标准画布）

| 区域       | 尺寸限制                       | 说明                   |
| ---------- | ------------------------------ | ---------------------- |
| 内容安全区 | 左右 30px 边距，上下 30px 边距 | 即 1220×660px 可用区域 |
| 页眉区     | 高度 40-60px                   | 标题放置区             |
| 页脚区     | 高度 30-40px                   | 页码/日期/来源         |
| 核心内容区 | 剩余高度                       | 主要信息展示           |

#### 超预算内容处理

| 内容类型 | 处理策略 |
| -------- | -------- |
| 文字 | 提炼措辞、拆分句子、调整区域比例；仍超预算则拆页 |
| 列表 | 合并重复项、按优先级保留核心项；其余移至相邻页 |
| 图表 | 简化非关键标签、增加图表区域或拆成两张图 |
| 图片 | 等比缩放至安全区域；仅纯装饰图片允许裁剪边缘 |

#### 溢出预警检查点

- [ ] **文字**：标题/正文是否完整显示
- [ ] **图表**：X 轴标签是否重叠、Y 轴是否被截断
- [ ] **图片**：是否超出容器边界
- [ ] **页边距**：内容是否紧贴边缘（应保持 ≥ 20px）

---

### 防空白核心策略

#### 内容扩展技术

当内容不足以填满可用空间时，采用以下扩展策略：

| 扩展技术   | 适用场景     | 操作方法                         |
| ---------- | ------------ | -------------------------------- |
| 视觉化转换 | 文字描述过多 | 将关键数据转为图表、图标、示意图 |
| 数据补充   | 数据支撑不足 | 添加趋势线、对比柱状、占比图示   |
| 案例填充   | 概念空洞     | 添加真实案例/引用/行业示例       |
| 图标装饰   | 内容稀疏     | 添加相关图标、装饰线条、背景形状 |
| 引用增强   | 观点单薄     | 添加名人名言、数据来源、权威背书 |

#### 布局补偿技术

- **元素放大**：将核心元素（图标、数字、标题）放大至视觉重心平衡
- **留白利用**：用渐变背景、装饰线条、logo 填补空白区域
- **对称平衡**：左右分布不均时添加呼应元素（如装饰色块）
- **视觉引导**：添加箭头、引导线连接分散的元素

#### 总结框使用边界

**核心策略**：总结框只用于新增决策价值，不作为填补空白的默认手段。

**触发条件**：页面确实需要一句跨区域结论，且该结论不是正文的简单重复。

**执行流程**：

```
检测到视觉重心失衡
         ↓
    ┌────────────────┐
    │ 分析空白区域位置  │
    │ (左侧/右侧/底部)  │
         ↓
    ┌────────────────┐
    │ 先调整主视觉与比例 │
    │ - 放大核心图表     │
    │ - 调整栏宽/行高    │
    │ - 收紧无意义间距   │
         ↓
    ┌────────────────┐
    │ 仍缺少决策结论时  │
    │ → 添加总结框     │
         ↓
    └────────────────┘
```

**1. 位置策略**

| 原始布局   | 空白位置 | 总结框位置 |
| ---------- | -------- | ---------- |
| 左对齐列表 | 右侧     | 右侧边栏框 |
| 右对齐列表 | 左侧     | 左侧边栏框 |
| 居中标题式 | 底部     | 底部通栏框 |
| 分散内容   | 四周     | 底部或侧边 |

**2. 尺寸规则**

```
- 宽度：空白区域宽度的 80-90%（留 10-20% 呼吸空间）
- 高度：根据内容自适应，但最大不超过 250px
- 内边距：16px
- 与主内容间距：≥ 40px
```

**3. 内容规则（防溢出关键）**

```
- 标题："关键洞察" 或 "核心总结"（固定）
- 正文：1-2 段，每段不超过 2 行
- 字体：正文 14px（比主内容小 2px）
- 行高：1.4
- 内容性质：提炼跨区域结论或决策含义，禁止简单重复正文
```

**4. 视觉样式**

```html
<!-- ✅ 正确：使用 flex 布局的侧边总结框 -->
<div class="flex gap-6">
  <div class="flex-1 min-h-0">
    <!-- 主内容区 -->
  </div>
  <div class="w-[350px] flex-shrink-0">
    <div
      class="summary-box bg-opacity-10 border-l-4 border-primary rounded-lg p-4 shadow-md"
    >
      <div class="summary-title text-sm font-bold text-primary mb-2">
        关键洞察
      </div>
      <div class="summary-content text-sm leading-relaxed text-gray-600">
        用 1-2 句话概括现有要点的核心含义...
      </div>
    </div>
  </div>
</div>
```

**5. 防溢出保障**

| 保障项   | 规则                        |
| -------- | --------------------------- |
| 内容量   | 最多 1-2 段，每段≤2 行      |
| 字体大小 | 正文 14px（比主内容小 2px） |
| 行数限制 | 超过预算时提炼或拆页，不截断 |
| 内容性质 | 概括重述，非补充新增        |

---

### 固定画布适配原则

#### 弹性容器设计

- 使用 flex 比例或明确像素预算定义容器尺寸
- 图片和图表设置 `max-width: 100%` 防止溢出
- 表格优先精简列、缩短标签或拆页，禁止横向滚动

#### 动态字号系统

| 元素类型       | 字号策略                             |
| -------------- | ------------------------------------ |
| 主标题         | 固定 36-48px，确保层次感             |
| 副标题         | 主标题的 60-80%，形成梯度            |
| 正文           | 16-20px，保证可读性                  |
| 辅助文字       | 14px，颜色淡化处理                |
| **响应式规则** | 容器宽度 < 400px 时，字号缩小 10-15% |

### 叙事逻辑结构

**问题驱动型**：背景 → 问题 → 分析 → 方案 → 效果（适用于商业提案）
**时间线型**：过去 → 现在 → 未来（适用于发展历程）
**金字塔型**：结论 → 论据 → 细节（适用于汇报总结）
**对比型**：现状 A→ 现状 B→ 对比分析 → 结论（适用于竞品分析）

---

## 图表与数据可视化（详见图表附录）

> 图表候选页生成前**必须**额外读取 `{skill_root}/pptx-craft/designer/charts.md`。页面类型为 `data` / `comparison` / `technology` / `trend` 的内容页默认都是图表候选页；其他内容页只要 outline 或 research 出现数据需求、图表、趋势、对比、指标、基准测试等信息，也视为图表候选页。该文件包含：图表类型选择、图表规范、ECharts SVG 初始化示例，以及 ECharts JavaScript 安全编码规范（formatter 书写规则、格式化函数模板、代码检查清单）。
> 结构性页面（cover/section/chapter/ending/agenda 等无图表页面）无需读取本附录。

## 图片使用规范

### 图片来源

- 使用图片搜索工具获取高质量图片
- 优先选择高分辨率、无版权问题的图片

### 图片处理

- 使用渐变蒙版增强文字可读性
- 可添加圆角或边框效果
- 调整透明度以达到最佳视觉效果

### 图片布局

- **全屏背景**：用于封面、章节页
- **局部配图**：用于内容页，与文字配合
- **图片网格**：多张图片可采用网格布局

---

## 关键原则

### 内容质量原则

- **信息密度**：每页必须包含高信息密度，避免空洞装饰
- **叙事逻辑**：遵循清晰的叙事结构
- **数据支撑**：所有关键论点必须有数据或案例支撑
- **受众适配**：内容深度和表达方式匹配目标受众

### 视觉设计原则

- **专业美感**：商务级专业设计，避免花哨效果
- **层次分明**：通过字体大小、颜色、间距建立清晰视觉层级
- **留白艺术**：合理使用留白，避免页面拥挤
- **一致性**：全篇保持色彩、字体、风格一致

### 技术规范原则

- **响应式设计**：使用 Tailwind CSS 确保布局稳定
- **字体规范**：严格使用指定字体库
- **图表生成**：数据图表必须用代码生成，禁止截图
- **性能优化**：控制单文件大小，确保加载流畅

---

## 禁止事项

### CSS 样式约束

> 完整支持/禁止样式白名单参见：`html-to-pptx/css-whitelist.md`

以下样式在 PPTX 转换中不可用，必须避免：

| 禁止样式                                      | 替代方案                              |
| --------------------------------------------- | ------------------------------------- |
| `blur-*`、`backdrop-blur-*`、`filter: blur()` | 纯色色块或半透明色块装饰              |
| 半透明渐变（`from-{color}/30`）               | 纯色背景 `bg-{color}`                 |
| `bg-[url(...)]` 背景图片                      | `<img>` 标签                          |
| `animate-*`、`transition` 动画                | 静态样式                              |
| `text-shadow`、`drop-shadow-*`                | `shadow`（box-shadow）                |
| `clip-path`                                   | `border-radius` 或 `overflow: hidden` |
| `ring-*`（outline）                           | `border` 或 `shadow`                  |
| `skew-*`、`scale-*`、`translate-*`            | 仅 `rotate-*` 有效                    |
| `columns-*` 多列布局                          | Flexbox                               |
| `line-through`                                | 不支持                                |
| `capitalize`                                  | 手动大写                              |
| `radial-gradient`、`conic-gradient`           | `linear-gradient` 或纯色              |

### 内容禁止

- 大段文字堆砌
- 单页超过 200 字无分段
- 图表无标题和说明
- 数据无来源标注
- 配色超过 4 种主色

---

## 质量控制清单

### 生成中检查

- [ ] 每页内容是否完整
- [ ] 图表是否正确生成
- [ ] 样式是否一致
- [ ] 字体是否正确加载
- [ ] 所有页面都在 `ppt-slide` 容器中

### 生成后检查

- [ ] 页面数量是否符合要求
- [ ] 内容密度是否合适
- [ ] 逻辑是否通顺
- [ ] 视觉是否专业
- [ ] 是否有错别字或语法错误

### 排版检查清单

#### 溢出检查

| 检查项       | 验收标准                              | 处理建议                              |
| ------------ | ------------------------------------- | ------------------------------------- |
| 文字溢出     | 标题、正文和标签完整显示              | 精简文字、重排布局或拆页              |
| 图表标签溢出 | 坐标轴标签、图例完整显示无遮挡        | 旋转标签、缩小字号或改用简短标签      |
| 图片溢出     | 图片完整显示在容器内，无截断          | 使用 `object-fit: contain` 或调整尺寸 |
| 页边距溢出   | 内容不紧贴画布边缘（≥ 20px）          | 调整内边距或容器尺寸                  |

#### 空白检查

| 检查项       | 验收标准                                   | 处理建议                         |
| ------------ | ------------------------------------------ | -------------------------------- |
| 内容区利用率 | 符合页面预算目标，且无大块无意义空白       | 放大核心元素、调整比例或收紧布局 |
| 视觉重心     | 画面重心在画布中心偏上 1/3 处              | 调整元素位置或尺寸以平衡重心     |
| 元素间距     | 相关元素间距 ≤ 50px，不相关元素间距 ≥ 50px | 重排布局或调整间距               |
| 留白质量     | 留白区域有目的（如引导视线、突出重点）     | 添加装饰元素或渐变背景           |

#### 美观检查

| 检查项   | 验收标准                             | 处理建议                   |
| -------- | ------------------------------------ | -------------------------- |
| 对齐检查 | 同级元素左对齐或居中对齐，无参差     | 使用网格系统或 flex 布局   |
| 色彩检查 | 配色协调，主色不超过 3 种            | 引用配色方案的色板         |
| 层级检查 | 标题 > 副标题 > 正文 > 辅助文字      | 检查字号梯度是否清晰       |
| 阅读顺序 | 符合从左到右、从上到下的自然阅读习惯 | 调整元素顺序或添加视觉引导 |

### 交付检查

- [ ] 文件是否保存到 `output/pages/` 目录（或 prompt 上下文指定的输出目录）
- [ ] 文件是否成功生成
- [ ] 总结是否准确
- [ ] 使用说明是否清晰
- [ ] 最终回复是否包含：完成状态、页面结构摘要、可继续优化方向

---

## 常见错误与解决方案

### 布局相关问题

| 问题         | 原因                           | 解决方案                             |
| ------------ | ------------------------------ | ------------------------------------ |
| 字体加载失败 | 字体名称拼写错误               | 使用字体库中列出的确切名称           |
| 图表不显示   | 容器 ID 错误或脚本执行时机问题 | 使用立即执行函数 (IIFE) 包裹图表代码 |
| 样式不一致   | Tailwind 类名冲突              | 使用!important 或更具体的选择器      |
| 内容溢出     | 内容过多超出 600px 高度        | 精简内容或调整布局                   |
| 图片加载失败 | 图片 URL 无效                  | 使用可靠的图片源或 base64 编码       |
| 空白失衡     | 主视觉过小或布局比例不合理       | 放大主视觉、调整区域比例或紧凑布局   |
| 元素溢出边界 | 位置/尺寸计算错误              | 检查 Tailwind 类名和内联样式         |
| **范围柱状图数据为空** | 使用 `value: [min, max]` 双值数组但未设置 `stack` | 必须给 series 添加 `stack: "xxx"`，否则 ECharts 只取第一个值渲染，区间柱不显示 |

### 布局错误避免清单

**绝对禁止**：

- ❌ 不要使用绝对定位放置大量内容
- ❌ 不要依赖浏览器默认样式
- ❌ 不要假设内容长度（预留扩展空间）
- ❌ 不要忽视 HTML 与 PPTX 字体度量差异
- ❌ 不要对内容区使用 `overflow: hidden`
- ❌ 不要使用 `fixed height + overflow` 组合
- ❌ 不要使用省略号、line-clamp、滚动或折叠隐藏核心信息

**强烈建议**：

- ✅ 所有元素距离边缘 ≥ 20px
- ✅ 元素间距 ≥ 16px
- ✅ 最小字号 ≥ 14px
- ✅ 文字与背景对比度 ≥ 4.5:1
- ✅ 优先使用 flex/grid 布局
- ✅ 预留 10% 缓冲空间应对内容扩展

### 典型问题解决方案

| 问题类型         | 具体表现                        | 解决方案                                                                     |
| ---------------- | ------------------------------- | ---------------------------------------------------------------------------- |
| **文字太多溢出** | 标题/正文超出容器边界           | ① 提炼核心文字，删除修饰词 ② 重排区域比例 ③ 拆分为多页 ④ 在字号下限内微调 |
| **内容太少空白** | 画面空洞、留白过多              | ① 添加辅助图表或数据 ② 放大核心元素 ③ 添加图标装饰 ④ 补充案例/引用           |
| **图文比例失衡** | 图太大压文字 / 图太小看不清     | ① 文字多则图缩小做配图 ② 图为主则文字做说明标签 ③ 保持 6:4 或 7:3 的图文占比 |
| **元素相互遮挡** | 背景遮住文字 / 弹窗遮住关键信息 | ① 提高文字层 z-index ② 添加半透明背景 ③ 调整元素堆叠顺序                     |
| **间距不协调**   | 元素挤成一团 / 分散零乱         | ① 相关元素收紧（≤ 50px）② 不相关元素拉开（≥ 50px）③ 使用网格对齐             |

---

## 输出要求

### 文件命名规范

| 阶段 | 文件命名                        | 说明                   |
| ---- | ------------------------------- | ---------------------- |
| HTML | `{output_dir}/page-N.pptx.html` | 高分辨率成品，1280×720 |

### 通用要求

1. **文件路径**：
   - **路径由调用方通过 prompt 指定**，本技能不得自行决定输出位置
   - **注意**：`output_dir` 参数指向 `{pages_dir}`（即 `{session_dir}/pages`），而非 `{session_dir}` 本身
   - 如调用方未提供 `output_dir` 参数，**必须报错终止**
   - 禁止使用 `output/pages/` 或任何其他硬编码路径

2. **文件格式**：HTML 文件，扩展名为 `.pptx.html`
3. **成品页面尺寸**：1280px × 720px
4. **页面类型**：使用正确的 `type` 属性标记
5. **内容密度**：确保每页有足够的信息量，避免大面积留白
6. **视觉一致性**：全篇保持统一的色彩、字体和风格
7. **最终回复格式**：需包含以下两部分
   - 完成状态，是否有待确认项
   - 页面结构摘要（按页或按章节概述）

### 阶段产出要求

**HTML 产出**：

- 所有页面的 HTML 文件（`page-N.pptx.html`）
- HTML 需内容完整，视觉精致，达到"可直接用于正式展示"的完成度

---

## 设计哲学

### 核心理念

> **"每一像素都应有其存在的意义"**

每一像素都应服务于信息的传递与视觉的体验。没有无缘无故的留白，也没有毫无意义的装饰。

### 设计三原则

| 原则       | 含义                       | 实践                       |
| ---------- | -------------------------- | -------------------------- |
| **必要性** | 每个元素都必须有存在的理由 | 删除无法解释其用途的元素   |
| **目的性** | 每个元素都应有明确的功能   | 装饰元素必须辅助信息理解   |
| **经济性** | 用最少的元素达成最好的效果 | 避免过度设计，信息密度适当 |

### 留白的艺术

- 留白不是浪费，而是给内容"呼吸"的空间
- 核心内容周围的留白可以引导视线、突出重点
- 低密度页面（如封面）的留白是一种视觉语言
- 高密度页面（如数据页）的留白可以分隔信息层级

### 视觉层级法则

1. **第一眼**：应看到最核心的信息（标题/数据/关键词）
2. **第二眼**：应看到辅助说明（图表/图标/次要文字）
3. **第三眼**：应看到装饰元素（背景/线条/品牌元素）

每个页面都应该有清晰的视觉层级，让读者在 3 秒内抓住重点。

### 布局即叙事

- 布局不仅是摆放元素，更是组织信息、引导阅读
- 重要的内容放在视觉重心位置（画面中心偏上 1/3 处）
- 相关内容应靠近，不相关内容应有明确分隔
- 阅读顺序应符合自然习惯（左到右、上到下）
