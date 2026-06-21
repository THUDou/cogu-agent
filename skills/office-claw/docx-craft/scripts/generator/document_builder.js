const fs = require('fs');
const { Document, Packer } = require('docx');
const templateLoader = require('./template_loader');
const styleFactory = require('./style_factory');
const sectionBuilder = require('./section_builder');
const contentMapper = require('./content_mapper');
const { safeJsonParse } = require('../utils/json_utils');

/**
 * Build a complete DOCX document from recipe + content data.
 *
 * @param {Object} options
 * @param {string} options.recipe - Recipe name (academic|report|government|memo|letter|default)
 * @param {Object|string} options.content - Content data object or path to content.json
 * @param {string} options.output - Output file path
 * @param {string} [options.title] - Document title override
 * @param {string} [options.author] - Document author
 * @param {string} [options.pageSize] - Page size override (letter|a4|legal|a3)
 * @param {string} [options.margins] - Margin preset override (standard|narrow|wide)
 * @param {boolean} [options.noToc] - Skip table of contents
 * @param {boolean} [options.noCover] - Skip cover page
 * @returns {Promise<string>} Output file path
 */
async function build(options) {
  // Load recipe
  const recipe = templateLoader.load(options.recipe);

  // Load content
  let contentData = options.content;
  if (typeof contentData === 'string') {
    contentData = safeJsonParse(fs.readFileSync(contentData, 'utf-8'));
  }

  // Apply overrides
  contentData.title = options.title || contentData.title || '';
  contentData.author = options.author || contentData.author || '';
  if (options.noToc) contentData.noToc = true;
  if (options.noCover) contentData.noCover = true;

  // Resolve page config
  const pageConfig = templateLoader.resolvePage(recipe, {
    pageSize: options.pageSize,
    margins: options.margins,
  });

  // Build styles
  const styles = styleFactory.buildStyles(recipe);

  // Build numbering config (reads recipe.extendedStyles.list)
  const numbering = contentMapper.buildNumbering(recipe);

  // Map all content items from body sections
  const contentSections = contentData.sections || [];
  const mappedSections = contentSections.map(sec => {
    if (sec.type === 'body' && sec.content) {
      return { ...sec, content: contentMapper.mapContent(sec.content, numbering, recipe) };
    }
    return sec;
  });
  contentData.sections = mappedSections;

  // Build sections
  const sections = sectionBuilder.buildSections(recipe, contentData, pageConfig);

  // Create document
  const doc = new Document({
    styles,
    numbering,
    sections,
    creator: contentData.author || 'docx-craft',
    title: contentData.title,
  });

  // Generate file
  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(options.output, buffer);

  return options.output;
}

module.exports = { build };
