"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _table = _interopRequireDefault(require("./table"));
var _string = _interopRequireDefault(require("../util/string"));
var _encoding = _interopRequireDefault(require("./cff/encoding"));
var _cffStandardStrings = _interopRequireDefault(require("./cff/cffStandardStrings"));
var _parseCFFDict = _interopRequireDefault(require("./cff/parseCFFDict"));
var _parseCFFGlyph = _interopRequireDefault(require("./cff/parseCFFGlyph"));
var _parseCFFCharset = _interopRequireDefault(require("./cff/parseCFFCharset"));
var _parseCFFEncoding = _interopRequireDefault(require("./cff/parseCFFEncoding"));
var _reader = _interopRequireDefault(require("../reader"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function getOffset(reader, offSize) {
  var v = 0;
  for (var i = 0; i < offSize; i++) {
    v <<= 8;
    v += reader.readUint8();
  }
  return v;
}

function parseCFFHead(reader) {
  var head = {};
  head.startOffset = reader.offset;
  head.endOffset = head.startOffset + 4;
  head.formatMajor = reader.readUint8();
  head.formatMinor = reader.readUint8();
  head.size = reader.readUint8();
  head.offsetSize = reader.readUint8();
  return head;
}

function parseCFFIndex(reader, offset, conversionFn) {
  if (offset) {
    reader.seek(offset);
  }
  var start = reader.offset;
  var offsets = [];
  var objects = [];
  var count = reader.readUint16();
  var i;
  var l;
  if (count !== 0) {
    var offsetSize = reader.readUint8();
    for (i = 0, l = count + 1; i < l; i++) {
      offsets.push(getOffset(reader, offsetSize));
    }
    for (i = 0, l = count; i < l; i++) {
      var value = reader.readBytes(offsets[i + 1] - offsets[i]);
      if (conversionFn) {
        value = conversionFn(value);
      }
      objects.push(value);
    }
  }
  return {
    objects: objects,
    startOffset: start,
    endOffset: reader.offset
  };
}

function calcCFFSubroutineBias(subrs) {
  var bias;
  if (subrs.length < 1240) {
    bias = 107;
  } else if (subrs.length < 33900) {
    bias = 1131;
  } else {
    bias = 32768;
  }
  return bias;
}
var _default = exports.default = _table.default.create('cff', [], {
  read: function read(reader, font) {
    var offset = this.offset;
    reader.seek(offset);
    var head = parseCFFHead(reader);
    var nameIndex = parseCFFIndex(reader, head.endOffset, _string.default.getString);
    var topDictIndex = parseCFFIndex(reader, nameIndex.endOffset);
    var stringIndex = parseCFFIndex(reader, topDictIndex.endOffset, _string.default.getString);
    var globalSubrIndex = parseCFFIndex(reader, stringIndex.endOffset);
    var cff = {
      head: head
    };

    cff.gsubrs = globalSubrIndex.objects;
    cff.gsubrsBias = calcCFFSubroutineBias(globalSubrIndex.objects);

    var dictReader = new _reader.default(new Uint8Array(topDictIndex.objects[0]).buffer);
    var topDict = _parseCFFDict.default.parseTopDict(dictReader, 0, dictReader.length, stringIndex.objects);
    cff.topDict = topDict;

    var privateDictLength = topDict.private[0];
    var privateDict = {};
    var privateDictOffset;
    if (privateDictLength) {
      privateDictOffset = offset + topDict.private[1];
      privateDict = _parseCFFDict.default.parsePrivateDict(reader, privateDictOffset, privateDictLength, stringIndex.objects);
      cff.defaultWidthX = privateDict.defaultWidthX;
      cff.nominalWidthX = privateDict.nominalWidthX;
    } else {
      cff.defaultWidthX = 0;
      cff.nominalWidthX = 0;
    }

    if (privateDict.subrs) {
      var subrOffset = privateDictOffset + privateDict.subrs;
      var subrIndex = parseCFFIndex(reader, subrOffset);
      cff.subrs = subrIndex.objects;
      cff.subrsBias = calcCFFSubroutineBias(cff.subrs);
    } else {
      cff.subrs = [];
      cff.subrsBias = 0;
    }
    cff.privateDict = privateDict;

    var charStringsIndex = parseCFFIndex(reader, offset + topDict.charStrings);
    var nGlyphs = charStringsIndex.objects.length;
    if (topDict.charset < 3) {
      cff.charset = _cffStandardStrings.default;
    } else {
      cff.charset = (0, _parseCFFCharset.default)(reader, offset + topDict.charset, nGlyphs, stringIndex.objects);
    }

    if (topDict.encoding === 0) {
      cff.encoding = _encoding.default.standardEncoding;
    }
    else if (topDict.encoding === 1) {
      cff.encoding = _encoding.default.expertEncoding;
    } else {
      cff.encoding = (0, _parseCFFEncoding.default)(reader, offset + topDict.encoding);
    }
    cff.glyf = [];

    var subset = font.readOptions.subset;
    if (subset && subset.length > 0) {
      var subsetMap = {
        0: true // 设置.notdef
      };
      var codes = font.cmap;

      Object.keys(codes).forEach(function (c) {
        if (subset.indexOf(+c) > -1) {
          var i = codes[c];
          subsetMap[i] = true;
        }
      });
      font.subsetMap = subsetMap;
      Object.keys(subsetMap).forEach(function (i) {
        i = +i;
        var glyf = (0, _parseCFFGlyph.default)(charStringsIndex.objects[i], cff, i);
        glyf.name = cff.charset[i];
        cff.glyf[i] = glyf;
      });
    }
    else {
      for (var i = 0, l = nGlyphs; i < l; i++) {
        var glyf = (0, _parseCFFGlyph.default)(charStringsIndex.objects[i], cff, i);
        glyf.name = cff.charset[i];
        cff.glyf.push(glyf);
      }
    }
    return cff;
  },
  write: function write(writer, font) {
    throw new Error('not support write cff table');
  },
  size: function size(font) {
    throw new Error('not support get cff table size');
  }
});
