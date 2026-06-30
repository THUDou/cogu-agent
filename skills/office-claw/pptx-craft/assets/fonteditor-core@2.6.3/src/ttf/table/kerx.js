
import table from './table';

export default table.create(
    'kerx',
    [],
    {

        read(reader, ttf) {
            const length = ttf.tables.kerx.length;
            return reader.readBytes(this.offset, length);
        },

        write(writer, ttf) {
            if (ttf.kerx) {
                writer.writeBytes(ttf.kerx, ttf.kerx.length);
            }
        },

        size(ttf) {
            return ttf.kerx ? ttf.kerx.length : 0;
        }
    }
);
