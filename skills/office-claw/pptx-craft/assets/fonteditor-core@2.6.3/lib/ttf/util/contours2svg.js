"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = contours2svg;
var _contour2svg = _interopRequireDefault(require("./contour2svg"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function contours2svg(contours, precision) {
  if (!contours.length) {
    return '';
  }
  return contours.map(function (contour) {
    return (0, _contour2svg.default)(contour, precision);
  }).join('');
}
