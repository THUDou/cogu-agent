
import Directory from './table/directory';
import supportTables from './table/support-otf';
import Reader from './reader';
import error from './error';

export default class OTFReader {

    constructor(options = {}) {
        options.subset = options.subset || [];
        this.options = options;
    }

    readBuffer(buffer) {

        const reader = new Reader(buffer, 0, buffer.byteLength, false);
        const font = {};

        font.version = reader.readString(0, 4);

        if (font.version !== 'OTTO') {
            error.raise(10301);
        }

        font.numTables = reader.readUint16();

        if (font.numTables <= 0 || font.numTables > 100) {
            error.raise(10302);
        }

        font.searchRange = reader.readUint16();

        font.entrySelector = reader.readUint16();

        font.rangeShift = reader.readUint16();

        font.tables = new Directory(reader.offset).read(reader, font);

        if (!font.tables.head || !font.tables.cmap || !font.tables.CFF) {
            error.raise(10302);
        }

        font.readOptions = this.options;

        Object.keys(supportTables).forEach((tableName) => {
            if (font.tables[tableName]) {
                const offset = font.tables[tableName].offset;
                font[tableName] = new supportTables[tableName](offset).read(reader, font);
            }
        });

        if (!font.CFF.glyf) {
            error.raise(10303);
        }

        reader.dispose();

        return font;
    }

    resolveGlyf(font) {

        const codes = font.cmap;
        let glyf = font.CFF.glyf;
        const subsetMap = font.readOptions.subset ? font.subsetMap : null; // 当前ttf的子集列表
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

        font.hmtx.forEach((item, i) => {
            if (subsetMap && !subsetMap[i]) {
                return;
            }
            glyf[i].advanceWidth = glyf[i].advanceWidth || item.advanceWidth || 0;
            glyf[i].leftSideBearing = item.leftSideBearing;
        });

        if (subsetMap) {
            const subGlyf = [];
            Object.keys(subsetMap).forEach((i) => {
                subGlyf.push(glyf[+i]);
            });
            glyf = subGlyf;
        }

        font.glyf = glyf;
    }

    cleanTables(font) {
        delete font.readOptions;
        delete font.tables;
        delete font.hmtx;
        delete font.post.glyphNameIndex;
        delete font.post.names;
        delete font.subsetMap;

        const cff = font.CFF;
        delete cff.glyf;
        delete cff.charset;
        delete cff.encoding;
        delete cff.gsubrs;
        delete cff.gsubrsBias;
        delete cff.subrs;
        delete cff.subrsBias;
    }

    read(buffer) {
        this.font = this.readBuffer(buffer);
        this.resolveGlyf(this.font);
        this.cleanTables(this.font);
        return this.font;
    }

    dispose() {
        delete this.font;
        delete this.options;
    }
}
