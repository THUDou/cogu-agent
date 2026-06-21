const assert = require('assert');
const fs = require('fs');
const path = require('path');
const {
  parseAnalysisResult,
  normalizeAnalysisResult,
  imageMediaType,
} = require('../scripts/vlm-analyzer.js');

function testParseJsonFence() {
  const result = parseAnalysisResult('```json\n{"page_roles":[{"page":1,"role":"cover"}]}\n```');
  assert.deepStrictEqual(result.page_roles, [{ page: 1, role: 'cover' }]);
}

function testNormalizeKeepsLegacyFields() {
  const legacy = {
    '配色方案': {
      '主色调': '科技蓝 #1F6FFF',
      '整体风格': '科技商务',
    },
    '视觉风格': {
      '整体风格': '深色科技感',
    },
  };

  const normalized = normalizeAnalysisResult(legacy);

  assert.strictEqual(normalized.schema_version, 'ppt-template-vlm-enhanced-v1');
  assert.deepStrictEqual(normalized['配色方案'], legacy['配色方案']);
  assert.deepStrictEqual(normalized['视觉风格'], legacy['视觉风格']);
  assert.deepStrictEqual(normalized.page_roles, []);
  assert.deepStrictEqual(normalized.visual_assets, []);
  assert.deepStrictEqual(normalized.layout_semantics, []);
  assert.deepStrictEqual(normalized.fixed_composition, []);
  assert.deepStrictEqual(normalized.corrections, []);
  assert.deepStrictEqual(normalized.replication_rules, []);
}

function testNormalizeCanonicalFields() {
  const enhanced = {
    page_roles: [{ page: 1, role: 'cover', confidence: 0.9 }],
    visual_assets: [{ asset_path: 'images/bg.png', visual_role: 'background' }],
    layout_semantics: [{ page: 2, layout_name: '左文右图' }],
    fixed_composition: [{ page_type: 'cover', required_elements: ['年份水印'] }],
    corrections: [{ target: 'color.primary', to: '#123456' }],
    replication_rules: ['必须复用背景图'],
  };

  const normalized = normalizeAnalysisResult(enhanced);

  assert.strictEqual(normalized.schema_version, 'ppt-template-vlm-enhanced-v1');
  assert.deepStrictEqual(normalized.page_roles, enhanced.page_roles);
  assert.deepStrictEqual(normalized.visual_assets, enhanced.visual_assets);
  assert.deepStrictEqual(normalized.layout_semantics, enhanced.layout_semantics);
  assert.deepStrictEqual(normalized.fixed_composition, enhanced.fixed_composition);
  assert.deepStrictEqual(normalized.corrections, enhanced.corrections);
  assert.deepStrictEqual(normalized.replication_rules, enhanced.replication_rules);
}

function testNormalizeChineseAliasFields() {
  const aliased = {
    '页面角色': [{ page: 1, role: 'cover' }],
    '视觉资产': [{ visual_role: 'background' }],
    '版式复刻规则': [{ layout_name: '封面居中' }],
    '固定构图': [{ page_type: 'cover', required_elements: ['年份水印'] }],
    '视觉纠偏': [{ target: 'font.title' }],
    '复刻优先级': ['保持中心边框'],
  };

  const normalized = normalizeAnalysisResult(aliased);

  assert.deepStrictEqual(normalized.page_roles, aliased['页面角色']);
  assert.deepStrictEqual(normalized.visual_assets, aliased['视觉资产']);
  assert.deepStrictEqual(normalized.layout_semantics, aliased['版式复刻规则']);
  assert.deepStrictEqual(normalized.fixed_composition, aliased['固定构图']);
  assert.deepStrictEqual(normalized.corrections, aliased['视觉纠偏']);
  assert.deepStrictEqual(normalized.replication_rules, aliased['复刻优先级']);
}

function testPromptRequestsEnhancedContract() {
  const configPath = path.join(__dirname, '..', 'vlm-config.json');
  const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
  const prompt = config.prompts.analysisPrompt;

  for (const requiredField of [
    'page_roles',
    'visual_assets',
    'layout_semantics',
    'fixed_composition',
    'corrections',
    'replication_rules',
    'semantic_type',
    'content_scenario',
    'information_relation',
    'slot_structure',
    'selection_rule',
  ]) {
    assert.ok(
      prompt.includes(requiredField),
      `analysisPrompt should request ${requiredField}`
    );
  }
}

function testImageMediaType() {
  assert.strictEqual(imageMediaType('cover.png'), 'image/png');
  assert.strictEqual(imageMediaType('photo.jpg'), 'image/jpeg');
  assert.strictEqual(imageMediaType('photo.jpeg'), 'image/jpeg');
  assert.strictEqual(imageMediaType('texture.webp'), 'image/webp');
}

testParseJsonFence();
testNormalizeKeepsLegacyFields();
testNormalizeCanonicalFields();
testNormalizeChineseAliasFields();
testPromptRequestsEnhancedContract();
testImageMediaType();

console.log('vlm_analyzer tests passed');
