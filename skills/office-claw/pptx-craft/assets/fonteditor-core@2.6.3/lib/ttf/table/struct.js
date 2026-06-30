"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;

var struct = {
  Int8: 1,
  Uint8: 2,
  Int16: 3,
  Uint16: 4,
  Int32: 5,
  Uint32: 6,
  Fixed: 7,
  FUnit: 8,
  F2Dot14: 11,
  LongDateTime: 12,
  Char: 13,
  String: 14,
  Bytes: 15,
  Uint24: 20
};

var names = {};
Object.keys(struct).forEach(function (key) {
  names[struct[key]] = key;
});
struct.names = names;
var _default = exports.default = struct;
