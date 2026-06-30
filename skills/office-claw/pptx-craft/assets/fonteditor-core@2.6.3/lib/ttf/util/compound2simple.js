"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = compound2simple;

function compound2simple(glyf, contours) {
  glyf.contours = contours;
  delete glyf.compound;
  delete glyf.glyfs;
  delete glyf.instructions;
  return glyf;
}
