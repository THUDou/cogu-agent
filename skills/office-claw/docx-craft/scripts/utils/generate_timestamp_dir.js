#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { error } = require('./logger.js');

const baseDir = process.argv[2] || 'output';

if (!baseDir || typeof baseDir !== 'string' || baseDir.trim() === '') {
  error('错误：输出目录路径不能为空');
  process.exit(1);
}

const now = new Date();
const timestampPrefix = [
  now.getFullYear(),
  String(now.getMonth() + 1).padStart(2, '0'),
  String(now.getDate()).padStart(2, '0'),
  '_',
  String(now.getHours()).padStart(2, '0'),
  String(now.getMinutes()).padStart(2, '0'),
  String(now.getSeconds()).padStart(2, '0')
].join('');

try {
  if (!fs.existsSync(baseDir)) {
    fs.mkdirSync(baseDir, { recursive: true });
  }
} catch (err) {
  error(`错误：无法创建基础目录 - ${baseDir}`);
  error(`  ${err.message}`);
  process.exit(1);
}

const MAX_SEQ = 1000;
let seq = 0;
while (fs.existsSync(path.join(baseDir, `${timestampPrefix}_${String(seq).padStart(3, '0')}`))) {
  if (seq >= MAX_SEQ) {
    error(`错误：同前缀目录数已达上限 (${MAX_SEQ})`);
    process.exit(1);
  }
  seq++;
}

const timestampDir = path.join(baseDir, `${timestampPrefix}_${String(seq).padStart(3, '0')}`);

try {
  fs.mkdirSync(timestampDir, { recursive: true });
} catch (err) {
  error(`错误：无法创建输出目录 - ${timestampDir}`);
  error(`  ${err.message}`);
  process.exit(1);
}

const pagesDir = path.join(timestampDir, 'pages');
fs.mkdirSync(pagesDir, { recursive: true });

console.log(timestampDir);
