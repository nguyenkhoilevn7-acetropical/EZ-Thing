/* EZ Thing homepage: two-frame carousel of real, same-origin customer storefronts. */
(() => {
  'use strict';
  const carousel = document.querySelector('[data-industry-carousel]');
  if (!carousel) return;

  const slides = [
    { href: '/menu/cafe', vi: 'Nhà hàng & Cafe', en: 'Restaurants & Cafes' },
    { href: '/store/mart', vi: 'Cửa hàng bán lẻ', en: 'Retail Store' },
    { href: '/store/online', vi: 'Bán hàng Online', en: 'Online Store' },
    { href: '/booking/wellness', vi: 'Spa & Dịch vụ', en: 'Spa & Services' }
  ];
  const frames = Array.from(carousel.querySelectorAll('.industry-frame'));
  const dots = Array.from(carousel.querySelectorAll('[data-industry-index]'));
  const caption = carousel.querySelector('[data-industry-caption]');
  const openLink = carousel.querySelector('[data-industry-link]');
  const fallback = carousel.querySelector('.industry-static-fallback');
  if (frames.length !== 2 || dots.length !== slides.length || !caption || !openLink) return;

  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const DELAY = 6200;
  let current = 0;
  let activeSlot = 0;
  let busy = false;
  let queued = null;
  let sequence = 0;
  let timer = null;
  let hovering = false;
  let focused = false;
  let touchStart = null;

  function isEnglish() {
    return document.documentElement.lang === 'en';
  }
  function paint() {
    const entry = slides[current];
    caption.textContent = isEnglish() ? entry.en : entry.vi;
    openLink.href = entry.href;
    openLink.textContent = isEnglish() ? 'Open live demo ↗' : 'Mở demo thật ↗';
    dots.forEach((dot, i) => {
      dot.classList.toggle('is-current', i === current);
      dot.setAttribute('aria-pressed', String(i === current));
      dot.setAttribute('aria-label',
        (isEnglish() ? 'Show ' : 'Xem ') + (isEnglish() ? slides[i].en : slides[i].vi));
    });
  }

  // Only load the active preview and its next neighbor, not four full applications.
  function loadFrame(slot, index, callback) {
    const frame = frames[slot];
    const wanted = String(index);
    if (frame.dataset.slide === wanted) {
      if (frame.dataset.ready === 'true') {
        callback();
      } else {
        frame.addEventListener('industry-preview-ready', () => {
          if (frame.dataset.slide === wanted) callback();
        }, { once: true });
      }
      return;
    }
    const request = String(++sequence);
    frame.dataset.job = request;
    frame.dataset.slide = wanted;
    frame.dataset.ready = 'false';
    frame.title = (isEnglish() ? slides[index].en : slides[index].vi) + ' — EZ Thing demo';

    frame.onload = () => {
      let settled = false;
      let observer = null;
      const finish = () => {
        if (settled) return;
        settled = true;
        if (observer) observer.disconnect();
        if (frame.dataset.job !== request) return;
        frame.dataset.ready = 'true';
        frame.dispatchEvent(new Event('industry-preview-ready'));
        callback();
      };
      try {
        const child = frame.contentDocument;
        if (child && child.querySelector('.merchant-hero')) {
          finish();
          return;
        }
        if (child && child.documentElement) {
          observer = new MutationObserver(() => {
            if (child.querySelector('.merchant-hero') ||
                child.querySelector('.customer-error, .customer-blocked')) finish();
          });
          observer.observe(child.documentElement, { childList: true, subtree: true });
        }
      } catch (_) {
        finish();
        return;
      }
      window.setTimeout(finish, 3500);
    };
    frame.src = slides[index].href;
  }

  function autoAllowed() {
    return !reduceMotion && !document.hidden && !hovering && !focused;
  }
  function scheduleAuto() {
    window.clearTimeout(timer);
    if (autoAllowed()) timer = window.setTimeout(() => goTo(current + 1), DELAY);
  }
  function prefetchNext(displayedIndex) {
    window.setTimeout(() => {
      if (busy || current !== displayedIndex || document.hidden) return;
      loadFrame(1 - activeSlot, (current + 1) % slides.length, () => {});
    }, 760);
  }
  function goTo(index) {
    const target = (index + slides.length) % slides.length;
    if (target === current && !busy) {
      scheduleAuto();
      return;
    }
    window.clearTimeout(timer);
    if (busy) {
      queued = target;
      return;
    }
    busy = true;
    const incoming = 1 - activeSlot;
    loadFrame(incoming, target, () => {
      if (queued !== null && queued !== target) {
        const requested = queued;
        queued = null;
        busy = false;
        goTo(requested);
        return;
      }
      queued = null;
      frames[incoming].classList.add('is-active');
      frames[activeSlot].classList.remove('is-active');
      activeSlot = incoming;
      current = target;
      carousel.classList.add('is-ready');
      if (fallback) fallback.setAttribute('hidden', '');
      paint();
      busy = false;
      scheduleAuto();
      prefetchNext(current);
    });
  }

  carousel.querySelectorAll('[data-industry-action]').forEach(button => {
    button.addEventListener('click', () => {
      goTo(current + (button.dataset.industryAction === 'previous' ? -1 : 1));
    });
  });
  dots.forEach((dot, index) => dot.addEventListener('click', () => goTo(index)));

  carousel.addEventListener('touchstart', event => {
    const t = event.changedTouches[0];
    if (t) touchStart = { x: t.clientX, y: t.clientY };
  }, { passive: true });
  carousel.addEventListener('touchend', event => {
    if (!touchStart) return;
    const t = event.changedTouches[0];
    if (!t) return;
    const dx = t.clientX - touchStart.x;
    const dy = t.clientY - touchStart.y;
    touchStart = null;
    if (Math.abs(dx) > 38 && Math.abs(dx) > Math.abs(dy) * 1.3) {
      goTo(current + (dx < 0 ? 1 : -1));
    }
  }, { passive: true });

  carousel.addEventListener('keydown', event => {
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
      event.preventDefault();
      goTo(current + (event.key === 'ArrowRight' ? 1 : -1));
    }
  });
  carousel.addEventListener('mouseenter', () => { hovering = true; scheduleAuto(); });
  carousel.addEventListener('mouseleave', () => { hovering = false; scheduleAuto(); });
  carousel.addEventListener('focusin', () => { focused = true; scheduleAuto(); });
  carousel.addEventListener('focusout', event => {
    if (!carousel.contains(event.relatedTarget)) {
      focused = false;
      scheduleAuto();
    }
  });
  document.addEventListener('visibilitychange', scheduleAuto);
  document.addEventListener('ezthing:language-changed', paint);

  paint();
  loadFrame(0, 0, () => {
    frames[0].classList.add('is-active');
    carousel.classList.add('is-ready');
    if (fallback) fallback.setAttribute('hidden', '');
    prefetchNext(0);
    scheduleAuto();
  });
})();