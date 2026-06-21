#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const { toPosix } = require('./lib/utils.js');

const DEFAULT_WIDTH = 1280;
const DEFAULT_HEIGHT = 720;
const BASE_PAGE_ROLES = ['cover', 'section', 'content', 'closing'];

function ensureDir(dir) { fs.mkdirSync(dir, { recursive: true }); }

function clearGeneratedHtmlTemplates(templatesDir) {
  if (!fs.existsSync(templatesDir)) return;
  for (const entry of fs.readdirSync(templatesDir, { withFileTypes: true })) {
    if (entry.isFile() && entry.name.toLowerCase().endsWith('.html')) {
      fs.unlinkSync(path.join(templatesDir, entry.name));
    }
  }
}

function cssEscape(value) { return String(value || '').replace(/\\/g, '\\\\').replace(/"/g, '\\"'); }

function htmlEscape(value) {
  return String(value || '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function normalizeHex(value, fallback) {
  const text = String(value || '').trim();
  return /^#[0-9a-fA-F]{6}$/.test(text) ? text.toUpperCase() : fallback;
}

function normalizeBgImagePath(value) {
  const itemPath = toPosix(value || '').replace(/^\.?\//, '');
  if (/^images\/bg_images\//i.test(itemPath)) return itemPath;
  if (/^bg_images\//i.test(itemPath)) return `images/${itemPath}`;
  return '';
}

function normalizeAssetImagePath(value) {
  const p = toPosix(value || '').replace(/^\.?\//, '');
  return /^images\/assets\//i.test(p) && !/\.\./.test(p) ? p : '';
}

function safeNum(v) { const n = Number(v); return Number.isFinite(n) ? n : null; }

function fontFromSpec(spec) { return spec?.fonts?.body || spec?.fonts?.title || 'Noto Sans SC'; }
function titleFontFromSpec(spec) { return spec?.fonts?.title || spec?.fonts?.body || 'Noto Sans SC'; }

function pxToPt(px) {
  const value = Number(px);
  return Number.isFinite(value) && value > 0 ? Math.round(value * 0.75 * 10) / 10 : null;
}

function executionTypographyScale(spec) {
  if (Array.isArray(spec?.execution_font_scale) && spec.execution_font_scale.length > 0) return spec.execution_font_scale;
  if (Array.isArray(spec?.execution_tokens?.typography_scale) && spec.execution_tokens.typography_scale.length > 0) return spec.execution_tokens.typography_scale;
  return [];
}

function executionRoleForFontSize(role) {
  if (role.includes('title')) return ['page_title'];
  if (role.includes('body')) return ['body_text', 'subsection_text'];
  if (role.includes('note')) return ['note_text'];
  return [];
}

function executionFontSizePt(spec, role) {
  const roles = executionRoleForFontSize(role);
  const scale = executionTypographyScale(spec);
  for (const name of roles) {
    const item = scale.find(entry => entry.role === name);
    const value = pxToPt(item?.px);
    if (value != null) return value;
  }
  return null;
}

function fontSize(spec, role, fallback) {
  const executionSize = executionFontSizePt(spec, role);
  if (executionSize != null) return executionSize;

  const tokens = spec?.typography_tokens;
  if (tokens) {
    if (role.includes('title')) { const v = Number(tokens.heading_pt); if (Number.isFinite(v) && v > 0) return Math.min(Math.max(v, 14), 72); }
    else if (role.includes('body')) { const v = Number(tokens.body_pt); if (Number.isFinite(v) && v > 0) return Math.min(Math.max(v, 14), 72); }
    else if (role.includes('note')) { const v = Number(tokens.note_pt); if (Number.isFinite(v) && v > 0) return Math.min(Math.max(v, 6), 20); }
  }
  const scale = Array.isArray(spec?.font_scale) ? spec.font_scale : [];
  const item = scale.find(entry => String(entry.role || '').toLowerCase().includes(role));
  const size = Number(item?.dominant_pt);
  return Number.isFinite(size) && size > 0 ? Math.min(Math.max(size, 6), 72) : fallback;
}

function pickBackgroundAsset(spec) {
  const assets = Array.isArray(spec?.visual_assets) ? spec.visual_assets : [];
  const asset = assets.find(item => {
    const role = String(item?.role || '').toLowerCase();
    const itemPath = normalizeBgImagePath(item?.path || '');
    return role === 'background' && itemPath;
  });
  return asset ? normalizeBgImagePath(asset.path || '') : '';
}

function fileBytesEqual(leftPath, rightPath) {
  try {
    if (!fs.existsSync(leftPath) || !fs.existsSync(rightPath)) return false;
    const left = fs.readFileSync(leftPath);
    const right = fs.readFileSync(rightPath);
    return left.length === right.length && left.equals(right);
  } catch {
    return false;
  }
}

function isDuplicateBackgroundAsset(outputDir, backgroundAsset, candidateAssetPath) {
  if (!backgroundAsset || !candidateAssetPath) return false;
  if (backgroundAsset === candidateAssetPath) return true;
  const bgPath = path.join(outputDir, ...backgroundAsset.split('/'));
  const candidatePath = path.join(outputDir, ...candidateAssetPath.split('/'));
  return fileBytesEqual(bgPath, candidatePath);
}

// decoration-map.json 是 Stage 5.5 由 Agent 手动写入的产物，首次生成时不存在属正常情况
function loadDecorationMap(outputDir) {
  const p = path.join(outputDir, 'temp', 'decoration-map.json');
  if (!fs.existsSync(p)) return null;
  try { return JSON.parse(fs.readFileSync(p, 'utf-8')); } catch { return null; }
}

function isSafeDecorationId(id) { return /^[a-z][a-z0-9-]*$/.test(String(id || '')); }

function isSafeDecorationCss(css) {
  const text = String(css || '');
  // Count braces to prevent CSS structure injection
  const opens = (text.match(/\{/g) || []).length;
  const closes = (text.match(/\}/g) || []).length;
  return /position\s*:\s*absolute\b/i.test(text) &&
    !/#[0-9a-fA-F]{3,8}\b/.test(text) &&
    !/url\s*\(/i.test(text) &&
    !/<\/?style\b/i.test(text) &&
    opens === closes; // balanced braces required
}

function isSafeDecorationHtml(html) {
  const text = String(html || '');
  return text &&
    !/<script\b/i.test(text) &&
    !/\son[a-z]+\s*=/i.test(text) &&
    !/slides\//i.test(text) &&
    !/images\/assets\//i.test(text) &&
    !/\bsrc\s*=/i.test(text); // ban all src attributes — decoration HTML should not load external resources
}

function validateDecorationMap(rawMap) {
  if (!rawMap || rawMap.schema_version !== 'decoration-map-v1') return null;
  const decorations = Array.isArray(rawMap.decorations) ? rawMap.decorations : [];
  const safeDecorations = decorations
    .filter(item => isSafeDecorationId(item?.id) && isSafeDecorationCss(item?.css) && isSafeDecorationHtml(item?.html))
    .map(item => ({ id: item.id, css: String(item.css || '').trim(), html: String(item.html || '').trim(), source_description: String(item.source_description || '') }));
  const safeIds = new Set(safeDecorations.map(item => item.id));
  const pageRoleMap = {};
  for (const role of BASE_PAGE_ROLES) {
    pageRoleMap[role] = Array.isArray(rawMap.page_role_map?.[role])
      ? rawMap.page_role_map[role].filter(id => safeIds.has(id)) : [];
  }
  return { schema_version: 'decoration-map-v1', decorations: safeDecorations, page_role_map: pageRoleMap };
}


function renderDecorationsForRole(decorationMap, pageRole) {
  if (!decorationMap) return { css: '', html: '' };
  const ids = new Set(Array.isArray(decorationMap.page_role_map?.[pageRole]) ? decorationMap.page_role_map[pageRole] : []);
  const roleDecors = (decorationMap.decorations || []).filter(d => ids.has(d.id));
  return {
    css: roleDecors.map(d => String(d.css || '').trim()).filter(Boolean).join('\n    '),
    html: roleDecors.map(d => String(d.html || '').trim()).filter(Boolean).join('\n      '),
  };
}

function renderStyleAssetsForRole(spec, pageRole, backgroundAsset, outputDir) {
  const items = Array.isArray(spec.reusable_style_assets) ? spec.reusable_style_assets : [];
  return items
    .filter(a => {
      if (!a.html_policy?.inject) return false;
      if (backgroundAsset && a.path === backgroundAsset) return false;
      const assetPath = normalizeAssetImagePath(a.path || '');
      if (isDuplicateBackgroundAsset(outputDir, backgroundAsset, assetPath)) return false;
      const roles = Array.isArray(a.html_policy?.page_roles) ? a.html_policy.page_roles : [];
      return roles.includes(pageRole);
    })
    .map(a => {
      const assetPath = normalizeAssetImagePath(a.path);
      if (!assetPath) return ''; // skip invalid paths
      const cls = ['style-asset', a.html_policy?.css_class].filter(Boolean).join(' ');
      const p = a.placement || {};
      const left = safeNum(p.left_pct);
      const top = safeNum(p.top_pct);
      const width = safeNum(p.width_pct);
      const height = safeNum(p.height_pct);
      const styleParts = [
        'position:absolute',
        left != null ? `left:${left}%` : null,
        top != null ? `top:${top}%` : null,
        width != null ? `width:${width}%` : null,
        height != null ? `height:${height}%` : null,
      ].filter(Boolean).join(';');
      return `<img class="${htmlEscape(cls)}" src="${htmlEscape(`../${assetPath}`)}" alt=""${styleParts ? ` style="${styleParts}"` : ''} />`;
    })
    .filter(Boolean) // remove empty strings from skipped items
    .join('\n      ');
}

function renderBaseHtml({ spec, pageRole, backgroundAsset, decorationMap, outputDir }) {
  const width = Number(spec?.slide_size?.width_px) || DEFAULT_WIDTH;
  const height = Number(spec?.slide_size?.height_px) || DEFAULT_HEIGHT;
  const colors = spec?.colors || {};
  const primary = normalizeHex(colors.primary, '#C00000');
  const background = normalizeHex(colors.background, '#FFFFFF');
  const text = normalizeHex(colors.text, '#222222');
  const font = fontFromSpec(spec);
  const titleFont = titleFontFromSpec(spec);
  const titlePt = fontSize(spec, 'title', 30);
  const bodyPt = fontSize(spec, 'body', 18);
  const notePt = fontSize(spec, 'note', 11);
  // CSS spec: 1pt = 96/72px (96 DPI baseline, consistent with ppt-template-generate extraction)
  const titlePx = Math.round(titlePt * 4 / 3);
  const bodyPx = Math.round(bodyPt * 4 / 3);
  const notePx = Math.round(notePt * 4 / 3);

  const templateId = `${pageRole}-base`;
  const bgSrc = backgroundAsset ? `../${backgroundAsset}` : '';
  const bgImg = bgSrc ? `<img class="template-bg-image" src="${htmlEscape(bgSrc)}" alt="" />` : '';

  const { css: decorCss, html: decorHtml } = renderDecorationsForRole(decorationMap, pageRole);
  const styleAssetImgs = renderStyleAssetsForRole(spec, pageRole, backgroundAsset, outputDir);
  const assetsContent = [styleAssetImgs, decorHtml].filter(s => s.trim()).join('\n      ');

  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="template-id" content="${htmlEscape(templateId)}" />
  <meta name="page-role" content="${htmlEscape(pageRole)}" />
  <style>
    :root {
      --slide-width: ${width}px;
      --slide-height: ${height}px;
      --color-primary: ${primary};
      --color-background: ${background};
      --color-text: ${text};
      --font-title: "${cssEscape(titleFont)}";
      --font-body: "${cssEscape(font)}";
      --font-size-title: ${titlePt}pt;
      --font-size-title-px: ${titlePx}px;
      --font-size-body: ${bodyPt}pt;
      --font-size-body-px: ${bodyPx}px;
      --font-size-note: ${notePt}pt;
      --font-size-note-px: ${notePx}px;
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: #f3f4f6; }
    .slide {
      position: relative;
      width: var(--slide-width);
      height: var(--slide-height);
      overflow: hidden;
      background: var(--color-background);
      color: var(--color-text);
      font-family: var(--font-body), "Noto Sans SC", sans-serif;
    }
    .template-bg-image {
      position: absolute; inset: 0;
      width: 100%; height: 100%;
      object-fit: cover; z-index: 0;
    }
    .template-assets {
      position: absolute; inset: 0;
      z-index: 1; pointer-events: none;
    }
    ${decorCss}
  </style>
</head>
<body>
  <section class="slide" data-template-id="${htmlEscape(templateId)}" data-page-role="${htmlEscape(pageRole)}">
    ${bgImg}
    <div class="template-assets">
      ${assetsContent}
    </div>
  </section>
</body>
</html>
`;
}

function collectPageRoles(spec) {
  const roles = new Set(['cover', 'section', 'content']); // always include these three
  for (const item of spec?.fixed_composition || []) {
    const pageType = String(item?.page_type || '').toLowerCase();
    // toc/catalog/agenda pages use the section base layout
    if (/toc|catalog|agenda|目录/.test(pageType)) roles.add('section');
    if (/closing|ending|thanks|结束|致谢/.test(pageType)) roles.add('closing');
  }
  return [...roles].filter(r => BASE_PAGE_ROLES.includes(r));
}

function generateHtmlTemplates(spec, outputDir) {
  const targetDir = path.resolve(outputDir);
  const templatesDir = path.join(targetDir, 'html-templates');
  ensureDir(templatesDir);
  clearGeneratedHtmlTemplates(templatesDir);

  const backgroundAsset = pickBackgroundAsset(spec);
  const fileDecorationMap = validateDecorationMap(loadDecorationMap(targetDir));
  // reusable_style_assets with placement are rendered directly as <img> tags;
  // only file-based decoration-map is used for the decoration pipeline here.
  const decorationMap = fileDecorationMap;

  const pageRoles = collectPageRoles(spec);
  const bases = [];

  for (const pageRole of pageRoles) {
    const templateId = `${pageRole}-base`;
    const fileName = `${templateId}.html`;
    const html = renderBaseHtml({ spec, pageRole, backgroundAsset, decorationMap, outputDir });
    fs.writeFileSync(path.join(templatesDir, fileName), html, 'utf-8');
    bases.push({ page_role: pageRole, file: toPosix(path.join('html-templates', fileName)) });
  }

  const manifest = {
    schema_version: 'ppt-template-manifest-v2',
    mode: 'base',
    style_name: spec?.style_name || '',
    generated_at: new Date().toISOString(),
    bases,
  };
  fs.writeFileSync(path.join(targetDir, 'template-manifest.json'), JSON.stringify(manifest, null, 2), 'utf-8');
  return manifest;
}

function validateTemplatePackage(outputDir) {
  const errors = [];
  const targetDir = path.resolve(outputDir);
  const manifestPath = path.join(targetDir, 'template-manifest.json');
  if (!fs.existsSync(manifestPath)) return { ok: false, errors: ['template-manifest.json not found'], warnings: [] };
  let manifest;
  try { manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8')); }
  catch (e) { return { ok: false, errors: [`template-manifest.json parse error: ${e.message}`], warnings: [] }; }

  if (manifest.mode === 'base') {
    for (const base of manifest.bases || []) {
      const htmlPath = path.join(targetDir, String(base.file || ''));
      if (!fs.existsSync(htmlPath)) {
        errors.push(`base "${base.page_role}" HTML file not found: ${base.file}`);
        continue;
      }
      const html = fs.readFileSync(htmlPath, 'utf-8');
      const expectedId = `${base.page_role}-base`;
      if (!html.includes(`content="${expectedId}"`))
        errors.push(`${base.file}: missing <meta name="template-id" content="${expectedId}">`);
      if (!html.includes(`data-page-role="${base.page_role}"`))
        errors.push(`${base.file}: missing data-page-role="${base.page_role}"`);
      if (!html.includes('template-assets'))
        errors.push(`${base.file}: missing .template-assets div`);
      if (/images\/assets\//i.test(html)) {
        const stripped = html.replace(/<img\b[^>]*class="style-asset[^"]*"[^>]*>/gi, '');
        if (/images\/assets\//i.test(stripped))
          errors.push(`${base.file}: references images/assets/ outside style-asset img tag`);
      }
      if (/slides\//i.test(html)) errors.push(`${base.file}: references slides/ screenshot`);
      if (/file:\/\//i.test(html)) errors.push(`${base.file}: contains file:// URL`);
    }
  }
  return { ok: errors.length === 0, errors, warnings: [] };
}

if (require.main === module) {
  const outputDir = process.argv[2];
  if (!outputDir) { console.error('Usage: node generate-html-templates.js <outputDir>'); process.exit(1); }
  const specPath = path.join(outputDir, 'template-spec.json');
  if (!fs.existsSync(specPath)) { console.error(`template-spec.json not found in ${outputDir}`); process.exit(1); }
  const spec = JSON.parse(fs.readFileSync(specPath, 'utf-8'));
  const result = generateHtmlTemplates(spec, outputDir);
  console.log(`Base HTML regenerated: ${result.bases.length} base files written to ${outputDir}`);
}

module.exports = { generateHtmlTemplates, validateTemplatePackage };
