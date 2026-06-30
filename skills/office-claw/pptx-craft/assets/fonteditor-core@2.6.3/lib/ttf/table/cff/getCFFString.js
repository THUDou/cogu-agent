"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = getCFFString;
var _cffStandardStrings = _interopRequireDefault(require("./cffStandardStrings"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function getCFFString(strings, index) {
  if (index <= 390) {
    index = _cffStandardStrings.default[index];
  }
  else {
    index = strings[index - 391];
  }
  return index;
}
