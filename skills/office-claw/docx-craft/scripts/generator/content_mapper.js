const {
  Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, PageBreak, AlignmentType,
  WidthType, ShadingType, BorderStyle, LevelFormat,
  ImageRun, ExternalHyperlink, FootnoteReferenceRun,
} = require('docx');
const fs = require('fs');
const path = require('path');

function mapContent(contentItems, numbering = null, recipe = null) {
  return contentItems.map(item => mapItem(item, numbering, recipe)).flat();
}

function mapItem(item, numbering = null, recipe = null) {
  switch (item.type) {
    case 'heading':
      return mapHeading(item);
    case 'paragraph':
      return mapParagraph(item);
    case 'title':
      return mapTitle(item);
    case 'subtitle':
      return mapSubtitle(item);
    case 'bullet_list':
      return mapBulletList(item, numbering);
    case 'numbered_list':
      return mapNumberedList(item, numbering);
    case 'table':
      return mapTable(item, recipe);
    case 'pagebreak':
      return new Paragraph({ children: [new PageBreak()] });
    case 'image':
      return mapImage(item);
    case 'hyperlink':
      return mapHyperlink(item);
    default:
      return mapParagraph(item);
  }
}

function mapHeading(item) {
  const level = Math.min(Math.max(item.level || 1, 1), 6);
  const headingMap = {
    1: HeadingLevel.HEADING_1,
    2: HeadingLevel.HEADING_2,
    3: HeadingLevel.HEADING_3,
    4: HeadingLevel.HEADING_4,
    5: HeadingLevel.HEADING_5,
    6: HeadingLevel.HEADING_6,
  };

  return new Paragraph({
    heading: headingMap[level],
    children: parseInlineFormatting(item.text || ''),
  });
}

function mapParagraph(item) {
  const text = item.text || '';
  const options = {
    children: parseInlineFormatting(text),
  };

  if (item.alignment) {
    options.alignment = _parseAlignment(item.alignment);
  }
  if (item.spacing) {
    options.spacing = item.spacing;
  }
  if (item.indent) {
    options.indent = item.indent;
  }

  return new Paragraph(options);
}

function mapTitle(item) {
  return new Paragraph({
    style: 'Title',
    children: [new TextRun({ text: item.text || '', bold: true })],
  });
}

function mapSubtitle(item) {
  return new Paragraph({
    style: 'Subtitle',
    children: [new TextRun({ text: item.text || '' })],
  });
}

function mapBulletList(item, numbering) {
  if (!numbering) {
    return (item.items || []).map(text => {
      return new Paragraph({
        bullet: { level: 0 },
        children: parseInlineFormatting(typeof text === 'string' ? text : text.text || ''),
      });
    });
  }
  return (item.items || []).map(text => {
    return new Paragraph({
      numbering: { reference: numbering.bulletRef, level: 0 },
      children: parseInlineFormatting(typeof text === 'string' ? text : text.text || ''),
    });
  });
}

function mapNumberedList(item, numbering) {
  if (!numbering) {
    return (item.items || []).map((text, i) => {
      return new Paragraph({
        children: [
          new TextRun({ text: `${i + 1}. ` }),
          ...parseInlineFormatting(typeof text === 'string' ? text : text.text || ''),
        ],
      });
    });
  }
  return (item.items || []).map(text => {
    return new Paragraph({
      numbering: { reference: numbering.numberRef, level: 0 },
      children: parseInlineFormatting(typeof text === 'string' ? text : text.text || ''),
    });
  });
}

function mapTable(item, recipe = null) {
  const headers = item.headers || [];
  const rows = item.rows || [];
  const colCount = headers.length || (rows[0] ? rows[0].length : 1);

  const tableStyle = recipe?.extendedStyles?.table || {};
  const borderCfg = tableStyle.borders || {};
  const headerCfg = tableStyle.headerRow || {};
  const bandedCfg = tableStyle.bandedRows || null;

  const totalWidth = 9360; // US Letter 1" margins
  const colWidth = Math.floor(totalWidth / colCount);
  const columnWidths = Array(colCount).fill(colWidth);
  columnWidths[colCount - 1] = totalWidth - colWidth * (colCount - 1);

  const borderSize = borderCfg.size !== undefined ? Math.max(1, Math.round(borderCfg.size / 4)) : 1;
  const borderColor = borderCfg.color === 'auto' ? '000000' : (borderCfg.color || 'CCCCCC');
  const borderStyle = _mapBorderStyle(borderCfg.style) || BorderStyle.SINGLE;
  const border = { style: borderStyle, size: borderSize, color: borderColor };
  const borders = { top: border, bottom: border, left: border, right: border };

  const tableRows = [];

  if (headers.length > 0) {
    const headerFill = headerCfg.fill || 'F2F2F2';
    const headerColor = headerCfg.color || undefined;
    tableRows.push(
      new TableRow({
        tableHeader: true,
        children: headers.map((h, i) =>
          new TableCell({
            borders,
            width: { size: columnWidths[i], type: WidthType.DXA },
            shading: { fill: headerFill, type: ShadingType.CLEAR },
            margins: { top: 80, bottom: 80, left: 120, right: 120 },
            children: [
              new Paragraph({
                children: [new TextRun({
                  text: String(h),
                  bold: headerCfg.bold !== false,
                  size: 20,
                  color: headerColor,
                })],
              }),
            ],
          })
        ),
      })
    );
  }

  rows.forEach((row, rowIdx) => {
    const cells = Array.isArray(row) ? row : [row];
    const bandedFill = bandedCfg && rowIdx % 2 === 1 ? bandedCfg.fill : undefined;
    tableRows.push(
      new TableRow({
        children: cells.map((cell, i) =>
          new TableCell({
            borders,
            width: { size: columnWidths[i] || colWidth, type: WidthType.DXA },
            shading: bandedFill ? { fill: bandedFill, type: ShadingType.CLEAR } : undefined,
            margins: { top: 80, bottom: 80, left: 120, right: 120 },
            children: [
              new Paragraph({
                children: [new TextRun({ text: String(cell), size: 20 })],
              }),
            ],
          })
        ),
      })
    );
  });

  return new Table({
    width: { size: totalWidth, type: WidthType.DXA },
    columnWidths,
    rows: tableRows,
  });
}

function mapImage(item) {
  const imagePath = item.path || '';
  if (!fs.existsSync(imagePath)) {
    return new Paragraph({
      children: [new TextRun({ text: `[Image not found: ${imagePath}]`, color: 'FF0000' })],
    });
  }

  const data = fs.readFileSync(imagePath);
  const ext = path.extname(imagePath).slice(1).toLowerCase();
  const typeMap = { jpg: 'jpg', jpeg: 'jpg', png: 'png', gif: 'gif', bmp: 'bmp', svg: 'svg' };

  return new Paragraph({
    children: [
      new ImageRun({
        type: typeMap[ext] || item.type || 'png',
        data,
        transformation: {
          width: item.width || 400,
          height: item.height || 300,
        },
        altText: {
          title: item.alt || 'Image',
          description: item.alt || 'Image',
          name: path.basename(imagePath),
        },
      }),
    ],
  });
}

function mapHyperlink(item) {
  return new Paragraph({
    children: [
      new ExternalHyperlink({
        children: [new TextRun({ text: item.text || item.link, style: 'Hyperlink' })],
        link: item.link,
      }),
    ],
  });
}

function parseInlineFormatting(text) {
  if (!text) return [new TextRun('')];

  const runs = [];
  const pattern = /(\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`)/g;
  let lastIndex = 0;
  let match;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      runs.push(new TextRun({ text: text.slice(lastIndex, match.index) }));
    }

    if (match[2]) {
      runs.push(new TextRun({ text: match[2], bold: true }));
    } else if (match[3]) {
      runs.push(new TextRun({ text: match[3], italics: true }));
    } else if (match[4]) {
      runs.push(new TextRun({ text: match[4], font: 'Courier New', size: 20 }));
    }

    lastIndex = pattern.lastIndex;
  }

  if (lastIndex < text.length) {
    runs.push(new TextRun({ text: text.slice(lastIndex) }));
  }

  return runs.length > 0 ? runs : [new TextRun(text)];
}

function buildNumbering(recipe = null) {
  const listStyle = recipe?.extendedStyles?.list || {};
  const bulletIndent = listStyle.bullet?.indent || 720;
  const bulletHanging = listStyle.bullet?.hanging || 360;
  const numberIndent = listStyle.number?.indent || 720;
  const numberHanging = listStyle.number?.hanging || 360;

  return {
    bulletRef: 'bullets',
    numberRef: 'numbers',
    config: [
      {
        reference: 'bullets',
        levels: [
          {
            level: 0,
            format: LevelFormat.BULLET,
            text: '•',
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: bulletIndent, hanging: bulletHanging } } },
          },
        ],
      },
      {
        reference: 'numbers',
        levels: [
          {
            level: 0,
            format: LevelFormat.DECIMAL,
            text: '%1.',
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: numberIndent, hanging: numberHanging } } },
          },
        ],
      },
    ],
  };
}

function _parseAlignment(align) {
  const map = {
    left: AlignmentType.LEFT,
    center: AlignmentType.CENTER,
    right: AlignmentType.RIGHT,
    justified: AlignmentType.JUSTIFIED,
  };
  return map[align?.toLowerCase()] || AlignmentType.LEFT;
}

function _mapBorderStyle(styleName) {
  const map = {
    single: BorderStyle.SINGLE,
    double: BorderStyle.DOUBLE,
    dashed: BorderStyle.DASHED,
    dotted: BorderStyle.DOTTED,
    dotDash: BorderStyle.DOT_DASH,
    dotDotDash: BorderStyle.DOT_DOT_DASH,
    triple: BorderStyle.TRIPLE,
    thick: BorderStyle.THICK,
    thinThickSmallGap: BorderStyle.THIN_THICK_SMALL_GAP,
    thickThinSmallGap: BorderStyle.THICK_THIN_SMALL_GAP,
    thinThickThinSmallGap: BorderStyle.THIN_THICK_THIN_SMALL_GAP,
    thinThickMediumGap: BorderStyle.THIN_THICK_MEDIUM_GAP,
    thickThinMediumGap: BorderStyle.THICK_THIN_MEDIUM_GAP,
    thinThickThinMediumGap: BorderStyle.THIN_THICK_THIN_MEDIUM_GAP,
    thinThickLargeGap: BorderStyle.THIN_THICK_LARGE_GAP,
    thickThinLargeGap: BorderStyle.THICK_THIN_LARGE_GAP,
    thinThickThinLargeGap: BorderStyle.THIN_THICK_THIN_LARGE_GAP,
    wave: BorderStyle.WAVE,
    doubleWave: BorderStyle.DOUBLE_WAVE,
    dashSmallGap: BorderStyle.DASH_SMALL_GAP,
    dashDotStroked: BorderStyle.DASH_DOT_STROKED,
    threeDEmboss: BorderStyle.THREE_D_EMBOSS,
    threeDEngrave: BorderStyle.THREE_D_ENGRAVE,
    outset: BorderStyle.OUTSET,
    inset: BorderStyle.INSET,
    nil: BorderStyle.NIL,
    none: BorderStyle.NIL,
  };
  return map[styleName?.toLowerCase()] || BorderStyle.SINGLE;
}

module.exports = { mapContent, mapItem, parseInlineFormatting, buildNumbering };
