
import TTFReader from './ttfreader';
import error from './error';
import config from './data/default';
import {getSymbolId} from './ttf2symbol';

function listUnicode(unicode) {
    return unicode.map((u) => '\\' + u.toString(16)).join(',');
}

function ttfobject2icon(ttf, options = {}) {

    const glyfList = [];

    const filtered = ttf.glyf.filter((g) => g.name !== '.notdef'
            && g.name !== '.null'
            && g.name !== 'nonmarkingreturn'
            && g.unicode && g.unicode.length);

    filtered.forEach((g, i) => {
        glyfList.push({
            code: '&#x' + g.unicode[0].toString(16) + ';',
            codeName: listUnicode(g.unicode),
            name: g.name,
            id: getSymbolId(g, i)
        });
    });

    return {
        fontFamily: ttf.name.fontFamily || config.name.fontFamily,
        iconPrefix: options.iconPrefix || 'icon',
        glyfList
    };

}


export default function ttf2icon(ttfBuffer, options = {}) {
    if (ttfBuffer instanceof ArrayBuffer) {
        const reader = new TTFReader();
        const ttfObject = reader.read(ttfBuffer);
        reader.dispose();

        return ttfobject2icon(ttfObject, options);
    }
    else if (ttfBuffer.version && ttfBuffer.glyf) {

        return ttfobject2icon(ttfBuffer, options);
    }

    error.raise(10101);
}
