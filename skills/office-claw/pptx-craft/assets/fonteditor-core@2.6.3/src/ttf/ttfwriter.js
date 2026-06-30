
import Writer from './writer';
import Directory from './table/directory';
import supportTables from './table/support';
import checkSum from './util/checkSum';
import error from './error';

const SUPPORT_TABLES = [
    'OS/2',
    'cmap',
    'glyf',
    'head',
    'hhea',
    'hmtx',
    'loca',
    'maxp',
    'name',
    'post'
];

export default class TTFWriter {
    constructor(options = {}) {
        this.options = {
            writeZeroContoursGlyfData: options.writeZeroContoursGlyfData || false, // 不写入空 glyf 数据
            hinting: options.hinting || false, // 默认不保留hints信息
            kerning: options.kerning || false, // 默认不保留 kernings space 信息
            support: options.support // 自定义的导出表结构，可以自己修改某些表项目
        };
    }

    resolveTTF(ttf) {

        ttf.version = ttf.version || 0x1;
        ttf.numTables = ttf.writeOptions.tables.length;
        ttf.entrySelector = Math.floor(Math.log(ttf.numTables) / Math.LN2);
        ttf.searchRange = Math.pow(2, ttf.entrySelector) * 16;
        ttf.rangeShift = ttf.numTables * 16 - ttf.searchRange;

        ttf.head.checkSumAdjustment = 0;
        ttf.head.magickNumber = 0x5F0F3CF5;

        if (typeof ttf.head.created === 'string') {
            ttf.head.created = /^\d+$/.test(ttf.head.created)
                ? +ttf.head.created : Date.parse(ttf.head.created);
        }
        if (typeof ttf.head.modified === 'string') {
            ttf.head.modified = /^\d+$/.test(ttf.head.modified)
                ? +ttf.head.modified : Date.parse(ttf.head.modified);
        }
        if (!ttf.head.created) {
            ttf.head.created = Date.now();
        }
        if (!ttf.head.modified) {
            ttf.head.modified = ttf.head.created;
        }

        const checkUnicodeRepeat = {}; // 检查是否有重复代码点

        ttf.glyf.forEach((glyf, index) => {
            if (glyf.unicode) {
                glyf.unicode = glyf.unicode.sort();

                glyf.unicode.forEach((u) => {
                    if (checkUnicodeRepeat[u]) {
                        error.raise({
                            number: 10200,
                            data: index
                        }, index);
                    }
                    else {
                        checkUnicodeRepeat[u] = true;
                    }
                });

            }
        });
    }

    dump(ttf) {

        ttf.support = Object.assign({}, this.options.support);

        let ttfSize = 12 + ttf.numTables * 16;
        let ttfHeadOffset = 0; // 记录head的偏移

        ttf.support.tables = [];
        ttf.writeOptions.tables.forEach((tableName) => {
            const offset = ttfSize;
            const TableClass = supportTables[tableName];
            const tableSize = new TableClass().size(ttf); // 原始的表大小
            let size = tableSize; // 对齐后的表大小

            if (tableName === 'head') {
                ttfHeadOffset = offset;
            }

            if (size % 4) {
                size += 4 - size % 4;
            }

            ttf.support.tables.push({
                name: tableName,
                checkSum: 0,
                offset,
                length: tableSize,
                size
            });

            ttfSize += size;
        });

        const writer = new Writer(new ArrayBuffer(ttfSize));

        writer.writeFixed(ttf.version);
        writer.writeUint16(ttf.numTables);
        writer.writeUint16(ttf.searchRange);
        writer.writeUint16(ttf.entrySelector);
        writer.writeUint16(ttf.rangeShift);

        new Directory().write(writer, ttf);

        ttf.support.tables.forEach((table) => {

            const tableStart = writer.offset;
            const TableClass = supportTables[table.name];
            new TableClass().write(writer, ttf);

            if (table.length % 4) {
                writer.writeEmpty(4 - table.length % 4);
            }

            table.checkSum = checkSum(writer.getBuffer(), tableStart, table.size);

        });

        ttf.support.tables.forEach((table, index) => {
            const offset = 12 + index * 16 + 4;
            writer.writeUint32(table.checkSum, offset);
        });

        const ttfCheckSum = (0xB1B0AFBA - checkSum(writer.getBuffer()) + 0x100000000) % 0x100000000;
        writer.writeUint32(ttfCheckSum, ttfHeadOffset + 8);

        delete ttf.writeOptions;
        delete ttf.support;

        const buffer = writer.getBuffer();
        writer.dispose();

        return buffer;
    }

    prepareDump(ttf) {

        if (!ttf.glyf || ttf.glyf.length === 0) {
            error.raise(10201);
        }

        if (!ttf['OS/2'] || !ttf.head || !ttf.name) {
            error.raise(10204);
        }


        const tables = SUPPORT_TABLES.slice(0);
        ttf.writeOptions = {};
        if (this.options.hinting) {
            ['cvt', 'fpgm', 'prep', 'gasp', 'GPOS', 'kern', 'kerx'].forEach((table) => {
                if (ttf[table]) {
                    tables.push(table);
                }
            });
        }
        if (this.options.kerning) {
            ['GPOS', 'kern', 'kerx'].forEach((table) => {
                if (ttf[table]) {
                    tables.push(table);
                }
            });
        }
        ttf.writeOptions.writeZeroContoursGlyfData = !!this.options.writeZeroContoursGlyfData;
        ttf.writeOptions.hinting = !!this.options.hinting;
        ttf.writeOptions.kerning = !!this.options.kerning;
        ttf.writeOptions.tables = tables.sort();
    }

    write(ttf) {
        this.prepareDump(ttf);
        this.resolveTTF(ttf);
        const buffer = this.dump(ttf);
        return buffer;
    }

    dispose() {
        delete this.options;
    }
}
