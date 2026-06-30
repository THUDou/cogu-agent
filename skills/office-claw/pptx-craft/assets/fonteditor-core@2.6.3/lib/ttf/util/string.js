"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _unicodeName = _interopRequireDefault(require("../enum/unicodeName"));
var _postName = _interopRequireDefault(require("../enum/postName"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function stringify(str) {
  if (!str) {
    return str;
  }
  var newStr = '';
  for (var i = 0, l = str.length, ch; i < l; i++) {
    ch = str.charCodeAt(i);
    if (ch === 0) {
      continue;
    }
    newStr += String.fromCharCode(ch);
  }
  return newStr;
}
var _default = exports.default = {
  stringify: stringify,
  escape: function (_escape) {
    function escape(_x) {
      return _escape.apply(this, arguments);
    }
    escape.toString = function () {
      return _escape.toString();
    };
    return escape;
  }(function (str) {
    if (!str) {
      return str;
    }
    return String(str).replace(/[\uff-\uffff]/g, function (c) {
      return escape(c).replace('%', '\\');
    });
  }),
  getString: function getString(bytes) {
    var s = '';
    for (var i = 0, l = bytes.length; i < l; i++) {
      s += String.fromCharCode(bytes[i]);
    }
    return s;
  },
  getUnicodeName: function getUnicodeName(unicode) {
    var unicodeNameIndex = _unicodeName.default[unicode];
    if (undefined !== unicodeNameIndex) {
      return _postName.default[unicodeNameIndex];
    }
    return 'uni' + unicode.toString(16).toUpperCase();
  },
  toUTF8Bytes: function toUTF8Bytes(str) {
    str = stringify(str);
    var byteArray = [];
    for (var i = 0, l = str.length; i < l; i++) {
      if (str.charCodeAt(i) <= 0x7F) {
        byteArray.push(str.charCodeAt(i));
      } else {
        var codePoint = str.codePointAt(i);
        if (codePoint > 0xffff) {
          i++;
        }
        var h = encodeURIComponent(String.fromCodePoint(codePoint)).slice(1).split('%');
        for (var j = 0; j < h.length; j++) {
          byteArray.push(parseInt(h[j], 16));
        }
      }
    }
    return byteArray;
  },
  toUCS2Bytes: function toUCS2Bytes(str) {
    str = stringify(str);
    var byteArray = [];
    for (var i = 0, l = str.length, ch; i < l; i++) {
      ch = str.charCodeAt(i);
      byteArray.push(ch >> 8);
      byteArray.push(ch & 0xFF);
    }
    return byteArray;
  },
  toPascalStringBytes: function toPascalStringBytes(str) {
    var bytes = [];
    var length = str ? str.length < 256 ? str.length : 255 : 0;
    bytes.push(length);
    for (var i = 0, l = str.length; i < l; i++) {
      var c = str.charCodeAt(i);
      bytes.push(c < 128 ? c : 42);
    }
    return bytes;
  },
  getUTF8String: function getUTF8String(bytes) {
    var str = '';
    for (var i = 0, l = bytes.length; i < l; i++) {
      if (bytes[i] < 0x7F) {
        str += String.fromCharCode(bytes[i]);
      } else {
        str += '%' + (256 + bytes[i]).toString(16).slice(1);
      }
    }
    return unescape(str);
  },
  getUCS2String: function getUCS2String(bytes) {
    var str = '';
    for (var i = 0, l = bytes.length; i < l; i += 2) {
      str += String.fromCharCode((bytes[i] << 8) + bytes[i + 1]);
    }
    return str;
  },
  getPascalString: function getPascalString(byteArray) {
    var strArray = [];
    var i = 0;
    var l = byteArray.length;
    while (i < l) {
      var strLength = byteArray[i++];
      var str = '';
      while (strLength-- > 0 && i < l) {
        str += String.fromCharCode(byteArray[i++]);
      }
      str = stringify(str);
      strArray.push(str);
    }
    return strArray;
  }
};
