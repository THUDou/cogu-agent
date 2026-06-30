
export default {

    decodeHTML(source) {

        const str = String(source)
            .replace(/&quot;/g, '"')
            .replace(/&lt;/g, '<')
            .replace(/&gt;/g, '>')
            .replace(/&amp;/g, '&');

        return str.replace(/&#([\d]+);/g, ($0, $1) => String.fromCodePoint(parseInt($1, 10)));
    },

    encodeHTML(source) {
        return String(source)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    },

    getLength(source) {
        return String(source).replace(/[^\x00-\xff]/g, '11').length;
    },

    format(source, data) {
        return source.replace(/\$\{([\w.]+)\}/g, ($0, $1) => {
            const ref = $1.split('.');
            let refObject = data;
            let level;

            while (refObject != null && (level = ref.shift())) {
                refObject = refObject[level];
            }

            return refObject != null ? refObject : '';
        });
    },

    pad(str, size, ch) {
        str = String(str);
        if (str.length > size) {
            return str.slice(str.length - size);
        }
        return new Array(size - str.length + 1).join(ch || '0') + str;
    },

    hashcode(str) {
        if (!str) {
            return 0;
        }

        let hash = 0;
        for (let i = 0, l = str.length; i < l; i++) {
            hash = 0x7FFFFFFFF & (hash * 31 + str.charCodeAt(i));
        }
        return hash;
    }
};
