
import string from '../common/string';
import i18n from './i18n';

export default {

    raise(e, ...fargs) {
        let number;
        let data;
        if (typeof e === 'object') {
            number = e.number || 0;
            data = e.data;
        }
        else {
            number = e;
        }

        let message = i18n.lang[number];
        if (fargs.length > 0) {
            const args = typeof fargs[0] === 'object'
                ? fargs[0]
                : fargs;
            message = string.format(message, args);
        }

        const event = new Error(message);
        event.number = number;
        if (data) {
            event.data = data;
        }

        throw event;
    }
};
