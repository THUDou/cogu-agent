"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _table = _interopRequireDefault(require("./table"));
var _parse = _interopRequireDefault(require("./cmap/parse"));
var _write = _interopRequireDefault(require("./cmap/write"));
var _sizeof = _interopRequireDefault(require("./cmap/sizeof"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }
var _default = exports.default = _table.default.create('cmap', [], {
  write: _write.default,
  read: _parse.default,
  size: _sizeof.default
});
