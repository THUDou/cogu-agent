"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = compound2simpleglyf;
var _transformGlyfContours = _interopRequireDefault(require("./transformGlyfContours"));
var _compound2simple = _interopRequireDefault(require("./compound2simple"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function compound2simpleglyf(glyf, ttf, recrusive) {
  var glyfIndex;
  if (typeof glyf === 'number') {
    glyfIndex = glyf;
    glyf = ttf.glyf[glyfIndex];
  } else {
    glyfIndex = ttf.glyf.indexOf(glyf);
    if (-1 === glyfIndex) {
      return glyf;
    }
  }
  if (!glyf.compound || !glyf.glyfs) {
    return glyf;
  }
  var contoursList = {};
  (0, _transformGlyfContours.default)(glyf, ttf, contoursList, glyfIndex);
  if (recrusive) {
    Object.keys(contoursList).forEach(function (index) {
      (0, _compound2simple.default)(ttf.glyf[index], contoursList[index]);
    });
  } else {
    (0, _compound2simple.default)(glyf, contoursList[glyfIndex]);
  }
  return glyf;
}
