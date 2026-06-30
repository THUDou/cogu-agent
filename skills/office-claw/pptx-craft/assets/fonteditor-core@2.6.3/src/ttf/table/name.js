
import table from './table';
import nameIdTbl from '../enum/nameId';
import string from '../util/string';
import platformTbl from '../enum/platform';
import {mac, win} from '../enum/encoding';

export default table.create(
    'name',
    [],
    {

        read(reader) {
            let offset = this.offset;
            reader.seek(offset);

            const nameTbl = {};
            nameTbl.format = reader.readUint16();
            nameTbl.count = reader.readUint16();
            nameTbl.stringOffset = reader.readUint16();

            const nameRecordTbl = [];
            const count = nameTbl.count;
            let i;
            let nameRecord;

            for (i = 0; i < count; ++i) {
                nameRecord = {};
                nameRecord.platform = reader.readUint16();
                nameRecord.encoding = reader.readUint16();
                nameRecord.language = reader.readUint16();
                nameRecord.nameId = reader.readUint16();
                nameRecord.length = reader.readUint16();
                nameRecord.offset = reader.readUint16();
                nameRecordTbl.push(nameRecord);
            }

            offset += nameTbl.stringOffset;

            for (i = 0; i < count; ++i) {
                nameRecord = nameRecordTbl[i];
                nameRecord.name = reader.readBytes(offset + nameRecord.offset, nameRecord.length);
            }

            const names = {};

            let platform = platformTbl.Macintosh;
            let encoding = mac.Default;
            let language = 0;

            if (nameRecordTbl.some((record) => record.platform === platformTbl.Microsoft
                    && record.encoding === win.UCS2
                    && record.language === 1033)) {
                platform = platformTbl.Microsoft;
                encoding = win.UCS2;
                language = 1033;
            }

            for (i = 0; i < count; ++i) {
                nameRecord = nameRecordTbl[i];
                if (nameRecord.platform === platform
                    && nameRecord.encoding === encoding
                    && nameRecord.language === language
                    && nameIdTbl[nameRecord.nameId]) {
                    names[nameIdTbl[nameRecord.nameId]] = language === 0
                        ? string.getUTF8String(nameRecord.name)
                        : string.getUCS2String(nameRecord.name);
                }
            }

            return names;
        },

        write(writer, ttf) {
            const nameRecordTbl = ttf.support.name;

            writer.writeUint16(0); // format
            writer.writeUint16(nameRecordTbl.length); // count
            writer.writeUint16(6 + nameRecordTbl.length * 12); // string offset

            let offset = 0;
            nameRecordTbl.forEach((nameRecord) => {
                writer.writeUint16(nameRecord.platform);
                writer.writeUint16(nameRecord.encoding);
                writer.writeUint16(nameRecord.language);
                writer.writeUint16(nameRecord.nameId);
                writer.writeUint16(nameRecord.name.length);
                writer.writeUint16(offset); // offset
                offset += nameRecord.name.length;
            });

            nameRecordTbl.forEach((nameRecord) => {
                writer.writeBytes(nameRecord.name);
            });

            return writer;
        },

        size(ttf) {
            const names = ttf.name;
            let nameRecordTbl = [];

            let size = 6;
            Object.keys(names).forEach((name) => {
                const id = nameIdTbl.names[name];

                const utf8Bytes = string.toUTF8Bytes(names[name]);
                const usc2Bytes = string.toUCS2Bytes(names[name]);

                if (undefined !== id) {
                    nameRecordTbl.push({
                        nameId: id,
                        platform: 1,
                        encoding: 0,
                        language: 0,
                        name: utf8Bytes
                    });

                    nameRecordTbl.push({
                        nameId: id,
                        platform: 3,
                        encoding: 1,
                        language: 1033,
                        name: usc2Bytes
                    });

                    size += 12 * 2 + utf8Bytes.length + usc2Bytes.length;
                }
            });

            const namingOrder = ['platform', 'encoding', 'language', 'nameId'];
            nameRecordTbl = nameRecordTbl.sort((a, b) => {
                let l = 0;
                namingOrder.some(name => {
                    const o = a[name] - b[name];
                    if (o) {
                        l = o;
                        return true;
                    }
                    return false;
                });
                return l;
            });

            ttf.support.name = nameRecordTbl;

            return size;
        }
    }
);
