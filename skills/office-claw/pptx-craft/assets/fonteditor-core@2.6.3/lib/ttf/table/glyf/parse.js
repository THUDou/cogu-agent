"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = parseGlyf;
var _glyFlag = _interopRequireDefault(require("../../enum/glyFlag"));
var _componentFlag = _interopRequireDefault(require("../../enum/componentFlag"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

var MAX_INSTRUCTION_LENGTH = 5000; // 设置instructions阈值防止读取错误
var MAX_NUMBER_OF_COORDINATES = 20000; // 设置坐标最大个数阈值，防止glyf读取错误

function parseSimpleGlyf(reader, glyf) {
  var offset = reader.offset;

  var numberOfCoordinates = glyf.endPtsOfContours[glyf.endPtsOfContours.length - 1] + 1;

  if (numberOfCoordinates > MAX_NUMBER_OF_COORDINATES) {
    console.warn('error read glyf coordinates:' + offset);
    return glyf;
  }

  var i;
  var length;
  var flags = [];
  var flag;
  i = 0;
  while (i < numberOfCoordinates) {
    flag = reader.readUint8();
    flags.push(flag);
    i++;

    if (flag & _glyFlag.default.REPEAT && i < numberOfCoordinates) {
      var repeat = reader.readUint8();
      for (var j = 0; j < repeat; j++) {
        flags.push(flag);
        i++;
      }
    }
  }

  var coordinates = [];
  var xCoordinates = [];
  var prevX = 0;
  var x;
  for (i = 0, length = flags.length; i < length; ++i) {
    x = 0;
    flag = flags[i];

    if (flag & _glyFlag.default.XSHORT) {
      x = reader.readUint8();

      x = flag & _glyFlag.default.XSAME ? x : -1 * x;
    }
    else if (flag & _glyFlag.default.XSAME) {
      x = 0;
    }
    else {
      x = reader.readInt16();
    }
    prevX += x;
    xCoordinates[i] = prevX;
    coordinates[i] = {
      x: prevX,
      y: 0
    };
    if (flag & _glyFlag.default.ONCURVE) {
      coordinates[i].onCurve = true;
    }
  }
  var yCoordinates = [];
  var prevY = 0;
  var y;
  for (i = 0, length = flags.length; i < length; i++) {
    y = 0;
    flag = flags[i];
    if (flag & _glyFlag.default.YSHORT) {
      y = reader.readUint8();
      y = flag & _glyFlag.default.YSAME ? y : -1 * y;
    } else if (flag & _glyFlag.default.YSAME) {
      y = 0;
    } else {
      y = reader.readInt16();
    }
    prevY += y;
    yCoordinates[i] = prevY;
    if (coordinates[i]) {
      coordinates[i].y = prevY;
    }
  }

  if (coordinates.length) {
    var endPtsOfContours = glyf.endPtsOfContours;
    var contours = [];
    contours.push(coordinates.slice(0, endPtsOfContours[0] + 1));
    for (i = 1, length = endPtsOfContours.length; i < length; i++) {
      contours.push(coordinates.slice(endPtsOfContours[i - 1] + 1, endPtsOfContours[i] + 1));
    }
    glyf.contours = contours;
  }
  return glyf;
}

function parseCompoundGlyf(reader, glyf) {
  glyf.compound = true;
  glyf.glyfs = [];
  var flags;
  var g;

  do {
    flags = reader.readUint16();
    g = {};
    g.flags = flags;
    g.glyphIndex = reader.readUint16();
    var arg1 = 0;
    var arg2 = 0;
    var scaleX = 16384;
    var scaleY = 16384;
    var scale01 = 0;
    var scale10 = 0;
    if (_componentFlag.default.ARG_1_AND_2_ARE_WORDS & flags) {
      arg1 = reader.readInt16();
      arg2 = reader.readInt16();
    } else {
      arg1 = reader.readInt8();
      arg2 = reader.readInt8();
    }
    if (_componentFlag.default.ROUND_XY_TO_GRID & flags) {
      arg1 = Math.round(arg1);
      arg2 = Math.round(arg2);
    }
    if (_componentFlag.default.WE_HAVE_A_SCALE & flags) {
      scaleX = reader.readInt16();
      scaleY = scaleX;
    } else if (_componentFlag.default.WE_HAVE_AN_X_AND_Y_SCALE & flags) {
      scaleX = reader.readInt16();
      scaleY = reader.readInt16();
    } else if (_componentFlag.default.WE_HAVE_A_TWO_BY_TWO & flags) {
      scaleX = reader.readInt16();
      scale01 = reader.readInt16();
      scale10 = reader.readInt16();
      scaleY = reader.readInt16();
    }
    if (_componentFlag.default.ARGS_ARE_XY_VALUES & flags) {
      g.useMyMetrics = !!flags & _componentFlag.default.USE_MY_METRICS;
      g.overlapCompound = !!flags & _componentFlag.default.OVERLAP_COMPOUND;
      g.transform = {
        a: Math.round(10000 * scaleX / 16384) / 10000,
        b: Math.round(10000 * scale01 / 16384) / 10000,
        c: Math.round(10000 * scale10 / 16384) / 10000,
        d: Math.round(10000 * scaleY / 16384) / 10000,
        e: arg1,
        f: arg2
      };
    } else {
      g.points = [arg1, arg2];
      g.transform = {
        a: Math.round(10000 * scaleX / 16384) / 10000,
        b: Math.round(10000 * scale01 / 16384) / 10000,
        c: Math.round(10000 * scale10 / 16384) / 10000,
        d: Math.round(10000 * scaleY / 16384) / 10000,
        e: 0,
        f: 0
      };
    }
    glyf.glyfs.push(g);
  } while (_componentFlag.default.MORE_COMPONENTS & flags);
  if (_componentFlag.default.WE_HAVE_INSTRUCTIONS & flags) {
    var length = reader.readUint16();
    if (length < MAX_INSTRUCTION_LENGTH) {
      var instructions = [];
      for (var i = 0; i < length; ++i) {
        instructions.push(reader.readUint8());
      }
      glyf.instructions = instructions;
    } else {
      console.warn(length);
    }
  }
  return glyf;
}

function parseGlyf(reader, ttf, offset) {
  if (null != offset) {
    reader.seek(offset);
  }
  var glyf = {};
  var i;
  var length;
  var instructions;

  var numberOfContours = reader.readInt16();
  glyf.xMin = reader.readInt16();
  glyf.yMin = reader.readInt16();
  glyf.xMax = reader.readInt16();
  glyf.yMax = reader.readInt16();

  if (numberOfContours >= 0) {
    glyf.endPtsOfContours = [];
    if (numberOfContours > 0) {
      for (i = 0; i < numberOfContours; i++) {
        glyf.endPtsOfContours.push(reader.readUint16());
      }
    } else {
      delete glyf.xMin;
      delete glyf.yMin;
      delete glyf.xMax;
      delete glyf.yMax;
    }

    length = reader.readUint16();
    if (length) {
      if (length < MAX_INSTRUCTION_LENGTH) {
        instructions = [];
        for (i = 0; i < length; ++i) {
          instructions.push(reader.readUint8());
        }
        glyf.instructions = instructions;
      } else {
        console.warn(length);
      }
    }
    parseSimpleGlyf(reader, glyf);
    delete glyf.endPtsOfContours;
  } else {
    parseCompoundGlyf(reader, glyf);
  }
  return glyf;
}
