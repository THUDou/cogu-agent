
import table from './table';
import parse from './glyf/parse';
import write from './glyf/write';
import sizeof from './glyf/sizeof';
import {isEmptyObject} from '../../common/lang';

export default table.create(
    'glyf',
    [],
    {

        read(reader, ttf) {
            const startOffset = this.offset;
            const loca = ttf.loca;
            const numGlyphs = ttf.maxp.numGlyphs;
            const glyphs = [];

            reader.seek(startOffset);

            const subset = ttf.readOptions.subset;

            if (subset && subset.length > 0) {
                const subsetMap = {
                    0: true // 设置.notdef
                };
                subsetMap[0] = true;
                const cmap = ttf.cmap;

                Object.keys(cmap).forEach((c) => {
                    if (subset.indexOf(+c) > -1) {
                        const i = cmap[c];
                        subsetMap[i] = true;
                    }
                });
                ttf.subsetMap = subsetMap;
                const parsedGlyfMap = {};
                const travelsParse = function travels(subsetMap) {
                    const newSubsetMap = {};
                    Object.keys(subsetMap).forEach((i) => {
                        const index = +i;
                        parsedGlyfMap[index] = true;
                        if (loca[index] === loca[index + 1]) {
                            glyphs[index] = {
                                contours: []
                            };
                        }
                        else {
                            glyphs[index] = parse(reader, ttf, startOffset + loca[index]);
                        }

                        if (glyphs[index].compound) {
                            glyphs[index].glyfs.forEach((g) => {
                                if (!parsedGlyfMap[g.glyphIndex]) {
                                    newSubsetMap[g.glyphIndex] = true;
                                }
                            });
                        }
                    });

                    if (!isEmptyObject(newSubsetMap)) {
                        travels(newSubsetMap);
                    }
                };

                travelsParse(subsetMap);
                return glyphs;
            }

            let i;
            let l;
            for (i = 0, l = numGlyphs - 1; i < l; i++) {
                if (loca[i] === loca[i + 1]) {
                    glyphs[i] = {
                        contours: []
                    };
                }
                else {
                    glyphs[i] = parse(reader, ttf, startOffset + loca[i]);
                }
            }

            if ((ttf.tables.glyf.length - loca[i]) < 5) {
                glyphs[i] = {
                    contours: []
                };
            }
            else {
                glyphs[i] = parse(reader, ttf, startOffset + loca[i]);
            }

            return glyphs;
        },

        write,
        size: sizeof
    }
);
