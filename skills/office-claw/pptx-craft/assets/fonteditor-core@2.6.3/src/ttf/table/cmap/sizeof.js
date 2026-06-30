
function encodeDelta(delta) {
    return delta > 0x7FFF
        ? delta - 0x10000
        : (delta < -0x7FFF ? delta + 0x10000 : delta);
}

function getSegments(glyfUnicodes, bound) {

    let prevGlyph = null;
    const result = [];
    let segment = {};

    glyfUnicodes.forEach((glyph) => {

        if (bound === undefined || glyph.unicode <= bound) {
            if (prevGlyph === null
                || glyph.unicode !== prevGlyph.unicode + 1
                || glyph.id !== prevGlyph.id + 1
            ) {
                if (prevGlyph !== null) {
                    segment.end = prevGlyph.unicode;
                    result.push(segment);
                    segment = {
                        start: glyph.unicode,
                        startId: glyph.id,
                        delta: encodeDelta(glyph.id - glyph.unicode)
                    };
                }
                else {
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
    const unicodes = [];
    glyfUnicodes.forEach((u) => {
        if (u.unicode !== undefined && u.unicode < 256) {
            unicodes.push([u.unicode, u.id]);
        }
    });

    unicodes.sort((a, b) => a[0] - b[0]);

    return unicodes;
}

export default function sizeof(ttf) {
    ttf.support.cmap = {};
    let glyfUnicodes = [];
    ttf.glyf.forEach((glyph, index) => {

        let unicodes = glyph.unicode;

        if (typeof glyph.unicode === 'number') {
            unicodes = [glyph.unicode];
        }

        if (unicodes && unicodes.length) {
            unicodes.forEach((unicode) => {
                glyfUnicodes.push({
                    unicode,
                    id: unicode !== 0xFFFF ? index : 0
                });
            });
        }

    });

    glyfUnicodes = glyfUnicodes.sort((a, b) => a.unicode - b.unicode);

    ttf.support.cmap.unicodes = glyfUnicodes;

    const unicodes2Bytes = glyfUnicodes;

    ttf.support.cmap.format4Segments = getSegments(unicodes2Bytes, 0xFFFF);
    ttf.support.cmap.format4Size = 24
        + ttf.support.cmap.format4Segments.length * 8;

    ttf.support.cmap.format0Segments = getFormat0Segment(glyfUnicodes);
    ttf.support.cmap.format0Size = 262;

    const hasGLyphsOver2Bytes = unicodes2Bytes.some((glyph) => glyph.unicode > 0xFFFF);

    if (hasGLyphsOver2Bytes) {
        ttf.support.cmap.hasGLyphsOver2Bytes = hasGLyphsOver2Bytes;

        const unicodes4Bytes = glyfUnicodes;

        ttf.support.cmap.format12Segments = getSegments(unicodes4Bytes);
        ttf.support.cmap.format12Size = 16
            + ttf.support.cmap.format12Segments.length * 12;
    }

    const size = 4 + (hasGLyphsOver2Bytes ? 32 : 24) // cmap header
        + ttf.support.cmap.format0Size // format 0
        + ttf.support.cmap.format4Size // format 4
        + (hasGLyphsOver2Bytes ? ttf.support.cmap.format12Size : 0); // format 12

    return size;
}
