# docx-js 关键规则与 API 模式

## 14 条关键规则

| # | 规则 | 说明 |
|---|------|------|
| 1 | 表格必须同时设置 `width` 和 `columnWidths` | 双宽度要求，缺少任一则渲染异常 |
| 2 | 表格底纹用 `ShadingType.CLEAR` 而非 `SOLID` | SOLID 语义差异会导致黑色背景 |
| 3 | 列表项用 `LevelFormat` 而非 Unicode 字符 | Word 依赖编号定义，Unicode 项目符号不生效 |
| 4 | 图片必须指定 `type` 参数 | 决定嵌入格式（png/jpg/gif/bmp/svg） |
| 5 | 分页符用 `PageBreak` 而非 `\n` | `\n` 不会产生分页效果 |
| 6 | 超链接用 `ExternalHyperlink` 包裹 | 确保可点击链接 |
| 7 | 脚注用 `Footnote` 并在段落中引用 | `FootnoteReferenceRun(id)` |
| 8 | 制表位用 `TabStop` 和 `TabStopType` | 右对齐/点前导等 |
| 9 | 多栏布局用 `Column` 配置 | `column: { count, space, equalWidth }` |
| 10 | 目录用 `TableOfContents` | `headingStyleRange: "1-3"` |
| 11 | 页眉页脚在 `Header` / `Footer` 中定义 | 支持 default/first/even/odd |
| 12 | 段落间距用 `spacing` 的 `before` / `after` | 单位 DXA，240 = 0.25 英寸 |
| 13 | 行距用 `line` 和 `lineRule` | `LineRuleType.AUTO` 或 `EXACT` |
| 14 | CJK 字体回退链用 `RunFonts` | 设置 ascii / eastAsia / hAnsi / cs |

## 常用 API 模式

### 页面尺寸

```javascript
// docx-js 默认 A4，必须显式设置
sections: [{
  properties: {
    page: {
      size: {
        width: 12240,   // US Letter
        height: 15840
      },
      margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
    }
  },
  children: [/* content */]
}]
```

**页面尺寸表 (DXA)**:

| 纸张 | 宽 | 高 |
|------|------|------|
| US Letter | 12,240 | 15,840 |
| A4 | 11,906 | 16,838 |
| Legal | 12,240 | 20,160 |
| A3 | 16,838 | 23,811 |

**换算**: 1 inch = 1440 DXA, 1 cm ≈ 567 DXA

### 样式系统

```javascript
const doc = new Document({
  styles: {
    default: {
      document: {
        run: { font: "Arial", size: 24 },  // 12pt = size 24
      },
    },
    paragraphStyles: [
      {
        id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 240, after: 240 }, outlineLevel: 0 },  // outlineLevel 必需!
      },
      {
        id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 180, after: 180 }, outlineLevel: 1 },
      },
    ],
  },
  sections: [/* ... */],
});
```

**要点**:
- 使用精确 ID 覆盖内置样式: "Heading1", "Heading2" 等
- `outlineLevel` 是必需的 — 没有它 TOC 和导航不可用
- 字号: `size` = pt × 2 (12pt → 24, 16pt → 32)

### 列表

```javascript
// 正确: 使用 LevelFormat
const doc = new Document({
  numbering: {
    config: [
      {
        reference: "bullets",
        levels: [{
          level: 0, format: LevelFormat.BULLET, text: "•",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } },
        }],
      },
      {
        reference: "numbers",
        levels: [{
          level: 0, format: LevelFormat.DECIMAL, text: "%1.",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } },
        }],
      },
    ],
  },
  sections: [{
    children: [
      new Paragraph({ numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Bullet item")] }),
      new Paragraph({ numbering: { reference: "numbers", level: 0 },
        children: [new TextRun("Numbered item")] }),
    ],
  }],
});
```

**注意**: 相同 reference 延续编号，不同 reference 重新开始。

### 表格

```javascript
// CRITICAL: 双宽度 + DXA + CLEAR
const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };

new Table({
  width: { size: 9360, type: WidthType.DXA },       // 总宽度
  columnWidths: [4680, 4680],                         // 列宽之和 = 总宽度
  rows: [
    new TableRow({
      children: [
        new TableCell({
          borders,
          width: { size: 4680, type: WidthType.DXA }, // 单元格宽度匹配列宽
          shading: { fill: "D5E8F0", type: ShadingType.CLEAR },  // CLEAR 不是 SOLID!
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          children: [new Paragraph({ children: [new TextRun("Cell")] })],
        }),
      ],
    }),
  ],
})
```

**宽度计算**: US Letter 1英寸边距 → 内容宽 = 12240 - 2880 = 9360 DXA

### 图片

```javascript
new Paragraph({
  children: [new ImageRun({
    type: "png",                    // 必需!
    data: fs.readFileSync("img.png"),
    transformation: { width: 200, height: 150 },
    altText: { title: "Title", description: "Desc", name: "Name" },  // 三项都必需
  })],
})
```

### 页眉页脚

```javascript
sections: [{
  properties: {
    page: { margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } },
  },
  headers: {
    default: new Header({ children: [new Paragraph("Header")] }),
  },
  footers: {
    default: new Footer({
      children: [new Paragraph({
        children: [
          new TextRun("Page "),
          new TextRun({ children: [PageNumber.CURRENT] }),
          new TextRun(" of "),
          new TextRun({ children: [PageNumber.TOTAL_PAGES] }),
        ],
      })],
    }),
  },
  children: [/* content */],
}]
```

### 目录

```javascript
new TableOfContents("Table of Contents", {
  hyperlink: true,
  headingStyleRange: "1-3",
})
```

**注意**: 标题必须使用 `HeadingLevel`，不能用自定义样式。

### CJK 字体配置

```javascript
// 设置字体回退链
run: {
  font: {
    ascii: "Calibri",
    eastAsia: "SimSun",      // 中文字体
    hAnsi: "Calibri",
    cs: "Times New Roman",   // 复杂脚本
  },
}
```

### 横向页面

```javascript
// docx-js 内部交换宽高，传入竖向尺寸即可
size: {
  width: 12240,   // 短边
  height: 15840,  // 长边
  orientation: PageOrientation.LANDSCAPE,
},
// 内容宽度 = 15840 - left margin - right margin
```
