
import table from './table';

export default table.create(
    'kern',
    [],
    {

        read(reader, ttf) {
            const length = ttf.tables.kern.length;
            return reader.readBytes(this.offset, length);
        },

        write(writer, ttf) {
            if (ttf.kern) {
                writer.writeBytes(ttf.kern, ttf.kern.length);
            }
        },

        size(ttf) {
            return ttf.kern ? ttf.kern.length : 0;
        }
    }
);
