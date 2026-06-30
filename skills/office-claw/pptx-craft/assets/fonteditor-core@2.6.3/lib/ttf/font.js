"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.Font = void 0;
exports.createFont = createFont;
exports.default = void 0;
var _buffer = _interopRequireDefault(require("../nodejs/buffer"));
var _getEmptyttfObject = _interopRequireDefault(require("./getEmptyttfObject"));
var _ttf = _interopRequireDefault(require("./ttf"));
var _woff2ttf = _interopRequireDefault(require("./woff2ttf"));
var _otf2ttfobject = _interopRequireDefault(require("./otf2ttfobject"));
var _eot2ttf = _interopRequireDefault(require("./eot2ttf"));
var _svg2ttfobject = _interopRequireDefault(require("./svg2ttfobject"));
var _ttfreader = _interopRequireDefault(require("./ttfreader"));
var _ttfwriter = _interopRequireDefault(require("./ttfwriter"));
var _ttf2eot = _interopRequireDefault(require("./ttf2eot"));
var _ttf2woff = _interopRequireDefault(require("./ttf2woff"));
var _ttf2svg = _interopRequireDefault(require("./ttf2svg"));
var _ttf2symbol = _interopRequireDefault(require("./ttf2symbol"));
var _ttftowoff = _interopRequireDefault(require("./ttftowoff2"));
var _woff2tottf = _interopRequireDefault(require("./woff2tottf"));
var _ttf2base = _interopRequireDefault(require("./ttf2base64"));
var _eot2base = _interopRequireDefault(require("./eot2base64"));
var _woff2base = _interopRequireDefault(require("./woff2base64"));
var _svg2base = _interopRequireDefault(require("./svg2base64"));
var _bytes2base = _interopRequireDefault(require("./util/bytes2base64"));
var _woff2tobase = _interopRequireDefault(require("./woff2tobase64"));
var _optimizettf = _interopRequireDefault(require("./util/optimizettf"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }
function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }
function _defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, _toPropertyKey(descriptor.key), descriptor); } }
function _createClass(Constructor, protoProps, staticProps) { if (protoProps) _defineProperties(Constructor.prototype, protoProps); if (staticProps) _defineProperties(Constructor, staticProps); Object.defineProperty(Constructor, "prototype", { writable: false }); return Constructor; }
function _toPropertyKey(t) { var i = _toPrimitive(t, "string"); return "symbol" == _typeof(i) ? i : i + ""; }
function _toPrimitive(t, r) { if ("object" != _typeof(t) || !t) return t; var e = t[Symbol.toPrimitive]; if (void 0 !== e) { var i = e.call(t, r || "default"); if ("object" != _typeof(i)) return i; throw new TypeError("@@toPrimitive must return a primitive value."); } return ("string" === r ? String : Number)(t); }
function _typeof(o) { "@babel/helpers - typeof"; return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function (o) { return typeof o; } : function (o) { return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o; }, _typeof(o); } /**
 * @file 字体管理对象，处理字体相关的读取、查询、转换
 *
 * @author mengke01(kekee000@gmail.com)
 */
var SUPPORT_BUFFER = (typeof process === "undefined" ? "undefined" : _typeof(process)) === 'object' && _typeof(process.versions) === 'object' && typeof process.versions.node !== 'undefined' && typeof Buffer === 'function';
var Font = exports.Font = /*#__PURE__*/function () {
  function Font(buffer) {
    var options = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {
      type: 'ttf'
    };
    _classCallCheck(this, Font);
    if (_typeof(buffer) === 'object' && buffer.glyf) {
      this.set(buffer);
    }
    else if (buffer) {
      this.read(buffer, options);
    }
    else {
      this.readEmpty();
    }
  }

  return _createClass(Font, [{
    key: "readEmpty",
    value:
    function readEmpty() {
      this.data = (0, _getEmptyttfObject.default)();
      return this;
    }

  }, {
    key: "read",
    value: function read(buffer, options) {
      if (SUPPORT_BUFFER) {
        if (buffer instanceof Buffer) {
          buffer = _buffer.default.toArrayBuffer(buffer);
        }
      }
      if (options.type === 'ttf') {
        this.data = new _ttfreader.default(options).read(buffer);
      } else if (options.type === 'otf') {
        this.data = (0, _otf2ttfobject.default)(buffer, options);
      } else if (options.type === 'eot') {
        buffer = (0, _eot2ttf.default)(buffer, options);
        this.data = new _ttfreader.default(options).read(buffer);
      } else if (options.type === 'woff') {
        buffer = (0, _woff2ttf.default)(buffer, options);
        this.data = new _ttfreader.default(options).read(buffer);
      } else if (options.type === 'woff2') {
        buffer = (0, _woff2tottf.default)(buffer, options);
        this.data = new _ttfreader.default(options).read(buffer);
      } else if (options.type === 'svg') {
        this.data = (0, _svg2ttfobject.default)(buffer, options);
      } else {
        throw new Error('not support font type' + options.type);
      }
      this.type = options.type;
      return this;
    }

  }, {
    key: "write",
    value: function write() {
      var options = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : {};
      if (!options.type) {
        options.type = this.type;
      }
      var buffer = null;
      if (options.type === 'ttf') {
        buffer = new _ttfwriter.default(options).write(this.data);
      } else if (options.type === 'eot') {
        buffer = new _ttfwriter.default(options).write(this.data);
        buffer = (0, _ttf2eot.default)(buffer, options);
      } else if (options.type === 'woff') {
        buffer = new _ttfwriter.default(options).write(this.data);
        buffer = (0, _ttf2woff.default)(buffer, options);
      } else if (options.type === 'woff2') {
        buffer = new _ttfwriter.default(options).write(this.data);
        buffer = (0, _ttftowoff.default)(buffer, options);
      } else if (options.type === 'svg') {
        buffer = (0, _ttf2svg.default)(this.data, options);
      } else if (options.type === 'symbol') {
        buffer = (0, _ttf2symbol.default)(this.data, options);
      } else {
        throw new Error('not support font type' + options.type);
      }
      if (SUPPORT_BUFFER) {
        if (false !== options.toBuffer && buffer instanceof ArrayBuffer) {
          buffer = _buffer.default.toBuffer(buffer);
        }
      }
      return buffer;
    }

  }, {
    key: "toBase64",
    value: function toBase64(options, buffer) {
      if (!options.type) {
        options.type = this.type;
      }
      if (buffer) {
        if (SUPPORT_BUFFER) {
          if (buffer instanceof Buffer) {
            buffer = _buffer.default.toArrayBuffer(buffer);
          }
        }
      } else {
        options.toBuffer = false;
        buffer = this.write(options);
      }
      var base64Str;
      if (options.type === 'ttf') {
        base64Str = (0, _ttf2base.default)(buffer);
      } else if (options.type === 'eot') {
        base64Str = (0, _eot2base.default)(buffer);
      } else if (options.type === 'woff') {
        base64Str = (0, _woff2base.default)(buffer);
      } else if (options.type === 'woff2') {
        base64Str = (0, _woff2tobase.default)(buffer);
      } else if (options.type === 'svg') {
        base64Str = (0, _svg2base.default)(buffer);
      } else if (options.type === 'symbol') {
        base64Str = (0, _svg2base.default)(buffer, 'image/svg+xml');
      } else {
        throw new Error('not support font type' + options.type);
      }
      return base64Str;
    }

  }, {
    key: "set",
    value: function set(data) {
      this.data = data;
      return this;
    }

  }, {
    key: "get",
    value: function get() {
      return this.data;
    }

  }, {
    key: "optimize",
    value: function optimize(out) {
      var result = (0, _optimizettf.default)(this.data);
      if (out) {
        out.result = result;
      }
      return this;
    }

  }, {
    key: "compound2simple",
    value: function compound2simple() {
      var ttfHelper = this.getHelper();
      ttfHelper.compound2simple();
      this.data = ttfHelper.get();
      return this;
    }

  }, {
    key: "sort",
    value: function sort() {
      var ttfHelper = this.getHelper();
      ttfHelper.sortGlyf();
      this.data = ttfHelper.get();
      return this;
    }

  }, {
    key: "find",
    value: function find(condition) {
      var ttfHelper = this.getHelper();
      var indexList = ttfHelper.findGlyf(condition);
      return indexList.length ? ttfHelper.getGlyf(indexList) : indexList;
    }

  }, {
    key: "merge",
    value: function merge(font, options) {
      var ttfHelper = this.getHelper();
      ttfHelper.mergeGlyf(font.get(), options);
      this.data = ttfHelper.get();
      return this;
    }

  }, {
    key: "getHelper",
    value: function getHelper() {
      return new _ttf.default(this.data);
    }
  }], [{
    key: "create",
    value: function create(buffer, options) {
      return new Font(buffer, options);
    }
  }]);
}();
Font.toBase64 = function (buffer) {
  if (typeof buffer === 'string') {
    if (typeof btoa === 'undefined') {
      return Buffer.from(buffer, 'binary').toString('base64');
    }
    return btoa(buffer);
  }
  return (0, _bytes2base.default)(buffer);
};
function createFont(buffer, options) {
  return new Font(buffer, options);
}
var _default = exports.default = Font;
