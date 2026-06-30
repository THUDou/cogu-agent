#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const { analyzeWithVLM } = require('./vlm-analyzer.js');
const {
  selectReusableStyleAssetCandidates,
  normalizeReusableStyleAssets,
} = require('./reusable-style-assets.js');
const { toPosix, readJson, writeJson } = require('./lib/utils.js');

function emptyReusableStyleAssets() {
  return {
    schema_version: 'reusable-style-assets-v1',
    source: 'vlm_page_context_review',
    assets: [],
    rejected_assets: [],
  };
}

function assetAbsPath(templateDir, assetPath) {
  return path.join(templateDir, ...toPosix(assetPath).split('/'));
}

function slideImagePath(templateDir, page) {
  return path.join(templateDir, 'slides', `slide-${String(page).padStart(3, '0')}.png`);
}

function firstSourcePage(candidate) {
  const pages = Array.isArray(candidate?.source_pages) ? candidate.source_pages : [];
  const page = Number(pages[0] || candidate?.source_slide || candidate?.slide || 1);
  return Number.isFinite(page) && page > 0 ? page : 1;
}

function buildReviewBatches(candidates, options = {}) {
  const maxAssetsPerBatch = Math.max(1, Number(options.maxAssetsPerBatch || 5));
  const byPage = new Map();

  for (const candidate of candidates || []) {
    const page = firstSourcePage(candidate);
    if (!byPage.has(page)) byPage.set(page, []);
    byPage.get(page).push(candidate);
  }

  const batches = [];
  for (const [page, assets] of [...byPage.entries()].sort((a, b) => a[0] - b[0])) {
    for (let i = 0; i < assets.length; i += maxAssetsPerBatch) {
      batches.push({ page, assets: assets.slice(i, i + maxAssetsPerBatch) });
    }
  }
  return batches;
}

function placementSummary(placement = {}) {
  const fields = [
    ['anchor', placement.anchor],
    ['left_pct', placement.left_pct],
    ['top_pct', placement.top_pct],
    ['width_pct', placement.width_pct],
    ['height_pct', placement.height_pct],
    ['x_cm', placement.x_cm],
    ['y_cm', placement.y_cm],
    ['width_cm', placement.width_cm],
    ['height_cm', placement.height_cm],
  ].filter(([, value]) => value !== undefined && value !== null && value !== '');

  return fields.map(([key, value]) => `${key}: ${value}`).join(', ') || 'not available';
}

function buildReviewPrompt(batch) {
  const assets = Array.isArray(batch?.assets) ? batch.assets : [];
  const assetLines = assets.map((asset, index) => {
    const imageNo = index + 2;
    const sourcePages = Array.isArray(asset.source_pages) ? asset.source_pages.join(', ') : '';
    return [
      `Image ${imageNo}: ${asset.path}`,
      `  role_hint: ${asset.role_hint || 'unknown'}`,
      `  source_pages: ${sourcePages || 'unknown'}`,
      `  placement: ${placementSummary(asset.placement)}`,
      `  candidate_reason: ${asset.reason || 'not provided'}`,
    ].join('\n');
  }).join('\n');

  return `You are reviewing reusable visual style assets for a PowerPoint HTML template.

Image 1 is the complete slide screenshot for source page ${batch?.page || 1}.
Images 2-N are candidate local image assets cropped or extracted from the deck.

Classify only whether each candidate asset should be reused as a fixed template style asset. Reject content-specific photos, charts, screenshots, people, venue/campus photos, brand marks that are only organization-specific, and anything that should change with slide content.

Candidate assets:
${assetLines || 'None'}

For every candidate asset, return one object with:
- path: exactly the candidate path shown above
- role: one of template_background, background_texture, template_decoration, edge_decoration, repeated_decoration, content_photo, content_chart, logo_or_brand, screenshot, other_content, unknown
- reuse_decision: one of must_reuse_for_style, optional_style_asset, same_topic_content_only, brand_or_org_only, do_not_reuse, uncertain
- confidence: high, medium, or low
- reason: concise visual evidence from Image 1 and the candidate image

Return ONLY valid JSON. Do not include markdown, comments, or extra text.
Required JSON shape:
{
  "asset_classifications": [
    {
      "path": "images/assets/example.png",
      "role": "template_decoration",
      "reuse_decision": "optional_style_asset",
      "confidence": "high",
      "reason": "short reason"
    }
  ]
}`;
}

function tempConfigPath(configPath, index) {
  const dir = path.dirname(configPath);
  const ext = path.extname(configPath) || '.json';
  const base = path.basename(configPath, ext);
  return path.join(dir, `${base}.reusable-style-assets.${process.pid}.${Date.now()}.${index}${ext}`);
}

function writeTempConfig(configPath, prompt, imageCount, index) {
  const config = readJson(configPath);
  const tempPath = tempConfigPath(configPath, index);
  const nextConfig = {
    ...config,
    analysis: {
      ...(config.analysis || {}),
      maxImagesPerRequest: Math.max(imageCount, Number(config.analysis?.maxImagesPerRequest || 0)),
    },
    prompts: {
      ...(config.prompts || {}),
      analysisPrompt: prompt,
    },
  };
  writeJson(tempPath, nextConfig);
  return tempPath;
}

function failedBatchReview(assets, error) {
  const message = String(error?.message || error || 'vlm_batch_failed');
  return {
    asset_classifications: assets.map(asset => ({
      path: asset.path,
      role: 'unknown',
      reuse_decision: 'uncertain',
      confidence: 'low',
      reason: `vlm_batch_failed: ${message}`,
    })),
  };
}

async function reviewReusableStyleAssets(templateDir, configPath, options = {}) {
  const imageMapPath = options.imageMapPath || path.join(templateDir, 'images', 'image-map.json');
  const outputPath = options.outputPath || path.join(templateDir, 'temp', 'reusable-style-assets.json');
  const analyzer = options.analyzeWithVLM || analyzeWithVLM;

  if (!fs.existsSync(imageMapPath)) {
    const empty = emptyReusableStyleAssets();
    writeJson(outputPath, empty);
    return empty;
  }

  const imageMap = readJson(imageMapPath);
  const candidates = selectReusableStyleAssetCandidates(imageMap, options);
  if (!candidates.length) {
    const empty = emptyReusableStyleAssets();
    writeJson(outputPath, empty);
    return empty;
  }

  const candidatesByPath = new Map(candidates.map(candidate => [candidate.path, candidate]));
  const reviews = [];
  const batches = buildReviewBatches(candidates, options);

  for (let i = 0; i < batches.length; i += 1) {
    const batch = batches[i];
    const slidePath = slideImagePath(templateDir, batch.page);
    if (!fs.existsSync(slidePath)) continue;

    const existingAssets = batch.assets.filter(asset => fs.existsSync(assetAbsPath(templateDir, asset.path)));
    if (!existingAssets.length) continue;

    const reviewBatch = { ...batch, assets: existingAssets };
    const imagePaths = [
      slidePath,
      ...existingAssets.map(asset => assetAbsPath(templateDir, asset.path)),
    ];
    const tempPath = writeTempConfig(configPath, buildReviewPrompt(reviewBatch), imagePaths.length, i + 1);

    try {
      const result = await analyzer(imagePaths, tempPath);
      if (result?.analysis) reviews.push(result.analysis);
    } catch (error) {
      reviews.push(failedBatchReview(existingAssets, error));
    } finally {
      try {
        fs.unlinkSync(tempPath);
      } catch {
      }
    }
  }

  const normalized = normalizeReusableStyleAssets(reviews, { candidatesByPath });
  writeJson(outputPath, normalized);
  return normalized;
}

async function main() {
  const args = process.argv.slice(2);
  const templateDir = args.find(arg => !arg.startsWith('--'));
  const configArg = args.find(arg => arg.startsWith('--config='));
  const configPath = configArg
    ? configArg.slice('--config='.length)
    : path.join(__dirname, '..', 'vlm-config.json');

  if (!templateDir) {
    console.error('Usage: node review-reusable-style-assets.js <templateDir> --config=<vlm-config>');
    process.exit(1);
  }

  const result = await reviewReusableStyleAssets(templateDir, configPath);
  console.log(JSON.stringify({
    assets: result.assets.length,
    rejected_assets: result.rejected_assets.length,
  }, null, 2));
}

module.exports = {
  buildReviewBatches,
  buildReviewPrompt,
  reviewReusableStyleAssets,
};

if (require.main === module) {
  main().catch(error => {
    console.error(error.message);
    process.exit(1);
  });
}
