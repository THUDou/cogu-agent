"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = pathCeil;

function pathCeil(contour, point) {
  var p;
  for (var i = 0, l = contour.length; i < l; i++) {
    p = contour[i];
    if (!point) {
      p.x = Math.round(p.x);
      p.y = Math.round(p.y);
    } else {
      p.x = Number(p.x.toFixed(point));
      p.y = Number(p.y.toFixed(point));
    }
  }
  return contour;
}
