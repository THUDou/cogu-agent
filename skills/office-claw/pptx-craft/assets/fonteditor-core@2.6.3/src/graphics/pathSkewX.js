import {computePath} from './computeBoundingBox';

export default function pathSkewX(contour, angle) {
    angle = angle === undefined ? 0 : angle;
    const y = computePath(contour).y;
    const tan = Math.tan(angle);
    let p;
    for (let i = 0, l = contour.length; i < l; i++) {
        p = contour[i];
        p.x += tan * (p.y - y);
    }
    return contour;
}
