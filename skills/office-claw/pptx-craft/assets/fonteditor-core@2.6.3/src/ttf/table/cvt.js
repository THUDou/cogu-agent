
import table from './table';

export default table.create(
    'cvt',
    [],
    {

        read(reader, ttf) {
            const length = ttf.tables.cvt.length;
            return reader.readBytes(this.offset, length);
        },

        write(writer, ttf) {
            if (ttf.cvt) {
                writer.writeBytes(ttf.cvt, ttf.cvt.length);
            }
        },

        size(ttf) {
            return ttf.cvt ? ttf.cvt.length : 0;
        }
    }
);
