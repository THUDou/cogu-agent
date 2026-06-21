#!/usr/bin/env node

/**
 * create_html.js — 基于 HTML 模板 + docx-js 的 DOCX 生成器
 *
 * 流程: HTML 模板 → 填充数据 → DOM 解析 → docx-js 构建 → DOCX
 *
 * 用法:
 *   node scripts/create_html.js --template meeting_decision --data data.json --output out.docx
 *
 * 参数:
 *   --template <name>   HTML 模板名（对应 scripts/html-templates/{name}.html）
 *   --data      <path>  会议数据 JSON 文件路径
 *   --output    <path>  输出 DOCX 文件路径
 */

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

// ============================================================
// 模板引擎（保留原逻辑）
// ============================================================

function getValue(data, keyPath) {
  const keys = keyPath.split('.');
  let val = data;
  for (const k of keys) {
    if (val == null || typeof val !== 'object') return undefined;
    val = val[k];
  }
  return val;
}

/**
 * 处理 {{#each list}}...{{/each}} 块
 * 策略：从外层到内层处理，使用栈式查找匹配的 {{/each}}
 * 这样内层 each 块在数据可用时才被处理（由外层 each 提供上下文）
 */
function processEach(template, data) {
  let result = template;

  // 循环处理，每次找到并处理第一个（最外层）可处理的 each 块
  while (true) {
    const eachRe = /\{\{#each\s+([\w.]+)\}\}/;
    const match = eachRe.exec(result);
    if (!match) break;

    const listPath = match[1];
    const startIdx = match.index;
    const openTagEnd = startIdx + match[0].length;

    // 通过跟踪嵌套深度找到匹配的 {{/each}}
    let depth = 1;
    let pos = openTagEnd;

    while (depth > 0 && pos < result.length) {
      // 检查是否有 {{/each}} 在当前位置之前
      const closeRe = /\{\{\/each\}\}/g;
      closeRe.lastIndex = pos;
      const closeMatch = closeRe.exec(result);
      if (!closeMatch) break; // 未匹配到闭合标签，退出

      // 在 closeMatch 和 pos 之间查找嵌套的 {{#each
      const betweenText = result.slice(pos, closeMatch.index);
      const innerEachRe = /\{\{#each\s+[\w.]+\}\}/g;
      let innerMatch;
      while ((innerMatch = innerEachRe.exec(betweenText)) !== null) {
        depth++;
      }

      depth--;
      pos = closeMatch.index + closeMatch[0].length;

      if (depth === 0) {
        // 找到了匹配的 {{/each}}
        const blockContent = result.slice(openTagEnd, closeMatch.index);
        const list = getValue(data, listPath);

        if (Array.isArray(list) && list.length > 0) {
          let replacement = '';
          for (const item of list) {
            // 在当前 item 上下文中处理块内容中的嵌套 each
            // 合并 data 和 item 形成临时上下文
            const mergedContext = { ...data, ...item };
            // 但 #each 内的变量应该用 item.xxx 访问
            // 使用 data 作为根，item 在 listPath 下
            // 创建嵌套上下文：根 + 当前项作为 listPath
            const ctx = { ...data };
            // 让 {{xxx}} 也能直接访问 item 字段
            // 设置 item 字段在顶层
            for (const key of Object.keys(item)) {
              ctx[key] = item[key];
            }
            let processed = renderBlock(blockContent, ctx);
            replacement += processed;
          }
          result = result.slice(0, startIdx) + replacement + result.slice(pos);
        } else {
          // 列表为空或不存在，删除整个 each 块
          result = result.slice(0, startIdx) + result.slice(pos);
        }
        break;
      }
    }

    if (depth > 0) {
      // 没有找到匹配的闭合标签，退出循环避免死循环
      break;
    }
  }

  return result;
}

/**
 * 处理 {{#if var}}...{{/if}} 条件块
 */
function processIf(template, data) {
  let result = template;
  const ifRe = /\{\{#if\s+([\w.]+)\}\}([\s\S]*?)\{\{\/if\}\}/;
  let match;

  while ((match = ifRe.exec(result)) !== null) {
    const varPath = match[1];
    const blockContent = match[2];
    const val = getValue(data, varPath);
    if (val && val !== 'false' && val !== '0') {
      // 条件为真，保留内容并处理其中的模板变量
      const processed = renderBlock(blockContent, data);
      result = result.slice(0, match.index) + processed + result.slice(match.index + match[0].length);
    } else {
      // 条件为假，删除整个 if 块
      result = result.slice(0, match.index) + result.slice(match.index + match[0].length);
    }
  }

  return result;
}

/**
 * 处理 {{variable}} 简单变量替换
 */
function processVariables(template, data) {
  return template.replace(/\{\{([\w.]+)\}\}/g, (match, keyPath) => {
    const val = getValue(data, keyPath);
    if (val == null) return '';
    return String(val);
  });
}

/**
 * 三遍渲染：each → if → variables
 */
function renderBlock(template, data) {
  let result = template;
  result = processEach(result, data);
  result = processIf(result, data);
  result = processVariables(result, data);
  return result;
}

// ============================================================
// 样式配置（按模板名）
// ============================================================

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
  // 默认正文 12pt = 24 半磅
  return (conf.body && conf.body.size) || 24;
}

// ============================================================
// HTML → docx-js 转换
// ============================================================

/**
 * 从 HTML 元素提取文本运行信息（字体、样式属性）
 * @param {Object} el - HTML 元素
 * @param {Object} conf - 样式配置
 * @param {boolean} isBold - 父级传递的加粗状态
 * @param {boolean} skipThBold - 是否跳过 <th> 自动加粗（跟踪表/效率表不需要表头加粗）
 */
function extractRuns(el, conf, isBold, skipThBold) {
  const runs = [];

  if (el.nodeType === 3) {
    // 文本节点
    const text = el.textContent || el.rawText || '';
    if (text.trim()) {
      runs.push({ text, bold: isBold });
    }
    return runs;
  }

  if (!el.tagName) return runs;

  const tag = el.tagName.toLowerCase();
  const classNames = (el.getAttribute('class') || '').split(' ').filter(Boolean);
  // Determine bold state from element/tag
  let thisBold = isBold;
  if (tag === 'strong' || tag === 'b') thisBold = true;
  if (tag === 'th' && !skipThBold) thisBold = true;
  if (classNames.includes('merged')) thisBold = true;
  if (classNames.includes('label')) thisBold = (conf.tableLabel && conf.tableLabel.bold === false) ? false : true;
  if (classNames.includes('resolution-item') || classNames.includes('resolution-label')) thisBold = true;

  // 检查 childNodes
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

/**
 * 构建 TextRun 数组（统一字体、大小）
 * @param {Array} runs - 文本运行数组 [{text, bold, size, font}]
 * @param {Object} conf - 样式配置
 * @param {boolean} defaultBold - 段落级默认加粗
 * @param {number} defaultSize - 段落级默认字号（半磅值），覆盖 conf 配置
 * @param {string} defaultFont - 段落级默认字体，覆盖 conf.fonts.ascii
 */
function buildTextRuns(runs, conf, defaultBold, defaultSize, defaultFont) {
  const baseSize = defaultSize || getBaseSize(conf);
  const baseFont = defaultFont || conf.fonts.ascii || 'SimSun';
  return runs.map(r => {
    const runOptions = {
      text: r.text,
      font: r.font || baseFont,
      size: r.size || baseSize,
    };

    // 加粗
    if (r.bold || defaultBold) {
      runOptions.bold = true;
    }

    // 对齐方式
    if (r.alignment) {
      runOptions.alignment = r.alignment;
    }

    return new TextRun(runOptions);
  });
}

/**
 * 将 <p> 元素转换为 Paragraph
 */
function elementToParagraph(el, conf) {
  const classNames = (el.getAttribute('class') || '').split(' ').filter(Boolean);
  const paraOptions = {
    spacing: { before: 30, after: 30, line: 360 },
  };

  // 样式映射
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
    // 首行缩进两个字符（约480 DXA）
    paraOptions.indent = { firstLine: 480 };
  } else if (classNames.includes('resolution-item')) {
    paraBold = true;
    paraOptions.indent = { firstLine: 480 };
  } else if (classNames.includes('first-indent')) {
    // 首行缩进 两个字符 (约 480 twips = 24pt * 2)
    paraOptions.indent = { firstLine: 480 };
  } else if (classNames.includes('conclusion-item')) {
  } else if (classNames.includes('attachment-item')) {
    // 附件项：减少段落间距避免多余换行
    paraOptions.spacing = { before: 0, after: 0 };
  } else if (classNames.includes('signoff')) {
    // 落款：右对齐
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
    // 章节之间额外间距
    paraOptions.spacing = { before: 240, after: 0 };
  } else if (classNames.includes('note')) {
    // italic handled via text run
  }

  if (paraAlignment) {
    paraOptions.alignment = paraAlignment;
  }

  // 提取文本运行
  const runs = extractRuns(el, conf, paraBold);
  const textRuns = buildTextRuns(runs, conf, paraBold, paraSize, paraFont);

  // 如果是从 runs 构建的，使用 runs 中的 bold/size
  if (textRuns.length > 0) {
    paraOptions.children = textRuns;
  } else {
    // 备用：直接使用文本内容
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

  // 制表位：在文本前插入 tab 字符
  if (paraOptions.tabStops && paraOptions.tabStops.length > 0 && paraOptions.children) {
    const tabRun = new TextRun({ text: '\t', size: paraSize || getBaseSize(conf) });
    paraOptions.children.unshift(tabRun);
  }

  return new Paragraph(paraOptions);
}

/**
 * 将 <table> 元素转换为 Table
 */
function elementToTable(el, conf) {
  const classNames = (el.getAttribute('class') || '').split(' ').filter(Boolean);
  const isMeta = classNames.includes('meta');
  const isTrack = classNames.includes('track');
  const isEfficiency = classNames.includes('efficiency');
  const isTasks = classNames.includes('tasks');

  // 行
  const rows = el.querySelectorAll('tr');
  if (!rows || rows.length === 0) return null;

  // 表头信息
  let tableBorders;
  let colWidths;
  let isTasksTable = false;

  if (isMeta) {
    // 元信息表：按模板配置处理
    const metaConf = conf.meta || {};
    const noBorder = { style: BorderStyle.NONE, size: 0 };

    // 判断是否为日常例会（配置了 cellBorderNone 即代表仅上下边框样式）
    if (metaConf.cellBorderNone) {
      // 日常类：上下粗横线，其余无框线
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
      // 决策类：全边框（使用原有逻辑）
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
    // 跟踪表：细边框 single sz=6
    const thinBorder = { style: BorderStyle.SINGLE, size: 6, color: '000000' };
    tableBorders = { top: thinBorder, bottom: thinBorder, left: thinBorder, right: thinBorder, insideHorizontal: thinBorder, insideVertical: thinBorder };
    colWidths = [800, 3000, 2000, 1500, 2000];
  } else if (isEfficiency) {
    // 效率表：细边框 single sz=6
    const thinBorder = { style: BorderStyle.SINGLE, size: 6, color: '000000' };
    tableBorders = { top: thinBorder, bottom: thinBorder, left: thinBorder, right: thinBorder, insideHorizontal: thinBorder, insideVertical: thinBorder };
    colWidths = [1200, 900, 900, 1600, 900, 1600];
  } else if (isTasks) {
    // 遗留任务表：无表级边框（边框在单元格级别）
    const noBorder = { style: BorderStyle.NONE, size: 0 };
    tableBorders = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder, insideHorizontal: noBorder, insideVertical: noBorder };
    colWidths = [695, 5732, 1246, 1354];
    isTasksTable = true;  // 标记用于后续单元格处理
  } else {
    // 未知表格：全边框
    const defBorder = { style: BorderStyle.SINGLE, size: 4, color: '000000' };
    tableBorders = { top: defBorder, bottom: defBorder, left: defBorder, right: defBorder, insideHorizontal: defBorder, insideVertical: defBorder };
    colWidths = null;
  }

  // 对于无 colWidths 的表格，不设置列宽（docx-js 会根据单元格内容自动分配）
  const hasColWidths = colWidths !== null;

  // 处理表头行
  const headerRow = rows[0];
  const headerCells = headerRow.querySelectorAll ? headerRow.querySelectorAll('th, td') : [];

  // 如果第一行全是 th，单独处理表头
  const firstRowHasTh = headerRow.querySelectorAll && headerRow.querySelectorAll('th').length > 0;

  const flatBorder = { style: BorderStyle.SINGLE, size: 6, color: '000000' };
  const noBorder = { style: BorderStyle.NONE, size: 0 };

  function makeMetaCellBorder(metaConf) {
    // 决策类：全边框 single sz=4；日常类：仅顶部边框 thick sz=24
    const full = metaConf.cellBorder || noBorder;
    const topOnly = metaConf.cellBorder || noBorder;
    const none = metaConf.cellBorderNone || noBorder;

    // 如果有 cellBorderNone，说明日常类（仅顶部有边框）
    if (metaConf.cellBorderNone) {
      return { top: none, bottom: none, left: none, right: none };
    }
    // 否则全边框（决策类）
    return { top: full, bottom: full, left: full, right: full };
  }

  const docxRows = rows.map((row, rowIdx) => {
    const cells = row.querySelectorAll ? row.querySelectorAll('td, th') : [];
    if (!cells || cells.length === 0) return null;

    const docxCells = cells.map((cell, cellIdx) => {
      const cellClass = (cell.getAttribute('class') || '').split(' ').filter(Boolean).join(' ');
      const cellTag = cell.tagName ? cell.tagName.toLowerCase() : 'td';
      const isHeader = cellTag === 'th' || (firstRowHasTh && rowIdx === 0);

      // 提取内容
      // 根据表格类型决定字体/字号/加粗
      let cellUseBold = isHeader;
      let cellUseSize = (conf.table && conf.table.size) || getBaseSize(conf);
      let cellUseFont = (conf.table && conf.table.font) || conf.fonts.ascii;
      let skipThBold = false;

      if (isMeta && cellClass.includes('label')) {
        // 元信息表标签
        cellUseFont = (conf.title && conf.title.font) || 'SimSun';
        cellUseSize = 24;
        cellUseBold = (conf.tableLabel && conf.tableLabel.bold !== false);
      } else if (isMeta) {
        // 元信息表值：宋体 12pt
        cellUseSize = 24;
        cellUseBold = false;
      } else if (isTrack || isEfficiency) {
        // 跟踪表/效率表：宋体 10.5pt，不加粗（含 th）
        cellUseBold = false;
        skipThBold = true;
      }

      // 效率表标签需覆盖为黑体
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

      // 计算 colspan 和单元格宽度
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

      // 底纹（阴影）
      if (isMeta && cellClass.includes('label') && conf.meta && conf.meta.labelShading) {
        // 决策类标签底纹 E6E6E6
        cellOptions.shading = {
          type: ShadingType.CLEAR,
          fill: conf.meta.labelShading,
          color: 'auto',
        };
      } else if (isHeader && (isTrack || isEfficiency)) {
        // 跟踪表/效率表表头灰色
        cellOptions.shading = {
          type: ShadingType.CLEAR,
          fill: 'C0C0C0',
          color: 'auto',
        };
      } else if (isTasksTable && isHeader) {
        // 遗留任务表表头 E6E6E6 底纹
        cellOptions.shading = {
          type: ShadingType.CLEAR,
          fill: 'E6E6E6',
          color: 'auto',
        };
      }

      // 边框 — 始终显式设置（防止 docx-js 自动添加默认边框）
      const metaConf = conf.meta || {};
      let cellBorder2;
      if (isMeta) {
        cellBorder2 = makeMetaCellBorder(metaConf);
      } else if (isTasksTable) {
        // 遗留任务表：所有边细边框 single sz=6
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

/**
 * 将 HTML body 子元素转换为 docx-js 对象数组 */
function htmlToDocxElements(bodyEl, conf) {
  const elements = [];
  const children = bodyEl.childNodes || [];

  for (const child of children) {
    if (!child.tagName) continue;
    const tag = child.tagName.toLowerCase();

    if (tag === 'br') {
      // <br> → 空段落（模拟换行间距）
      elements.push(new Paragraph({
        children: [new TextRun({ text: '', size: getBaseSize(conf) })],
        spacing: { before: 60, after: 60 },
      }));
    } else if (tag === 'p' || tag === 'div') {
      // 检查是否有子表格（p 包裹了 table 内容）
      const hasTableChild = child.querySelector && child.querySelector('table');
      if (hasTableChild) {
        // 分裂处理：先处理非 table 部分，再处理 table
        continue; // table 会被单独处理
      }
      elements.push(elementToParagraph(child, conf));
    } else if (tag === 'table') {
      elements.push(elementToTable(child, conf));
    } else if (tag === 'ol' || tag === 'ul') {
      // 列表 - 每个 li 作为一个段落
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
    // 其他标签忽略（style, head, body wrapper 等）
  }

  // 二次遍历：获取所有独立 table
  const tables = bodyEl.querySelectorAll ? bodyEl.querySelectorAll('table') : [];
  // 找到 table 在 body 子元素中的位置并替换对应 p 元素
  // 更简单：将 table 插入到对应位置
  const tableSet = new Set();
  for (const tbl of tables) {
    tableSet.add(tbl);
  }

  return elements;
}

// ============================================================
// 主流程
// ============================================================

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

  // 1. 加载 HTML 模板
  const templatesDir = path.resolve(__dirname, 'html-templates');
  const templatePath = path.resolve(templatesDir, `${template}.html`);
  if (!fs.existsSync(templatePath)) {
    throw new Error(`HTML 模板未找到: ${templatePath}\n可用模板: ${fs.readdirSync(templatesDir).filter(f => f.endsWith('.html')).join(', ')}`);
  }
  const templateHtml = fs.readFileSync(templatePath, 'utf-8');

  // 2. 加载数据 JSON
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

  // 3. 填充模板
  const filledHtml = renderBlock(templateHtml, dataObj);

  // 4. 解析 HTML DOM
  const root = parseHtml(filledHtml);
  const body = root.querySelector('body');

  if (!body) {
    throw new Error('HTML 模板缺少 <body> 标签');
  }

  // 5. 获取模板样式配置
  const conf = STYLE_CONFIGS[template];
  if (!conf) {
    throw new Error(`未找到模板样式配置: ${template}`);
  }

  // 6. 转换 HTML → docx-js 元素
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
      // div 是容器，递归处理其子节点
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

  // 7. 构建 Document
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

  // 8. 生成 DOCX
  let buffer = await Packer.toBuffer(doc);

  // 9. 修复 fontTable.xml 缺失的 Relationship 引用
  // docx-js 在 Content_Types.xml 中注册了 fontTable.xml，但未在
  // word/_rels/document.xml.rels 中添加对应的 Relationship 条目。
  // 这会导致 OPC 验证报 "Unreferenced file: word/fontTable.xml"。
  buffer = await fixFontTableRelationship(buffer);

  const outputPath = path.resolve(output);
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, buffer);

  return outputPath;
}

/**
 * 修复 DOCX 中 fontTable.xml 的关系引用
 *
 * docx-js 生成的 [Content_Types].xml 包含了 fontTable.xml，
 * 但 word/_rels/document.xml.rels 缺少对应的 Relationship，
 * 导致 OPC 验证报 "Unreferenced file: word/fontTable.xml"。
 */
async function fixFontTableRelationship(buffer) {
  const zip = await JSZip.loadAsync(buffer);

  // 检查 document.xml.rels 是否已包含 fontTable 引用
  const relsPath = 'word/_rels/document.xml.rels';
  const relsFile = zip.file(relsPath);
  if (!relsFile) return buffer; // 没有 rels 文件，跳过

  let relsXml = await relsFile.async('string');

  // 如果已经存在 fontTable 关系，跳过
  if (relsXml.includes('fontTable.xml')) return buffer;

  // 找到最后一个 Relationship，在其后插入 fontTable 引用
  // 先计算最大 rId
  const rIdRegex = /Id="rId(\d+)"/g;
  let maxId = 0;
  let match;
  while ((match = rIdRegex.exec(relsXml)) !== null) {
    maxId = Math.max(maxId, parseInt(match[1], 10));
  }
  const newId = maxId + 1;

  // 在 </Relationships> 前插入新关系
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
