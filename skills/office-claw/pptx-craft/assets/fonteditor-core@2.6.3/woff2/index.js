
const woff2ModuleLoader = require('./woff2');

function convertFromVecToUint8Array(vector) {
    const arr = [];
    for (let i = 0, l = vector.size(); i < l; i++) {
        arr.push(vector.get(i));
    }
    return new Uint8Array(arr);
}

const woff2Module = {
    woff2Module: null,

    isInited() {
        return (
            this.woff2Module && this.woff2Module.woff2Enc && this.woff2Module.woff2Dec
        );
    },

    init(wasmUrl) {
        return new Promise((resolve) => {
            if (this.woff2Module) {
                resolve(this);
                return;
            }

            let moduleLoaderConfig = null;
            if (typeof window !== 'undefined') {
                moduleLoaderConfig = {
                    locateFile(path) {
                        if (path.endsWith('.wasm')) {
                            return wasmUrl;
                        }
                        return path;
                    },
                };
            }
            else {
                let wasmPath = './woff2.wasm';
                if (typeof __dirname !== 'undefined') {
                    wasmPath = __dirname + '/woff2.wasm';
                }

                moduleLoaderConfig = {
                    wasmBinaryFile: wasmPath,
                };
            }
            const woffModule = woff2ModuleLoader(moduleLoaderConfig);
            woffModule.onRuntimeInitialized = () => {
                this.woff2Module = woffModule;
                resolve(this);
            };
        });
    },

    encode(ttfBuffer) {
        const buffer = new Uint8Array(ttfBuffer);
        const woffbuff = this.woff2Module.woff2Enc(buffer, buffer.byteLength);
        return convertFromVecToUint8Array(woffbuff);
    },

    decode(woff2Buffer) {
        const buffer = new Uint8Array(woff2Buffer);
        const ttfbuff = this.woff2Module.woff2Dec(buffer, buffer.byteLength);
        return convertFromVecToUint8Array(ttfbuff);
    },
};

module.exports = woff2Module;
