#!/usr/bin/env node


const fs = require('fs');
const path = require('path');
const JSZip = require('jszip');
const { HTMLElement, parse: parseHtml } = require('node-html-parser');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  WidthType, AlignmentType, ShadingType, BorderStyle,
  Header, Footer, PageNumber, PageReference,
  TabStopType, TabStopPosition,
} = require('docx');
const { safeJsonParse } = require('./utils/json_utils');


function getValue(data, keyPath) {
  const keys = keyPath.split('.');
  let val = data;
  for (const k of keys) {
    if (val == null || typeof val !== 'object') return undefined;
    val = val[k];
  }
  return val;
}

function processEach(template, data) {
  let result = template;

  while (true) {
    const eachRe = /\{\{#each\s+([\w.]+)\}\}/;
    const match = eachRe.exec(result);
    if (!match) break;

    const listPath = match[1];
    const startIdx = match.index;
    const openTagEnd = startIdx + match[0].length;

    let depth = 1;
    let pos = openTagEnd;

    while (depth > 0 && pos < result.length) {
      const closeRe = /\{\{\/each\}\}/g;
      closeRe.lastIndex = pos;
      const closeMatch = closeRe.exec(result);
      if (!closeMatch) break; // 未匹配到闭合标签，退出

      const betweenText = result.slice(pos, closeMatch.index);
      const innerEachRe = /\{\{#each\s+[\w.]+\}\}/g;
      let innerMatch;
      while ((innerMatch = innerEachRe.exec(betweenText)) !== null) {
        depth++;
      }

      depth--;
      pos = closeMatch.index + closeMatch[0].length;

      if (depth === 0) {
        const blockContent = result.slice(openTagEnd, closeMatch.index);
        const list = getValue(data, listPath);

        if (Array.isArray(list) && list.length > 0) {
          let replacement = '';
          for (const item of list) {
            const mergedContext = { ...data, ...item };
            const ctx = { ...data };
            for (const key of Object.keys(item)) {
              ctx[key] = item[key];
            }
            let processed = renderBlock(blockContent, ctx);
            replacement += processed;
          }
          result = result.slice(0, startIdx) + replacement + result.slice(pos);
        } else {
          result = result.slice(0, startIdx) + result.slice(pos);
        }
        break;
      }
    }

    if (depth > 0) {
      break;
    }
  }

  return result;
}

function processIf(template, data) {
  let result = template;
  const ifRe = /\{\{#if\s+([\w.]+)\}\}([\s\S]*?)\{\{\/if\}\}/;
  let match;

  while ((match = ifRe.exec(result)) !== null) {
    const varPath = match[1];
    const blockContent = match[2];
    const val = getValue(data, varPath);
    if (val && val !== 'false' && val !== '0') {
      const processed = renderBlock(blockContent, data);
      result = result.slice(0, match.index) + processed + result.slice(match.index + match[0].length);
    } else {
      result = result.slice(0, match.index) + result.slice(match.index + match[0].length);
    }
  }

  return result;
}

function processVariables(template, data) {
  return template.replace(/\{\{([\w.]+)\}\}/g, (match, keyPath) => {
    const val = getValue(data, keyPath);
    if (val == null) return '';
    return String(val);
  });
}

function renderBlock(template, data) {
  let result = template;
  result = processEach(result, data);
  result = processIf(result, data);
  result = processVariables(result, data);
  return result;
}


const STYLE_CONFIGS = {
  meeting_decision: {
    title: { font: 'SimSun', size: 48, bold: true, alignment: AlignmentType.CENTER },
    subtitle: { font: 'SimSun', size: 48, bold: true, alignment: AlignmentType.CENTER },
    heading: { font: 'SimSun', size: 24, bold: true },
    body: { font: 'SimSun', size: 24, bold: false, ascii: 'Arial', eastAsia: 'Arial' },
    table: { font: 'SimSun', size: 24, bold: false },
    tableLabel: { font: 'SimSun', size: 24, bold: false, shading: 'E6E6E6' },
    fonts: { ascii: 'SimSun', eastAsia: 'Arial', hAnsi: 'Arial' },
    meta: {
      colWidths: [1550, 7476],
      labelShading: 'E6E6E6',
      tableBorder: { style: BorderStyle.SINGLE, size: 4, color: '000000' },
      cellBorder: { style: BorderStyle.SINGLE, size: 4, color: '000000' },
    },
  },
  meeting_daily: {
    title: { font: 'SimHei', size: 36, bold: true, alignment: AlignmentType.CENTER },
    subtitle: { font: 'SimHei', size: 48, bold: true, alignment: AlignmentType.CENTER },
    heading: { font: 'SimHei', size: 28, bold: true },
    body: { font: 'SimSun', size: 24, bold: false, ascii: 'SimSun', eastAsia: 'SimSun' },
    table: { font: 'SimSun', size: 21, bold: false },
    tableLabel: { font: 'SimSun', size: 24, bold: true },
    fonts: { ascii: 'SimSun', eastAsia: '宋体', hAnsi: 'SimSun' },
    meta: {
      colWidths: [1910, 7116],
      tableBorder: { style: BorderStyle.NONE, size: 0 },
      cellBorder: { style: BorderStyle.SINGLE, size: 24, color: '000000' },
      cellBorderNone: { style: BorderStyle.NONE, size: 0 },
    },
  },
  meeting_seminar: {
    title: { font: 'SimHei', size: 36, bold: true, alignment: AlignmentType.CENTER },
    subtitle: { font: 'SimHei', size: 48, bold: true, alignment: AlignmentType.CENTER },
    heading: { font: 'SimHei', size: 28, bold: true },
    body: { font: 'SimSun', size: 24, bold: false, ascii: 'SimSun', eastAsia: 'SimSun' },
    table: { font: 'SimSun', size: 21, bold: false },
    tableLabel: { font: 'SimSun', size: 24, bold: true },
    fonts: { ascii: 'SimSun', eastAsia: '宋体', hAnsi: 'SimSun' },
    meta: {
      colWidths: [1910, 7116],
      tableBorder: { style: BorderStyle.NONE, size: 0 },
      cellBorder: { style: BorderStyle.SINGLE, size: 24, color: '000000' },
      cellBorderNone: { style: BorderStyle.NONE, size: 0 },
    },
  },
};

function getBaseSize(conf) {
  return (conf.body && conf.body.size) || 24;
}


function extractRuns(el, conf, isBold, skipThBold) {
  const runs = [];

  if (el.nodeType === 3) {
    const text = el.textContent || el.rawText || '';
    if (text.trim()) {
      runs.push({ text, bold: isBold });
    }
    return runs;
  }

  if (!el.tagName) return runs;

  const tag = el.tagName.toLowerCase();
  const classNames = (el.getAttribute('class') || '').split(' ').filter(Boolean);
  let thisBold = isBold;
  if (tag === 'strong' || tag === 'b') thisBold = true;
  if (tag === 'th' && !skipThBold) thisBold = true;
  if (classNames.includes('merged')) thisBold = true;
  if (classNames.includes('label')) thisBold = (conf.tableLabel && conf.tableLabel.bold === false) ? false : true;
  if (classNames.includes('resolution-item') || classNames.includes('resolution-label')) thisBold = true;

  const children = el.childNodes || [];
  for (const child of children) {
    if (child.nodeType === 3) {
      const text = child.textContent || child.rawText || '';
      if (text.trim()) {
        runs.push({ text, bold: thisBold });
      }
    } else if (child.tagName) {
      const childRuns = extractRuns(child, conf, thisBold, skipThBold);
      runs.push(...childRuns);
    }
  }

  return runs;
}

function buildTextRuns(runs, conf, defaultBold, defaultSize, defaultFont) {
  const baseSize = defaultSize || getBaseSize(conf);
  const baseFont = defaultFont || conf.fonts.ascii || 'SimSun';
  return runs.map(r => {
    const runOptions = {
      text: r.text,
      font: r.font || baseFont,
      size: r.size || baseSize,
    };

    if (r.bold || defaultBold) {
      runOptions.bold = true;
    }

    if (r.alignment) {
      runOptions.alignment = r.alignment;
    }

    return new TextRun(runOptions);
  });
}

function elementToParagraph(el, conf) {
  const classNames = (el.getAttribute('class') || '').split(' ').filter(Boolean);
  const paraOptions = {
    spacing: { before: 30, after: 30, line: 360 },
  };

  let paraSize = getBaseSize(conf);
  let paraBold = false;
  let paraAlignment;
  let paraFont;

  if (classNames.includes('title-main')) {
    paraSize = (conf.title && conf.title.size) || 48;
    paraBold = true;
    paraAlignment = (conf.title && conf.title.alignment) || AlignmentType.CENTER;
    paraFont = (conf.title && conf.title.font) || conf.fonts.ascii;
  } else if (classNames.includes('title-sub')) {
    paraSize = (conf.subtitle && conf.subtitle.size) || 24;
    paraBold = (conf.subtitle && conf.subtitle.bold) || false;
    paraAlignment = (conf.subtitle && conf.subtitle.alignment) || AlignmentType.CENTER;
    paraFont = (conf.subtitle && conf.subtitle.font) || conf.fonts.ascii;
  } else if (classNames.includes('section-heading')) {
    paraSize = (conf.heading && conf.heading.size) || 28;
    paraBold = true;
    paraFont = (conf.heading && conf.heading.font) || conf.fonts.ascii;
  } else if (classNames.includes('agenda-l1')) {
    paraBold = true;
    paraOptions.spacing = { before: 180, after: 60 };
  } else if (classNames.includes('agenda-l2')) {
    paraOptions.indent = { left: 400 };
  } else if (classNames.includes('agenda-l3')) {
    paraOptions.indent = { left: 800 };
  } else if (classNames.includes('agenda-l4')) {
    paraOptions.indent = { left: 1200 };
  } else if (classNames.includes('resolution-label')) {
    paraBold = true;
    paraOptions.spacing = { before: 120, after: 60 };
    paraOptions.indent = { firstLine: 480 };
  } else if (classNames.includes('resolution-item')) {
    paraBold = true;
    paraOptions.indent = { firstLine: 480 };
  } else if (classNames.includes('first-indent')) {
    paraOptions.indent = { firstLine: 480 };
  } else if (classNames.includes('conclusion-item')) {
  } else if (classNames.includes('attachment-item')) {
    paraOptions.spacing = { before: 0, after: 0 };
  } else if (classNames.includes('signoff')) {
    paraAlignment = AlignmentType.RIGHT;
  } else if (classNames.includes('group-heading')) {
    paraBold = true;
    paraOptions.spacing = { before: 180, after: 60 };
  } else if (classNames.includes('group-conclusion-label')) {
    paraOptions.spacing = { before: 60, after: 40 };
  } else if (classNames.includes('group-conclusion-title')) {
    paraOptions.spacing = { before: 120, after: 60 };
  } else if (classNames.includes('group-detail-l2')) {
    paraOptions.indent = { left: 400 };
  } else if (classNames.includes('group-detail-l3')) {
    paraOptions.indent = { left: 800 };
  } else if (classNames.includes('group-detail-l4')) {
    paraOptions.indent = { left: 1200 };
  } else if (classNames.includes('distribution-date')) {
    paraOptions.tabStops = [{ type: TabStopType.LEFT, position: 4200 }];
  } else if (classNames.includes('distribution-dept')) {
    paraOptions.tabStops = [{ type: TabStopType.LEFT, position: 4200 }];
  } else if (classNames.includes('section-break')) {
    paraOptions.spacing = { before: 240, after: 0 };
  } else if (classNames.includes('note')) {
  }

  if (paraAlignment) {
    paraOptions.alignment = paraAlignment;
  }

  const runs = extractRuns(el, conf, paraBold);
  const textRuns = buildTextRuns(runs, conf, paraBold, paraSize, paraFont);

  if (textRuns.length > 0) {
    paraOptions.children = textRuns;
  } else {
    const text = el.textContent || el.rawText || '';
    if (text.trim()) {
      paraOptions.children = [
        new TextRun({
          text,
          font: conf.fonts.ascii || 'SimSun',
          size: paraSize,
          bold: paraBold,
        }),
      ];
    }
  }

  if (paraOptions.tabStops && paraOptions.tabStops.length > 0 && paraOptions.children) {
    const tabRun = new TextRun({ text: '\t', size: paraSize || getBaseSize(conf) });
    paraOptions.children.unshift(tabRun);
  }

  return new Paragraph(paraOptions);
}

function elementToTable(el, conf) {
  const classNames = (el.getAttribute('class') || '').split(' ').filter(Boolean);
  const isMeta = classNames.includes('meta');
  const isTrack = classNames.includes('track');
  const isEfficiency = classNames.includes('efficiency');
  const isTasks = classNames.includes('tasks');

  const rows = el.querySelectorAll('tr');
  if (!rows || rows.length === 0) return null;

  let tableBorders;
  let colWidths;
  let isTasksTable = false;

  if (isMeta) {
    const metaConf = conf.meta || {};
    const noBorder = { style: BorderStyle.NONE, size: 0 };

    if (metaConf.cellBorderNone) {
      const thickBorder = metaConf.cellBorder; // 取到配置的 size: 24 粗黑线
      tableBorders = {
        top: thickBorder,
        bottom: thickBorder,
        left: noBorder,
        right: noBorder,
        insideHorizontal: noBorder, // 内部横向无框线！
        insideVertical: noBorder    // 内部纵向无框线
      };
    } else {
      const tb = metaConf.tableBorder || noBorder;
      tableBorders = {
        top: tb,
        bottom: tb,
        left: tb,
        right: tb,
        insideHorizontal: tb,
        insideVertical: tb
      };
    }

    colWidths = metaConf.colWidths || [1552, 7474];
  } else if (isTrack) {
    const thinBorder = { style: BorderStyle.SINGLE, size: 6, color: '000000' };
    tableBorders = { top: thinBorder, bottom: thinBorder, left: thinBorder, right: thinBorder, insideHorizontal: thinBorder, insideVertical: thinBorder };
    colWidths = [800, 3000, 2000, 1500, 2000];
  } else if (isEfficiency) {
    const thinBorder = { style: BorderStyle.SINGLE, size: 6, color: '000000' };
    tableBorders = { top: thinBorder, bottom: thinBorder, left: thinBorder, right: thinBorder, insideHorizontal: thinBorder, insideVertical: thinBorder };
    colWidths = [1200, 900, 900, 1600, 900, 1600];
  } else if (isTasks) {
    const noBorder = { style: BorderStyle.NONE, size: 0 };
    tableBorders = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder, insideHorizontal: noBorder, insideVertical: noBorder };
    colWidths = [695, 5732, 1246, 1354];
    isTasksTable = true;  // 标记用于后续单元格处理
  } else {
    const defBorder = { style: BorderStyle.SINGLE, size: 4, color: '000000' };
    tableBorders = { top: defBorder, bottom: defBorder, left: defBorder, right: defBorder, insideHorizontal: defBorder, insideVertical: defBorder };
    colWidths = null;
  }

  const hasColWidths = colWidths !== null;

  const headerRow = rows[0];
  const headerCells = headerRow.querySelectorAll ? headerRow.querySelectorAll('th, td') : [];

  const firstRowHasTh = headerRow.querySelectorAll && headerRow.querySelectorAll('th').length > 0;

  const flatBorder = { style: BorderStyle.SINGLE, size: 6, color: '000000' };
  const noBorder = { style: BorderStyle.NONE, size: 0 };

  function makeMetaCellBorder(metaConf) {
    const full = metaConf.cellBorder || noBorder;
    const topOnly = metaConf.cellBorder || noBorder;
    const none = metaConf.cellBorderNone || noBorder;

    if (metaConf.cellBorderNone) {
      return { top: none, bottom: none, left: none, right: none };
    }
    return { top: full, bottom: full, left: full, right: full };
  }

  const docxRows = rows.map((row, rowIdx) => {
    const cells = row.querySelectorAll ? row.querySelectorAll('td, th') : [];
    if (!cells || cells.length === 0) return null;

    const docxCells = cells.map((cell, cellIdx) => {
      const cellClass = (cell.getAttribute('class') || '').split(' ').filter(Boolean).join(' ');
      const cellTag = cell.tagName ? cell.tagName.toLowerCase() : 'td';
      const isHeader = cellTag === 'th' || (firstRowHasTh && rowIdx === 0);

      let cellUseBold = isHeader;
      let cellUseSize = (conf.table && conf.table.size) || getBaseSize(conf);
      let cellUseFont = (conf.table && conf.table.font) || conf.fonts.ascii;
      let skipThBold = false;

      if (isMeta && cellClass.includes('label')) {
        cellUseFont = (conf.title && conf.title.font) || 'SimSun';
        cellUseSize = 24;
        cellUseBold = (conf.tableLabel && conf.tableLabel.bold !== false);
      } else if (isMeta) {
        cellUseSize = 24;
        cellUseBold = false;
      } else if (isTrack || isEfficiency) {
        cellUseBold = false;
        skipThBold = true;
      }

      if (isEfficiency && cellClass.includes('label')) {
        cellUseFont = (conf.title && conf.title.font) || 'SimSun';
        cellUseBold = true;
      }

      const cellRuns = extractRuns(cell, conf, cellUseBold, skipThBold);
      const textRuns = buildTextRuns(cellRuns, conf, cellUseBold, cellUseSize, cellUseFont);

      if (textRuns.length === 0) {
        const text = cell.textContent || cell.rawText || '';
        if (text.trim()) {
          textRuns.push(new TextRun({
            text,
            font: cellUseFont,
            size: cellUseSize,
            bold: cellUseBold,
          }));
        }
      }

      const colspan = parseInt(cell.getAttribute('colspan') || '1', 10);
      let cellWidth;
      if (colWidths && colspan > 1) {
        let totalW = 0;
        for (let c = 0; c < colspan; c++) {
          totalW += (colWidths[cellIdx + c] || 0);
        }
        cellWidth = { size: totalW, type: WidthType.DXA };
      } else if (colWidths && colWidths[cellIdx] != null) {
        cellWidth = { size: colWidths[cellIdx], type: WidthType.DXA };
      }

      const cellOptions = {
        children: [new Paragraph({
          children: textRuns,
          spacing: { before: 60, after: 60 },
          alignment: cellClass.includes('merged') ? AlignmentType.LEFT : AlignmentType.CENTER,
        })],
        verticalAlign: 'center',
        width: cellWidth,
      };

      if (isMeta && cellClass.includes('label') && conf.meta && conf.meta.labelShading) {
        cellOptions.shading = {
          type: ShadingType.CLEAR,
          fill: conf.meta.labelShading,
          color: 'auto',
        };
      } else if (isHeader && (isTrack || isEfficiency)) {
        cellOptions.shading = {
          type: ShadingType.CLEAR,
          fill: 'C0C0C0',
          color: 'auto',
        };
      } else if (isTasksTable && isHeader) {
        cellOptions.shading = {
          type: ShadingType.CLEAR,
          fill: 'E6E6E6',
          color: 'auto',
        };
      }

      const metaConf = conf.meta || {};
      let cellBorder2;
      if (isMeta) {
        cellBorder2 = makeMetaCellBorder(metaConf);
      } else if (isTasksTable) {
        const tasksBorder = { style: BorderStyle.SINGLE, size: 6, color: '000000' };
        cellBorder2 = { top: tasksBorder, bottom: tasksBorder, left: tasksBorder, right: tasksBorder };
      } else {
        cellBorder2 = { top: flatBorder, bottom: flatBorder, left: flatBorder, right: flatBorder };
      }
      cellOptions.borders = cellBorder2;

      if (colspan > 1) {
        cellOptions.columnSpan = colspan;
      }

      return new TableCell(cellOptions);
    });

    return new TableRow({ children: docxCells });
  }).filter(Boolean);

  const tableOptions = {
    rows: docxRows,
    width: { size: 100, type: WidthType.PERCENTAGE },
    borders: tableBorders,
  };
  if (hasColWidths) {
    tableOptions.columnWidths = colWidths;
  }
  return new Table(tableOptions);
}

function htmlToDocxElements(bodyEl, conf) {
  const elements = [];
  const children = bodyEl.childNodes || [];

  for (const child of children) {
    if (!child.tagName) continue;
    const tag = child.tagName.toLowerCase();

    if (tag === 'br') {
      elements.push(new Paragraph({
        children: [new TextRun({ text: '', size: getBaseSize(conf) })],
        spacing: { before: 60, after: 60 },
      }));
    } else if (tag === 'p' || tag === 'div') {
      const hasTableChild = child.querySelector && child.querySelector('table');
      if (hasTableChild) {
        continue; // table 会被单独处理
      }
      elements.push(elementToParagraph(child, conf));
    } else if (tag === 'table') {
      elements.push(elementToTable(child, conf));
    } else if (tag === 'ol' || tag === 'ul') {
      const lis = child.querySelectorAll('li');
      for (const li of lis) {
        const runs = extractRuns(li, conf, false);
        const textRuns = buildTextRuns(runs, conf, false);
        elements.push(new Paragraph({
          children: textRuns,
          spacing: { before: 30, after: 30 },
          indent: { left: 400 },
        }));
      }
    }
  }

  const tables = bodyEl.querySelectorAll ? bodyEl.querySelectorAll('table') : [];
  const tableSet = new Set();
  for (const tbl of tables) {
    tableSet.add(tbl);
  }

  return elements;
}


function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i++) {
    if (argv[i].startsWith('--')) {
      const key = argv[i].slice(2);
      const next = argv[i + 1];
      if (next && !next.startsWith('--')) {
        args[key] = next;
        i++;
      } else {
        args[key] = true;
      }
    }
  }
  return args;
}

async function build(options) {
  const { template, data, output } = options;

  const templatesDir = path.resolve(__dirname, 'html-templates');
  const templatePath = path.resolve(templatesDir, `${template}.html`);
  if (!fs.existsSync(templatePath)) {
    throw new Error(`HTML 模板未找到: ${templatePath}\n可用模板: ${fs.readdirSync(templatesDir).filter(f => f.endsWith('.html')).join(', ')}`);
  }
  const templateHtml = fs.readFileSync(templatePath, 'utf-8');

  let dataObj;
  if (typeof data === 'string') {
    const dataPath = path.resolve(data);
    if (!fs.existsSync(dataPath)) {
      throw new Error(`数据文件未找到: ${dataPath}`);
    }
    dataObj = safeJsonParse(fs.readFileSync(dataPath, 'utf-8'));
  } else {
    dataObj = data;
  }

  const filledHtml = renderBlock(templateHtml, dataObj);

  const root = parseHtml(filledHtml);
  const body = root.querySelector('body');

  if (!body) {
    throw new Error('HTML 模板缺少 <body> 标签');
  }

  const conf = STYLE_CONFIGS[template];
  if (!conf) {
    throw new Error(`未找到模板样式配置: ${template}`);
  }

  const children = [];
  const bodyNodes = body.childNodes || [];

  for (const child of bodyNodes) {
    if (!child.tagName) continue;
    const tag = child.tagName.toLowerCase();

    if (tag === 'br') {
      children.push(new Paragraph({
        children: [new TextRun({ text: '', size: getBaseSize(conf) })],
        spacing: { before: 60, after: 60 },
      }));
    } else if (tag === 'p') {
      children.push(elementToParagraph(child, conf));
    } else if (tag === 'div') {
      const subElements = htmlToDocxElements(child, conf);
      for (const el of subElements) {
        children.push(el);
      }
    } else if (tag === 'table') {
      children.push(elementToTable(child, conf));
    } else if (tag === 'ol' || tag === 'ul') {
      const lis = child.querySelectorAll('li');
      for (const li of lis) {
        const runs = extractRuns(li, conf, false);
        const textRuns = buildTextRuns(runs, conf, false);
        children.push(new Paragraph({
          children: textRuns,
          spacing: { before: 30, after: 30 },
          indent: { left: 400 },
        }));
      }
    }
  }

  const doc = new Document({
    styles: {
      default: {
        document: {
          run: {
            font: conf.fonts.ascii,
            size: getBaseSize(conf),
          },
        },
      },
    },
    sections: [{
      properties: {
        page: {
          size: { width: 11906, height: 16838 }, // A4
          margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 },
        },
      },
      children,
    }],
  });

  let buffer = await Packer.toBuffer(doc);

  buffer = await fixFontTableRelationship(buffer);

  const outputPath = path.resolve(output);
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, buffer);

  return outputPath;
}

async function fixFontTableRelationship(buffer) {
  const zip = await JSZip.loadAsync(buffer);

  const relsPath = 'word/_rels/document.xml.rels';
  const relsFile = zip.file(relsPath);
  if (!relsFile) return buffer; // 没有 rels 文件，跳过

  let relsXml = await relsFile.async('string');

  if (relsXml.includes('fontTable.xml')) return buffer;

  const rIdRegex = /Id="rId(\d+)"/g;
  let maxId = 0;
  let match;
  while ((match = rIdRegex.exec(relsXml)) !== null) {
    maxId = Math.max(maxId, parseInt(match[1], 10));
  }
  const newId = maxId + 1;

  const newRel = `  <Relationship Id="rId${newId}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/fontTable" Target="fontTable.xml"/>\n`;
  relsXml = relsXml.replace('</Relationships>', newRel + '</Relationships>');

  zip.file(relsPath, relsXml);
  return zip.generateAsync({ type: 'nodebuffer' });
}

function main() {
  const args = parseArgs(process.argv);

  if (!args.template) {
    console.error('Error: --template is required');
    console.error('可用模板: meeting_decision, meeting_daily, meeting_seminar');
    process.exit(1);
  }
  if (!args.data) {
    console.error('Error: --data is required (path to data JSON)');
    process.exit(1);
  }
  if (!args.output) {
    console.error('Error: --output is required (output .docx path)');
    process.exit(1);
  }

  build({
    template: args.template,
    data: args.data,
    output: args.output,
  }).then(outputPath => {
    console.log(`Created: ${outputPath}`);
  }).catch(e => {
    console.error(`Error: ${e.message}`);
    process.exit(1);
  });
}

if (require.main === module) {
  main();
}

module.exports = { build };
