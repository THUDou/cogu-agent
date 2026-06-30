"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _table = _interopRequireDefault(require("./table"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }
var _default = exports.default = _table.default.create('kern', [], {
  read: function read(reader, ttf) {
    var length = ttf.tables.kern.length;
    return reader.readBytes(this.offset, length);
  },
  write: function write(writer, ttf) {
    if (ttf.kern) {
      writer.writeBytes(ttf.kern, ttf.kern.length);
    }
  },
  size: function size(ttf) {
    return ttf.kern ? ttf.kern.length : 0;
  }
});
