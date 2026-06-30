#!/usr/bin/env node


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

  const result = await mammoth.convertToHtml({ path: inputPath });
  
  const html = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="generator" content="docx-craft / mammoth">
<style>

body {
  font-family: 'Arial', sans-serif;
  font-size: 12pt;
  line-height: 1.5;
  margin: 72pt 72pt;
  color: #000;
}

.title-main {
  font-size: 24pt;
  font-weight: bold;
  text-align: center;
  margin-bottom: 6pt;
}

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

p {
  margin: 6pt 0;
}

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
