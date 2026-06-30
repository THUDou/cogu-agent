
import getCFFString from './getCFFString';

export default function parseCFFCharset(reader, start, nGlyphs, strings) {
    if (start) {
        reader.seek(start);
    }

    let i;
    let sid;
    let count;
    nGlyphs -= 1;
    const charset = ['.notdef'];

    const format = reader.readUint8();
    if (format === 0) {
        for (i = 0; i < nGlyphs; i += 1) {
            sid = reader.readUint16();
            charset.push(getCFFString(strings, sid));
        }
    }
    else if (format === 1) {
        while (charset.length <= nGlyphs) {
            sid = reader.readUint16();
            count = reader.readUint8();
            for (i = 0; i <= count; i += 1) {
                charset.push(getCFFString(strings, sid));
                sid += 1;
            }
        }
    }
    else if (format === 2) {
        while (charset.length <= nGlyphs) {
            sid = reader.readUint16();
            count = reader.readUint16();
            for (i = 0; i <= count; i += 1) {
                charset.push(getCFFString(strings, sid));
                sid += 1;
            }
        }
    }
    else {
        throw new Error('Unknown charset format ' + format);
    }

    return charset;
}
