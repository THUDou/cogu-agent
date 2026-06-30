
export default function rect2contour(x, y, width, height) {
    x = +x;
    y = +y;
    width = +width;
    height = +height;

    return [
        {
            x,
            y,
            onCurve: true
        },
        {
            x: x + width,
            y,
            onCurve: true
        },
        {
            x: x + width,
            y: y + height,
            onCurve: true
        },
        {
            x,
            y: y + height,
            onCurve: true
        }
    ];
}
