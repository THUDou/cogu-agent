const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const {
  validateTemplateName,
  renameTemplate,
} = require('../scripts/rename-template.js');

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ppt-template-rename-'));
const oldDir = path.join(root, 'old-name');
fs.mkdirSync(oldDir, { recursive: true });
fs.writeFileSync(path.join(oldDir, 'old-name.md'), '# old-name - PPT 样式规范\n\ncontent\n', 'utf-8');
fs.writeFileSync(
  path.join(oldDir, 'template-spec.json'),
  JSON.stringify({ schema_version: 'ppt-template-spec-v1', style_name: 'old-name' }, null, 2),
  'utf-8'
);

const before = validateTemplateName(oldDir);
assert.strictEqual(before.ok, true);

const newDir = renameTemplate(oldDir, '红标现代商务');
assert.strictEqual(path.basename(newDir), '红标现代商务');
assert.ok(fs.existsSync(path.join(newDir, '红标现代商务.md')));
const md = fs.readFileSync(path.join(newDir, '红标现代商务.md'), 'utf-8');
assert.ok(md.startsWith('# 红标现代商务 - PPT 样式规范'));
const spec = JSON.parse(fs.readFileSync(path.join(newDir, 'template-spec.json'), 'utf-8'));
assert.strictEqual(spec.style_name, '红标现代商务');

const after = validateTemplateName(newDir);
assert.strictEqual(after.ok, true);

fs.writeFileSync(path.join(newDir, '红标现代商务.md'), '# 错误标题 - PPT 样式规范\n', 'utf-8');
const invalid = validateTemplateName(newDir);
assert.strictEqual(invalid.ok, false);
assert.ok(invalid.errors.some(e => e.includes('一级标题')));

fs.rmSync(root, { recursive: true, force: true });
console.log('rename_template tests passed');
