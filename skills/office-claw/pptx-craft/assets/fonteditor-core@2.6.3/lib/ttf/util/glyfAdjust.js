"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = glyfAdjust;
var _pathAdjust = _interopRequireDefault(require("../../graphics/pathAdjust"));
var _pathCeil = _interopRequireDefault(require("../../graphics/pathCeil"));
var _computeBoundingBox = require("../../graphics/computeBoundingBox");
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function glyfAdjust(g) {
  var scaleX = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : 1;
  var scaleY = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : 1;
  var offsetX = arguments.length > 3 && arguments[3] !== undefined ? arguments[3] : 0;
  var offsetY = arguments.length > 4 && arguments[4] !== undefined ? arguments[4] : 0;
  var useCeil = arguments.length > 5 && arguments[5] !== undefined ? arguments[5] : true;
  if (g.contours && g.contours.length) {
    if (scaleX !== 1 || scaleY !== 1) {
      g.contours.forEach(function (contour) {
        (0, _pathAdjust.default)(contour, scaleX, scaleY);
      });
    }
    if (offsetX !== 0 || offsetY !== 0) {
      g.contours.forEach(function (contour) {
        (0, _pathAdjust.default)(contour, 1, 1, offsetX, offsetY);
      });
    }
    if (false !== useCeil) {
      g.contours.forEach(function (contour) {
        (0, _pathCeil.default)(contour);
      });
    }
  }

  var advanceWidth = g.advanceWidth;
  if (undefined === g.xMin || undefined === g.yMax || undefined === g.leftSideBearing || undefined === g.advanceWidth) {
    var bound;
    if (g.contours && g.contours.length) {
      bound = _computeBoundingBox.computePathBox.apply(this, g.contours);
    } else {
      bound = {
        x: 0,
        y: 0,
        width: 0,
        height: 0
      };
    }
    g.xMin = bound.x;
    g.xMax = bound.x + bound.width;
    g.yMin = bound.y;
    g.yMax = bound.y + bound.height;
    g.leftSideBearing = g.xMin;

    if (undefined !== advanceWidth) {
      g.advanceWidth = Math.round(advanceWidth * scaleX + offsetX);
    } else {
      g.advanceWidth = g.xMax + Math.abs(g.xMin);
    }
  } else {
    g.xMin = Math.round(g.xMin * scaleX + offsetX);
    g.xMax = Math.round(g.xMax * scaleX + offsetX);
    g.yMin = Math.round(g.yMin * scaleY + offsetY);
    g.yMax = Math.round(g.yMax * scaleY + offsetY);
    g.leftSideBearing = Math.round(g.leftSideBearing * scaleX + offsetX);
    g.advanceWidth = Math.round(advanceWidth * scaleX + offsetX);
  }
  return g;
}
