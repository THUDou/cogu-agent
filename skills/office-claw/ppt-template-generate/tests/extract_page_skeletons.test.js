'use strict';
const assert = require('assert');
const {
  pxFromEmu,
  inferSlotFromElement,
  computeVisualSignature,
  inferSemanticType,
  isTemplateCollectionPptx,
} = require('../scripts/extract-page-skeletons.js');

// pxFromEmu
assert.equal(pxFromEmu(914400), 96, 'pxFromEmu: 1 inch = 96px');
assert.equal(pxFromEmu(0), 0,  'pxFromEmu: 0 EMU = 0 px');
assert.equal(pxFromEmu(9144000), 960, 'pxFromEmu: 10 inches = 960px');

// inferSlotFromElement — placeholder wins
assert.equal(inferSlotFromElement({ type: 'text', placeholder: 'title',    font_size_pt: 32 }), 'title');
assert.equal(inferSlotFromElement({ type: 'text', placeholder: 'ctr title',font_size_pt: 32 }), 'title');
assert.equal(inferSlotFromElement({ type: 'text', placeholder: 'subtitle', font_size_pt: 18 }), 'subtitle');
assert.equal(inferSlotFromElement({ type: 'text', placeholder: 'body',     font_size_pt: 18 }), 'body_1');
// infer from font size when no placeholder
assert.equal(inferSlotFromElement({ type: 'text', placeholder: '', font_size_pt: 24 }), 'title');
assert.equal(inferSlotFromElement({ type: 'text', placeholder: '', font_size_pt: 14 }), 'body_1');
// non-text elements return null
assert.equal(inferSlotFromElement({ type: 'shape', font_size_pt: 0 }), null);

// computeVisualSignature
const elems = [
  { type: 'text',      shape_geom: 'rect' },
  { type: 'shape',     shape_geom: 'chevronRight' },
  { type: 'shape',     shape_geom: 'chevronRight' },
  { type: 'connector', shape_geom: 'straightConnector1' },
  { type: 'picture' },
  { type: 'table' },
  { type: 'chart' },
];
const sig = computeVisualSignature(elems);
assert.equal(sig.shape_count,   4, 'shape_count = text + 2 shapes + connector');
assert.equal(sig.picture_count, 1);
assert.equal(sig.table_count,   1);
assert.equal(sig.chart_count,   1);
assert.equal(sig.has_large_arrow, true, 'chevronRight detected as arrow');

// inferSemanticType
assert.equal(inferSemanticType({ has_dashboard_chart: true,  table_count:1, chart_count:1 }), 'data_dashboard');
assert.equal(inferSemanticType({ has_large_arrow:    true,  table_count:0, chart_count:0, has_dashboard_chart:false }), 'arrow_process');
assert.equal(inferSemanticType({ table_count:1,  chart_count:0, has_large_arrow:false, has_dashboard_chart:false }), 'table_layout');
assert.equal(inferSemanticType({ chart_count:1,  table_count:0, has_large_arrow:false, has_dashboard_chart:false }), 'chart_layout');
assert.equal(inferSemanticType({ shape_count:5,  table_count:0, chart_count:0, has_large_arrow:false, has_dashboard_chart:false, has_card_columns:false, picture_count:0 }), 'content');

// isTemplateCollectionPptx — diverse sigs → collection
const diverse = [
  { shape_count:5,  table_count:1, chart_count:0, has_large_arrow:false },
  { shape_count:3,  table_count:0, chart_count:1, has_large_arrow:false },
  { shape_count:8,  table_count:0, chart_count:0, has_large_arrow:true  },
  { shape_count:6,  table_count:0, chart_count:0, has_large_arrow:false },
];
assert.ok(isTemplateCollectionPptx(4, diverse), 'diverse sigs should be collection');
// same sigs → not a collection
const same = Array(4).fill({ shape_count:5, table_count:0, chart_count:0, has_large_arrow:false });
assert.ok(!isTemplateCollectionPptx(4, same), 'identical sigs should not be collection');
// slide_count > 12 → not collection even if diverse
assert.ok(!isTemplateCollectionPptx(13, diverse), '>12 slides is never collection');

console.log('extract_page_skeletons utility tests passed');

const { renderElement, buildSlideHtml } = require('../scripts/extract-page-skeletons.js');

// renderElement — text box
const sc1 = {};
const titleEl = { type:'text', x:457200, y:274638, cx:8229600, cy:1143000,
                  placeholder:'title', font_size_pt:40, bold:true, fill:'#1E3A5F', z_index:0 };
const r1 = renderElement(titleEl, 9144000, 5143500, sc1);
assert.ok(r1 !== null, 'title element should render');
assert.ok(r1.html.includes('data-slot="title"'),   'title slot attribute present');
assert.ok(r1.html.includes('left:48px'),            'x EMU→px: 457200 EMU = 48px');
assert.equal(r1.slot, 'title',                      'slot property = title');

// renderElement — second title becomes title_2
const sc1b = { title: 1 };
const titleEl2 = { type:'text', x:457200, y:500000, cx:4000000, cy:500000,
                   placeholder:'title', font_size_pt:40, bold:false, z_index:1 };
const r1b = renderElement(titleEl2, 9144000, 5143500, sc1b);
assert.ok(r1b.slot !== 'title', 'second title should be title_2 not title');
assert.ok(r1b.html.includes('data-slot="title_2"'), 'second title slot = title_2');

// renderElement — shape rect
const sc2 = {};
const rectEl = { type:'shape', x:914400, y:914400, cx:2743200, cy:1828800,
                 fill:'#FF0000', stroke:'#000000', stroke_width:9144, shape_geom:'rect', z_index:1 };
const r2 = renderElement(rectEl, 9144000, 5143500, sc2);
assert.ok(r2 !== null,               'rect shape should render');
assert.ok(r2.html.includes('<rect'), 'SVG rect element');
assert.ok(r2.html.includes('fill="#FF0000"'), 'fill colour');
assert.equal(r2.slot, null,          'shapes have no slot');

// renderElement — shape ellipse
const sc2b = {};
const ellipseEl = { type:'shape', x:914400, y:914400, cx:2743200, cy:1828800,
                    fill:'#0000FF', shape_geom:'ellipse', z_index:1 };
const r2b = renderElement(ellipseEl, 9144000, 5143500, sc2b);
assert.ok(r2b.html.includes('<ellipse'), 'ellipse uses SVG ellipse element');

// renderElement — picture
const sc3 = {};
const picEl = { type:'picture', x:914400, y:914400, cx:2743200, cy:1828800, z_index:2 };
const r3 = renderElement(picEl, 9144000, 5143500, sc3);
assert.ok(r3 !== null, 'picture should render');
assert.ok(r3.html.includes('data-slot="visual_1"'), 'first picture = visual_1');

// renderElement — table 2×3
const sc4 = {};
const tblEl = { type:'table', x:457200, y:914400, cx:5486400, cy:2743200, rows:2, cols:3, z_index:3 };
const r4 = renderElement(tblEl, 9144000, 5143500, sc4);
assert.ok(r4 !== null, 'table should render');
assert.ok(r4.html.includes('data-slot="table_1"'), 'table slot');
assert.ok(r4.html.includes('data-slot="cell_1"'),  'first cell slot');
assert.ok(r4.html.includes('data-slot="cell_6"'),  'last cell of 2×3 = cell_6');

// renderElement — connector
const sc5 = {};
const cxnEl = { type:'connector', x:457200, y:914400, cx:4572000, cy:9144,
                stroke:'#444444', stroke_width:9144, z_index:4 };
const r5 = renderElement(cxnEl, 9144000, 5143500, sc5);
assert.ok(r5 !== null,               'connector should render');
assert.ok(r5.html.includes('<line'), 'SVG line element');
assert.equal(r5.slot, null,          'connectors have no slot');

// renderElement — chart
const sc6 = {};
const chartEl = { type:'chart', x:457200, y:914400, cx:4572000, cy:2286000, z_index:5 };
const r6 = renderElement(chartEl, 9144000, 5143500, sc6);
assert.ok(r6 !== null, 'chart should render');
assert.ok(r6.html.includes('data-slot="chart_1"'), 'chart slot');

// renderElement — group with nested children (slots surfaced via flatMap)
const sc7 = {};
const groupEl = {
  type: 'group', x: 457200, y: 914400, cx: 4572000, cy: 2286000, z_index: 6,
  children: [
    { type: 'text', x: 500000, y: 1000000, cx: 1000000, cy: 300000,
      placeholder: 'body', font_size_pt: 18, z_index: 0 },
    { type: 'shape', x: 1600000, y: 1000000, cx: 800000, cy: 300000,
      fill: '#CCCCCC', shape_geom: 'rect', z_index: 1 },
  ],
};
const r7 = renderElement(groupEl, 9144000, 5143500, sc7);
assert.ok(r7 !== null, 'group should render');
assert.ok(r7.slots && r7.slots.length > 0, 'group should surface child slots');
assert.ok(r7.slots.includes('body_1'), 'body text slot surfaced from group');

// renderElement — zero dimension element returns null
const sc8 = {};
const zeroEl = { type:'shape', x:0, y:0, cx:0, cy:100, fill:'#FF0000', shape_geom:'rect', z_index:0 };
assert.equal(renderElement(zeroEl, 9144000, 5143500, sc8), null, 'zero-width element returns null');

// buildSlideHtml — required quality-gate HTML attributes
const mockSlide = {
  index: 1,
  elements: [
    { type:'text', x:457200, y:274638, cx:8229600, cy:1143000,
      placeholder:'title', font_size_pt:40, bold:true, z_index:0 },
    { type:'shape', x:914400, y:1828800, cx:2743200, cy:1828800,
      fill:'#1E3A5F', shape_geom:'rect', z_index:1 },
    { type:'picture', x:3657600, y:1828800, cx:2743200, cy:1828800, z_index:2 },
  ],
};
const { html: bHtml, slots: bSlots } = buildSlideHtml(mockSlide, 'layout-001-test', 9144000, 5143500, null);
assert.ok(bHtml.includes('<meta name="template-id" content="layout-001-test"'), 'meta template-id');
assert.ok(bHtml.includes('data-template-id="layout-001-test"'),                 'data-template-id attr');
assert.ok(bHtml.includes('class="slide template-layout-001-test"'),             'root class');
assert.ok(bHtml.includes('template-layer'),                                     'template-layer present');
assert.ok(bHtml.includes('data-slot='),                                         'at least one slot');
assert.ok(bSlots.includes('title'),    'title slot in output slots array');
assert.ok(bSlots.includes('visual_1'),'visual_1 slot in output slots array');

// buildSlideHtml — no forbidden content
assert.ok(!bHtml.includes('file://'),  'no file:// URLs in template HTML');
assert.ok(!bHtml.includes('slides/'), 'no slides/ screenshot reference');

// buildSlideHtml — spec colours propagate when spec provided
const colorSpec = {
  colors: { primary: '#112233', background: '#FFEEDD', text: '#445566' },
};
const { html: cHtml } = buildSlideHtml(mockSlide, 'layout-colour-test', 9144000, 5143500, colorSpec);
assert.ok(cHtml.includes('--color-primary: #112233'),    'primary colour from spec');
assert.ok(cHtml.includes('--color-background: #FFEEDD'), 'background colour from spec');
assert.ok(cHtml.includes('--color-text: #445566'),       'text colour from spec');

console.log('renderElement + buildSlideHtml tests passed');
