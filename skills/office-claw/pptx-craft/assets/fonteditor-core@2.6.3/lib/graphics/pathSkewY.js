"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = pathSkewY;
var _computeBoundingBox = require("./computeBoundingBox");

function pathSkewY(contour, angle) {
  angle = angle === undefined ? 0 : angle;
  var x = (0, _computeBoundingBox.computePath)(contour).x;
  var tan = Math.tan(angle);
  var p;
  for (var i = 0, l = contour.length; i < l; i++) {
    p = contour[i];
    p.y += tan * (p.x - x);
  }
  return contour;
}
