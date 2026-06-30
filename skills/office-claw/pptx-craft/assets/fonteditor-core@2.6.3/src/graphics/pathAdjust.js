
export default function pathAdjust(contour, scaleX, scaleY, offsetX, offsetY) {
    scaleX = scaleX === undefined ? 1 : scaleX;
    scaleY = scaleY === undefined ? 1 : scaleY;
    const x = offsetX || 0;
    const y = offsetY || 0;
    let p;
    for (let i = 0, l = contour.length; i < l; i++) {
        p = contour[i];
        p.x = scaleX * (p.x + x);
        p.y = scaleY * (p.y + y);
    }
    return contour;
}
