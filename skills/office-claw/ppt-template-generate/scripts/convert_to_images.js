#!/usr/bin/env node
/**
 * PPT 转图片脚本
 * 使用 Spire.Presentation.Free 将 PowerPoint 文件转换为高分辨率图片
 */

const { execSync, spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const SPIRE_SCRIPT = path.join(__dirname, 'convert_to_images_spire.py');

let _checkSpireCache = null;
let _pythonCmd = null;

function findPythonCmd() {
  if (_pythonCmd !== null) return _pythonCmd;
  const skillDir = path.dirname(__dirname);
  const isWin = process.platform === 'win32';
  const venvPython = isWin
    ? path.join(skillDir, '.venv', 'Scripts', 'python.exe')
    : path.join(skillDir, '.venv', 'bin', 'python');
  _pythonCmd = fs.existsSync(venvPython) ? venvPython : 'python';
  return _pythonCmd;
}

function checkSpire() {
  if (_checkSpireCache !== null) return _checkSpireCache;
  if (!fs.existsSync(SPIRE_SCRIPT)) {
    _checkSpireCache = false;
    return false;
  }
  try {
    const pythonCmd = findPythonCmd();
    execSync(`"${pythonCmd}" "${SPIRE_SCRIPT}" --check`, {
      stdio: 'ignore',
      timeout: 5000,
    });
    _checkSpireCache = true;
    return true;
  } catch (e) {
    _checkSpireCache = false;
    return false;
  }
}

async function pptxToImages(pptxPath, outputDir, options = {}) {
  const { maxSlides = 3 } = options;

  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  if (!checkSpire()) {
    throw new Error(
      'Spire.Presentation.Free 未安装，无法转换 PPTX 文件。\n' +
      '请执行: pip install spire.presentation.free'
    );
  }

  console.log(`正在转换: ${pptxPath}`);
  console.log(`输出目录: ${outputDir}`);
  console.log('使用 Spire.Presentation 转换...');

  const pythonCmd = findPythonCmd();
  const absolutePptx = path.resolve(pptxPath);
  const absoluteOutput = path.resolve(outputDir);

  return new Promise((resolve, reject) => {
    const proc = spawn(pythonCmd, [
      SPIRE_SCRIPT,
      `--input=${absolutePptx}`,
      `--output=${absoluteOutput}`,
      `--max-slides=${maxSlides}`,
    ], { stdio: 'inherit' });

    proc.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(`Spire 转换失败，退出码: ${code}`));
        return;
      }
      const images = fs.readdirSync(absoluteOutput)
        .filter(f => /^slide-\d+\.png$/i.test(f))
        .sort()
        .map(f => path.join(absoluteOutput, f));
      console.log(`转换完成，共生成 ${images.length} 张图片`);
      resolve(images);
    });

    proc.on('error', reject);
  });
}

async function pptxDirToImages(splitDir, outputDir) {
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  if (!checkSpire()) {
    throw new Error(
      'Spire.Presentation.Free 未安装，无法转换 PPTX 文件。\n' +
      '请执行: pip install spire.presentation.free'
    );
  }

  const splitFiles = fs.readdirSync(splitDir)
    .filter(f => /^slide_\d+\.pptx$/i.test(f))
    .sort();

  if (splitFiles.length === 0) {
    throw new Error(`单页 PPTX 目录为空: ${splitDir}`);
  }

  console.log(`正在转换 ${splitFiles.length} 个单页 PPTX...`);

  const pythonCmd = findPythonCmd();
  const absoluteOutput = path.resolve(outputDir);
  const failedSlides = [];

  for (let i = 0; i < splitFiles.length; i++) {
    const absoluteInput = path.resolve(path.join(splitDir, splitFiles[i]));

    await new Promise((resolve, reject) => {
      const proc = spawn(pythonCmd, [
        SPIRE_SCRIPT,
        `--input=${absoluteInput}`,
        `--output=${absoluteOutput}`,
        '--max-slides=1',
        `--offset=${i}`,
      ], { stdio: 'inherit' });

      proc.on('close', (code) => {
        if (code !== 0) {
          failedSlides.push(splitFiles[i]);
          console.warn(`  警告: ${splitFiles[i]} 转换失败（退出码 ${code}），跳过`);
        }
        resolve();
      });

      proc.on('error', reject);
    });
  }

  if (failedSlides.length > 0) {
    console.warn(`转换完成，${failedSlides.length} 页失败: ${failedSlides.join(', ')}`);
  }

  const images = fs.readdirSync(absoluteOutput)
    .filter(f => /^slide-\d+\.png$/i.test(f))
    .sort()
    .map(f => path.join(absoluteOutput, f));

  console.log(`转换完成，共生成 ${images.length} 张图片`);
  return images;
}

function checkDependencies() {
  return { spire: checkSpire() };
}

async function main() {
  const args = process.argv.slice(2);

  if (args.length === 0 || args[0] === '--help') {
    console.log(`
用法: node convert_to_images.js <pptx文件> [输出目录] [选项]

选项:
  --max-slides=3       最多转换页数 (默认: 3)
  --check              检查环境依赖

示例:
  node convert_to_images.js presentation.pptx ./slides
  node convert_to_images.js presentation.pptx ./slides --max-slides=5
  node convert_to_images.js --check
`);
    process.exit(0);
  }

  if (args[0] === '--check') {
    const deps = checkDependencies();
    console.log(`Spire: ${deps.spire ? '✓ 已安装' : '✗ 未安装（pip install spire.presentation.free）'}`);
    process.exit(deps.spire ? 0 : 1);
  }

  const pptxPath = args[0];
  const outputDir = args[1] || './slides';

  const options = {};
  for (const arg of args.slice(2)) {
    if (arg.startsWith('--')) {
      const [key, value] = arg.slice(2).split('=');
      options[key.replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = value;
    }
  }

  try {
    const images = await pptxToImages(pptxPath, outputDir, options);
    console.log('\n生成的图片:');
    console.log(JSON.stringify(images, null, 2));
  } catch (error) {
    console.error(`错误: ${error.message}`);
    process.exit(1);
  }
}

module.exports = {
  pptxToImages,
  pptxDirToImages,
  checkDependencies,
  checkSpire,
  findPythonCmd,
};

if (require.main === module) {
  main();
}
