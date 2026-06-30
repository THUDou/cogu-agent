"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _table = _interopRequireDefault(require("./table"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }
var _default = exports.default = _table.default.create('kerx', [], {
  read: function read(reader, ttf) {
    var length = ttf.tables.kerx.length;
    return reader.readBytes(this.offset, length);
  },
  write: function write(writer, ttf) {
    if (ttf.kerx) {
      writer.writeBytes(ttf.kerx, ttf.kerx.length);
    }
  },
  size: function size(ttf) {
    return ttf.kerx ? ttf.kerx.length : 0;
  }
});
