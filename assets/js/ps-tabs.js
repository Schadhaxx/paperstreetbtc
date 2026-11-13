/* iPhone tab nav (13 Nov 2026).
   1) Overflow-only chevrons: each .ps-row shows its chevron + edge fade
      ONLY when its scroller really overflows (scrollWidth > clientWidth).
      Right hides at the end, left shows once scrolled. Re-checked on
      ResizeObserver, scroll, resize, orientation change and font load, so
      a useless arrow never sits on a row that already fits.
   2) Sleeves sub-row: the Sleeves tab is a disclosure button
      (aria-expanded / aria-controls) that toggles the second row.
      Tapping Sleeves again, tapping outside, or Esc closes it. On a page
      that belongs to the Sleeves section (Monthly Recap pages) the row
      starts open with the current item highlighted.
   3) Current page highlighting from the URL (path + hash). */
(function () {
  var nav = document.querySelector('.ps-tabs');
  if (!nav) return;
  var rows = [].slice.call(nav.querySelectorAll('.ps-row'));
  var drop = nav.querySelector('.ps-tab-drop');
  var sub = drop ? document.getElementById(drop.getAttribute('aria-controls')) : null;

  function wire(row) {
    var sc = row.querySelector('.ps-tabs-scroller');
    if (!sc) return null;
    var l = row.querySelector('.ps-tab-chev-l'), r = row.querySelector('.ps-tab-chev-r');
    var ticking = false;
    function update() {
      ticking = false;
      var visible = row.offsetParent !== null || getComputedStyle(row).position === 'fixed';
      var overflow = visible && sc.scrollWidth > sc.clientWidth + 1;
      var atStart = sc.scrollLeft <= 2;
      var atEnd = sc.scrollLeft + sc.clientWidth >= sc.scrollWidth - 2;
      row.classList.toggle('is-overflow', overflow);
      row.classList.toggle('is-fit', !overflow);
      row.classList.toggle('is-show-left', overflow && !atStart);
      row.classList.toggle('is-show-right', overflow && !atEnd);
      if (l) { l.hidden = !(overflow && !atStart); l.setAttribute('aria-hidden', l.hidden ? 'true' : 'false'); }
      if (r) { r.hidden = !(overflow && !atEnd); r.setAttribute('aria-hidden', r.hidden ? 'true' : 'false'); }
    }
    function schedule() { if (ticking) return; ticking = true; requestAnimationFrame(update); }
    function page(dir) { sc.scrollBy({ left: Math.round(sc.clientWidth * 0.85) * dir, behavior: 'smooth' }); }
    if (l) l.addEventListener('click', function (e) { e.stopPropagation(); page(-1); });
    if (r) r.addEventListener('click', function (e) { e.stopPropagation(); page(1); });
    sc.addEventListener('scroll', schedule, { passive: true });
    addEventListener('resize', schedule);
    addEventListener('orientationchange', function () { setTimeout(update, 80); });
    if (window.ResizeObserver) { var ro = new ResizeObserver(schedule); ro.observe(sc); ro.observe(row); }
    if (window.MutationObserver) new MutationObserver(schedule).observe(sc, { childList: true, subtree: true, characterData: true });
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(update);
    if (sc.scrollLeft > 0 && sc.scrollLeft < 12) sc.scrollLeft = 0;
    update();
    return update;
  }
  var updaters = rows.map(wire).filter(Boolean);
  function updateAll() { updaters.forEach(function (u) { u(); }); }
  window.__psTabsUpdate = updateAll;

  function norm(p) { return (p || '/').replace(/\/index\.html$/, '/').replace(/\/+$/, '') || '/'; }
  function matches(a) {
    var href = a.getAttribute('href') || '';
    try {
      var u = new URL(href, location.href);
      var up = norm(u.pathname), lp = norm(location.pathname);
      /* every monthly recap page belongs to "Monthly Recap" */
      if (/\/recap$/.test(up) && /\/recap(\/|$)/.test(lp) && !u.hash) return true;
      if (up !== lp) return false;
      return !u.hash || u.hash === location.hash;
    } catch (e) { return false; }
  }
  function markCurrent() {
    var any = false;
    nav.querySelectorAll('.ps-main a[href]').forEach(function (a) {
      var on = matches(a);
      a.classList.toggle('is-current', on);
      if (on) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
    });
    if (sub) {
      sub.querySelectorAll('a[href]').forEach(function (a) {
        var on = matches(a);
        if (on) any = true;
        a.classList.toggle('is-current', on);
        if (on) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
      });
    }
    if (drop) drop.classList.toggle('is-current', any);
    return any;
  }

  function setOpen(open, byUser) {
    if (!drop || !sub) return;
    sub.hidden = !open;
    drop.setAttribute('aria-expanded', open ? 'true' : 'false');
    updateAll();
    if (open) {
      var cur = sub.querySelector('a.is-current');
      var sc = sub.querySelector('.ps-tabs-scroller');
      if (cur && sc && cur.offsetLeft + cur.offsetWidth > sc.clientWidth) sc.scrollLeft = cur.offsetLeft - 24;
    }
  }
  if (drop && sub) {
    drop.addEventListener('click', function (e) { e.stopPropagation(); setOpen(sub.hidden, true); });
    sub.addEventListener('click', function (e) { if (e.target.closest('a')) setOpen(false); });
    /* pointerdown, not click: iOS Safari often sends no click for taps on
       plain, non-clickable content, so the outside tap would be missed. */
    document.addEventListener('pointerdown', function (e) {
      if (!sub.hidden && !nav.contains(e.target)) setOpen(false);
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !sub.hidden) { setOpen(false); drop.focus(); }
    });
  }
  var inSection = markCurrent();
  /* Sleeves-section pages (Monthly Recap pages) start with the row open. */
  if (inSection && /\/recap\//.test(location.pathname)) setOpen(true, false);
  addEventListener('hashchange', markCurrent);
  updateAll();
})();
