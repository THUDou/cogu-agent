"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = base642bytes;

function base642bytes(base64) {
  var str = atob(base64);
  var result = [];
  for (var i = 0, l = str.length; i < l; i++) {
    result.push(str[i].charCodeAt(0));
  }
  return result;
}
