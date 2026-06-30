
import {overwrite} from '../common/lang';
import string from './util/string';
import pathAdjust from '../graphics/pathAdjust';
import pathCeil from '../graphics/pathCeil';
import {computePath, computePathBox} from '../graphics/computeBoundingBox';
import compound2simpleglyf from './util/compound2simpleglyf';
import glyfAdjust from './util/glyfAdjust';
import optimizettf from './util/optimizettf';
import config from './data/default';

function adjustToEmBox(glyfList, ascent, descent, adjustToEmPadding) {

    glyfList.forEach((g) => {

        if (g.contours && g.contours.length) {
            const rightSideBearing = g.advanceWidth - g.xMax;
            const bound = computePath(...g.contours);
            const scale = (ascent - descent - adjustToEmPadding) / bound.height;
            const center = (ascent + descent) / 2;
            const yOffset = center - (bound.y + bound.height / 2) * scale;

            g.contours.forEach((contour) => {
                if (scale !== 1) {
                    pathAdjust(contour, scale, scale);
                }

                pathAdjust(contour, 1, 1, 0, yOffset);
                pathCeil(contour);
            });

            const box = computePathBox(...g.contours);

            g.xMin = box.x;
            g.xMax = box.x + box.width;
            g.yMin = box.y;
            g.yMax = box.y + box.height;

            g.leftSideBearing = g.xMin;
            g.advanceWidth = g.xMax + rightSideBearing;

        }

    });

    return glyfList;
}

function adjustPos(glyfList, leftSideBearing, rightSideBearing, verticalAlign) {

    let changed = false;

    if (null != leftSideBearing) {
        changed = true;

        glyfList.forEach((g) => {
            if (g.leftSideBearing !== leftSideBearing) {
                glyfAdjust(g, 1, 1, leftSideBearing - g.leftSideBearing);
            }
        });
    }

    if (null != rightSideBearing) {
        changed = true;

        glyfList.forEach((g) => {
            g.advanceWidth = g.xMax + rightSideBearing;
        });
    }

    if (null != verticalAlign) {
        changed = true;

        glyfList.forEach(g => {
            if (g.contours && g.contours.length) {
                const bound = computePath(...g.contours);
                const offset = verticalAlign - bound.y;
                glyfAdjust(g, 1, 1, 0, offset);
            }
        });
    }

    return changed ? glyfList : [];
}



function merge(ttf, imported, options = {scale: true}) {

    const list = imported.glyf.filter((g) =>
        g.contours && g.contours.length
            && g.name !== '.notdef' && g.name !== '.null' && g.name !== 'nonmarkingreturn'
    );

    if (options.adjustGlyf) {
        const ascent = ttf.hhea.ascent;
        const descent = ttf.hhea.descent;
        const adjustToEmPadding = 16;
        adjustPos(list, 16, 16);
        adjustToEmBox(list, ascent, descent, adjustToEmPadding);

        list.forEach((g) => {
            ttf.glyf.push(g);
        });
    }
    else if (options.scale) {

        let scale = 1;

        if (imported.head.unitsPerEm && imported.head.unitsPerEm !== ttf.head.unitsPerEm) {
            scale = ttf.head.unitsPerEm / imported.head.unitsPerEm;
        }

        list.forEach((g) => {
            glyfAdjust(g, scale, scale);
            ttf.glyf.push(g);
        });
    }

    return list;
}

export default class TTF {

    constructor(ttf) {
        this.ttf = ttf;
    }

    codes() {
        return Object.keys(this.ttf.cmap);
    }

    getGlyfIndexByCode(c) {
        const charCode = typeof c === 'number' ? c : c.codePointAt(0);
        const glyfIndex = this.ttf.cmap[charCode] || -1;
        return glyfIndex;
    }

    getGlyfByIndex(glyfIndex) {
        const glyfList = this.ttf.glyf;
        const glyf = glyfList[glyfIndex];
        return glyf;
    }

    getGlyfByCode(c) {
        const glyfIndex = this.getGlyfIndexByCode(c);
        return this.getGlyfByIndex(glyfIndex);
    }

    set(ttf) {
        this.ttf = ttf;
        return this;
    }

    get() {
        return this.ttf;
    }

    addGlyf(glyf) {
        return this.insertGlyf(glyf);
    }

    insertGlyf(glyf, insertIndex) {
        if (insertIndex >= 0 && insertIndex < this.ttf.glyf.length) {
            this.ttf.glyf.splice(insertIndex, 0, glyf);
        }
        else {
            this.ttf.glyf.push(glyf);
        }

        return [glyf];
    }

    mergeGlyf(imported, options) {
        const list = merge(this.ttf, imported, options);
        return list;
    }


    removeGlyf(indexList) {
        const glyf = this.ttf.glyf;
        const removed = [];
        for (let i = glyf.length - 1; i >= 0; i--) {
            if (indexList.indexOf(i) >= 0) {
                removed.push(glyf[i]);
                glyf.splice(i, 1);
            }
        }
        return removed;
    }


    setUnicode(unicode, indexList, isGenerateName) {
        const glyf = this.ttf.glyf;
        let list = [];
        if (indexList && indexList.length) {
            const first = indexList.indexOf(0);
            if (first >= 0) {
                indexList.splice(first, 1);
            }
            list = indexList.map((item) => glyf[item]);
        }
        else {
            list = glyf.slice(1);
        }

        if (list.length > 1) {
            const less32 = function (u) {
                return u < 33;
            };
            list = list.filter((g) => !g.unicode || !g.unicode.some(less32));
        }

        if (list.length) {
            unicode = Number('0x' + unicode.slice(1));
            list.forEach((g) => {
                if (unicode === 0xA0 || unicode === 0x3000) {
                    unicode++;
                }

                g.unicode = [unicode];

                if (isGenerateName) {
                    g.name = string.getUnicodeName(unicode);
                }
                unicode++;
            });
        }

        return list;
    }

    genGlyfName(indexList) {
        const glyf = this.ttf.glyf;
        let list = [];
        if (indexList && indexList.length) {
            list = indexList.map((item) => glyf[item]);
        }
        else {
            list = glyf;
        }

        if (list.length) {
            const first = this.ttf.glyf[0];

            list.forEach((g) => {
                if (g === first) {
                    g.name = '.notdef';
                }
                else if (g.unicode && g.unicode.length) {
                    g.name = string.getUnicodeName(g.unicode[0]);
                }
                else {
                    g.name = '.notdef';
                }
            });
        }

        return list;
    }

    clearGlyfName(indexList) {
        const glyf = this.ttf.glyf;
        let list = [];
        if (indexList && indexList.length) {
            list = indexList.map((item) => glyf[item]);
        }
        else {
            list = glyf;
        }

        if (list.length) {

            list.forEach((g) => {
                delete g.name;
            });
        }

        return list;
    }

    appendGlyf(glyfList, indexList) {
        const glyf = this.ttf.glyf;
        const result = glyfList.slice(0);

        if (indexList && indexList.length) {
            const l = Math.min(glyfList.length, indexList.length);
            for (let i = 0; i < l; i++) {
                glyf[indexList[i]] = glyfList[i];
            }
            glyfList = glyfList.slice(l);
        }

        if (glyfList.length) {
            Array.prototype.splice.apply(glyf, [glyf.length, 0, ...glyfList]);
        }

        return result;
    }


    adjustGlyfPos(indexList, setting) {

        const glyfList = this.getGlyf(indexList);
        return adjustPos(
            glyfList,
            setting.leftSideBearing,
            setting.rightSideBearing,
            setting.verticalAlign
        );
    }


    adjustGlyf(indexList, setting) {

        const glyfList = this.getGlyf(indexList);
        let changed = false;
        setting.adjustToEmBox = setting.ajdustToEmBox || setting.adjustToEmBox;
        setting.adjustToEmPadding = setting.ajdustToEmPadding || setting.adjustToEmPadding;

        if (setting.reverse || setting.mirror) {

            changed = true;

            glyfList.forEach((g) => {
                if (g.contours && g.contours.length) {
                    const offsetX = g.xMax + g.xMin;
                    const offsetY = g.yMax + g.yMin;
                    g.contours.forEach((contour) => {
                        pathAdjust(contour, setting.mirror ? -1 : 1, setting.reverse ? -1 : 1);
                        pathAdjust(contour, 1, 1, setting.mirror ? offsetX : 0, setting.reverse ? offsetY : 0);
                    });
                }
            });
        }


        if (setting.scale && setting.scale !== 1) {

            changed = true;

            const scale = setting.scale;
            glyfList.forEach((g) => {
                if (g.contours && g.contours.length) {
                    glyfAdjust(g, scale, scale);
                }
            });
        }
        else if (setting.adjustToEmBox) {

            changed = true;
            const ascent = this.ttf.hhea.ascent;
            const descent = this.ttf.hhea.descent;
            const adjustToEmPadding = 2 * (setting.adjustToEmPadding || 0);

            adjustToEmBox(glyfList, ascent, descent, adjustToEmPadding);
        }

        return changed ? glyfList : [];
    }

    getGlyf(indexList) {
        const glyf = this.ttf.glyf;
        if (indexList && indexList.length) {
            return indexList.map((item) => glyf[item]);
        }

        return glyf;
    }


    findGlyf(condition) {
        if (!condition) {
            return [];
        }


        const filters = [];

        if (condition.unicode) {
            const unicodeList = Array.isArray(condition.unicode) ? condition.unicode : [condition.unicode];
            const unicodeHash = {};
            unicodeList.forEach((unicode) => {
                if (typeof unicode === 'string') {
                    unicode = Number('0x' + unicode.slice(1));
                }
                unicodeHash[unicode] = true;
            });

            filters.push((glyf) => {
                if (!glyf.unicode || !glyf.unicode.length) {
                    return false;
                }

                for (let i = 0, l = glyf.unicode.length; i < l; i++) {
                    if (unicodeHash[glyf.unicode[i]]) {
                        return true;
                    }
                }
            });
        }

        if (condition.name) {
            const name = condition.name;
            filters.push((glyf) => glyf.name && glyf.name.indexOf(name) === 0);
        }

        if (typeof condition.filter === 'function') {
            filters.push(condition.filter);
        }

        const indexList = [];
        this.ttf.glyf.forEach((glyf, index) => {
            for (let filterIndex = 0, filter; (filter = filters[filterIndex++]);) {
                if (true === filter(glyf)) {
                    indexList.push(index);
                    break;
                }
            }
        });

        return indexList;
    }


    replaceGlyf(glyf, index) {
        if (index >= 0 && index < this.ttf.glyf.length) {
            this.ttf.glyf[index] = glyf;
            return [glyf];
        }
        return [];
    }

    setGlyf(glyfList) {
        delete this.glyf;
        this.ttf.glyf = glyfList || [];
        return this.ttf.glyf;
    }

    sortGlyf() {
        const glyf = this.ttf.glyf;
        if (glyf.length > 1) {

            if (glyf.some((a) => a.compound)) {
                return -2;
            }

            const notdef = glyf.shift();
            glyf.sort((a, b) => {
                if ((!a.unicode || !a.unicode.length) && (!b.unicode || !b.unicode.length)) {
                    return 0;
                }
                else if ((!a.unicode || !a.unicode.length) && b.unicode) {
                    return 1;
                }
                else if (a.unicode && (!b.unicode || !b.unicode.length)) {
                    return -1;
                }
                return Math.min.apply(null, a.unicode) - Math.min.apply(null, b.unicode);
            });

            glyf.unshift(notdef);
            return glyf;
        }

        return -1;
    }



    setName(name) {

        if (name) {
            this.ttf.name.fontFamily = this.ttf.name.fullName = name.fontFamily || config.name.fontFamily;
            this.ttf.name.fontSubFamily = name.fontSubFamily || config.name.fontSubFamily;
            this.ttf.name.uniqueSubFamily = name.uniqueSubFamily || '';
            this.ttf.name.postScriptName = name.postScriptName || '';
        }

        return this.ttf.name;
    }

    setHead(head) {
        if (head) {
            if (head.unitsPerEm && head.unitsPerEm >= 64 && head.unitsPerEm <= 16384) {
                this.ttf.head.unitsPerEm = head.unitsPerEm;
            }

            if (head.lowestRecPPEM && head.lowestRecPPEM >= 8 && head.lowestRecPPEM <= 16384) {
                this.ttf.head.lowestRecPPEM = head.lowestRecPPEM;
            }
            if (head.created) {
                this.ttf.head.created = head.created;
            }
            if (head.modified) {
                this.ttf.head.modified = head.modified;
            }
        }
        return this.ttf.head;
    }

    setHhea(fields) {
        overwrite(this.ttf.hhea, fields, ['ascent', 'descent', 'lineGap']);
        return this.ttf.hhea;
    }

    setOS2(fields) {
        overwrite(
            this.ttf['OS/2'], fields,
            [
                'usWinAscent', 'usWinDescent',
                'sTypoAscender', 'sTypoDescender', 'sTypoLineGap',
                'sxHeight', 'bXHeight', 'usWeightClass', 'usWidthClass',
                'yStrikeoutPosition', 'yStrikeoutSize',
                'achVendID',
                'bFamilyType', 'bSerifStyle', 'bWeight', 'bProportion', 'bContrast',
                'bStrokeVariation', 'bArmStyle', 'bLetterform', 'bMidline', 'bXHeight'
            ]
        );
        return this.ttf['OS/2'];
    }

    setPost(fields) {
        overwrite(
            this.ttf.post, fields,
            [
                'underlinePosition', 'underlineThickness'
            ]
        );
        return this.ttf.post;
    }


    calcMetrics() {
        let ascent = -16384;
        let descent = 16384;
        const uX = 0x78;
        const uH = 0x48;
        let sxHeight;
        let sCapHeight;
        this.ttf.glyf.forEach((g) => {

            if (g.yMax > ascent) {
                ascent = g.yMax;
            }

            if (g.yMin < descent) {
                descent = g.yMin;
            }

            if (g.unicode) {
                if (g.unicode.indexOf(uX) >= 0) {
                    sxHeight = g.yMax;
                }
                if (g.unicode.indexOf(uH) >= 0) {
                    sCapHeight = g.yMax;
                }
            }
        });

        ascent = Math.round(ascent);
        descent = Math.round(descent);

        return {

            ascent,
            descent,
            sTypoAscender: ascent,
            sTypoDescender: descent,

            usWinAscent: ascent,
            usWinDescent: -descent,
            sxHeight: sxHeight || 0,
            sCapHeight: sCapHeight || 0
        };
    }


    optimize() {
        return optimizettf(this.ttf);
    }

    compound2simple(indexList) {

        const ttf = this.ttf;
        if (ttf.maxp && !ttf.maxp.maxComponentElements) {
            return [];
        }

        let i;
        let l;
        if (!indexList || !indexList.length) {
            indexList = [];
            for (i = 0, l = ttf.glyf.length; i < l; ++i) {
                if (ttf.glyf[i].compound) {
                    indexList.push(i);
                }
            }
        }

        const list = [];
        for (i = 0, l = indexList.length; i < l; ++i) {
            const glyfIndex = indexList[i];
            if (ttf.glyf[glyfIndex] && ttf.glyf[glyfIndex].compound) {
                compound2simpleglyf(glyfIndex, ttf, true);
                list.push(ttf.glyf[glyfIndex]);
            }
        }

        return list;
    }
}
