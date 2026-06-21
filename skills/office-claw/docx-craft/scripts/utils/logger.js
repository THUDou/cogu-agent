#!/usr/bin/env node
// 简易日志工具

function error(...args) {
  console.error('[ERROR]', ...args);
}

function info(...args) {
  console.log('[INFO]', ...args);
}

function warn(...args) {
  console.warn('[WARN]', ...args);
}

module.exports = { error, info, warn };
