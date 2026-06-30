"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _table = _interopRequireDefault(require("./table"));
var _parse = _interopRequireDefault(require("./glyf/parse"));
var _write = _interopRequireDefault(require("./glyf/write"));
var _sizeof = _interopRequireDefault(require("./glyf/sizeof"));
var _lang = require("../../common/lang");
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }
var _default = exports.default = _table.default.create('glyf', [], {
  read: function read(reader, ttf) {
    var startOffset = this.offset;
    var loca = ttf.loca;
    var numGlyphs = ttf.maxp.numGlyphs;
    var glyphs = [];
    reader.seek(startOffset);

    var subset = ttf.readOptions.subset;
    if (subset && subset.length > 0) {
      var subsetMap = {
        0: true // 设置.notdef
      };
      subsetMap[0] = true;
      var cmap = ttf.cmap;

      Object.keys(cmap).forEach(function (c) {
        if (subset.indexOf(+c) > -1) {
          var _i = cmap[c];
          subsetMap[_i] = true;
        }
      });
      ttf.subsetMap = subsetMap;
      var parsedGlyfMap = {};
      var travelsParse = function travels(subsetMap) {
        var newSubsetMap = {};
        Object.keys(subsetMap).forEach(function (i) {
          var index = +i;
          parsedGlyfMap[index] = true;
          if (loca[index] === loca[index + 1]) {
            glyphs[index] = {
              contours: []
            };
          } else {
            glyphs[index] = (0, _parse.default)(reader, ttf, startOffset + loca[index]);
          }
          if (glyphs[index].compound) {
            glyphs[index].glyfs.forEach(function (g) {
              if (!parsedGlyfMap[g.glyphIndex]) {
                newSubsetMap[g.glyphIndex] = true;
              }
            });
          }
        });
        if (!(0, _lang.isEmptyObject)(newSubsetMap)) {
          travels(newSubsetMap);
        }
      };
      travelsParse(subsetMap);
      return glyphs;
    }

    var i;
    var l;
    for (i = 0, l = numGlyphs - 1; i < l; i++) {
      if (loca[i] === loca[i + 1]) {
        glyphs[i] = {
          contours: []
        };
      } else {
        glyphs[i] = (0, _parse.default)(reader, ttf, startOffset + loca[i]);
      }
    }

    if (ttf.tables.glyf.length - loca[i] < 5) {
      glyphs[i] = {
        contours: []
      };
    } else {
      glyphs[i] = (0, _parse.default)(reader, ttf, startOffset + loca[i]);
    }
    return glyphs;
  },
  write: _write.default,
  size: _sizeof.default
});
