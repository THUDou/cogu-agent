
import pathAdjust from '../../graphics/pathAdjust';
import pathCeil from '../../graphics/pathCeil';
import {computePathBox} from '../../graphics/computeBoundingBox';


export default function glyfAdjust(g, scaleX = 1, scaleY = 1, offsetX = 0, offsetY = 0, useCeil = true) {

    if (g.contours && g.contours.length) {
        if (scaleX !== 1 || scaleY !== 1) {
            g.contours.forEach((contour) => {
                pathAdjust(contour, scaleX, scaleY);
            });
        }

        if (offsetX !== 0 || offsetY !== 0) {
            g.contours.forEach((contour) => {
                pathAdjust(contour, 1, 1, offsetX, offsetY);
            });
        }

        if (false !== useCeil) {
            g.contours.forEach((contour) => {
                pathCeil(contour);
            });
        }
    }

    const advanceWidth = g.advanceWidth;
    if (
        undefined === g.xMin
        || undefined === g.yMax
        || undefined === g.leftSideBearing
        || undefined === g.advanceWidth
    ) {
        let bound;
        if (g.contours && g.contours.length) {
            bound = computePathBox.apply(this, g.contours);
        }
        else {
            bound = {
                x: 0,
                y: 0,
                width: 0,
                height: 0
            };
        }

        g.xMin = bound.x;
        g.xMax = bound.x + bound.width;
        g.yMin = bound.y;
        g.yMax = bound.y + bound.height;

        g.leftSideBearing = g.xMin;

        if (undefined !== advanceWidth) {
            g.advanceWidth = Math.round(advanceWidth * scaleX + offsetX);
        }
        else {
            g.advanceWidth = g.xMax + Math.abs(g.xMin);
        }
    }
    else {
        g.xMin = Math.round(g.xMin * scaleX + offsetX);
        g.xMax = Math.round(g.xMax * scaleX + offsetX);
        g.yMin = Math.round(g.yMin * scaleY + offsetY);
        g.yMax = Math.round(g.yMax * scaleY + offsetY);
        g.leftSideBearing = Math.round(g.leftSideBearing * scaleX + offsetX);
        g.advanceWidth = Math.round(advanceWidth * scaleX + offsetX);
    }

    return g;
}
