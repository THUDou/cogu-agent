"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _computeBoundingBox = require("./computeBoundingBox");
var _pathAdjust = _interopRequireDefault(require("./pathAdjust"));
var _pathRotate = _interopRequireDefault(require("./pathRotate"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }
function _toConsumableArray(arr) { return _arrayWithoutHoles(arr) || _iterableToArray(arr) || _unsupportedIterableToArray(arr) || _nonIterableSpread(); }
function _nonIterableSpread() { throw new TypeError("Invalid attempt to spread non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method."); }
function _unsupportedIterableToArray(o, minLen) { if (!o) return; if (typeof o === "string") return _arrayLikeToArray(o, minLen); var n = Object.prototype.toString.call(o).slice(8, -1); if (n === "Object" && o.constructor) n = o.constructor.name; if (n === "Map" || n === "Set") return Array.from(o); if (n === "Arguments" || /^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n)) return _arrayLikeToArray(o, minLen); }
function _iterableToArray(iter) { if (typeof Symbol !== "undefined" && iter[Symbol.iterator] != null || iter["@@iterator"] != null) return Array.from(iter); }
function _arrayWithoutHoles(arr) { if (Array.isArray(arr)) return _arrayLikeToArray(arr); }
function _arrayLikeToArray(arr, len) { if (len == null || len > arr.length) len = arr.length; for (var i = 0, arr2 = new Array(len); i < len; i++) arr2[i] = arr[i]; return arr2; } /**
 * @file 路径组变化函数
 * @author mengke01(kekee000@gmail.com)
 */
function mirrorPaths(paths, xScale, yScale) {
  var _computePath = _computeBoundingBox.computePath.apply(void 0, _toConsumableArray(paths)),
    x = _computePath.x,
    y = _computePath.y,
    width = _computePath.width,
    height = _computePath.height;
  if (xScale === -1) {
    paths.forEach(function (p) {
      (0, _pathAdjust.default)(p, -1, 1, -x, 0);
      (0, _pathAdjust.default)(p, 1, 1, x + width, 0);
      p.reverse();
    });
  }
  if (yScale === -1) {
    paths.forEach(function (p) {
      (0, _pathAdjust.default)(p, 1, -1, 0, -y);
      (0, _pathAdjust.default)(p, 1, 1, 0, y + height);
      p.reverse();
    });
  }
  return paths;
}
var _default = exports.default = {
  rotate: function rotate(paths, angle) {
    if (!angle) {
      return paths;
    }
    var bound = _computeBoundingBox.computePath.apply(void 0, _toConsumableArray(paths));
    var cx = bound.x + bound.width / 2;
    var cy = bound.y + bound.height / 2;
    paths.forEach(function (p) {
      (0, _pathRotate.default)(p, angle, cx, cy);
    });
    return paths;
  },
  move: function move(paths, x, y) {
    var bound = _computeBoundingBox.computePath.apply(void 0, _toConsumableArray(paths));
    paths.forEach(function (path) {
      (0, _pathAdjust.default)(path, 1, 1, x - bound.x, y - bound.y);
    });
    return paths;
  },
  mirror: function mirror(paths) {
    return mirrorPaths(paths, -1, 1);
  },
  flip: function flip(paths) {
    return mirrorPaths(paths, 1, -1);
  }
};
