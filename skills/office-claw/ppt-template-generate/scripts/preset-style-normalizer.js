const fs = require('fs');
const path = require('path');

const DEFAULT_PROFILE_PATH = path.join(__dirname, '..', 'preset-style-profiles.json');
const HIGH_CONFIDENCE_SCORE = 0.7;
const MEDIUM_CONFIDENCE_SCORE = 0.45;
const AMBIGUOUS_DELTA = 0.1;
const EXTREME_PAGE_TITLE_PX = 72;

function roundScore(value) {
  return Math.round(Number(value || 0) * 1000) / 1000;
}

function normalizeHex(value) {
  const text = String(value || '').trim();
  return /^#[0-9a-fA-F]{6}$/.test(text) ? text.toUpperCase() : '';
}

function hexToRgb(hex) {
  const normalized = normalizeHex(hex);
  if (!normalized) return null;
  return {
    r: parseInt(normalized.slice(1, 3), 16),
    g: parseInt(normalized.slice(3, 5), 16),
    b: parseInt(normalized.slice(5, 7), 16),
  };
}

function colorSimilarity(left, right) {
  const a = hexToRgb(left);
  const b = hexToRgb(right);
  if (!a || !b) return 0;
  const distance = Math.sqrt(
    Math.pow(a.r - b.r, 2) +
    Math.pow(a.g - b.g, 2) +
    Math.pow(a.b - b.b, 2),
  );
  return Math.max(0, 1 - distance / 441.7);
}

function withExecutionScaleMetadata(item, presetId) {
  const px = Number(item?.px);
  return {
    ...item,
    px,
    tailwind: `text-[${px}px]`,
    source: 'preset',
    preset_id: presetId,
  };
}

let _cachedProfiles = null;

function loadPresetProfiles(profilePath = DEFAULT_PROFILE_PATH) {
  if (_cachedProfiles) return _cachedProfiles;
  try {
    const parsed = JSON.parse(fs.readFileSync(profilePath, 'utf-8'));
    const profiles = Array.isArray(parsed.profiles) ? parsed.profiles : [];
    _cachedProfiles = profiles.map(profile => ({
      ...profile,
      typography_scale: (profile.typography_scale || []).map(item => (
        withExecutionScaleMetadata(item, profile.id)
      )),
    }));
  } catch {
    console.warn('[preset-style-normalizer] Failed to load preset profiles; falling back to source typography.');
    _cachedProfiles = [];
  }
  return _cachedProfiles;
}

function collectActualColorSignals(actualColors = {}) {
  return Object.entries(actualColors || {})
    .map(([hex, info]) => {
      const normalized = normalizeHex(hex);
      const area = Number(info?.area_weight) || 0;
      const fill = Number(info?.fill_count) || 0;
      const text = Number(info?.text_count) || 0;
      return {
        hex: normalized,
        weight: area > 0 ? area : (fill * 0.05 + text * 0.03),
      };
    })
    .filter(item => item.hex)
    .sort((a, b) => b.weight - a.weight)
    .slice(0, 8);
}

function collectTextParts(value, out = []) {
  if (value == null) return out;
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    out.push(String(value));
    return out;
  }
  if (Array.isArray(value)) {
    for (const item of value) collectTextParts(item, out);
    return out;
  }
  if (typeof value === 'object') {
    for (const item of Object.values(value)) collectTextParts(item, out);
  }
  return out;
}

function keywordScore(text, keywords = []) {
  const normalizedText = String(text || '').toLowerCase();
  const normalizedKeywords = keywords.map(item => String(item || '').trim()).filter(Boolean);
  if (!normalizedText || !normalizedKeywords.length) return 0;
  let hits = 0;
  for (const keyword of normalizedKeywords) {
    if (normalizedText.includes(keyword.toLowerCase())) hits += 1;
  }
  return Math.min(1, hits / Math.min(4, normalizedKeywords.length));
}

function colorScore(profile, actualColorSignals) {
  const profileColors = (profile.matching?.colors || []).map(normalizeHex).filter(Boolean);
  if (!profileColors.length || !actualColorSignals.length) return 0;
  let weightedScore = 0;
  let totalWeight = 0;
  for (const signal of actualColorSignals) {
    const weight = Math.max(0.01, Number(signal.weight) || 0);
    const best = Math.max(...profileColors.map(color => colorSimilarity(signal.hex, color)));
    weightedScore += best * weight;
    totalWeight += weight;
  }
  return totalWeight ? weightedScore / totalWeight : 0;
}

function componentScore(profile, componentStyles = {}) {
  const expectations = profile.matching?.component_expectations || {};
  const entries = Object.entries(expectations);
  if (!entries.length) return 0;
  let known = 0;
  let matches = 0;
  for (const [key, expected] of entries) {
    if (typeof componentStyles[key] !== 'boolean') continue;
    known += 1;
    if (componentStyles[key] === expected) matches += 1;
  }
  return known ? matches / known : 0;
}

function buildSearchText({ styleName = '', structureData = {}, vlmAnalysis = {}, imageMapData = {} }) {
  const textParts = [styleName];
  collectTextParts(structureData.content_layout_styles || [], textParts);
  collectTextParts(structureData.layout_semantics || [], textParts);
  collectTextParts(vlmAnalysis, textParts);
  collectTextParts(imageMapData, textParts);
  return textParts.join(' ');
}

function scoreProfile(profile, context) {
  const text = buildSearchText(context);
  const matching = profile.matching || {};
  const tone = keywordScore(text, matching.tone_keywords);
  const componentText = keywordScore(text, matching.component_keywords);
  const layout = keywordScore(text, matching.layout_keywords);
  const semantic = keywordScore(text, matching.semantic_keywords);
  const textScore = Math.max(tone, componentText, layout, semantic);
  const colors = colorScore(profile, context.actualColorSignals);
  const components = componentScore(profile, context.structureData?.component_styles || {});
  return {
    color_score: roundScore(colors),
    component_score: roundScore(components),
    keyword_score: roundScore(textScore),
    score: roundScore(colors * 0.5 + components * 0.3 + textScore * 0.2),
  };
}

function confidenceForScore(score) {
  if (score >= HIGH_CONFIDENCE_SCORE) return 'high';
  if (score >= MEDIUM_CONFIDENCE_SCORE) return 'medium';
  if (score > 0) return 'low';
  return 'none';
}

function confidenceForMatch(score, ambiguous) {
  const confidence = confidenceForScore(score);
  return confidence === 'high' && ambiguous ? 'medium' : confidence;
}

function matchPresetStyle({
  styleName = '',
  structureData = {},
  vlmAnalysis = {},
  imageMapData = {},
  profiles = loadPresetProfiles(),
} = {}) {
  const actualColorSignals = collectActualColorSignals(structureData.actual_colors || {});
  const context = {
    styleName,
    structureData,
    vlmAnalysis,
    imageMapData,
    actualColorSignals,
  };
  const candidates = (profiles || [])
    .map(profile => {
      const scored = scoreProfile(profile, context);
      return {
        id: profile.id,
        name: profile.name,
        ...scored,
      };
    })
    .sort((a, b) => b.score - a.score);

  const selected = candidates[0] || null;
  const runnerUp = candidates[1] || null;
  const ambiguous = Boolean(
    selected &&
    runnerUp &&
    selected.score >= MEDIUM_CONFIDENCE_SCORE &&
    selected.score - runnerUp.score < AMBIGUOUS_DELTA
  );
  const confidence = confidenceForMatch(selected?.score || 0, ambiguous);
  const appliedPolicy = selected && confidence === 'high' && !ambiguous
    ? 'preset_execution_typography'
    : 'source_typography_with_extreme_display_guard';

  return {
    selected_profile_id: selected?.id || null,
    selected_profile_name: selected?.name || null,
    confidence,
    score: roundScore(selected?.score || 0),
    ambiguous,
    applied_policy: appliedPolicy,
    actual_color_signals: actualColorSignals,
    top_candidates: candidates.slice(0, 3),
  };
}

function ptToPx(pt) {
  const value = Number(pt);
  return Number.isFinite(value) && value > 0 ? Math.round(value * 96 / 72) : null;
}

function detectDisplayTitleReferences(fontScale = []) {
  const references = [];
  for (const entry of fontScale || []) {
    const sizes = [];
    if (entry?.dominant_pt != null) sizes.push(entry.dominant_pt);
    if (Array.isArray(entry?.common_sizes_pt)) sizes.push(...entry.common_sizes_pt);
    for (const pt of sizes) {
      const px = ptToPx(pt);
      if (!px || px <= EXTREME_PAGE_TITLE_PX) continue;
      if (references.some(item => item.px === px && item.role === entry.role)) continue;
      references.push({
        role: entry.role || '',
        dominant_font: entry.dominant_font || '',
        pt: Number(pt),
        px,
        tailwind: `text-[${px}px]`,
        source: 'extracted_display_reference',
      });
    }
  }
  return references.sort((a, b) => b.px - a.px);
}

function cloneScale(scale = []) {
  return (scale || []).map(item => ({ ...item }));
}

function findProfile(profiles, profileId) {
  return (profiles || []).find(profile => profile.id === profileId) || null;
}

function buildPresetNormalization({
  fontScale = [],
  match = null,
  profiles = loadPresetProfiles(),
} = {}) {
  const displayTitleReference = detectDisplayTitleReferences(fontScale);
  const selectedProfile = match?.applied_policy === 'preset_execution_typography'
    ? findProfile(profiles, match.selected_profile_id)
    : null;
  const executionScale = selectedProfile ? cloneScale(selectedProfile.typography_scale) : [];

  return {
    schema_version: 'ppt-template-generate-typography-normalization-v1',
    execution_policy: selectedProfile
      ? 'preset_execution_typography'
      : 'source_typography_with_extreme_display_guard',
    match: match || null,
    source_font_scale: cloneScale(fontScale),
    display_title_reference: displayTitleReference,
    execution_typography_scale: executionScale,
  };
}

function normalizeFallbackEntry(item, shouldApplyDisplayGuard) {
  const px = Number(item?.px);
  if (
    !shouldApplyDisplayGuard ||
    item?.role !== 'page_title' ||
    !Number.isFinite(px) ||
    px <= EXTREME_PAGE_TITLE_PX
  ) {
    return { ...item };
  }
  const cappedPx = EXTREME_PAGE_TITLE_PX;
  return {
    ...item,
    px: cappedPx,
    tailwind: `text-[${cappedPx}px]`,
    source: 'normalized',
    original_px: px,
  };
}

function resolveExecutionTypographyScale({ normalization = null, fallbackScale = [] } = {}) {
  if (
    normalization?.execution_policy === 'preset_execution_typography' &&
    Array.isArray(normalization.execution_typography_scale) &&
    normalization.execution_typography_scale.length
  ) {
    return cloneScale(normalization.execution_typography_scale);
  }
  const shouldApplyDisplayGuard = Array.isArray(normalization?.display_title_reference) &&
    normalization.display_title_reference.length > 0;
  return cloneScale(fallbackScale).map(item => normalizeFallbackEntry(item, shouldApplyDisplayGuard));
}

module.exports = {
  loadPresetProfiles,
  matchPresetStyle,
  buildPresetNormalization,
  resolveExecutionTypographyScale,
  collectActualColorSignals,
  detectDisplayTitleReferences,
};
