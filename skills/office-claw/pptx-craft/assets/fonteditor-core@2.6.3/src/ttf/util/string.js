
import unicodeName from '../enum/unicodeName';
import postName from '../enum/postName';

function stringify(str) {
    if (!str) {
        return str;
    }

    let newStr = '';
    for (let i = 0, l = str.length, ch; i < l; i++) {
        ch = str.charCodeAt(i);
        if (ch === 0) {
            continue;
        }
        newStr += String.fromCharCode(ch);
    }
    return newStr;
}

export default {

    stringify,

    escape(str) {
        if (!str) {
            return str;
        }
        return String(str).replace(/[\uff-\uffff]/g, c => escape(c).replace('%', '\\'));
    },

    getString(bytes) {
        let s = '';
        for (let i = 0, l = bytes.length; i < l; i++) {
            s += String.fromCharCode(bytes[i]);
        }
        return s;
    },

    getUnicodeName(unicode) {
        const unicodeNameIndex = unicodeName[unicode];
        if (undefined !== unicodeNameIndex) {
            return postName[unicodeNameIndex];
        }

        return 'uni' + unicode.toString(16).toUpperCase();
    },

    toUTF8Bytes(str) {
        str = stringify(str);
        const byteArray = [];
        for (let i = 0, l = str.length; i < l; i++) {
            if (str.charCodeAt(i) <= 0x7F) {
                byteArray.push(str.charCodeAt(i));
            }
            else {
                const codePoint = str.codePointAt(i);
                if (codePoint > 0xffff) {
                    i++;
                }
                const h = encodeURIComponent(String.fromCodePoint(codePoint)).slice(1).split('%');
                for (let j = 0; j < h.length; j++) {
                    byteArray.push(parseInt(h[j], 16));
                }
            }
        }
        return byteArray;
    },

    toUCS2Bytes(str) {
        str = stringify(str);
        const byteArray = [];

        for (let i = 0, l = str.length, ch; i < l; i++) {
            ch = str.charCodeAt(i);
            byteArray.push(ch >> 8);
            byteArray.push(ch & 0xFF);
        }

        return byteArray;
    },


    toPascalStringBytes(str) {
        const bytes = [];
        const length = str ? (str.length < 256 ? str.length : 255) : 0;
        bytes.push(length);

        for (let i = 0, l = str.length; i < l; i++) {
            const c = str.charCodeAt(i);
            bytes.push(c < 128 ? c : 42);
        }

        return bytes;
    },

    getUTF8String(bytes) {
        let str = '';
        for (let i = 0, l = bytes.length; i < l; i++) {
            if (bytes[i] < 0x7F) {
                str += String.fromCharCode(bytes[i]);
            }
            else {
                str += '%' + (256 + bytes[i]).toString(16).slice(1);
            }
        }

        return unescape(str);
    },

    getUCS2String(bytes) {
        let str = '';
        for (let i = 0, l = bytes.length; i < l; i += 2) {
            str += String.fromCharCode((bytes[i] << 8) + bytes[i + 1]);
        }
        return str;
    },

    getPascalString(byteArray) {
        const strArray = [];
        let i = 0;
        const l = byteArray.length;

        while (i < l) {
            let strLength = byteArray[i++];
            let str = '';

            while (strLength-- > 0 && i < l) {
                str += String.fromCharCode(byteArray[i++]);
            }
            str = stringify(str);
            strArray.push(str);
        }

        return strArray;
    }
};
