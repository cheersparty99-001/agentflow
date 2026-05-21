(function() {
  const lang = localStorage.getItem('agentflow_lang') || 'en';
  document.documentElement.lang = lang;
  window.setLang = function(code) {
    localStorage.setItem('agentflow_lang', code);
    location.reload();
  };
  async function applyTranslations() {
    const lang = localStorage.getItem('agentflow_lang') || 'en';
    try {
      const res = await fetch('/locales/' + lang + '.json');
      const dict = await res.json();
      document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (dict[key]) {
          if (el.tagName === 'INPUT' && el.getAttribute('placeholder')) {
            el.placeholder = dict[key];
          } else {
            el.textContent = dict[key];
          }
        }
      });
    } catch(e) {}
  }
  document.addEventListener('DOMContentLoaded', applyTranslations);
})();