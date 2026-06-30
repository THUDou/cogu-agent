#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const {
  matchPresetStyle,
  buildPresetNormalization,
  resolveExecutionTypographyScale,
} = require('./preset-style-normalizer.js');

const COLOR_NAME_MAP = {
  dk1: '深色1（主文字色）', lt1: '浅色1（主背景色）',
  dk2: '深色2', lt2: '浅色2',
  accent1: '强调色1', accent2: '强调色2', accent3: '强调色3',
  accent4: '强调色4', accent5: '强调色5', accent6: '强调色6',
  hlink: '超链接色', folHlink: '已访问链接色'
};

const PLACEHOLDER_TYPE_MAP = {
  'TITLE (1)': '标题', 'BODY (2)': '正文', 'CENTER_TITLE (3)': '居中标题',
  'CENTER_BODY (4)': '居中正文', 'HEADER (5)': '页眉', 'FOOTER (6)': '页脚',
  'OBJECT (7)': '对象', 'CHART (8)': '图表', 'TABLE (9)': '表格',
  'PICTURE (12)': '图片', 'DATE (13)': '日期', 'SLIDE_NUMBER (14)': '页码'
};

const USAGE_LABEL = {
  title_fill: '标题区填充', title_text: '标题文字', title_border: '标题边框',
  title_fill_gradient: '标题区渐变填充', title_text_gradient: '标题文字渐变',
  body_fill: '正文区填充', body_text: '正文文字', body_border: '正文边框',
  body_fill_gradient: '正文区渐变填充', body_text_gradient: '正文文字渐变',
  center_title_fill: '居中标题填充', center_title_text: '居中标题文字',
  center_title_fill_gradient: '居中标题渐变填充', center_title_text_gradient: '居中标题文字渐变',
  slide_shape_fill: '幻灯片装饰形状填充', slide_shape_border: '幻灯片装饰形状边框',
  slide_shape_fill_gradient: '幻灯片装饰渐变填充', slide_shape_text_gradient: '幻灯片文字渐变',
  free_shape_fill: '自由形状填充', free_shape_border: '自由形状边框',
  free_shape_text: '自由形状文字',
  free_shape_fill_gradient: '自由形状渐变填充', free_shape_text_gradient: '自由形状文字渐变',
};


function extractVLMColorSemantics(analyses) {
  if (!analyses || !analyses.length) return {};
  let primary = '', secondary = '', textColor = '', accent = '', bg = '', style = '';
  for (const a of analyses) {
    const cs = a['配色方案'] || a.color_scheme || a.design_analysis?.color_scheme || {};
    primary     = primary     || cs['主色调'] || cs.primary_color || '';
    secondary   = secondary   || cs['辅助色'] || cs.secondary_color || '';
    textColor   = textColor   || cs['文字色'] || cs.text_color || '';
    accent      = accent      || cs['点缀色'] || cs['强调色'] || '';
    bg          = bg          || cs['背景色'] || '';
    style       = style       || cs['配色风格'] || cs['风格描述'] || cs.overall_style || '';
  }
  return { primary, secondary, textColor, accent, bg, style };
}

function extractVLMOverallStyle(analyses) {
  if (!analyses || !analyses.length) return '';
  for (const a of analyses) {
    const vs = a['视觉风格'] || a['整体风格'] || {};
    const desc = vs['整体风格'] || vs['风格定位'] || vs['一句话描述'] || a['overall_style'] || '';
    if (desc) return desc;
  }
  return '';
}

function collectVLMItems(analyses, field) {
  if (!analyses || !analyses.length) return [];
  const items = [];
  for (const a of analyses) {
    if (Array.isArray(a?.[field])) items.push(...a[field]);
  }
  return items;
}

function extractVLMOverlayPolicy(analyses) {
  if (!analyses || !analyses.length) return null;
  for (const a of analyses) {
    const op = a.overlay_policy;
    if (op && typeof op.present === 'boolean') {
      return {
        present: op.present,
        color: typeof op.color === 'string' ? op.color : null,
        description: typeof op.description === 'string' ? op.description : '',
      };
    }
  }
  return null;
}

function uniqueValues(values) {
  return [...new Set(values.filter(Boolean))];
}

function luminance(hex) {
  const h = String(hex || '').trim();
  if (!/^#[0-9a-fA-F]{6}$/.test(h)) return 0;
  const r = parseInt(h.slice(1, 3), 16) / 255;
  const g = parseInt(h.slice(3, 5), 16) / 255;
  const b = parseInt(h.slice(5, 7), 16) / 255;
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function selectColors(actualColors = {}, vlmBg = '') {
  const entries = Object.entries(actualColors);
  const allowed = entries.map(([hex]) => hex.toUpperCase());
  const fillEntries = entries
    .filter(([, info]) => (info.fill_count || 0) > 0)
    .sort((a, b) => (b[1].area_weight || 0) - (a[1].area_weight || 0));
  const textEntries = entries
    .filter(([, info]) => (info.text_count || 0) > 0)
    .sort((a, b) => (b[1].text_count || 0) - (a[1].text_count || 0));

  const validVlmBg = /^#[0-9a-fA-F]{6}$/.test(String(vlmBg || '').trim())
    ? vlmBg.trim().toUpperCase() : '';
  const lightFill = fillEntries.find(([hex]) => luminance(hex) > 0.85);

  const usedBg = validVlmBg || lightFill?.[0]?.toUpperCase() || '#FFFFFF';
  const allowedWithBg = validVlmBg && !allowed.includes(validVlmBg)
    ? [...allowed, validVlmBg]
    : allowed;

  return {
    primary: (fillEntries.find(([hex]) => luminance(hex) <= 0.85)?.[0] || fillEntries[0]?.[0] || '').toUpperCase(),
    background: usedBg,
    text: (textEntries[0]?.[0] || '').toUpperCase(),
    allowed: allowedWithBg,
  };
}

function buildLayoutLibrary(vlmLayouts, contentStyles) {
  if (vlmLayouts?.length) {
    return vlmLayouts.slice(0, 12).map((item, index) => ({
      id: `layout-${String(index + 1).padStart(2, '0')}`,
      source: 'vlm',
      name: item.layout_name || `版式 ${index + 1}`,
      page_role: item.page_role || 'unknown',
      semantic_type: item.semantic_type || 'unknown',
      content_scenario: item.content_scenario || item.reuse_rule || '',
      information_relation: item.information_relation || '',
      slot_structure: Array.isArray(item.slot_structure) ? item.slot_structure : String(item.slot_structure || '').split(/[；;,，]/).map(s => s.trim()).filter(Boolean),
      selection_rule: item.selection_rule || '',
      layout_points: [
        item.title_position ? `标题${item.title_position}` : '',
        item.body_structure,
        item.visual_structure,
        item.spacing_rules ? `间距：${item.spacing_rules}` : '',
      ].filter(Boolean),
      avoid_rules: Array.isArray(item.avoid_rules) ? item.avoid_rules : String(item.avoid_rules || '').split(/[；;,，]/).map(s => s.trim()).filter(Boolean),
    }));
  }

  return (contentStyles || []).slice(0, 8).map((style, index) => ({
    id: style.id || `layout-${String(index + 1).padStart(2, '0')}`,
    source: 'tool',
    name: style.name || `内容页样式 ${index + 1}`,
    page_role: 'content',
    semantic_type: style.semantic_type_guess || 'unknown',
    content_scenario: style.usage_rule || '',
    information_relation: style.information_relation || '',
    slot_structure: uniqueValues([
      ...(style.body_blocks || []).map(b => `正文:${b.region || '-'}`),
      ...(style.visual_blocks || []).map(v => `视觉:${v.region || '-'}`),
    ]),
    selection_rule: style.selection_rule || style.usage_rule || '',
    layout_points: [style.description].filter(Boolean),
    avoid_rules: [],
  }));
}

function buildVisualAssets(imageMapData = {}) {
  const roles = imageMapData.asset_roles || {};
  const imageMapItems = (roles.background || [])
    .filter(item => String(item.confidence || '').toLowerCase() === 'high');
  const fromImageMap = imageMapItems.map(item => ({
    source: 'image-map',
    path: (rawPath => rawPath.startsWith('images/') ? rawPath : `images/${rawPath}`)((item.path || item.saved_as || '').replace(/\\/g, '/')),
    role: item.role || 'unknown',
    policy: 'reuse_by_role',
    usage: formatRoleSources(item),
  }));

  const seen = new Set();
  const merged = [];
  for (const item of fromImageMap) {
    const key = `${item.source}|${item.path}|${item.role}|${String(item.usage).replace(/\s+/g, '')}`;
    if (seen.has(key)) continue;
    seen.add(key);
    merged.push(item);
    if (merged.length >= 30) break;
  }
  return merged;
}

function loadReusableStyleAssets(filePath) {
  if (!filePath || !fs.existsSync(filePath)) {
    return { schema_version: 'reusable-style-assets-v1', assets: [], rejected_assets: [] };
  }
  try {
    const parsed = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    return {
      schema_version: parsed.schema_version || 'reusable-style-assets-v1',
      assets: Array.isArray(parsed.assets) ? parsed.assets : [],
      rejected_assets: Array.isArray(parsed.rejected_assets) ? parsed.rejected_assets : [],
    };
  } catch {
    return { schema_version: 'reusable-style-assets-v1', assets: [], rejected_assets: [] };
  }
}

const ACCEPTED_REUSABLE_DECISIONS = new Set(['must_reuse_for_style', 'optional_style_asset']);
const ACCEPTED_REUSABLE_ROLES = new Set([
  'template_background',
  'background_texture',
  'template_decoration',
  'edge_decoration',
  'repeated_decoration',
]);
const PROCESS_REASON_PATTERN = /\b(?:VLM|prompt|batch|tool|analyzeWithVLM|vlm_batch_failed)\b/i;

function normalizeReusableAssetPath(value) {
  const raw = String(value || '');
  if (!raw || /^[a-zA-Z]:[\\/]/.test(raw) || raw.startsWith('/') || raw.startsWith('\\')) return '';
  if (/["'<>`\x00-\x1F\x7F]/.test(raw)) return '';

  const normalized = raw.replace(/\\/g, '/').replace(/^\.\//, '');
  if (/\/{2,}/.test(normalized)) return '';
  const segments = normalized.split('/');
  if (segments.includes('..') || segments.includes('.')) return '';

  const assetPath = normalized.startsWith('assets/') || normalized.startsWith('bg_images/')
    ? `images/${normalized}`
    : normalized;
  if (!assetPath.startsWith('images/assets/') && !assetPath.startsWith('images/bg_images/')) return '';
  return assetPath;
}

function sanitizeReusableReason(value) {
  const reason = String(value || '').trim();
  if (!reason || PROCESS_REASON_PATTERN.test(reason)) return '';
  return reason;
}

function sanitizeReusableStyleAsset(asset) {
  const path = normalizeReusableAssetPath(asset?.path);
  const role = String(asset?.role || '').toLowerCase();
  const reuseDecision = String(asset?.reuse_decision || '').toLowerCase();
  if (!path || !ACCEPTED_REUSABLE_ROLES.has(role) || !ACCEPTED_REUSABLE_DECISIONS.has(reuseDecision)) {
    return null;
  }
  return {
    path,
    role,
    reuse_decision: reuseDecision,
    page_roles: Array.isArray(asset.page_roles) ? asset.page_roles.filter(Boolean).map(String) : [],
    placement: asset.placement && typeof asset.placement === 'object' ? asset.placement : {},
    html_policy: asset.html_policy && typeof asset.html_policy === 'object' ? asset.html_policy : {},
    confidence: String(asset.confidence || ''),
    reason: sanitizeReusableReason(asset.reason),
  };
}

function buildReusableStyleAssets(reusableStyleAssets = {}) {
  const seen = new Set();
  const out = [];
  for (const asset of reusableStyleAssets.assets || []) {
    const sanitized = sanitizeReusableStyleAsset(asset);
    if (!sanitized || seen.has(sanitized.path)) continue;
    seen.add(sanitized.path);
    out.push(sanitized);
  }
  return out;
}

const EXECUTION_TYPOGRAPHY_ROLES = [
  { role: 'page_title', label: '页面标题', usage: '封面主标题、页面标题' },
  { role: 'section_title', label: '一级标题 / 卡片标题', usage: '模块标题、卡片标题' },
  { role: 'subsection_text', label: '二级标题 / 重点正文', usage: '重点说明、区块标题' },
  { role: 'body_text', label: '正文文本', usage: '正文、列表项、卡片说明' },
  { role: 'note_text', label: '辅助文本', usage: '页脚、来源、注释' },
];

function ptToPx(pt) {
  const value = Number(pt);
  return Number.isFinite(value) && value > 0 ? Math.round(value * 4 / 3) : null;
}

function collectExtractedTypographySizes(fontScale) {
  const byPx = new Map();
  for (const item of fontScale || []) {
    const candidates = [item?.dominant_pt, ...(Array.isArray(item?.common_sizes_pt) ? item.common_sizes_pt : [])];
    for (const candidate of candidates) {
      const pt = Number(candidate);
      const px = ptToPx(pt);
      if (!px || byPx.has(px)) continue;
      byPx.set(px, { px, pt: Math.round(pt * 10) / 10 });
    }
  }
  return [...byPx.values()].sort((a, b) => b.px - a.px);
}

function makeTypographyItem(roleInfo, px, source, pt) {
  const item = {
    role: roleInfo.role,
    label: roleInfo.label,
    px,
    source,
    tailwind: `text-[${px}px]`,
    usage: roleInfo.usage,
  };
  if (source === 'extracted' && Number.isFinite(pt)) item.pt = pt;
  return item;
}

function ensureDescendingUnique(items) {
  let previous = Infinity;
  return items.map(item => {
    const next = { ...item };
    if (next.px >= previous) {
      next.px = Math.max(1, previous - 1);
      next.tailwind = `text-[${next.px}px]`;
      if (next.source === 'extracted') {
        next.source = 'inferred';
        delete next.pt;
      }
    }
    previous = next.px;
    return next;
  });
}

function buildExecutionTypographyScale(fontScale) {
  const extracted = collectExtractedTypographySizes(fontScale);
  if (!extracted.length) return [];

  if (extracted.length >= EXECUTION_TYPOGRAPHY_ROLES.length) {
    return extracted.slice(0, EXECUTION_TYPOGRAPHY_ROLES.length).map((size, index) => (
      makeTypographyItem(EXECUTION_TYPOGRAPHY_ROLES[index], size.px, 'extracted', size.pt)
    ));
  }

  const page = extracted[0];
  const note = extracted[extracted.length - 1];
  const subsection = extracted.length >= 3
    ? extracted[Math.floor((extracted.length - 1) / 2)]
    : { px: Math.max(note.px + 2, Math.round(page.px * 0.6)), pt: null };

  return ensureDescendingUnique([
    makeTypographyItem(EXECUTION_TYPOGRAPHY_ROLES[0], page.px, 'extracted', page.pt),
    makeTypographyItem(EXECUTION_TYPOGRAPHY_ROLES[1], Math.round(page.px * 0.75), 'inferred'),
    makeTypographyItem(
      EXECUTION_TYPOGRAPHY_ROLES[2],
      subsection.px,
      Number.isFinite(subsection.pt) ? 'extracted' : 'inferred',
      subsection.pt,
    ),
    makeTypographyItem(EXECUTION_TYPOGRAPHY_ROLES[3], Math.round(subsection.px * 0.75), 'inferred'),
    makeTypographyItem(EXECUTION_TYPOGRAPHY_ROLES[4], note.px, 'extracted', note.pt),
  ]);
}

const EXECUTION_TYPOGRAPHY_LABELS = {
  page_title: '页面标题',
  section_title: '一级标题 / 卡片标题',
  subsection_text: '二级标题 / 重点正文',
  body_text: '正文文本',
  note_text: '辅助文本',
};

function sourceLabel(source) {
  return source === 'extracted' ? '抽取' : '推断补齐';
}

function fontSizesToScale(fontSizes) {
  return Object.entries(fontSizes || {}).map(([role, info]) => ({
    role,
    dominant_pt: info?.dominant_pt ?? null,
    common_sizes_pt: info?.common_sizes_pt || [],
    dominant_font: info?.dominant_font || '',
  }));
}

function buildTypographyNormalization({ styleName, structureData, vlmAnalysis, imageMapData, fontScale }) {
  const match = matchPresetStyle({
    styleName,
    structureData,
    vlmAnalysis,
    imageMapData,
  });
  return buildPresetNormalization({
    fontScale,
    match,
  });
}

function renderPresetStyleMatchSection(normalization) {
  const match = normalization?.match;
  if (
    !match?.selected_profile_id ||
    normalization?.execution_policy !== 'preset_execution_typography'
  ) return '';
  let md = '### 预设风格匹配与字号归一化\n\n';
  md += `- **匹配预设**: \`${match.selected_profile_id}\`（${match.selected_profile_name || '-'}）\n`;
  md += `- **置信度**: ${match.confidence}（score=${match.score}）\n`;
  md += `- **执行策略**: \`${normalization.execution_policy}\`\n`;
  if (normalization.display_title_reference?.length) {
    const refs = normalization.display_title_reference
      .map(item => `${item.pt}pt -> ${item.px}px (${item.tailwind})`)
      .join(' / ');
    md += `- **展示型字号参考**: ${refs}\n`;
  }
  if (Array.isArray(match.top_candidates) && match.top_candidates.length) {
    md += '\n| 候选预设 | 得分 | 触发信号 |\n|---------|------|----------|\n';
    for (const candidate of match.top_candidates) {
      md += `| \`${candidate.profile_id || candidate.id}\` | ${candidate.score} | ${(candidate.reasons || []).join(' / ') || '-'} |\n`;
    }
  }
  return `${md}\n`;
}

function renderExecutionTypographyTable(scale) {
  if (!scale?.length) return '';

  let md = '### 字体大小定义（Tailwind CSS 类）\n\n';
  md += '| 元素类型 | 字号 | Tailwind 类 | 来源 | 使用场景 |\n|---------|------|-------------|------|----------|\n';
  for (const item of scale) {
    const label = EXECUTION_TYPOGRAPHY_LABELS[item.role] || item.label || item.role;
    md += `| ${label} | ${item.px}px | \`${item.tailwind}\` | ${sourceLabel(item.source)} | ${item.usage || '-'} |\n`;
  }

  md += '\n**硬性约束**\n\n';
  md += '- 生成 HTML 时必须优先使用上表字号。\n';
  md += '- 禁止自行创造未列出的字号。\n';
  md += '- 正文不得降级为辅助字号。\n';
  md += '- 内容放不下时，首选精简文字、拆分页面、调整版式；若内容不可删减且要点数超过 5，可将正文字号适当缩小，但不得低于辅助文本字号。\n';
  md += '- 只有页脚、来源、日期、角标可以使用辅助文本字号。\n';
  return md;
}

function renderTypographyAppendix(fontScale, scale) {
  const extracted = collectExtractedTypographySizes(fontScale);
  if (!extracted.length && !scale?.length) return '';

  const extractedPt = extracted.map(item => `${item.pt}pt`).join(' / ') || '-';
  const extractedPx = extracted.map(item => `${item.pt}pt -> ${item.px}px`).join(' / ') || '-';
  const inferred = (scale || [])
    .filter(item => item.source !== 'extracted')
    .map(item => `${EXECUTION_TYPOGRAPHY_LABELS[item.role] || item.label || item.role}: ${item.px}px (${item.tailwind})`)
    .join(' / ') || '无';

  let md = '## 附录：抽取依据\n\n';
  md += '### 字号抽取依据\n\n';
  md += `- 原始抽取字号：${extractedPt}\n`;
  md += `- 折算像素：${extractedPx}\n`;
  md += `- 推断补齐：${inferred}\n`;
  md += '- 推断原则：优先保留抽取得到的最大标题字号、正文候选字号和最小辅助字号；缺失层级按从大到小的视觉层级补齐，并确保 Tailwind 字号唯一递减。\n';
  return md;
}

function renderExecutionChecklist(scale) {
  if (!scale || !scale.length) return '';
  const title = scale.find(item => item.role === 'page_title');
  const body = scale.find(item => item.role === 'body_text');
  const note = scale.find(item => item.role === 'note_text');
  let md = '## 六、生成检查清单\n\n';
  if (title) md += `- [ ] 页面标题是否使用 \`${title.tailwind}\`。\n`;
  if (body) md += `- [ ] 正文、列表项、卡片说明是否使用 \`${body.tailwind}\`。\n`;
  if (note) md += `- [ ] 页脚、来源、注释是否使用 \`${note.tailwind}\`。\n`;
  md += '- [ ] 是否没有出现未定义字号。\n';
  md += '- [ ] 是否没有通过缩小字号解决内容溢出。\n';
  md += '- [ ] 是否优先复用了模板背景、装饰和版式结构。\n\n';
  return md;
}

function deriveTypographyTokens(fontScale) {
  const sizes = [];
  for (const item of fontScale || []) {
    const d = Number(item?.dominant_pt);
    if (Number.isFinite(d) && d > 0) sizes.push(Math.round(d * 10) / 10);
    for (const s of item?.common_sizes_pt || []) {
      const v = Number(s);
      if (Number.isFinite(v) && v > 0) sizes.push(Math.round(v * 10) / 10);
    }
  }
  const allSizesPt = [...new Set(sizes)].sort((a, b) => a - b);
  if (!allSizesPt.length) return null;

  const headingPt = allSizesPt[allSizesPt.length - 1];
  const notePt = allSizesPt[0];
  const bodyItem = (fontScale || []).find(item => {
    const role = String(item?.role || '').toLowerCase();
    return role === 'body' || role.includes('content')
      || role.includes('正文') || role.includes('内容');
  });
  const rawBodyCandidate = Number(bodyItem?.dominant_pt);
  const bodyCandidate = Number.isFinite(rawBodyCandidate) && rawBodyCandidate > 0
    ? Math.round(rawBodyCandidate * 10) / 10
    : NaN;
  const bodyPt = Number.isFinite(bodyCandidate) && bodyCandidate > 0
    ? bodyCandidate
    : allSizesPt.length >= 3 ? allSizesPt[Math.floor((allSizesPt.length - 1) / 2)] : allSizesPt[0];

  return { heading_pt: headingPt, body_pt: bodyPt, note_pt: notePt, all_sizes_pt: allSizesPt };
}

function buildExecutionTokens(fontScale, normalization = null) {
  const fallbackScale = buildExecutionTypographyScale(fontScale);
  const typographyScale = resolveExecutionTypographyScale({
    normalization,
    fallbackScale,
  });
  if (!typographyScale.length) return null;
  return {
    typography_scale: typographyScale,
    preset_style_match: normalization?.match || null,
    display_title_reference: normalization?.display_title_reference || [],
    rules: {
      forbid_undefined_font_sizes: true,
      forbid_body_as_note_size: true,
      overflow_strategy: ['shorten_text', 'split_page', 'change_layout'],
    },
  };
}

function generateTemplateSpec(options) {
  const {
    styleName = '自定义风格',
    structureData = {},
    vlmAnalysis = {},
    imageMapData = {},
    reusableStyleAssets = {},
  } = options;
  const vlmAnalyses = vlmAnalysis?.analyses || [];
  const fixedComposition = collectVLMItems(vlmAnalyses, 'fixed_composition');
  const vlmLayoutSemantics = collectVLMItems(vlmAnalyses, 'layout_semantics');
  const vlmColorSemantics = extractVLMColorSemantics(vlmAnalyses);
  const colors = selectColors(structureData.actual_colors || {}, vlmColorSemantics.bg);
  const fontSizes = structureData.font_sizes || {};
  const fontScale = fontSizesToScale(fontSizes);
  const typographyNormalization = buildTypographyNormalization({
    styleName,
    structureData,
    vlmAnalysis,
    imageMapData,
    fontScale,
  });
  const executionTypographyScale = resolveExecutionTypographyScale({
    normalization: typographyNormalization,
    fallbackScale: buildExecutionTypographyScale(fontScale),
  });
  return {
    schema_version: 'ppt-template-spec-v1',
    style_name: styleName,
    slide_size: structureData.slide_size || {},
    colors,
    fonts: {
      title: structureData.fonts?.major?.ea || structureData.fonts?.major?.latin || '',
      body: structureData.fonts?.minor?.ea || structureData.fonts?.minor?.latin || '',
    },
    font_scale: fontScale,
    source_font_scale: fontScale,
    execution_font_scale: executionTypographyScale,
    preset_style_match: typographyNormalization.match,
    typography_normalization: typographyNormalization,
    typography_tokens: deriveTypographyTokens(fontScale),
    execution_tokens: buildExecutionTokens(fontScale, typographyNormalization),
    fixed_composition: fixedComposition,
    layout_library: buildLayoutLibrary(vlmLayoutSemantics, structureData.content_layout_styles || []),
    visual_assets: buildVisualAssets(imageMapData),
    reusable_style_assets: buildReusableStyleAssets(reusableStyleAssets),
    asset_policy: {
      slides: 'reference_only',
      images_assets: 'optional_reference',
      bg_images: 'reuse_when_present',
    },
    hard_constraints: [
      'slides/ 下的整页截图仅作视觉参考，不得直接作为新页面背景',
      '优先按 layout_library 的 page_role、semantic_type 和 selection_rule 选择版式',
      '配色只能使用 colors.allowed 中的颜色',
    ],
  };
}

const SECTION_NUMBERS = ['一', '二', '三', '四', '五', '六', '七', '八', '九', '十', '十一', '十二'];

function renderNumberedSections(sections) {
  return sections
    .filter(section => section?.body != null && String(section.body).trim())
    .map((section, index) => `## ${SECTION_NUMBERS[index] || index + 1}、${section.title}\n\n${String(section.body).trim()}\n`)
    .join('\n---\n\n');
}

function generateFixedCompositionSection(items) {
  if (!items?.length) return null;
  const selected = [];
  const seen = new Set();
  for (const item of items) {
    const elements = Array.isArray(item.required_elements) ? item.required_elements.slice(0, 4).join('|') : '';
    const key = `${item.page_type || 'general'}|${elements}|${item.layout_rule || ''}`.replace(/\s+/g, '');
    if (seen.has(key)) continue;
    seen.add(key);
    selected.push(item);
    if (selected.length >= 6) break;
  }

  let md = '> 只保留影响相似度的页面骨架。生成时先套骨架，再填充新内容。\n\n';
  for (const [index, item] of selected.entries()) {
    const no = String(index + 1).padStart(2, '0');
    md += `### 页面骨架 ${no}：${item.page_type || '通用页面'}\n\n`;
    if (Array.isArray(item.required_elements) && item.required_elements.length) {
      md += `- **保留元素**: ${item.required_elements.slice(0, 6).join('；')}\n`;
    }
    if (item.layout_rule) md += `- **布局要点**: ${item.layout_rule}\n`;
    if (hasText(item.avoid_rules)) md += `- **禁用**: ${formatListLike(item.avoid_rules)}\n`;
    md += '\n';
  }
  return md;
}

function formatListLike(value) {
  if (Array.isArray(value)) return value.join('；');
  return value || '-';
}

function hasText(value) {
  return String(formatListLike(value) || '').trim().length > 0;
}

function generateReplicationPrioritySection(replicationRules) {
  if (!replicationRules?.length) return null;
  const seenTexts = new Set();
  const seenTopics = new Set();
  const topicPatterns = [
    ['background', /背景|底图|纹理/],
    ['color', /主色|辅助色|配色|颜色|色调/],
    ['title', /标题|副标题/],
    ['body', /正文|段落|行距|内容/],
    ['asset', /装饰|图标|图片|资产|箭头|三角|点阵/],
    ['component', /按钮|卡片|边框|圆角|阴影/],
    ['chart', /数据|图表/],
  ];
  const selected = [];
  for (const rule of replicationRules) {
    const text = typeof rule === 'string' ? rule : (rule.rule || rule.text || rule.requirement || '');
    const normalized = text.replace(/\s+/g, '').replace(/[。；;,.，]/g, '');
    if (!text || seenTexts.has(normalized)) continue;
    seenTexts.add(normalized);
    const topic = topicPatterns.find(([, pattern]) => pattern.test(text))?.[0] || `other-${selected.length}`;
    if (seenTopics.has(topic)) continue;
    seenTopics.add(topic);
    selected.push(text);
    if (selected.length >= 8) break;
  }
  if (!selected.length) return null;
  let md = '后续生成新 PPT 时，优先遵守以下核心约束；相似规则已合并，避免把分析过程中的重复判断写入规范。\n\n';
  for (const text of selected) md += `- ${text}\n`;
  return md;
}

function generateVLMPageRolesSection(pageRoles) {
  if (!pageRoles?.length) return null;
  const roleOrder = ['cover', 'toc', 'section', 'content', 'data', 'divider', 'ending', 'unknown'];
  const roleLabels = {
    cover: '封面页',
    toc: '目录页',
    section: '章节页',
    content: '内容页',
    data: '数据页',
    divider: '过渡页',
    ending: '结束页',
    unknown: '其他页面',
  };
  const roleCounts = new Map();
  for (const item of pageRoles) {
    const role = item.role || 'unknown';
    roleCounts.set(role, (roleCounts.get(role) || 0) + 1);
  }

  let md = '> 生成时先判断页面类型，再选择对应版式；不要把封面页、章节页和内容页混用。\n\n';
  for (const role of roleOrder) {
    if (!roleCounts.has(role)) continue;
    const count = roleCounts.get(role);
    md += `- **${roleLabels[role] || role}**：检测到该类页面样式，可作为新 PPT 的${roleLabels[role] || role}参考`;
    if (count > 1) md += `（多页样例，优先抽象共性）`;
    md += '。\n';
  }
  return md;
}

function generateVLMLayoutSemanticsSection(layoutSemantics) {
  if (!layoutSemantics?.length) return null;
  const semanticLabels = {
    progressive: '递进型',
    parallel: '分列/并列型',
    comparison: '对比型',
    summary_detail: '总分型',
    process: '流程型',
    timeline: '时间轴型',
    matrix: '矩阵型',
    case: '案例型',
    data_focus: '数据强调型',
    image_text: '图文说明型',
    quote: '观点引用型',
    unknown: '未确定',
  };

  const selected = [];
  const seen = new Set();
  for (const item of layoutSemantics) {
    const key = [
      item.page_role || 'unknown',
      item.semantic_type || 'unknown',
      item.layout_name || '',
      item.slot_structure || '',
    ].join('|').replace(/\s+/g, '');
    if (seen.has(key)) continue;
    seen.add(key);
    selected.push(item);
    if (selected.length >= 8) break;
  }

  let md = '> 先判断当前页的信息关系，再选择版式；这是后续生成 PPT 的主要排版依据。\n\n';
  selected.forEach((item, index) => {
    const no = String(index + 1).padStart(2, '0');
    md += `#### 版式 ${no}：${item.layout_name || '未命名版式'}\n\n`;
    const semanticType = semanticLabels[item.semantic_type] || item.semantic_type || '未确定';
    md += `- **类型/角色**: ${semanticType} / \`${item.page_role || 'unknown'}\`\n`;
    const scenario = item.content_scenario || item.reuse_rule;
    if (scenario) md += `- **适用**: ${scenario}\n`;
    if (item.information_relation) md += `- **信息关系**: ${item.information_relation}\n`;
    if (item.slot_structure) md += `- **内容槽位**: ${formatListLike(item.slot_structure)}\n`;
    if (item.selection_rule) md += `- **选择规则**: ${item.selection_rule}\n`;
    const layoutPoints = [
      item.title_position ? `标题${item.title_position}` : '',
      item.body_structure,
      item.visual_structure,
      item.spacing_rules ? `间距：${item.spacing_rules}` : '',
    ].filter(Boolean).join('；');
    if (layoutPoints) md += `- **布局要点**: ${layoutPoints}\n`;
    if (hasText(item.avoid_rules)) md += `- **禁用**: ${formatListLike(item.avoid_rules)}\n`;
    md += '\n';
  });
  return md;
}

function correctionPriorityRank(priority) {
  const p = String(priority || '').toLowerCase();
  if (p === 'high') return 0;
  if (p === 'medium') return 1;
  if (p === 'low') return 2;
  return 3;
}

function hasDisallowedHex(value, allowedHexes) {
  if (!allowedHexes?.size) return false;
  const matches = String(value || '').match(/#[0-9a-fA-F]{6}\b/g) || [];
  return matches.some(hex => !allowedHexes.has(hex.toUpperCase()));
}

function generateVLMCorrectionsSection(corrections, allowedHexes = null) {
  if (!corrections?.length) return null;
  const filtered = corrections.filter(item => {
    const priority = String(item.priority || '').toLowerCase();
    if (priority !== 'high' && priority !== 'medium') return false;
    return !hasDisallowedHex([
      item.target,
      item.observed,
      item.recommendation,
      item.reason,
    ].join(' '), allowedHexes);
  });
  if (!filtered.length) return null;
  const sorted = [...filtered].sort((a, b) => (
    correctionPriorityRank(a.priority) - correctionPriorityRank(b.priority)
  ));

  let md = '> 下列规则用于处理工具结构提取与截图视觉观感可能不一致的情况。生成新 PPT 时，如遇冲突，应优先遵守高优先级纠偏建议。\n\n';
  md += '| 优先级 | 目标 | 视觉观察 | 复刻建议 | 原因 |\n|--------|------|----------|----------|------|\n';
  for (const item of sorted) {
    md += `| ${item.priority || '-'} | \`${item.target || '-'}\` | ${item.observed || '-'} | ${item.recommendation || '-'} | ${item.reason || '-'} |\n`;
  }
  return md;
}

function generateHardConstraintsSection(options) {
  const {
    hasPageRoles,
    hasReusableAssets,
    hasLayoutSemantics,
    hasCorrections,
    hasContentStyles,
    hasActualColors,
    hasFixedComposition,
    primaryColor,
    overlayPolicy,
  } = options;

  const rules = [];
  rules.push('只使用本规范列出的页面尺寸、字体层级、规范配色和版式选择库；不要引入默认 Office 模板风格。');
  if (hasFixedComposition) {
    rules.push('优先复刻“模板固定构图”中的页面骨架，再填充新内容；不得用相似但不同的装饰替代固定构图。');
  }
  if (hasReusableAssets) {
    rules.push('仅 `images/bg_images/` 中的正式背景图要求迁移；`images/assets/` 中的局部图片、纹理、点缀图暂不作为强制复用资产。');
  }
  rules.push('`slides/` 下的整页截图仅作视觉参考，不得直接作为新页面背景；除 `images/bg_images/` 外，不要求复用模板抽取图片。');
  if (hasLayoutSemantics) {
    rules.push('先判断当前页的信息关系（递进/并列/对比/总分/流程/矩阵/案例/数据强调），再按“版式选择库”的类型/角色和选择规则选版。');
    rules.push('标题位置、正文结构、视觉结构必须服务于选定版式的信息关系；不要为了填充内容随意移动核心区域。');
  } else if (hasContentStyles) {
    rules.push('内容页必须优先复用“版式选择库”中的结构，不要创造与源模板无关的新版式。');
  }
  if (hasActualColors) {
    rules.push('配色必须来自“规范配色（源PPT实际使用）”；未列出的主题色、默认色和临时调试色不得作为新页面配色。');
  }
  if (hasCorrections) {
    rules.push('高优先级视觉纠偏规则必须覆盖通用模板建议，尤其是主色、背景、页面角色和核心版式相关规则。');
  }

  rules.push(
    '每页 HTML 的 `<style>` 块中必须包含以下规则以防止全局 Tailwind CSS 覆盖背景图渲染：' +
    '`.ppt-slide .template-bg-image, .slide .template-bg-image { object-fit: cover !important; width: 100% !important; height: 100% !important; position: absolute; inset: 0; z-index: 0; }`；' +
    '背景图 `<img>` 元素必须使用 class `template-bg-image`。'
  );
  if (primaryColor) {
    rules.push(
      `幻灯片容器（\`.ppt-slide\` / \`.slide\`）必须设置 \`background-color: ${primaryColor}\` 作为兜底色，确保背景图加载前页面不显示白屏或灰屏。`
    );
  }
  if (overlayPolicy && typeof overlayPolicy.present === 'boolean') {
    if (overlayPolicy.present) {
      const overlayColor = overlayPolicy.color || 'rgba(0,0,0,0.35)';
      rules.push(
        `使用背景图的页面（封面、章节页等）必须叠加半透明遮罩：\`background: ${overlayColor}\`，以确保文字可读；不得省略此遮罩。`
      );
    } else {
      rules.push(
        '使用背景图的页面（封面、章节页等）禁止添加任何额外遮罩层（overlay / mask）；原模板背景图直接呈现，无半透明覆盖。'
      );
    }
  } else {
    rules.push(
      '使用背景图的页面（封面、章节页等）禁止自行添加未经本规范指定的遮罩层（overlay / mask）；若原模板无遮罩，不得添加。'
    );
  }

  rules.push('每页先确定页面角色和信息关系，再选择版式，最后填充内容；不要先堆内容再临时调整视觉样式。');

  let md = '以下规则是生成新 PPT 时的最终执行清单，后续大模型应把它作为硬约束使用。\n\n';
  for (const rule of rules) {
    md += `- ${rule}\n`;
  }
  return md;
}


function generateActualColorsSection(actualColors, slideCount) {
  if (!actualColors || !Object.keys(actualColors).length) return null;
  const sc = (Number.isFinite(slideCount) && slideCount > 0) ? slideCount : 1;

  const fillEntries = [], textOnlyEntries = [];
  for (const [hex, info] of Object.entries(actualColors)) {
    if ((info.fill_count || 0) > 0) {
      fillEntries.push([hex, info]);
    } else {
      textOnlyEntries.push([hex, info]);
    }
  }

  let md = '';

  if (fillEntries.length) {
    const pageBackgroundEntries = fillEntries.filter(([, info]) => {
      const usages = info.usages || [];
      return usages.includes('background_fill') && (info.area_weight || 0) / sc >= 0.95;
    });
    if (pageBackgroundEntries.length) {
      md += '### 页面级背景色规则\n\n';
      md += '> **页面画布背景优先级高于元素配色。** 下列颜色来自幻灯片背景本身，必须用于整页背景/画布底色；不要降级理解为卡片、标题、按钮等局部元素填充色。\n\n';
      md += '| 页面背景色 | 视觉占比 | 使用规则 |\n|------|----------|----------|\n';
      for (const [hex, info] of pageBackgroundEntries) {
        const areaStr = info.area_weight != null ? `${(info.area_weight / sc * 100).toFixed(1)}%` : '-';
        md += `| \`${hex}\` | ${areaStr} | 作为整页背景色铺满幻灯片画布 |\n`;
      }
      md += '\n';
    }
    md += '**填充/背景色**（按视觉面积排序，设计时以这组为主）\n\n';
    md += '> **颜色使用约束**：用途中仅出现"渐变填充"的颜色，只能作为对应渐变的色标/端点使用，禁止作为独立实心背景、内容框、卡片、按钮或大面积纯色填充。只有同时出现非渐变"填充"用途的颜色，才可作为独立实心填充色。\n\n';
    md += '| 颜色 | 用途 | 视觉占比 | 使用约束 |\n|------|------|----------|----------|\n';
    for (const [hex, info] of fillEntries) {
      const rawUsages = (info.usages || []).filter(u => !u.includes('_text'));
      const usages = (info.usages || [])
        .filter(u => !u.includes('_text'))
        .map(u => USAGE_LABEL[u] || u)
        .join(' / ');
      const areaStr = info.area_weight != null ? `${(info.area_weight / sc * 100).toFixed(1)}%` : '-';
      const hasGradientFill = rawUsages.some(u => u.includes('_fill_gradient'));
      const hasSolidFill = rawUsages.some(u => /_fill$/.test(u) || u === 'background_fill');
      const constraint = hasGradientFill && !hasSolidFill
        ? '仅作为渐变色标/端点；禁止独立实心填充'
        : hasGradientFill && hasSolidFill
          ? '可作实心填充；也可按模板渐变使用'
          : '可作独立实心填充';
      md += `| \`${hex}\` | ${usages || '-'} | ${areaStr} | ${constraint} |\n`;
    }
    md += '\n';
  }

  if (textOnlyEntries.length) {
    md += '**文字色**（仅出现在文本中，不建议用作背景或大面积填充）\n\n';
    md += '| 颜色 | 用途 |\n|------|------|\n';
    for (const [hex, info] of textOnlyEntries) {
      const usages = (info.usages || []).map(u => USAGE_LABEL[u] || u).join(' / ');
      md += `| \`${hex}\` | ${usages || '-'} |\n`;
    }
    md += '\n';
  }

  return md || null;
}


const FONT_SIZE_LABEL = {
  title: '标题占位符', center_title: '居中标题', body: '正文占位符',
  subtitle: '副标题', free_text: '自由文本框', free_shape: '自由文本/形状文本',
};

function generateFontSection(fonts, fontSizes, executionTypographyScale = null, normalization = null) {
  let md = '';

  if (fonts && Object.keys(fonts).length) {
    if (fonts.major) {
      md += '**标题字体（majorFont）**\n';
      if (fonts.major.latin) md += `- 西文: \`${fonts.major.latin}\`\n`;
      if (fonts.major.ea)    md += `- 中文: \`${fonts.major.ea}\`\n`;
    }
    if (fonts.minor) {
      md += '\n**正文字体（minorFont）**\n';
      if (fonts.minor.latin) md += `- 西文: \`${fonts.minor.latin}\`\n`;
      if (fonts.minor.ea)    md += `- 中文: \`${fonts.minor.ea}\`\n`;
    }
  } else {
    md += '未检测到字体方案\n';
  }

  const fontScale = fontSizesToScale(fontSizes);
  const typographyScale = executionTypographyScale || buildExecutionTypographyScale(fontScale);
  const presetMatchSection = renderPresetStyleMatchSection(normalization);
  const typographyTable = renderExecutionTypographyTable(typographyScale);
  if (typographyTable) {
    return `${md}\n${presetMatchSection}${typographyTable}`.trim();
  }

  return `${md}\n${presetMatchSection}`.trim() || '未检测到字体信息';
}


const ALIGN_LABEL = {
  'PP_ALIGN.LEFT (1)': '左对齐', 'PP_ALIGN.CENTER (2)': '居中',
  'PP_ALIGN.RIGHT (3)': '右对齐', 'PP_ALIGN.JUSTIFY (4)': '两端对齐',
  'PP_ALIGN.DISTRIBUTE (5)': '分散对齐',
  '1': '左对齐', '2': '居中', '3': '右对齐', '4': '两端对齐',
};

function generateParaAlignmentSection(paraAlignment) {
  if (!paraAlignment || !Object.keys(paraAlignment).length) return null;

  let md = '| 层级 | 主要对齐 | 分布 |\n|------|---------|------|\n';
  for (const [role, info] of Object.entries(paraAlignment)) {
    const label    = FONT_SIZE_LABEL[role] || role;
    const dominant = ALIGN_LABEL[info.dominant] || info.dominant || '-';
    const dist     = Object.entries(info.counts || {})
      .map(([k, v]) => `${ALIGN_LABEL[k] || k}×${v}`)
      .join(' / ');
    md += `| ${label} | **${dominant}** | ${dist || '-'} |\n`;
  }
  return md;
}


function generateMasterSection(master) {
  if (!master || (!master.fixed_shapes?.length && !master.background?.color)) return null;

  let md = '';

  if (master.background?.color) {
    md += `- **背景色**: \`${master.background.color}\`\n`;
  }

  if (master.fixed_shapes?.length) {
    md += `\n以下固定装饰形状应在每页保留（共 ${master.fixed_shapes.length} 个）：\n\n`;
    md += '| 类型 | 位置 (左%, 上%) | 尺寸 (宽%, 高%) | 填充色 |\n';
    md += '|------|----------------|----------------|--------|\n';
    for (const s of master.fixed_shapes) {
      const fill = s.fill_color ? `\`${s.fill_color}\`` : '-';
      const text = s.text_preview ? `（"${s.text_preview}"）` : '';
      md += `| ${s.shape_type}${text} | ${s.left_pct}%, ${s.top_pct}% | ${s.width_pct}%, ${s.height_pct}% | ${fill} |\n`;
    }
  }

  return md;
}


function generateComponentStylesSection(styles) {
  if (!styles || !Object.keys(styles).length) return null;

  const rules = [];
  rules.push('容器以白底信息块为主，使用规范主色的细线边框或标题栏建立层级。');
  rules.push('折角、箭头、编号圆点等装饰服务于版式结构，不作为随机点缀新增。');
  if (styles.shadow) {
    rules.push('阴影只作轻微层级提示，不使用厚重投影或强发光。');
  } else {
    rules.push('整体以扁平风格为主，避免额外阴影。');
  }
  if (styles.gradient) {
    rules.push('渐变仅用于年份水印、波浪或装饰层，不作为大面积内容背景。');
  }
  return rules.map(rule => `- ${rule}`).join('\n');
}


function generateLayoutSection(layouts) {
  if (!layouts || !layouts.length) return '未检测到版式信息';

  let md = `本模板定义以下 **${layouts.length}** 种版式：\n\n`;
  for (const layout of layouts) {
    md += `### ${layout.name || `版式 ${layout.index}`}\n\n`;
    if (layout.placeholders?.length) {
      md += '| 占位符 | 位置 (cm) | 尺寸 (cm) | 字号 | 字体 | 对齐 |\n';
      md += '|--------|-----------|-----------|------|------|------|\n';
      for (const ph of layout.placeholders) {
        const type  = PLACEHOLDER_TYPE_MAP[ph.type] || ph.type || '未知';
        const pos   = ph.left_cm != null ? `${ph.left_cm}, ${ph.top_cm}` : '-';
        const size  = ph.width_cm != null ? `${ph.width_cm} × ${ph.height_cm}` : '-';
        const sz    = ph.font_size_pt != null ? `${ph.font_size_pt}pt` : '-';
        const font  = ph.font_name ? `\`${ph.font_name}\`` : '-';
        const align = ALIGN_LABEL[ph.alignment] || ph.alignment || '-';
        md += `| ${type} | ${pos} | ${size} | ${sz} | ${font} | ${align} |\n`;
      }
    }
    md += '\n';
  }
  return md;
}


function formatPctBox(box) {
  if (!box) return '-';
  return `左 ${box.left ?? '-'}%, 上 ${box.top ?? '-'}%, 宽 ${box.width ?? '-'}%, 高 ${box.height ?? '-'}%`;
}

function generateContentLayoutStylesSection(styles) {
  if (!styles || !styles.length) return null;

  let md = '> VLM 未提供语义版式时，使用下列工具抽取版式兜底。\n\n';
  for (const [index, style] of styles.slice(0, 5).entries()) {
    const styleNo = String(index + 1).padStart(2, '0');
    md += `#### 内容页样式 ${styleNo}：${style.name || '内容页样式'}\n\n`;
    md += `- **类型**: \`${style.subtype || '-'}\`\n`;
    if (style.description) md += `- **排版描述**: ${style.description}\n`;
    if (style.usage_rule) md += `- **选择规则**: ${style.usage_rule}\n`;
    const bodyRegions = [...new Set((style.body_blocks || []).map(b => b.region).filter(Boolean))];
    const visualRegions = [...new Set((style.visual_blocks || []).map(b => b.region).filter(Boolean))];
    if (bodyRegions.length || visualRegions.length) md += `- **区域**: 正文 ${bodyRegions.join(' / ') || '-'}；视觉 ${visualRegions.join(' / ') || '-'}\n`;
    md += '\n';
  }
  return md;
}

function generatePageStructureGuidanceSection(hasContentStyles) {
  let md = `### 页面类型使用建议

- **封面页**：突出主题名称和副标题，使用大面积留白、主色强调块或边角装饰建立第一视觉；信息控制在标题、副标题、汇报对象/日期三类以内。
- **章节页**：用于承接内容段落切换，标题应短而有方向感；可使用编号、主色块、留白和固定装饰元素形成节奏停顿。
- **内容页**：围绕一个核心观点组织信息，优先复用下方内容页样式；正文、数据、图示之间保持清晰分区，不使用与模板无关的新视觉语言。
- **结束页**：保持简洁，可使用感谢语、行动建议或联系方式；延续封面/章节页的主色与装饰秩序。

`;
  if (hasContentStyles) {
    md += '> 下方内容页样式库是新内容排版的主要依据；它描述的是可复用结构，不是对源 PPT 页码的分析。\n\n';
  }
  return md;
}


function generateVLMSupplementSection(vlmAnalysis) {
  if (!vlmAnalysis?.analyses?.length) return null;

  let md = '';
  for (let i = 0; i < vlmAnalysis.analyses.length; i++) {
    const a = vlmAnalysis.analyses[i];
    const data = a['配色方案'] ? a : (a['设计分析报告'] || a);
    const batch = vlmAnalysis.analyses.length > 1 ? `批次 ${i + 1} · ` : '';

    if (data['配色方案']) {
      const cs = data['配色方案'];
      md += `#### ${batch}配色\n`;
      if (cs['主色调'])   md += `- 主色调: ${cs['主色调']}\n`;
      if (cs['辅助色'])   md += `- 辅助色: ${cs['辅助色']}\n`;
      if (cs['文字色'])   md += `- 文字色: ${cs['文字色']}\n`;
      if (cs['点缀色'])   md += `- 点缀色: ${cs['点缀色']}\n`;
      if (cs['配色风格']) md += `- 风格: ${cs['配色风格']}\n`;
      md += '\n';
    }
    if (data['字体风格']) {
      const fs = data['字体风格'];
      md += `#### ${batch}字体排版\n`;
      if (fs['中文字体'] || fs['字体类型']) md += `- 中文字体: ${fs['中文字体'] || fs['字体类型']}\n`;
      if (fs['英文数字'] || fs['排版特征']) md += `- 英文/数字: ${fs['英文数字'] || fs['排版特征']}\n`;
      if (fs['排版风格']) md += `- 排版风格: ${fs['排版风格']}\n`;
      md += '\n';
    }
    if (data['布局结构']) {
      const ls = data['布局结构'];
      md += `#### ${batch}布局\n`;
      const mode = ls['整体模式'] || ls['布局模式'] || ls['页面模式'];
      if (mode) md += `- 布局模式: ${mode}\n`;
      if (Array.isArray(ls['结构特征'])) md += `- 结构特征: ${ls['结构特征'].join(', ')}\n`;
      if (ls['对齐方式']) md += `- 对齐: ${ls['对齐方式']}\n`;
      md += '\n';
    }
    if (data['视觉风格']) {
      const vs = data['视觉风格'];
      md += `#### ${batch}视觉风格\n`;
      const overall = vs['整体风格'] || vs['风格定位'];
      if (overall) md += `- 整体: ${overall}\n`;
      if (vs['设计特点']) md += `- 特点: ${vs['设计特点']}\n`;
      if (Array.isArray(vs['设计关键词'])) md += `- 关键词: ${vs['设计关键词'].join(', ')}\n`;
      md += '\n';
    }
    if (data['组件样式']) {
      const cs = data['组件样式'];
      md += `#### ${batch}组件\n`;
      if (cs['边框与容器'] || cs['边框与线条']) md += `- 边框: ${cs['边框与容器'] || cs['边框与线条']}\n`;
      if (cs['圆角'])     md += `- 圆角: ${cs['圆角']}\n`;
      if (cs['阴影效果']) md += `- 阴影: ${cs['阴影效果']}\n`;
      if (cs['装饰元素']) md += `- 装饰: ${cs['装饰元素']}\n`;
      md += '\n';
    }
  }
  return md;
}


function generateBgImagesSection(bgImages) {
  if (!bgImages || !Object.keys(bgImages).length) return null;

  let md = `以下背景图片按建议用途使用：\n\n`;
  md += '| 路径 | 类型 | 使用建议 | 格式 |\n|------|------|----------|------|\n';
  for (const [, info] of Object.entries(bgImages)) {
    const isShape = info.source_method === 'shape';
    const typeTag = isShape ? '形状背景' : '正式背景';
    const usage = isShape ? '作为大面积风格背景或纹理层使用' : '作为整页背景使用';
    md += `| \`${info.saved_as}\` | ${typeTag} | ${usage} | ${info.format} |\n`;
  }
  md += '\n> 背景图片位于 `images/bg_images/` 目录，可直接引用。"形状背景"为覆盖率 >90% 的大图，同时也保存在 `images/assets/` 中。\n';
  return md;
}


function generateReusableStyleAssetsSection(reusableStyleAssets) {
  const assets = buildReusableStyleAssets(reusableStyleAssets);
  if (!assets.length) return null;

  let md = '> Reuse these vetted style images only as decorative template assets. Keep content photos, charts, screenshots, and organization-specific images out of fixed template layers.\n\n';
  for (const asset of assets.slice(0, 12)) {
    if (!asset?.path) continue;
    const role = String(asset.role || 'style_asset').replace(/_/g, ' ');
    const pageRoles = Array.isArray(asset.page_roles) && asset.page_roles.length
      ? `; page roles: ${asset.page_roles.join(', ')}`
      : '';
    const reason = asset.reason ? `; ${asset.reason}` : '';
    md += `- \`${asset.path}\`: ${role}${pageRoles}${reason}\n`;
  }
  return md.trim();
}

function formatRoleSources(item) {
  const role = item.role || '';
  if (role.includes('background')) return '作为背景层或底纹层使用';
  if (role === 'edge_decoration') return '放置在页边或角落，保持相对位置稳定';
  if (role === 'repeated_decoration') return '作为跨页面重复装饰元素使用';
  if (role === 'large_texture' || role === 'decorative_texture') return '作为大面积装饰纹理或视觉氛围层使用';
  return '按风格装饰资产使用';
}

function roleLabel(role) {
  const labels = {
    background: '背景图',
    background_texture: '背景纹理',
    large_texture: '大面积纹理',
    repeated_decoration: '重复装饰图',
    edge_decoration: '边角装饰图',
    decorative_texture: '装饰纹理',
  };
  return labels[role] || role || '-';
}

function isHighConfidenceAsset(item) {
  return String(item?.confidence || '').toLowerCase() === 'high';
}

function generateAssetRolesSection(assetRoles) {
  if (!assetRoles) return null;
  const backgrounds = (assetRoles.background || []).filter(isHighConfidenceAsset);
  if (!backgrounds.length) return null;

  let md = `> 仅以下正式背景图要求迁移引用；\`images/assets/\` 中的局部图片、纹理和点缀图暂不强制使用。\n\n`;
  md += '| 路径 | 角色 | 使用建议 |\n|------|------|----------|\n';
  for (const item of backgrounds) {
    md += `| \`${item.path}\` | ${roleLabel(item.role)} | ${formatRoleSources(item)} |\n`;
  }
  md += '\n**使用要求**：\n';
  md += '- 生成 HTML 前，必须将本模板的整个 `images/` 目录完整复制到 HTML 输出目录（`pages/`）下的 `template-assets/` 中，使其结构为 `pages/template-assets/images/bg_images/...` 和 `pages/template-assets/images/assets/...`。\n';
  md += '- HTML 中所有图片引用统一使用 `template-assets/images/...` 相对路径，禁止使用指向模板 Hub 目录（`../`）的跨目录相对路径。\n';
  md += '- 复制命令示例（需根据实际路径替换）：`cp -r <本模板目录>/images/ <pages_dir>/template-assets/images/`\n';
  return md;
}


function generateBgTextMappingSection(bgTextMapping) {
  if (!bgTextMapping || !Object.keys(bgTextMapping).length) return null;

  let md = '| 背景色 | 推荐文字色 | 使用页数 |\n|--------|-----------|----------|\n';
  for (const [bg, info] of Object.entries(bgTextMapping)) {
    const textColors = (info.text_colors || []).map(c => `\`${c}\``).join(' / ');
    md += `| \`${bg}\` | ${textColors || '-'} | ${info.slide_count ?? '-'} |\n`;
  }
  return md;
}


function generateStyleSpec(options) {
  const {
    styleName = '自定义风格',
    structureData = {},
    vlmAnalysis = {},
    imageMapData = {},
    reusableStyleAssets = {},
    timestamp = ''
  } = options;

  const { actual_colors, bg_text_mapping, fonts, font_sizes, para_alignment,
          slide_size, layouts, master, component_styles, slide_count,
          content_layout_styles } = structureData;
  const bgImages = imageMapData.bg_images || {};
  const assetRoles = imageMapData.asset_roles || null;

  const vlmAnalyses = vlmAnalysis?.analyses || [];
  const vlmColors   = extractVLMColorSemantics(vlmAnalyses);
  const vlmStyle    = extractVLMOverallStyle(vlmAnalyses);
  const vlmPageRoles = collectVLMItems(vlmAnalyses, 'page_roles');
  const vlmLayoutSemantics = collectVLMItems(vlmAnalyses, 'layout_semantics');
  const vlmReplicationRules = collectVLMItems(vlmAnalyses, 'replication_rules');
  const vlmCorrections = collectVLMItems(vlmAnalyses, 'corrections');
  const fixedComposition = collectVLMItems(vlmAnalyses, 'fixed_composition');

  const now = new Date();
  const timeStr = timestamp
    ? `${timestamp} (${now.toLocaleString('zh-CN')})`
    : now.toISOString();

  const styleOneLiner = vlmStyle
    ? `\n> **整体风格定位**：${vlmStyle}\n`
    : '';

  const vlmLayoutSemanticsSection = generateVLMLayoutSemanticsSection(vlmLayoutSemantics);
  const fixedCompositionSection = generateFixedCompositionSection(fixedComposition);

  const actualColorsSection = generateActualColorsSection(actual_colors, slide_count);
  const hasActualColors = Boolean(actual_colors && Object.keys(actual_colors).length);
  const actualColorSet = hasActualColors
    ? new Set(Object.keys(actual_colors).map(hex => String(hex).toUpperCase()))
    : null;
  const vlmCorrectionsSection = generateVLMCorrectionsSection(vlmCorrections, actualColorSet);

  const bgTextMappingSection = generateBgTextMappingSection(bg_text_mapping);

  const masterSection = generateMasterSection(master);

  const bgImagesSection = generateBgImagesSection(bgImages);

  const contentLayoutStylesSection = generateContentLayoutStylesSection(content_layout_styles);

  const assetRolesSection = generateAssetRolesSection(assetRoles);
  const reusableStyleAssetsSection = generateReusableStyleAssetsSection(reusableStyleAssets);

  const componentSection = generateComponentStylesSection(component_styles);

  const overlayPolicy = extractVLMOverlayPolicy(vlmAnalyses);
  const primaryColor = selectColors(actual_colors || {}, vlmColors.bg).primary || '';
  const hardConstraintsSection = generateHardConstraintsSection({
    hasPageRoles: vlmPageRoles.length > 0,
    hasReusableAssets: Boolean(assetRolesSection),
    hasLayoutSemantics: vlmLayoutSemantics.length > 0,
    hasCorrections: vlmCorrections.length > 0,
    hasContentStyles: Boolean(content_layout_styles?.length),
    hasActualColors: Boolean(actual_colors && Object.keys(actual_colors).length),
    hasFixedComposition: Boolean(fixedCompositionSection),
    primaryColor,
    overlayPolicy,
  });

  const writingSection = `- 观点在标题上，简短语句表达；每页传递观点三点以内
- **中文字体**：${fonts?.major?.ea || fonts?.minor?.ea || '见下方字体规范'}
- **英文字体**：${fonts?.major?.latin || fonts?.minor?.latin || '见下方字体规范'}
- 字号三种以内；关键内容可使用强调色加粗；慎用感叹号

### 内容密度原则

- 标题含核心观点；正文 3-5 个支撑要点，每点有具体说明或数据
- 单页至少：1 个核心观点 + 3 个支撑要点 + 1 个数据/图表
- 超过 6 个要点时拆分为多页`;

  const fontScaleForAppendix = fontSizesToScale(font_sizes);
  const typographyNormalization = buildTypographyNormalization({
    styleName,
    structureData,
    vlmAnalysis,
    imageMapData,
    fontScale: fontScaleForAppendix,
  });
  const executionTypographyScale = resolveExecutionTypographyScale({
    normalization: typographyNormalization,
    fallbackScale: buildExecutionTypographyScale(fontScaleForAppendix),
  });

  const fontSection = `${generateFontSection(
    fonts,
    font_sizes,
    executionTypographyScale,
    typographyNormalization,
  )}
${generateParaAlignmentSection(para_alignment) ? `
### 段落对齐（按层级）

${generateParaAlignmentSection(para_alignment)}` : ''}`;

  const executionChecklistSection = renderExecutionChecklist(executionTypographyScale);
  const typographyAppendixSection = renderTypographyAppendix(
    fontScaleForAppendix,
    executionTypographyScale,
  );

  const colorSection = `> ⚠️ **生成新PPT时必须严格使用下方"规范配色"中列出的颜色。** 未在此处出现的主题定义色、默认 Office 色或脚本调试色，不应作为新 PPT 的可选配色。

### 规范配色（源PPT实际使用）

${actualColorsSection || '未扫描到实际使用颜色；请优先基于幻灯片截图和视觉分析结果人工确认主色、背景色、文字色与点缀色。'}
${bgTextMappingSection ? `
### 背景-文字配色映射

> 不同背景色使用不同文字色，生成时须严格对应。

${bgTextMappingSection}` : ''}
${!hasActualColors && (vlmColors.primary || vlmColors.secondary) ? `
### 视觉参考配色

${vlmColors.primary     ? `- **主色调**: ${vlmColors.primary}\n` : ''}${vlmColors.secondary  ? `- **辅助色**: ${vlmColors.secondary}\n` : ''}${vlmColors.textColor  ? `- **文字色**: ${vlmColors.textColor}\n` : ''}${vlmColors.accent     ? `- **点缀色**: ${vlmColors.accent}\n` : ''}${vlmColors.bg         ? `- **背景色**: ${vlmColors.bg}\n` : ''}${vlmColors.style      ? `- **配色风格**: ${vlmColors.style}\n` : ''}` : ''}`;

  const sizeLayoutSection = `${slide_size ? `- 页面尺寸: **${slide_size.width_px} × ${slide_size.height_px}px**（${slide_size.aspect_ratio}）
- 内容区有效宽度估算: ~${Math.round(slide_size.width_px * 0.88)}px（两侧各留 6% 边距）` : '未检测到尺寸信息'}
${vlmLayoutSemanticsSection ? `
### 版式选择库

${vlmLayoutSemanticsSection}` : contentLayoutStylesSection ? `
### 版式选择库

${contentLayoutStylesSection}` : ''}`;

  const masterAssetsSection = `${masterSection || ''}${assetRolesSection ? `
### 风格迁移图片资产（强制引用）

${assetRolesSection}` : ''}
${reusableStyleAssetsSection ? `
### Reusable style image assets

${reusableStyleAssetsSection}` : ''}
${bgImagesSection ? `
### 背景图片

${bgImagesSection}` : ''}`;

  const numberedSections = renderNumberedSections([
    { title: '模板固定构图', body: fixedCompositionSection },
    { title: '写作基础', body: writingSection },
    { title: '字体与字号', body: fontSection },
    { title: '配色方案', body: colorSection },
    { title: '页面与版式选择', body: sizeLayoutSection },
    { title: '母版固定元素', body: masterAssetsSection },
    { title: '组件样式', body: componentSection || '未检测到明显的组件样式（边框/阴影/圆角），以纯白扁平风格为主。' },
    { title: '视觉纠偏规则', body: vlmCorrectionsSection },
    { title: '生成新 PPT 的硬约束', body: hardConstraintsSection },
  ]);

  const machineReadableArtifactsSection = `## 附：机器可读模板产物

以下文件与本 Markdown 位于同一目录，供 \`pptx-craft\` 模板复刻模式自动读取：

- \`template-spec.json\`：结构化模板规范，包含配色、字体、固定构图、版式选择库和资产策略。
- \`template-manifest.json\`：HTML 模板索引（v2 格式），声明 base HTML 文件路径与对应 page_role。
- \`html-templates/\`：base HTML 文件（每种 page_role 一个），仅含 CSS 变量、背景图、装饰图层；\`pptx-craft\` 以此为资产底层，排版由风格 MD 文件决定。
- \`images/bg_images/\`：正式背景图资产；后续生成只强制迁移该目录下的背景图。

说明：Markdown 正文用于人类阅读和模型理解；HTML 模板文件的发现与选择以 \`template-manifest.json\` 为准，不依赖正文中的逐个链接。
`;

  let md = `# ${styleName} - PPT 样式规范

> 本规范由 ppt-template-generate 自动生成
> 生成时间: ${timeStr}
${styleOneLiner}
---

${numberedSections}

${executionChecklistSection ? `${executionChecklistSection}\n` : ''}
${typographyAppendixSection ? `${typographyAppendixSection}\n` : ''}
${machineReadableArtifactsSection}
`;

  return md;
}


function aggregate(structurePath, vlmPath, outputPath, options = {}) {
  let structureData = {};
  if (fs.existsSync(structurePath)) {
    structureData = JSON.parse(fs.readFileSync(structurePath, 'utf-8'));
  }

  let vlmAnalysis = {};
  if (vlmPath && fs.existsSync(vlmPath)) {
    vlmAnalysis = JSON.parse(fs.readFileSync(vlmPath, 'utf-8'));
  }

  let imageMapData = {};
  if (options.imageMapPath && fs.existsSync(options.imageMapPath)) {
    imageMapData = JSON.parse(fs.readFileSync(options.imageMapPath, 'utf-8'));
  }
  const reusableStyleAssets = loadReusableStyleAssets(options.reusableStyleAssetsPath);

  const styleSpec = generateStyleSpec({
    styleName: options.styleName || '自定义风格',
    structureData,
    vlmAnalysis,
    imageMapData,
    reusableStyleAssets,
    timestamp: options.timestamp || '',
  });

  fs.writeFileSync(outputPath, styleSpec, 'utf-8');
  if (options.specPath) {
    const templateSpec = generateTemplateSpec({
      styleName: options.styleName || '自定义风格',
      structureData,
      vlmAnalysis,
      imageMapData,
      reusableStyleAssets,
    });
    fs.writeFileSync(options.specPath, JSON.stringify(templateSpec, null, 2), 'utf-8');
  }
  return outputPath;
}


function main() {
  const args = process.argv.slice(2);
  if (args.length < 2) {
    console.log(`
用法: node aggregate.js <结构数据JSON> <输出MD路径> [选项]

选项:
  --vlm=<路径>         VLM 分析结果 JSON
  --name=<名称>        风格名称
  --timestamp=<时间戳> 生成时间戳
  --template-spec=<路径> 生成机器可读模板规范 JSON

示例:
  node aggregate.js template_data.json output.md --name="企业蓝"
  node aggregate.js template_data.json output.md --vlm=vlm_analysis.json
`);
    process.exit(0);
  }

  const structurePath = args[0];
  const outputPath = args[1];
  const options = {};
  for (const arg of args.slice(2)) {
    if (arg.startsWith('--')) {
      const [key, value] = arg.slice(2).split('=');
      options[key] = value;
    }
  }

  try {
    const result = aggregate(structurePath, options.vlm, outputPath, {
      styleName: options.name,
      timestamp: options.timestamp,
      imageMapPath: options['image-map'],
      reusableStyleAssetsPath: options['reusable-style-assets'],
      specPath: options['template-spec'],
    });
    console.log(`样式规范已生成: ${result}`);
  } catch (error) {
    console.error(`错误: ${error.message}`);
    console.error('Stack:', error.stack);
    process.exit(1);
  }
}

function buildSpec(structureData, vlmAnalysis, imageMapData, styleName) {
  return generateTemplateSpec({
    styleName: styleName || '自定义风格',
    structureData: structureData || {},
    vlmAnalysis: vlmAnalysis || {},
    imageMapData: imageMapData || {},
  });
}

module.exports = {
  aggregate,
  generateStyleSpec,
  generateTemplateSpec,
  buildSpec,
  buildTypographyNormalization,
  deriveTypographyTokens,
  buildExecutionTypographyScale,
  renderPresetStyleMatchSection,
  renderExecutionTypographyTable,
  renderExecutionChecklist,
  renderTypographyAppendix,
  generateActualColorsSection,
  generateBgTextMappingSection,
  generateFontSection,
  generateMasterSection,
  generateComponentStylesSection,
  generateLayoutSection,
  generateContentLayoutStylesSection,
};

if (require.main === module) {
  main();
}
