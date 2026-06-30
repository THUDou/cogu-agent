"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = write;
var _componentFlag = _interopRequireDefault(require("../../enum/componentFlag"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

function write(writer, ttf) {
  var hinting = ttf.writeOptions ? ttf.writeOptions.hinting : false;
  var writeZeroContoursGlyfData = ttf.writeOptions ? ttf.writeOptions.writeZeroContoursGlyfData : false;
  ttf.glyf.forEach(function (glyf, index) {
    if (!glyf.compound && !writeZeroContoursGlyfData && (!glyf.contours || !glyf.contours.length)) {
      return;
    }
    writer.writeInt16(glyf.compound ? -1 : (glyf.contours || []).length);
    writer.writeInt16(glyf.xMin);
    writer.writeInt16(glyf.yMin);
    writer.writeInt16(glyf.xMax);
    writer.writeInt16(glyf.yMax);
    var i;
    var l;
    var flags;

    if (glyf.compound) {
      for (i = 0, l = glyf.glyfs.length; i < l; i++) {
        var g = glyf.glyfs[i];
        flags = g.points ? 0 : _componentFlag.default.ARGS_ARE_XY_VALUES + _componentFlag.default.ROUND_XY_TO_GRID; // xy values

        if (i < l - 1) {
          flags += _componentFlag.default.MORE_COMPONENTS;
        }

        flags += g.useMyMetrics ? _componentFlag.default.USE_MY_METRICS : 0;
        flags += g.overlapCompound ? _componentFlag.default.OVERLAP_COMPOUND : 0;
        var transform = g.transform;
        var a = transform.a;
        var b = transform.b;
        var c = transform.c;
        var d = transform.d;
        var e = g.points ? g.points[0] : transform.e;
        var f = g.points ? g.points[1] : transform.f;

        if (e < 0 || e > 0x7F || f < 0 || f > 0x7F) {
          flags += _componentFlag.default.ARG_1_AND_2_ARE_WORDS;
        }
        if (b || c) {
          flags += _componentFlag.default.WE_HAVE_A_TWO_BY_TWO;
        } else if ((a !== 1 || d !== 1) && a === d) {
          flags += _componentFlag.default.WE_HAVE_A_SCALE;
        } else if (a !== 1 || d !== 1) {
          flags += _componentFlag.default.WE_HAVE_AN_X_AND_Y_SCALE;
        }
        writer.writeUint16(flags);
        writer.writeUint16(g.glyphIndex);
        if (_componentFlag.default.ARG_1_AND_2_ARE_WORDS & flags) {
          writer.writeInt16(e);
          writer.writeInt16(f);
        } else {
          writer.writeUint8(e);
          writer.writeUint8(f);
        }
        if (_componentFlag.default.WE_HAVE_A_SCALE & flags) {
          writer.writeInt16(Math.round(a * 16384));
        } else if (_componentFlag.default.WE_HAVE_AN_X_AND_Y_SCALE & flags) {
          writer.writeInt16(Math.round(a * 16384));
          writer.writeInt16(Math.round(d * 16384));
        } else if (_componentFlag.default.WE_HAVE_A_TWO_BY_TWO & flags) {
          writer.writeInt16(Math.round(a * 16384));
          writer.writeInt16(Math.round(b * 16384));
          writer.writeInt16(Math.round(c * 16384));
          writer.writeInt16(Math.round(d * 16384));
        }
      }
    } else {
      var endPtsOfContours = -1;
      (glyf.contours || []).forEach(function (contour) {
        endPtsOfContours += contour.length;
        writer.writeUint16(endPtsOfContours);
      });

      if (hinting && glyf.instructions) {
        var instructions = glyf.instructions;
        writer.writeUint16(instructions.length);
        for (i = 0, l = instructions.length; i < l; i++) {
          writer.writeUint8(instructions[i]);
        }
      } else {
        writer.writeUint16(0);
      }

      flags = ttf.support.glyf[index].flags || [];
      for (i = 0, l = flags.length; i < l; i++) {
        writer.writeUint8(flags[i]);
      }
      var xCoord = ttf.support.glyf[index].xCoord || [];
      for (i = 0, l = xCoord.length; i < l; i++) {
        if (0 <= xCoord[i] && xCoord[i] <= 0xFF) {
          writer.writeUint8(xCoord[i]);
        } else {
          writer.writeInt16(xCoord[i]);
        }
      }
      var yCoord = ttf.support.glyf[index].yCoord || [];
      for (i = 0, l = yCoord.length; i < l; i++) {
        if (0 <= yCoord[i] && yCoord[i] <= 0xFF) {
          writer.writeUint8(yCoord[i]);
        } else {
          writer.writeInt16(yCoord[i]);
        }
      }
    }

    var glyfSize = ttf.support.glyf[index].glyfSize;
    if (glyfSize % 4) {
      writer.writeEmpty(4 - glyfSize % 4);
    }
  });
  return writer;
}
