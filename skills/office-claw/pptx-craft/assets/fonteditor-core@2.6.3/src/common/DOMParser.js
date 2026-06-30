
export default typeof window !== 'undefined' && window.DOMParser
    ? window.DOMParser
    : require('@xmldom/xmldom').DOMParser;
