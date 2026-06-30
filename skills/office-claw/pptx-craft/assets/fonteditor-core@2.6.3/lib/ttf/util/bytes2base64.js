"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = bytes2base64;

function bytes2base64(buffer) {
  var str = '';
  var length;
  var i;
  if (buffer instanceof ArrayBuffer) {
    length = buffer.byteLength;
    var view = new DataView(buffer, 0, length);
    for (i = 0; i < length; i++) {
      str += String.fromCharCode(view.getUint8(i, false));
    }
  }
  else if (buffer.length) {
    length = buffer.length;
    for (i = 0; i < length; i++) {
      str += String.fromCharCode(buffer[i]);
    }
  }
  if (!str) {
    return '';
  }
  return typeof btoa !== 'undefined' ? btoa(str) : Buffer.from(str, 'binary').toString('base64');
}
