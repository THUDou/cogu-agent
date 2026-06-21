const assert = require('assert');
const {
  loadPresetProfiles,
  matchPresetStyle,
  buildPresetNormalization,
  resolveExecutionTypographyScale,
} = require('../scripts/preset-style-normalizer.js');

const profiles = loadPresetProfiles();
assert.ok(profiles.length >= 4, 'preset profiles should include all built-in pptx-craft styles');
assert.ok(profiles.some(profile => profile.id === 'business-classic'), 'business-classic profile exists');
assert.ok(profiles.some(profile => profile.id === 'tech-minimal'), 'tech-minimal profile exists');
assert.ok(profiles.some(profile => profile.id === 'elegant-narrative'), 'elegant-narrative profile exists');
assert.ok(profiles.some(profile => profile.id === 'industrial-tech'), 'industrial-tech profile exists');

const redBusinessMatch = matchPresetStyle({
  styleName: '红色商务简约',
  structureData: {
    actual_colors: {
      '#C00000': { fill_count: 14, area_weight: 0.38 },
      '#FFFFFF': { fill_count: 9, area_weight: 0.48 },
      '#222222': { text_count: 18, area_weight: 0.08 },
    },
    component_styles: { shadow: false, gradient: false, border: true, rounded: false },
    content_layout_styles: [
      { name: '商务汇报卡片', description: '红色标题栏、白底信息卡片、简约商务汇报版式' },
    ],
  },
  vlmAnalysis: {
    analyses: [
      {
        '配色方案': { '主色调': '红色 #C00000', '背景色': '白色 #FFFFFF' },
        '视觉风格': { '整体风格': '红色 商务 简约 汇报' },
      },
    ],
  },
  profiles,
});

assert.strictEqual(redBusinessMatch.selected_profile_id, 'business-classic');
assert.strictEqual(redBusinessMatch.confidence, 'high');
assert.strictEqual(redBusinessMatch.applied_policy, 'preset_execution_typography');
assert.ok(redBusinessMatch.score >= 0.7, `expected high score, got ${redBusinessMatch.score}`);

const sourceFontScale = [
  { role: 'free_shape', dominant_pt: 138, common_sizes_pt: [138, 44, 28, 14], dominant_font: 'Alibaba PuHuiTi' },
];
const redBusinessNormalization = buildPresetNormalization({
  fontScale: sourceFontScale,
  match: redBusinessMatch,
  profiles,
});

assert.strictEqual(redBusinessNormalization.execution_policy, 'preset_execution_typography');
assert.strictEqual(redBusinessNormalization.execution_typography_scale[0].role, 'page_title');
assert.strictEqual(redBusinessNormalization.execution_typography_scale[0].px, 35);
assert.strictEqual(redBusinessNormalization.execution_typography_scale[0].source, 'preset');
assert.strictEqual(redBusinessNormalization.execution_typography_scale[0].preset_id, 'business-classic');
assert.ok(
  redBusinessNormalization.display_title_reference.some(item => item.px === 184),
  '184px extracted cover display size should be preserved as reference only',
);

const fallbackScale = [
  { role: 'page_title', label: '页面标题', px: 184, tailwind: 'text-[184px]', source: 'extracted' },
  { role: 'section_title', label: '一级标题', px: 59, tailwind: 'text-[59px]', source: 'extracted' },
  { role: 'subsection_text', label: '二级标题', px: 37, tailwind: 'text-[37px]', source: 'extracted' },
  { role: 'body_text', label: '正文文本', px: 28, tailwind: 'text-[28px]', source: 'extracted' },
  { role: 'note_text', label: '辅助文本', px: 19, tailwind: 'text-[19px]', source: 'extracted' },
];
const resolvedBusinessScale = resolveExecutionTypographyScale({
  normalization: redBusinessNormalization,
  fallbackScale,
});
assert.deepStrictEqual(
  resolvedBusinessScale.map(item => item.px),
  [35, 23, 21, 19, 16],
);

const ambiguousMatch = matchPresetStyle({
  styleName: '灰色信息图',
  structureData: {
    actual_colors: {
      '#777777': { fill_count: 4, area_weight: 0.28 },
      '#F7F7F7': { fill_count: 5, area_weight: 0.44 },
      '#222222': { text_count: 8, area_weight: 0.12 },
    },
    component_styles: { shadow: false, gradient: false },
    content_layout_styles: [{ name: '信息图', description: '中性灰色图文排版' }],
  },
  vlmAnalysis: { analyses: [{ '视觉风格': { '整体风格': '中性 信息图' } }] },
  profiles,
});
assert.notStrictEqual(ambiguousMatch.applied_policy, 'preset_execution_typography');

const ambiguousNormalization = buildPresetNormalization({
  fontScale: sourceFontScale,
  match: ambiguousMatch,
  profiles,
});
const resolvedAmbiguousScale = resolveExecutionTypographyScale({
  normalization: ambiguousNormalization,
  fallbackScale,
});
assert.strictEqual(resolvedAmbiguousScale[0].px <= 72, true, 'ambiguous extreme page title should be capped');
assert.strictEqual(resolvedAmbiguousScale[0].source, 'normalized');

const tiedProfiles = [
  {
    id: 'tie-alpha',
    name: 'Tie Alpha',
    matching: {
      colors: ['#123456'],
      tone_keywords: ['tie'],
      component_keywords: ['card'],
      layout_keywords: ['report'],
      semantic_keywords: ['shared'],
      component_expectations: { shadow: false, gradient: false, border: true, rounded: false },
    },
    typography_scale: [{ role: 'page_title', px: 35 }],
  },
  {
    id: 'tie-beta',
    name: 'Tie Beta',
    matching: {
      colors: ['#123456'],
      tone_keywords: ['tie'],
      component_keywords: ['card'],
      layout_keywords: ['report'],
      semantic_keywords: ['shared'],
      component_expectations: { shadow: false, gradient: false, border: true, rounded: false },
    },
    typography_scale: [{ role: 'page_title', px: 35 }],
  },
];
const tiedHighMatch = matchPresetStyle({
  styleName: 'tie shared report card',
  structureData: {
    actual_colors: { '#123456': { fill_count: 8, area_weight: 1 } },
    component_styles: { shadow: false, gradient: false, border: true, rounded: false },
    content_layout_styles: [{ name: 'shared report card', description: 'tie shared report card' }],
  },
  profiles: tiedProfiles,
});
assert.strictEqual(tiedHighMatch.ambiguous, true, 'identical high-scoring profiles should be ambiguous');
assert.notStrictEqual(tiedHighMatch.confidence, 'high', 'ambiguous matches must not report high confidence');
assert.notStrictEqual(
  tiedHighMatch.applied_policy,
  'preset_execution_typography',
  'ambiguous matches must not apply preset execution typography',
);

const fallbackWithLargeBody = [
  { role: 'page_title', px: 184, tailwind: 'text-[184px]', source: 'extracted' },
  { role: 'body_text', px: 90, tailwind: 'text-[90px]', source: 'extracted' },
];
const cappedWithReference = resolveExecutionTypographyScale({
  normalization: {
    execution_policy: 'source_typography_with_extreme_display_guard',
    display_title_reference: [{ px: 184 }],
  },
  fallbackScale: fallbackWithLargeBody,
});
assert.strictEqual(cappedWithReference[0].px, 72, 'display-referenced page title should be capped');
assert.strictEqual(cappedWithReference[1].px, 90, 'non-page-title fallback sizes should not be capped');

const uncappedWithoutReference = resolveExecutionTypographyScale({
  normalization: {
    execution_policy: 'source_typography_with_extreme_display_guard',
    display_title_reference: [],
  },
  fallbackScale: fallbackWithLargeBody,
});
assert.strictEqual(uncappedWithoutReference[0].px, 184, 'page title should not be capped without display references');

console.log('preset style normalizer tests passed');
