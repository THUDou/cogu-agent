"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = reduceGlyf;
var _reducePath = _interopRequireDefault(require("../../graphics/reducePath"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function reduceGlyf(glyf) {
  var contours = glyf.contours;
  var contour;
  for (var j = contours.length - 1; j >= 0; j--) {
    contour = (0, _reducePath.default)(contours[j]);

    if (contour.length <= 2) {
      contours.splice(j, 1);
      continue;
    }
  }
  if (0 === glyf.contours.length) {
    delete glyf.contours;
  }
  return glyf;
}
