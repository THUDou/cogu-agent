const path = require('path');
const { toPosix } = require('./lib/utils.js');

function normalizeAssetPath(value) {
  const normalized = toPosix(value || '');
  if (!normalized) return '';
  if (/[\x00-\x1F\x7F"'<>]/.test(normalized)) return '';
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(normalized)) return '';
  if (/^[a-z]:\//i.test(normalized) || normalized.startsWith('/')) return '';
  if (normalized.includes('//')) return '';

  const raw = normalized.replace(/^\.\//, '');
  const parts = raw.split('/');
  if (parts.some(part => part === '..' || part === '')) return '';

  if (raw.startsWith('images/assets/') || raw.startsWith('images/bg_images/')) return raw;
  if (raw.startsWith('assets/') || raw.startsWith('bg_images/')) return `images/${raw}`;
  return '';
}

function safeCssClass(assetPath) {
  const base = path.basename(assetPath, path.extname(assetPath))
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return `style-asset-${base || 'image'}`;
}

function usageArea(usage) {
  return Number(usage?.cx_cm || usage?.width_cm || 0) * Number(usage?.cy_cm || usage?.height_cm || 0);
}

function toPercent(value) {
  return Math.round(Number(value || 0) * 1000) / 10;
}

function toPercentPlacement(usage, slideSize = {}) {
  const width = Number(slideSize.width_cm || 33.87);
  const height = Number(slideSize.height_cm || 19.05);
  return {
    left_pct: toPercent(Number(usage.x_cm || 0) / width),
    top_pct: toPercent(Number(usage.y_cm || 0) / height),
    width_pct: toPercent(Number(usage.cx_cm || usage.width_cm || 0) / width),
    height_pct: toPercent(Number(usage.cy_cm || usage.height_cm || 0) / height),
  };
}

function inferAnchor(placement) {
  if (placement.top_pct <= 18 && placement.left_pct >= 70) return 'top_right';
  if (placement.top_pct <= 18 && placement.left_pct <= 20) return 'top_left';
  if (placement.top_pct >= 75 && placement.left_pct >= 70) return 'bottom_right';
  if (placement.top_pct >= 75 && placement.left_pct <= 20) return 'bottom_left';
  if (placement.top_pct <= 25) return 'title_flank';
  return 'decorative';
}

function summarizeUsages(usages, slideSize) {
  const sorted = usages.slice().sort((a, b) => usageArea(b) - usageArea(a));
  const primary = sorted[0] || {};
  const placement = toPercentPlacement(primary, slideSize);
  return {
    source_pages: [...new Set(usages.map(u => Number(u.slide)).filter(Boolean))].sort((a, b) => a - b),
    max_area_cm2: Math.round(usageArea(primary) * 10) / 10,
    placement: {
      anchor: inferAnchor(placement),
      ...placement,
      x_cm: Number(primary.x_cm || 0),
      y_cm: Number(primary.y_cm || 0),
      width_cm: Number(primary.cx_cm || primary.width_cm || 0),
      height_cm: Number(primary.cy_cm || primary.height_cm || 0),
    },
  };
}

function dedupeByPath(items) {
  const seen = new Set();
  const out = [];
  for (const item of items) {
    if (!item.path || seen.has(item.path)) continue;
    seen.add(item.path);
    out.push(item);
  }
  return out;
}

function selectReusableStyleAssetCandidates(imageMapData = {}, options = {}) {
  const slideSize = options.slideSize || {};
  const candidates = [];

  for (const item of Object.values(imageMapData.bg_images || {})) {
    const assetPath = normalizeAssetPath(item.path || item.saved_as);
    if (!assetPath) continue;
    candidates.push({
      path: assetPath,
      role_hint: 'template_background',
      reason: 'bg_images entry',
      source_pages: [Number(item.source_slide || item.slide || 1)].filter(Boolean),
      page_roles: ['cover', 'section', 'content', 'closing'],
      placement: { anchor: 'full_slide', left_pct: 0, top_pct: 0, width_pct: 100, height_pct: 100 },
    });
  }

  for (const [name, info] of Object.entries(imageMapData.images || {})) {
    const assetPath = normalizeAssetPath(info.saved_as || name);
    if (!assetPath || !assetPath.startsWith('images/assets/')) continue;

    const usages = Array.isArray(info.usages) ? info.usages : [];
    if (!usages.length) continue;

    const usageSummary = summarizeUsages(usages, slideSize);
    const repeated = usageSummary.source_pages.length >= 2 || usages.length >= 2;
    const fullSlide = usageSummary.placement.width_pct >= 85 && usageSummary.placement.height_pct >= 85;
    const small = usageSummary.placement.width_pct <= 20 && usageSummary.placement.height_pct <= 20;
    const edge = usageSummary.placement.top_pct <= 20 || usageSummary.placement.top_pct >= 75
      || usageSummary.placement.left_pct <= 15 || usageSummary.placement.left_pct >= 75;

    if (!fullSlide && !(repeated && small) && !(small && edge)) continue;

    candidates.push({
      path: assetPath,
      role_hint: fullSlide ? 'template_background' : 'template_decoration',
      reason: fullSlide ? 'near full-slide asset' : 'small repeated or edge asset',
      source_pages: usageSummary.source_pages,
      page_roles: ['content'],
      placement: usageSummary.placement,
    });
  }

  return dedupeByPath(candidates);
}

const ACCEPTED_DECISIONS = new Set(['must_reuse_for_style', 'optional_style_asset']);
const ACCEPTED_ROLES = new Set([
  'template_background',
  'background_texture',
  'template_decoration',
  'edge_decoration',
  'repeated_decoration',
]);

function isAcceptedStyleAsset(item) {
  return ACCEPTED_DECISIONS.has(String(item.reuse_decision || '').toLowerCase())
    && ACCEPTED_ROLES.has(String(item.role || '').toLowerCase())
    && String(item.confidence || '').toLowerCase() !== 'low';
}

function normalizeReusableStyleAssets(reviews = [], options = {}) {
  const candidatesByPath = options.candidatesByPath || new Map();
  const classificationsByPath = new Map();

  for (const review of reviews) {
    const classifications = Array.isArray(review.asset_classifications) ? review.asset_classifications : [];
    for (const raw of classifications) {
      const assetPath = normalizeAssetPath(raw.path || raw.file);
      if (!assetPath) continue;

      const candidate = candidatesByPath.get(assetPath) || {};
      const normalized = {
        path: assetPath,
        role: String(raw.role || 'unknown'),
        reuse_decision: String(raw.reuse_decision || 'uncertain'),
        page_roles: candidate.page_roles || ['content'],
        source_pages: candidate.source_pages || [],
        placement: candidate.placement || {},
        html_policy: {
          inject: true,
          page_roles: candidate.page_roles || ['content'],
          css_class: safeCssClass(assetPath),
        },
        confidence: String(raw.confidence || 'low'),
        reason: String(raw.reason || raw.observed_in_page || ''),
      };
      if (!classificationsByPath.has(assetPath)) classificationsByPath.set(assetPath, []);
      classificationsByPath.get(assetPath).push(normalized);
    }
  }

  const assets = [];
  const rejected_assets = [];
  for (const [assetPath, classifications] of classificationsByPath.entries()) {
    const candidate = candidatesByPath.get(assetPath);
    if (!candidate) {
      const first = classifications[0];
      rejected_assets.push({
        path: assetPath,
        role: first.role,
        reuse_decision: first.reuse_decision,
        confidence: first.confidence,
        reason: `${first.reason ? `${first.reason}; ` : ''}not selected as style asset candidate`,
      });
      continue;
    }

    const rejected = classifications.find(item => !isAcceptedStyleAsset(item));
    if (rejected) {
      rejected_assets.push({
        path: assetPath,
        role: rejected.role,
        reuse_decision: rejected.reuse_decision,
        confidence: rejected.confidence,
        reason: `${rejected.reason ? `${rejected.reason}; ` : ''}conflicting or rejected classification`,
      });
      continue;
    }

    assets.push(classifications[0]);
  }

  return {
    schema_version: 'reusable-style-assets-v1',
    source: 'vlm_page_context_review',
    assets: dedupeByPath(assets),
    rejected_assets: dedupeByPath(rejected_assets),
  };
}

function cssNumber(value, fallback) {
  const n = Number(value);
  return Number.isFinite(n) ? Math.max(0, Math.min(100, Math.round(n * 10) / 10)) : fallback;
}

function deriveDecorationMapFromReusableAssets(reusable = {}) {
  const decorations = [];
  const page_role_map = { cover: [], content: [], section: [], closing: [] };

  for (const asset of reusable.assets || []) {
    if (!isAcceptedStyleAsset(asset)) continue;
    if (asset.html_policy && asset.html_policy.inject === false) continue;
    const assetPath = normalizeAssetPath(asset.path);
    if (!assetPath) continue;

    const id = String(asset.html_policy?.css_class || safeCssClass(assetPath))
      .replace(/[^a-zA-Z0-9_-]/g, '-');
    const p = asset.placement || {};
    const left = cssNumber(p.left_pct, 0);
    const top = cssNumber(p.top_pct, 0);
    const width = cssNumber(p.width_pct, 8);
    const height = cssNumber(p.height_pct, 8);

    decorations.push({
      id,
      css: `.${id} { position: absolute; left: ${left}%; top: ${top}%; width: ${width}%; height: ${height}%; object-fit: contain; pointer-events: none; z-index: 2; }`,
      html: `<img class="style-asset ${id}" src="../${assetPath}" alt="" />`,
      source_description: asset.reason || asset.role,
    });

    const roles = asset.html_policy?.page_roles || asset.page_roles || ['content'];
    for (const role of roles) {
      if (page_role_map[role] && !page_role_map[role].includes(id)) {
        page_role_map[role].push(id);
      }
    }
  }

  return { schema_version: 'decoration-map-v1', decorations, page_role_map };
}

module.exports = {
  normalizeAssetPath,
  selectReusableStyleAssetCandidates,
  normalizeReusableStyleAssets,
  deriveDecorationMapFromReusableAssets,
  toPercentPlacement,
};
