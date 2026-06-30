"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = otfContours2ttfContours;
var _bezierCubic2Q = _interopRequireDefault(require("../../math/bezierCubic2Q2"));
var _pathCeil = _interopRequireDefault(require("../../graphics/pathCeil"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function transformContour(otfContour) {
  var contour = [];
  var prevPoint;
  var curPoint;
  var nextPoint;
  var nextNextPoint;
  contour.push(prevPoint = otfContour[0]);
  for (var i = 1, l = otfContour.length; i < l; i++) {
    curPoint = otfContour[i];
    if (curPoint.onCurve) {
      contour.push(curPoint);
      prevPoint = curPoint;
    }
    else {
      nextPoint = otfContour[i + 1];
      nextNextPoint = i === l - 2 ? otfContour[0] : otfContour[i + 2];
      var bezierArray = (0, _bezierCubic2Q.default)(prevPoint, curPoint, nextPoint, nextNextPoint);
      bezierArray[0][2].onCurve = true;
      contour.push(bezierArray[0][1]);
      contour.push(bezierArray[0][2]);

      if (bezierArray[1]) {
        bezierArray[1][2].onCurve = true;
        contour.push(bezierArray[1][1]);
        contour.push(bezierArray[1][2]);
      }
      prevPoint = nextNextPoint;
      i += 2;
    }
  }
  return (0, _pathCeil.default)(contour);
}

function otfContours2ttfContours(otfContours) {
  if (!otfContours || !otfContours.length) {
    return otfContours;
  }
  var contours = [];
  for (var i = 0, l = otfContours.length; i < l; i++) {
    if (otfContours[i][0]) {
      contours.push(transformContour(otfContours[i]));
    }
  }
  return contours;
}
