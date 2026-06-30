const fs = require('fs');
const { Document, Packer } = require('docx');
const templateLoader = require('./template_loader');
const styleFactory = require('./style_factory');
const sectionBuilder = require('./section_builder');
const contentMapper = require('./content_mapper');
const { safeJsonParse } = require('../utils/json_utils');

async function build(options) {
  const recipe = templateLoader.load(options.recipe);

  let contentData = options.content;
  if (typeof contentData === 'string') {
    contentData = safeJsonParse(fs.readFileSync(contentData, 'utf-8'));
  }

  contentData.title = options.title || contentData.title || '';
  contentData.author = options.author || contentData.author || '';
  if (options.noToc) contentData.noToc = true;
  if (options.noCover) contentData.noCover = true;

  const pageConfig = templateLoader.resolvePage(recipe, {
    pageSize: options.pageSize,
    margins: options.margins,
  });

  const styles = styleFactory.buildStyles(recipe);

  const numbering = contentMapper.buildNumbering(recipe);

  const contentSections = contentData.sections || [];
  const mappedSections = contentSections.map(sec => {
    if (sec.type === 'body' && sec.content) {
      return { ...sec, content: contentMapper.mapContent(sec.content, numbering, recipe) };
    }
    return sec;
  });
  contentData.sections = mappedSections;

  const sections = sectionBuilder.buildSections(recipe, contentData, pageConfig);

  const doc = new Document({
    styles,
    numbering,
    sections,
    creator: contentData.author || 'docx-craft',
    title: contentData.title,
  });

  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(options.output, buffer);

  return options.output;
}

module.exports = { build };
