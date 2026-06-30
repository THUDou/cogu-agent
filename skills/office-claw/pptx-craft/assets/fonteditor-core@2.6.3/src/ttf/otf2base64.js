
import bytes2base64 from './util/bytes2base64';

export default function ttf2base64(arrayBuffer) {
    return 'data:font/otf;charset=utf-8;base64,' + bytes2base64(arrayBuffer);
}
