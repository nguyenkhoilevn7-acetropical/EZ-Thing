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

  /* The phone uses the actual same-origin storefront pages, not synthetic artwork. */
  const preview = document.querySelector('[data-ez-preview]');
  if (preview) {
    const frames = Array.from(preview.querySelectorAll('.live-preview-frame'));
    const controls = Array.from(preview.querySelectorAll('[data-preview-index]'));
    const caption = preview.querySelector('.live-preview-label');
    const open = preview.querySelector('.live-preview-open');
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let selected = 0;
    let timer = null;
    let onscreen = !('IntersectionObserver' in window);
    let hovered = false;
    let focused = false;
    let generation = 0;

    const loadFrame = index => {
      const frame = frames[index];
      if (frame && !frame.hasAttribute('src')) {
        frame.setAttribute('src', frame.dataset.previewSrc);
      }
    };
    const present = index => {
      if (!Number.isInteger(index) || index < 0 || index >= frames.length || index === selected) return;
      const frame = frames[index];
      const turn = ++generation;
      const commit = () => {
        if (turn !== generation) return;
        selected = index;
        frames.forEach((item, i) => item.classList.toggle('is-active', i === index));
        controls.forEach((button, i) => {
          button.classList.toggle('is-active', i === index);
          button.setAttribute('aria-pressed', String(i === index));
        });
        caption.textContent = frame.dataset.previewLabel;
        open.setAttribute('href', frame.dataset.previewSrc);
        loadFrame((index + 1) % frames.length);
      };
      if (frame.dataset.loaded === 'true') {
        commit();
      } else {
        frame.addEventListener('load', () => {
          frame.dataset.loaded = 'true';
          commit();
        }, { once: true });
        loadFrame(index);
      }
    };
    frames.forEach(frame => frame.addEventListener('load', () => {
      frame.dataset.loaded = 'true';
    }));
    loadFrame(1);
    const pause = () => {
      if (timer !== null) clearInterval(timer);
      timer = null;
    };
    const cycle = () => {
      pause();
      if (prefersReducedMotion || document.hidden || !onscreen || hovered || focused) return;
      timer = setInterval(() => present((selected + 1) % frames.length), 6500);
    };
    controls.forEach(button => button.addEventListener('click', () => {
      present(Number(button.dataset.previewIndex));
      cycle();
    }));
    preview.addEventListener('mouseenter', () => { hovered = true; cycle(); });
    preview.addEventListener('mouseleave', () => { hovered = false; cycle(); });
    preview.addEventListener('focusin', () => { focused = true; cycle(); });
    preview.addEventListener('focusout', () => {
      focused = preview.contains(document.activeElement);
      cycle();
    });
    document.addEventListener('visibilitychange', cycle);
    if ('IntersectionObserver' in window) {
      const previewObserver = new IntersectionObserver(entries => {
        onscreen = entries.some(entry => entry.isIntersecting);
        cycle();
      }, { threshold: 0.05 });
      previewObserver.observe(preview);
    } else {
      cycle();
    }
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
