"use strict";

function _typeof(o) { "@babel/helpers - typeof"; return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function (o) { return typeof o; } : function (o) { return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o; }, _typeof(o); }
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _lang = require("../common/lang");
var _string = _interopRequireDefault(require("./util/string"));
var _pathAdjust = _interopRequireDefault(require("../graphics/pathAdjust"));
var _pathCeil = _interopRequireDefault(require("../graphics/pathCeil"));
var _computeBoundingBox = require("../graphics/computeBoundingBox");
var _compound2simpleglyf = _interopRequireDefault(require("./util/compound2simpleglyf"));
var _glyfAdjust = _interopRequireDefault(require("./util/glyfAdjust"));
var _optimizettf = _interopRequireDefault(require("./util/optimizettf"));
var _default = _interopRequireDefault(require("./data/default"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }
function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }
function _defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, _toPropertyKey(descriptor.key), descriptor); } }
function _createClass(Constructor, protoProps, staticProps) { if (protoProps) _defineProperties(Constructor.prototype, protoProps); if (staticProps) _defineProperties(Constructor, staticProps); Object.defineProperty(Constructor, "prototype", { writable: false }); return Constructor; }
function _toPropertyKey(t) { var i = _toPrimitive(t, "string"); return "symbol" == _typeof(i) ? i : i + ""; }
function _toPrimitive(t, r) { if ("object" != _typeof(t) || !t) return t; var e = t[Symbol.toPrimitive]; if (void 0 !== e) { var i = e.call(t, r || "default"); if ("object" != _typeof(i)) return i; throw new TypeError("@@toPrimitive must return a primitive value."); } return ("string" === r ? String : Number)(t); }
function _toConsumableArray(arr) { return _arrayWithoutHoles(arr) || _iterableToArray(arr) || _unsupportedIterableToArray(arr) || _nonIterableSpread(); }
function _nonIterableSpread() { throw new TypeError("Invalid attempt to spread non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method."); }
function _unsupportedIterableToArray(o, minLen) { if (!o) return; if (typeof o === "string") return _arrayLikeToArray(o, minLen); var n = Object.prototype.toString.call(o).slice(8, -1); if (n === "Object" && o.constructor) n = o.constructor.name; if (n === "Map" || n === "Set") return Array.from(o); if (n === "Arguments" || /^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n)) return _arrayLikeToArray(o, minLen); }
function _iterableToArray(iter) { if (typeof Symbol !== "undefined" && iter[Symbol.iterator] != null || iter["@@iterator"] != null) return Array.from(iter); }
function _arrayWithoutHoles(arr) { if (Array.isArray(arr)) return _arrayLikeToArray(arr); }
function _arrayLikeToArray(arr, len) { if (len == null || len > arr.length) len = arr.length; for (var i = 0, arr2 = new Array(len); i < len; i++) arr2[i] = arr[i]; return arr2; } /**
 * @file ttf相关处理对象
 * @author mengke01(kekee000@gmail.com)
 */
function adjustToEmBox(glyfList, ascent, descent, adjustToEmPadding) {
  glyfList.forEach(function (g) {
    if (g.contours && g.contours.length) {
      var rightSideBearing = g.advanceWidth - g.xMax;
      var bound = _computeBoundingBox.computePath.apply(void 0, _toConsumableArray(g.contours));
      var scale = (ascent - descent - adjustToEmPadding) / bound.height;
      var center = (ascent + descent) / 2;
      var yOffset = center - (bound.y + bound.height / 2) * scale;
      g.contours.forEach(function (contour) {
        if (scale !== 1) {
          (0, _pathAdjust.default)(contour, scale, scale);
        }
        (0, _pathAdjust.default)(contour, 1, 1, 0, yOffset);
        (0, _pathCeil.default)(contour);
      });
      var box = _computeBoundingBox.computePathBox.apply(void 0, _toConsumableArray(g.contours));
      g.xMin = box.x;
      g.xMax = box.x + box.width;
      g.yMin = box.y;
      g.yMax = box.y + box.height;
      g.leftSideBearing = g.xMin;
      g.advanceWidth = g.xMax + rightSideBearing;
    }
  });
  return glyfList;
}

function adjustPos(glyfList, leftSideBearing, rightSideBearing, verticalAlign) {
  var changed = false;

  if (null != leftSideBearing) {
    changed = true;
    glyfList.forEach(function (g) {
      if (g.leftSideBearing !== leftSideBearing) {
        (0, _glyfAdjust.default)(g, 1, 1, leftSideBearing - g.leftSideBearing);
      }
    });
  }

  if (null != rightSideBearing) {
    changed = true;
    glyfList.forEach(function (g) {
      g.advanceWidth = g.xMax + rightSideBearing;
    });
  }

  if (null != verticalAlign) {
    changed = true;
    glyfList.forEach(function (g) {
      if (g.contours && g.contours.length) {
        var bound = _computeBoundingBox.computePath.apply(void 0, _toConsumableArray(g.contours));
        var offset = verticalAlign - bound.y;
        (0, _glyfAdjust.default)(g, 1, 1, 0, offset);
      }
    });
  }
  return changed ? glyfList : [];
}

function merge(ttf, imported) {
  var options = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : {
    scale: true
  };
  var list = imported.glyf.filter(function (g) {
    return (
      g.contours && g.contours.length
      && g.name !== '.notdef' && g.name !== '.null' && g.name !== 'nonmarkingreturn'
    );
  });

  if (options.adjustGlyf) {
    var ascent = ttf.hhea.ascent;
    var descent = ttf.hhea.descent;
    var adjustToEmPadding = 16;
    adjustPos(list, 16, 16);
    adjustToEmBox(list, ascent, descent, adjustToEmPadding);
    list.forEach(function (g) {
      ttf.glyf.push(g);
    });
  }
  else if (options.scale) {
    var scale = 1;

    if (imported.head.unitsPerEm && imported.head.unitsPerEm !== ttf.head.unitsPerEm) {
      scale = ttf.head.unitsPerEm / imported.head.unitsPerEm;
    }
    list.forEach(function (g) {
      (0, _glyfAdjust.default)(g, scale, scale);
      ttf.glyf.push(g);
    });
  }
  return list;
}
var TTF = exports.default = /*#__PURE__*/function () {
  function TTF(ttf) {
    _classCallCheck(this, TTF);
    this.ttf = ttf;
  }

  return _createClass(TTF, [{
    key: "codes",
    value: function codes() {
      return Object.keys(this.ttf.cmap);
    }

  }, {
    key: "getGlyfIndexByCode",
    value: function getGlyfIndexByCode(c) {
      var charCode = typeof c === 'number' ? c : c.codePointAt(0);
      var glyfIndex = this.ttf.cmap[charCode] || -1;
      return glyfIndex;
    }

  }, {
    key: "getGlyfByIndex",
    value: function getGlyfByIndex(glyfIndex) {
      var glyfList = this.ttf.glyf;
      var glyf = glyfList[glyfIndex];
      return glyf;
    }

  }, {
    key: "getGlyfByCode",
    value: function getGlyfByCode(c) {
      var glyfIndex = this.getGlyfIndexByCode(c);
      return this.getGlyfByIndex(glyfIndex);
    }

  }, {
    key: "set",
    value: function set(ttf) {
      this.ttf = ttf;
      return this;
    }

  }, {
    key: "get",
    value: function get() {
      return this.ttf;
    }

  }, {
    key: "addGlyf",
    value: function addGlyf(glyf) {
      return this.insertGlyf(glyf);
    }

  }, {
    key: "insertGlyf",
    value: function insertGlyf(glyf, insertIndex) {
      if (insertIndex >= 0 && insertIndex < this.ttf.glyf.length) {
        this.ttf.glyf.splice(insertIndex, 0, glyf);
      } else {
        this.ttf.glyf.push(glyf);
      }
      return [glyf];
    }

  }, {
    key: "mergeGlyf",
    value: function mergeGlyf(imported, options) {
      var list = merge(this.ttf, imported, options);
      return list;
    }

  }, {
    key: "removeGlyf",
    value: function removeGlyf(indexList) {
      var glyf = this.ttf.glyf;
      var removed = [];
      for (var i = glyf.length - 1; i >= 0; i--) {
        if (indexList.indexOf(i) >= 0) {
          removed.push(glyf[i]);
          glyf.splice(i, 1);
        }
      }
      return removed;
    }

  }, {
    key: "setUnicode",
    value: function setUnicode(unicode, indexList, isGenerateName) {
      var glyf = this.ttf.glyf;
      var list = [];
      if (indexList && indexList.length) {
        var first = indexList.indexOf(0);
        if (first >= 0) {
          indexList.splice(first, 1);
        }
        list = indexList.map(function (item) {
          return glyf[item];
        });
      } else {
        list = glyf.slice(1);
      }

      if (list.length > 1) {
        var less32 = function less32(u) {
          return u < 33;
        };
        list = list.filter(function (g) {
          return !g.unicode || !g.unicode.some(less32);
        });
      }
      if (list.length) {
        unicode = Number('0x' + unicode.slice(1));
        list.forEach(function (g) {
          if (unicode === 0xA0 || unicode === 0x3000) {
            unicode++;
          }
          g.unicode = [unicode];
          if (isGenerateName) {
            g.name = _string.default.getUnicodeName(unicode);
          }
          unicode++;
        });
      }
      return list;
    }

  }, {
    key: "genGlyfName",
    value: function genGlyfName(indexList) {
      var glyf = this.ttf.glyf;
      var list = [];
      if (indexList && indexList.length) {
        list = indexList.map(function (item) {
          return glyf[item];
        });
      } else {
        list = glyf;
      }
      if (list.length) {
        var first = this.ttf.glyf[0];
        list.forEach(function (g) {
          if (g === first) {
            g.name = '.notdef';
          } else if (g.unicode && g.unicode.length) {
            g.name = _string.default.getUnicodeName(g.unicode[0]);
          } else {
            g.name = '.notdef';
          }
        });
      }
      return list;
    }

  }, {
    key: "clearGlyfName",
    value: function clearGlyfName(indexList) {
      var glyf = this.ttf.glyf;
      var list = [];
      if (indexList && indexList.length) {
        list = indexList.map(function (item) {
          return glyf[item];
        });
      } else {
        list = glyf;
      }
      if (list.length) {
        list.forEach(function (g) {
          delete g.name;
        });
      }
      return list;
    }

  }, {
    key: "appendGlyf",
    value: function appendGlyf(glyfList, indexList) {
      var glyf = this.ttf.glyf;
      var result = glyfList.slice(0);
      if (indexList && indexList.length) {
        var l = Math.min(glyfList.length, indexList.length);
        for (var i = 0; i < l; i++) {
          glyf[indexList[i]] = glyfList[i];
        }
        glyfList = glyfList.slice(l);
      }
      if (glyfList.length) {
        Array.prototype.splice.apply(glyf, [glyf.length, 0].concat(_toConsumableArray(glyfList)));
      }
      return result;
    }

  }, {
    key: "adjustGlyfPos",
    value: function adjustGlyfPos(indexList, setting) {
      var glyfList = this.getGlyf(indexList);
      return adjustPos(glyfList, setting.leftSideBearing, setting.rightSideBearing, setting.verticalAlign);
    }

  }, {
    key: "adjustGlyf",
    value: function adjustGlyf(indexList, setting) {
      var glyfList = this.getGlyf(indexList);
      var changed = false;
      setting.adjustToEmBox = setting.ajdustToEmBox || setting.adjustToEmBox;
      setting.adjustToEmPadding = setting.ajdustToEmPadding || setting.adjustToEmPadding;
      if (setting.reverse || setting.mirror) {
        changed = true;
        glyfList.forEach(function (g) {
          if (g.contours && g.contours.length) {
            var offsetX = g.xMax + g.xMin;
            var offsetY = g.yMax + g.yMin;
            g.contours.forEach(function (contour) {
              (0, _pathAdjust.default)(contour, setting.mirror ? -1 : 1, setting.reverse ? -1 : 1);
              (0, _pathAdjust.default)(contour, 1, 1, setting.mirror ? offsetX : 0, setting.reverse ? offsetY : 0);
            });
          }
        });
      }
      if (setting.scale && setting.scale !== 1) {
        changed = true;
        var scale = setting.scale;
        glyfList.forEach(function (g) {
          if (g.contours && g.contours.length) {
            (0, _glyfAdjust.default)(g, scale, scale);
          }
        });
      }
      else if (setting.adjustToEmBox) {
        changed = true;
        var ascent = this.ttf.hhea.ascent;
        var descent = this.ttf.hhea.descent;
        var adjustToEmPadding = 2 * (setting.adjustToEmPadding || 0);
        adjustToEmBox(glyfList, ascent, descent, adjustToEmPadding);
      }
      return changed ? glyfList : [];
    }

  }, {
    key: "getGlyf",
    value: function getGlyf(indexList) {
      var glyf = this.ttf.glyf;
      if (indexList && indexList.length) {
        return indexList.map(function (item) {
          return glyf[item];
        });
      }
      return glyf;
    }

  }, {
    key: "findGlyf",
    value: function findGlyf(condition) {
      if (!condition) {
        return [];
      }
      var filters = [];

      if (condition.unicode) {
        var unicodeList = Array.isArray(condition.unicode) ? condition.unicode : [condition.unicode];
        var unicodeHash = {};
        unicodeList.forEach(function (unicode) {
          if (typeof unicode === 'string') {
            unicode = Number('0x' + unicode.slice(1));
          }
          unicodeHash[unicode] = true;
        });
        filters.push(function (glyf) {
          if (!glyf.unicode || !glyf.unicode.length) {
            return false;
          }
          for (var i = 0, l = glyf.unicode.length; i < l; i++) {
            if (unicodeHash[glyf.unicode[i]]) {
              return true;
            }
          }
        });
      }

      if (condition.name) {
        var name = condition.name;
        filters.push(function (glyf) {
          return glyf.name && glyf.name.indexOf(name) === 0;
        });
      }

      if (typeof condition.filter === 'function') {
        filters.push(condition.filter);
      }
      var indexList = [];
      this.ttf.glyf.forEach(function (glyf, index) {
        for (var filterIndex = 0, filter; filter = filters[filterIndex++];) {
          if (true === filter(glyf)) {
            indexList.push(index);
            break;
          }
        }
      });
      return indexList;
    }

  }, {
    key: "replaceGlyf",
    value: function replaceGlyf(glyf, index) {
      if (index >= 0 && index < this.ttf.glyf.length) {
        this.ttf.glyf[index] = glyf;
        return [glyf];
      }
      return [];
    }

  }, {
    key: "setGlyf",
    value: function setGlyf(glyfList) {
      delete this.glyf;
      this.ttf.glyf = glyfList || [];
      return this.ttf.glyf;
    }

  }, {
    key: "sortGlyf",
    value: function sortGlyf() {
      var glyf = this.ttf.glyf;
      if (glyf.length > 1) {
        if (glyf.some(function (a) {
          return a.compound;
        })) {
          return -2;
        }
        var notdef = glyf.shift();
        glyf.sort(function (a, b) {
          if ((!a.unicode || !a.unicode.length) && (!b.unicode || !b.unicode.length)) {
            return 0;
          } else if ((!a.unicode || !a.unicode.length) && b.unicode) {
            return 1;
          } else if (a.unicode && (!b.unicode || !b.unicode.length)) {
            return -1;
          }
          return Math.min.apply(null, a.unicode) - Math.min.apply(null, b.unicode);
        });
        glyf.unshift(notdef);
        return glyf;
      }
      return -1;
    }

  }, {
    key: "setName",
    value: function setName(name) {
      if (name) {
        this.ttf.name.fontFamily = this.ttf.name.fullName = name.fontFamily || _default.default.name.fontFamily;
        this.ttf.name.fontSubFamily = name.fontSubFamily || _default.default.name.fontSubFamily;
        this.ttf.name.uniqueSubFamily = name.uniqueSubFamily || '';
        this.ttf.name.postScriptName = name.postScriptName || '';
      }
      return this.ttf.name;
    }

  }, {
    key: "setHead",
    value: function setHead(head) {
      if (head) {
        if (head.unitsPerEm && head.unitsPerEm >= 64 && head.unitsPerEm <= 16384) {
          this.ttf.head.unitsPerEm = head.unitsPerEm;
        }

        if (head.lowestRecPPEM && head.lowestRecPPEM >= 8 && head.lowestRecPPEM <= 16384) {
          this.ttf.head.lowestRecPPEM = head.lowestRecPPEM;
        }
        if (head.created) {
          this.ttf.head.created = head.created;
        }
        if (head.modified) {
          this.ttf.head.modified = head.modified;
        }
      }
      return this.ttf.head;
    }

  }, {
    key: "setHhea",
    value: function setHhea(fields) {
      (0, _lang.overwrite)(this.ttf.hhea, fields, ['ascent', 'descent', 'lineGap']);
      return this.ttf.hhea;
    }

  }, {
    key: "setOS2",
    value: function setOS2(fields) {
      (0, _lang.overwrite)(this.ttf['OS/2'], fields, ['usWinAscent', 'usWinDescent', 'sTypoAscender', 'sTypoDescender', 'sTypoLineGap', 'sxHeight', 'bXHeight', 'usWeightClass', 'usWidthClass', 'yStrikeoutPosition', 'yStrikeoutSize', 'achVendID',
      'bFamilyType', 'bSerifStyle', 'bWeight', 'bProportion', 'bContrast', 'bStrokeVariation', 'bArmStyle', 'bLetterform', 'bMidline', 'bXHeight']);
      return this.ttf['OS/2'];
    }

  }, {
    key: "setPost",
    value: function setPost(fields) {
      (0, _lang.overwrite)(this.ttf.post, fields, ['underlinePosition', 'underlineThickness']);
      return this.ttf.post;
    }

  }, {
    key: "calcMetrics",
    value: function calcMetrics() {
      var ascent = -16384;
      var descent = 16384;
      var uX = 0x78;
      var uH = 0x48;
      var sxHeight;
      var sCapHeight;
      this.ttf.glyf.forEach(function (g) {
        if (g.yMax > ascent) {
          ascent = g.yMax;
        }
        if (g.yMin < descent) {
          descent = g.yMin;
        }
        if (g.unicode) {
          if (g.unicode.indexOf(uX) >= 0) {
            sxHeight = g.yMax;
          }
          if (g.unicode.indexOf(uH) >= 0) {
            sCapHeight = g.yMax;
          }
        }
      });
      ascent = Math.round(ascent);
      descent = Math.round(descent);
      return {
        ascent: ascent,
        descent: descent,
        sTypoAscender: ascent,
        sTypoDescender: descent,
        usWinAscent: ascent,
        usWinDescent: -descent,
        sxHeight: sxHeight || 0,
        sCapHeight: sCapHeight || 0
      };
    }

  }, {
    key: "optimize",
    value: function optimize() {
      return (0, _optimizettf.default)(this.ttf);
    }

  }, {
    key: "compound2simple",
    value: function compound2simple(indexList) {
      var ttf = this.ttf;
      if (ttf.maxp && !ttf.maxp.maxComponentElements) {
        return [];
      }
      var i;
      var l;
      if (!indexList || !indexList.length) {
        indexList = [];
        for (i = 0, l = ttf.glyf.length; i < l; ++i) {
          if (ttf.glyf[i].compound) {
            indexList.push(i);
          }
        }
      }
      var list = [];
      for (i = 0, l = indexList.length; i < l; ++i) {
        var glyfIndex = indexList[i];
        if (ttf.glyf[glyfIndex] && ttf.glyf[glyfIndex].compound) {
          (0, _compound2simpleglyf.default)(glyfIndex, ttf, true);
          list.push(ttf.glyf[glyfIndex]);
        }
      }
      return list;
    }
  }]);
}();
