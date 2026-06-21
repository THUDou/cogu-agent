# html-to-pptx CSS 样式白名单

本文档列出 html-to-pptx 转换器支持的 CSS 属性、有效值范围、PPTX 映射方式和已知限制。
**仅白名单内的样式可被正确转换**，不在列表中的样式将被忽略或降级处理。

> 维护者：更新转换器代码后，请同步更新对应条目。源码引用格式为 `file:line`。

---

## 1. 颜色

| CSS 属性 | 支持的值 | PPTX 映射 | 已知限制 | 源码 |
|---|---|---|---|---|
| `color` | `#hex`, `rgb()`, `rgba()`, 命名颜色, `transparent` | 文本 `color` | oklch/hsl/lab 降级到 Canvas API 转换，可能丢失 alpha | `utils.js:528` |
| `background-color` | `#hex`, `rgb()`, `rgba()`, 命名颜色, `transparent` | 形状 `fill: {color, transparency}` | alpha 映射为 PPTX transparency (0-100) | `slide.js:1084` |
| `background-image` | `linear-gradient(...)` 仅限 | `generateGradientSVG()` → SVG/PNG 图片 | 不支持 `radial-gradient`、`conic-gradient`、`url()` | `utils.js:807` |
| `background-clip: text` / `-webkit-background-clip: text` | `text` | 降级为渐变首个不透明色 | 不实现真正的文字渐变效果 | `utils.js:531` |
| `background-size` | 仅用于检测平铺模式 | 检测到非 auto + 多层渐变时跳过渲染 | 不支持真正的背景平铺 | `slide.js:1098` |

---

## 2. 文本样式

| CSS 属性 | 支持的值 | PPTX 映射 | 已知限制 | 源码 |
|---|---|---|---|---|
| `font-size` | px 值 | `px * 0.75 * scale` → pt (`fontSize`) | | `utils.js:537` |
| `font-weight` | 100-900 数值 | ≥600 → `bold: true` | 仅 bold/normal 二态 | `utils.js:549` |
| `font-family` | 任意字体栈 | 取第一个字体名 (`fontFace`) | 后备字体被忽略 | `utils.js:553` |
| `font-style` | `normal`, `italic` | `italic: true/false` | 不支持 `oblique` | `utils.js:555` |
| `text-decoration` | `none`, `underline` | `underline: true/false` | 不支持 `line-through`, `overline` | `utils.js:556` |
| `text-align` | `left`, `center`, `right`, `justify`, `start`, `end` | `align` | start→left, end→right | `slide.js:1298` |
| `text-transform` | `none`, `uppercase`, `lowercase` | 预处理文本内容 | 不支持 `capitalize` | `slide.js:1175` |
| `white-space` | `nowrap`, `pre`, `pre-wrap` | 影响换行检测逻辑 | 不直接映射 PPTX 属性 | `dom.js:isNoWrap` |
| `line-height` | 任意（通过 computed style） | 间接影响 `detectLineBreaks()` | 不直接映射 PPTX lineSpacing | `utils.js:detectLineBreaks` |
| `letter-spacing` | 任意（通过 computed style） | 间接影响宽度计算 | 不直接映射 PPTX | |

---

## 3. 盒模型

| CSS 属性 | 支持的值 | PPTX 映射 | 已知限制 | 源码 |
|---|---|---|---|---|
| `width` / `height` | 通过 `getBoundingClientRect()` 获取 | `x, y, w, h` (英寸) | 使用 DOM rect 而非 CSS 值 | `slide.js:595` |
| `padding-top/right/bottom/left` | px 值 | `margin: [l, r, b, t]` (pt) | 系数 0.85（减少 15%） | `utils.js:502` |
| `margin-left` / `margin-top` | px 值 | 位置偏移 | 仅用于 clipped div 偏移计算 | `slide.js:1062` |
| `border-*-width` | px 值 | `line.width` (pt) | 系数 0.65 | `utils.js:329` |
| `border-*-style` | `solid`, `dashed`, `dotted`, `none`, `hidden` | `dashType: solid/dash/dot` | 不支持 `double`, `groove`, `ridge`, `inset`, `outset` | `utils.js:262` |
| `border-*-color` | `#hex`, `rgb()`, `rgba()` | `line.color` | 支持 alpha via transparency | `utils.js:279` |
| `border-radius` / `border-*-radius` | px, % | `roundRect` / `ellipse` / SVG 回退 | 非均匀四角 → SVG 图片回退 | `slide.js:1013` |
| `border-collapse` | `collapse`, `separate` | 间接影响表格渲染 | | |

---

## 4. 布局

| CSS 属性 | 支持的值 | PPTX 映射 | 已知限制 | 源码 |
|---|---|---|---|---|
| `display` | `flex`, `inline-flex`, `none` | flex→对齐映射; none→跳过 | Grid 仅检测不转换，视为非文本容器 | `slide.js:1304` |
| `display: none` / `visibility: hidden` / `opacity: 0` | — | 完全跳过元素 | | `slide.js:1841` |
| `flex-direction` | `row`, `column`（及变体） | 决定对齐轴映射方向 | 仅 row/column 有实际意义 | `slide.js:1306` |
| `justify-content` | `center`, `flex-start`, `flex-end`, `space-between` | 根据 direction 映射为 `align` 或 `valign` | space-between 仅用于 flex column 的 valign | `slide.js:1333` |
| `align-items` | `center`, `flex-start`, `flex-end` | 根据 direction 映射为 `valign` 或 `align` | 不支持 `stretch`, `baseline` | `slide.js:1334` |
| `overflow` | `hidden`, `clip` | `isClippedByParent()` 裁剪检测 | 仅用于检测，不映射 PPTX 属性 | `utils.js:186` |
| `vertical-align` | `middle`, `bottom`, `top` (默认) | `valign` | 仅用于非 flex 元素 | `slide.js:1347` |
| `z-index` | 数值, `auto` | 渲染排序键 | `auto` 不改变层级 | `slide.js:1844` |
| `inset` | `0px`（特殊场景） | 检测全覆盖渐变子元素 | 仅用于渐变背景检测 | `slide.js:1811` |

---

## 5. 视觉效果

| CSS 属性 | 支持的值 | PPTX 映射 | 已知限制 | 源码 |
|---|---|---|---|---|
| `opacity` | 0-1 | `(1 - opacity) * 100` → `transparency` | 父元素 opacity 会累乘 | `slide.js:600` |
| `transform: rotate()` | `rotate(Ndeg)`（通过 matrix 解析） | `rotate` | 仅支持 rotate；不支持 `scale`, `translate`, `skew` | `utils.js:663` |
| `box-shadow` | `color offsetX offsetY blurRadius` | `shadow: {type, angle, blur, offset, color, opacity}` | 仅 outer shadow；不支持 `inset`, `spread-radius` | `utils.js:775` |
| `filter: blur()` | `blur(Npx)` | `generateBlurredSVG()` → soft edges | 不支持其他 filter 函数（brightness, contrast 等） | `utils.js:514` |
| `backdrop-filter: blur()` | `blur(Npx)` | 同 `filter: blur()`，但优先读取 | PPT 不原生支持，通过 SVG 模拟 | `utils.js:516` |

---

## 6. 元素类型

### 表格

| 特性 | 支持情况 | 源码 |
|---|---|---|
| `<table>`, `<tr>`, `<th>`, `<td>` | 完整支持 | `utils.js:37` |
| `rowspan` / `colspan` | 支持 | `utils.js:168` |
| 单元格边框（四边独立） | 支持 solid/dashed/dotted | `utils.js:142` |
| 单元格背景色 | 支持（含 tr/thead/tbody/容器 继承链） | `utils.js:79` |
| 单元格 padding | px → pt | `utils.js:131` |
| 单元格文本样式 | font-size/weight/color/align/valign | `utils.js:74` |
| 单元格 vertical-align | middle/bottom/top | `utils.js:126` |

**限制**: 表格高度由 PowerPoint 控制，可能比 HTML 中略短。

### 列表

| 特性 | 支持情况 | 源码 |
|---|---|---|
| `<ul>`, `<ol>`, `<li>` | 支持（简单列表） | `slide.js:637` |
| `list-style-type: disc` | 默认，Unicode 2022 | `slide.js:655` |
| `list-style-type: circle` | Unicode 25CB | |
| `list-style-type: square` | Unicode 25A0 | |
| `list-style-type: decimal` | 有序列表 | |
| `list-style-type: none` | 无标记 | |
| `::marker` 颜色和字号 | 支持 | `slide.js:669` |

**限制**: 不支持嵌套列表；不支持 flex/grid 布局的 `<li>`。

### 图片

| 特性 | 支持情况 | 源码 |
|---|---|---|
| `<img>` | 支持，转为 PNG | `slide.js:901` |
| `object-fit: fill` | 默认行为 | `image.js:61` |
| `object-fit: contain` | 等比缩放适应 | `image.js:62` |
| `object-fit: cover` | 等比裁剪填充 | `image.js:65` |
| `object-fit: none` | 原始尺寸 | `image.js:69` |
| `object-fit: scale-down` | 取 none/contain 较小者 | `image.js:72` |
| `object-position` | 百分比/关键词 | `image.js:86` |
| `border-radius` 裁剪 | 支持四角独立圆角 | `image.js:17` |

**限制**: 需要有效的 `src`；不支持 CORS 受限图片。

### Canvas

| 特性 | 支持情况 |
|---|---|
| `<canvas>` | 支持，`toDataURL("image/png")` |

**限制**: 不支持 tainted canvas（跨域限制）。

### SVG

| 特性 | 支持情况 | 源码 |
|---|---|---|
| `<svg>` 矢量模式 | `svgToSvg()` → SVG data URL | `utils.js:711` |
| `<svg>` 位图模式 | `svgToPng()` → PNG data URL | `utils.js:675` |
| `<svg>` 可编辑模式 | `convertSVGToObjects()` → PPTX 形状/文本 | `slide.js:877` |
| SVG 内联样式 | fill, stroke, stroke-width, opacity, font-* | `utils.js:743` |

### 图标

| 图标库 | 支持情况 | 源码 |
|---|---|---|
| FontAwesome (`.fa`, `.fas`, `.far`, `.fab`, `.fa-*`) | SVG→PNG 高质量渲染 | `slide.js:257` |
| Material Icons (`.material-icons`) | html2canvas 回退 | `slide.js:445` |
| Bootstrap Icons (`.bi-*`) | html2canvas 回退 | `slide.js:445` |
| 其他图标库 | html2canvas 回退 | |

---

## 7. 禁止使用的样式

以下 CSS 特性**不被转换器支持**，使用后会导致转换结果与 HTML 预览不一致：

| 禁止样式 | 替代方案 |
|---|---|
| `background-image: url(...)` | 使用 `<img>` 标签 |
| `radial-gradient()`, `conic-gradient()` | 使用 `linear-gradient()` 或纯色 |
| 多层渐变 + `background-size` 平铺 | 使用单一渐变或纯色 |
| CSS Grid 布局 (`display: grid`) | 使用 Flexbox |
| CSS 动画 (`animation`, `transition`) | 静态样式 |
| `border-image` | 使用 `border-color` + `border-style` |
| `outline` | 使用 `border` 或 `box-shadow` |
| `text-shadow` | 在独立元素上使用 `box-shadow` |
| `clip-path` | 使用 `border-radius` 或 `overflow: hidden` |
| `column-count` / 多列布局 | 使用 Flexbox 多列 |
| `writing-mode: vertical-rl` | 使用 Flexbox column 模拟 |
| `direction: rtl` | 不支持 |

---

## 8. Tailwind CSS 安全类速查

Designer 使用 Tailwind CSS 生成 HTML，以下是白名单对应的 Tailwind 类：

### 安全

| 分类 | Tailwind 类 | 对应 CSS |
|---|---|---|
| 颜色 | `text-{color}`, `bg-{color}` | `color`, `background-color` |
| 渐变 | `bg-gradient-to-{dir}`, `from-{color}`, `via-{color}`, `to-{color}` | `background-image: linear-gradient(...)` |
| 文本大小 | `text-xs/sm/base/lg/xl/2xl/3xl/4xl/5xl/6xl/7xl/8xl/9xl` | `font-size` |
| 文本粗细 | `font-thin/extralight/light/normal/medium/semibold/bold/extrabold/black` | `font-weight` |
| 字体样式 | `italic`, `not-italic` | `font-style` |
| 文本装饰 | `underline`, `line-through`(注意: 仅 underline 有效), `no-underline` | `text-decoration` |
| 文本对齐 | `text-left`, `text-center`, `text-right`, `text-justify` | `text-align` |
| 文本变换 | `uppercase`, `lowercase`, `capitalize`(注意: capitalize 无效), `normal-case` | `text-transform` |
| 内边距 | `p-{n}`, `px-{n}`, `py-{n}`, `pt/pr/pb/pl-{n}` | `padding-*` |
| 外边距 | `m-{n}`, `mx-{n}`, `my-{n}`, `mt/mr/mb/ml-{n}` | `margin-*` (仅 left/top 偏移) |
| 边框 | `border`, `border-{n}`, `border-{color}`, `border-solid/dashed/dotted` | `border-*` |
| 圆角 | `rounded-{size}`, `rounded-t/r/b/l-{size}`, `rounded-tl/tr/br/bl-{size}` | `border-radius` |
| Flex 布局 | `flex`, `inline-flex`, `flex-col`, `flex-row`, `flex-wrap` | `display: flex` |
| Flex 对齐 | `items-start/center/end`, `justify-start/center/end/between` | `align-items`, `justify-content` |
| 透明度 | `opacity-{n}` | `opacity` |
| 阴影 | `shadow`, `shadow-{size}` | `box-shadow` |
| 旋转 | `rotate-{n}` | `transform: rotate()` |
| 溢出 | `overflow-hidden`, `overflow-clip` | `overflow` |
| 层级 | `z-{n}` | `z-index` |
| 垂直对齐 | `align-middle`, `align-bottom`, `align-top` | `vertical-align` |
| 空白处理 | `whitespace-nowrap`, `whitespace-pre`, `whitespace-pre-wrap` | `white-space` |

### 禁止

| Tailwind 类 | 原因 | 替代方案 |
|---|---|---|
| `blur-*`, `backdrop-blur-*` | PPT 渲染不一致 | 纯色色块或半透明色块 |
| `bg-gradient-*` + 透明度修饰符 (如 `from-red-500/30`) | PPT 透明度计算差异 | 纯色背景 `bg-{color}` |
| `bg-[url(...)]` | 不支持背景图片 | `<img>` 标签 |
| `animate-*`, `transition` | 不支持动画 | 静态样式 |
| `line-through` | 不支持 | 无 |
| `capitalize` | 不支持 | 手动大写 |
| `drop-shadow-*` | 不支持 filter | `shadow` (box-shadow) |
| `skew-*`, `scale-*`, `translate-*` | 仅支持 rotate | 无 |
| `columns-*` | 不支持多列 | Flexbox |
| `ring-*` | 不支持 outline | `border` 或 `shadow` |
| `bg-gradient-to-*` + `bg-fixed/local/clip` | 不支持背景附加属性 | 基本渐变 |
