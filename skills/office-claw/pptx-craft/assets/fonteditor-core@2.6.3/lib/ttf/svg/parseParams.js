"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = _default;

var SEGMENT_REGEX = /-?\d+(?:\.\d+)?(?:e[-+]?\d+)?\b/g;

function getSegment(d) {
  return +d.trim();
}

function _default(str) {
  if (!str) {
    return [];
  }
  var matchs = str.match(SEGMENT_REGEX);
  return matchs ? matchs.map(getSegment) : [];
}
