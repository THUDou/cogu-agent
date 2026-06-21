const assert = require('assert');
const {
  buildExecutionTypographyScale,
  generateStyleSpec,
  generateTemplateSpec,
} = require('../scripts/aggregate.js');

const threeSizeScale = buildExecutionTypographyScale([
  {
    role: 'free_shape',
    dominant_pt: 28,
    common_sizes_pt: [28, 11, 44],
    dominant_font: 'Aa细黑',
  },
]);

assert.strictEqual(threeSizeScale.length, 5);
assert.deepStrictEqual(
  threeSizeScale.map(item => item.role),
  ['page_title', 'section_title', 'subsection_text', 'body_text', 'note_text'],
);
assert.deepStrictEqual(
  threeSizeScale.map(item => item.px),
  [59, 44, 37, 28, 15],
);
assert.strictEqual(threeSizeScale[0].source, 'extracted');
assert.strictEqual(threeSizeScale[1].source, 'inferred');
assert.strictEqual(threeSizeScale[2].source, 'extracted');
assert.strictEqual(threeSizeScale[3].source, 'inferred');
assert.strictEqual(threeSizeScale[4].source, 'extracted');
assert.strictEqual(threeSizeScale[0].tailwind, 'text-[59px]');

const fiveSizeScale = buildExecutionTypographyScale([
  {
    role: 'free_shape',
    common_sizes_pt: [45, 34, 25, 18, 11],
  },
]);
assert.deepStrictEqual(
  fiveSizeScale.map(item => item.px),
  [60, 45, 33, 24, 15],
);
assert.ok(fiveSizeScale.every(item => item.source === 'extracted'));

const md = generateStyleSpec({
  styleName: 'Typography Exec Test',
  structureData: {
    fonts: {},
    font_sizes: {
      free_shape: {
        dominant_font: 'Aa细黑',
        dominant_pt: 28,
        common_sizes_pt: [28, 11, 44],
      },
    },
    para_alignment: {
      free_shape: {
        dominant: 'PP_ALIGN.LEFT (1)',
        counts: { 'PP_ALIGN.LEFT (1)': 3 },
      },
    },
  },
});

for (const cls of ['text-[59px]', 'text-[44px]', 'text-[37px]', 'text-[28px]', 'text-[15px]']) {
  assert.ok(md.includes(`\`${cls}\``), `Markdown should contain ${cls}`);
}
assert.ok(md.includes('禁止自行创造未列出的字号'));
assert.ok(md.includes('正文不得降级为辅助字号'));
assert.ok(md.includes('## 六、生成检查清单'));
assert.ok(md.includes('是否没有出现未定义字号'));
assert.ok(md.includes('## 附录：抽取依据'));

const fontSectionMatch = md.match(/## [^\n]*字体与字号/);
const fontSectionIndex = fontSectionMatch ? fontSectionMatch.index : -1;
const appendixIndex = md.indexOf('## 附录：抽取依据');
assert.ok(fontSectionIndex >= 0, 'main font section should exist');
assert.ok(appendixIndex > fontSectionIndex, 'appendix should come after main font section');
const nextSectionIndex = md.indexOf('\n## ', fontSectionIndex + 1);
assert.ok(nextSectionIndex > fontSectionIndex, 'main font section should end before the next top-level section');
const mainFontSection = md.slice(fontSectionIndex, nextSectionIndex);
assert.ok(!mainFontSection.includes('free_shape'), 'main font section should hide internal role names');

const spec = generateTemplateSpec({
  styleName: 'Typography Exec Test',
  structureData: {
    font_sizes: {
      free_shape: {
        dominant_font: 'Aa细黑',
        dominant_pt: 28,
        common_sizes_pt: [28, 11, 44],
      },
    },
  },
});

assert.ok(spec.execution_tokens);
assert.strictEqual(spec.execution_tokens.typography_scale.length, 5);
assert.strictEqual(spec.execution_tokens.typography_scale[1].source, 'inferred');
assert.strictEqual(spec.execution_tokens.rules.forbid_undefined_font_sizes, true);
assert.deepStrictEqual(spec.execution_tokens.rules.overflow_strategy, [
  'shorten_text',
  'split_page',
  'change_layout',
]);

const unrelatedMd = generateStyleSpec({
  styleName: 'Unrelated Empty Style',
  structureData: {
    fonts: {},
    actual_colors: {},
    component_styles: {},
    content_layout_styles: [],
    font_sizes: {
      free_shape: {
        dominant_font: 'Arial',
        dominant_pt: 28,
        common_sizes_pt: [28, 11, 44],
      },
    },
  },
  vlmAnalysis: { analyses: [] },
});

assert.ok(!unrelatedMd.includes('business-classic'), 'Unrelated Markdown should not mention preset ids');
assert.ok(
  !unrelatedMd.includes('预设风格匹配与字号归一化'),
  'Unrelated Markdown should not render preset matching section',
);
for (const cls of ['text-[59px]', 'text-[44px]', 'text-[37px]', 'text-[28px]', 'text-[15px]']) {
  assert.ok(unrelatedMd.includes(`\`${cls}\``), `Unrelated Markdown should preserve extracted class ${cls}`);
}

const presetMd = generateStyleSpec({
  styleName: '红色商务简约',
  structureData: {
    actual_colors: {
      '#C00000': { fill_count: 12, area_weight: 0.42 },
      '#FFFFFF': { fill_count: 8, area_weight: 0.46 },
      '#222222': { text_count: 20, area_weight: 0.1 },
    },
    component_styles: { shadow: false, gradient: false, border: true, rounded: false },
    content_layout_styles: [
      { name: '商务汇报卡片', description: '红色商务简约汇报页面，白底卡片和标题栏' },
    ],
    fonts: {},
    font_sizes: {
      free_shape: {
        dominant_font: 'Alibaba PuHuiTi',
        dominant_pt: 138,
        common_sizes_pt: [138, 44, 28, 14],
      },
    },
  },
  vlmAnalysis: {
    analyses: [
      {
        '配色方案': { '主色调': '红色 #C00000', '背景色': '白色 #FFFFFF' },
        '视觉风格': { '整体风格': '红色 商务 简约 汇报' },
      },
    ],
  },
});

assert.ok(presetMd.includes('business-classic'), 'Markdown should mention matched preset id');
for (const cls of ['text-[35px]', 'text-[23px]', 'text-[21px]', 'text-[19px]', 'text-[16px]']) {
  assert.ok(presetMd.includes(`\`${cls}\``), `Markdown should contain preset class ${cls}`);
}
assert.ok(presetMd.includes('text-[184px]'), 'Markdown appendix should preserve extracted display reference');

const presetSpec = generateTemplateSpec({
  styleName: '红色商务简约',
  structureData: {
    actual_colors: {
      '#C00000': { fill_count: 12, area_weight: 0.42 },
      '#FFFFFF': { fill_count: 8, area_weight: 0.46 },
      '#222222': { text_count: 20, area_weight: 0.1 },
    },
    component_styles: { shadow: false, gradient: false, border: true, rounded: false },
    content_layout_styles: [
      { name: '商务汇报卡片', description: '红色商务简约汇报页面，白底卡片和标题栏' },
    ],
    font_sizes: {
      free_shape: {
        dominant_font: 'Alibaba PuHuiTi',
        dominant_pt: 138,
        common_sizes_pt: [138, 44, 28, 14],
      },
    },
  },
  vlmAnalysis: {
    analyses: [
      {
        '配色方案': { '主色调': '红色 #C00000', '背景色': '白色 #FFFFFF' },
        '视觉风格': { '整体风格': '红色 商务 简约 汇报' },
      },
    ],
  },
});

assert.strictEqual(presetSpec.preset_style_match.selected_profile_id, 'business-classic');
assert.strictEqual(presetSpec.typography_normalization.execution_policy, 'preset_execution_typography');
assert.deepStrictEqual(
  presetSpec.execution_font_scale.map(item => item.px),
  [35, 23, 21, 19, 16],
);
assert.strictEqual(presetSpec.source_font_scale[0].dominant_pt, 138);
assert.ok(presetSpec.typography_normalization.display_title_reference.some(item => item.px === 184));
assert.strictEqual(presetSpec.execution_tokens.typography_scale[0].source, 'preset');

console.log('typography execution token tests passed');
