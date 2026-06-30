
import contour2svg from './contour2svg';

export default function contours2svg(contours, precision) {

    if (!contours.length) {
        return '';
    }

    return contours.map((contour) => contour2svg(contour, precision)).join('');
}
