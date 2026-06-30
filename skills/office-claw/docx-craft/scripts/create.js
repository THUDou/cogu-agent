#!/usr/bin/env node


const path = require('path');
const fs = require('fs');
const documentBuilder = require('./generator/document_builder');

const MAMMOTH_RECIPES = ['meeting_decision', 'meeting_daily', 'meeting_seminar'];

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i++) {
    if (argv[i].startsWith('--')) {
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
