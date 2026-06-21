const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const {
  normalizeAssetPath,
  selectReusableStyleAssetCandidates,
  normalizeReusableStyleAssets,
  deriveDecorationMapFromReusableAssets,
  toPercentPlacement,
} = require('../scripts/reusable-style-assets.js');
const {
  buildReviewBatches,
  buildReviewPrompt,
  reviewReusableStyleAssets,
} = require('../scripts/review-reusable-style-assets.js');

const slideSize = { width_cm: 33.87, height_cm: 19.05 };

function testSelectCandidates() {
  const imageMap = {
    images: {
      'image-bg.png': {
        saved_as: 'assets/image-bg.png',
        usages: [
          { slide: 1, x_cm: 0, y_cm: 0, cx_cm: 33.87, cy_cm: 19.05, z_order: 1 },
          { slide: 2, x_cm: 0, y_cm: 0, cx_cm: 33.87, cy_cm: 19.05, z_order: 1 },
        ],
      },
      'image-cloud.png': {
        saved_as: 'assets/image-cloud.png',
        usages: [
          { slide: 1, x_cm: 28, y_cm: 1, cx_cm: 2, cy_cm: 1, z_order: 5 },
          { slide: 2, x_cm: 28, y_cm: 1, cx_cm: 2, cy_cm: 1, z_order: 5 },
          { slide: 3, x_cm: 28, y_cm: 1, cx_cm: 2, cy_cm: 1, z_order: 5 },
        ],
      },
      'campus-photo.jpeg': {
        saved_as: 'assets/campus-photo.jpeg',
        usages: [
          { slide: 1, x_cm: 5, y_cm: 4, cx_cm: 12, cy_cm: 7, z_order: 9 },
        ],
      },
    },
    bg_images: {
      'slide_001_shape_bg.png': {
        saved_as: 'bg_images/slide_001_shape_bg.png',
        source_slide: 1,
      },
    },
  };

  const candidates = selectReusableStyleAssetCandidates(imageMap, { slideSize });
  const paths = candidates.map(item => item.path).sort();
  assert.ok(paths.includes('images/bg_images/slide_001_shape_bg.png'));
  assert.ok(paths.includes('images/assets/image-bg.png'));
  assert.ok(paths.includes('images/assets/image-cloud.png'));
  assert.ok(!paths.includes('images/assets/campus-photo.jpeg'));
}

function testPercentPlacement() {
  const pct = toPercentPlacement(
    { x_cm: 16.935, y_cm: 9.525, cx_cm: 3.387, cy_cm: 1.905 },
    slideSize
  );
  assert.deepStrictEqual(pct, {
    left_pct: 50,
    top_pct: 50,
    width_pct: 10,
    height_pct: 10,
  });
}

function testNormalizeReusableStyleAssets() {
  const review = {
    asset_classifications: [
      {
        path: 'images/assets/image-cloud.png',
        role: 'template_decoration',
        reuse_decision: 'optional_style_asset',
        confidence: 'high',
        reason: 'repeated title decoration',
      },
      {
        path: 'images/assets/campus-photo.jpeg',
        role: 'content_photo',
        reuse_decision: 'same_topic_content_only',
        confidence: 'high',
        reason: 'campus photo',
      },
    ],
  };
  const normalized = normalizeReusableStyleAssets([review], {
    candidatesByPath: new Map([
      ['images/assets/image-cloud.png', {
        path: 'images/assets/image-cloud.png',
        source_pages: [1, 2],
        page_roles: ['content'],
        placement: { anchor: 'top_right', left_pct: 82, top_pct: 5, width_pct: 6, height_pct: 5 },
      }],
      ['images/assets/campus-photo.jpeg', {
        path: 'images/assets/campus-photo.jpeg',
        source_pages: [1],
        page_roles: ['content'],
      }],
    ]),
  });

  assert.strictEqual(normalized.schema_version, 'reusable-style-assets-v1');
  assert.strictEqual(normalized.assets.length, 1);
  assert.strictEqual(normalized.assets[0].path, 'images/assets/image-cloud.png');
  assert.strictEqual(normalized.rejected_assets.length, 1);
  assert.strictEqual(normalized.rejected_assets[0].path, 'images/assets/campus-photo.jpeg');
}

function testRejectsAcceptedLookingAssetAbsentFromCandidates() {
  const review = {
    asset_classifications: [{
      path: 'images/assets/campus-photo.jpeg',
      role: 'template_decoration',
      reuse_decision: 'optional_style_asset',
      confidence: 'high',
      reason: 'looks decorative',
    }],
  };
  const normalized = normalizeReusableStyleAssets([review], {
    candidatesByPath: new Map(),
  });

  assert.strictEqual(normalized.assets.length, 0);
  assert.strictEqual(normalized.rejected_assets.length, 1);
  assert.strictEqual(normalized.rejected_assets[0].path, 'images/assets/campus-photo.jpeg');
  assert.ok(normalized.rejected_assets[0].reason.includes('not selected as style asset candidate'));
}

function testConflictingClassificationsRejectPath() {
  const review = {
    asset_classifications: [
      {
        path: 'images/assets/image-cloud.png',
        role: 'template_decoration',
        reuse_decision: 'optional_style_asset',
        confidence: 'high',
        reason: 'repeated title decoration',
      },
      {
        path: 'images/assets/image-cloud.png',
        role: 'content_photo',
        reuse_decision: 'same_topic_content_only',
        confidence: 'high',
        reason: 'content-bound photo',
      },
    ],
  };
  const normalized = normalizeReusableStyleAssets([review], {
    candidatesByPath: new Map([
      ['images/assets/image-cloud.png', {
        path: 'images/assets/image-cloud.png',
        source_pages: [1, 2],
        page_roles: ['content'],
        placement: { left_pct: 82, top_pct: 5, width_pct: 6, height_pct: 5 },
      }],
    ]),
  });

  assert.strictEqual(normalized.assets.length, 0);
  assert.strictEqual(normalized.rejected_assets.length, 1);
  assert.strictEqual(normalized.rejected_assets[0].path, 'images/assets/image-cloud.png');
  assert.ok(normalized.rejected_assets[0].reason.includes('conflicting or rejected classification'));
}

function testUnsafePathsAreRejectedAndNotEmittedInDecorationHtml() {
  const unsafePaths = [
    'images/assets/bad"quote.png',
    'images/assets/bad<tag>.png',
    'images/assets/bad\nline.png',
    'images/assets//double.png',
    'https://example.com/image.png',
    'C:/tmp/image.png',
    '/images/assets/absolute.png',
    'images/assets/../secret.png',
    'slides/image.png',
  ];

  for (const unsafePath of unsafePaths) {
    assert.strictEqual(normalizeAssetPath(unsafePath), '', unsafePath);
  }

  const map = deriveDecorationMapFromReusableAssets({
    schema_version: 'reusable-style-assets-v1',
    assets: unsafePaths.map(path => ({
      path,
      role: 'template_decoration',
      reuse_decision: 'optional_style_asset',
      confidence: 'high',
      page_roles: ['content'],
      placement: { left_pct: 1, top_pct: 1, width_pct: 1, height_pct: 1 },
    })),
  });

  assert.strictEqual(map.decorations.length, 0);
  assert.deepStrictEqual(map.page_role_map.content, []);
}

function testDeriveDecorationMap() {
  const reusable = {
    schema_version: 'reusable-style-assets-v1',
    assets: [{
      path: 'images/assets/image-cloud.png',
      role: 'template_decoration',
      reuse_decision: 'optional_style_asset',
      page_roles: ['content'],
      placement: { left_pct: 82, top_pct: 5, width_pct: 6, height_pct: 5 },
      html_policy: { inject: true, page_roles: ['content'], css_class: 'style-asset-image-cloud' },
    }],
  };
  const map = deriveDecorationMapFromReusableAssets(reusable);
  assert.strictEqual(map.schema_version, 'decoration-map-v1');
  assert.strictEqual(map.decorations.length, 1);
  assert.ok(map.decorations[0].html.includes('../images/assets/image-cloud.png'));
  assert.ok(map.decorations[0].css.includes('left: 82%'));
  assert.deepStrictEqual(map.page_role_map.content, ['style-asset-image-cloud']);
}

function testReviewBatches() {
  const candidates = [
    { path: 'images/assets/a.png', source_pages: [1] },
    { path: 'images/assets/b.png', source_pages: [1] },
    { path: 'images/assets/c.png', source_pages: [2] },
  ];
  const batches = buildReviewBatches(candidates, { maxAssetsPerBatch: 2 });
  assert.strictEqual(batches.length, 2);
  assert.strictEqual(batches[0].page, 1);
  assert.strictEqual(batches[0].assets.length, 2);
  assert.strictEqual(batches[1].page, 2);
}

function testReviewPrompt() {
  const prompt = buildReviewPrompt({
    page: 4,
    assets: [{
      path: 'images/assets/cloud.png',
      role_hint: 'template_decoration',
      placement: { anchor: 'title_flank', left_pct: 60, top_pct: 10, width_pct: 6, height_pct: 5 },
      source_pages: [4, 5],
    }],
  });
  assert.ok(prompt.includes('Image 1 is the complete slide screenshot'));
  assert.ok(prompt.includes('images/assets/cloud.png'));
  assert.ok(prompt.includes('template_decoration'));
  assert.ok(prompt.includes('Return ONLY valid JSON'));
}

function writeJson(filePath, data) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf-8');
}

async function testReviewReusableStyleAssetsContinuesAfterBatchFailure() {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'reusable-style-assets-'));
  const configPath = path.join(tempDir, 'vlm-config.json');
  const outputPath = path.join(tempDir, 'temp', 'reusable-style-assets.json');

  try {
    writeJson(configPath, {
      enabled: true,
      provider: 'openai',
      api: { openai: { apiKey: 'test-placeholder' } },
      prompts: { analysisPrompt: 'base prompt' },
    });
    writeJson(path.join(tempDir, 'images', 'image-map.json'), {
      bg_images: {
        'failed-bg.png': { saved_as: 'bg_images/failed-bg.png', source_slide: 1 },
        'ok-bg.png': { saved_as: 'bg_images/ok-bg.png', source_slide: 2 },
      },
    });
    fs.mkdirSync(path.join(tempDir, 'slides'), { recursive: true });
    fs.mkdirSync(path.join(tempDir, 'images', 'bg_images'), { recursive: true });
    fs.writeFileSync(path.join(tempDir, 'slides', 'slide-001.png'), 'slide 1');
    fs.writeFileSync(path.join(tempDir, 'slides', 'slide-002.png'), 'slide 2');
    fs.writeFileSync(path.join(tempDir, 'images', 'bg_images', 'failed-bg.png'), 'failed asset');
    fs.writeFileSync(path.join(tempDir, 'images', 'bg_images', 'ok-bg.png'), 'ok asset');

    const calls = [];
    const result = await reviewReusableStyleAssets(tempDir, configPath, {
      outputPath,
      maxAssetsPerBatch: 1,
      analyzeWithVLM: async (imagePaths) => {
        calls.push(imagePaths);
        if (imagePaths.some(item => item.includes('failed-bg.png'))) {
          throw new Error('mock vlm outage');
        }
        return {
          analysis: {
            asset_classifications: [{
              path: 'images/bg_images/ok-bg.png',
              role: 'template_background',
              reuse_decision: 'must_reuse_for_style',
              confidence: 'high',
              reason: 'full-slide background style',
            }],
          },
        };
      },
    });

    assert.strictEqual(calls.length, 2, 'mock analyzer should be called for both batches');
    assert.ok(fs.existsSync(outputPath), 'output JSON should exist');
    assert.strictEqual(result.assets.length, 1);
    assert.strictEqual(result.assets[0].path, 'images/bg_images/ok-bg.png');

    const written = JSON.parse(fs.readFileSync(outputPath, 'utf-8'));
    const failed = written.rejected_assets.find(asset => asset.path === 'images/bg_images/failed-bg.png');
    assert.ok(failed, 'failed candidate should be represented in rejected_assets');
    assert.strictEqual(failed.reuse_decision, 'uncertain');
    assert.strictEqual(failed.confidence, 'low');
    assert.ok(failed.reason.includes('mock vlm outage') || failed.reason.includes('vlm_batch_failed'));

    const tempConfigs = fs.readdirSync(tempDir)
      .filter(name => name.includes('.reusable-style-assets.'));
    assert.deepStrictEqual(tempConfigs, [], 'temporary VLM configs should be cleaned up');
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
}

async function run() {
  testSelectCandidates();
  testPercentPlacement();
  testNormalizeReusableStyleAssets();
  testRejectsAcceptedLookingAssetAbsentFromCandidates();
  testConflictingClassificationsRejectPath();
  testUnsafePathsAreRejectedAndNotEmittedInDecorationHtml();
  testDeriveDecorationMap();
  testReviewBatches();
  testReviewPrompt();
  await testReviewReusableStyleAssetsContinuesAfterBatchFailure();
}

run().then(() => {
  console.log('reusable_style_assets tests passed');
}).catch(error => {
  console.error(error);
  process.exit(1);
});
