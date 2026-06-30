
import {getPointHash} from './util';

export function interpolate(path) {
    const newPath = [];
    for (let i = 0, l = path.length; i < l; i++) {
        const next = i === l - 1 ? 0 : i + 1;
        newPath.push(path[i]);
        if (!path[i].onCurve && !path[next].onCurve) {
            newPath.push({
                x: (path[i].x + path[next].x) / 2,
                y: (path[i].y + path[next].y) / 2,
                onCurve: true
            });
        }
    }

    return newPath;
}


export function deInterpolate(path) {
    const newPath = [];

    for (let i = 0, l = path.length; i < l; i++) {
        const next = i === l - 1 ? 0 : i + 1;
        const prev = i === 0 ? l - 1 : i - 1;
        if (
            !path[prev].onCurve && path[i].onCurve && !path[next].onCurve
            && Math.abs(2 * path[i].x - path[prev].x - path[next].x) < 0.001
            && Math.abs(2 * path[i].y - path[prev].y - path[next].y) < 0.001
        ) {
            continue;
        }

        newPath.push(path[i]);
    }

    return newPath;
}


export function isClockWise(path) {

    if (path.length < 3) {
        return 0;
    }

    let zCount = 0;
    for (let i = 0, l = path.length; i < l; i++) {
        const cur = path[i];
        const prev = i === 0 ? path[l - 1] : path[i - 1];
        const next = i === l - 1 ? path[0] : path[i + 1];
        const z = (cur.x - prev.x) * (next.y - cur.y)
            - (cur.y - prev.y) * (next.x - cur.x);

        if (z < 0) {
            zCount--;
        }
        else if (z > 0) {
            zCount++;
        }
    }

    return zCount === 0
        ? 0
        : zCount < 0 ? 1 : -1;
}

export function getPathHash(path) {
    let hash = 0;
    const seed = 131;

    path.forEach(p => {
        hash = 0x7FFFFFFF & (hash * seed + getPointHash(p) + (p.onCurve ? 1 : 0));
    });

    return hash;
}


export function removeOverlapPoints(points) {
    const hash = {};
    const ret = [];
    for (let i = 0, l = points.length; i < l; i++) {
        const hashcode = points[i].x * 31 + points[i].y;
        if (!hash[hashcode]) {
            ret.push(points[i]);
            hash[hashcode] = 1;
        }
    }
    return ret;
}

export function makeLink(path) {
    for (let i = 0, l = path.length; i < l; i++) {
        const cur = path[i];
        const prev = i === 0 ? path[l - 1] : path[i - 1];
        const next = i === l - 1 ? path[0] : path[i + 1];
        cur.index = i;
        cur.next = next;
        cur.prev = prev;
    }

    return path;
}

export function scale(path, ratio) {
    for (let i = 0, l = path.length; i < l; i++) {
        const cur = path[i];
        cur.x *= ratio;
        cur.y *= ratio;
    }

    return path;
}


export function clone(path) {
    return path ? path.map(p => {
        const newP = {
            x: p.x,
            y: p.y
        };

        if (p.onCurve) {
            newP.onCurve = true;
        }

        return newP;
    }) : path;
}
