// Language selector functionality

function initializeLanguageSelector() {
    const languageSelect = document.getElementById('language-select');
    if (!languageSelect) return;

    const trigger = languageSelect.querySelector('.select-trigger');
    const options = languageSelect.querySelector('.select-options');
    const selectText = languageSelect.querySelector('.select-text');

    // Update selector to match current language when i18n is ready
    if (window.i18n) {
        updateLanguageSelector(window.i18n.getCurrentLanguage());
    }

    // Toggle dropdown
    trigger.addEventListener('click', function(e) {
        e.stopPropagation();
        languageSelect.classList.toggle('open');
    });

    // Handle option selection
    languageSelect.querySelectorAll('.select-option').forEach(option => {
        option.addEventListener('click', function(e) {
            e.stopPropagation();
            const newLang = this.dataset.value;

            if (newLang !== i18n.getCurrentLanguage()) {
                changeLanguage(newLang);
            }

            languageSelect.classList.remove('open');
        });
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', function(event) {
        if (!languageSelect.contains(event.target)) {
            languageSelect.classList.remove('open');
        }
    });

    // Listen for i18n system events to keep selector in sync
    document.addEventListener('translationsLoaded', function() {
        if (window.i18n) {
            updateLanguageSelector(window.i18n.getCurrentLanguage());
        }
    });

    document.addEventListener('languageChanged', function(e) {
        if (e.detail && e.detail.language) {
            updateLanguageSelector(e.detail.language);
        }
    });
}

function updateLanguageSelector(currentLang) {
    const languageSelect = document.getElementById('language-select');
    if (!languageSelect) return;

    const selectText = languageSelect.querySelector('.select-text');
    const options = languageSelect.querySelectorAll('.select-option');

    // Update display text
    if (selectText) {
        selectText.textContent = currentLang.toUpperCase();
    }

    // Update selected option
    options.forEach(option => {
        const optionLang = option.dataset.value;
        if (optionLang === currentLang) {
            option.classList.add('selected');
        } else {
            option.classList.remove('selected');
        }
    });
}

function changeLanguage(newLang) {
    // Update language in i18n system
    i18n.setLanguage(newLang).then(() => {
        // Update URL and reload page with new language
        const currentPath = window.location.pathname;
        const currentParams = window.location.search;

        let newPath;
        if (newLang === 'en') {
            // Remove language prefix for English
            newPath = currentPath.replace(/^\/[a-z]{2}\//, '/');
        } else {
            // Add or update language prefix
            if (currentPath.match(/^\/[a-z]{2}\//)) {
                newPath = currentPath.replace(/^\/[a-z]{2}\//, `/${newLang}/`);
            } else {
                newPath = `/${newLang}${currentPath}`;
            }
        }

        // Redirect to new URL
        window.location.href = newPath + currentParams;
    });
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    initializeLanguageSelector();

    // Try to sync with i18n system after a brief delay if it wasn't ready initially
    setTimeout(function() {
        if (window.i18n) {
            updateLanguageSelector(window.i18n.getCurrentLanguage());
        }
    }, 100);
});

// Export functions
window.initializeLanguageSelector = initializeLanguageSelector;
window.updateLanguageSelector = updateLanguageSelector;
window.changeLanguage = changeLanguage;