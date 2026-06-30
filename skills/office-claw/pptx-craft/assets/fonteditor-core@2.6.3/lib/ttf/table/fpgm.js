"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _table = _interopRequireDefault(require("./table"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }
var _default = exports.default = _table.default.create('fpgm', [], {
  read: function read(reader, ttf) {
    var length = ttf.tables.fpgm.length;
    return reader.readBytes(this.offset, length);
  },
  write: function write(writer, ttf) {
    if (ttf.fpgm) {
      writer.writeBytes(ttf.fpgm, ttf.fpgm.length);
    }
  },
  size: function size(ttf) {
    return ttf.fpgm ? ttf.fpgm.length : 0;
  }
});
