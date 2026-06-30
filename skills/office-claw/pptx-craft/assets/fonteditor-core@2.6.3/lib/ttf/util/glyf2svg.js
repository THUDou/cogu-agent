"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = glyf2svg;
var _contours2svg = _interopRequireDefault(require("./contours2svg"));
var _transformGlyfContours = _interopRequireDefault(require("./transformGlyfContours"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function glyf2svg(glyf, ttf) {
  if (!glyf) {
    return '';
  }
  var pathArray = [];
  if (!glyf.compound) {
    if (glyf.contours && glyf.contours.length) {
      pathArray.push((0, _contours2svg.default)(glyf.contours));
    }
  } else {
    var contours = (0, _transformGlyfContours.default)(glyf, ttf);
    if (contours && contours.length) {
      pathArray.push((0, _contours2svg.default)(contours));
    }
  }
  return pathArray.join(' ');
}
