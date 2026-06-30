
const struct = {
    Int8: 1,
    Uint8: 2,
    Int16: 3,
    Uint16: 4,
    Int32: 5,
    Uint32: 6,
    Fixed: 7, // 32-bit signed fixed-point number (16.16)
    FUnit: 8, // Smallest measurable distance in the em space
    F2Dot14: 11,
    LongDateTime: 12,

    Char: 13,
    String: 14,
    Bytes: 15,
    Uint24: 20
};

const names = {};
Object.keys(struct).forEach((key) => {
    names[struct[key]] = key;
});

struct.names = names;

export default struct;
