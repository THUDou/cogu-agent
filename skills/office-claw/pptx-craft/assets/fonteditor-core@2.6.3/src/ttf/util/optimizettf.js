
import reduceGlyf from './reduceGlyf';
import pathCeil from '../../graphics/pathCeil';

export default function optimizettf(ttf) {

    const checkUnicodeRepeat = {}; // 检查是否有重复代码点
    const repeatList = [];

    ttf.glyf.forEach((glyf, index) => {
        if (glyf.unicode) {
            glyf.unicode = glyf.unicode.sort();

            glyf.unicode.sort((a, b) => a - b).forEach((u) => {
                if (checkUnicodeRepeat[u]) {
                    repeatList.push(index);
                }
                else {
                    checkUnicodeRepeat[u] = true;
                }
            });

        }

        if (!glyf.compound && glyf.contours) {
            glyf.contours.forEach((contour) => {
                pathCeil(contour);
            });
            reduceGlyf(glyf);
        }

        glyf.xMin = Math.round(glyf.xMin || 0);
        glyf.xMax = Math.round(glyf.xMax || 0);
        glyf.yMin = Math.round(glyf.yMin || 0);
        glyf.yMax = Math.round(glyf.yMax || 0);
        glyf.leftSideBearing = Math.round(glyf.leftSideBearing || 0);
        glyf.advanceWidth = Math.round(glyf.advanceWidth || 0);
    });

    if (!ttf.glyf.some((a) => a.compound)) {
        ttf.glyf = ttf.glyf.filter((glyf, index) => index === 0 || glyf.contours && glyf.contours.length);
    }

    if (!repeatList.length) {
        return true;
    }

    return {
        repeat: repeatList
    };
}
