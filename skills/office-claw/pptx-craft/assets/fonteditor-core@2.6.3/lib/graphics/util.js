"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.ceil = ceil;
exports.ceilPoint = ceilPoint;
exports.getPointHash = getPointHash;
exports.isPointInBound = isPointInBound;
exports.isPointOverlap = isPointOverlap;

function ceilPoint(p) {
  var t = p.x;

  if (Math.abs(Math.round(t) - t) < 0.00002) {
    p.x = Math.round(t);
  } else {
    p.x = Math.round(p.x * 100000) / 100000;
  }
  t = p.y;
  if (Math.abs(Math.round(t) - t) < 0.00005) {
    p.y = Math.round(t);
  } else {
    p.y = Math.round(p.y * 100000) / 100000;
  }
  return p;
}

function ceil(x) {
  if (Math.abs(Math.round(x) - x) < 0.00002) {
    return Math.round(x);
  }
  return Math.round(x * 100000) / 100000;
}

function isPointInBound(bound, p, fixed) {
  if (fixed) {
    return ceil(p.x) <= ceil(bound.x + bound.width) && ceil(p.x) >= ceil(bound.x) && ceil(p.y) <= ceil(bound.y + bound.height) && ceil(p.y) >= ceil(bound.y);
  }
  return p.x <= bound.x + bound.width && p.x >= bound.x && p.y <= bound.y + bound.height && p.y >= bound.y;
}

function isPointOverlap(p0, p1) {
  return ceil(p0.x) === ceil(p1.x) && ceil(p0.y) === ceil(p1.y);
}

function getPointHash(p) {
  return Math.floor(7 * Math.floor(p.x * 10) + 131 * Math.floor(p.y * 100));
}
