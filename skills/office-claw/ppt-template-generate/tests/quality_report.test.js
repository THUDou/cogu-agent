const assert = require('assert');
const { generateQualityReport } = require('../scripts/quality-report.js');

const report = generateQualityReport({
  skipVlm: false,
  structureData: {
    actual_colors: {
      '#C00000': {},
      '#FFFFFF': {},
    },
    content_layout_styles: [{ id: 'content-style-01' }],
  },
  vlmAnalysis: {
    analyses: [
      {
        fixed_composition: [],
        layout_semantics: [{ layout_name: '流程页' }],
        '配色方案': {
          '主色调': '深红 #B22234',
          '背景色': '白色 #FFFFFF',
        },
      },
    ],
  },
});

assert.strictEqual(report.vlm.enabled, true);
assert.strictEqual(report.vlm.has_fixed_composition, false);
assert.strictEqual(report.vlm.has_layout_semantics, true);
assert.deepStrictEqual(report.vlm.missing_required_fields, ['fixed_composition']);
assert.strictEqual(report.vlm.fell_back_to_tool_layouts, false);
assert.deepStrictEqual(report.colors.filtered_vlm_hexes, ['#B22234']);
assert.strictEqual(report.asset_policy.slides, 'reference_only');
assert.strictEqual(report.asset_policy.images_assets, 'optional_reference');
assert.strictEqual(report.asset_policy.bg_images, 'reuse_when_present');

const skipped = generateQualityReport({
  skipVlm: true,
  structureData: { content_layout_styles: [{ id: 'fallback' }] },
  vlmAnalysis: {},
  vlmFallbackReason: 'VLM API 未配置',
});
assert.strictEqual(skipped.vlm.enabled, false);
assert.strictEqual(skipped.vlm.fell_back_to_tool_layouts, true);
assert.strictEqual(skipped.vlm.fallback_reason, 'VLM API 未配置');

const reusableStyleAssets = {
  schema_version: 'reusable-style-assets-v1',
  assets: [{ path: 'images/assets/cloud.png', role: 'template_decoration' }],
  rejected_assets: [{ path: 'images/assets/photo.jpeg', role: 'content_photo' }],
};

const withAssets = generateQualityReport({
  skipVlm: false,
  structureData: { content_layout_styles: [] },
  vlmAnalysis: { analyses: [{ fixed_composition: [{}], layout_semantics: [] }] },
  reusableStyleAssets,
});
assert.strictEqual(withAssets.reusable_style_assets.enabled, true);
assert.strictEqual(withAssets.reusable_style_assets.assets, 1);
assert.strictEqual(withAssets.reusable_style_assets.rejected_assets, 1);

const normalizedReport = generateQualityReport({
  skipVlm: false,
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
        fixed_composition: [{}],
        layout_semantics: [{ layout_name: '商务卡片' }],
        '配色方案': { '主色调': '红色 #C00000', '背景色': '白色 #FFFFFF' },
        '视觉风格': { '整体风格': '红色 商务 简约 汇报' },
      },
    ],
  },
});

assert.strictEqual(normalizedReport.typography_normalization.preset_style.selected_profile_id, 'business-classic');
assert.strictEqual(normalizedReport.typography_normalization.execution_policy, 'preset_execution_typography');
assert.strictEqual(normalizedReport.typography_normalization.display_title_reference_count, 1);

console.log('quality_report tests passed');
