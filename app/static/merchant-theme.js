/* Merchant-only theme selector. Browser-local, scoped to each business. */
(() => {
  'use strict';
  const THEMES = Object.freeze(['apple', 'tropical', 'graphite']);
  const names = {
    apple: ['Apple Light', 'Apple Light'],
    tropical: ['Tropical Green', 'Tropical Green'],
    graphite: ['Graphite Dark', 'Graphite Dark']
  };
  const explanations = {
    apple: ['Trắng, xám nhạt, xanh dương', 'White, soft gray and blue'],
    tropical: ['Màu xanh EZ Thing hiện tại', 'Original EZ Thing green'],
    graphite: ['Nền tối, chữ sáng', 'Dark background and light text']
  };
  let businessId = 'global';
  let theme = 'apple';
  const storageKey = () => 'ezthing_merchant_theme:' + businessId;
  const english = () => document.documentElement.lang === 'en';
  const t = (vi, en) => english() ? en : vi;

  function read() {
    try {
      const saved = localStorage.getItem(storageKey());
      return THEMES.includes(saved) ? saved : 'apple';
    } catch (_) { return 'apple'; }
  }
  function sync() {
    document.documentElement.dataset.ezMerchantTheme = theme;
    document.querySelectorAll('[data-merchant-theme-value]').forEach(button => {
      const selected = button.dataset.merchantThemeValue === theme;
      button.setAttribute('aria-pressed', String(selected));
      const mark = button.querySelector('.merchant-theme-check');
      if (mark) mark.textContent = selected ? '✓' : '';
    });
  }
  function setBusiness(id) {
    businessId = String(id || 'global');
    theme = read();
    sync();
  }
  function setTheme(next) {
    if (!THEMES.includes(next)) return;
    theme = next;
    try { localStorage.setItem(storageKey(), theme); } catch (_) { /* private storage */ }
    sync();
    document.dispatchEvent(new CustomEvent('ezthing:merchant-theme-changed', { detail: { theme } }));
  }
  function pickerMarkup() {
    const trigger = t('Chọn màu giao diện', 'Choose interface theme');
    const heading = t('MÀU GIAO DIỆN', 'APPEARANCE');
    const rows = THEMES.map(name =>
      '<button type="button" class="merchant-theme-choice" data-merchant-theme-value="' + name +
      '" aria-pressed="' + String(theme === name) + '">' +
      '<span class="merchant-theme-swatch theme-swatch-' + name + '" aria-hidden="true"></span>' +
      '<span class="merchant-theme-choice-copy"><strong>' + names[name][english() ? 1 : 0] +
      '</strong><small>' + explanations[name][english() ? 1 : 0] + '</small></span>' +
      '<span class="merchant-theme-check" aria-hidden="true">' + (theme === name ? '✓' : '') + '</span></button>'
    ).join('');
    return '<div class="merchant-theme-picker" data-ez-lang-ignore>' +
      '<button type="button" class="merchant-theme-trigger" data-merchant-theme-toggle ' +
      'aria-haspopup="true" aria-expanded="false" aria-label="' + trigger + '" title="' + trigger + '">' +
      '<svg aria-hidden="true" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
      '<circle cx="12" cy="12" r="9"/><circle cx="7.5" cy="10" r="1"/><circle cx="11" cy="6.7" r="1"/>' +
      '<circle cx="16.2" cy="9" r="1"/><path d="M12 21c-1.8-.9-2.1-3.6-.3-4.6 2.8-1.6 5.1 2 7.8-.7"/></svg>' +
      '<span class="merchant-theme-trigger-dot" aria-hidden="true"></span></button>' +
      '<div class="merchant-theme-menu" data-merchant-theme-menu role="group" aria-label="' + trigger + '" hidden>' +
      '<span class="merchant-theme-heading">' + heading + '</span>' + rows + '</div></div>';
  }
  function closePicker(restoreFocus) {
    const picker = document.querySelector('.merchant-theme-picker');
    if (!picker) return;
    const menu = picker.querySelector('[data-merchant-theme-menu]');
    const trigger = picker.querySelector('[data-merchant-theme-toggle]');
    if (!menu || menu.hidden) return;
    menu.hidden = true;
    trigger?.setAttribute('aria-expanded', 'false');
    if (restoreFocus) trigger?.focus();
  }
  document.addEventListener('click', event => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    const toggle = target.closest('[data-merchant-theme-toggle]');
    if (toggle) {
      const menu = toggle.closest('.merchant-theme-picker')?.querySelector('[data-merchant-theme-menu]');
      if (!menu) return;
      const willOpen = menu.hidden;
      closePicker(false);
      menu.hidden = !willOpen;
      toggle.setAttribute('aria-expanded', String(willOpen));
      return;
    }
    const choice = target.closest('[data-merchant-theme-value]');
    if (choice) {
      setTheme(choice.dataset.merchantThemeValue);
      closePicker(false);
      return;
    }
    if (!target.closest('.merchant-theme-picker')) closePicker(false);
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') closePicker(true);
    if (event.key === 'ArrowDown' && event.target.closest?.('[data-merchant-theme-toggle]')) {
      event.preventDefault();
      event.target.click();
      document.querySelector('[data-merchant-theme-value]')?.focus();
    }
  });
  document.addEventListener('ezthing:language-changed', () => {
    document.querySelectorAll('.merchant-theme-picker').forEach(picker => {
      const trigger = picker.querySelector('[data-merchant-theme-toggle]');
      const menu = picker.querySelector('[data-merchant-theme-menu]');
      const title = t('Chọn màu giao diện', 'Choose interface theme');
      if (trigger) { trigger.setAttribute('aria-label', title); trigger.title = title; }
      if (menu) menu.setAttribute('aria-label', title);
      const heading = picker.querySelector('.merchant-theme-heading');
      if (heading) heading.textContent = t('MÀU GIAO DIỆN', 'APPEARANCE');
      picker.querySelectorAll('[data-merchant-theme-value]').forEach(button => {
        const id = button.dataset.merchantThemeValue;
        button.querySelector('strong').textContent = names[id][english() ? 1 : 0];
        button.querySelector('small').textContent = explanations[id][english() ? 1 : 0];
      });
    });
  });
  window.addEventListener('storage', event => {
    if (event.key === storageKey()) { theme = read(); sync(); }
  });
  theme = read();
  sync();
  Object.defineProperty(window, 'EZMerchantTheme', {
    value: Object.freeze({ setBusiness, setTheme, pickerMarkup, current: () => theme }),
    writable: false
  });
})();