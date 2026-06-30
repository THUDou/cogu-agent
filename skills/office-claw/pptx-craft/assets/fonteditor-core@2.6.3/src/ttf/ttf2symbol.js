
import string from '../common/string';
import TTFReader from './ttfreader';
import contours2svg from './util/contours2svg';
import pathsUtil from '../graphics/pathsUtil';
import error from './error';

const XML_TPL = ''
    + '<svg style="position: absolute; width: 0; height: 0;" width="0" height="0" version="1.1"'
    + ' xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">'
    + '<defs>${symbolList}</defs>'
    + '</svg>';

const SYMBOL_TPL = ''
    + '<symbol id="${id}" viewBox="0 ${descent} ${unitsPerEm} ${unitsPerEm}">'
    + '<path d="${d}"></path>'
    + '</symbol>';


export function getSymbolId(glyf, index) {
    if (glyf.name) {
        return glyf.name;
    }

    if (glyf.unicode && glyf.unicode.length) {
        return 'uni-' + glyf.unicode[0];
    }
    return 'symbol-' + index;
}

function ttfobject2symbol(ttf, options = {}) {
    const xmlObject = {};
    const unitsPerEm = ttf.head.unitsPerEm;
    const descent = ttf.hhea.descent;
    let symbolList = '';
    for (let i = 1, l = ttf.glyf.length; i < l; i++) {
        const glyf = ttf.glyf[i];
        if (!glyf.compound && glyf.contours) {
            const contours = pathsUtil.flip(glyf.contours);
            const glyfObject = {
                descent,
                unitsPerEm,
                id: getSymbolId(glyf, i),
                d: contours2svg(contours)
            };
            symbolList += string.format(SYMBOL_TPL, glyfObject);
        }
    }
    xmlObject.symbolList = symbolList;
    return string.format(XML_TPL, xmlObject);
}


export default function ttf2symbol(ttfBuffer, options = {}) {

    if (ttfBuffer instanceof ArrayBuffer) {
        const reader = new TTFReader();
        const ttfObject = reader.read(ttfBuffer);
        reader.dispose();

        return ttfobject2symbol(ttfObject, options);
    }
    else if (ttfBuffer.version && ttfBuffer.glyf) {

        return ttfobject2symbol(ttfBuffer, options);
    }

    error.raise(10112);
}
