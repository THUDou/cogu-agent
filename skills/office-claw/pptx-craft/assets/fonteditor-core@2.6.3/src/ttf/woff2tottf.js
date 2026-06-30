import woff2 from '../../woff2/index';


export default function woff2tottf(woff2Buffer, options = {}) {
    if (!woff2.isInited()) {
        throw new Error('use woff2.init() to init woff2 module!');
    }
    const result = woff2.decode(woff2Buffer);
    return result.buffer;
}

export function woff2tottfasync(woff2Buffer, options = {}) {
    return woff2.init(options.wasmUrl).then(() => {
        const result = woff2.decode(woff2Buffer);
        return result.buffer;
    });
}
