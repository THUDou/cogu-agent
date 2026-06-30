
import pathCeil from '../../graphics/pathCeil';
import pathTransform from '../../graphics/pathTransform';
import {clone} from '../../common/lang';


export default function transformGlyfContours(glyf, ttf, contoursList = {}, glyfIndex) {

    if (!glyf.glyfs) {
        return glyf;
    }

    const compoundContours = [];
    glyf.glyfs.forEach(g => {
        const glyph = ttf.glyf[g.glyphIndex];

        if (!glyph || glyph === glyf) {
            return;
        }

        if (glyph.compound && !contoursList[g.glyphIndex]) {
            transformGlyfContours(glyph, ttf, contoursList, g.glyphIndex);
        }

        const contours = clone(glyph.compound ? (contoursList[g.glyphIndex] || []) : glyph.contours);
        const transform = g.transform;
        for (let i = 0, l = contours.length; i < l; i++) {
            pathTransform(
                contours[i],
                transform.a,
                transform.b,
                transform.c,
                transform.d,
                transform.e,
                transform.f
            );
            compoundContours.push(pathCeil(contours[i]));
        }
    });

    if (null != glyfIndex) {
        contoursList[glyfIndex] = compoundContours;
    }

    return compoundContours;
}
