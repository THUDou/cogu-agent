"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = ttf2symbol;
exports.getSymbolId = getSymbolId;
var _string = _interopRequireDefault(require("../common/string"));
var _ttfreader = _interopRequireDefault(require("./ttfreader"));
var _contours2svg = _interopRequireDefault(require("./util/contours2svg"));
var _pathsUtil = _interopRequireDefault(require("../graphics/pathsUtil"));
var _error = _interopRequireDefault(require("./error"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

var XML_TPL = '' + '<svg style="position: absolute; width: 0; height: 0;" width="0" height="0" version="1.1"' + ' xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">' + '<defs>${symbolList}</defs>' + '</svg>';

var SYMBOL_TPL = '' + '<symbol id="${id}" viewBox="0 ${descent} ${unitsPerEm} ${unitsPerEm}">' + '<path d="${d}"></path>' + '</symbol>';

function getSymbolId(glyf, index) {
  if (glyf.name) {
    return glyf.name;
  }
  if (glyf.unicode && glyf.unicode.length) {
    return 'uni-' + glyf.unicode[0];
  }
  return 'symbol-' + index;
}

function ttfobject2symbol(ttf) {
  var options = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {};
  var xmlObject = {};
  var unitsPerEm = ttf.head.unitsPerEm;
  var descent = ttf.hhea.descent;
  var symbolList = '';
  for (var i = 1, l = ttf.glyf.length; i < l; i++) {
    var glyf = ttf.glyf[i];
    if (!glyf.compound && glyf.contours) {
      var contours = _pathsUtil.default.flip(glyf.contours);
      var glyfObject = {
        descent: descent,
        unitsPerEm: unitsPerEm,
        id: getSymbolId(glyf, i),
        d: (0, _contours2svg.default)(contours)
      };
      symbolList += _string.default.format(SYMBOL_TPL, glyfObject);
    }
  }
  xmlObject.symbolList = symbolList;
  return _string.default.format(XML_TPL, xmlObject);
}

function ttf2symbol(ttfBuffer) {
  var options = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {};
  if (ttfBuffer instanceof ArrayBuffer) {
    var reader = new _ttfreader.default();
    var ttfObject = reader.read(ttfBuffer);
    reader.dispose();
    return ttfobject2symbol(ttfObject, options);
  }
  else if (ttfBuffer.version && ttfBuffer.glyf) {
    return ttfobject2symbol(ttfBuffer, options);
  }
  _error.default.raise(10112);
}
