"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = svg2base64;

function svg2base64(svg) {
  var scheme = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : 'font/svg';
  if (typeof btoa === 'undefined') {
    return 'data:' + scheme + ';charset=utf-8;base64,' + Buffer.from(svg, 'binary').toString('base64');
  }
  return 'data:' + scheme + ';charset=utf-8;base64,' + btoa(svg);
}
