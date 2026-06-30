import woff2 from '../../woff2/index.esm.js';

export default function ttftowoff2(ttfBuffer, options = {}) {
    if (!woff2.isInited()) {
        throw new Error('use woff2.init() to init woff2 module!');
    }

    const result = woff2.encode(ttfBuffer);
    return result.buffer;
}


export function ttftowoff2async(ttfBuffer, options = {}) {
    return woff2.init(options.wasmUrl).then(() => {
        const result = woff2.encode(ttfBuffer);
        return result.buffer;
    });
}
