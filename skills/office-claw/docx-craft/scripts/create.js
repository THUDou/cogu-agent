#!/usr/bin/env node

/**
 * docx-craft: Create DOCX documents from recipe + content JSON.
 *
 * 支持两种引擎：
 *   - docx（默认）：使用 docx-js 构建，适用于 6 种标准文档模板
 *   - mammoth：使用 HTML 模板 + pandoc 构建，适用于会议纪要等模板
 *
 * Usage:
 *   node scripts/create.js --recipe report --content content.json --output out.docx
 *   node scripts/create.js --recipe meeting_decision --content decision.json --output meeting.docx
 *   node scripts/create.js --recipe meeting_decision --content data.json --output meeting.docx --engine docx
 */

const path = require('path');
const fs = require('fs');
const documentBuilder = require('./generator/document_builder');

// mammoth 引擎的 recipe 名称列表
const MAMMOTH_RECIPES = ['meeting_decision', 'meeting_daily', 'meeting_seminar'];

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i++) {
    if (argv[i].startsWith('--')) {
      // 保留原始 key 名（不转 camelCase），用于 engine 等参数
      const rawKey = argv[i].slice(2);
      const key = rawKey.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
      const next = argv[i + 1];
      if (next && !next.startsWith('--')) {
        args[key] = next;
        args[rawKey] = next; // 同时保留原始格式
      } else {
        args[key] = true;
        args[rawKey] = true;
      }
    }
  }
  return args;
}

function getRecipeEngine(recipeName) {
  const recipePath = path.resolve(__dirname, '../recipes', `${recipeName}.json`);
  try {
    const recipe = require(recipePath);
    return recipe.engine || 'docx';
  } catch {
    return 'docx';
  }
}

async function main() {
  const args = parseArgs(process.argv);

  if (!args.recipe) {
    console.error('Error: --recipe is required');
    console.error('  docx 引擎: academic|report|government|memo|letter|default');
    console.error('  mammoth 引擎: meeting_decision|meeting_daily|meeting_seminar');
    process.exit(1);
  }
  if (!args.content) {
    console.error('Error: --content is required (path to content/data JSON)');
    process.exit(1);
  }
  if (!args.output) {
    console.error('Error: --output is required (output .docx path)');
    process.exit(1);
  }

  // 确定引擎 — 优先级: --engine 参数 > recipe JSON 声明 > 自动检测
  let engine = args.engine || getRecipeEngine(args.recipe);
  if (engine === 'auto') {
    engine = MAMMOTH_RECIPES.includes(args.recipe) ? 'mammoth' : 'docx';
  }

  const contentPath = path.resolve(args.content);
  if (!fs.existsSync(contentPath)) {
    console.error(`Error: content file not found: ${contentPath}`);
    process.exit(1);
  }

  if (engine === 'mammoth') {
    // ====== mammoth + HTML 路径 ======
    const htmlBuilder = require('./create_html');
    try {
      const outputPath = await htmlBuilder.build({
        template: args.recipe,
        data: contentPath,
        output: path.resolve(args.output),
      });
      console.log(`Created: ${outputPath}`);
    } catch (e) {
      console.error(`Error: ${e.message}`);
      process.exit(1);
    }
  } else {
    // ====== docx-js 路径（原有） ======
    const options = {
      recipe: args.recipe,
      content: contentPath,
      output: path.resolve(args.output),
      title: args.title,
      author: args.author,
      pageSize: args.pageSize,
      margins: args.margins,
      noToc: args.noToc || false,
      noCover: args.noCover || false,
    };

    try {
      const outputPath = await documentBuilder.build(options);
      console.log(`Created: ${outputPath}`);
    } catch (e) {
      console.error(`Error: ${e.message}`);
      process.exit(1);
    }
  }
}

main();
