"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = sizeof;

function encodeDelta(delta) {
  return delta > 0x7FFF ? delta - 0x10000 : delta < -0x7FFF ? delta + 0x10000 : delta;
}

function getSegments(glyfUnicodes, bound) {
  var prevGlyph = null;
  var result = [];
  var segment = {};
  glyfUnicodes.forEach(function (glyph) {
    if (bound === undefined || glyph.unicode <= bound) {
      if (prevGlyph === null || glyph.unicode !== prevGlyph.unicode + 1 || glyph.id !== prevGlyph.id + 1) {
        if (prevGlyph !== null) {
          segment.end = prevGlyph.unicode;
          result.push(segment);
          segment = {
            start: glyph.unicode,
            startId: glyph.id,
            delta: encodeDelta(glyph.id - glyph.unicode)
          };
        } else {
          segment.start = glyph.unicode;
          segment.startId = glyph.id;
          segment.delta = encodeDelta(glyph.id - glyph.unicode);
        }
      }
      prevGlyph = glyph;
    }
  });

  if (prevGlyph !== null) {
    segment.end = prevGlyph.unicode;
    result.push(segment);
  }

  return result;
}

function getFormat0Segment(glyfUnicodes) {
  var unicodes = [];
  glyfUnicodes.forEach(function (u) {
    if (u.unicode !== undefined && u.unicode < 256) {
      unicodes.push([u.unicode, u.id]);
    }
  });

  unicodes.sort(function (a, b) {
    return a[0] - b[0];
  });
  return unicodes;
}

function sizeof(ttf) {
  ttf.support.cmap = {};
  var glyfUnicodes = [];
  ttf.glyf.forEach(function (glyph, index) {
    var unicodes = glyph.unicode;
    if (typeof glyph.unicode === 'number') {
      unicodes = [glyph.unicode];
    }
    if (unicodes && unicodes.length) {
      unicodes.forEach(function (unicode) {
        glyfUnicodes.push({
          unicode: unicode,
          id: unicode !== 0xFFFF ? index : 0
        });
      });
    }
  });
  glyfUnicodes = glyfUnicodes.sort(function (a, b) {
    return a.unicode - b.unicode;
  });
  ttf.support.cmap.unicodes = glyfUnicodes;
  var unicodes2Bytes = glyfUnicodes;
  ttf.support.cmap.format4Segments = getSegments(unicodes2Bytes, 0xFFFF);
  ttf.support.cmap.format4Size = 24 + ttf.support.cmap.format4Segments.length * 8;
  ttf.support.cmap.format0Segments = getFormat0Segment(glyfUnicodes);
  ttf.support.cmap.format0Size = 262;

  var hasGLyphsOver2Bytes = unicodes2Bytes.some(function (glyph) {
    return glyph.unicode > 0xFFFF;
  });
  if (hasGLyphsOver2Bytes) {
    ttf.support.cmap.hasGLyphsOver2Bytes = hasGLyphsOver2Bytes;
    var unicodes4Bytes = glyfUnicodes;
    ttf.support.cmap.format12Segments = getSegments(unicodes4Bytes);
    ttf.support.cmap.format12Size = 16 + ttf.support.cmap.format12Segments.length * 12;
  }
  var size = 4 + (hasGLyphsOver2Bytes ? 32 : 24) // cmap header
  + ttf.support.cmap.format0Size // format 0
  + ttf.support.cmap.format4Size // format 4
  + (hasGLyphsOver2Bytes ? ttf.support.cmap.format12Size : 0); // format 12

  return size;
}
