

export function isArray(obj) {
    return obj != null && toString.call(obj).slice(8, -1) === 'Array';
}

export function isObject(obj) {
    return obj != null && toString.call(obj).slice(8, -1) === 'Object';
}

export function isString(obj) {
    return obj != null && toString.call(obj).slice(8, -1) === 'String';
}

export function isFunction(obj) {
    return obj != null && toString.call(obj).slice(8, -1) === 'Function';
}

export function isDate(obj) {
    return obj != null && toString.call(obj).slice(8, -1) === 'Date';
}

export function isEmptyObject(object) {
    for (const name in object) {
        if (object.hasOwnProperty(name)) {
            return false;
        }
    }
    return true;
}

export function curry(fn, ...cargs) {
    return function (...rargs) {
        const args = cargs.concat(rargs);
        return fn.apply(this, args);
    };
}


export function generic(method) {
    return function (...fargs) {
        return Function.call.apply(method, fargs);
    };
}


export function overwrite(thisObj, thatObj, fields) {

    if (!thatObj) {
        return thisObj;
    }

    fields = fields || Object.keys(thatObj);
    fields.forEach(field => {
        if (
            thisObj[field] && typeof thisObj[field] === 'object'
            && thatObj[field] && typeof thatObj[field] === 'object'
        ) {
            overwrite(thisObj[field], thatObj[field]);
        }
        else {
            thisObj[field] = thatObj[field];
        }
    });

    return thisObj;
}

export function clone(source) {
    if (!source || typeof source !== 'object') {
        return source;
    }

    let cloned = source;

    if (isArray(source)) {
        cloned = source.slice().map(clone);
    }
    else if (isObject(source) && 'isPrototypeOf' in source) {
        cloned = {};
        for (const key of Object.keys(source)) {
            cloned[key] = clone(source[key]);
        }
    }

    return cloned;
}


export function throttle(func, wait) {
    let context;
    let args;
    let timeout;
    let result;
    let previous = 0;
    const later = function () {
        previous = new Date();
        timeout = null;
        result = func.apply(context, args);
    };

    return function (...args) {
        const now = new Date();
        const remaining = wait - (now - previous);
        context = this;
        if (remaining <= 0) {
            clearTimeout(timeout);
            timeout = null;
            previous = now;
            result = func.apply(context, args);
        }
        else if (!timeout) {
            timeout = setTimeout(later, remaining);
        }
        return result;
    };
}

export function debounce(func, wait, immediate) {
    let timeout;
    let result;

    return function (...args) {
        const context = this;
        const later = function () {
            timeout = null;
            if (!immediate) {
                result = func.apply(context, args);
            }
        };

        const callNow = immediate && !timeout;

        clearTimeout(timeout);
        timeout = setTimeout(later, wait);

        if (callNow) {
            result = func.apply(context, args);
        }

        return result;
    };
}

export function equals(thisObj, thatObj, fields) {

    if (thisObj === thatObj) {
        return true;
    }

    if (thisObj == null && thatObj == null) {
        return true;
    }

    if (thisObj == null && thatObj != null || thisObj != null && thatObj == null) {
        return false;
    }

    fields = fields || (typeof thisObj === 'object'
        ? Object.keys(thisObj)
        : []);

    if (!fields.length) {
        return thisObj === thatObj;
    }

    let equal = true;
    for (let i = 0, l = fields.length, field; equal && i < l; i++) {
        field = fields[i];

        if (
            thisObj[field] && typeof thisObj[field] === 'object'
            && thatObj[field] && typeof thatObj[field] === 'object'
        ) {
            equal = equal && equals(thisObj[field], thatObj[field]);
        }
        else {
            equal = equal && (thisObj[field] === thatObj[field]);
        }
    }

    return equal;
}
