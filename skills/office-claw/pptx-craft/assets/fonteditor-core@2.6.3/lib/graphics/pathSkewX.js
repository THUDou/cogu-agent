"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = pathSkewX;
var _computeBoundingBox = require("./computeBoundingBox");

function pathSkewX(contour, angle) {
  angle = angle === undefined ? 0 : angle;
  var y = (0, _computeBoundingBox.computePath)(contour).y;
  var tan = Math.tan(angle);
  var p;
  for (var i = 0, l = contour.length; i < l; i++) {
    p = contour[i];
    p.x += tan * (p.y - y);
  }
  return contour;
}
