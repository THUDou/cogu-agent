
const SEGMENT_REGEX = /-?\d+(?:\.\d+)?(?:e[-+]?\d+)?\b/g;

function getSegment(d) {
    return +d.trim();
}

export default function (str) {
    if (!str) {
        return [];
    }
    const matchs = str.match(SEGMENT_REGEX);
    return matchs ? matchs.map(getSegment) : [];
}
