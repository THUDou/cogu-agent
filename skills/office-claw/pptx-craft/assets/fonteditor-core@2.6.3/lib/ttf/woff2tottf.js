"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = woff2tottf;
exports.woff2tottfasync = woff2tottfasync;
var _index = _interopRequireDefault(require("../../woff2/index"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function woff2tottf(woff2Buffer) {
  var options = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {};
  if (!_index.default.isInited()) {
    throw new Error('use woff2.init() to init woff2 module!');
  }
  var result = _index.default.decode(woff2Buffer);
  return result.buffer;
}

function woff2tottfasync(woff2Buffer) {
  var options = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {};
  return _index.default.init(options.wasmUrl).then(function () {
    var result = _index.default.decode(woff2Buffer);
    return result.buffer;
  });
}
