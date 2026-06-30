"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = transformGlyfContours;
var _pathCeil = _interopRequireDefault(require("../../graphics/pathCeil"));
var _pathTransform = _interopRequireDefault(require("../../graphics/pathTransform"));
var _lang = require("../../common/lang");
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function transformGlyfContours(glyf, ttf) {
  var contoursList = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : {};
  var glyfIndex = arguments.length > 3 ? arguments[3] : undefined;
  if (!glyf.glyfs) {
    return glyf;
  }
  var compoundContours = [];
  glyf.glyfs.forEach(function (g) {
    var glyph = ttf.glyf[g.glyphIndex];
    if (!glyph || glyph === glyf) {
      return;
    }

    if (glyph.compound && !contoursList[g.glyphIndex]) {
      transformGlyfContours(glyph, ttf, contoursList, g.glyphIndex);
    }

    var contours = (0, _lang.clone)(glyph.compound ? contoursList[g.glyphIndex] || [] : glyph.contours);
    var transform = g.transform;
    for (var i = 0, l = contours.length; i < l; i++) {
      (0, _pathTransform.default)(contours[i], transform.a, transform.b, transform.c, transform.d, transform.e, transform.f);
      compoundContours.push((0, _pathCeil.default)(contours[i]));
    }
  });

  if (null != glyfIndex) {
    contoursList[glyfIndex] = compoundContours;
  }
  return compoundContours;
}
