"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = optimizettf;
var _reduceGlyf = _interopRequireDefault(require("./reduceGlyf"));
var _pathCeil = _interopRequireDefault(require("../../graphics/pathCeil"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function optimizettf(ttf) {
  var checkUnicodeRepeat = {}; // 检查是否有重复代码点
  var repeatList = [];
  ttf.glyf.forEach(function (glyf, index) {
    if (glyf.unicode) {
      glyf.unicode = glyf.unicode.sort();

      glyf.unicode.sort(function (a, b) {
        return a - b;
      }).forEach(function (u) {
        if (checkUnicodeRepeat[u]) {
          repeatList.push(index);
        } else {
          checkUnicodeRepeat[u] = true;
        }
      });
    }
    if (!glyf.compound && glyf.contours) {
      glyf.contours.forEach(function (contour) {
        (0, _pathCeil.default)(contour);
      });
      (0, _reduceGlyf.default)(glyf);
    }

    glyf.xMin = Math.round(glyf.xMin || 0);
    glyf.xMax = Math.round(glyf.xMax || 0);
    glyf.yMin = Math.round(glyf.yMin || 0);
    glyf.yMax = Math.round(glyf.yMax || 0);
    glyf.leftSideBearing = Math.round(glyf.leftSideBearing || 0);
    glyf.advanceWidth = Math.round(glyf.advanceWidth || 0);
  });

  if (!ttf.glyf.some(function (a) {
    return a.compound;
  })) {
    ttf.glyf = ttf.glyf.filter(function (glyf, index) {
      return index === 0 || glyf.contours && glyf.contours.length;
    });
  }
  if (!repeatList.length) {
    return true;
  }
  return {
    repeat: repeatList
  };
}
