
import contours2svg from './contours2svg';
import transformGlyfContours from './transformGlyfContours';

export default function glyf2svg(glyf, ttf) {

    if (!glyf) {
        return '';
    }

    const pathArray = [];

    if (!glyf.compound) {
        if (glyf.contours && glyf.contours.length) {
            pathArray.push(contours2svg(glyf.contours));
        }

    }
    else {
        const contours = transformGlyfContours(glyf, ttf);
        if (contours && contours.length) {
            pathArray.push(contours2svg(contours));
        }
    }

    return pathArray.join(' ');
}
