
export default function compound2simple(glyf, contours) {
    glyf.contours = contours;
    delete glyf.compound;
    delete glyf.glyfs;
    delete glyf.instructions;
    return glyf;
}
