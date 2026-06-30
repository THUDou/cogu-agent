
function appendLanguage(store, languageList) {
    languageList.forEach(item => {
        const language = item[0];
        store[language] = Object.assign(store[language] || {}, item[1]);
    });
    return store;
}

export default class I18n {
    constructor(languageList, defaultLanguage) {
        this.store = appendLanguage({}, languageList);
        this.setLanguage(
            defaultLanguage
            || typeof navigator !== 'undefined' && navigator.language && navigator.language.toLowerCase()
            || 'en-us'
        );
    }

    setLanguage(language) {
        if (!this.store[language]) {
            language = 'en-us';
        }
        this.lang = this.store[this.language = language];
        return this;
    }

    addLanguage(language, langObject) {
        appendLanguage(this.store, [[language, langObject]]);
        return this;
    }

    get(path) {
        const ref = path.split('.');
        let refObject = this.lang;
        let level;
        while (refObject != null && (level = ref.shift())) {
            refObject = refObject[level];
        }
        return refObject != null ? refObject : '';
    }
}
