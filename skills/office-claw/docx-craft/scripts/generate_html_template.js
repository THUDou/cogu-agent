#!/usr/bin/env node

/**
 * generate_html_template.js — 一次性开发脚本
 *
 * 用 mammoth 将 .docx 模板转为 HTML 结构，并注入 CSS 样式信息。
 * 输出结果供手工精调，替换占位符。
 *
 * 用法:
 *   node scripts/generate_html_template.js <input.docx> <output.html> [--style-inline]
 */

const mammoth = require('mammoth');
const fs = require('fs');
const path = require('path');

async function main() {
  const args = process.argv.slice(2);
  if (args.length < 2) {
    console.error('Usage: node scripts/generate_html_template.js <input.docx> <output.html>');
    process.exit(1);
  }

  const inputPath = path.resolve(args[0]);
  const outputPath = path.resolve(args[1]);

  if (!fs.existsSync(inputPath)) {
    console.error(`Input file not found: ${inputPath}`);
    process.exit(1);
  }

  // 1. 使用 mammoth 转换 DOCX → HTML (保留原始结构)
  const result = await mammoth.convertToHtml({ path: inputPath });
  
  // 2. 生成完整 HTML 文档（含 CSS）
  const html = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="generator" content="docx-craft / mammoth">
<style>
/*
 * 样式模板 — 请根据源 .docx 模板的实际样式精调
 * mammoth 导出的 HTML 不带格式信息，
 * 以下样式需根据模板手工填入准确值。
 */

/* === 页面基础 === */
body {
  font-family: 'Arial', sans-serif;
  font-size: 12pt;
  line-height: 1.5;
  margin: 72pt 72pt;
  color: #000;
}

/* === 标题 === */
.title-main {
  font-size: 24pt;
  font-weight: bold;
  text-align: center;
  margin-bottom: 6pt;
}

/* === 表格 === */
table {
  border-collapse: collapse;
  width: 100%;
  margin: 12pt 0;
}
table td, table th {
  border: 1px solid #000;
  padding: 4pt 8pt;
  vertical-align: top;
}
table th {
  font-weight: bold;
  text-align: center;
}
.table-label {
  background-color: #E6E6E6;
  font-weight: bold;
}

/* === 段落 === */
p {
  margin: 6pt 0;
}

/* === 列表 === */
ol {
  margin: 6pt 0;
  padding-left: 24pt;
}
</style>
</head>
<body>
${result.value}
</body>
</html>`;

  // 3. 写入 HTML 文件
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, html, 'utf-8');

  console.log(`Generated: ${outputPath}`);
  console.log(`Warnings: ${result.messages.length}`);
  result.messages.forEach(m => {
    if (m.type === 'warning') console.warn(`  [warn] ${m.message}`);
  });
}

main().catch(e => {
  console.error(e.message);
  process.exit(1);
});
