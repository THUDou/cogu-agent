"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = woff2tobase64;
var _bytes2base = _interopRequireDefault(require("./util/bytes2base64"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function woff2tobase64(arrayBuffer) {
  return 'data:font/woff2;charset=utf-8;base64,' + (0, _bytes2base.default)(arrayBuffer);
}
