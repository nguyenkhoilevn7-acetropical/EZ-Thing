/* Progressive enhancement: editorial reveal + accessible responsive navigation. */
(() => {
  'use strict';
  const nav = document.getElementById('site-primary-nav');
  const toggle = document.querySelector('.mobile-menu-toggle');
  const header = document.querySelector('.site-header');
  const closeMenu = () => {
    header?.classList.remove('menu-open');
    toggle?.setAttribute('aria-expanded', 'false');
    toggle?.setAttribute('aria-label', 'Mở menu');
  };
  if (nav && toggle && header) {
    toggle.addEventListener('click', () => {
      const next = !header.classList.contains('menu-open');
      header.classList.toggle('menu-open', next);
      toggle.setAttribute('aria-expanded', String(next));
      toggle.setAttribute('aria-label', next ? 'Đóng menu' : 'Mở menu');
    });
    nav.addEventListener('click', event => {
      if (event.target.closest('a')) closeMenu();
    });
    document.addEventListener('click', event => {
      if (!header.contains(event.target)) closeMenu();
    });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape') closeMenu();
    });
    window.matchMedia('(min-width: 791px)').addEventListener?.('change', event => {
      if (event.matches) closeMenu();
    });
  }
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches ||
      !('IntersectionObserver' in window)) return;
  const items = document.querySelectorAll('.solution-card, .how-grid article, .pricing-grid article');
  if (!items.length) return;
  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      entry.target.classList.add('is-visible');
      observer.unobserve(entry.target);
    }
  }, { threshold: 0.08, rootMargin: '0px 0px 40px 0px' });
  for (const item of items) {
    item.classList.add('premium-reveal');
    observer.observe(item);
  }
})();
