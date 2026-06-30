
import componentFlag from '../../enum/componentFlag';

export default function write(writer, ttf) {
    const hinting = ttf.writeOptions ? ttf.writeOptions.hinting : false;
    const writeZeroContoursGlyfData = ttf.writeOptions ? ttf.writeOptions.writeZeroContoursGlyfData : false;
    ttf.glyf.forEach((glyf, index) => {
        if (!glyf.compound && !writeZeroContoursGlyfData && (!glyf.contours || !glyf.contours.length)) {
            return;
        }
        writer.writeInt16(glyf.compound ? -1 : (glyf.contours || []).length);
        writer.writeInt16(glyf.xMin);
        writer.writeInt16(glyf.yMin);
        writer.writeInt16(glyf.xMax);
        writer.writeInt16(glyf.yMax);

        let i;
        let l;
        let flags;

        if (glyf.compound) {

            for (i = 0, l = glyf.glyfs.length; i < l; i++) {
                const g = glyf.glyfs[i];

                flags = g.points
                    ? 0 : (componentFlag.ARGS_ARE_XY_VALUES + componentFlag.ROUND_XY_TO_GRID); // xy values

                if (i < l - 1) {
                    flags += componentFlag.MORE_COMPONENTS;
                }


                flags += g.useMyMetrics ? componentFlag.USE_MY_METRICS : 0;
                flags += g.overlapCompound ? componentFlag.OVERLAP_COMPOUND : 0;

                const transform = g.transform;
                const a = transform.a;
                const b = transform.b;
                const c = transform.c;
                const d = transform.d;
                const e = g.points ? g.points[0] : transform.e;
                const f = g.points ? g.points[1] : transform.f;

                if (e < 0 || e > 0x7F || f < 0 || f > 0x7F) {
                    flags += componentFlag.ARG_1_AND_2_ARE_WORDS;
                }

                if (b || c) {
                    flags += componentFlag.WE_HAVE_A_TWO_BY_TWO;
                }
                else if ((a !== 1 || d !== 1) && a === d) {
                    flags += componentFlag.WE_HAVE_A_SCALE;
                }
                else if (a !== 1 || d !== 1) {
                    flags += componentFlag.WE_HAVE_AN_X_AND_Y_SCALE;
                }

                writer.writeUint16(flags);
                writer.writeUint16(g.glyphIndex);

                if (componentFlag.ARG_1_AND_2_ARE_WORDS & flags) {
                    writer.writeInt16(e);
                    writer.writeInt16(f);

                }
                else {
                    writer.writeUint8(e);
                    writer.writeUint8(f);
                }

                if (componentFlag.WE_HAVE_A_SCALE & flags) {
                    writer.writeInt16(Math.round(a * 16384));
                }
                else if (componentFlag.WE_HAVE_AN_X_AND_Y_SCALE & flags) {
                    writer.writeInt16(Math.round(a * 16384));
                    writer.writeInt16(Math.round(d * 16384));
                }
                else if (componentFlag.WE_HAVE_A_TWO_BY_TWO & flags) {
                    writer.writeInt16(Math.round(a * 16384));
                    writer.writeInt16(Math.round(b * 16384));
                    writer.writeInt16(Math.round(c * 16384));
                    writer.writeInt16(Math.round(d * 16384));
                }
            }

        }
        else {
            let endPtsOfContours = -1;
            (glyf.contours || []).forEach((contour) => {
                endPtsOfContours += contour.length;
                writer.writeUint16(endPtsOfContours);
            });

            if (hinting && glyf.instructions) {
                const instructions = glyf.instructions;
                writer.writeUint16(instructions.length);
                for (i = 0, l = instructions.length; i < l; i++) {
                    writer.writeUint8(instructions[i]);
                }
            }
            else {
                writer.writeUint16(0);
            }


            flags = ttf.support.glyf[index].flags || [];
            for (i = 0, l = flags.length; i < l; i++) {
                writer.writeUint8(flags[i]);
            }

            const xCoord = ttf.support.glyf[index].xCoord || [];
            for (i = 0, l = xCoord.length; i < l; i++) {
                if (0 <= xCoord[i] && xCoord[i] <= 0xFF) {
                    writer.writeUint8(xCoord[i]);
                }
                else {
                    writer.writeInt16(xCoord[i]);
                }
            }

            const yCoord = ttf.support.glyf[index].yCoord || [];
            for (i = 0, l = yCoord.length; i < l; i++) {
                if (0 <= yCoord[i] && yCoord[i] <= 0xFF) {
                    writer.writeUint8(yCoord[i]);
                }
                else {
                    writer.writeInt16(yCoord[i]);
                }
            }
        }

        const glyfSize = ttf.support.glyf[index].glyfSize;

        if (glyfSize % 4) {
            writer.writeEmpty(4 - glyfSize % 4);
        }
    });

    return writer;
}
