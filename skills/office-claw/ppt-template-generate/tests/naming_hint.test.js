const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const {
  buildNamingHint,
  printNamingHint,
  writeNamingHintJson,
} = require('../scripts/index.js');

function makeContext(overrides = {}) {
  return {
    fileName: '年度汇报',
    temporaryDir: 'ppt-template-hub/年度汇报',
    namingHintJsonPath: 'ppt-template-hub/年度汇报/temp/naming-hint.json',
    imageMapData: {},
    ...overrides,
  };
}

function testClearNamingHint() {
  const hint = buildNamingHint({
    slide_count: 10,
    actual_colors: {
      '#D02227': {
        count: 12,
        fill_count: 12,
        text_count: 0,
        area_weight: 2.5,
        usages: ['shape_fill'],
      },
      '#1A1A1A': {
        count: 10,
        fill_count: 10,
        text_count: 0,
        area_weight: 10,
        usages: ['background_fill'],
      },
    },
    bg_text_mapping: {
      '#1A1A1A': {
        slide_count: 10,
        text_colors: ['#FFFFFF'],
      },
    },
    slide_roles: [{ slide: 1, role: 'cover' }],
  }, makeContext());

  assert.strictEqual(hint.schema_version, 'ppt-template-naming-hint-v1');
  assert.strictEqual(hint.status, 'clear');
  assert.strictEqual(hint.colors.fill_colors[0].hex, '#1A1A1A');
  assert.strictEqual(hint.colors.background.type, 'solid');
  assert.strictEqual(hint.fallback_context.slide_count, 10);
}

function testNeutralOnlyIsWeak() {
  const hint = buildNamingHint({
    slide_count: 3,
    actual_colors: {
      '#FFFFFF': {
        count: 3,
        fill_count: 3,
        text_count: 0,
        area_weight: 3,
        usages: ['background_fill'],
      },
      '#222222': {
        count: 8,
        fill_count: 2,
        text_count: 6,
        area_weight: 0.1,
        usages: ['body_fill', 'body_text'],
      },
    },
    bg_text_mapping: {
      '#FFFFFF': {
        slide_count: 3,
        text_colors: ['#222222'],
      },
    },
  }, makeContext());

  assert.strictEqual(hint.status, 'weak');
  assert.ok(hint.reasons.some(reason => reason.includes('中性色')));
}

function testEmptyStructureIsMissing() {
  const hint = buildNamingHint({}, makeContext());
  assert.strictEqual(hint.status, 'missing');
  assert.ok(hint.reasons.some(reason => reason.includes('结构化配色')));
}

function testBackgroundImageMetadataIsWeakSignal() {
  const hint = buildNamingHint({
    slide_count: 5,
    actual_colors: {},
    bg_text_mapping: {},
    colors: { accent1: '#4472C4' },
  }, makeContext({
    imageMapData: {
      bg_images: {
        'bg1.png': {
          saved_as: 'bg_images/bg1.png',
          sources: [{ type: 'slide', slide_no: 1 }],
        },
      },
    },
  }));

  assert.strictEqual(hint.status, 'weak');
  assert.strictEqual(hint.fallback_context.has_background_images, true);
  assert.strictEqual(hint.colors.background.type, 'image_or_unresolved');
  assert.ok(hint.reasons.some(reason => reason.includes('背景图')));
}

function testPrintIncludesStatusAndJsonPath() {
  const hint = buildNamingHint({
    slide_count: 1,
    actual_colors: {},
    bg_text_mapping: {},
  }, makeContext());
  const text = printNamingHint(hint, { write: false });

  assert.ok(text.includes('=== NAMING_HINT ==='));
  assert.ok(text.includes('命名线索状态: missing'));
  assert.ok(text.includes('结构化命名线索: ppt-template-hub/年度汇报/temp/naming-hint.json'));
}

function testWrittenJsonDoesNotContainSlidesPath() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'naming-hint-'));
  const filePath = path.join(tmp, 'naming-hint.json');
  const hint = buildNamingHint({
    slide_count: 1,
    actual_colors: {},
    bg_text_mapping: {},
  }, makeContext({
    temporaryDir: path.join(tmp, 'template'),
    namingHintJsonPath: filePath,
    imageMapData: {
      bg_images: {
        'bg1.png': {
          saved_as: 'bg_images/bg1.png',
          sources: [{ path: 'slides/slide-001.png' }],
        },
      },
    },
  }));

  writeNamingHintJson(filePath, hint);
  const raw = fs.readFileSync(filePath, 'utf-8');
  assert.ok(raw.includes('ppt-template-naming-hint-v1'));
  assert.ok(!raw.includes('slides/'));
  assert.ok(!raw.includes('slides\\'));
  fs.rmSync(tmp, { recursive: true, force: true });
}

testClearNamingHint();
testNeutralOnlyIsWeak();
testEmptyStructureIsMissing();
testBackgroundImageMetadataIsWeakSignal();
testPrintIncludesStatusAndJsonPath();
testWrittenJsonDoesNotContainSlidesPath();

console.log('naming_hint tests passed');
