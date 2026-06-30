
import table from './table';
import parse from './cmap/parse';
import write from './cmap/write';
import sizeof from './cmap/sizeof';

export default table.create(
    'cmap',
    [],
    {
        write,
        read: parse,
        size: sizeof
    }
);
