"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.mul = mul;
exports.multiply = multiply;

function mul() {
  var matrix1 = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : [1, 0, 0, 1];
  var matrix2 = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : [1, 0, 0, 1];
  if (matrix1.length === 4) {
    return [matrix1[0] * matrix2[0] + matrix1[2] * matrix2[1], matrix1[1] * matrix2[0] + matrix1[3] * matrix2[1], matrix1[0] * matrix2[2] + matrix1[2] * matrix2[3], matrix1[1] * matrix2[2] + matrix1[3] * matrix2[3]];
  }

  return [matrix1[0] * matrix2[0] + matrix1[2] * matrix2[1], matrix1[1] * matrix2[0] + matrix1[3] * matrix2[1], matrix1[0] * matrix2[2] + matrix1[2] * matrix2[3], matrix1[1] * matrix2[2] + matrix1[3] * matrix2[3], matrix1[0] * matrix2[4] + matrix1[2] * matrix2[5] + matrix1[4], matrix1[1] * matrix2[4] + matrix1[3] * matrix2[5] + matrix1[5]];
}

function multiply() {
  var result = arguments.length <= 0 ? undefined : arguments[0];
  for (var i = 1, matrix; matrix = i < 0 || arguments.length <= i ? undefined : arguments[i]; i++) {
    result = mul(result, matrix);
  }
  return result;
}
