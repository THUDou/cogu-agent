"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = polygon2contour;
var _parseParams = _interopRequireDefault(require("./parseParams"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function polygon2contour(points) {
  if (!points || !points.length) {
    return null;
  }
  var contours = [];
  var segments = (0, _parseParams.default)(points);
  for (var i = 0, l = segments.length; i < l; i += 2) {
    contours.push({
      x: segments[i],
      y: segments[i + 1],
      onCurve: true
    });
  }
  return contours;
}
