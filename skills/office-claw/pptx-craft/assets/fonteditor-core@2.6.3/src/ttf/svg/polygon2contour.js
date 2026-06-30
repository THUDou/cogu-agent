
import parseParams from './parseParams';

export default function polygon2contour(points) {

    if (!points || !points.length) {
        return null;
    }

    const contours = [];
    const segments = parseParams(points);
    for (let i = 0, l = segments.length; i < l; i += 2) {
        contours.push({
            x: segments[i],
            y: segments[i + 1],
            onCurve: true
        });
    }

    return contours;
}
