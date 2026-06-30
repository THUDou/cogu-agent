import bytes2base64 from './util/bytes2base64';

export default function eot2base64(arrayBuffer) {
    return 'data:font/eot;charset=utf-8;base64,' + bytes2base64(arrayBuffer);
}
