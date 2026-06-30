"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _lang = require("../common/lang");
var _error = _interopRequireDefault(require("./error"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }
function _typeof(o) { "@babel/helpers - typeof"; return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function (o) { return typeof o; } : function (o) { return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o; }, _typeof(o); }
function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }
function _defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, _toPropertyKey(descriptor.key), descriptor); } }
function _createClass(Constructor, protoProps, staticProps) { if (protoProps) _defineProperties(Constructor.prototype, protoProps); if (staticProps) _defineProperties(Constructor, staticProps); Object.defineProperty(Constructor, "prototype", { writable: false }); return Constructor; }
function _toPropertyKey(t) { var i = _toPrimitive(t, "string"); return "symbol" == _typeof(i) ? i : i + ""; }
function _toPrimitive(t, r) { if ("object" != _typeof(t) || !t) return t; var e = t[Symbol.toPrimitive]; if (void 0 !== e) { var i = e.call(t, r || "default"); if ("object" != _typeof(i)) return i; throw new TypeError("@@toPrimitive must return a primitive value."); } return ("string" === r ? String : Number)(t); } /**
 * @file 数据写入器
 * @author mengke01(kekee000@gmail.com)
 */
if (typeof ArrayBuffer === 'undefined' || typeof DataView === 'undefined') {
  throw new Error('not support ArrayBuffer and DataView');
}

var dataType = {
  Int8: 1,
  Int16: 2,
  Int32: 4,
  Uint8: 1,
  Uint16: 2,
  Uint32: 4,
  Float32: 4,
  Float64: 8
};

var Writer = /*#__PURE__*/function () {
  function Writer(buffer, offset, length, littleEndian) {
    _classCallCheck(this, Writer);
    var bufferLength = buffer.byteLength || buffer.length;
    this.offset = offset || 0;
    this.length = length || bufferLength - this.offset;
    this.littleEndian = littleEndian || false;
    this.view = new DataView(buffer, this.offset, this.length);
  }

  return _createClass(Writer, [{
    key: "write",
    value: function write(type, value, offset, littleEndian) {
      if (undefined === offset) {
        offset = this.offset;
      }

      if (undefined === littleEndian) {
        littleEndian = this.littleEndian;
      }

      if (undefined === dataType[type]) {
        return this['write' + type](value, offset, littleEndian);
      }
      var size = dataType[type];
      this.offset = offset + size;
      this.view['set' + type](offset, value, littleEndian);
      return this;
    }

  }, {
    key: "writeBytes",
    value: function writeBytes(value, length, offset) {
      length = length || value.byteLength || value.length;
      var i;
      if (!length) {
        return this;
      }
      if (undefined === offset) {
        offset = this.offset;
      }
      if (length < 0 || offset + length > this.length) {
        _error.default.raise(10002, this.length, offset + length);
      }
      var littleEndian = this.littleEndian;
      if (value instanceof ArrayBuffer) {
        var view = new DataView(value, 0, length);
        for (i = 0; i < length; ++i) {
          this.view.setUint8(offset + i, view.getUint8(i, littleEndian), littleEndian);
        }
      } else {
        for (i = 0; i < length; ++i) {
          this.view.setUint8(offset + i, value[i], littleEndian);
        }
      }
      this.offset = offset + length;
      return this;
    }

  }, {
    key: "writeEmpty",
    value: function writeEmpty(length, offset) {
      if (length < 0) {
        _error.default.raise(10002, this.length, length);
      }
      if (undefined === offset) {
        offset = this.offset;
      }
      var littleEndian = this.littleEndian;
      for (var i = 0; i < length; ++i) {
        this.view.setUint8(offset + i, 0, littleEndian);
      }
      this.offset = offset + length;
      return this;
    }

  }, {
    key: "writeString",
    value: function writeString() {
      var str = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : '';
      var length = arguments.length > 1 ? arguments[1] : undefined;
      var offset = arguments.length > 2 ? arguments[2] : undefined;
      if (undefined === offset) {
        offset = this.offset;
      }

      length = length || str.replace(/[^\x00-\xff]/g, '11').length;
      if (length < 0 || offset + length > this.length) {
        _error.default.raise(10002, this.length, offset + length);
      }
      this.seek(offset);
      for (var i = 0, l = str.length, charCode; i < l; ++i) {
        charCode = str.charCodeAt(i) || 0;
        if (charCode > 127) {
          this.writeUint16(charCode);
        } else {
          this.writeUint8(charCode);
        }
      }
      this.offset = offset + length;
      return this;
    }

  }, {
    key: "writeChar",
    value: function writeChar(value, offset) {
      return this.writeString(value, offset);
    }

  }, {
    key: "writeFixed",
    value: function writeFixed(value, offset) {
      if (undefined === offset) {
        offset = this.offset;
      }
      this.writeInt32(Math.round(value * 65536), offset);
      return this;
    }

  }, {
    key: "writeLongDateTime",
    value: function writeLongDateTime(value, offset) {
      if (undefined === offset) {
        offset = this.offset;
      }

      var delta = -2077545600000;
      if (typeof value === 'undefined') {
        value = delta;
      } else if (typeof value.getTime === 'function') {
        value = value.getTime();
      } else if (/^\d+$/.test(value)) {
        value = +value;
      } else {
        value = Date.parse(value);
      }
      var time = Math.round((value - delta) / 1000);
      this.writeUint32(0, offset);
      this.writeUint32(time, offset + 4);
      return this;
    }

  }, {
    key: "seek",
    value: function seek(offset) {
      if (undefined === offset) {
        this.offset = 0;
      }
      if (offset < 0 || offset > this.length) {
        _error.default.raise(10002, this.length, offset);
      }
      this._offset = this.offset;
      this.offset = offset;
      return this;
    }

  }, {
    key: "head",
    value: function head() {
      this.offset = this._offset || 0;
      return this;
    }

  }, {
    key: "getBuffer",
    value: function getBuffer() {
      return this.view.buffer;
    }

  }, {
    key: "dispose",
    value: function dispose() {
      delete this.view;
    }
  }]);
}(); // 直接支持的数据类型
Object.keys(dataType).forEach(function (type) {
  Writer.prototype['write' + type] = (0, _lang.curry)(Writer.prototype.write, type);
});
var _default = exports.default = Writer;
