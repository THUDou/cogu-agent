const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');
const { generateStyleSpec, generateTemplateSpec, deriveTypographyTokens } = require('../scripts/aggregate.js');

const spec = generateTemplateSpec({
  styleName: '红标现代商务',
  structureData: {
    slide_size: { width_px: 1280, height_px: 720, aspect_ratio: '16:9' },
    actual_colors: {
      '#FFFFFF': { fill_count: 10, text_count: 0, area_weight: 0.7 },
      '#C00000': { fill_count: 5, text_count: 1, area_weight: 0.1 },
      '#000000': { fill_count: 0, text_count: 20, area_weight: 0 },
    },
    fonts: {
      major: { ea: '梦源宋体 CN W27', latin: 'Source Han Sans' },
      minor: { ea: '思源黑体 CN Regular', latin: 'Source Han Sans' },
    },
    font_sizes: {
      free_shape: {
        dominant_pt: 24,
        common_sizes_pt: [24, 32, 138],
        dominant_font: '梦源宋体 CN W27',
      },
    },
    content_layout_styles: [
      {
        name: '流程内容页',
        subtype: 'content-timeline',
        semantic_type_guess: 'process',
        information_relation: '多个步骤按顺序推进',
        selection_rule: '适用于阶段、路径和流程',
        body_blocks: [],
        visual_blocks: [],
      },
    ],
  },
  vlmAnalysis: {
    analyses: [
      {
        visual_assets: [
          {
            visual_role: 'repeated_decoration',
            must_reuse: true,
            usage: '右上角点阵装饰，用于封面页和目录页',
            confidence: 'high',
          },
          {
            visual_role: 'content_image',
            must_reuse: false,
            usage: '普通内容配图，可替换',
            confidence: 'medium',
          },
        ],
        fixed_composition: [
          {
            page_type: 'cover',
            required_elements: ['年份水印', '底部波浪'],
            layout_rule: '年份在上，波浪在底部',
            avoid_rules: ['移除波浪'],
          },
        ],
        layout_semantics: [
          {
            layout_name: '三列流程页',
            page_role: 'content',
            semantic_type: 'process',
            content_scenario: '三阶段流程',
            information_relation: '从左到右推进',
            slot_structure: ['标题', '三列步骤'],
            selection_rule: '适用于三阶段流程',
          },
        ],
      },
    ],
  },
  imageMapData: {
    asset_roles: {
      background: [
        { role: 'background', path: 'images/bg_images/bg.png', confidence: 'high' },
      ],
      style_assets: [
        { role: 'edge_decoration', path: 'images/assets/corner.png', confidence: 'high' },
      ],
    },
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
      {
        path: 'images/assets/process-mark.png',
        role: 'edge_decoration',
        reuse_decision: 'must_reuse_for_style',
        page_roles: ['cover'],
        html_policy: { inject: true, css_class: 'style-asset-process-mark' },
        confidence: 'high',
        reason: 'VLM prompt batch tool analyzeWithVLM vlm_batch_failed',
      },
      {
        path: '../secrets.png',
        role: 'template_decoration',
        reuse_decision: 'optional_style_asset',
      },
      {
        path: 'C:/tmp/evil.png',
        role: 'template_decoration',
        reuse_decision: 'optional_style_asset',
      },
      {
        path: 'images//assets/bad.png',
        role: 'template_decoration',
        reuse_decision: 'optional_style_asset',
      },
      {
        path: 'images/assets/<bad>.png',
        role: 'template_decoration',
        reuse_decision: 'optional_style_asset',
      },
      {
        path: 'images/assets/content.png',
        role: 'content_photo',
        reuse_decision: 'optional_style_asset',
      },
      {
        path: 'images/assets/rejected-decision.png',
        role: 'template_decoration',
        reuse_decision: 'same_topic_content_only',
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

assert.strictEqual(spec.schema_version, 'ppt-template-spec-v1');
assert.strictEqual(spec.style_name, '红标现代商务');
assert.strictEqual(spec.asset_policy.slides, 'reference_only');
assert.ok(spec.colors.allowed.includes('#C00000'));
assert.strictEqual(spec.colors.primary, '#C00000');
assert.strictEqual(spec.colors.background, '#FFFFFF');
assert.strictEqual(spec.colors.text, '#000000');
assert.strictEqual(spec.layout_library[0].semantic_type, 'process');
assert.strictEqual(spec.layout_library[0].source, 'vlm');
assert.strictEqual(spec.fixed_composition.length, 1);
assert.strictEqual(spec.visual_assets.length, 1);
assert.ok(spec.visual_assets.some(asset => asset.source === 'image-map' && asset.role === 'background'));
assert.ok(!spec.visual_assets.some(asset => asset.source === 'vlm'));
assert.ok(!spec.visual_assets.some(asset => asset.role === 'edge_decoration'));
assert.ok(!spec.visual_assets.some(asset => asset.role === 'content_image'));
assert.strictEqual(spec.reusable_style_assets.length, 2);
assert.ok(spec.reusable_style_assets.some(asset => asset.path === 'images/assets/cloud.png'));
assert.ok(spec.reusable_style_assets.some(asset => asset.path === 'images/assets/process-mark.png'));
assert.strictEqual(
  spec.reusable_style_assets.find(asset => asset.path === 'images/assets/process-mark.png').reason,
  ''
);
assert.ok(!spec.reusable_style_assets.some(asset => asset.path.includes('photo.jpeg')));
assert.ok(!spec.reusable_style_assets.some(asset => asset.path.includes('secrets')));
assert.ok(!spec.reusable_style_assets.some(asset => asset.path.includes('evil')));
assert.ok(!spec.reusable_style_assets.some(asset => asset.path.includes('bad')));
assert.ok(!spec.reusable_style_assets.some(asset => asset.path.includes('content.png')));
assert.ok(!spec.reusable_style_assets.some(asset => asset.path.includes('rejected-decision')));
assert.ok(spec.hard_constraints.some(rule => rule.includes('slides/')));

// typography_tokens
// spec uses font_sizes.free_shape: dominant_pt=24, common_sizes_pt=[24,32,138]
// → allSizesPt=[24,32,138], headingPt=138, notePt=24, bodyPt=32 (middle, no body role)
assert.ok(spec.typography_tokens != null, 'typography_tokens should exist');
assert.strictEqual(spec.typography_tokens.heading_pt, 138);
assert.strictEqual(spec.typography_tokens.note_pt, 24);
assert.ok(Array.isArray(spec.typography_tokens.all_sizes_pt));
assert.ok(spec.typography_tokens.all_sizes_pt.includes(138));
assert.ok(spec.typography_tokens.all_sizes_pt.includes(24));
assert.strictEqual(spec.typography_tokens.body_pt, 32);
assert.ok(spec.execution_tokens != null, 'execution_tokens should exist');
assert.strictEqual(spec.execution_tokens.typography_scale.length, 5);
assert.deepStrictEqual(
  spec.execution_tokens.typography_scale.map(item => item.role),
  ['page_title', 'section_title', 'subsection_text', 'body_text', 'note_text'],
);
assert.ok(spec.execution_tokens.typography_scale.every(item => item.tailwind.startsWith('text-[')));
assert.strictEqual(spec.execution_tokens.rules.forbid_undefined_font_sizes, true);
for (const item of spec.execution_tokens.typography_scale) {
  if (item.source === 'extracted' && Number.isFinite(item.pt)) {
    assert.strictEqual(item.px, Math.round(item.pt * 4 / 3));
  }
}

const fallback = generateTemplateSpec({
  styleName: '兜底',
  structureData: {
    content_layout_styles: [
      {
        name: '图文页',
        semantic_type_guess: 'image_text',
        information_relation: '图片提供证据，文字解释观点',
        selection_rule: '适用于单图说明',
      },
    ],
  },
  vlmAnalysis: {},
  imageMapData: {},
});
assert.strictEqual(fallback.layout_library[0].semantic_type, 'image_text');
assert.strictEqual(fallback.layout_library[0].source, 'tool');

const nullFontSizeSpec = generateTemplateSpec({
  structureData: {
    font_sizes: {
      title: null,
    },
  },
});
assert.deepStrictEqual(nullFontSizeSpec.font_scale[0], {
  role: 'title',
  dominant_pt: null,
  common_sizes_pt: [],
  dominant_font: '',
});

// typography_tokens is null when font_scale is empty
assert.strictEqual(deriveTypographyTokens([]), null, 'empty font_scale yields null tokens');
assert.strictEqual(deriveTypographyTokens(null), null, 'null font_scale yields null tokens');

// body_pt role-matching branch
const withBodyRole = deriveTypographyTokens([
  { role: 'title', dominant_pt: 40 },
  { role: 'body', dominant_pt: 20 },
  { role: 'note', dominant_pt: 10 },
]);
assert.ok(withBodyRole != null, 'tokens exist with body role');
assert.strictEqual(withBodyRole.body_pt, 20, 'body_pt from body-role item');
assert.strictEqual(withBodyRole.heading_pt, 40, 'heading_pt is max');
assert.strictEqual(withBodyRole.note_pt, 10, 'note_pt is min');

const md = generateStyleSpec({
  styleName: 'Demo',
  structureData: {},
  vlmAnalysis: {},
  imageMapData: {},
});
assert.ok(md.includes('## 附：机器可读模板产物'));
assert.ok(md.includes('template-spec.json'));
assert.ok(md.includes('template-manifest.json'));
assert.ok(md.includes('html-templates/'));

const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'template-spec-reusable-'));
const structurePath = path.join(tempDir, 'template_data.json');
const markdownPath = path.join(tempDir, 'style.md');
const specPath = path.join(tempDir, 'template-spec.json');
const reusablePath = path.join(tempDir, 'reusable-style-assets.json');
fs.writeFileSync(structurePath, JSON.stringify({ slide_size: { width_px: 1280, height_px: 720 } }), 'utf-8');
fs.writeFileSync(reusablePath, JSON.stringify({
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
    {
      path: 'images/bg_images/texture.png',
      role: 'background_texture',
      reuse_decision: 'must_reuse_for_style',
      page_roles: ['cover'],
      confidence: 'high',
      reason: 'VLM prompt batch tool analyzeWithVLM vlm_batch_failed',
    },
    {
      path: '/tmp/absolute.png',
      role: 'template_decoration',
      reuse_decision: 'optional_style_asset',
    },
    {
      path: 'images/assets/../bad.png',
      role: 'template_decoration',
      reuse_decision: 'optional_style_asset',
    },
    {
      path: 'images/assets/"quoted".png',
      role: 'template_decoration',
      reuse_decision: 'optional_style_asset',
    },
    {
      path: 'images/assets/chart.png',
      role: 'content_photo',
      reuse_decision: 'optional_style_asset',
    },
    {
      path: 'images/assets/uncertain.png',
      role: 'template_decoration',
      reuse_decision: 'uncertain',
    },
  ],
  rejected_assets: [
    {
      path: 'images/assets/photo.jpeg',
      role: 'content_photo',
      reuse_decision: 'same_topic_content_only',
    },
  ],
}), 'utf-8');
execFileSync(process.execPath, [
  path.join(__dirname, '..', 'scripts', 'aggregate.js'),
  structurePath,
  markdownPath,
  `--template-spec=${specPath}`,
  `--reusable-style-assets=${reusablePath}`,
], { stdio: 'pipe' });
const fileSpec = JSON.parse(fs.readFileSync(specPath, 'utf-8'));
assert.strictEqual(fileSpec.reusable_style_assets.length, 2);
assert.ok(fileSpec.reusable_style_assets.some(asset => asset.path === 'images/assets/cloud.png'));
assert.ok(fileSpec.reusable_style_assets.some(asset => asset.path === 'images/bg_images/texture.png'));
assert.strictEqual(
  fileSpec.reusable_style_assets.find(asset => asset.path === 'images/bg_images/texture.png').reason,
  ''
);
assert.ok(!fileSpec.reusable_style_assets.some(asset => asset.path.includes('photo.jpeg')));
assert.ok(!fileSpec.reusable_style_assets.some(asset => asset.path.includes('absolute')));
assert.ok(!fileSpec.reusable_style_assets.some(asset => asset.path.includes('bad')));
assert.ok(!fileSpec.reusable_style_assets.some(asset => asset.path.includes('quoted')));
assert.ok(!fileSpec.reusable_style_assets.some(asset => asset.path.includes('chart')));
assert.ok(!fileSpec.reusable_style_assets.some(asset => asset.path.includes('uncertain')));
const fileMd = fs.readFileSync(markdownPath, 'utf-8');
assert.ok(fileMd.includes('Reusable style image assets'));
assert.ok(fileMd.includes('images/assets/cloud.png'));
assert.ok(fileMd.includes('images/bg_images/texture.png'));
assert.ok(!fileMd.includes('images/assets/photo.jpeg'));
assert.ok(!fileMd.includes('/tmp/absolute.png'));
assert.ok(!fileMd.includes('images/assets/../bad.png'));
assert.ok(!fileMd.includes('images/assets/"quoted".png'));
assert.ok(!fileMd.includes('images/assets/chart.png'));
assert.ok(!fileMd.includes('images/assets/uncertain.png'));
assert.ok(!fileMd.includes('analyzeWithVLM'));
assert.ok(!fileMd.includes('vlm_batch_failed'));

console.log('template_spec tests passed');
