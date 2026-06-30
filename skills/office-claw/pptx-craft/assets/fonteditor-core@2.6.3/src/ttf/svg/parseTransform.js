
import parseParams from './parseParams';
const TRANSFORM_REGEX = /(\w+)\s*\(([\d-.,\s]*)\)/g;

export default function parseTransform(str) {

    if (!str) {
        return false;
    }

    TRANSFORM_REGEX.lastIndex = 0;
    const transforms = [];
    let match;

    while ((match = TRANSFORM_REGEX.exec(str))) {
        transforms.push({
            name: match[1],
            params: parseParams(match[2])
        });
    }

    return transforms;
}
