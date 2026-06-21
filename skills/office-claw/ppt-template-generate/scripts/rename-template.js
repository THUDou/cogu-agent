#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

function validateTemplateName(dir) {
  const errors = [];
  const targetDir = path.resolve(dir);
  const dirName = path.basename(targetDir);

  const specPath = path.join(targetDir, 'template-spec.json');
  if (!fs.existsSync(specPath)) {
    errors.push('template-spec.json not found');
    return { ok: false, errors };
  }

  let spec;
  try {
    spec = JSON.parse(fs.readFileSync(specPath, 'utf-8'));
  } catch {
    errors.push('template-spec.json is not valid JSON');
    return { ok: false, errors };
  }

  const styleName = spec.style_name || '';
  if (!styleName) {
    errors.push('template-spec.json missing style_name');
  }

  if (styleName && dirName !== styleName) {
    errors.push(`目录名 "${dirName}" 与 style_name "${styleName}" 不一致`);
  }

  const expectedMd = `${dirName}.md`;
  const mdPath = path.join(targetDir, expectedMd);
  if (!fs.existsSync(mdPath)) {
    errors.push(`规范文件 ${expectedMd} 不存在`);
  } else {
    const firstLine = fs.readFileSync(mdPath, 'utf-8').split('\n')[0] || '';
    const expectedHeading = `# ${dirName} - PPT 样式规范`;
    if (firstLine.trim() !== expectedHeading) {
      errors.push(`一级标题应为 "${expectedHeading}"，实际为 "${firstLine.trim()}"`);
    }
  }

  return { ok: errors.length === 0, errors };
}

function renameTemplate(oldDir, newName) {
  const targetDir = path.resolve(oldDir);
  const oldDirName = path.basename(targetDir);
  const parentDir = path.dirname(targetDir);
  const newDir = path.join(parentDir, newName);

  if (fs.existsSync(newDir) && path.resolve(newDir) !== path.resolve(targetDir)) {
    throw new Error(`目标目录已存在: ${newDir}`);
  }

  const specPath = path.join(targetDir, 'template-spec.json');
  if (!fs.existsSync(specPath)) {
    throw new Error(`template-spec.json not found in ${targetDir}`);
  }
  const spec = JSON.parse(fs.readFileSync(specPath, 'utf-8'));

  const oldMdName = `${oldDirName}.md`;
  const oldMdPath = path.join(targetDir, oldMdName);
  const newMdName = `${newName}.md`;

  if (fs.existsSync(oldMdPath)) {
    let content = fs.readFileSync(oldMdPath, 'utf-8');
    const lines = content.split('\n');
    if (lines[0] && lines[0].startsWith('# ')) {
      lines[0] = `# ${newName} - PPT 样式规范`;
      content = lines.join('\n');
    }
    fs.writeFileSync(oldMdPath, content, 'utf-8');
    if (newMdName !== oldMdName) {
      fs.renameSync(oldMdPath, path.join(targetDir, newMdName));
    }
  }

  spec.style_name = newName;
  fs.writeFileSync(specPath, JSON.stringify(spec, null, 2), 'utf-8');

  if (path.resolve(newDir) !== path.resolve(targetDir)) {
    fs.renameSync(targetDir, newDir);
  }

  return newDir;
}

function main() {
  const [,, command, dirArg, newNameArg] = process.argv;

  if (command === 'check') {
    if (!dirArg) { console.error('Usage: rename-template.js check <dir>'); process.exit(1); }
    const result = validateTemplateName(dirArg);
    if (result.ok) {
      console.log('OK');
    } else {
      console.error('校验失败:');
      result.errors.forEach(e => console.error(` - ${e}`));
      process.exit(1);
    }
  } else if (command === 'rename') {
    if (!dirArg || !newNameArg) {
      console.error('Usage: rename-template.js rename <dir> <newName>');
      process.exit(1);
    }
    try {
      const newDir = renameTemplate(dirArg, newNameArg);
      console.log(newDir);
    } catch (error) {
      console.error(error.message);
      process.exit(1);
    }
  } else {
    console.error('Usage: rename-template.js <check|rename> <dir> [newName]');
    process.exit(1);
  }
}

module.exports = { validateTemplateName, renameTemplate };

if (require.main === module) {
  main();
}
