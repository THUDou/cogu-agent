"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = getArc;
var _bezierCubic2Q = _interopRequireDefault(require("../math/bezierCubic2Q2"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

var TAU = Math.PI * 2;
function vectorAngle(ux, uy, vx, vy) {
  var sign = ux * vy - uy * vx < 0 ? -1 : 1;
  var umag = Math.sqrt(ux * ux + uy * uy);
  var vmag = Math.sqrt(ux * ux + uy * uy);
  var dot = ux * vx + uy * vy;
  var div = dot / (umag * vmag);
  if (div > 1 || div < -1) {
    div = Math.max(div, -1);
    div = Math.min(div, 1);
  }
  return sign * Math.acos(div);
}
function correctRadii(midx, midy, rx, ry) {
  rx = Math.abs(rx);
  ry = Math.abs(ry);
  var Λ = midx * midx / (rx * rx) + midy * midy / (ry * ry);
  if (Λ > 1) {
    rx *= Math.sqrt(Λ);
    ry *= Math.sqrt(Λ);
  }
  return [rx, ry];
}
function getArcCenter(x1, y1, x2, y2, fa, fs, rx, ry, sin_φ, cos_φ) {

  var x1p = cos_φ * (x1 - x2) / 2 + sin_φ * (y1 - y2) / 2;
  var y1p = -sin_φ * (x1 - x2) / 2 + cos_φ * (y1 - y2) / 2;
  var rx_sq = rx * rx;
  var ry_sq = ry * ry;
  var x1p_sq = x1p * x1p;
  var y1p_sq = y1p * y1p;

  var radicant = rx_sq * ry_sq - rx_sq * y1p_sq - ry_sq * x1p_sq;
  if (radicant < 0) {
    radicant = 0;
  }
  radicant /= rx_sq * y1p_sq + ry_sq * x1p_sq;
  radicant = Math.sqrt(radicant) * (fa === fs ? -1 : 1);
  var cxp = radicant * rx / ry * y1p;
  var cyp = radicant * -ry / rx * x1p;

  var cx = cos_φ * cxp - sin_φ * cyp + (x1 + x2) / 2;
  var cy = sin_φ * cxp + cos_φ * cyp + (y1 + y2) / 2;

  var v1x = (x1p - cxp) / rx;
  var v1y = (y1p - cyp) / ry;
  var v2x = (-x1p - cxp) / rx;
  var v2y = (-y1p - cyp) / ry;
  var θ1 = vectorAngle(1, 0, v1x, v1y);
  var Δθ = vectorAngle(v1x, v1y, v2x, v2y);
  if (fs === 0 && Δθ > 0) {
    Δθ -= TAU;
  }
  if (fs === 1 && Δθ < 0) {
    Δθ += TAU;
  }
  return [cx, cy, θ1, Δθ];
}
function approximateUnitArc(θ1, Δθ) {
  var α = 4 / 3 * Math.tan(Δθ / 4);
  var x1 = Math.cos(θ1);
  var y1 = Math.sin(θ1);
  var x2 = Math.cos(θ1 + Δθ);
  var y2 = Math.sin(θ1 + Δθ);
  return [x1, y1, x1 - y1 * α, y1 + x1 * α, x2 + y2 * α, y2 - x2 * α, x2, y2];
}
function a2c(x1, y1, x2, y2, fa, fs, rx, ry, φ) {
  var sin_φ = Math.sin(φ * TAU / 360);
  var cos_φ = Math.cos(φ * TAU / 360);

  var x1p = cos_φ * (x1 - x2) / 2 + sin_φ * (y1 - y2) / 2;
  var y1p = -sin_φ * (x1 - x2) / 2 + cos_φ * (y1 - y2) / 2;
  if (x1p === 0 && y1p === 0) {
    return [];
  }
  if (rx === 0 || ry === 0) {
    return [];
  }
  var radii = correctRadii(x1p, y1p, rx, ry);
  rx = radii[0];
  ry = radii[1];

  var cc = getArcCenter(x1, y1, x2, y2, fa, fs, rx, ry, sin_φ, cos_φ);
  var result = [];
  var θ1 = cc[2];
  var Δθ = cc[3];

  var segments = Math.max(Math.ceil(Math.abs(Δθ) / (TAU / 4)), 1);
  Δθ /= segments;
  for (var i = 0; i < segments; i++) {
    result.push(approximateUnitArc(θ1, Δθ));
    θ1 += Δθ;
  }

  return result.map(function (curve) {
    for (var _i = 0; _i < curve.length; _i += 2) {
      var x = curve[_i + 0];
      var y = curve[_i + 1];

      x *= rx;
      y *= ry;

      var xp = cos_φ * x - sin_φ * y;
      var yp = sin_φ * x + cos_φ * y;

      curve[_i + 0] = xp + cc[0];
      curve[_i + 1] = yp + cc[1];
    }
    return curve;
  });
}

function getArc(rx, ry, angle, largeArc, sweep, p0, p1) {
  var result = a2c(p0.x, p0.y, p1.x, p1.y, largeArc, sweep, rx, ry, angle);
  var path = [];
  if (result.length) {
    path.push({
      x: result[0][0],
      y: result[0][1],
      onCurve: true
    });

    result.forEach(function (c) {
      var q2Array = (0, _bezierCubic2Q.default)({
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
