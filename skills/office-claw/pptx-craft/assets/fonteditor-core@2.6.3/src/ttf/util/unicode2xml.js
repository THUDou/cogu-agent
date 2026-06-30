import string from '../../common/string';

export default function unicode2xml(unicodeList) {
    if (typeof unicodeList === 'number') {
        unicodeList = [unicodeList];
    }
    return unicodeList.map(u => {
        if (u < 0x20) {
            return '';
        }
        return u >= 0x20 && u <= 255
            ? string.encodeHTML(String.fromCharCode(u))
            : '&#x' + u.toString(16) + ';';
    }).join('');
}
