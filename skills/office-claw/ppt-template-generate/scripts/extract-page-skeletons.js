#!/usr/bin/env node
'use strict';

const fs   = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const EMU_PX = 96 / 914400;

function pxFromEmu(emu) {
  return Math.round(Number(emu) * EMU_PX);
}

function inferSlotFromElement(el) {
  if (!el || el.type !== 'text') return null;
  const ph = String(el.placeholder || '').toLowerCase().trim();
  if (ph === 'title' || ph === 'ctr title') return 'title';
  if (ph === 'subtitle') return 'subtitle';
  if (ph === 'body')     return 'body_1';
  const fs = el.font_size_pt || 0;
  return fs >= 20 ? 'title' : 'body_1';
}

function computeVisualSignature(elements) {
  let shapeCount = 0, picCount = 0, tableCount = 0, chartCount = 0;
  let connCount = 0, groupCount = 0;
  const geomCounts = {};
  let hasArrow = false;

  function walk(els) {
    for (const el of els) {
      if      (el.type === 'shape')     shapeCount++;
      else if (el.type === 'text')      shapeCount++;   // text boxes count as shapes
      else if (el.type === 'picture')   picCount++;
      else if (el.type === 'table')     tableCount++;
      else if (el.type === 'chart')     chartCount++;
      else if (el.type === 'connector') connCount++;
      else if (el.type === 'group')   { groupCount++; if (el.children) walk(el.children); }
      if (el.shape_geom) geomCounts[el.shape_geom] = (geomCounts[el.shape_geom] || 0) + 1;
      if (el.shape_geom && /arrow|chevron/i.test(el.shape_geom)) hasArrow = true;
    }
  }
  walk(elements);

  shapeCount += connCount;   // connectors roll into shape_count

  const dominant = Object.entries(geomCounts)
    .sort((a, b) => b[1] - a[1]).slice(0, 3).map(([k]) => k);

  return {
    shape_count:          shapeCount,
    picture_count:        picCount,
    table_count:          tableCount,
    chart_count:          chartCount,
    group_count:          groupCount,
    dominant_shape_types: dominant,
    has_large_arrow:      hasArrow,
    has_timeline:         hasArrow || connCount >= 3,
    has_dashboard_chart:  chartCount >= 1 && tableCount >= 1,
    has_card_columns:     groupCount >= 3,
  };
}

function inferSemanticType(sig) {
  if (sig.has_dashboard_chart)              return 'data_dashboard';
  if (sig.table_count >= 1)                 return 'table_layout';
  if (sig.chart_count >= 1)                 return 'chart_layout';
  if (sig.has_large_arrow)                  return 'arrow_process';
  if (sig.has_timeline)                     return 'timeline';
  if (sig.has_card_columns)                 return 'result_cards';
  if ((sig.picture_count || 0) >= 2)        return 'image_gallery';
  return 'content';
}

function isTemplateCollectionPptx(slideCount, signatures) {
  if (slideCount === 0) return false;
  if (slideCount > 12) return false;
  const keys = signatures.map(s => JSON.stringify({
    sc: s.shape_count, tc: s.table_count, cc: s.chart_count, a: s.has_large_arrow,
  }));
  const unique = new Set(keys).size;
  return unique / slideCount >= 0.65;
}


function _hex(val) {
  return typeof val === 'string' && /^#[0-9a-fA-F]{6}$/.test(val) ? val : null;
}
function _clampZ(z) { return Math.min(999, Math.max(0, Number(z) || 0)); }
function _htmlEsc(str) {
  return String(str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function renderElement(el, slideW, slideH, slotCounters) {
  if (!el) return null;
  const x = pxFromEmu(el.x), y = pxFromEmu(el.y);
  const w = pxFromEmu(el.cx), h = pxFromEmu(el.cy);
  if (w <= 0 || h <= 0) return null;
  const base = `left:${x}px; top:${y}px; width:${w}px; height:${h}px;`;
  const z = _clampZ(el.z_index);

  if (el.type === 'text') {
    const baseSlot = inferSlotFromElement(el) || 'body_1';
    slotCounters[baseSlot] = (slotCounters[baseSlot] || 0) + 1;
    const slot = slotCounters[baseSlot] > 1 ? `${baseSlot.replace(/_1$/, '')}_${slotCounters[baseSlot]}` : baseSlot;
    const rawPx = el.font_size_pt ? Math.round(el.font_size_pt * 96 / 72) : 0;
    const fsPx  = rawPx > 0 ? `font-size:${Math.min(Math.max(rawPx, 11), 96)}px;` : '';
    const bg    = _hex(el.fill) ? `background:${el.fill};` : '';
    const bold  = el.bold ? 'font-weight:700;' : '';
    const label = slot.replace(/_/g, ' ');
    return {
      html: `      <div class="pptx-shape text-slot" data-slot="${_htmlEsc(slot)}" style="${base} ${fsPx}${bg}${bold} z-index:${z};">${_htmlEsc(label)}</div>`,
      slot,
    };
  }

  if (el.type === 'shape') {
    const fill    = _hex(el.fill)   || 'transparent';
    const stroke  = _hex(el.stroke) || 'none';
    const sw      = el.stroke_width ? Math.max(1, pxFromEmu(el.stroke_width)) : 0;
    const geom    = el.shape_geom || 'rect';
    let inner;
    if (geom === 'ellipse') {
      inner = `<ellipse cx="${Math.round(w/2)}" cy="${Math.round(h/2)}" rx="${Math.round(w/2)}" ry="${Math.round(h/2)}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}"/>`;
    } else if (geom === 'roundRect') {
      const rx = Math.min(8, Math.round(Math.min(w, h) * 0.1));
      inner = `<rect width="${w}" height="${h}" rx="${rx}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}"/>`;
    } else {
      inner = `<rect width="${w}" height="${h}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}"/>`;
    }
    return {
      html: `      <svg class="pptx-shape shape-${_htmlEsc(geom)}" style="${base} z-index:${z}; overflow:visible;" width="${w}" height="${h}">${inner}</svg>`,
      slot: null,
    };
  }

  if (el.type === 'connector') {
    const stroke = _hex(el.stroke) || '#555555';
    const sw     = el.stroke_width ? Math.max(1, pxFromEmu(el.stroke_width)) : 1;
    const x2     = h > w ? 0 : w;
    const y2     = h > w ? h : 0;
    return {
      html: `      <svg class="pptx-shape shape-connector" style="${base} z-index:${z}; overflow:visible;" width="${Math.max(w,1)}" height="${Math.max(h,1)}"><line x1="0" y1="0" x2="${x2}" y2="${y2}" stroke="${stroke}" stroke-width="${sw}"/></svg>`,
      slot: null,
    };
  }

  if (el.type === 'picture') {
    const key = 'visual';
    slotCounters[key] = (slotCounters[key] || 0) + 1;
    const slot = `visual_${slotCounters[key]}`;
    return {
      html: `      <div class="pptx-picture-placeholder" data-slot="${_htmlEsc(slot)}" style="${base} z-index:${z};">${_htmlEsc(slot.replace(/_/g, ' '))}</div>`,
      slot,
    };
  }

  if (el.type === 'table') {
    const key = 'table';
    slotCounters[key] = (slotCounters[key] || 0) + 1;
    const slot = `table_${slotCounters[key]}`;
    const rows = Math.max(1, el.rows || 2);
    const cols = Math.max(1, el.cols || 2);
    let ci = 0;
    const trs = Array.from({ length: rows }, () =>
      `<tr>${Array.from({ length: cols }, () => { ci++; return `<td data-slot="cell_${ci}">cell ${ci}</td>`; }).join('')}</tr>`
    ).join('\n        ');
    return {
      html: `      <table class="pptx-table" data-slot="${_htmlEsc(slot)}" style="${base} z-index:${z}; border-collapse:collapse;">\n        ${trs}\n      </table>`,
      slot,
    };
  }

  if (el.type === 'chart') {
    const key = 'chart';
    slotCounters[key] = (slotCounters[key] || 0) + 1;
    const slot = `chart_${slotCounters[key]}`;
    return {
      html: `      <div class="pptx-chart-placeholder" data-slot="${_htmlEsc(slot)}" style="${base} z-index:${z};">${_htmlEsc(slot.replace(/_/g, ' '))}</div>`,
      slot,
    };
  }

  if (el.type === 'group' && el.children) {
    const childResults = el.children
      .map(c => renderElement(c, slideW, slideH, slotCounters))
      .filter(Boolean);
    if (!childResults.length) return null;
    return {
      html:  childResults.map(r => r.html).join('\n'),
      slot:  null,
      slots: childResults.flatMap(r => r.slot ? [r.slot] : (r.slots || [])),
    };
  }

  return null;
}

function buildSlideHtml(slideData, templateId, slideW, slideH, spec) {
  const elements = slideData.elements || [];
  const slotCounters = {};
  const rendered = elements
    .map(el => renderElement(el, slideW, slideH, slotCounters))
    .filter(Boolean);

  const bodyParts = rendered.map(r => r.html);
  const slots     = rendered.flatMap(r => r.slot ? [r.slot] : (r.slots || []));

  const W = pxFromEmu(slideW), H = pxFromEmu(slideH);
  const primary = _hex(spec?.colors?.primary)    || '#C00000';
  const bg      = _hex(spec?.colors?.background) || '#FFFFFF';
  const txt     = _hex(spec?.colors?.text)        || '#222222';
  const sid     = String(templateId).replace(/[^a-z0-9-_]/gi, '-').toLowerCase();

  const html = `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="template-id" content="${sid}" />
  <meta name="template-kind" content="page-derived" />
  <style>
    :root {
      --slide-width: ${W}px; --slide-height: ${H}px;
      --color-primary: ${primary}; --color-background: ${bg}; --color-text: ${txt};
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: #f3f4f6; }
    .slide {
      position: relative; width: var(--slide-width); height: var(--slide-height);
      overflow: hidden; background: var(--color-background);
    }
    .template-layer { position: absolute; inset: 0; z-index: 2; }
    .pptx-shape { position: absolute; }
    .text-slot { overflow: hidden; display: flex; align-items: center; padding: 4px 8px; color: var(--color-text); }
    .pptx-picture-placeholder, .pptx-chart-placeholder {
      position: absolute; display: flex; align-items: center; justify-content: center;
      border: 2px dashed #999; background: rgba(200,200,200,0.25); color: #666; font-size: 12px;
    }
    .pptx-table { position: absolute; border-collapse: collapse; font-size: 12px; }
    .pptx-table td { border: 1px solid #ccc; padding: 4px 8px; }
  </style>
</head>
<body>
  <section class="slide template-${sid}" data-template-id="${sid}">
    <div class="template-layer">
${bodyParts.join('\n')}
    </div>
  </section>
</body>
</html>
`;
  return { html, slots };
}


function _sigKey(sig) {
  return JSON.stringify({
    sc:    sig.shape_count,
    pc:    sig.picture_count,
    tc:    sig.table_count,
    cc:    sig.chart_count,
    arrow: sig.has_large_arrow,
    geom:  (sig.dominant_shape_types || []).slice(0, 2).sort().join(','),
  });
}


function extractPageSkeletons(pptxPath, outputDir) {
  const { findPythonCmd } = require('./convert_to_images.js');

  const skeletonsDir = path.join(outputDir, 'temp', 'page-skeletons');
  fs.mkdirSync(skeletonsDir, { recursive: true });

  const xmlDataPath = path.join(outputDir, 'temp', 'page-xml.json');
  const scriptPath  = path.join(__dirname, 'extract_page_xml.py');
  const pythonCmd   = findPythonCmd();

  const spawnResult = spawnSync(pythonCmd, [scriptPath, pptxPath, xmlDataPath], {
    stdio: ['pipe', 'pipe', 'pipe'],
  });
  if (spawnResult.status !== 0) {
    const errMsg = (spawnResult.stderr || '').toString().trim() || 'Python extraction failed';
    return { ok: false, error: errMsg, slidesProcessed: 0 };
  }

  if (!fs.existsSync(xmlDataPath)) {
    return { ok: false, error: 'page-xml.json not created', slidesProcessed: 0 };
  }

  let xmlData;
  try { xmlData = JSON.parse(fs.readFileSync(xmlDataPath, 'utf-8')); }
  catch (e) { return { ok: false, error: `parse error: ${e.message}`, slidesProcessed: 0 }; }

  const slideW  = xmlData.slide_size?.width_emu  || 9144000;
  const slideH  = xmlData.slide_size?.height_emu || 5143500;
  const slides  = xmlData.slides || [];

  let spec = null;
  try {
    const sp = path.join(outputDir, 'template-spec.json');
    if (fs.existsSync(sp)) spec = JSON.parse(fs.readFileSync(sp, 'utf-8'));
  } catch {}

  const signatures = [];
  const allEntries = [];

  for (const slide of slides) {
    const idx  = slide.index;
    const sig  = computeVisualSignature(slide.elements || []);
    signatures.push(sig);

    const semanticType = inferSemanticType(sig);
    const padded       = String(idx).padStart(3, '0');
    const templateId   = `layout-${padded}-${semanticType.replace(/_/g, '-')}`;

    const { html, slots } = buildSlideHtml(slide, templateId, slideW, slideH, spec);
    const htmlFile        = `page-${padded}.html`;
    fs.writeFileSync(path.join(skeletonsDir, htmlFile), html, 'utf-8');

    const thinTemplate = slots.filter(s => !/^visual/.test(s)).length < 2;
    allEntries.push({
      id:              templateId,
      source_slide:    idx,
      page_role:       'content',
      semantic_type:   semanticType,
      file:            `temp/page-skeletons/${htmlFile}`,
      slots,
      visual_signature: sig,
      selection_rule:   `适合 ${semanticType.replace(/_/g, ' ')} 类型内容页。`,
      skeleton_fidelity: thinTemplate ? 'low' : 'high',
      _sigKey:           _sigKey(sig),
    });
  }

  const isCollection = isTemplateCollectionPptx(slides.length, signatures);
  let finalTemplates;

  if (!isCollection) {
    const byKey = new Map();
    for (const t of allEntries) {
      if (!byKey.has(t._sigKey)) {
        byKey.set(t._sigKey, { ...t, aliases: [] });
      } else {
        byKey.get(t._sigKey).aliases.push({ id: t.id, source_slide: t.source_slide });
      }
    }
    finalTemplates = Array.from(byKey.values());
  } else {
    finalTemplates = allEntries.map(t => ({ ...t, aliases: [] }));
  }

  const skeletonsJson = {
    schema_version:        'page-skeletons-v1',
    source:                'pptx_xml',
    slide_size:            { width_px: pxFromEmu(slideW), height_px: pxFromEmu(slideH) },
    is_template_collection: isCollection,
    templates:             finalTemplates.map(({ _sigKey: _, ...rest }) => rest),
  };
  const jsonPath = path.join(skeletonsDir, 'page-skeletons.json');
  fs.writeFileSync(jsonPath, JSON.stringify(skeletonsJson, null, 2), 'utf-8');

  return { ok: true, slidesProcessed: slides.length, skeletonsJsonPath: jsonPath, isCollection };
}


module.exports = {
  extractPageSkeletons,
  pxFromEmu,
  inferSlotFromElement,
  computeVisualSignature,
  inferSemanticType,
  isTemplateCollectionPptx,
  renderElement,
  buildSlideHtml,
};

if (require.main === module) {
  const [, , pptxPath, outputDir] = process.argv;
  if (!pptxPath || !outputDir) {
    console.error('Usage: node extract-page-skeletons.js <pptxPath> <outputDir>');
    process.exit(1);
  }
  const result = extractPageSkeletons(pptxPath, outputDir);
  if (result.ok) {
    console.log(`Extracted ${result.slidesProcessed} slides → ${result.skeletonsJsonPath}`);
  } else {
    console.error(`Extraction failed: ${result.error}`);
    process.exit(1);
  }
}
