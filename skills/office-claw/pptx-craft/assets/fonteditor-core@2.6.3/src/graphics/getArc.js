
import bezierCubic2Q2 from '../math/bezierCubic2Q2';


const TAU = Math.PI * 2;

function vectorAngle(ux, uy, vx, vy) {
    const sign = (ux * vy - uy * vx < 0) ? -1 : 1;
    const umag = Math.sqrt(ux * ux + uy * uy);
    const vmag = Math.sqrt(ux * ux + uy * uy);
    const dot = ux * vx + uy * vy;
    let div = dot / (umag * vmag);

    if (div > 1 || div < -1) {
        div = Math.max(div, -1);
        div = Math.min(div, 1);
    }

    return sign * Math.acos(div);
}

function correctRadii(midx, midy, rx, ry) {
    rx = Math.abs(rx);
    ry = Math.abs(ry);

    const Λ = (midx * midx) / (rx * rx) + (midy * midy) / (ry * ry);
    if (Λ > 1) {
        rx *= Math.sqrt(Λ);
        ry *= Math.sqrt(Λ);
    }

    return [rx, ry];
}


function getArcCenter(x1, y1, x2, y2, fa, fs, rx, ry, sin_φ, cos_φ) {

    const x1p = cos_φ * (x1 - x2) / 2 + sin_φ * (y1 - y2) / 2;
    const y1p = -sin_φ * (x1 - x2) / 2 + cos_φ * (y1 - y2) / 2;

    const rx_sq = rx * rx;
    const ry_sq = ry * ry;
    const x1p_sq = x1p * x1p;
    const y1p_sq = y1p * y1p;

    let radicant = (rx_sq * ry_sq) - (rx_sq * y1p_sq) - (ry_sq * x1p_sq);

    if (radicant < 0) {
        radicant = 0;
    }

    radicant /= (rx_sq * y1p_sq) + (ry_sq * x1p_sq);
    radicant = Math.sqrt(radicant) * (fa === fs ? -1 : 1);

    const cxp = radicant * rx / ry * y1p;
    const cyp = radicant * -ry / rx * x1p;

    const cx = cos_φ * cxp - sin_φ * cyp + (x1 + x2) / 2;
    const cy = sin_φ * cxp + cos_φ * cyp + (y1 + y2) / 2;

    const v1x = (x1p - cxp) / rx;
    const v1y = (y1p - cyp) / ry;
    const v2x = (-x1p - cxp) / rx;
    const v2y = (-y1p - cyp) / ry;

    const θ1 = vectorAngle(1, 0, v1x, v1y);
    let Δθ = vectorAngle(v1x, v1y, v2x, v2y);

    if (fs === 0 && Δθ > 0) {
        Δθ -= TAU;
    }
    if (fs === 1 && Δθ < 0) {
        Δθ += TAU;
    }

    return [cx, cy, θ1, Δθ];
}

function approximateUnitArc(θ1, Δθ) {
    const α = 4 / 3 * Math.tan(Δθ / 4);

    const x1 = Math.cos(θ1);
    const y1 = Math.sin(θ1);
    const x2 = Math.cos(θ1 + Δθ);
    const y2 = Math.sin(θ1 + Δθ);

    return [x1, y1, x1 - y1 * α, y1 + x1 * α, x2 + y2 * α, y2 - x2 * α, x2, y2];
}


function a2c(x1, y1, x2, y2, fa, fs, rx, ry, φ) {
    const sin_φ = Math.sin(φ * TAU / 360);
    const cos_φ = Math.cos(φ * TAU / 360);

    const x1p = cos_φ * (x1 - x2) / 2 + sin_φ * (y1 - y2) / 2;
    const y1p = -sin_φ * (x1 - x2) / 2 + cos_φ * (y1 - y2) / 2;

    if (x1p === 0 && y1p === 0) {
        return [];
    }

    if (rx === 0 || ry === 0) {
        return [];
    }

    const radii = correctRadii(x1p, y1p, rx, ry);
    rx = radii[0];
    ry = radii[1];

    const cc = getArcCenter(x1, y1, x2, y2, fa, fs, rx, ry, sin_φ, cos_φ);

    const result = [];
    let θ1 = cc[2];
    let Δθ = cc[3];

    const segments = Math.max(Math.ceil(Math.abs(Δθ) / (TAU / 4)), 1);
    Δθ /= segments;

    for (let i = 0; i < segments; i++) {
        result.push(approximateUnitArc(θ1, Δθ));
        θ1 += Δθ;
    }

    return result.map(curve => {
        for (let i = 0; i < curve.length; i += 2) {
            let x = curve[i + 0];
            let y = curve[i + 1];

            x *= rx;
            y *= ry;

            const xp = cos_φ * x - sin_φ * y;
            const yp = sin_φ * x + cos_φ * y;

            curve[i + 0] = xp + cc[0];
            curve[i + 1] = yp + cc[1];
        }

        return curve;
    });
}

export default function getArc(rx, ry, angle, largeArc, sweep, p0, p1) {
    const result = a2c(p0.x, p0.y, p1.x, p1.y, largeArc, sweep, rx, ry, angle);
    const path = [];

    if (result.length) {
        path.push({
            x: result[0][0],
            y: result[0][1],
            onCurve: true
        });

        result.forEach(c => {
            const q2Array = bezierCubic2Q2({
                x: c[0],
                y: c[1]
            }, {
                x: c[2],
                y: c[3]
            }, {
                x: c[4],
                y: c[5]
            }, {
                x: c[6],
                y: c[7]
            });

            q2Array[0][2].onCurve = true;
            path.push(q2Array[0][1]);
            path.push(q2Array[0][2]);
            if (q2Array[1]) {
                q2Array[1][2].onCurve = true;
                path.push(q2Array[1][1]);
                path.push(q2Array[1][2]);
            }
        });
    }

    return path;
}
