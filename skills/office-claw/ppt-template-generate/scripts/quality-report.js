const fs = require('fs');
const path = require('path');
const {
  matchPresetStyle,
  buildPresetNormalization,
} = require('./preset-style-normalizer.js');

function extractHexColorsFromVlm(vlmAnalysis) {
  const hexes = [];
  const seen = new Set();
  for (const analysis of (vlmAnalysis.analyses || [])) {
    const colorScheme = analysis['配色方案'] || {};
    for (const value of Object.values(colorScheme)) {
      const matches = String(value || '').match(/#[0-9A-Fa-f]{6}/g) || [];
      for (const m of matches) {
        const upper = m.toUpperCase();
        if (!seen.has(upper)) { seen.add(upper); hexes.push(upper); }
      }
    }
  }
  return hexes;
}

function fontSizesToScale(fontSizes = {}) {
  return Object.entries(fontSizes || {}).map(([role, info]) => ({
    role,
    dominant_pt: info?.dominant_pt ?? null,
    common_sizes_pt: info?.common_sizes_pt || [],
    dominant_font: info?.dominant_font || '',
  }));
}

function generateQualityReport(options = {}) {
  const { skipVlm = false, styleName = '', structureData = {}, vlmAnalysis = {}, reusableStyleAssets, vlmFallbackReason = null } = options;

  const actualColors = new Set(
    Object.keys(structureData.actual_colors || {}).map(c => c.toUpperCase())
  );

  const analyses = Array.isArray(vlmAnalysis.analyses) ? vlmAnalysis.analyses : [];
  const hasFixedComposition = analyses.some(a => Array.isArray(a.fixed_composition) && a.fixed_composition.length > 0);
  const hasLayoutSemantics = analyses.some(a => Array.isArray(a.layout_semantics) && a.layout_semantics.length > 0);

  const missingRequiredFields = [];
  if (!hasFixedComposition) missingRequiredFields.push('fixed_composition');

  const vlmHexes = extractHexColorsFromVlm(vlmAnalysis);
  const filteredVlmHexes = vlmHexes.filter(hex => !actualColors.has(hex));
  const presetStyleMatch = matchPresetStyle({
    styleName,
    structureData,
    vlmAnalysis,
  });
  const typographyNormalization = buildPresetNormalization({
    fontScale: fontSizesToScale(structureData.font_sizes || {}),
    match: presetStyleMatch,
  });

  const report = {
    vlm: {
      enabled: !skipVlm,
      has_fixed_composition: hasFixedComposition,
      has_layout_semantics: hasLayoutSemantics,
      missing_required_fields: missingRequiredFields,
      fell_back_to_tool_layouts: skipVlm || !analyses.length,
      fallback_reason: vlmFallbackReason,
    },
    colors: {
      filtered_vlm_hexes: filteredVlmHexes,
    },
    asset_policy: {
      slides: 'reference_only',
      images_assets: 'optional_reference',
      bg_images: 'reuse_when_present',
    },
    typography_normalization: {
      preset_style: presetStyleMatch,
      execution_policy: typographyNormalization.execution_policy,
      display_title_reference_count: typographyNormalization.display_title_reference.length,
    },
  };

  if (reusableStyleAssets !== undefined) {
    report.reusable_style_assets = {
      enabled: Array.isArray(reusableStyleAssets.assets),
      assets: Array.isArray(reusableStyleAssets.assets) ? reusableStyleAssets.assets.length : 0,
      rejected_assets: Array.isArray(reusableStyleAssets.rejected_assets) ? reusableStyleAssets.rejected_assets.length : 0,
    };
  }

  return report;
}

function writeQualityReport(filePath, options = {}) {
  const report = generateQualityReport(options);
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(report, null, 2), 'utf-8');
  return report;
}

module.exports = { generateQualityReport, writeQualityReport };
