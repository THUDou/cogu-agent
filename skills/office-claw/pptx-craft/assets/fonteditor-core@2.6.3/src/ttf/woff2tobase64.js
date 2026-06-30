
import bytes2base64 from './util/bytes2base64';

export default function woff2tobase64(arrayBuffer) {
    return 'data:font/woff2;charset=utf-8;base64,' + bytes2base64(arrayBuffer);
}
