"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = unicode2xml;
var _string = _interopRequireDefault(require("../../common/string"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function unicode2xml(unicodeList) {
  if (typeof unicodeList === 'number') {
    unicodeList = [unicodeList];
  }
  return unicodeList.map(function (u) {
    if (u < 0x20) {
      return '';
    }
    return u >= 0x20 && u <= 255 ? _string.default.encodeHTML(String.fromCharCode(u)) : '&#x' + u.toString(16) + ';';
  }).join('');
}
