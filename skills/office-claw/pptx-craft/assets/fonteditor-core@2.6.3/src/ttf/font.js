
import bufferTool from '../nodejs/buffer';

import getEmptyttfObject from './getEmptyttfObject';
import TTF from './ttf';

import woff2ttf from './woff2ttf';
import otf2ttfobject from './otf2ttfobject';
import eot2ttf from './eot2ttf';
import svg2ttfobject from './svg2ttfobject';
import TTFReader from './ttfreader';

import TTFWriter from './ttfwriter';
import ttf2eot from './ttf2eot';
import ttf2woff from './ttf2woff';
import ttf2svg from './ttf2svg';
import ttf2symbol from './ttf2symbol';

import ttf2base64 from './ttf2base64';
import eot2base64 from './eot2base64';
import woff2base64 from './woff2base64';
import svg2base64 from './svg2base64';
import bytes2base64 from './util/bytes2base64';
import woff2tobase64 from './woff2tobase64';

import optimizettf from './util/optimizettf';

const SUPPORT_BUFFER =
  typeof process === 'object' &&
  typeof process.versions === 'object' &&
  typeof process.versions.node !== 'undefined' &&
  typeof Buffer === 'function';

class Font {
    constructor(buffer, options = { type: 'ttf' }) {
        if (typeof buffer === 'object' && buffer.glyf) {
            this.set(buffer);
        }
        else if (buffer) {
            this.read(buffer, options);
        }
        else {
            this.readEmpty();
        }
    }

    static create(buffer, options) {
        return new Font(buffer, options);
    }

    readEmpty() {
        this.data = getEmptyttfObject();
        return this;
    }

    read(buffer, options) {
        if (SUPPORT_BUFFER) {
            if (buffer instanceof Buffer) {
                buffer = bufferTool.toArrayBuffer(buffer);
            }
        }

        if (options.type === 'ttf') {
            this.data = new TTFReader(options).read(buffer);
        } else if (options.type === 'otf') {
            this.data = otf2ttfobject(buffer, options);
        } else if (options.type === 'eot') {
            buffer = eot2ttf(buffer, options);
            this.data = new TTFReader(options).read(buffer);
        } else if (options.type === 'woff') {
            buffer = woff2ttf(buffer, options);
            this.data = new TTFReader(options).read(buffer);
        } else if (options.type === 'woff2') {
            throw new Error('woff2 read is not supported in the bundled browser build');
        } else if (options.type === 'svg') {
            this.data = svg2ttfobject(buffer, options);
        } else {
            throw new Error('not support font type' + options.type);
        }

        this.type = options.type;
        return this;
    }

    write(options = {}) {
        if (!options.type) {
            options.type = this.type;
        }

        let buffer = null;
        if (options.type === 'ttf') {
            buffer = new TTFWriter(options).write(this.data);
        } else if (options.type === 'eot') {
            buffer = new TTFWriter(options).write(this.data);
            buffer = ttf2eot(buffer, options);
        } else if (options.type === 'woff') {
            buffer = new TTFWriter(options).write(this.data);
            buffer = ttf2woff(buffer, options);
        } else if (options.type === 'woff2') {
            throw new Error('woff2 write is not supported in the bundled browser build');
        } else if (options.type === 'svg') {
            buffer = ttf2svg(this.data, options);
        } else if (options.type === 'symbol') {
            buffer = ttf2symbol(this.data, options);
        } else {
            throw new Error('not support font type' + options.type);
        }

        if (SUPPORT_BUFFER) {
            if (false !== options.toBuffer && buffer instanceof ArrayBuffer) {
                buffer = bufferTool.toBuffer(buffer);
            }
        }

        return buffer;
    }

    toBase64(options, buffer) {
        if (!options.type) {
            options.type = this.type;
        }

        if (buffer) {
            if (SUPPORT_BUFFER) {
                if (buffer instanceof Buffer) {
                    buffer = bufferTool.toArrayBuffer(buffer);
                }
            }
        } else {
            options.toBuffer = false;
            buffer = this.write(options);
        }

        let base64Str;
        if (options.type === 'ttf') {
            base64Str = ttf2base64(buffer);
        } else if (options.type === 'eot') {
            base64Str = eot2base64(buffer);
        } else if (options.type === 'woff') {
            base64Str = woff2base64(buffer);
        } else if (options.type === 'woff2') {
            base64Str = woff2tobase64(buffer);
        } else if (options.type === 'svg') {
            base64Str = svg2base64(buffer);
        } else if (options.type === 'symbol') {
            base64Str = svg2base64(buffer, 'image/svg+xml');
        } else {
            throw new Error('not support font type' + options.type);
        }

        return base64Str;
    }

    set(data) {
        this.data = data;
        return this;
    }

    get() {
        return this.data;
    }

    optimize(out) {
        const result = optimizettf(this.data);
        if (out) {
            out.result = result;
        }
        return this;
    }

    compound2simple() {
        const ttfHelper = this.getHelper();
        ttfHelper.compound2simple();
        this.data = ttfHelper.get();
        return this;
    }

    sort() {
        const ttfHelper = this.getHelper();
        ttfHelper.sortGlyf();
        this.data = ttfHelper.get();
        return this;
    }

    find(condition) {
        const ttfHelper = this.getHelper();
        const indexList = ttfHelper.findGlyf(condition);
        return indexList.length ? ttfHelper.getGlyf(indexList) : indexList;
    }

    merge(font, options) {
        const ttfHelper = this.getHelper();
        ttfHelper.mergeGlyf(font.get(), options);
        this.data = ttfHelper.get();
        return this;
    }

    getHelper() {
        return new TTF(this.data);
    }
}

Font.toBase64 = function (buffer) {
    if (typeof buffer === 'string') {
        if (typeof btoa === 'undefined') {
            return Buffer.from(buffer, 'binary').toString('base64');
        }

        return btoa(buffer);
    }
    return bytes2base64(buffer);
};

function createFont(buffer, options) {
    return new Font(buffer, options);
}

export {Font, createFont};

export default Font;
