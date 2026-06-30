

import transformGlyfContours from './transformGlyfContours';
import compound2simple from './compound2simple';

export default function compound2simpleglyf(glyf, ttf, recrusive) {

    let glyfIndex;
    if (typeof glyf === 'number') {
        glyfIndex = glyf;
        glyf = ttf.glyf[glyfIndex];
    }
    else {
        glyfIndex = ttf.glyf.indexOf(glyf);
        if (-1 === glyfIndex) {
            return glyf;
        }
    }

    if (!glyf.compound || !glyf.glyfs) {
        return glyf;
    }

    const contoursList = {};
    transformGlyfContours(glyf, ttf, contoursList, glyfIndex);

    if (recrusive) {
        Object.keys(contoursList).forEach((index) => {
            compound2simple(ttf.glyf[index], contoursList[index]);
        });
    }
    else {
        compound2simple(glyf, contoursList[glyfIndex]);
    }

    return glyf;
}
