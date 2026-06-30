"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = eot2ttf;
var _reader = _interopRequireDefault(require("./reader"));
var _writer = _interopRequireDefault(require("./writer"));
var _error = _interopRequireDefault(require("./error"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function eot2ttf(eotBuffer) {
  var options = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {};
  var eotReader = new _reader.default(eotBuffer, 0, eotBuffer.byteLength, true);

  var magicNumber = eotReader.readUint16(34);
  if (magicNumber !== 0x504C) {
    _error.default.raise(10110);
  }

  var version = eotReader.readUint32(8);
  if (version !== 0x20001 && version !== 0x10000 && version !== 0x20002) {
    _error.default.raise(10110);
  }
  var eotSize = eotBuffer.byteLength || eotBuffer.length;
  var fontSize = eotReader.readUint32(4);
  var fontOffset = 82;
  var familyNameSize = eotReader.readUint16(fontOffset);
  fontOffset += 4 + familyNameSize;
  var styleNameSize = eotReader.readUint16(fontOffset);
  fontOffset += 4 + styleNameSize;
  var versionNameSize = eotReader.readUint16(fontOffset);
  fontOffset += 4 + versionNameSize;
  var fullNameSize = eotReader.readUint16(fontOffset);
  fontOffset += 2 + fullNameSize;

  if (version === 0x20001 || version === 0x20002) {
    var rootStringSize = eotReader.readUint16(fontOffset + 2);
    fontOffset += 4 + rootStringSize;
  }

  if (version === 0x20002) {
    fontOffset += 10;
    var signatureSize = eotReader.readUint16(fontOffset);
    fontOffset += 2 + signatureSize;
    fontOffset += 4;
    var eudcFontSize = eotReader.readUint32(fontOffset);
    fontOffset += 4 + eudcFontSize;
  }
  if (fontOffset + fontSize > eotSize) {
    _error.default.raise(10001);
  }

  if (eotBuffer.slice) {
    return eotBuffer.slice(fontOffset, fontOffset + fontSize);
  }

  var bytes = eotReader.readBytes(fontOffset, fontSize);
  return new _writer.default(new ArrayBuffer(fontSize)).writeBytes(bytes).getBuffer();
}
