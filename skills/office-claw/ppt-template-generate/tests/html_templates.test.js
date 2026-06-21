const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { generateHtmlTemplates, validateTemplatePackage } = require('../scripts/generate-html-templates.js');

// ── 基础 spec，有背景图 + 一个 style-asset + decoration-map ─────────────────
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ppt-base-'));
fs.mkdirSync(path.join(root, 'images', 'bg_images'), { recursive: true });
fs.mkdirSync(path.join(root, 'images', 'assets'), { recursive: true });
fs.writeFileSync(path.join(root, 'images', 'bg_images', 'bg.png'), 'same-background-bytes');
fs.writeFileSync(path.join(root, 'images', 'assets', 'bg-copy.png'), 'same-background-bytes');
fs.writeFileSync(path.join(root, 'images', 'assets', 'cloud.png'), 'cloud-bytes');

// 写 decoration-map 到 temp/
const decorTempDir = path.join(root, 'temp');
fs.mkdirSync(decorTempDir, { recursive: true });
fs.writeFileSync(path.join(decorTempDir, 'decoration-map.json'), JSON.stringify({
  schema_version: 'decoration-map-v1',
  decorations: [
    {
      id: 'decor-wave',
      css: '.decor-wave { position: absolute; bottom: 0; left: 0; width: 100%; height: 20%; background: var(--color-primary); }',
      html: '<div class="decor decor-wave"></div>',
      source_description: 'wave',
    },
  ],
  page_role_map: { cover: ['decor-wave'], section: [], content: [], closing: [] },
}), 'utf-8');

const spec = {
  schema_version: 'ppt-template-spec-v1',
  style_name: 'Base Test',
  slide_size: { width_px: 1280, height_px: 720 },
  colors: { primary: '#AA0000', background: '#FFFFFF', text: '#222222', allowed: ['#AA0000', '#FFFFFF', '#222222'] },
  fonts: { title: 'Source Han Serif', body: 'Source Han Sans' },
  font_scale: [
    { role: 'title', dominant_pt: 44 },
    { role: 'body', dominant_pt: 28 },
  ],
  fixed_composition: [
    { page_type: 'cover', layout_rule: 'center title' },
    { page_type: 'section', layout_rule: 'chapter title' },
    { page_type: 'closing', layout_rule: 'thank you' },
  ],
  layout_library: [
    { id: 'layout-01', page_role: 'content', semantic_type: 'comparison', source: 'vlm',
      name: 'Compare', selection_rule: 'comparison', slot_structure: ['left', 'right'] },
  ],
  visual_assets: [
    { path: 'images/bg_images/bg.png', role: 'background', policy: 'reuse_by_role' },
  ],
  reusable_style_assets: [
    {
      path: 'images/assets/bg-copy.png',
      role: 'background_texture',
      reuse_decision: 'must_reuse_for_style',
      page_roles: ['content'],
      placement: { left_pct: 0, top_pct: 0.4, width_pct: 100, height_pct: 99.2 },
      html_policy: { inject: true, css_class: 'style-asset-bg-copy', page_roles: ['content'] },
      confidence: 'high',
    },
    {
      path: 'images/assets/cloud.png',
      role: 'template_decoration',
      reuse_decision: 'optional_style_asset',
      page_roles: ['content'],
      placement: { left_pct: 80, top_pct: 8, width_pct: 6, height_pct: 5 },
      html_policy: { inject: true, css_class: 'style-asset-cloud', page_roles: ['content'] },
      confidence: 'high',
    },
  ],
};

const manifest = generateHtmlTemplates(spec, root);

// ── v2 manifest 结构 ───────────────────────────────────────────────────────
assert.strictEqual(manifest.schema_version, 'ppt-template-manifest-v2', 'v2 schema_version');
assert.strictEqual(manifest.mode, 'base', 'mode: base');
assert.ok(Array.isArray(manifest.bases), 'bases is array');
assert.ok(manifest.bases.some(b => b.page_role === 'cover'), 'has cover base');
assert.ok(manifest.bases.some(b => b.page_role === 'section'), 'has section base');
assert.ok(manifest.bases.some(b => b.page_role === 'content'), 'has content base');
assert.ok(manifest.bases.some(b => b.page_role === 'closing'), 'has closing base');

// ── 生成 base HTML 文件，不再生成 v1 骨架 ─────────────────────────────────
assert.ok(fs.existsSync(path.join(root, 'html-templates', 'cover-base.html')), 'cover-base.html exists');
assert.ok(fs.existsSync(path.join(root, 'html-templates', 'section-base.html')), 'section-base.html exists');
assert.ok(fs.existsSync(path.join(root, 'html-templates', 'content-base.html')), 'content-base.html exists');
assert.ok(fs.existsSync(path.join(root, 'html-templates', 'closing-base.html')), 'closing-base.html exists');
assert.ok(!fs.existsSync(path.join(root, 'html-templates', 'layout-01.html')), 'no layout-01.html');
assert.ok(!fs.existsSync(path.join(root, 'html-templates', 'cover.html')), 'no old cover.html');
assert.ok(!fs.existsSync(path.join(root, 'html-templates', 'content-default.html')), 'no content-default.html');

// ── cover-base.html 内容验证 ───────────────────────────────────────────────
const coverHtml = fs.readFileSync(path.join(root, 'html-templates', 'cover-base.html'), 'utf-8');
assert.ok(coverHtml.includes('content="cover-base"'), 'cover-base meta template-id');
assert.ok(coverHtml.includes('data-page-role="cover"'), 'cover-base data-page-role');
assert.ok(coverHtml.includes('data-template-id="cover-base"'), 'cover-base data-template-id');
assert.ok(coverHtml.includes('template-assets'), 'cover-base has template-assets div');
assert.ok(!coverHtml.includes('template-layer'), 'no template-layer in cover-base');
assert.ok(!coverHtml.includes('data-slot='), 'no data-slot in cover-base');
assert.ok(coverHtml.includes('../images/bg_images/bg.png'), 'cover-base has background image');
assert.ok(coverHtml.includes('template-bg-image'), 'cover-base has template-bg-image class');

// CSS 变量含 px ──────────────────────────────────────────────────────────────
assert.ok(coverHtml.includes('--font-size-title-px: 59px'), 'title px (44pt→59px)');
assert.ok(coverHtml.includes('--font-size-body-px: 37px'), 'body px (28pt→37px)');
assert.ok(coverHtml.includes('--font-size-title: 44pt'), 'title pt retained');

// decoration-map 注入 cover ──────────────────────────────────────────────────
assert.ok(coverHtml.includes('decor-wave'), 'cover has decor-wave from decoration-map');

// ── content-base.html：style-asset 注入（有 placement + page_roles: content）
const contentHtml = fs.readFileSync(path.join(root, 'html-templates', 'content-base.html'), 'utf-8');
assert.ok(!contentHtml.includes('../images/assets/bg-copy.png'), 'duplicate background asset NOT injected in content-base');
assert.ok(!contentHtml.includes('style-asset-bg-copy'), 'duplicate background class NOT in content-base');
assert.ok(contentHtml.includes('../images/assets/cloud.png'), 'cloud style-asset in content-base');
assert.ok(contentHtml.includes('style-asset-cloud'), 'style-asset class in content-base');
assert.ok(contentHtml.includes('left:80%'), 'placement left in content-base');
assert.ok(contentHtml.includes('top:8%'), 'placement top in content-base');

// style-asset 不应出现在 cover（page_roles 仅 content）──────────────────────
assert.ok(!coverHtml.includes('../images/assets/cloud.png'), 'cloud NOT in cover-base');

// ── validateTemplatePackage v2 通过 ────────────────────────────────────────
const pkgResult = validateTemplatePackage(root);
assert.ok(pkgResult.ok, `validateTemplatePackage v2 pass: ${pkgResult.errors.join('; ')}`);

// ── validateTemplatePackage v2 失败：HTML 文件缺失 ─────────────────────────
const brokenRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'ppt-broken-'));
fs.mkdirSync(path.join(brokenRoot, 'html-templates'), { recursive: true });
fs.writeFileSync(path.join(brokenRoot, 'template-manifest.json'), JSON.stringify({
  schema_version: 'ppt-template-manifest-v2',
  mode: 'base',
  bases: [{ page_role: 'cover', file: 'html-templates/cover-base.html' }],
}));
const brokenResult = validateTemplatePackage(brokenRoot);
assert.strictEqual(brokenResult.ok, false, 'should fail when HTML missing');
assert.ok(brokenResult.errors.some(e => e.includes('cover')), `expected cover error, got: ${brokenResult.errors}`);

// ── toc page_type → section base ────────────────────────────────────────────
const tocRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'ppt-toc-'));
const tocManifest = generateHtmlTemplates({
  schema_version: 'ppt-template-spec-v1',
  style_name: 'Toc',
  slide_size: { width_px: 1280, height_px: 720 },
  colors: { primary: '#AA0000', background: '#FFFFFF', text: '#222222', allowed: [] },
  fonts: { title: 'Sans', body: 'Sans' },
  font_scale: [],
  fixed_composition: [{ page_type: 'toc', layout_rule: 'chapter list' }],
  layout_library: [],
  visual_assets: [],
}, tocRoot);
assert.ok(tocManifest.bases.some(b => b.page_role === 'section'), 'toc → section base');

// ── typography_tokens 优先于 font_scale ──────────────────────────────────────
const tokRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'ppt-tok-'));
generateHtmlTemplates({
  schema_version: 'ppt-template-spec-v1',
  style_name: 'Tok',
  slide_size: { width_px: 1280, height_px: 720 },
  colors: { primary: '#AA0000', background: '#FFFFFF', text: '#222222', allowed: [] },
  fonts: { title: 'Sans', body: 'Sans' },
  font_scale: [{ role: 'title', dominant_pt: 34 }, { role: 'body', dominant_pt: 18 }],
  typography_tokens: { heading_pt: 40, body_pt: 22, note_pt: 10 },
  fixed_composition: [{ page_type: 'cover', layout_rule: 'test' }],
  layout_library: [],
  visual_assets: [],
}, tokRoot);
const tokCover = fs.readFileSync(path.join(tokRoot, 'html-templates', 'cover-base.html'), 'utf-8');
assert.ok(tokCover.includes('--font-size-title: 40pt'), 'typography_tokens heading_pt=40 wins');
assert.ok(!tokCover.includes('34pt'), 'font_scale 34pt not used when tokens present');

const execRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'ppt-exec-typography-'));
generateHtmlTemplates({
  schema_version: 'ppt-template-spec-v1',
  style_name: 'Exec Typography',
  slide_size: { width_px: 1280, height_px: 720 },
  colors: { primary: '#AA0000', background: '#FFFFFF', text: '#222222', allowed: [] },
  fonts: { title: 'Sans', body: 'Sans' },
  font_scale: [{ role: 'title', dominant_pt: 138 }, { role: 'body', dominant_pt: 28 }],
  typography_tokens: { heading_pt: 138, body_pt: 28, note_pt: 14 },
  execution_font_scale: [
    { role: 'page_title', px: 35, tailwind: 'text-[35px]', source: 'preset' },
    { role: 'section_title', px: 23, tailwind: 'text-[23px]', source: 'preset' },
    { role: 'subsection_text', px: 21, tailwind: 'text-[21px]', source: 'preset' },
    { role: 'body_text', px: 19, tailwind: 'text-[19px]', source: 'preset' },
    { role: 'note_text', px: 16, tailwind: 'text-[16px]', source: 'preset' },
  ],
  execution_tokens: {
    typography_scale: [
      { role: 'page_title', px: 35, tailwind: 'text-[35px]', source: 'preset' },
      { role: 'section_title', px: 23, tailwind: 'text-[23px]', source: 'preset' },
      { role: 'subsection_text', px: 21, tailwind: 'text-[21px]', source: 'preset' },
      { role: 'body_text', px: 19, tailwind: 'text-[19px]', source: 'preset' },
      { role: 'note_text', px: 16, tailwind: 'text-[16px]', source: 'preset' },
    ],
  },
  fixed_composition: [{ page_type: 'cover', layout_rule: 'test' }],
  layout_library: [],
  visual_assets: [],
}, execRoot);
const execCover = fs.readFileSync(path.join(execRoot, 'html-templates', 'cover-base.html'), 'utf-8');
assert.ok(execCover.includes('--font-size-title-px: 35px'), 'execution page_title px wins');
assert.ok(execCover.includes('--font-size-body-px: 19px'), 'execution body_text px wins');
assert.ok(execCover.includes('--font-size-note-px: 16px'), 'execution note_text px wins');
assert.ok(!execCover.includes('--font-size-title-px: 184px'), 'source 138pt title should not drive base HTML');

const nestedExecRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'ppt-exec-nested-'));
generateHtmlTemplates({
  schema_version: 'ppt-template-spec-v1',
  style_name: 'Nested Exec Typography',
  slide_size: { width_px: 1280, height_px: 720 },
  colors: { primary: '#AA0000', background: '#FFFFFF', text: '#222222', allowed: [] },
  fonts: { title: 'Sans', body: 'Sans' },
  font_scale: [{ role: 'title', dominant_pt: 138 }, { role: 'body', dominant_pt: 28 }],
  typography_tokens: { heading_pt: 138, body_pt: 28, note_pt: 14 },
  execution_font_scale: [],
  execution_tokens: {
    typography_scale: [
      { role: 'page_title', px: 34, tailwind: 'text-[34px]', source: 'preset' },
      { role: 'body_text', px: 18, tailwind: 'text-[18px]', source: 'preset' },
      { role: 'note_text', px: 15, tailwind: 'text-[15px]', source: 'preset' },
    ],
  },
  fixed_composition: [{ page_type: 'cover', layout_rule: 'test' }],
  layout_library: [],
  visual_assets: [],
}, nestedExecRoot);
const nestedExecCover = fs.readFileSync(path.join(nestedExecRoot, 'html-templates', 'cover-base.html'), 'utf-8');
assert.ok(nestedExecCover.includes('--font-size-title-px: 34px'), 'nested execution page_title px wins when top-level scale empty');
assert.ok(nestedExecCover.includes('--font-size-body-px: 18px'), 'nested execution body_text px wins when top-level scale empty');
assert.ok(nestedExecCover.includes('--font-size-note-px: 15px'), 'nested execution note_text px wins when top-level scale empty');

const invalidBodyExecRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'ppt-exec-invalid-body-'));
generateHtmlTemplates({
  schema_version: 'ppt-template-spec-v1',
  style_name: 'Invalid Body Exec Typography',
  slide_size: { width_px: 1280, height_px: 720 },
  colors: { primary: '#AA0000', background: '#FFFFFF', text: '#222222', allowed: [] },
  fonts: { title: 'Sans', body: 'Sans' },
  font_scale: [{ role: 'title', dominant_pt: 34 }, { role: 'body', dominant_pt: 18 }],
  typography_tokens: { heading_pt: 40, body_pt: 28, note_pt: 10 },
  execution_font_scale: [
    { role: 'page_title', px: 35, tailwind: 'text-[35px]', source: 'preset' },
    { role: 'body_text', px: null, tailwind: 'text-[19px]', source: 'preset' },
    { role: 'subsection_text', px: 21, tailwind: 'text-[21px]', source: 'preset' },
    { role: 'note_text', px: 16, tailwind: 'text-[16px]', source: 'preset' },
  ],
  fixed_composition: [{ page_type: 'cover', layout_rule: 'test' }],
  layout_library: [],
  visual_assets: [],
}, invalidBodyExecRoot);
const invalidBodyExecCover = fs.readFileSync(path.join(invalidBodyExecRoot, 'html-templates', 'cover-base.html'), 'utf-8');
assert.ok(invalidBodyExecCover.includes('--font-size-body-px: 21px'), 'invalid body_text px falls back to subsection_text px');
assert.ok(!invalidBodyExecCover.includes('--font-size-body-px: 37px'), 'invalid body_text px should not fall back to typography_tokens body_pt');

console.log('html_templates base mode tests passed');
