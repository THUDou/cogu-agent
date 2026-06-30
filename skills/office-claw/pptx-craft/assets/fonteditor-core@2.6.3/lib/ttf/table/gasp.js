"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _table = _interopRequireDefault(require("./table"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }
var _default = exports.default = _table.default.create('gasp', [], {
  read: function read(reader, ttf) {
    var length = ttf.tables.gasp.length;
    return reader.readBytes(this.offset, length);
  },
  write: function write(writer, ttf) {
    if (ttf.gasp) {
      writer.writeBytes(ttf.gasp, ttf.gasp.length);
    }
  },
  size: function size(ttf) {
    return ttf.gasp ? ttf.gasp.length : 0;
  }
});
