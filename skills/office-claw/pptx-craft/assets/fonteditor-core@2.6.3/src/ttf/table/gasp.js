
import table from './table';

export default table.create(
    'gasp',
    [],
    {

        read(reader, ttf) {
            const length = ttf.tables.gasp.length;
            return reader.readBytes(this.offset, length);
        },

        write(writer, ttf) {
            if (ttf.gasp) {
                writer.writeBytes(ttf.gasp, ttf.gasp.length);
            }
        },

        size(ttf) {
            return ttf.gasp ? ttf.gasp.length : 0;
        }
    }
);
