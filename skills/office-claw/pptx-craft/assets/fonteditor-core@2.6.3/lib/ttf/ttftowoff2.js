"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = ttftowoff2;
exports.ttftowoff2async = ttftowoff2async;
var _index = _interopRequireDefault(require("../../woff2/index"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function ttftowoff2(ttfBuffer) {
  var options = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {};
  if (!_index.default.isInited()) {
    throw new Error('use woff2.init() to init woff2 module!');
  }
  var result = _index.default.encode(ttfBuffer);
  return result.buffer;
}

function ttftowoff2async(ttfBuffer) {
  var options = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {};
  return _index.default.init(options.wasmUrl).then(function () {
    var result = _index.default.encode(ttfBuffer);
    return result.buffer;
  });
}
