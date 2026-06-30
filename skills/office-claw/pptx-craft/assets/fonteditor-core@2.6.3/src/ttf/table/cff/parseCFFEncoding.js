
export default function parseCFFEncoding(reader, start) {
    if (null != start) {
        reader.seek(start);
    }

    let i;
    let code;
    const encoding = {};
    const format = reader.readUint8();

    if (format === 0) {
        const nCodes = reader.readUint8();
        for (i = 0; i < nCodes; i += 1) {
            code = reader.readUint8();
            encoding[code] = i;
        }
    }
    else if (format === 1) {
        const nRanges = reader.readUint8();
        code = 1;
        for (i = 0; i < nRanges; i += 1) {
            const first = reader.readUint8();
            const nLeft = reader.readUint8();
            for (let j = first; j <= first + nLeft; j += 1) {
                encoding[j] = code;
                code += 1;
            }
        }
    }
    else {
        console.warn('unknown encoding format:' + format);
    }

    return encoding;
}
