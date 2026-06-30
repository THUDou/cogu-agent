import {computePath} from './computeBoundingBox';

export default function pathSkewY(contour, angle) {
    angle = angle === undefined ? 0 : angle;
    const x = computePath(contour).x;
    const tan = Math.tan(angle);
    let p;
    for (let i = 0, l = contour.length; i < l; i++) {
        p = contour[i];
        p.y += tan * (p.x - x);
    }
    return contour;
}
