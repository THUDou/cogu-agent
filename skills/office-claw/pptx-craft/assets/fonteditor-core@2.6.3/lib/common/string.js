"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _default = exports.default = {
  decodeHTML: function decodeHTML(source) {
    var str = String(source).replace(/&quot;/g, '"').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');

    return str.replace(/&#([\d]+);/g, function ($0, $1) {
      return String.fromCodePoint(parseInt($1, 10));
    });
  },
  encodeHTML: function encodeHTML(source) {
    return String(source).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  },
  getLength: function getLength(source) {
    return String(source).replace(/[^\x00-\xff]/g, '11').length;
  },
  format: function format(source, data) {
    return source.replace(/\$\{([\w.]+)\}/g, function ($0, $1) {
      var ref = $1.split('.');
      var refObject = data;
      var level;
      while (refObject != null && (level = ref.shift())) {
        refObject = refObject[level];
      }
      return refObject != null ? refObject : '';
    });
  },
  pad: function pad(str, size, ch) {
    str = String(str);
    if (str.length > size) {
      return str.slice(str.length - size);
    }
    return new Array(size - str.length + 1).join(ch || '0') + str;
  },
  hashcode: function hashcode(str) {
    if (!str) {
      return 0;
    }
    var hash = 0;
    for (var i = 0, l = str.length; i < l; i++) {
      hash = 0x7FFFFFFFF & hash * 31 + str.charCodeAt(i);
    }
    return hash;
  }
};
