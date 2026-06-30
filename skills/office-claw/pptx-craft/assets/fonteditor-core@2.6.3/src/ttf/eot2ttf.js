
import Reader from './reader';
import Writer from './writer';
import error from './error';

export default function eot2ttf(eotBuffer, options = {}) {
    const eotReader = new Reader(eotBuffer, 0, eotBuffer.byteLength, true);

    const magicNumber = eotReader.readUint16(34);
    if (magicNumber !== 0x504C) {
        error.raise(10110);
    }

    const version = eotReader.readUint32(8);
    if (version !== 0x20001 && version !== 0x10000 && version !== 0x20002) {
        error.raise(10110);
    }

    const eotSize = eotBuffer.byteLength || eotBuffer.length;
    const fontSize = eotReader.readUint32(4);

    let fontOffset = 82;
    const familyNameSize = eotReader.readUint16(fontOffset);
    fontOffset += 4 + familyNameSize;

    const styleNameSize = eotReader.readUint16(fontOffset);
    fontOffset += 4 + styleNameSize;

    const versionNameSize = eotReader.readUint16(fontOffset);
    fontOffset += 4 + versionNameSize;

    const fullNameSize = eotReader.readUint16(fontOffset);
    fontOffset += 2 + fullNameSize;

    if (version === 0x20001 || version === 0x20002) {
        const rootStringSize = eotReader.readUint16(fontOffset + 2);
        fontOffset += 4 + rootStringSize;
    }

    if (version === 0x20002) {
        fontOffset += 10;
        const signatureSize = eotReader.readUint16(fontOffset);
        fontOffset += 2 + signatureSize;
        fontOffset += 4;
        const eudcFontSize = eotReader.readUint32(fontOffset);
        fontOffset += 4 + eudcFontSize;
    }

    if (fontOffset + fontSize > eotSize) {
        error.raise(10001);
    }

    if (eotBuffer.slice) {
        return eotBuffer.slice(fontOffset, fontOffset + fontSize);
    }

    const bytes = eotReader.readBytes(fontOffset, fontSize);
    return new Writer(new ArrayBuffer(fontSize)).writeBytes(bytes).getBuffer();
}
