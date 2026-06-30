
import {clone} from '../common/lang';
import emptyttf from './data/empty';
import config from './data/default';


export default function getEmpty() {
    const ttf = clone(emptyttf);
    Object.assign(ttf.name, config.name);
    ttf.head.created = ttf.head.modified = Date.now();
    return ttf;
}
