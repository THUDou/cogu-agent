
import string from '../common/string';
import DOMParser from '../common/DOMParser';
import path2contours from './svg/path2contours';
import svgnode2contours from './svg/svgnode2contours';
import {computePathBox} from '../graphics/computeBoundingBox';
import pathsUtil from '../graphics/pathsUtil';
import glyfAdjust from './util/glyfAdjust';
import error from './error';
import getEmptyttfObject from './getEmptyttfObject';
import reduceGlyf from './util/reduceGlyf';

function loadXML(xml) {
    if (DOMParser) {
        try {
            const domParser = new DOMParser();
            const xmlDoc = domParser.parseFromString(xml, 'text/xml');
            return xmlDoc;
        }
        catch (exp) {
            error.raise(10103);
        }
    }
    error.raise(10004);
}

function resolveSVG(svg) {
    svg = svg.replace(/\s+xmlns(?::[\w-]+)?=("|')[^"']*\1/g, ' ')
        .replace(/<defs[>\s][\s\S]+?\/defs>/g, (text) => {
            if (text.indexOf('</font>') >= 0) {
                return text;
            }
            return '';
        })
        .replace(/<use[>\s][\s\S]+?\/use>/g, '');
    return svg;
}

function getEmptyTTF() {
    const ttf = getEmptyttfObject();
    ttf.head.unitsPerEm = 0; // 去除unitsPerEm以便于重新计算
    ttf.from = 'svgfont';
    return ttf;
}

function getEmptyObject() {
    return {
        'from': 'svg',
        'OS/2': {},
        'name': {},
        'hhea': {},
        'head': {},
        'post': {},
        'glyf': []
    };
}

function getUnitsPerEm(xMin, xMax, yMin, yMax) {
    const seed = Math.ceil(Math.min(yMax - yMin, xMax - xMin));

    if (!seed) {
        return 1024;
    }

    if (seed <= 128) {
        return seed;
    }

    let unitsPerEm = 128;
    while (unitsPerEm < 16384) {

        if (seed <= 1.2 * unitsPerEm) {
            return unitsPerEm;
        }

        unitsPerEm <<= 1;
    }

    return 1024;
}

function resolve(ttf) {


    if (ttf.from === 'svgfont' && ttf.head.unitsPerEm > 128) {
        ttf.glyf.forEach((g) => {
            if (g.contours) {
                glyfAdjust(g);
                reduceGlyf(g);
            }
        });
    }
    else {
        let xMin = 16384;
        let xMax = -16384;
        let yMin = 16384;
        let yMax = -16384;

        ttf.glyf.forEach((g) => {
            if (g.contours) {
                const bound = computePathBox(...g.contours);
                if (bound) {
                    xMin = Math.min(xMin, bound.x);
                    xMax = Math.max(xMax, bound.x + bound.width);
                    yMin = Math.min(yMin, bound.y);
                    yMax = Math.max(yMax, bound.y + bound.height);
                }
            }
        });

        const unitsPerEm = getUnitsPerEm(xMin, xMax, yMin, yMax);
        const scale = 1024 / unitsPerEm;

        ttf.glyf.forEach((g) => {
            glyfAdjust(g, scale, scale);
            reduceGlyf(g);
        });
        ttf.head.unitsPerEm = 1024;
    }

    return ttf;
}

function parseFont(xmlDoc, ttf) {

    const metaNode = xmlDoc.getElementsByTagName('metadata')[0];
    const fontNode = xmlDoc.getElementsByTagName('font')[0];
    const fontFaceNode = xmlDoc.getElementsByTagName('font-face')[0];

    if (metaNode && metaNode.textContent) {
        ttf.metadata = string.decodeHTML(metaNode.textContent.trim());
    }

    if (fontNode) {
        ttf.id = fontNode.getAttribute('id') || '';
        ttf.hhea.advanceWidthMax = +(fontNode.getAttribute('horiz-adv-x') || 0);
        ttf.from = 'svgfont';
    }

    if (fontFaceNode) {
        const OS2 = ttf['OS/2'];
        ttf.name.fontFamily = fontFaceNode.getAttribute('font-family') || '';
        OS2.usWeightClass = +(fontFaceNode.getAttribute('font-weight') || 0);
        ttf.head.unitsPerEm = +(fontFaceNode.getAttribute('units-per-em') || 0);

        const panose = (fontFaceNode.getAttribute('panose-1') || '').split(' ');
        [
            'bFamilyType', 'bSerifStyle', 'bWeight', 'bProportion', 'bContrast',
            'bStrokeVariation', 'bArmStyle', 'bLetterform', 'bMidline', 'bXHeight'
        ].forEach((name, i) => {
            OS2[name] = +(panose[i] || 0);
        });

        ttf.hhea.ascent = +(fontFaceNode.getAttribute('ascent') || 0);
        ttf.hhea.descent = +(fontFaceNode.getAttribute('descent') || 0);
        OS2.bXHeight = +(fontFaceNode.getAttribute('x-height') || 0);

        const box = (fontFaceNode.getAttribute('bbox') || '').split(' ');
        ['xMin', 'yMin', 'xMax', 'yMax'].forEach((name, i) => {
            ttf.head[name] = +(box[i] || '');
        });

        ttf.post.underlineThickness = +(fontFaceNode.getAttribute('underline-thickness') || 0);
        ttf.post.underlinePosition = +(fontFaceNode.getAttribute('underline-position') || 0);

        const unicodeRange = fontFaceNode.getAttribute('unicode-range');
        if (unicodeRange) {
            unicodeRange.replace(/u\+([0-9A-Z]+)(-[0-9A-Z]+)?/i, ($0, a, b) => {
                OS2.usFirstCharIndex = Number('0x' + a);
                OS2.usLastCharIndex = b ? Number('0x' + b.slice(1)) : 0xFFFFFFFF;
            });
        }
    }

    return ttf;
}

function parseGlyf(xmlDoc, ttf) {

    const missingNode = xmlDoc.getElementsByTagName('missing-glyph')[0];

    let d;
    let unicode;
    if (missingNode) {

        const missing = {
            name: '.notdef'
        };

        if (missingNode.getAttribute('horiz-adv-x')) {
            missing.advanceWidth = +missingNode.getAttribute('horiz-adv-x');
        }

        if ((d = missingNode.getAttribute('d'))) {
            missing.contours = path2contours(d);
        }

        if (ttf.glyf[0] && ttf.glyf[0].name === '.notdef') {
            ttf.glyf.splice(0, 1);
        }

        ttf.glyf.unshift(missing);
    }

    const glyfNodes = xmlDoc.getElementsByTagName('glyph');

    if (glyfNodes.length) {


        for (let i = 0, l = glyfNodes.length; i < l; i++) {

            const node = glyfNodes[i];
            const glyf = {
                name: node.getAttribute('glyph-name') || node.getAttribute('name') || ''
            };

            if (node.getAttribute('horiz-adv-x')) {
                glyf.advanceWidth = +node.getAttribute('horiz-adv-x');
            }

            if ((unicode = node.getAttribute('unicode'))) {
                const nextUnicode = [];
                let totalCodePoints = 0;
                for (let ui = 0; ui < unicode.length; ui++) {
                    const ucp = unicode.codePointAt(ui);
                    nextUnicode.push(ucp);
                    ui = ucp > 0xffff ? ui + 1 : ui;
                    totalCodePoints += 1;
                }
                if (totalCodePoints === 1) {
                    glyf.unicode = nextUnicode;

                    if ((d = node.getAttribute('d'))) {
                        glyf.contours = path2contours(d);
                    }
                    ttf.glyf.push(glyf);

                }
            }

        }
    }

    return ttf;
}


function parsePath(xmlDoc, ttf) {

    let contours;
    let glyf;
    let node;
    const pathNodes = xmlDoc.getElementsByTagName('path');

    if (pathNodes.length) {
        for (let i = 0, l = pathNodes.length; i < l; i++) {
            node = pathNodes[i];
            glyf = {
                name: node.getAttribute('name') || ''
            };
            contours = svgnode2contours([node]);
            glyf.contours = contours;
            ttf.glyf.push(glyf);
        }
    }

    contours = svgnode2contours(
        Array.prototype.slice.call(xmlDoc.getElementsByTagName('*')).filter((node) => node.tagName !== 'path')
    );
    if (contours) {
        glyf = {
            name: ''
        };

        glyf.contours = contours;
        ttf.glyf.push(glyf);
    }
}

function parseXML(xmlDoc, options) {

    if (!xmlDoc.getElementsByTagName('svg').length) {
        error.raise(10106);
    }

    let ttf;

    if (xmlDoc.getElementsByTagName('font')[0]) {
        ttf = getEmptyTTF();
        parseFont(xmlDoc, ttf);
        parseGlyf(xmlDoc, ttf);
    }
    else {
        ttf = getEmptyObject();
        parsePath(xmlDoc, ttf);
    }

    if (!ttf.glyf.length) {
        error.raise(10201);
    }

    if (ttf.from === 'svg') {
        const glyf = ttf.glyf;
        let i;
        let l;
        if (options.combinePath) {
            const combined = [];
            for (i = 0, l = glyf.length; i < l; i++) {
                const contours = glyf[i].contours;
                for (let index = 0, length = contours.length; index < length; index++) {
                    combined.push(contours[index]);
                }
            }

            glyf[0].contours = combined;
            glyf.splice(1);
        }

        for (i = 0, l = glyf.length; i < l; i++) {
            glyf[i].contours = pathsUtil.flip(glyf[i].contours);
        }
    }

    return ttf;
}

export default function svg2ttfObject(svg, options = {combinePath: false}) {
    let xmlDoc = svg;
    if (typeof svg === 'string') {
        svg = resolveSVG(svg);
        xmlDoc = loadXML(svg);
    }

    const ttf = parseXML(xmlDoc, options);
    return resolve(ttf);
}
