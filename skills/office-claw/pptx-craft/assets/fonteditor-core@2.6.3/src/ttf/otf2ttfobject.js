
import error from './error';
import OTFReader from './otfreader';
import otfContours2ttfContours from './util/otfContours2ttfContours';
import {computePathBox} from '../graphics/computeBoundingBox';

export default function otf2ttfobject(otfBuffer, options) {
    let otfObject;
    if (otfBuffer instanceof ArrayBuffer) {
        const otfReader = new OTFReader(options);
        otfObject = otfReader.read(otfBuffer);
        otfReader.dispose();
    }
    else if (otfBuffer.head && otfBuffer.glyf && otfBuffer.cmap) {
        otfObject = otfBuffer;
    }
    else {
        error.raise(10111);
    }

    otfObject.glyf.forEach((g) => {
        g.contours = otfContours2ttfContours(g.contours);
        const box = computePathBox(...g.contours);
        if (box) {
            g.xMin = box.x;
            g.xMax = box.x + box.width;
            g.yMin = box.y;
            g.yMax = box.y + box.height;
            g.leftSideBearing = g.xMin;
        }
        else {
            g.xMin = 0;
            g.xMax = 0;
            g.yMin = 0;
            g.yMax = 0;
            g.leftSideBearing = 0;
        }
    });

    otfObject.version = 0x1;

    otfObject.maxp.version = 1.0;
    otfObject.maxp.maxZones = otfObject.maxp.maxTwilightPoints ? 2 : 1;

    delete otfObject.CFF;
    delete otfObject.VORG;

    return otfObject;
}
