"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = parseCFFCharstring;

function parseCFFCharstring(code, font, index) {
  var c1x;
  var c1y;
  var c2x;
  var c2y;
  var contours = [];
  var contour = [];
  var stack = [];
  var glyfs = [];
  var nStems = 0;
  var haveWidth = false;
  var width = font.defaultWidthX;
  var open = false;
  var x = 0;
  var y = 0;
  function lineTo(x, y) {
    contour.push({
      onCurve: true,
      x: x,
      y: y
    });
  }
  function curveTo(c1x, c1y, c2x, c2y, x, y) {
    contour.push({
      x: c1x,
      y: c1y
    });
    contour.push({
      x: c2x,
      y: c2y
    });
    contour.push({
      onCurve: true,
      x: x,
      y: y
    });
  }
  function newContour(x, y) {
    if (open) {
      contours.push(contour);
    }
    contour = [];
    lineTo(x, y);
    open = true;
  }
  function parseStems() {
    var hasWidthArg = stack.length % 2 !== 0;
    if (hasWidthArg && !haveWidth) {
      width = stack.shift() + font.nominalWidthX;
    }
    nStems += stack.length >> 1;
    stack.length = 0;
    haveWidth = true;
  }
  function parse(code) {
    var b1;
    var b2;
    var b3;
    var b4;
    var codeIndex;
    var subrCode;
    var jpx;
    var jpy;
    var c3x;
    var c3y;
    var c4x;
    var c4y;
    var i = 0;
    while (i < code.length) {
      var v = code[i];
      i += 1;
      switch (v) {
        case 1:
          parseStems();
          break;
        case 3:
          parseStems();
          break;
        case 4:
          if (stack.length > 1 && !haveWidth) {
            width = stack.shift() + font.nominalWidthX;
            haveWidth = true;
          }
          y += stack.pop();
          newContour(x, y);
          break;
        case 5:
          while (stack.length > 0) {
            x += stack.shift();
            y += stack.shift();
            lineTo(x, y);
          }
          break;
        case 6:
          while (stack.length > 0) {
            x += stack.shift();
            lineTo(x, y);
            if (stack.length === 0) {
              break;
            }
            y += stack.shift();
            lineTo(x, y);
          }
          break;
        case 7:
          while (stack.length > 0) {
            y += stack.shift();
            lineTo(x, y);
            if (stack.length === 0) {
              break;
            }
            x += stack.shift();
            lineTo(x, y);
          }
          break;
        case 8:
          while (stack.length > 0) {
            c1x = x + stack.shift();
            c1y = y + stack.shift();
            c2x = c1x + stack.shift();
            c2y = c1y + stack.shift();
            x = c2x + stack.shift();
            y = c2y + stack.shift();
            curveTo(c1x, c1y, c2x, c2y, x, y);
          }
          break;
        case 10:
          codeIndex = stack.pop() + font.subrsBias;
          subrCode = font.subrs[codeIndex];
          if (subrCode) {
            parse(subrCode);
          }
          break;
        case 11:
          return;
        case 12:
          v = code[i];
          i += 1;
          switch (v) {
            case 35:
              c1x = x + stack.shift(); // dx1
              c1y = y + stack.shift(); // dy1
              c2x = c1x + stack.shift(); // dx2
              c2y = c1y + stack.shift(); // dy2
              jpx = c2x + stack.shift(); // dx3
              jpy = c2y + stack.shift(); // dy3
              c3x = jpx + stack.shift(); // dx4
              c3y = jpy + stack.shift(); // dy4
              c4x = c3x + stack.shift(); // dx5
              c4y = c3y + stack.shift(); // dy5
              x = c4x + stack.shift(); // dx6
              y = c4y + stack.shift(); // dy6
              stack.shift(); // flex depth
              curveTo(c1x, c1y, c2x, c2y, jpx, jpy);
              curveTo(c3x, c3y, c4x, c4y, x, y);
              break;
            case 34:
              c1x = x + stack.shift(); // dx1
              c1y = y; // dy1
              c2x = c1x + stack.shift(); // dx2
              c2y = c1y + stack.shift(); // dy2
              jpx = c2x + stack.shift(); // dx3
              jpy = c2y; // dy3
              c3x = jpx + stack.shift(); // dx4
              c3y = c2y; // dy4
              c4x = c3x + stack.shift(); // dx5
              c4y = y; // dy5
              x = c4x + stack.shift(); // dx6
              curveTo(c1x, c1y, c2x, c2y, jpx, jpy);
              curveTo(c3x, c3y, c4x, c4y, x, y);
              break;
            case 36:
              c1x = x + stack.shift(); // dx1
              c1y = y + stack.shift(); // dy1
              c2x = c1x + stack.shift(); // dx2
              c2y = c1y + stack.shift(); // dy2
              jpx = c2x + stack.shift(); // dx3
              jpy = c2y; // dy3
              c3x = jpx + stack.shift(); // dx4
              c3y = c2y; // dy4
              c4x = c3x + stack.shift(); // dx5
              c4y = c3y + stack.shift(); // dy5
              x = c4x + stack.shift(); // dx6
              curveTo(c1x, c1y, c2x, c2y, jpx, jpy);
              curveTo(c3x, c3y, c4x, c4y, x, y);
              break;
            case 37:
              c1x = x + stack.shift(); // dx1
              c1y = y + stack.shift(); // dy1
              c2x = c1x + stack.shift(); // dx2
              c2y = c1y + stack.shift(); // dy2
              jpx = c2x + stack.shift(); // dx3
              jpy = c2y + stack.shift(); // dy3
              c3x = jpx + stack.shift(); // dx4
              c3y = jpy + stack.shift(); // dy4
              c4x = c3x + stack.shift(); // dx5
              c4y = c3y + stack.shift(); // dy5
              if (Math.abs(c4x - x) > Math.abs(c4y - y)) {
                x = c4x + stack.shift();
              } else {
                y = c4y + stack.shift();
              }
              curveTo(c1x, c1y, c2x, c2y, jpx, jpy);
              curveTo(c3x, c3y, c4x, c4y, x, y);
              break;
            default:
              console.warn('Glyph ' + index + ': unknown operator ' + (1200 + v));
              stack.length = 0;
          }
          break;
        case 14:
          if (stack.length === 1 && !haveWidth) {
            width = stack.shift() + font.nominalWidthX;
            haveWidth = true;
          } else if (stack.length === 4) {
            glyfs[1] = {
              glyphIndex: font.charset.indexOf(font.encoding[stack.pop()]),
              transform: {
                a: 1,
                b: 0,
                c: 0,
                d: 1,
                e: 0,
                f: 0
              }
            };
            glyfs[0] = {
              glyphIndex: font.charset.indexOf(font.encoding[stack.pop()]),
              transform: {
                a: 1,
                b: 0,
                c: 0,
                d: 1,
                e: 0,
                f: 0
              }
            };
            glyfs[1].transform.f = stack.pop();
            glyfs[1].transform.e = stack.pop();
          } else if (stack.length === 5) {
            if (!haveWidth) {
              width = stack.shift() + font.nominalWidthX;
            }
            haveWidth = true;
            glyfs[1] = {
              glyphIndex: font.charset.indexOf(font.encoding[stack.pop()]),
              transform: {
                a: 1,
                b: 0,
                c: 0,
                d: 1,
                e: 0,
                f: 0
              }
            };
            glyfs[0] = {
              glyphIndex: font.charset.indexOf(font.encoding[stack.pop()]),
              transform: {
                a: 1,
                b: 0,
                c: 0,
                d: 1,
                e: 0,
                f: 0
              }
            };
            glyfs[1].transform.f = stack.pop();
            glyfs[1].transform.e = stack.pop();
          }
          if (open) {
            contours.push(contour);
            open = false;
          }
          break;
        case 18:
          parseStems();
          break;
        case 19: // hintmask
        case 20:
          parseStems();
          i += nStems + 7 >> 3;
          break;
        case 21:
          if (stack.length > 2 && !haveWidth) {
            width = stack.shift() + font.nominalWidthX;
            haveWidth = true;
          }
          y += stack.pop();
          x += stack.pop();
          newContour(x, y);
          break;
        case 22:
          if (stack.length > 1 && !haveWidth) {
            width = stack.shift() + font.nominalWidthX;
            haveWidth = true;
          }
          x += stack.pop();
          newContour(x, y);
          break;
        case 23:
          parseStems();
          break;
        case 24:
          while (stack.length > 2) {
            c1x = x + stack.shift();
            c1y = y + stack.shift();
            c2x = c1x + stack.shift();
            c2y = c1y + stack.shift();
            x = c2x + stack.shift();
            y = c2y + stack.shift();
            curveTo(c1x, c1y, c2x, c2y, x, y);
          }
          x += stack.shift();
          y += stack.shift();
          lineTo(x, y);
          break;
        case 25:
          while (stack.length > 6) {
            x += stack.shift();
            y += stack.shift();
            lineTo(x, y);
          }
          c1x = x + stack.shift();
          c1y = y + stack.shift();
          c2x = c1x + stack.shift();
          c2y = c1y + stack.shift();
          x = c2x + stack.shift();
          y = c2y + stack.shift();
          curveTo(c1x, c1y, c2x, c2y, x, y);
          break;
        case 26:
          if (stack.length % 2) {
            x += stack.shift();
          }
          while (stack.length > 0) {
            c1x = x;
            c1y = y + stack.shift();
            c2x = c1x + stack.shift();
            c2y = c1y + stack.shift();
            x = c2x;
            y = c2y + stack.shift();
            curveTo(c1x, c1y, c2x, c2y, x, y);
          }
          break;
        case 27:
          if (stack.length % 2) {
            y += stack.shift();
          }
          while (stack.length > 0) {
            c1x = x + stack.shift();
            c1y = y;
            c2x = c1x + stack.shift();
            c2y = c1y + stack.shift();
            x = c2x + stack.shift();
            y = c2y;
            curveTo(c1x, c1y, c2x, c2y, x, y);
          }
          break;
        case 28:
          b1 = code[i];
          b2 = code[i + 1];
          stack.push((b1 << 24 | b2 << 16) >> 16);
          i += 2;
          break;
        case 29:
          codeIndex = stack.pop() + font.gsubrsBias;
          subrCode = font.gsubrs[codeIndex];
          if (subrCode) {
            parse(subrCode);
          }
          break;
        case 30:
          while (stack.length > 0) {
            c1x = x;
            c1y = y + stack.shift();
            c2x = c1x + stack.shift();
            c2y = c1y + stack.shift();
            x = c2x + stack.shift();
            y = c2y + (stack.length === 1 ? stack.shift() : 0);
            curveTo(c1x, c1y, c2x, c2y, x, y);
            if (stack.length === 0) {
              break;
            }
            c1x = x + stack.shift();
            c1y = y;
            c2x = c1x + stack.shift();
            c2y = c1y + stack.shift();
            y = c2y + stack.shift();
            x = c2x + (stack.length === 1 ? stack.shift() : 0);
            curveTo(c1x, c1y, c2x, c2y, x, y);
          }
          break;
        case 31:
          while (stack.length > 0) {
            c1x = x + stack.shift();
            c1y = y;
            c2x = c1x + stack.shift();
            c2y = c1y + stack.shift();
            y = c2y + stack.shift();
            x = c2x + (stack.length === 1 ? stack.shift() : 0);
            curveTo(c1x, c1y, c2x, c2y, x, y);
            if (stack.length === 0) {
              break;
            }
            c1x = x;
            c1y = y + stack.shift();
            c2x = c1x + stack.shift();
            c2y = c1y + stack.shift();
            x = c2x + stack.shift();
            y = c2y + (stack.length === 1 ? stack.shift() : 0);
            curveTo(c1x, c1y, c2x, c2y, x, y);
          }
          break;
        default:
          if (v < 32) {
            console.warn('Glyph ' + index + ': unknown operator ' + v);
          } else if (v < 247) {
            stack.push(v - 139);
          } else if (v < 251) {
            b1 = code[i];
            i += 1;
            stack.push((v - 247) * 256 + b1 + 108);
          } else if (v < 255) {
            b1 = code[i];
            i += 1;
            stack.push(-(v - 251) * 256 - b1 - 108);
          } else {
            b1 = code[i];
            b2 = code[i + 1];
            b3 = code[i + 2];
            b4 = code[i + 3];
            i += 4;
            stack.push((b1 << 24 | b2 << 16 | b3 << 8 | b4) / 65536);
          }
      }
    }
  }
  parse(code);
  var glyf = {
    contours: contours.map(function (contour) {
      var last = contour.length - 1;
      if (contour[0].x === contour[last].x && contour[0].y === contour[last].y) {
        contour.splice(last, 1);
      }
      return contour;
    }),
    advanceWidth: width
  };
  if (glyfs.length) {
    glyf.compound = true;
    glyf.glyfs = glyfs;
  }
  return glyf;
}
