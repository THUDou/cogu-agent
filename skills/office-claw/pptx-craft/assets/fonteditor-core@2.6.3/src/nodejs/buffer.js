
export default {

    toArrayBuffer(buffer) {
        const length = buffer.length;
        const view = new DataView(new ArrayBuffer(length), 0, length);
        for (let i = 0, l = length; i < l; i++) {
            view.setUint8(i, buffer[i], false);
        }
        return view.buffer;
    },

    toBuffer(arrayBuffer) {
        if (Array.isArray(arrayBuffer)) {
            return Buffer.from(arrayBuffer);
        }

        const length = arrayBuffer.byteLength;
        const view = new DataView(arrayBuffer, 0, length);
        const buffer = Buffer.alloc(length);
        for (let i = 0, l = length; i < l; i++) {
            buffer[i] = view.getUint8(i, false);
        }
        return buffer;
    }
};
