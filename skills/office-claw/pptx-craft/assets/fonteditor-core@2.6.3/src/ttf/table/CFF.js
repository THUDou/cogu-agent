
import table from './table';
import string from '../util/string';
import encoding from './cff/encoding';
import cffStandardStrings from './cff/cffStandardStrings';
import parseCFFDict from './cff/parseCFFDict';
import parseCFFGlyph from './cff/parseCFFGlyph';
import parseCFFCharset from './cff/parseCFFCharset';
import parseCFFEncoding from './cff/parseCFFEncoding';
import Reader from '../reader';

function getOffset(reader, offSize) {
    let v = 0;
    for (let i = 0; i < offSize; i++) {
        v <<= 8;
        v += reader.readUint8();
    }
    return v;
}

function parseCFFHead(reader) {
    const head = {};
    head.startOffset = reader.offset;
    head.endOffset = head.startOffset + 4;
    head.formatMajor = reader.readUint8();
    head.formatMinor = reader.readUint8();
    head.size = reader.readUint8();
    head.offsetSize = reader.readUint8();
    return head;
}

function parseCFFIndex(reader, offset, conversionFn) {
    if (offset) {
        reader.seek(offset);
    }
    const start = reader.offset;
    const offsets = [];
    const objects = [];
    const count = reader.readUint16();
    let i;
    let l;
    if (count !== 0) {
        const offsetSize = reader.readUint8();
        for (i = 0, l = count + 1; i < l; i++) {
            offsets.push(getOffset(reader, offsetSize));
        }

        for (i = 0, l = count; i < l; i++) {
            let value = reader.readBytes(offsets[i + 1] - offsets[i]);
            if (conversionFn) {
                value = conversionFn(value);
            }
            objects.push(value);
        }
    }

    return {
        objects,
        startOffset: start,
        endOffset: reader.offset
    };
}

function calcCFFSubroutineBias(subrs) {
    let bias;
    if (subrs.length < 1240) {
        bias = 107;
    }
    else if (subrs.length < 33900) {
        bias = 1131;
    }
    else {
        bias = 32768;
    }

    return bias;
}


export default table.create(
    'cff',
    [],
    {
        read(reader, font) {

            const offset = this.offset;
            reader.seek(offset);

            const head = parseCFFHead(reader);
            const nameIndex = parseCFFIndex(reader, head.endOffset, string.getString);
            const topDictIndex = parseCFFIndex(reader, nameIndex.endOffset);
            const stringIndex = parseCFFIndex(reader, topDictIndex.endOffset, string.getString);
            const globalSubrIndex = parseCFFIndex(reader, stringIndex.endOffset);

            const cff = {
                head
            };

            cff.gsubrs = globalSubrIndex.objects;
            cff.gsubrsBias = calcCFFSubroutineBias(globalSubrIndex.objects);

            const dictReader = new Reader(new Uint8Array(topDictIndex.objects[0]).buffer);
            const topDict = parseCFFDict.parseTopDict(
                dictReader,
                0,
                dictReader.length,
                stringIndex.objects
            );
            cff.topDict = topDict;

            const privateDictLength = topDict.private[0];
            let privateDict = {};
            let privateDictOffset;
            if (privateDictLength) {
                privateDictOffset = offset + topDict.private[1];
                privateDict = parseCFFDict.parsePrivateDict(
                    reader,
                    privateDictOffset,
                    privateDictLength,
                    stringIndex.objects
                );
                cff.defaultWidthX = privateDict.defaultWidthX;
                cff.nominalWidthX = privateDict.nominalWidthX;
            }
            else {
                cff.defaultWidthX = 0;
                cff.nominalWidthX = 0;
            }

            if (privateDict.subrs) {
                const subrOffset = privateDictOffset + privateDict.subrs;
                const subrIndex = parseCFFIndex(reader, subrOffset);
                cff.subrs = subrIndex.objects;
                cff.subrsBias = calcCFFSubroutineBias(cff.subrs);
            }
            else {
                cff.subrs = [];
                cff.subrsBias = 0;
            }
            cff.privateDict = privateDict;

            const charStringsIndex = parseCFFIndex(reader, offset + topDict.charStrings);
            const nGlyphs = charStringsIndex.objects.length;

            if (topDict.charset < 3) {
                cff.charset = cffStandardStrings;
            }
            else {
                cff.charset = parseCFFCharset(reader, offset + topDict.charset, nGlyphs, stringIndex.objects);
            }

            if (topDict.encoding === 0) {
                cff.encoding = encoding.standardEncoding;
            }
            else if (topDict.encoding === 1) {
                cff.encoding = encoding.expertEncoding;
            }
            else {
                cff.encoding = parseCFFEncoding(reader, offset + topDict.encoding);
            }

            cff.glyf = [];

            const subset = font.readOptions.subset;
            if (subset && subset.length > 0) {

                const subsetMap = {
                    0: true // 设置.notdef
                };
                const codes = font.cmap;

                Object.keys(codes).forEach((c) => {
                    if (subset.indexOf(+c) > -1) {
                        const i = codes[c];
                        subsetMap[i] = true;
                    }
                });
                font.subsetMap = subsetMap;

                Object.keys(subsetMap).forEach((i) => {
                    i = +i;
                    const glyf = parseCFFGlyph(charStringsIndex.objects[i], cff, i);
                    glyf.name = cff.charset[i];
                    cff.glyf[i] = glyf;
                });
            }
            else {
                for (let i = 0, l = nGlyphs; i < l; i++) {
                    const glyf = parseCFFGlyph(charStringsIndex.objects[i], cff, i);
                    glyf.name = cff.charset[i];
                    cff.glyf.push(glyf);
                }
            }

            return cff;
        },

        write(writer, font) {
            throw new Error('not support write cff table');
        },

        size(font) {
            throw new Error('not support get cff table size');
        }
    }
);
