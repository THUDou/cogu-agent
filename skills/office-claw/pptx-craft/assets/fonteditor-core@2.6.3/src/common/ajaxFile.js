

export default function ajaxFile(options) {
    const xhr = new XMLHttpRequest();

    xhr.onreadystatechange = function () {
        if (xhr.readyState === 4) {
            const status = xhr.status;
            if (status >= 200 && status < 300 || status === 304) {
                if (options.onSuccess) {
                    if (options.type === 'binary') {
                        const buffer = xhr.responseBlob || xhr.response;
                        options.onSuccess(buffer);
                    }
                    else if (options.type === 'xml') {
                        options.onSuccess(xhr.responseXML);
                    }
                    else if (options.type === 'json') {
                        options.onSuccess(JSON.parse(xhr.responseText));
                    }
                    else {
                        options.onSuccess(xhr.responseText);
                    }
                }

            }
            else if (options.onError) {
                options.onError(xhr, xhr.status);
            }
        }
    };

    const method = (options.method || 'GET').toUpperCase();
    let params = null;
    if (options.params) {

        let str = [];
        Object.keys(options.params).forEach(key => {
            str.push(key + '=' + encodeURIComponent(options.params[key]));
        });
        str = str.join('&');
        if (method === 'GET') {
            options.url += (options.url.indexOf('?') === -1 ? '?' : '&') + str;
        }
        else {
            params = str;
        }
    }

    xhr.open(method, options.url, true);

    if (options.type === 'binary') {
        xhr.responseType = 'arraybuffer';
    }
    xhr.send(params);
}

export function loadFile(url, type = 'binary') {
    return new Promise((resolve, reject) => {
        ajaxFile({
            type,
            url,
            onSuccess(buffer) {
                resolve(buffer);
            },
            onError(e) {
                reject(e);
            }
        });
    });
}
