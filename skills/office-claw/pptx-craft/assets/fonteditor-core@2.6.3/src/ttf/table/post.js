
import table from './table';
import struct from './struct';
import string from '../util/string';
import unicodeName from '../enum/unicodeName';

const Posthead = table.create(
    'posthead',
    [
        ['format', struct.Fixed],
        ['italicAngle', struct.Fixed],
        ['underlinePosition', struct.Int16],
        ['underlineThickness', struct.Int16],
        ['isFixedPitch', struct.Uint32],
        ['minMemType42', struct.Uint32],
        ['maxMemType42', struct.Uint32],
        ['minMemType1', struct.Uint32],
        ['maxMemType1', struct.Uint32]
    ]
);

export default table.create(
    'post',
    [],
    {

        read(reader, ttf) {
            const format = reader.readFixed(this.offset);
            const tbl = new Posthead(this.offset).read(reader, ttf);

            if (format === 2) {
                const numberOfGlyphs = reader.readUint16();
                const glyphNameIndex = [];

                for (let i = 0; i < numberOfGlyphs; ++i) {
                    glyphNameIndex.push(reader.readUint16());
                }

                const pascalStringOffset = reader.offset;
                const pascalStringLength = ttf.tables.post.length - (pascalStringOffset - this.offset);
                const pascalStringBytes = reader.readBytes(reader.offset, pascalStringLength);

                tbl.nameIndex = glyphNameIndex; // 设置glyf名字索引
                tbl.names = string.getPascalString(pascalStringBytes); // glyf名字数组
            }
            else if (format === 2.5) {
                tbl.format = 3;
            }

            return tbl;
        },

        write(writer, ttf) {


            const post = ttf.post || {
                format: 3
            };

            writer.writeFixed(post.format); // format
            writer.writeFixed(post.italicAngle || 0); // italicAngle
            writer.writeInt16(post.underlinePosition || 0); // underlinePosition
            writer.writeInt16(post.underlineThickness || 0); // underlineThickness
            writer.writeUint32(post.isFixedPitch || 0); // isFixedPitch
            writer.writeUint32(post.minMemType42 || 0); // minMemType42
            writer.writeUint32(post.maxMemType42 || 0); // maxMemType42
            writer.writeUint32(post.minMemType1 || 0); // minMemType1
            writer.writeUint32(post.maxMemType1 || 0); // maxMemType1

            if (post.format === 2) {
                const numberOfGlyphs = ttf.glyf.length;
                writer.writeUint16(numberOfGlyphs); // numberOfGlyphs
                const nameIndex = ttf.support.post.nameIndex;
                for (let i = 0, l = nameIndex.length; i < l; i++) {
                    writer.writeUint16(nameIndex[i]);
                }

                ttf.support.post.names.forEach((name) => {
                    writer.writeBytes(name);
                });
            }
        },

        size(ttf) {

            const numberOfGlyphs = ttf.glyf.length;
            ttf.post = ttf.post || {};
            ttf.post.format = ttf.post.format || 3;
            ttf.post.maxMemType1 = numberOfGlyphs;

            if (ttf.post.format === 3 || ttf.post.format === 1) {
                return 32;
            }

            let size = 34 + numberOfGlyphs * 2; // header + numberOfGlyphs + numberOfGlyphs * 2
            const glyphNames = [];
            const nameIndexArr = [];
            let nameIndex = 0;

            for (let i = 0; i < numberOfGlyphs; i++) {
                if (i === 0) {
                    nameIndexArr.push(0);
                }
                else {
                    const glyf = ttf.glyf[i];
                    const unicode = glyf.unicode ? glyf.unicode[0] : 0;
                    const unicodeNameIndex = unicodeName[unicode];
                    if (undefined !== unicodeNameIndex) {
                        nameIndexArr.push(unicodeNameIndex);
                    }
                    else {
                        const name = glyf.name;
                        if (!name || name.charCodeAt(0) < 32) {
                            nameIndexArr.push(258 + nameIndex++);
                            glyphNames.push([0]);
                            size++;
                        }
                        else {
                            nameIndexArr.push(258 + nameIndex++);
                            const bytes = string.toPascalStringBytes(name); // pascal string bytes
                            glyphNames.push(bytes);
                            size += bytes.length;
                        }
                    }
                }
            }

            ttf.support.post = {
                nameIndex: nameIndexArr,
                names: glyphNames
            };

            return size;
        }
    }
);
