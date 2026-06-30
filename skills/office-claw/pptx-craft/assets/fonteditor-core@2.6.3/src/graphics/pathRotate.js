
export default function pathRotate(contour, angle, centerX, centerY) {
    angle = angle === undefined ? 0 : angle;
    const x = centerX || 0;
    const y = centerY || 0;
    const cos = Math.cos(angle);
    const sin = Math.sin(angle);
    let px;
    let py;
    let p;

    for (let i = 0, l = contour.length; i < l; i++) {
        p = contour[i];
        px = cos * (p.x - x) - sin * (p.y - y);
        py = cos * (p.y - y) + sin * (p.x - x);
        p.x = px + x;
        p.y = py + y;
    }

    return contour;
}
