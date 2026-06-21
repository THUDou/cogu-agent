# 图表附录（Charts Appendix）

> 本文件从 `designer/SKILL.md` 拆出，供**图表候选页**在生成前读取。页面类型为 `data` / `comparison` / `technology` / `trend` 的内容页默认都是图表候选页；结构性页面（cover/section/chapter/ending/agenda 等无图表页面）无需读取。
> 图表容器的 flex/高度约束见 `designer/SKILL.md` 的「防溢出硬性约束 → #### 5. 图表容器约束」。

## 图表与数据可视化

### 图表类型选择

> **⚠️ 按页面类型选默认图表（避免选型反复横跳）**：先按页面 `类型` 直接取默认图表，不要在多个图表类型间反复比较纠结——除非数据形态明显更适合别的类型：
> - `trend`（趋势）→ **折线图**（时间序列）
> - `data` / `comparison`（数据/对比）→ **柱状图/分组柱状图**（类别对比）；占比才用饼图
> - `technology` / 多维能力对比 → **雷达图**
> - 其余按下表数据形态选。**同一页只在"默认图表不合数据"时才换，换一次即定，不要 radar↔bar 来回切。**

根据数据类型和目的选择最合适的图表类型：

| 数据类型/目的            | 推荐图表类型          | 适用的变种             | 用途说明                             |
| ------------------------ | --------------------- | ---------------------- | ------------------------------------ |
| **比较类别数据**         | 柱状图 (Bar Chart)    | 分组柱状图、堆叠柱状图 | 比较不同类别的数据或显示时间趋势     |
| **时间序列数据**         | 折线图 (Line Chart)   | 面积图、堆叠面积图     | 显示数据随时间变化的趋势             |
| **两变量关系**           | 散点图 (Scatter Plot) | 气泡图                 | 显示两个变量之间的关系和相关性       |
| **类别占比**             | 饼图 (Pie Chart)      | -                      | 显示类别在整体中的比例               |
| **单一变量分布**         | 直方图 (Histogram)    | 核密度估计图           | 显示单一变量的分布                   |
| **数据分布和离群值检测** | 箱线图 (Box Plot)     | -                      | 显示数据分布的五数概括，包括离群值   |
| **多维数据比较**         | 雷达图 (Radar Chart)  | -                      | 显示多个变量在不同类别中的相对表现   |
| **矩阵数据**             | 热力图 (Heatmap)      | -                      | 显示矩阵数据的值，通过颜色编码表示   |
| **层次结构数据**         | 树状图 (Tree Map)     | -                      | 显示层次性数据的比例                 |
| **地理位置数据**         | 地图 (Map)            | 气泡地图、热力地图     | 显示地理位置数据，如销售额、人口     |
| **三变量关系**           | 气泡图 (Bubble Chart) | -                      | 同时表示三个变量，包括气泡大小和颜色 |

### 图表规范

- 数据标签清晰标注数据值、单位
- 坐标轴明确标注含义和单位
- 多系列数据必须添加图例
- 颜色与整体配色方案协调
- 注明数据来源
- ECharts 图表允许使用半透明纯色（如 `rgba(74, 108, 140, 0.18)`），但禁止使用渐变色配置；尤其是折线/面积图的 `areaStyle` 必须写成纯色字符串，不能写成 `colorStops` 渐变对象

### ECharts 示例

```javascript
// 强制：必须使用 echarts.init(document.getElementById('xxx'), null, { renderer: 'svg' }) 单行形式初始化
// 重要：{ renderer: 'svg' } 参数确保 html-to-pptx 引擎能提取矢量图，避免使用 canvas 导致输出位图
// 禁止：ECharts 渐变填充会生成 SVG linearGradient/radialGradient，导出 PPTX 时会触发位图化
// 允许：半透明纯色，例如 areaStyle: { color: "rgba(74, 108, 140, 0.18)" }
const CHART_FONT_FAMILY = "WenYuan Sans SC, Noto Sans SC, sans-serif";
const chart = echarts.init(document.getElementById("chart-id"), null, {
  renderer: "svg",
});
const option = {
  animation: false,
  textStyle: { fontFamily: CHART_FONT_FAMILY },
  color: ["#4A6C8C", "#8D99AE", "#D4A373"],
  grid: { left: "3%", right: "4%", bottom: "3%", containLabel: true },
  xAxis: {
    type: "category",
    data: ["2020", "2021", "2022", "2023", "2024"],
    axisLabel: { fontFamily: CHART_FONT_FAMILY, fontSize: 12 },
    nameTextStyle: { fontFamily: CHART_FONT_FAMILY, fontSize: 12 },
    axisLine: { lineStyle: { color: "#8D99AE" } },
  },
  yAxis: {
    type: "value",
    axisLabel: { fontFamily: CHART_FONT_FAMILY, fontSize: 12 },
    nameTextStyle: { fontFamily: CHART_FONT_FAMILY, fontSize: 12 },
    axisLine: { lineStyle: { color: "#8D99AE" } },
    splitLine: { lineStyle: { color: "#E5E5E5" } },
  },
  series: [
    {
      data: [50, 85, 140, 220, 380],
      type: "bar",
      barWidth: "50%",
      itemStyle: { borderRadius: [4, 4, 0, 0] },
    },
  ],
};
chart.setOption(option);
```

---

## ECharts JavaScript 安全编码规范

### formatter 函数书写规则（重要）

**背景**：ECharts 在某些情况下会将内联 `formatter` 函数序列化为字符串再解析。如果函数体内包含除法运算符 `/`、中文字符串或正则表达式，序列化后的字符串可能导致解析失败，报错：

```
Uncaught (in promise) Error: Unexpected '/'. Escaping special characters with \ may help.
```

**禁止**在 ECharts 配置对象内部直接定义包含以下内容的 `formatter` 函数：

- 除法运算符 `/`
- 中文字符串
- 正则表达式

**正确做法**：将 `formatter` 函数提取为独立的外部函数，然后通过引用传递。

**❌ 错误示例**：

```javascript
chart.setOption({
  yAxis: {
    axisLabel: {
      formatter: function (value) {
        if (value >= 10000) return value / 10000 + "亿"; // ❌ 错误：除法 + 中文
        return value + "万";
      },
    },
  },
});
```

**✅ 正确示例**：

```javascript
// 步骤 1：在 chart.setOption 之前定义外部函数
function formatAxisValue(value) {
  if (value >= 10000) return value / 10000 + "亿";
  if (value >= 1000) return value / 1000 + "千万";
  return value + "万";
}

// 步骤 2：在配置中引用外部函数
chart.setOption({
  yAxis: {
    axisLabel: { formatter: formatAxisValue }, // ✅ 正确：引用外部函数
  },
});
```

### 通用格式化函数模板

**⚠️ formatter 参数类型差异**：

ECharts 的 `formatter` 回调参数类型取决于使用位置：

| 使用位置 | 参数类型 | 示例 |
|----------|----------|------|
| `yAxis.axisLabel.formatter` | 原始数值（number） | `993`、`15000` |
| `xAxis.axisLabel.formatter` | 原始数值（number） | 同上 |
| `series[].label.formatter` | **params 对象** | `{ value: 993, dataIndex: 0, ... }` |
| `tooltip.formatter` | **params 数组** | `[{ value: 993, ... }, ...]` |

**常见错误**：在 `series[].label.formatter` 中使用 `function(value)` 并对 `value` 调用 `.toFixed()` 或 `.toString()`，此时 `value` 是 params 对象，结果是 `"[object Object]"` 或报错。

**正确做法**：根据使用位置选择合适的函数签名。

**axisLabel 格式化（接收原始数值）**：

```javascript
// 用于 yAxis.axisLabel.formatter / xAxis.axisLabel.formatter
function formatAxisNumber(value) {
  if (value >= 100000000) return (value / 100000000).toFixed(1) + "亿";
  if (value >= 10000000) return (value / 10000000).toFixed(1) + "千万";
  if (value >= 10000) return (value / 10000).toFixed(1) + "万";
  if (value >= 1000) return (value / 1000).toFixed(0) + "千";
  return value.toString();
}

function formatAxisPercent(value) {
  return (value * 100).toFixed(1) + "%";
}
```

**series label 格式化（接收 params 对象）**：

```javascript
// 用于 series[].label.formatter
function formatLabelNumber(params) {
  var value = typeof params === "object" ? params.value : params;
  if (value == null) return "";
  if (value >= 100000000) return (value / 100000000).toFixed(1) + "亿";
  if (value >= 10000) return (value / 10000).toFixed(1) + "万";
  return value.toString();
}

function formatLabelPercent(params) {
  var value = typeof params === "object" ? params.value : params;
  if (value == null) return "";
  return value.toFixed(1) + "%";
}
```

**使用示例**：

```javascript
(function () {
  // axisLabel 用：接收原始数值
  function formatAxisNumber(value) {
    if (value >= 100000000) return (value / 100000000).toFixed(1) + "亿";
    if (value >= 10000) return (value / 10000).toFixed(1) + "万";
    return value.toString();
  }

  // series label 用：接收 params 对象，需提取 .value
  function formatLabelNumber(params) {
    var value = typeof params === "object" ? params.value : params;
    if (value == null) return "";
    if (value >= 10000) return (value / 10000).toFixed(1) + "万";
    return value.toString();
  }

  const chart = echarts.init(document.getElementById("chart"), null, {
    renderer: "svg",
  });
  chart.setOption({
    animation: false,
    xAxis: { type: 'category' },
    yAxis: { axisLabel: { formatter: formatAxisNumber } },
    series: [
      {
        type: "bar",
        label: {
          show: true,
          formatter: formatLabelNumber, // 不是 formatAxisNumber！
        },
      },
    ],
  });
})();
```

### 代码检查清单

生成 ECharts 图表代码后，必须逐项检查：

- [ ] 初始化是否使用单行形式 `echarts.init(document.getElementById('xxx'), null, { renderer: 'svg' })`（禁止两步赋值）
- [ ] **是否使用 SVG 渲染器** `{ renderer: 'svg' }` 作为第三个参数（确保 html-to-pptx 能提取矢量图）
- [ ] 所有 `formatter` 函数是否定义在配置对象外部
- [ ] 是否使用函数引用而非内联定义
- [ ] 函数是否使用 `function` 关键字或箭头函数定义
- [ ] 图表代码是否包裹在 IIFE 中：`(function() { ... })();`
- [ ] 是否设置 `animation: false` 禁用动画（PPT 静态输出必须禁用）
- [ ] 是否定义并使用 `CHART_FONT_FAMILY`，且 `textStyle`、图例、坐标轴、轴名称、数据标签均显式设置 `fontFamily`
- [ ] 是否禁用了 ECharts 渐变填充：禁止 `colorStops`、`type: "linear"`、`type: "radial"`、`echarts.graphic.LinearGradient`、`echarts.graphic.RadialGradient`
- [ ] 折线/面积图如需面积填充，`areaStyle.color` 是否使用半透明纯色字符串（如 `rgba(..., 0.18)`），而不是渐变对象
- [ ] **series[].label.formatter 的函数参数是否从 params 对象提取 `.value`**（直接使用参数会得到 `[object Object]`）
- [ ] axisLabel.formatter 和 series.label.formatter 是否使用了对应的函数（前者接收数值，后者接收 params 对象）
