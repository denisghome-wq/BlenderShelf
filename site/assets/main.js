(function () {
  const STORAGE_KEY = 'blendershelf-lang';

  function currentLanguage() {
    try {
      return localStorage.getItem(STORAGE_KEY) || 'ru';
    } catch (e) {
      return 'ru';
    }
  }

  function applyLanguage(lang) {
    document.querySelectorAll('[data-ru]').forEach((el) => {
      const text = lang === 'ru' ? el.dataset.ru : el.dataset.en;
      if (text !== undefined) el.textContent = text;
    });
    document.documentElement.lang = lang;
    const toggle = document.getElementById('lang-toggle');
    if (toggle) toggle.textContent = lang === 'ru' ? 'EN' : 'RU';
  }

  function setLanguage(lang) {
    try {
      localStorage.setItem(STORAGE_KEY, lang);
    } catch (e) {
      // private browsing / blocked storage — language still applies for this view
    }
    applyLanguage(lang);
  }

  document.addEventListener('DOMContentLoaded', () => {
    applyLanguage(currentLanguage());

    const toggle = document.getElementById('lang-toggle');
    if (toggle) {
      toggle.addEventListener('click', () => {
        setLanguage(currentLanguage() === 'ru' ? 'en' : 'ru');
      });
    }
  });
})();
