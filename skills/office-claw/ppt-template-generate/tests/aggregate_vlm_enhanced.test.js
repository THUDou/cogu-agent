const assert = require('assert');
const { generateStyleSpec } = require('../scripts/aggregate.js');

const md = generateStyleSpec({
  styleName: 'Test Style',
  structureData: {
    slide_size: {
      width_px: 1280,
      height_px: 720,
      width_cm: 33.87,
      height_cm: 19.05,
      aspect_ratio: '16:9',
    },
    fonts: {},
    font_sizes: {},
    para_alignment: {},
    layouts: [],
    master: {},
    component_styles: {},
    content_layout_styles: [],
  },
  vlmAnalysis: {
    analyses: [
      {
        schema_version: 'ppt-template-vlm-enhanced-v1',
        fixed_composition: [
          {
            page_type: 'cover',
            required_elements: ['top watermark', 'center title frame', 'bottom wave'],
            layout_rule: 'title stays inside the center frame',
            avoid_rules: 'do not replace the page skeleton with a generic card layout',
          },
        ],
        layout_semantics: [
          {
            page: 2,
            layout_name: 'three step progression',
            page_role: 'content',
            semantic_type: 'progressive',
            content_scenario: 'stage, roadmap, capability evolution',
            information_relation: 'left to right progression',
            slot_structure: 'three parallel modules with number, title, explanation',
            selection_rule: 'use when content contains three ordered steps',
            title_position: 'upper left',
            body_structure: 'three equal columns',
            visual_structure: 'small emphasis marks only',
            avoid_rules: 'do not center the title',
          },
        ],
        replication_rules: [
          'content page title stays upper left',
          'content page title stays upper left',
          'body copy is left aligned',
        ],
        corrections: [
          {
            target: 'color.primary',
            observed: 'tool may over-count black body text',
            recommendation: 'use red as the dominant visual color',
            reason: 'red carries the brand and section emphasis',
            priority: 'high',
          },
        ],
        visual_assets: [
          {
            page: 1,
            visual_role: 'background_texture',
            must_reuse: true,
            usage: 'Full-page texture from VLM should not become a required asset.',
            confidence: 'high',
          },
          {
            page: 2,
            visual_role: 'content_image',
            must_reuse: false,
            usage: 'replaceable content image',
            confidence: 'medium',
          },
        ],
      },
    ],
  },
  reusableStyleAssets: {
    schema_version: 'reusable-style-assets-v1',
    assets: [
      {
        path: 'images/assets/cloud.png',
        role: 'template_decoration',
        reuse_decision: 'optional_style_asset',
        page_roles: ['content'],
        html_policy: { inject: true, css_class: 'style-asset-cloud' },
        confidence: 'high',
        reason: 'title cloud decoration',
      },
    ],
    rejected_assets: [
      {
        path: 'images/assets/photo.jpeg',
        role: 'content_photo',
        reuse_decision: 'same_topic_content_only',
      },
    ],
  },
});

assert.ok(md.includes('top watermark'));
assert.ok(md.includes('three step progression'));
assert.ok(md.includes('left to right progression'));
assert.ok(md.includes('use when content contains three ordered steps'));
assert.ok(md.includes('color.primary'));
assert.ok(md.includes('use red as the dominant visual color'));
assert.ok(md.includes('images/bg_images'));
assert.ok(md.includes('images/assets/cloud.png'));
assert.ok(md.includes('title cloud decoration'));
assert.ok(!md.includes('images/assets/photo.jpeg'));
assert.ok(md.includes('`slides/`'));
assert.ok(!md.includes('Full-page texture from VLM should not become a required asset.'));
assert.ok(!md.includes('replaceable content image'));
assert.ok(!md.includes('asset_classifications'));
assert.ok(!md.includes('Image 1 is the complete slide screenshot'));
assert.ok(!md.includes('VLM'));

const fontMd = generateStyleSpec({
  styleName: 'Font Test',
  structureData: {
    fonts: {},
    font_sizes: {
      free_shape: {
        dominant_font: 'Source Han Serif',
        dominant_pt: 138,
        common_sizes_pt: [138, 32, 24],
      },
    },
  },
});
assert.ok(fontMd.includes('138pt'));

const gradientMd = generateStyleSpec({
  styleName: 'Gradient Test',
  structureData: {
    fonts: {},
    component_styles: {
      gradient: {
        count: 1,
        examples: [
          {
            stops: [
              { position_pct: 0 },
              { color: '#C00000', position_pct: 100 },
            ],
            angle_deg: 90,
          },
        ],
      },
    },
  },
});
assert.ok(!gradientMd.includes('undefined@'));

console.log('aggregate_vlm_enhanced tests passed');

const { buildSpec } = require('../scripts/aggregate.js');

const specNearWhite = buildSpec(
  {
    slide_size: { width_px: 1280, height_px: 720, width_cm: 33.87, height_cm: 19.05, aspect_ratio: '16:9' },
    fonts: {}, font_sizes: {}, para_alignment: {}, layouts: [], master: {},
    component_styles: {}, content_layout_styles: [],
    actual_colors: {
      '#D29D88': { fill_count: 110, area_weight: 0.6, text_count: 5 },
      '#F5F5F5': { fill_count: 18, area_weight: 0.38, text_count: 0 },
    },
  },
  { analyses: [] },
  {},
  'TestStyle',
);
assert.equal(specNearWhite.colors.background.toUpperCase(), '#F5F5F5', 'near-white should be background');
assert.notEqual(specNearWhite.colors.background.toUpperCase(), specNearWhite.colors.primary.toUpperCase(), 'background must differ from primary');

const specVlmBg = buildSpec(
  {
    slide_size: { width_px: 1280, height_px: 720, width_cm: 33.87, height_cm: 19.05, aspect_ratio: '16:9' },
    fonts: {}, font_sizes: {}, para_alignment: {}, layouts: [], master: {},
    component_styles: {}, content_layout_styles: [],
    actual_colors: {
      '#D29D88': { fill_count: 110, area_weight: 0.6, text_count: 5 },
    },
  },
  {
    analyses: [{
      schema_version: 'ppt-template-vlm-enhanced-v1',
      配色方案: { 背景色: '#FAFAFA' },
      fixed_composition: [], layout_semantics: [], replication_rules: [],
      visual_corrections: [],
    }],
  },
  {},
  'TestStyle',
);
assert.equal(specVlmBg.colors.background.toUpperCase(), '#FAFAFA', 'VLM bg should take priority');

console.log('selectColors background detection tests passed');

const { buildSpec: buildSpec2 } = require('../scripts/aggregate.js');

const specWithBgPath = buildSpec2(
  {
    slide_size: { width_px: 1280, height_px: 720, width_cm: 33.87, height_cm: 19.05, aspect_ratio: '16:9' },
    fonts: {}, font_sizes: {}, para_alignment: {}, layouts: [], master: {},
    component_styles: {}, content_layout_styles: [], actual_colors: {},
  },
  { analyses: [] },
  {
    asset_roles: {
      background: [{ path: 'bg_images/slide_001_shape_bg.png', confidence: 'high' }],
    },
  },
  'TestStyle',
);
const bgAsset = specWithBgPath.visual_assets?.[0];
assert.ok(bgAsset, 'should have a visual_asset entry');
assert.ok(
  bgAsset.path.startsWith('images/'),
  `path should start with images/ but got: ${bgAsset.path}`,
);

console.log('buildVisualAssets path normalisation tests passed');
