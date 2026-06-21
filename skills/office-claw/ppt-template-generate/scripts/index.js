#!/usr/bin/env node
/**
 * PPT 模板规范生成 - 主入口脚本
 * 协调工具提取、视觉分析、聚合生成等流程
 */

const fs = require('fs');
const path = require('path');
const { execSync, spawn } = require('child_process');

// 强制所有 Python 子进程使用 UTF-8 输出（修复 Windows 控制台乱码）
process.env.PYTHONUTF8 = '1';

// 获取脚本目录
const SCRIPTS_DIR = __dirname;
const SKILL_DIR = path.dirname(SCRIPTS_DIR);
const PROJECT_ROOT = path.resolve(SKILL_DIR, '..', '..');

// 默认输出根目录（可通过 --output-dir 覆盖）
const DEFAULT_HUB_DIR = path.join(PROJECT_ROOT, 'ppt-template-hub');

const { findPythonCmd, pptxDirToImages } = require('./convert_to_images.js');

/**
 * 生成时间戳字符串（用于区分并行任务）
 * 格式: YYYYMMDD_HHMMSS_xxx (xxx 为随机 3 位数)
 */
function generateTimestamp() {
  const now = new Date();
  const date = now.toISOString().slice(0, 10).replace(/-/g, '');
  const time = now.toISOString().slice(11, 19).replace(/:/g, '');
  const random = String(Math.floor(Math.random() * 1000)).padStart(3, '0');
  return `${date}_${time}_${random}`;
}

function generateHtmlTemplateSkeletons(templateSpecPath, outputDir) {
  const { generateHtmlTemplates } = require('./generate-html-templates.js');
  if (!fs.existsSync(templateSpecPath)) {
    throw new Error(`template-spec.json not found: ${templateSpecPath}`);
  }
  const spec = JSON.parse(fs.readFileSync(templateSpecPath, 'utf-8'));
  const manifest = generateHtmlTemplates(spec, outputDir);
  return {
    manifestPath: path.join(outputDir, 'template-manifest.json'),
    templateCount: (manifest.bases || manifest.templates || []).length,
  };
}

function resolveVlmAvailability({ skipVlm, strictVlm, vlmApiOk, failureReason }) {
  if (skipVlm) return { skipVlm: true, fallbackReason: null };
  if (vlmApiOk) return { skipVlm: false, fallbackReason: null };

  const reason = failureReason || 'VLM API 未配置或不可用';
  if (strictVlm) {
    throw new Error(
      'VLM_DEPENDENCY_MISSING\n' +
      `原因: ${reason}`
    );
  }

  return { skipVlm: true, fallbackReason: reason };
}

/**
 * 检测运行时依赖：Node.js 版本、Python、python-pptx、lxml、Pillow
 * 返回各依赖的状态对象
 */
function checkRuntimeDeps() {
  const results = {
    nodejs: { ok: false, detail: '' },
    python: { ok: false, detail: '', cmd: '' },
    python_pptx: { ok: false, detail: '' },
  };

  // Node.js ≥ 18
  const nodeVer = process.version;
  const major = parseInt(nodeVer.slice(1), 10);
  results.nodejs.ok = major >= 18;
  results.nodejs.detail = results.nodejs.ok ? `${nodeVer} (≥18)` : `${nodeVer} (需要 ≥18)`;

  // Python：优先 venv，回退系统 python
  const pythonCmd = findPythonCmd();
  results.python.cmd = pythonCmd;

  try {
    const ver = execSync(`"${pythonCmd}" --version`, { encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] }).trim();
    results.python.ok = true;
    results.python.detail = `${ver}`;
  } catch {
    results.python.ok = false;
    results.python.detail = `未找到 (${pythonCmd})`;
  }

  // Python 包检测（仅当 Python 可用时）
  if (results.python.ok) {
    const checkPkg = (importName) => {
      try {
        execSync(`"${pythonCmd}" -c "import ${importName}"`, { encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] });
        return { ok: true, detail: '✓ 已安装' };
      } catch {
        return { ok: false, detail: '✗ 未安装' };
      }
    };
    const pptx = checkPkg('pptx');
    results.python_pptx.ok = pptx.ok;
    results.python_pptx.detail = pptx.detail;
  } else {
    results.python_pptx.detail = '✗ (Python 不可用)';
  }

  return results;
}

/**
 * 打印完整环境检测报告（运行时 + 图片转换）
 */
function printEnvReport(runtimeDeps, imageDeps, imageChecked) {
  const mark = (ok) => ok ? '✓' : '✗';
  console.log('环境检测结果:');
  console.log(`  Node.js:     ${mark(runtimeDeps.nodejs.ok)} ${runtimeDeps.nodejs.detail}`);
  console.log(`  Python:      ${mark(runtimeDeps.python.ok)} ${runtimeDeps.python.detail}`);
  console.log(`  python-pptx: ${runtimeDeps.python_pptx.detail}`);
  if (imageChecked) {
    console.log(`  Spire:       ${mark(imageDeps.spire)} ${imageDeps.spire ? '已安装' : '未安装（pip install spire.presentation.free）'}`);
  } else {
    console.log(`  图片转换依赖: 跳过检测（--skip-convert 已启用且 VLM 未开启）`);
  }
}

/**
 * 执行 Python 结构提取
 */
function extractStructure(pptxPath, outputPath) {
  const scriptPath = path.join(SCRIPTS_DIR, 'extract_structure.py');
  const pythonCmd = findPythonCmd();
  const cmd = `"${pythonCmd}" "${scriptPath}" "${pptxPath}" "${outputPath}"`;

  console.log('执行结构提取...');
  try {
    execSync(cmd, { stdio: 'inherit' });
    return true;
  } catch (error) {
    console.error('结构提取失败:', error.message);
    return false;
  }
}

/**
 * 执行图片资产提取
 */
function extractImages(pptxPath, outputDir) {
  const scriptPath = path.join(SCRIPTS_DIR, 'extract_images.py');
  const pythonCmd = findPythonCmd();
  const cmd = `"${pythonCmd}" "${scriptPath}" --input="${pptxPath}" --output="${outputDir}"`;

  console.log('执行图片资产提取...');
  try {
    execSync(cmd, { stdio: 'inherit' });
    return true;
  } catch (error) {
    console.error('图片资产提取失败:', error.message);
    return false;
  }
}

/**
 * 调用 split_pptx.py，将 PPTX 拆分为单页临时文件
 */
function splitPptx(pptxPath, outputDir, options = {}) {
  const { maxSlides = 0 } = options;
  const scriptPath = path.join(SCRIPTS_DIR, 'split_pptx.py');
  const pythonCmd = findPythonCmd();
  const cmd = `"${pythonCmd}" "${scriptPath}" --input="${path.resolve(pptxPath)}" --output="${path.resolve(outputDir)}" --max-slides=${maxSlides}`;

  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }
  console.log('拆分 PPTX 为单页文件...');
  try {
    execSync(cmd, { stdio: 'inherit' });
  } catch (error) {
    throw new Error(`PPTX 拆分失败: ${error.message}`);
  }

  const files = fs.readdirSync(outputDir).filter(f => /^slide_\d+\.pptx$/i.test(f));
  if (files.length === 0) {
    throw new Error(`拆分后未生成任何单页文件: ${outputDir}`);
  }
  console.log(`拆分完成，共 ${files.length} 个单页文件`);
  return files.length;
}

/**
 * 执行图片转换（Spire.Presentation.Free）
 */
async function convertToImages(pptxPath, outputDir, options = {}) {
  const { pptxToImages } = require('./convert_to_images.js');
  console.log('执行 PPT 转图片...');
  return pptxToImages(pptxPath, outputDir, options);
}

/**
 * 执行 VLM 视觉分析（必需，失败则抛出错误）
 */
async function runVLMAnalysis(slidesDir, configPath) {
  const { batchAnalyze, testConnection } = require('./vlm-analyzer.js');

  const configLoaded = await testConnection(configPath);
  if (!configLoaded) {
    throw new Error('VLM API 未正确配置，请检查 vlm-config.json');
  }

  console.log('执行 VLM 视觉分析...');
  const result = await batchAnalyze(slidesDir, configPath, null);
  return result;
}

/**
 * 执行聚合生成
 */
function aggregate(structurePath, outputPath, options) {
  const scriptPath = path.join(SCRIPTS_DIR, 'aggregate.js');
  let cmd = `node "${scriptPath}" "${structurePath}" "${outputPath}"`;

  if (options.name) {
    cmd += ` --name="${options.name}"`;
  }
  if (options.vlmPath) {
    cmd += ` --vlm="${options.vlmPath}"`;
  }
  if (options.timestamp) {
    cmd += ` --timestamp="${options.timestamp}"`;
  }
  if (options.imageMapPath) {
    cmd += ` --image-map="${options.imageMapPath}"`;
  }
  if (options.reusableStyleAssetsPath) {
    cmd += ` --reusable-style-assets="${options.reusableStyleAssetsPath}"`;
  }
  if (options.specPath) {
    cmd += ` --template-spec="${options.specPath}"`;
  }

  console.log('执行聚合生成...');
  try {
    execSync(cmd, { stdio: 'inherit' });
    return true;
  } catch (error) {
    console.error('聚合生成失败:', error.message);
    return false;
  }
}

/**
 * hex -> HSL（h: 0-360, s: 0-1, l: 0-1）
 */
function hexToHsl(hex) {
  if (!hex || hex.length < 7) return { h: 0, s: 0, l: 0 };
  const r = parseInt(hex.slice(1, 3), 16) / 255;
  const g = parseInt(hex.slice(3, 5), 16) / 255;
  const b = parseInt(hex.slice(5, 7), 16) / 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  const l = (max + min) / 2;
  if (max === min) return { h: 0, s: 0, l };
  const d = max - min;
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
  let h;
  if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) / 6;
  else if (max === g) h = ((b - r) / d + 2) / 6;
  else h = ((r - g) / d + 4) / 6;
  return { h: h * 360, s, l };
}

/**
 * 将 hex 颜色映射到中文色彩名（用于风格命名）
 * 返回 null 表示颜色不具备命名价值
 */
function colorToChineseName(hex) {
  if (!hex || !hex.startsWith('#') || hex.length < 7) return null;
  const { h, s, l } = hexToHsl(hex);
  if (l > 0.90) return null;
  if (l < 0.12) return '深色';
  if (s < 0.12) {
    if (l < 0.45) return '深灰';
    return null;
  }
  if (h < 20 || h >= 345) return '中国红';
  if (h < 45) return '橙色';
  if (h < 65) return '金色';
  if (h < 155) return '清新绿';
  if (h < 195) return '青色';
  if (h < 255) return '科技蓝';
  if (h < 285) return '深蓝';
  if (h < 345) return '紫色';
  return null;
}

function isNonFatalReusableAssetReviewError(error) {
  if (!error) return true;
  if (error instanceof TypeError || error instanceof SyntaxError) return false;
  if (error.code === 'MODULE_NOT_FOUND') return false;

  const text = `${error.name || ''} ${error.code || ''} ${error.message || error}`.toLowerCase();
  if (/\b(typeerror|syntaxerror|referenceerror)\b/.test(text)) return false;
  if (/module_not_found|cannot find module/.test(text)) return false;

  return /vlm|api|network|timeout|parse|json|image limit|rate limit|connection|fetch|request|response|provider|model/.test(text);
}

function normalizeHex(hex) {
  const text = String(hex || '').trim().toUpperCase();
  return /^#[0-9A-F]{6}$/.test(text) ? text : '';
}

function colorStats(hex) {
  const normalized = normalizeHex(hex);
  if (!normalized) return { h: 0, s: 0, l: 0 };
  const r = parseInt(normalized.slice(1, 3), 16) / 255;
  const g = parseInt(normalized.slice(3, 5), 16) / 255;
  const b = parseInt(normalized.slice(5, 7), 16) / 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;
  let h = 0;
  let s = 0;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    if (max === r) h = (g - b) / d + (g < b ? 6 : 0);
    else if (max === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    h *= 60;
  }
  return { h, s, l };
}

function isNeutralNamingColor(hex) {
  const { s, l } = colorStats(hex);
  return s < 0.12 || l < 0.08 || l > 0.94;
}

function hasBackgroundImages(imageMapData = {}) {
  if (imageMapData.bg_images && Object.keys(imageMapData.bg_images).length > 0) return true;
  const roles = imageMapData.asset_roles || {};
  return Array.isArray(roles.background) && roles.background.length > 0;
}

function buildNamingHint(structureData = {}, context = {}) {
  const actualColors = structureData.actual_colors || {};
  const bgTextMap = structureData.bg_text_mapping || {};
  const themeColors = structureData.colors || {};
  const slideCount = structureData.slide_count || 0;
  const imageBacked = hasBackgroundImages(context.imageMapData || {});

  const fillColors = Object.entries(actualColors)
    .filter(([, info]) => (info.fill_count || 0) > 0)
    .sort((a, b) => {
      const wA = a[1].area_weight || 0;
      const wB = b[1].area_weight || 0;
      if (Math.abs(wA - wB) > 0.001) return wB - wA;
      return (b[1].fill_count || 0) - (a[1].fill_count || 0);
    })
    .slice(0, 6)
    .map(([hex, info], index) => {
      const normalized = normalizeHex(hex) || hex;
      const usages = info.usages || [];
      const isBg = usages.some(u => String(u).includes('background'));
      const avg = info.area_weight > 0 && slideCount > 0
        ? Math.round((info.area_weight / slideCount) * 100)
        : 0;
      return {
        hex: normalized,
        name: colorToChineseName(normalized) || '其他色',
        fill_count: info.fill_count || 0,
        text_count: info.text_count || 0,
        area_weight: info.area_weight || 0,
        avg_slide_coverage_pct: avg,
        role: isBg ? 'background' : index === 0 ? 'primary' : 'accent',
        usages,
        naming_value: !isNeutralNamingColor(normalized),
      };
    });

  const bgTop = Object.entries(bgTextMap)
    .sort((a, b) => (b[1].slide_count || 0) - (a[1].slide_count || 0))[0];
  const background = bgTop
    ? {
        type: 'solid',
        hex: normalizeHex(bgTop[0]) || bgTop[0],
        name: colorToChineseName(bgTop[0]) || '未知',
        slide_count: bgTop[1].slide_count || 0,
      }
    : {
        type: imageBacked ? 'image_or_unresolved' : 'unresolved',
        hex: '',
        name: imageBacked ? '图片背景或未解析背景' : '未解析背景',
        slide_count: 0,
      };

  let bgTone = '';
  let colorTone = '';
  if (background.hex) {
    const { l } = colorStats(background.hex);
    bgTone = l < 0.40 ? '暗底' : '亮底';
  }
  const topNamingFill = fillColors.find(item => item.naming_value) || fillColors[0];
  if (topNamingFill) {
    const { h, s } = colorStats(topNamingFill.hex);
    if (s > 0.2) {
      colorTone = (h < 60 || h > 300) ? '暖色' : (h > 180 && h < 270) ? '冷色' : '';
    }
  }

  const reasons = [];
  const hasStructuredColors = Object.keys(actualColors).length > 0
    || Object.keys(bgTextMap).length > 0
    || Object.keys(themeColors).length > 0;
  const hasFill = fillColors.length > 0;
  const hasNamingFill = fillColors.some(item => item.naming_value);
  const hasTextOnlyColors = Object.values(actualColors).some(info => (info.text_count || 0) > 0)
    && !hasFill;

  let status = 'clear';
  if (!hasStructuredColors && !imageBacked) {
    status = 'missing';
    reasons.push('结构化配色数据为空');
  } else {
    if (!hasFill) reasons.push('未解析到可用填充色');
    if (hasFill && !hasNamingFill) reasons.push('填充色主要为黑白灰或低饱和中性色');
    if (!bgTop) {
      reasons.push(imageBacked
        ? '未解析到纯色背景，但检测到背景图元数据'
        : '未解析到纯色背景');
    }
    if (hasTextOnlyColors) reasons.push('颜色主要来自文字色，缺少视觉主色填充');
    if (reasons.length > 0) status = 'weak';
  }

  return {
    schema_version: 'ppt-template-naming-hint-v1',
    status,
    reasons,
    source: {
      file_name: context.fileName || structureData.file || '',
      temporary_dir: context.temporaryDir || structureData.temp_dir || '',
    },
    colors: {
      fill_colors: fillColors,
      background,
      tone: [bgTone, colorTone].filter(Boolean).join(' ') || '中性',
    },
    fallback_context: {
      slide_count: slideCount,
      slide_roles: structureData.slide_roles || [],
      has_background_images: imageBacked,
    },
    artifact_path: context.namingHintJsonPath || '',
  };
}

function formatNamingHint(hint) {
  const lines = [
    '',
    '=== NAMING_HINT ===',
    `文件名: ${hint.source.file_name}`,
    `临时目录: ${hint.source.temporary_dir}`,
    `命名线索状态: ${hint.status}`,
  ];
  if (hint.reasons.length) {
    lines.push('原因:');
    hint.reasons.forEach(reason => lines.push(`  - ${reason}`));
  }
  lines.push('主要配色（按使用频率）:');
  if (hint.colors.fill_colors.length) {
    hint.colors.fill_colors.forEach((item, index) => {
      const avg = item.avg_slide_coverage_pct > 0 ? ` 单页均覆${item.avg_slide_coverage_pct}%` : '';
      const role = item.role === 'background' ? '[背景]' : item.role === 'primary' ? '[主色]' : '[点缀]';
      lines.push(`  ${index + 1}. ${item.name}(${item.hex}) × ${item.fill_count}次填充${avg} ${role}`);
    });
  } else {
    lines.push('  （无明确填充色）');
  }
  const bg = hint.colors.background;
  if (bg.type === 'solid') {
    lines.push(`背景色: ${bg.name}(${bg.hex}) × ${bg.slide_count}张`);
  } else {
    lines.push(`背景色: ${bg.name}`);
  }
  lines.push(`整体色调: ${hint.colors.tone}`);
  if (hint.artifact_path) lines.push(`结构化命名线索: ${hint.artifact_path}`);
  lines.push('===================');
  return lines.join('\n');
}

function printNamingHint(hint, options = {}) {
  const text = formatNamingHint(hint);
  if (options.write !== false) console.log(text);
  return text;
}

function writeNamingHintJson(filePath, hint) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(hint, null, 2), 'utf-8');
}

function selectInitialStyleName({ pptxPath, explicitName }) {
  return explicitName || path.basename(pptxPath, '.pptx');
}

/**
 * 解析最终风格目录（处理重名冲突）
 * 规则：中国风 → 中国风_01 → 中国风_02 ...
 */
function resolveStyleDir(styleName, hubDir) {
  if (!fs.existsSync(hubDir)) {
    fs.mkdirSync(hubDir, { recursive: true });
  }

  const basePath = path.join(hubDir, styleName);
  if (!fs.existsSync(basePath)) {
    return { dirName: styleName, dirPath: basePath };
  }

  let idx = 1;
  while (true) {
    const candidate = `${styleName}_${String(idx).padStart(2, '0')}`;
    const candidatePath = path.join(hubDir, candidate);
    if (!fs.existsSync(candidatePath)) {
      return { dirName: candidate, dirPath: candidatePath };
    }
    idx++;
  }
}

/**
 * 主流程
 */
async function main(options) {
  const {
    pptxPath,
    skipVlm = false,
    strictVlm = false,
    skipConvert = false,
    config: customConfigPath = null,
  } = options;

  const effectiveHubDir = options.outputDir
    ? path.resolve(options.outputDir)
    : DEFAULT_HUB_DIR;
  let effectiveSkipVlm = skipVlm;
  let vlmFallbackReason = null;

  // 验证输入文件
  if (!fs.existsSync(pptxPath)) {
    throw new Error(`PPTX 文件不存在: ${pptxPath}`);
  }

  // VLM + --skip-convert 组合检查
  if (!effectiveSkipVlm && skipConvert) {
    const availability = resolveVlmAvailability({
      skipVlm: effectiveSkipVlm,
      strictVlm,
      vlmApiOk: false,
      failureReason: 'VLM 视觉分析需要幻灯片截图，但 --skip-convert 已启用',
    });
    effectiveSkipVlm = availability.skipVlm;
    vlmFallbackReason = availability.fallbackReason;
    if (vlmFallbackReason) {
      console.warn(`VLM_UNAVAILABLE_FALLBACK: ${vlmFallbackReason}，已自动降级为工具提取模式。`);
    }
  }

  // 运行时依赖检测（Node.js、Python、python-pptx）
  const runtimeDeps = checkRuntimeDeps();

  // 图片转换依赖检测（仅在启用转换或VLM时才检测，避免无谓的Python子进程调用）
  let imageDeps = { spire: false };
  const imageChecked = !skipConvert || !effectiveSkipVlm;
  if (imageChecked) {
    const { checkDependencies } = require('./convert_to_images.js');
    imageDeps = checkDependencies();
  }

  // 统一输出环境报告
  printEnvReport(runtimeDeps, imageDeps, imageChecked);

  // 关键依赖缺失时抛出错误
  if (!runtimeDeps.nodejs.ok) {
    throw new Error(`Node.js 版本不满足: ${runtimeDeps.nodejs.detail}，需要 ≥18`);
  }
  if (!runtimeDeps.python.ok) {
    throw new Error(
      'Python 不可用，结构提取步骤无法执行。\n' +
      '请安装 Python 3.8+ 或在 skills/ppt-template-generate/.venv 下创建虚拟环境。'
    );
  }
  if (!runtimeDeps.python_pptx.ok) {
    throw new Error(
      'python-pptx 未安装，结构提取将严重缺失（颜色/字号/版式等无法提取）。\n' +
      `请执行: "${runtimeDeps.python.cmd}" -m pip install python-pptx`
    );
  }

  // 图片转换依赖校验（仅在启用转换时）
  if (!skipConvert) {
    if (!imageDeps.spire) {
      throw new Error(
        'Spire.Presentation.Free 未安装，PPT 转图片无法执行。\n' +
        '请执行: pip install spire.presentation.free'
      );
    }
  }

  if (!effectiveSkipVlm) {
    const { testConnection } = require('./vlm-analyzer.js');
    const vlmConfigPath = customConfigPath || path.join(SKILL_DIR, 'vlm-config.json');
    let vlmApiOk = false;
    let failureReason = 'VLM API 未配置或不可用（请检查 vlm-config.json 中的 API 密钥）';
    try {
      vlmApiOk = await testConnection(vlmConfigPath);
    } catch (e) {
      failureReason = e?.message || failureReason;
    }
    const availability = resolveVlmAvailability({
      skipVlm: effectiveSkipVlm,
      strictVlm,
      vlmApiOk,
      failureReason,
    });
    effectiveSkipVlm = availability.skipVlm;
    vlmFallbackReason = availability.fallbackReason;
    if (vlmFallbackReason) {
      console.warn(`VLM_UNAVAILABLE_FALLBACK: ${vlmFallbackReason}，已自动降级为工具提取模式。`);
    }
  }

  // 生成时间戳（用于临时工作目录，避免并行任务冲突）
  const timestamp = generateTimestamp();

  // 创建临时工作目录（以 .tmp_ 开头，稍后重命名为风格名）
  const tmpWorkDir = path.join(effectiveHubDir, `.tmp_${timestamp}`);
  const tempDir = path.join(tmpWorkDir, 'temp');
  if (!fs.existsSync(tempDir)) {
    fs.mkdirSync(tempDir, { recursive: true });
  }

  const structurePath = path.join(tempDir, 'template_data.json');
  const imagesDir = path.join(tmpWorkDir, 'images');
  const slidesDir = path.join(tmpWorkDir, 'slides');
  const configPath = customConfigPath || path.join(SKILL_DIR, 'vlm-config.json');

  const totalSteps = effectiveSkipVlm ? 3 : 4;

  console.log('========================================');
  console.log('PPT 模板规范生成');
  console.log('========================================');
  console.log(`输入文件: ${pptxPath}`);
  const maxSlidesLabel = options.maxSlides > 0 ? `最多 ${options.maxSlides} 张` : '全部';
  console.log(`PPT 转图片: ${skipConvert ? '跳过' : `启用（${maxSlidesLabel}）`}`);
  console.log(`VLM 视觉分析: ${effectiveSkipVlm ? '跳过' : '启用'}`);
  if (vlmFallbackReason) {
    console.log(`VLM 降级原因: ${vlmFallbackReason}`);
  }
  console.log('');

  // Step 1: 结构提取
  console.log(`[Step 1/${totalSteps}] 结构提取`);
  const structureOk = extractStructure(pptxPath, structurePath);
  if (!structureOk) {
    console.warn('结构提取失败，使用空数据继续');
  }

  // Step 1.5: 图片资产提取
  console.log(`\n[图片提取] 提取所有幻灯片图片资产...`);
  extractImages(pptxPath, imagesDir);

  // Step 2: PPT 拆分 + 转图片
  console.log(`\n[Step 2/${totalSteps}] PPT 转图片`);
  let slideImages = [];
  if (!skipConvert) {
    const singlePptDir = path.join(tempDir, 'single_ppt');

    // Step 2a: 拆分为单页文件
    console.log('[Step 2a] 拆分 PPTX 为单页文件...');
    const splitCount = splitPptx(pptxPath, singlePptDir, { maxSlides: options.maxSlides ?? 10 });

    // Step 2b: 逐个转换为图片
    console.log('[Step 2b] 逐页转换图片...');
    slideImages = await pptxDirToImages(singlePptDir, slidesDir);
    if (slideImages.length === 0) {
      throw new Error('PPT 转图片失败，未生成任何幻灯片图片');
    }
    console.log(`已生成 ${slideImages.length}/${splitCount} 张幻灯片图片`);
  } else {
    console.log('已跳过 PPT 转图片');
  }

  // Step 3: VLM 分析（默认启用，可用 --skip-vlm 跳过）
  let vlmResultPath = null;

  if (!effectiveSkipVlm) {
    console.log(`\n[Step 3/${totalSteps}] VLM 视觉分析`);
    vlmResultPath = path.join(tempDir, 'vlm_analysis.json');
    try {
      const vlmResult = await runVLMAnalysis(slidesDir, configPath);
      fs.writeFileSync(vlmResultPath, JSON.stringify(vlmResult, null, 2), 'utf-8');
      console.log('VLM 分析完成');
    } catch (error) {
      if (strictVlm) {
        throw new Error(
          'VLM_DEPENDENCY_MISSING\n' +
          `原因: ${error?.message || 'VLM 分析失败'}`
        );
      }
      vlmFallbackReason = error?.message || 'VLM 分析失败';
      effectiveSkipVlm = true;
      vlmResultPath = null;
      console.warn(`VLM_UNAVAILABLE_FALLBACK: ${vlmFallbackReason}，已自动降级为工具提取模式。`);
    }
  } else {
    console.log(`\n[Step 3/${totalSteps}] VLM 视觉分析（已跳过）`);
  }

  // 确定初始目录名称：用户指定则直接使用；否则以文件名作为临时目录名，
  // agent 在读取 NAMING_HINT 后负责重命名。VLM 只增强模板内容，不参与命名。
  let finalStyleName = selectInitialStyleName({
    pptxPath,
    explicitName: options.name || null,
  });
  if (!options.name) {
    console.log(`临时目录名（待 agent 重命名）: ${finalStyleName}`);
  }

  // 解析最终输出目录，处理重名冲突（中国风 → 中国风_01 → 中国风_02）
  const { dirName: finalDirName, dirPath: finalTaskDir } = resolveStyleDir(finalStyleName, effectiveHubDir);
  if (finalDirName !== finalStyleName) {
    console.log(`风格名 "${finalStyleName}" 已存在，使用目录名: ${finalDirName}`);
    finalStyleName = finalDirName;
  }

  // 将临时工作目录重命名为最终目录
  fs.renameSync(tmpWorkDir, finalTaskDir);

  // 更新路径（基于重命名后的目录）
  const finalTempDir = path.join(finalTaskDir, 'temp');
  const finalStructurePath = path.join(finalTempDir, 'template_data.json');
  const finalVlmResultPath = path.join(finalTempDir, 'vlm_analysis.json');
  const finalQualityReportPath = path.join(finalTempDir, 'quality_report.json');
  const finalSlidesDir = path.join(finalTaskDir, 'slides');
  const finalReusableStyleAssetsPath = path.join(finalTempDir, 'reusable-style-assets.json');

  const toSafeName = (name) => name
    .replace(/\s+/g, '-')
    .replace(/[^a-zA-Z0-9\u4e00-\u9fa5_\-]/g, '');

  const outputFileName = `${toSafeName(finalStyleName)}.md`;
  const outputPath = path.join(finalTaskDir, outputFileName);
  const templateSpecPath = path.join(finalTaskDir, 'template-spec.json');

  console.log(`任务目录: ${finalTaskDir}`);
  console.log(`输出文件: ${outputFileName}`);
  console.log(`风格名称: ${finalStyleName}`);
  console.log('');

  // Step 最后: 聚合生成
  console.log(`\n[Step ${totalSteps}/${totalSteps}] 聚合生成`);
  const imageMapPath = path.join(finalTaskDir, 'images', 'image-map.json');
  if (!effectiveSkipVlm && fs.existsSync(finalVlmResultPath)) {
    const { reviewReusableStyleAssets } = require('./review-reusable-style-assets.js');
    console.log('[Reusable Style Assets] Starting VLM page-context review...');
    try {
      await reviewReusableStyleAssets(finalTaskDir, configPath, {
        outputPath: finalReusableStyleAssetsPath,
        maxAssetsPerBatch: 5,
      });
      console.log(`[Reusable Style Assets] Wrote ${finalReusableStyleAssetsPath}`);
    } catch (error) {
      if (!isNonFatalReusableAssetReviewError(error)) {
        throw error;
      }
      console.warn(`[Reusable Style Assets] Skipped: ${error.message}`);
    }
  }
  const aggregateOk = aggregate(finalStructurePath, outputPath, {
    name: finalStyleName,
    vlmPath: !effectiveSkipVlm && fs.existsSync(finalVlmResultPath) ? finalVlmResultPath : null,
    imageMapPath: fs.existsSync(imageMapPath) ? imageMapPath : null,
    reusableStyleAssetsPath: fs.existsSync(finalReusableStyleAssetsPath) ? finalReusableStyleAssetsPath : null,
    timestamp: timestamp,
    specPath: templateSpecPath,
  });
  if (!aggregateOk) {
    throw new Error('聚合生成失败');
  }

  const decorationMapPath = path.join(finalTempDir, 'decoration-map.json');
  if (!effectiveSkipVlm && fs.existsSync(finalVlmResultPath) && !fs.existsSync(decorationMapPath)) {
    console.log('\n[HTML 模板装饰] 未发现 temp/decoration-map.json，本次生成无装饰最小骨架。');
    console.log('如需注入 VLM 确认后的装饰层，请先完成 Stage 5.5 写入 decoration-map.json，再运行:');
    console.log(`node skills/ppt-template-generate/scripts/generate-html-templates.js "${finalTaskDir}"`);
  }
  const htmlTemplateResult = generateHtmlTemplateSkeletons(templateSpecPath, finalTaskDir);

  const { writeQualityReport } = require('./quality-report.js');
  const structureData = fs.existsSync(finalStructurePath)
    ? JSON.parse(fs.readFileSync(finalStructurePath, 'utf-8'))
    : {};
  const vlmAnalysis = !effectiveSkipVlm && finalVlmResultPath && fs.existsSync(finalVlmResultPath)
    ? JSON.parse(fs.readFileSync(finalVlmResultPath, 'utf-8'))
    : {};
  const reusableStyleAssets = fs.existsSync(finalReusableStyleAssetsPath)
    ? JSON.parse(fs.readFileSync(finalReusableStyleAssetsPath, 'utf-8'))
    : {};
  writeQualityReport(finalQualityReportPath, {
    skipVlm: effectiveSkipVlm,
    styleName: finalStyleName,
    vlmFallbackReason,
    structureData,
    vlmAnalysis,
    reusableStyleAssets,
  });

  // 未指定名称时始终输出配色分析，供 agent 自主命名并重命名目录。
  if (!options.name) {
    const namingHintPath = path.join(finalTempDir, 'naming-hint.json');
    const imageMapData = fs.existsSync(imageMapPath)
      ? JSON.parse(fs.readFileSync(imageMapPath, 'utf-8'))
      : {};
    const hint = buildNamingHint(structureData, {
      fileName: path.basename(pptxPath, '.pptx'),
      temporaryDir: finalTaskDir,
      namingHintJsonPath: namingHintPath,
      imageMapData,
    });
    writeNamingHintJson(namingHintPath, hint);
    printNamingHint(hint);
  }

  console.log('\n========================================');
  console.log('生成完成!');
  console.log(`输出文件: ${outputPath}`);
  console.log(`机器可读模板规范: ${templateSpecPath}`);
  if (slideImages.length > 0) console.log(`幻灯片图片目录: ${finalSlidesDir}`);
  console.log(`质量诊断报告: ${finalQualityReportPath}`);
  console.log('========================================');

  const imageMapMdPath = path.join(finalTaskDir, 'images', 'image-map.md');
  const hasImageMap = fs.existsSync(imageMapPath);

  if (hasImageMap) {
    console.log(`图片资产地图: ${imageMapPath}`);
  }

  // 保留 temp 目录，便于复查 template_data.json 与 vlm_analysis.json。
  // 这些文件不包含 API Key，可用于定位 VLM 是否按增强结构返回了固定构图等字段。

  return {
    timestamp,
    outputPath,
    taskDir: finalTaskDir,
    slidesDir: slideImages.length > 0 ? finalSlidesDir : null,
    imageMapPath: hasImageMap ? imageMapPath : null,
    imageMapMdPath: hasImageMap ? imageMapMdPath : null,
    reusableStyleAssetsPath: fs.existsSync(finalReusableStyleAssetsPath) ? finalReusableStyleAssetsPath : null,
    templateSpecPath,
    templateManifestPath: htmlTemplateResult.manifestPath,
    decorationMapPath: fs.existsSync(decorationMapPath) ? decorationMapPath : null,
  };
}

// CLI 入口
function parseCliOptions(args) {
  const pptxPath = args[0];

  const options = {
    pptxPath,
    skipVlm: false,
    strictVlm: false,
    skipConvert: false,
    config: null,
    maxSlides: 10,
    outputDir: null,
  };

  for (const arg of args.slice(1)) {
    if (arg.startsWith('--')) {
      const eqIdx = arg.indexOf('=');
      const key = eqIdx >= 0 ? arg.slice(2, eqIdx) : arg.slice(2);
      const value = eqIdx >= 0 ? arg.slice(eqIdx + 1) : undefined;
      if (key === 'skip-vlm') {
        options.skipVlm = true;
      } else if (key === 'enable-vlm') {
        options.skipVlm = false;
      } else if (key === 'strict-vlm') {
        options.strictVlm = true;
      } else if (key === 'skip-convert') {
        options.skipConvert = true;
      } else if (key === 'config') {
        options.config = value;
      } else if (key === 'max-slides') {
        options.maxSlides = parseInt(value, 10) || 10;
      } else if (key === 'output-dir') {
        options.outputDir = value;
      } else {
        options[key] = value;
      }
    }
  }

  return options;
}

async function cli() {
  const args = process.argv.slice(2);

  if (args.length === 0 || args[0] === '--help') {
    console.log(`
用法: node index.js <pptx文件> [选项]

选项:
  --name=<名称>         风格名称 (默认: 以原始文件名为临时目录名，由 agent 根据 NAMING_HINT 重命名)
  --output-dir=<路径>   输出根目录 (默认: ppt-template-hub)
  --skip-convert        跳过 PPT 转图片
  --max-slides=<n>      最多转换页数（默认: 10；0 = 全部）
  --skip-vlm            跳过 VLM 视觉分析
  --enable-vlm          启用 VLM 视觉分析 (兼容旧用法；当前默认已启用)
  --strict-vlm          VLM 不可用时直接失败（默认自动降级为工具提取模式）
  --config=<路径>       VLM 配置文件路径 (默认: ./vlm-config.json)
  --test-vlm            测试 VLM API 连接

注意: PPT 转图片默认启用（最多 10 张）。VLM 分析默认启用；若 API 未配置或不可用会自动降级，传入 --strict-vlm 可恢复失败即停。

输出:
  任务目录: {output-dir}/{风格名}/
  风格文件: {output-dir}/{风格名}/{风格名}.md

示例:
  node index.js presentation.pptx --name="企业蓝"
  node index.js --test-vlm                                    # 测试 API 连接
`);
    process.exit(0);
  }

  // 检查测试模式
  if (args.includes('--test-vlm')) {
    const configPath = args.find(a => a.startsWith('--config='))?.slice('--config='.length)
      || path.join(SKILL_DIR, 'vlm-config.json');
    const { testConnection } = require('./vlm-analyzer.js');
    await testConnection(configPath);
    process.exit(0);
  }

  const options = parseCliOptions(args);

  try {
    const result = await main(options);
    console.log(`\n输出文件路径: ${result.outputPath}`);
  } catch (error) {
    console.error(`错误: ${error.message}`);
    process.exit(1);
  }
}

// 导出
module.exports = {
  main,
  parseCliOptions,
  resolveVlmAvailability,
  selectInitialStyleName,
  normalizeHex,
  colorStats,
  isNeutralNamingColor,
  hasBackgroundImages,
  buildNamingHint,
  printNamingHint,
  writeNamingHintJson,
  extractStructure,
  convertToImages,
  aggregate,
};

if (require.main === module) {
  cli();
}
