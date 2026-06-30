
export default function svg2base64(svg, scheme = 'font/svg') {
    if (typeof btoa === 'undefined') {
        return 'data:' + scheme + ';charset=utf-8;base64,'
            + Buffer.from(svg, 'binary').toString('base64');
    }
    return 'data:' + scheme + ';charset=utf-8;base64,' + btoa(svg);
}
