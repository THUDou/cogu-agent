const { HeadingLevel, BorderStyle } = require('docx');

function buildStyles(recipe) {
  const fonts = recipe.fonts || {};
  const bodyFont = fonts.body || {};
  const headingFont = fonts.heading || bodyFont;
  const bodySize = bodyFont.size || 22; // 11pt default
  const lineSpacing = recipe.lineSpacing || 276; // 1.15x

  const styles = {
    default: {
      document: {
        run: {
          font: bodyFont.ascii || 'Calibri',
          size: bodySize,
        },
        paragraph: {
          spacing: { line: lineSpacing },
        },
      },
    },
    paragraphStyles: [
      {
        id: 'Heading1',
        name: 'Heading 1',
        basedOn: 'Normal',
        next: 'Normal',
        quickFormat: true,
        run: {
          font: headingFont.ascii || bodyFont.ascii || 'Calibri',
          size: _getHeadingSize(recipe, 1, 52),
          bold: true,
          color: _getHeadingColor(recipe, 1),
        },
        paragraph: {
          spacing: _getHeadingSpacing(recipe, 1, { before: 480, after: 240 }),
          outlineLevel: 0,
        },
      },
      {
        id: 'Heading2',
        name: 'Heading 2',
        basedOn: 'Normal',
        next: 'Normal',
        quickFormat: true,
        run: {
          font: headingFont.ascii || bodyFont.ascii || 'Calibri',
          size: _getHeadingSize(recipe, 2, 40),
          bold: true,
          color: _getHeadingColor(recipe, 2),
        },
        paragraph: {
          spacing: _getHeadingSpacing(recipe, 2, { before: 360, after: 180 }),
          outlineLevel: 1,
        },
      },
      {
        id: 'Heading3',
        name: 'Heading 3',
        basedOn: 'Normal',
        next: 'Normal',
        quickFormat: true,
        run: {
          font: headingFont.ascii || bodyFont.ascii || 'Calibri',
          size: _getHeadingSize(recipe, 3, 32),
          bold: true,
          color: _getHeadingColor(recipe, 3),
        },
        paragraph: {
          spacing: _getHeadingSpacing(recipe, 3, { before: 240, after: 120 }),
          outlineLevel: 2,
        },
      },
      {
        id: 'Heading4',
        name: 'Heading 4',
        basedOn: 'Normal',
        next: 'Normal',
        quickFormat: true,
        run: {
          font: headingFont.ascii || bodyFont.ascii || 'Calibri',
          size: _getHeadingSize(recipe, 4, 28),
          bold: true,
          color: _getHeadingColor(recipe, 4),
        },
        paragraph: {
          spacing: _getHeadingSpacing(recipe, 4, { before: 200, after: 100 }),
          outlineLevel: 3,
        },
      },
      {
        id: 'Heading5',
        name: 'Heading 5',
        basedOn: 'Normal',
        next: 'Normal',
        quickFormat: true,
        run: {
          font: headingFont.ascii || bodyFont.ascii || 'Calibri',
          size: _getHeadingSize(recipe, 5, 24),
          bold: _getHeadingBold(recipe, 5, true),
          ...(_getHeadingItalics(recipe, 5, false) ? { italics: true } : {}),
          color: _getHeadingColor(recipe, 5),
        },
        paragraph: {
          spacing: _getHeadingSpacing(recipe, 5, { before: 160, after: 80 }),
          outlineLevel: 4,
        },
      },
      {
        id: 'Heading6',
        name: 'Heading 6',
        basedOn: 'Normal',
        next: 'Normal',
        quickFormat: true,
        run: {
          font: headingFont.ascii || bodyFont.ascii || 'Calibri',
          size: _getHeadingSize(recipe, 6, 24),
          ...(_getHeadingBold(recipe, 6, false) ? { bold: true } : {}),
          ...(_getHeadingItalics(recipe, 6, true) ? { italics: true } : {}),
          color: _getHeadingColor(recipe, 6),
        },
        paragraph: {
          spacing: _getHeadingSpacing(recipe, 6, { before: 160, after: 80 }),
          outlineLevel: 5,
        },
      },
      {
        id: 'Title',
        name: 'Title',
        basedOn: 'Normal',
        next: 'Normal',
        quickFormat: true,
        run: {
          font: headingFont.ascii || bodyFont.ascii || 'Calibri',
          size: _getHeadingSize(recipe, 0, 56),
          bold: true,
          color: _getHeadingColor(recipe, 0),
        },
        paragraph: {
          spacing: { after: 120 },
          alignment: 'center',
        },
      },
      {
        id: 'Subtitle',
        name: 'Subtitle',
        basedOn: 'Normal',
        next: 'Normal',
        quickFormat: true,
        run: {
          font: bodyFont.ascii || 'Calibri',
          size: bodySize + 4,
          color: '666666',
        },
        paragraph: {
          spacing: { after: 240 },
          alignment: 'center',
        },
      },
    ],
  };

  // CJK font fallback for body
  if (bodyFont.eastAsia) {
    styles.default.document.run.font = {
      ascii: bodyFont.ascii || 'Calibri',
      eastAsia: bodyFont.eastAsia,
      hAnsi: bodyFont.ascii || 'Calibri',
    };
  }

  // CJK font fallback for heading styles
  if (headingFont.eastAsia) {
    styles.paragraphStyles.forEach(ps => {
      if (ps.id.startsWith('Heading') || ps.id === 'Title') {
        const baseFont = ps.run.font;
        ps.run.font = {
          ascii: headingFont.ascii || bodyFont.ascii || baseFont,
          eastAsia: headingFont.eastAsia,
          hAnsi: headingFont.ascii || bodyFont.ascii || baseFont,
        };
      }
    });
  }

  // ── extendedStyles ─────────────────────────────
  const ext = recipe.extendedStyles || {};

  // TOC styles (TOC1, TOC2, TOC3, ...)
  if (ext.toc?.levels && Array.isArray(ext.toc.levels)) {
    ext.toc.levels.forEach(tocLevel => {
      const lvl = tocLevel.level || 1;
      styles.paragraphStyles.push({
        id: `TOC${lvl}`,
        name: `toc ${lvl}`,
        basedOn: 'Normal',
        next: 'Normal',
        quickFormat: true,
        run: {
          font: bodyFont.ascii || 'Calibri',
          size: bodySize,
          ...(tocLevel.bold ? { bold: true } : {}),
        },
        paragraph: {
          spacing: { before: 120, after: 120 },
          indent: { left: tocLevel.indent || 0 },
        },
      });
    });
  }

  // Quote / IntenseQuote
  if (ext.quote?.normal) {
    const qn = ext.quote.normal;
    styles.paragraphStyles.push({
      id: 'Quote',
      name: 'Quote',
      basedOn: 'Normal',
      next: 'Normal',
      quickFormat: true,
      run: {
        font: bodyFont.ascii || 'Calibri',
        size: bodySize,
        ...(qn.italics ? { italics: true } : {}),
        color: qn.color || undefined,
      },
      paragraph: {
        spacing: qn.spacing || { before: 240, after: 240 },
        indent: qn.indent || { left: 720, right: 720, firstLine: 0 },
      },
    });
  }

  if (ext.quote?.intense) {
    const iq = ext.quote.intense;
    const intenseStyle = {
      id: 'IntenseQuote',
      name: 'Intense Quote',
      basedOn: 'Quote',
      next: 'Normal',
      quickFormat: true,
      run: {
        font: bodyFont.ascii || 'Calibri',
        size: bodySize,
        ...(iq.bold ? { bold: true } : {}),
        ...(iq.italics ? { italics: true } : {}),
        color: iq.color || undefined,
      },
      paragraph: {
        spacing: iq.spacing || { before: 240, after: 240 },
        indent: iq.indent || { left: 720, right: 720, firstLine: 0 },
      },
    };
    if (iq.leftBorder) {
      intenseStyle.paragraph.border = {
        left: {
          style: _mapBorderStyle(iq.leftBorder.style) || BorderStyle.SINGLE,
          size: iq.leftBorder.size || 18,
          space: iq.leftBorder.space || 12,
          color: iq.leftBorder.color || '2F5496',
        },
      };
    }
    styles.paragraphStyles.push(intenseStyle);
  }

  // Comment styles
  if (ext.comment) {
    styles.paragraphStyles.push({
      id: 'CommentText',
      name: 'Comment Text',
      basedOn: 'Normal',
      next: 'Normal',
      run: {
        font: bodyFont.ascii || 'Calibri',
        size: ext.comment.textSize || 20,
      },
    });
    styles.paragraphStyles.push({
      id: 'CommentReference',
      name: 'Comment Reference',
      basedOn: 'Normal',
      next: 'Normal',
      run: {
        font: bodyFont.ascii || 'Calibri',
        size: ext.comment.referenceSize || 16,
        superscript: true,
      },
    });
  }

  return styles;
}

function _getHeadingSize(recipe, level, defaultSize) {
  const headings = recipe.headings || [];
  const h = headings.find(h => h.level === level);
  return h ? h.size : defaultSize;
}

function _getHeadingColor(recipe, level) {
  const headings = recipe.headings || [];
  const h = headings.find(h => h.level === level);
  return h?.color || undefined;
}

function _getHeadingBold(recipe, level, defaultBold) {
  const headings = recipe.headings || [];
  const h = headings.find(h => h.level === level);
  return h?.bold !== undefined ? h.bold : defaultBold;
}

function _getHeadingItalics(recipe, level, defaultItalics) {
  const headings = recipe.headings || [];
  const h = headings.find(h => h.level === level);
  return h?.italics !== undefined ? h.italics : defaultItalics;
}

function _getHeadingSpacing(recipe, level, defaults) {
  const headings = recipe.headings || [];
  const h = headings.find(h => h.level === level);
  if (h?.spacing) {
    return { before: h.spacing.before, after: h.spacing.after };
  }
  return defaults;
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

module.exports = { buildStyles };
