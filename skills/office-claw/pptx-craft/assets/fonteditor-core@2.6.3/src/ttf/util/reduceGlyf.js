
import reducePath from '../../graphics/reducePath';

export default function reduceGlyf(glyf) {

    const contours = glyf.contours;
    let contour;
    for (let j = contours.length - 1; j >= 0; j--) {
        contour = reducePath(contours[j]);

        if (contour.length <= 2) {
            contours.splice(j, 1);
            continue;
        }
    }

    if (0 === glyf.contours.length) {
        delete glyf.contours;
    }

    return glyf;
}
