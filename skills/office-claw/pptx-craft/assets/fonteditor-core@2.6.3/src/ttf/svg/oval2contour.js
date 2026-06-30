
import {computePath} from '../../graphics/computeBoundingBox';
import pathAdjust from '../../graphics/pathAdjust';
import circlePath from '../../graphics/path/circle';
import {clone} from '../../common/lang';

export default function oval2contour(cx, cy, rx, ry) {

    if (undefined === ry) {
        ry = rx;
    }

    const bound = computePath(circlePath);
    const scaleX = (+rx) * 2 / bound.width;
    const scaleY = (+ry) * 2 / bound.height;
    const centerX = bound.width * scaleX / 2;
    const centerY = bound.height * scaleY / 2;
    const contour = clone(circlePath);
    pathAdjust(contour, scaleX, scaleY);
    pathAdjust(contour, 1, 1, +cx - centerX, +cy - centerY);

    return contour;
}
