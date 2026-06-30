"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _default = exports.default = {
  toArrayBuffer: function toArrayBuffer(buffer) {
    var length = buffer.length;
    var view = new DataView(new ArrayBuffer(length), 0, length);
    for (var i = 0, l = length; i < l; i++) {
      view.setUint8(i, buffer[i], false);
    }
    return view.buffer;
  },
  toBuffer: function toBuffer(arrayBuffer) {
    if (Array.isArray(arrayBuffer)) {
      return Buffer.from(arrayBuffer);
    }
    var length = arrayBuffer.byteLength;
    var view = new DataView(arrayBuffer, 0, length);
    var buffer = Buffer.alloc(length);
    for (var i = 0, l = length; i < l; i++) {
      buffer[i] = view.getUint8(i, false);
    }
    return buffer;
  }
};
