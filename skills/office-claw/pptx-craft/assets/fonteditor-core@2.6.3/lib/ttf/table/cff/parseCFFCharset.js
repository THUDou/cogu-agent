"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = parseCFFCharset;
var _getCFFString = _interopRequireDefault(require("./getCFFString"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function parseCFFCharset(reader, start, nGlyphs, strings) {
  if (start) {
    reader.seek(start);
  }
  var i;
  var sid;
  var count;
  nGlyphs -= 1;
  var charset = ['.notdef'];
  var format = reader.readUint8();
  if (format === 0) {
    for (i = 0; i < nGlyphs; i += 1) {
      sid = reader.readUint16();
      charset.push((0, _getCFFString.default)(strings, sid));
    }
  } else if (format === 1) {
    while (charset.length <= nGlyphs) {
      sid = reader.readUint16();
      count = reader.readUint8();
      for (i = 0; i <= count; i += 1) {
        charset.push((0, _getCFFString.default)(strings, sid));
        sid += 1;
      }
    }
  } else if (format === 2) {
    while (charset.length <= nGlyphs) {
      sid = reader.readUint16();
      count = reader.readUint16();
      for (i = 0; i <= count; i += 1) {
        charset.push((0, _getCFFString.default)(strings, sid));
        sid += 1;
      }
    }
  } else {
    throw new Error('Unknown charset format ' + format);
  }
  return charset;
}
