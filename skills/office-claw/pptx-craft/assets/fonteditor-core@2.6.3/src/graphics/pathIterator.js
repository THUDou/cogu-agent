
export default function pathIterator(contour, callBack) {

    let curPoint;
    let prevPoint;
    let nextPoint;
    let cursorPoint; // cursorPoint 为当前单个绘制命令的起点

    for (let i = 0, l = contour.length; i < l; i++) {
        curPoint = contour[i];
        prevPoint = i === 0 ? contour[l - 1] : contour[i - 1];
        nextPoint = i === l - 1 ? contour[0] : contour[i + 1];

        if (i === 0) {
            if (curPoint.onCurve) {
                cursorPoint = curPoint;
            }
            else if (prevPoint.onCurve) {
                cursorPoint = prevPoint;
            }
            else {
                cursorPoint = {
                    x: (prevPoint.x + curPoint.x) / 2,
                    y: (prevPoint.y + curPoint.y) / 2
                };
            }

        }

        if (curPoint.onCurve && nextPoint.onCurve) {
            if (false === callBack('L', curPoint, nextPoint, 0, i)) {
                break;
            }
            cursorPoint = nextPoint;
        }
        else if (!curPoint.onCurve) {

            if (nextPoint.onCurve) {
                if (false === callBack('Q', cursorPoint, curPoint, nextPoint, i)) {
                    break;
                }
                cursorPoint = nextPoint;
            }
            else {
                const last = {
                    x: (curPoint.x + nextPoint.x) / 2,
                    y: (curPoint.y + nextPoint.y) / 2
                };
                if (false === callBack('Q', cursorPoint, curPoint, last, i)) {
                    break;
                }
                cursorPoint = last;
            }
        }
    }
}
