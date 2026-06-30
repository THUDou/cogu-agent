"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = parseTransform;
var _parseParams = _interopRequireDefault(require("./parseParams"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

var TRANSFORM_REGEX = /(\w+)\s*\(([\d-.,\s]*)\)/g;

function parseTransform(str) {
  if (!str) {
    return false;
  }
  TRANSFORM_REGEX.lastIndex = 0;
  var transforms = [];
  var match;
  while (match = TRANSFORM_REGEX.exec(str)) {
    transforms.push({
      name: match[1],
      params: (0, _parseParams.default)(match[2])
    });
  }
  return transforms;
}
