"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _directory = _interopRequireDefault(require("./table/directory"));
var _supportOtf = _interopRequireDefault(require("./table/support-otf"));
var _reader = _interopRequireDefault(require("./reader"));
var _error = _interopRequireDefault(require("./error"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }
function _typeof(o) { "@babel/helpers - typeof"; return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function (o) { return typeof o; } : function (o) { return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o; }, _typeof(o); }
function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }
function _defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, _toPropertyKey(descriptor.key), descriptor); } }
function _createClass(Constructor, protoProps, staticProps) { if (protoProps) _defineProperties(Constructor.prototype, protoProps); if (staticProps) _defineProperties(Constructor, staticProps); Object.defineProperty(Constructor, "prototype", { writable: false }); return Constructor; }
function _toPropertyKey(t) { var i = _toPrimitive(t, "string"); return "symbol" == _typeof(i) ? i : i + ""; }
function _toPrimitive(t, r) { if ("object" != _typeof(t) || !t) return t; var e = t[Symbol.toPrimitive]; if (void 0 !== e) { var i = e.call(t, r || "default"); if ("object" != _typeof(i)) return i; throw new TypeError("@@toPrimitive must return a primitive value."); } return ("string" === r ? String : Number)(t); } /**
 * @file otf字体读取
 * @author mengke01(kekee000@gmail.com)
 */
var OTFReader = exports.default = /*#__PURE__*/function () {
  function OTFReader() {
    var options = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : {};
    _classCallCheck(this, OTFReader);
    options.subset = options.subset || [];
    this.options = options;
  }

  return _createClass(OTFReader, [{
    key: "readBuffer",
    value: function readBuffer(buffer) {
      var reader = new _reader.default(buffer, 0, buffer.byteLength, false);
      var font = {};

      font.version = reader.readString(0, 4);
      if (font.version !== 'OTTO') {
        _error.default.raise(10301);
      }

      font.numTables = reader.readUint16();
      if (font.numTables <= 0 || font.numTables > 100) {
        _error.default.raise(10302);
      }

      font.searchRange = reader.readUint16();

      font.entrySelector = reader.readUint16();

      font.rangeShift = reader.readUint16();
      font.tables = new _directory.default(reader.offset).read(reader, font);
      if (!font.tables.head || !font.tables.cmap || !font.tables.CFF) {
        _error.default.raise(10302);
      }
      font.readOptions = this.options;

      Object.keys(_supportOtf.default).forEach(function (tableName) {
        if (font.tables[tableName]) {
          var offset = font.tables[tableName].offset;
          font[tableName] = new _supportOtf.default[tableName](offset).read(reader, font);
        }
      });
      if (!font.CFF.glyf) {
        _error.default.raise(10303);
      }
      reader.dispose();
      return font;
    }

  }, {
    key: "resolveGlyf",
    value: function resolveGlyf(font) {
      var codes = font.cmap;
      var glyf = font.CFF.glyf;
      var subsetMap = font.readOptions.subset ? font.subsetMap : null; // 当前ttf的子集列表
      Object.keys(codes).forEach(function (c) {
        var i = codes[c];
        if (subsetMap && !subsetMap[i]) {
          return;
        }
        if (!glyf[i].unicode) {
          glyf[i].unicode = [];
        }
        glyf[i].unicode.push(+c);
      });

      font.hmtx.forEach(function (item, i) {
        if (subsetMap && !subsetMap[i]) {
          return;
        }
        glyf[i].advanceWidth = glyf[i].advanceWidth || item.advanceWidth || 0;
        glyf[i].leftSideBearing = item.leftSideBearing;
      });

      if (subsetMap) {
        var subGlyf = [];
        Object.keys(subsetMap).forEach(function (i) {
          subGlyf.push(glyf[+i]);
        });
        glyf = subGlyf;
      }
      font.glyf = glyf;
    }

  }, {
    key: "cleanTables",
    value: function cleanTables(font) {
      delete font.readOptions;
      delete font.tables;
      delete font.hmtx;
      delete font.post.glyphNameIndex;
      delete font.post.names;
      delete font.subsetMap;

      var cff = font.CFF;
      delete cff.glyf;
      delete cff.charset;
      delete cff.encoding;
      delete cff.gsubrs;
      delete cff.gsubrsBias;
      delete cff.subrs;
      delete cff.subrsBias;
    }

  }, {
    key: "read",
    value: function read(buffer) {
      this.font = this.readBuffer(buffer);
      this.resolveGlyf(this.font);
      this.cleanTables(this.font);
      return this.font;
    }

  }, {
    key: "dispose",
    value: function dispose() {
      delete this.font;
      delete this.options;
    }
  }]);
}();
