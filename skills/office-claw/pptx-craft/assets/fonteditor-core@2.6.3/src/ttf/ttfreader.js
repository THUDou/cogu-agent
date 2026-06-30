
import Directory from './table/directory';
import supportTables from './table/support';
import Reader from './reader';
import postName from './enum/postName';
import error from './error';
import compound2simpleglyf from './util/compound2simpleglyf';

export default class TTFReader {

    constructor(options = {}) {
        options.subset = options.subset || []; // 子集
        options.hinting = options.hinting || false; // 默认不保留 hints 信息
        options.kerning = options.kerning || false; // 默认不保留 kerning 信息
        options.compound2simple = options.compound2simple || false; // 复合字形转简单字形
        this.options = options;
    }

    readBuffer(buffer) {

        const reader = new Reader(buffer, 0, buffer.byteLength, false);

        const ttf = {};

        ttf.version = reader.readFixed(0);

        if (ttf.version !== 0x1) {
            error.raise(10101);
        }

        ttf.numTables = reader.readUint16();

        if (ttf.numTables <= 0 || ttf.numTables > 100) {
            error.raise(10101);
        }

        ttf.searchRange = reader.readUint16();

        ttf.entrySelector = reader.readUint16();

        ttf.rangeShift = reader.readUint16();

        ttf.tables = new Directory(reader.offset).read(reader, ttf);

        if (!ttf.tables.glyf || !ttf.tables.head || !ttf.tables.cmap || !ttf.tables.hmtx) {
            error.raise(10204);
        }

        ttf.readOptions = this.options;

        Object.keys(supportTables).forEach((tableName) => {

            if (ttf.tables[tableName]) {
                const offset = ttf.tables[tableName].offset;
                ttf[tableName] = new supportTables[tableName](offset).read(reader, ttf);
            }
        });

        if (!ttf.glyf) {
            error.raise(10201);
        }

        reader.dispose();

        return ttf;
    }

    resolveGlyf(ttf) {
        const codes = ttf.cmap;
        const glyf = ttf.glyf;
        const subsetMap = ttf.readOptions.subset ? ttf.subsetMap : null; // 当前ttf的子集列表

        Object.keys(codes).forEach((c) => {
            const i = codes[c];
            if (subsetMap && !subsetMap[i]) {
                return;
            }
            if (!glyf[i].unicode) {
                glyf[i].unicode = [];
            }
            glyf[i].unicode.push(+c);
        });

        ttf.hmtx.forEach((item, i) => {
            if (subsetMap && !subsetMap[i]) {
                return;
            }
            glyf[i].advanceWidth = item.advanceWidth;
            glyf[i].leftSideBearing = item.leftSideBearing;
        });

        if (ttf.post && 2 === ttf.post.format) {
            const nameIndex = ttf.post.nameIndex;
            const names = ttf.post.names;
            nameIndex.forEach((nameIndex, i) => {
                if (subsetMap && !subsetMap[i]) {
                    return;
                }
                if (nameIndex <= 257) {
                    glyf[i].name = postName[nameIndex];
                }
                else {
                    glyf[i].name = names[nameIndex - 258] || '';
                }
            });
        }

        if (subsetMap) {
            const subGlyf = [];
            Object.keys(subsetMap).forEach((i) => {
                i = +i;
                if (glyf[i].compound) {
                    compound2simpleglyf(i, ttf, true);
                }
                subGlyf.push(glyf[i]);
            });
            ttf.glyf = subGlyf;
            ttf.maxp.maxComponentElements = 0;
            ttf.maxp.maxComponentDepth = 0;
        }
    }

    cleanTables(ttf) {
        delete ttf.readOptions;
        delete ttf.tables;
        delete ttf.hmtx;
        delete ttf.loca;
        if (ttf.post) {
            delete ttf.post.nameIndex;
            delete ttf.post.names;
        }

        delete ttf.subsetMap;

        if (!this.options.hinting) {
            delete ttf.fpgm;
            delete ttf.cvt;
            delete ttf.prep;
            ttf.glyf.forEach((glyf) => {
                delete glyf.instructions;
            });
        }

        if (!this.options.hinting && !this.options.kerning) {
            delete ttf.GPOS;
            delete ttf.kern;
            delete ttf.kerx;
        }

        if (this.options.compound2simple && ttf.maxp.maxComponentElements) {
            ttf.glyf.forEach((glyf, index) => {
                if (glyf.compound) {
                    compound2simpleglyf(index, ttf, true);
                }
            });
            ttf.maxp.maxComponentElements = 0;
            ttf.maxp.maxComponentDepth = 0;
        }
    }

    read(buffer) {
        this.ttf = this.readBuffer(buffer);
        this.resolveGlyf(this.ttf);
        this.cleanTables(this.ttf);
        return this.ttf;
    }

    dispose() {
        delete this.ttf;
        delete this.options;
    }

}
