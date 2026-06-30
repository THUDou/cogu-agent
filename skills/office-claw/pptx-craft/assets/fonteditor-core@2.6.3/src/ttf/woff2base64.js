
import bytes2base64 from './util/bytes2base64';

export default function woff2base64(arrayBuffer) {
    return 'data:font/woff;charset=utf-8;base64,' + bytes2base64(arrayBuffer);
}
