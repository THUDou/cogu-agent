
import {curry} from '../common/lang';
import error from './error';

if (typeof ArrayBuffer === 'undefined' || typeof DataView === 'undefined') {
    throw new Error('not support ArrayBuffer and DataView');
}

const dataType = {
    Int8: 1,
    Int16: 2,
    Int32: 4,
    Uint8: 1,
    Uint16: 2,
    Uint32: 4,
    Float32: 4,
    Float64: 8
};

export default class Reader {

    constructor(buffer, offset, length, littleEndian) {

        const bufferLength = buffer.byteLength || buffer.length;

        this.offset = offset || 0;
        this.length = length || (bufferLength - this.offset);
        this.littleEndian = littleEndian || false;

        this.view = new DataView(buffer, this.offset, this.length);
    }

    read(type, offset, littleEndian) {

        if (undefined === offset) {
            offset = this.offset;
        }

        if (undefined === littleEndian) {
            littleEndian = this.littleEndian;
        }

        if (undefined === dataType[type]) {
            return this['read' + type](offset, littleEndian);
        }

        const size = dataType[type];
        this.offset = offset + size;
        return this.view['get' + type](offset, littleEndian);
    }

    readBytes(offset, length = null) {

        if (length == null) {
            length = offset;
            offset = this.offset;
        }

        if (length < 0 || offset + length > this.length) {
            error.raise(10001, this.length, offset + length);
        }

        const buffer = [];
        for (let i = 0; i < length; ++i) {
            buffer.push(this.view.getUint8(offset + i));
        }

        this.offset = offset + length;
        return buffer;
    }

    readString(offset, length = null) {

        if (length == null) {
            length = offset;
            offset = this.offset;
        }

        if (length < 0 || offset + length > this.length) {
            error.raise(10001, this.length, offset + length);
        }

        let value = '';
        for (let i = 0; i < length; ++i) {
            const c = this.readUint8(offset + i);
            value += String.fromCharCode(c);
        }

        this.offset = offset + length;

        return value;
    }

    readChar(offset) {
        return this.readString(offset, 1);
    }

    readUint24(offset) {
        const [i, j, k] = this.readBytes(offset || this.offset, 3);
        return (i << 16) + (j << 8) + k;
    }

    readFixed(offset) {
        if (undefined === offset) {
            offset = this.offset;
        }
        const val = this.readInt32(offset, false) / 65536.0;
        return Math.ceil(val * 100000) / 100000;
    }

    readLongDateTime(offset) {
        if (undefined === offset) {
            offset = this.offset;
        }

        const delta = -2077545600000;
        const time = this.readUint32(offset + 4, false);
        const date = new Date();
        date.setTime(time * 1000 + delta);
        return date;
    }

    seek(offset) {
        if (undefined === offset) {
            this.offset = 0;
        }

        if (offset < 0 || offset > this.length) {
            error.raise(10001, this.length, offset);
        }

        this.offset = offset;

        return this;
    }

    dispose() {
        delete this.view;
    }
}

Object.keys(dataType).forEach((type) => {
    Reader.prototype['read' + type] = curry(Reader.prototype.read, type);
});
