
export default function base642bytes(base64) {
    const str = atob(base64);
    const result = [];
    for (let i = 0, l = str.length; i < l; i++) {
        result.push(str[i].charCodeAt(0));
    }
    return result;
}
