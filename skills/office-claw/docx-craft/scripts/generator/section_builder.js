const {
  Header, Footer, Paragraph, TextRun, PageNumber,
  TableOfContents, SectionType, PageBreak,
} = require('docx');

function buildSections(recipe, contentData, pageConfig) {
  const sections = [];
  const contentSections = contentData.sections || [];
  const recipeSections = recipe.sections || [];

  const hasCover = recipeSections.includes('cover') && !contentData.noCover;
  const hasToc = recipeSections.includes('toc') && !contentData.noToc;
  const hasExecSummary = recipeSections.includes('executive_summary');

  if (hasCover) {
    const coverContent = _findSectionContent(contentSections, 'cover');
    sections.push(_buildCoverSection(recipe, coverContent, pageConfig));
  }

  if (hasToc || hasExecSummary) {
    const tocChildren = [];
    if (hasExecSummary) {
      const summaryContent = _findSectionContent(contentSections, 'executive_summary');
      tocChildren.push(..._buildExecSummary(summaryContent));
    }
    if (hasToc) {
      const tocLevels = recipe.extendedStyles?.toc?.levels || [];
      const maxTocLevel = tocLevels.length > 0
        ? Math.max(...tocLevels.map(l => l.level || 1))
        : 3;
      const headingStyleRange = `1-${maxTocLevel}`;

      tocChildren.push(
        new Paragraph({
          heading: 'Heading1',
          children: [new TextRun('Table of Contents')],
        }),
        new TableOfContents('Table of Contents', {
          hyperlink: true,
          headingStyleRange,
        }),
        new Paragraph({ children: [new PageBreak()] })
      );
    }
    sections.push({
      properties: {
        page: pageConfig,
        titlePage: hasCover,
      },
      headers: _buildHeader(recipe, true),
      footers: _buildFooter(recipe, true),
      children: tocChildren,
    });
  }

  const bodyContent = _findSectionContent(contentSections, 'body');
  if (bodyContent.length > 0) {
    sections.push({
      properties: {
        page: pageConfig,
      },
      headers: _buildHeader(recipe, false),
      footers: _buildFooter(recipe, false),
      children: bodyContent,
    });
  }

  if (sections.length === 0) {
    sections.push({
      properties: { page: pageConfig },
      children: [
        new Paragraph({ children: [new TextRun(contentData.title || 'Document')] }),
      ],
    });
  }

  return sections;
}

function _findSectionContent(contentSections, type) {
  const section = contentSections.find(s => s.type === type);
  return section ? section.content || [] : [];
}

function _buildCoverSection(recipe, coverContent, pageConfig) {
  const children = [];

  children.push(new Paragraph({ spacing: { before: 4000 } }));

  if (coverContent.length > 0) {
    const contentMapper = require('./content_mapper');
    coverContent.forEach(item => {
      children.push(contentMapper.mapItem(item));
    });
  } else {
    children.push(
      new Paragraph({
        alignment: 'center',
        spacing: { after: 400 },
        children: [new TextRun({ text: recipe.title || '', size: 56, bold: true })],
      })
    );
  }

  return {
    properties: {
      page: pageConfig,
      titlePage: true,
    },
    headers: { default: new Header({ children: [new Paragraph('')] }) },
    footers: { default: new Footer({ children: [new Paragraph('')] }) },
    children,
  };
}

function _buildExecSummary(summaryContent) {
  const children = [];
  children.push(
    new Paragraph({
      heading: 'Heading1',
      children: [new TextRun('Executive Summary')],
    })
  );
  if (summaryContent.length > 0) {
    const contentMapper = require('./content_mapper');
    summaryContent.forEach(item => {
      children.push(contentMapper.mapItem(item));
    });
  }
  return children;
}

function _buildHeader(recipe, isFirstSection) {
  const headerText = recipe.header?.text || '';
  if (!headerText) return undefined;

  const align = recipe.header?.align || 'right';
  return {
    default: new Header({
      children: [
        new Paragraph({
          alignment: align === 'right' ? 'right' : align === 'center' ? 'center' : 'left',
          children: [new TextRun({ text: headerText, size: 18, color: '888888' })],
        }),
      ],
    }),
  };
}

function _buildFooter(recipe, isFirstSection) {
  const footerConfig = recipe.footer || {};
  const footerType = footerConfig.type || 'page_number';
  const align = footerConfig.align || 'center';

  const alignValue = align === 'right' ? 'right' : align === 'center' ? 'center' : 'left';

  if (footerType === 'page_x_of_y') {
    return {
      default: new Footer({
        children: [
          new Paragraph({
            alignment: alignValue,
            children: [
              new TextRun({ text: 'Page ', size: 18 }),
              new TextRun({ children: [PageNumber.CURRENT], size: 18 }),
              new TextRun({ text: ' of ', size: 18 }),
              new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 18 }),
            ],
          }),
        ],
      }),
    };
  }

  return {
    default: new Footer({
      children: [
        new Paragraph({
          alignment: alignValue,
          children: [
            new TextRun({ children: [PageNumber.CURRENT], size: 18 }),
          ],
        }),
      ],
    }),
  };
}

module.exports = { buildSections };
