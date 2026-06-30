
import glyFlag from '../../enum/glyFlag';

function sizeofSimple(glyf, glyfSupport, hinting, writeZeroContoursGlyfData) {
    if (!writeZeroContoursGlyfData && (!glyf.contours || !glyf.contours.length)) {
        return 0;
    }

    let result = 12
        + (glyf.contours || []).length * 2
        + (glyfSupport.flags || []).length;

    (glyfSupport.xCoord || []).forEach((x) => {
        result += 0 <= x && x <= 0xFF ? 1 : 2;
    });

    (glyfSupport.yCoord || []).forEach((y) => {
        result += 0 <= y && y <= 0xFF ? 1 : 2;
    });

    return result + (hinting && glyf.instructions ? glyf.instructions.length : 0);
}

function sizeofCompound(glyf, hinting) {
    let size = 10;
    let transform;
    glyf.glyfs.forEach((g) => {
        transform = g.transform;
        size += 4;

        if (transform.e < 0 || transform.e > 0x7F || transform.f < 0 || transform.f > 0x7F) {
            size += 4;
        }
        else {
            size += 2;
        }

        if (transform.b || transform.c) {
            size += 8;
        }
        else if (transform.a !== 1 || transform.d !== 1) {
            size += transform.a === transform.d ? 2 : 4;
        }

    });

    return size;
}

function getFlags(glyf, glyfSupport) {

    if (!glyf.contours || 0 === glyf.contours.length) {
        return glyfSupport;
    }

    const flags = [];
    const xCoord = [];
    const yCoord = [];

    const contours = glyf.contours;
    let contour;
    let prev;
    let first = true;

    for (let j = 0, cl = contours.length; j < cl; j++) {
        contour = contours[j];

        for (let i = 0, l = contour.length; i < l; i++) {

            const point = contour[i];
            if (first) {
                xCoord.push(point.x);
                yCoord.push(point.y);
                first = false;
            }
            else {
                xCoord.push(point.x - prev.x);
                yCoord.push(point.y - prev.y);
            }
            flags.push(point.onCurve ? glyFlag.ONCURVE : 0);
            prev = point;
        }
    }

    const flagsC = [];
    const xCoordC = [];
    const yCoordC = [];
    let x;
    let y;
    let prevFlag;
    let repeatPoint = -1;

    flags.forEach((flag, index) => {

        x = xCoord[index];
        y = yCoord[index];

        if (index === 0) {

            if (-0xFF <= x && x <= 0xFF) {
                flag += glyFlag.XSHORT;
                if (x >= 0) {
                    flag += glyFlag.XSAME;
                }

                x = Math.abs(x);
            }

            if (-0xFF <= y && y <= 0xFF) {
                flag += glyFlag.YSHORT;
                if (y >= 0) {
                    flag += glyFlag.YSAME;
                }

                y = Math.abs(y);
            }

            flagsC.push(prevFlag = flag);
            xCoordC.push(x);
            yCoordC.push(y);
        }
        else {

            if (x === 0) {
                flag += glyFlag.XSAME;
            }
            else {
                if (-0xFF <= x && x <= 0xFF) {
                    flag += glyFlag.XSHORT;
                    if (x > 0) {
                        flag += glyFlag.XSAME;
                    }

                    x = Math.abs(x);
                }

                xCoordC.push(x);
            }

            if (y === 0) {
                flag += glyFlag.YSAME;
            }
            else {
                if (-0xFF <= y && y <= 0xFF) {
                    flag += glyFlag.YSHORT;
                    if (y > 0) {
                        flag += glyFlag.YSAME;
                    }
                    y = Math.abs(y);
                }
                yCoordC.push(y);
            }

            if (flag === prevFlag) {
                if (-1 === repeatPoint) {
                    repeatPoint = flagsC.length - 1;
                    flagsC[repeatPoint] |= glyFlag.REPEAT;
                    flagsC.push(1);
                }
                else {
                    ++flagsC[repeatPoint + 1];
                }
            }
            else {
                repeatPoint = -1;
                flagsC.push(prevFlag = flag);
            }
        }

    });

    glyfSupport.flags = flagsC;
    glyfSupport.xCoord = xCoordC;
    glyfSupport.yCoord = yCoordC;

    return glyfSupport;
}

export default function sizeof(ttf) {
    ttf.support.glyf = [];
    let tableSize = 0;
    const hinting = ttf.writeOptions ? ttf.writeOptions.hinting : false;
    const writeZeroContoursGlyfData = ttf.writeOptions ? ttf.writeOptions.writeZeroContoursGlyfData : false;
    ttf.glyf.forEach((glyf) => {
        let glyfSupport = {};
        glyfSupport = glyf.compound ? glyfSupport : getFlags(glyf, glyfSupport);

        const glyfSize = glyf.compound
            ? sizeofCompound(glyf, hinting)
            : sizeofSimple(glyf, glyfSupport, hinting, writeZeroContoursGlyfData);
        let size = glyfSize;

        if (size % 4) {
            size += 4 - size % 4;
        }

        glyfSupport.glyfSize = glyfSize;
        glyfSupport.size = size;

        ttf.support.glyf.push(glyfSupport);

        tableSize += size;
    });

    ttf.support.glyf.tableSize = tableSize;

    ttf.head.indexToLocFormat = tableSize > 65536 ? 1 : 0;

    return ttf.support.glyf.tableSize;
}
