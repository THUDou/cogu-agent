"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = ttf2icon;
var _ttfreader = _interopRequireDefault(require("./ttfreader"));
var _error = _interopRequireDefault(require("./error"));
var _default = _interopRequireDefault(require("./data/default"));
var _ttf2symbol = require("./ttf2symbol");
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function listUnicode(unicode) {
  return unicode.map(function (u) {
    return '\\' + u.toString(16);
  }).join(',');
}

function ttfobject2icon(ttf) {
  var options = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {};
  var glyfList = [];

  var filtered = ttf.glyf.filter(function (g) {
    return g.name !== '.notdef' && g.name !== '.null' && g.name !== 'nonmarkingreturn' && g.unicode && g.unicode.length;
  });
  filtered.forEach(function (g, i) {
    glyfList.push({
      code: '&#x' + g.unicode[0].toString(16) + ';',
      codeName: listUnicode(g.unicode),
      name: g.name,
      id: (0, _ttf2symbol.getSymbolId)(g, i)
    });
  });
  return {
    fontFamily: ttf.name.fontFamily || _default.default.name.fontFamily,
    iconPrefix: options.iconPrefix || 'icon',
    glyfList: glyfList
  };
}

function ttf2icon(ttfBuffer) {
  var options = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {};
  if (ttfBuffer instanceof ArrayBuffer) {
    var reader = new _ttfreader.default();
    var ttfObject = reader.read(ttfBuffer);
    reader.dispose();
    return ttfobject2icon(ttfObject, options);
  }
  else if (ttfBuffer.version && ttfBuffer.glyf) {
    return ttfobject2icon(ttfBuffer, options);
  }
  _error.default.raise(10101);
}
