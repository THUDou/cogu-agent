#!/usr/bin/env node

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
