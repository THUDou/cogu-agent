
import bezierCubic2Q2 from '../../math/bezierCubic2Q2';
import pathCeil from '../../graphics/pathCeil';

function transformContour(otfContour) {
    const contour = [];
    let prevPoint;
    let curPoint;
    let nextPoint;
    let nextNextPoint;

    contour.push(prevPoint = otfContour[0]);
    for (let i = 1, l = otfContour.length; i < l; i++) {
        curPoint = otfContour[i];

        if (curPoint.onCurve) {
            contour.push(curPoint);
            prevPoint = curPoint;
        }
        else {
            nextPoint = otfContour[i + 1];
            nextNextPoint = i === l - 2 ? otfContour[0] : otfContour[i + 2];
            const bezierArray = bezierCubic2Q2(prevPoint, curPoint, nextPoint, nextNextPoint);
            bezierArray[0][2].onCurve = true;
            contour.push(bezierArray[0][1]);
            contour.push(bezierArray[0][2]);

            if (bezierArray[1]) {
                bezierArray[1][2].onCurve = true;
                contour.push(bezierArray[1][1]);
                contour.push(bezierArray[1][2]);
            }

            prevPoint = nextNextPoint;
            i += 2;
        }
    }

    return pathCeil(contour);
}


export default function otfContours2ttfContours(otfContours) {
    if (!otfContours || !otfContours.length) {
        return otfContours;
    }
    const contours = [];
    for (let i = 0, l = otfContours.length; i < l; i++) {

        if (otfContours[i][0]) {
            contours.push(transformContour(otfContours[i]));
        }
    }

    return contours;
}
