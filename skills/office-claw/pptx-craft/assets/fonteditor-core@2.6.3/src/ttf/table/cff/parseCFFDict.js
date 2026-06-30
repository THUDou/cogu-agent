
import getCFFString from './getCFFString';

const TOP_DICT_META = [
    {
        name: 'version',
        op: 0,
        type: 'SID'
    },
    {
        name: 'notice',
        op: 1,
        type: 'SID'
    },
    {
        name: 'copyright',
        op: 1200,
        type: 'SID'
    },
    {
        name: 'fullName',
        op: 2,
        type: 'SID'
    },
    {
        name: 'familyName',
        op: 3,
        type: 'SID'
    },
    {
        name: 'weight',
        op: 4,
        type: 'SID'
    },
    {
        name: 'isFixedPitch',
        op: 1201,
        type: 'number',
        value: 0
    },
    {
        name: 'italicAngle',
        op: 1202,
        type: 'number',
        value: 0
    },
    {
        name: 'underlinePosition',
        op: 1203,
        type: 'number',
        value: -100
    },
    {
        name: 'underlineThickness',
        op: 1204,
        type: 'number',
        value: 50
    },
    {
        name: 'paintType',
        op: 1205,
        type: 'number',
        value: 0
    },
    {
        name: 'charstringType',
        op: 1206,
        type: 'number',
        value: 2
    },
    {
        name: 'fontMatrix',
        op: 1207,
        type: ['real', 'real', 'real', 'real', 'real', 'real'],
        value: [0.001, 0, 0, 0.001, 0, 0]
    },
    {
        name: 'uniqueId',
        op: 13,
        type: 'number'
    },
    {
        name: 'fontBBox',
        op: 5,
        type: ['number', 'number', 'number', 'number'],
        value: [0, 0, 0, 0]
    },
    {
        name: 'strokeWidth',
        op: 1208,
        type: 'number',
        value: 0
    },
    {
        name: 'xuid',
        op: 14,
        type: [],
        value: null
    },
    {
        name: 'charset',
        op: 15,
        type: 'offset',
        value: 0
    },
    {
        name: 'encoding',
        op: 16,
        type: 'offset',
        value: 0
    },
    {
        name: 'charStrings',
        op: 17,
        type: 'offset',
        value: 0
    },
    {
        name: 'private',
        op: 18,
        type: ['number', 'offset'],
        value: [0, 0]
    }
];

const PRIVATE_DICT_META = [
    {
        name: 'subrs',
        op: 19,
        type: 'offset',
        value: 0
    },
    {
        name: 'defaultWidthX',
        op: 20,
        type: 'number',
        value: 0
    },
    {
        name: 'nominalWidthX',
        op: 21,
        type: 'number',
        value: 0
    }
];

function entriesToObject(entries) {
    const hash = {};

    for (let i = 0, l = entries.length; i < l; i++) {
        const key = entries[i][0];
        if (undefined !== hash[key]) {
            console.warn('dict already has key:' + key);
            continue;
        }

        const values = entries[i][1];
        hash[key] = values.length === 1 ? values[0] : values;
    }

    return hash;
}


function parseFloatOperand(reader) {
    let s = '';
    const eof = 15;
    const lookup = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '.', 'E', 'E-', null, '-'];

    while (true) {
        const b = reader.readUint8();
        const n1 = b >> 4;
        const n2 = b & 15;

        if (n1 === eof) {
            break;
        }

        s += lookup[n1];

        if (n2 === eof) {
            break;
        }

        s += lookup[n2];
    }

    return parseFloat(s);
}

function parseOperand(reader, b0) {
    let b1;
    let b2;
    let b3;
    let b4;
    if (b0 === 28) {
        b1 = reader.readUint8();
        b2 = reader.readUint8();
        return b1 << 8 | b2;
    }

    if (b0 === 29) {
        b1 = reader.readUint8();
        b2 = reader.readUint8();
        b3 = reader.readUint8();
        b4 = reader.readUint8();
        return b1 << 24 | b2 << 16 | b3 << 8 | b4;
    }

    if (b0 === 30) {
        return parseFloatOperand(reader);
    }

    if (b0 >= 32 && b0 <= 246) {
        return b0 - 139;
    }

    if (b0 >= 247 && b0 <= 250) {
        b1 = reader.readUint8();
        return (b0 - 247) * 256 + b1 + 108;
    }

    if (b0 >= 251 && b0 <= 254) {
        b1 = reader.readUint8();
        return -(b0 - 251) * 256 - b1 - 108;
    }

    throw new Error('invalid b0 ' + b0 + ',at:' + reader.offset);
}



function interpretDict(dict, meta, strings) {
    const newDict = {};

    for (let i = 0, l = meta.length; i < l; i++) {
        const m = meta[i];
        let value = dict[m.op];
        if (value === undefined) {
            value = m.value !== undefined ? m.value : null;
        }

        if (m.type === 'SID') {
            value = getCFFString(strings, value);
        }

        newDict[m.name] = value;
    }

    return newDict;
}


function parseCFFDict(reader, offset, length) {
    if (null != offset) {
        reader.seek(offset);
    }

    const entries = [];
    let operands = [];
    const lastOffset = reader.offset + (null != length ? length : reader.length);

    while (reader.offset < lastOffset) {
        let op = reader.readUint8();

        if (op <= 21) {
            if (op === 12) {
                op = 1200 + reader.readUint8();
            }

            entries.push([op, operands]);
            operands = [];
        }
        else {
            operands.push(parseOperand(reader, op));
        }
    }

    return entriesToObject(entries);
}

function parseTopDict(reader, start, length, strings) {
    const dict = parseCFFDict(reader, start || 0, length || reader.length);
    return interpretDict(dict, TOP_DICT_META, strings);
}

function parsePrivateDict(reader, start, length, strings) {
    const dict = parseCFFDict(reader, start || 0, length || reader.length);
    return interpretDict(dict, PRIVATE_DICT_META, strings);
}


export default {
    parseTopDict,
    parsePrivateDict
};
