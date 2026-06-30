"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = ajaxFile;
exports.loadFile = loadFile;

function ajaxFile(options) {
  var xhr = new XMLHttpRequest();
  xhr.onreadystatechange = function () {
    if (xhr.readyState === 4) {
      var status = xhr.status;
      if (status >= 200 && status < 300 || status === 304) {
        if (options.onSuccess) {
          if (options.type === 'binary') {
            var buffer = xhr.responseBlob || xhr.response;
            options.onSuccess(buffer);
          } else if (options.type === 'xml') {
            options.onSuccess(xhr.responseXML);
          } else if (options.type === 'json') {
            options.onSuccess(JSON.parse(xhr.responseText));
          } else {
            options.onSuccess(xhr.responseText);
          }
        }
      } else if (options.onError) {
        options.onError(xhr, xhr.status);
      }
    }
  };
  var method = (options.method || 'GET').toUpperCase();
  var params = null;
  if (options.params) {
    var str = [];
    Object.keys(options.params).forEach(function (key) {
      str.push(key + '=' + encodeURIComponent(options.params[key]));
    });
    str = str.join('&');
    if (method === 'GET') {
      options.url += (options.url.indexOf('?') === -1 ? '?' : '&') + str;
    } else {
      params = str;
    }
  }
  xhr.open(method, options.url, true);
  if (options.type === 'binary') {
    xhr.responseType = 'arraybuffer';
  }
  xhr.send(params);
}
function loadFile(url) {
  var type = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : 'binary';
  return new Promise(function (resolve, reject) {
    ajaxFile({
      type: type,
      url: url,
      onSuccess: function onSuccess(buffer) {
        resolve(buffer);
      },
      onError: function onError(e) {
        reject(e);
      }
    });
  });
}
