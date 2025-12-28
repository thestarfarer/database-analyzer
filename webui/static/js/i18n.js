// Internationalization utility for WebUI
class I18n {
    constructor() {
        this.currentLanguage = 'en';
        this.translations = {};
        this.fallbackLanguage = 'en';

        // Detect language from URL, localStorage, or browser
        this.detectLanguage();

        // Load translations
        this.loadTranslations();
    }

    detectLanguage() {
        // Check URL path for language prefix
        const path = window.location.pathname;
        const urlLang = path.match(/^\/([a-z]{2})\//);
        if (urlLang) {
            this.currentLanguage = urlLang[1];
            return;
        }

        // Check localStorage
        const savedLang = localStorage.getItem('webui_language');
        if (savedLang) {
            this.currentLanguage = savedLang;
            return;
        }

        // Check browser language
        const browserLang = navigator.language.split('-')[0];
        this.currentLanguage = browserLang;
    }

    async loadTranslations() {
        try {
            const response = await fetch(`/static/translations/${this.currentLanguage}.json`);
            if (!response.ok) {
                throw new Error(`Failed to load ${this.currentLanguage} translations`);
            }
            this.translations = await response.json();

            // Emit custom event when translations are loaded
            document.dispatchEvent(new CustomEvent('translationsLoaded', {
                detail: { language: this.currentLanguage }
            }));
        } catch (error) {
            console.error('Error loading translations:', error);

            // Fallback to English if current language fails
            if (this.currentLanguage !== this.fallbackLanguage) {
                this.currentLanguage = this.fallbackLanguage;
                await this.loadTranslations();
            }
        }
    }

    t(key, replacements = {}) {
        const keys = key.split('.');
        let translation = this.translations;

        // Navigate through nested object
        for (const k of keys) {
            if (translation && typeof translation === 'object' && k in translation) {
                translation = translation[k];
            } else {
                console.warn(`Translation key not found: ${key}`);
                return key; // Return the key itself if translation not found
            }
        }

        // Handle string replacements
        if (typeof translation === 'string' && Object.keys(replacements).length > 0) {
            return this.interpolate(translation, replacements);
        }

        return translation;
    }

    interpolate(template, replacements) {
        return template.replace(/{(\w+)}/g, (match, key) => {
            return replacements.hasOwnProperty(key) ? replacements[key] : match;
        });
    }

    async setLanguage(lang) {
        this.currentLanguage = lang;
        localStorage.setItem('webui_language', lang);

        await this.loadTranslations();

        // Update URL if needed
        this.updateURL();

        // Emit language change event
        document.dispatchEvent(new CustomEvent('languageChanged', {
            detail: { language: lang }
        }));
    }

    updateURL() {
        const path = window.location.pathname;
        const newPath = this.currentLanguage === 'en'
            ? path.replace(/^\/[a-z]{2}\//, '/').replace(/^\/$/, '/')
            : `/${this.currentLanguage}${path.replace(/^\/[a-z]{2}\//, '/')}`;

        if (path !== newPath) {
            window.history.replaceState({}, '', newPath);
        }
    }

    getCurrentLanguage() {
        return this.currentLanguage;
    }

    // Format numbers with pluralization
    formatCount(count, singularKey, pluralKey = null) {
        const key = count === 1 ? singularKey : (pluralKey || singularKey);
        return this.t(key, { count });
    }

    // Format relative time with proper localization
    formatRelativeTime(timestamp) {
        if (!timestamp) return this.t('common.unknown');

        let date;
        if (typeof timestamp === 'number') {
            date = new Date(timestamp * 1000);
        } else {
            date = new Date(timestamp);
        }

        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) return this.t('time.just_now');
        if (diffMins < 60) return this.t('time.minutes_ago', { count: diffMins });
        if (diffHours < 24) return this.t('time.hours_ago', { count: diffHours });
        return this.t('time.days_ago', { count: diffDays });
    }

    // Format duration with localization
    formatDuration(startTime, endTime) {
        if (!startTime) return this.t('common.unknown');

        let start, end;
        if (typeof startTime === 'number') {
            start = new Date(startTime * 1000);
        } else {
            start = new Date(startTime);
        }

        if (endTime) {
            if (typeof endTime === 'number') {
                end = new Date(endTime * 1000);
            } else {
                end = new Date(endTime);
            }
        } else {
            end = new Date();
        }

        const diffMs = end - start;
        const diffSecs = Math.floor(diffMs / 1000);
        const diffMins = Math.floor(diffSecs / 60);
        const diffHours = Math.floor(diffMins / 60);

        if (diffSecs < 60) return this.t('time.seconds', { count: diffSecs });
        if (diffMins < 60) return this.t('time.minutes', {
            count: diffMins,
            seconds: diffSecs % 60
        });
        return this.t('time.hours', {
            count: diffHours,
            minutes: diffMins % 60
        });
    }
}

// Global instance
const i18n = new I18n();

// Global translation function
window.t = (key, replacements) => i18n.t(key, replacements);

// Export for use in other modules
window.I18n = I18n;
window.i18n = i18n;

// Helper function to translate a specific element and its children
function translateElement(element) {
    // Translate elements with data-i18n attribute
    element.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        const replacements = el.getAttribute('data-i18n-replacements');

        let params = {};
        if (replacements) {
            try {
                params = JSON.parse(replacements);
            } catch (e) {
                console.warn('Invalid JSON in data-i18n-replacements:', replacements);
            }
        }

        const translation = i18n.t(key, params);

        // Update text content or placeholder based on element type
        if (el.tagName === 'INPUT' && el.type === 'text') {
            el.placeholder = translation;
        } else {
            el.textContent = translation;
        }
    });

    // Translate elements with data-i18n-placeholder attribute
    element.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const key = el.getAttribute('data-i18n-placeholder');
        const translation = i18n.t(key);
        el.placeholder = translation;
    });

    // Also check if the element itself has data-i18n attribute
    if (element.hasAttribute && element.hasAttribute('data-i18n')) {
        const key = element.getAttribute('data-i18n');
        const replacements = element.getAttribute('data-i18n-replacements');

        let params = {};
        if (replacements) {
            try {
                params = JSON.parse(replacements);
            } catch (e) {
                console.warn('Invalid JSON in data-i18n-replacements:', replacements);
            }
        }

        const translation = i18n.t(key, params);

        if (element.tagName === 'INPUT' && element.type === 'text') {
            element.placeholder = translation;
        } else {
            element.textContent = translation;
        }
    }

    // Translate elements with data-i18n-html attribute (for HTML content)
    element.querySelectorAll('[data-i18n-html]').forEach(el => {
        const key = el.getAttribute('data-i18n-html');
        const replacements = el.getAttribute('data-i18n-replacements');

        let params = {};
        if (replacements) {
            try {
                params = JSON.parse(replacements);
            } catch (e) {
                console.warn('Invalid JSON in data-i18n-replacements:', replacements);
            }
        }

        el.innerHTML = i18n.t(key, params);
    });
}

// Make translateElement globally available
window.translateElement = translateElement;

// Auto-translate elements with data-i18n attribute when translations load
document.addEventListener('translationsLoaded', () => {
    translatePageElements();
});

document.addEventListener('languageChanged', () => {
    translatePageElements();
});

function translatePageElements() {
    // Translate elements with data-i18n attribute
    document.querySelectorAll('[data-i18n]').forEach(element => {
        const key = element.getAttribute('data-i18n');
        const replacements = element.getAttribute('data-i18n-replacements');

        let params = {};
        if (replacements) {
            try {
                params = JSON.parse(replacements);
            } catch (e) {
                console.warn('Invalid JSON in data-i18n-replacements:', replacements);
            }
        }

        const translation = i18n.t(key, params);

        // Update text content or placeholder based on element type
        if (element.tagName === 'INPUT' && element.type === 'text') {
            element.placeholder = translation;
        } else {
            element.textContent = translation;
        }
    });

    // Translate elements with data-i18n-html attribute (for HTML content)
    document.querySelectorAll('[data-i18n-html]').forEach(element => {
        const key = element.getAttribute('data-i18n-html');
        const replacements = element.getAttribute('data-i18n-replacements');

        let params = {};
        if (replacements) {
            try {
                params = JSON.parse(replacements);
            } catch (e) {
                console.warn('Invalid JSON in data-i18n-replacements:', replacements);
            }
        }

        element.innerHTML = i18n.t(key, params);
    });

    // Translate elements with data-i18n-placeholder attribute
    document.querySelectorAll('[data-i18n-placeholder]').forEach(element => {
        const key = element.getAttribute('data-i18n-placeholder');
        const translation = i18n.t(key);
        element.placeholder = translation;
    });
}

// Initialize translations when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        // Translations will be loaded by constructor
    });
} else {
    // Document already loaded, translations should be loading/loaded
}