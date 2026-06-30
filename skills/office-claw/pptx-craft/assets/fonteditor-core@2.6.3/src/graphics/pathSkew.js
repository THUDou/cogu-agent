
export default function pathSkew(contour, angle, offsetX, offsetY) {
    angle = angle === undefined ? 0 : angle;
    const x = offsetX || 0;
    const tan = Math.tan(angle);
    let p;
    let i;
    let l;

    if (x === 0) {
        for (i = 0, l = contour.length; i < l; i++) {
            p = contour[i];
            p.x += tan * (p.y - offsetY);
        }
    }
    else {
        for (i = 0, l = contour.length; i < l; i++) {
            p = contour[i];
            p.y += tan * (p.x - offsetX);
        }
    }

    return contour;
}
