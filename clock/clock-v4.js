/* Live BTC Chart V4 (13 Nov 2026): full-screen chart / full-screen price.
   - Uses the Fullscreen API on the stage where available (desktop, iPad).
   - iPhone Safari has no element fullscreen: the html.v4-fs-* classes give
     the same full-viewport layout from CSS (fixed, 100dvh, safe areas).
   - Exit with the "Exit full screen" button or Esc.
   - After the stage resizes, a window resize is dispatched so the inline
     chart (btcchart-panel.js) redraws at the new size. */
(function () {
  var stage = document.getElementById('hero');
  if (!stage) return;
  var root = document.documentElement;
  var exitBtn = stage.querySelector('.v4-fs-exit');
  var btns = stage.querySelectorAll('.v4-fs-btn');
  var mode = null, opener = null;

  function fsEl() { return document.fullscreenElement || document.webkitFullscreenElement || null; }
  function canFs() {
    return !!(stage.requestFullscreen || stage.webkitRequestFullscreen) &&
      (document.fullscreenEnabled || document.webkitFullscreenEnabled);
  }
  function kick() {
    try { window.dispatchEvent(new Event('resize')); } catch (e) {}
    setTimeout(function () { try { window.dispatchEvent(new Event('resize')); } catch (e) {} }, 120);
  }
  function setBtns() {
    for (var i = 0; i < btns.length; i++) {
      btns[i].setAttribute('aria-pressed', btns[i].getAttribute('data-fs') === mode ? 'true' : 'false');
    }
  }
  function apply(m) {
    mode = m;
    root.classList.toggle('v4-fs-on', !!m);
    root.classList.toggle('v4-fs-chart', m === 'chart');
    root.classList.toggle('v4-fs-price', m === 'price');
    placeWake();
    setBtns();
    kick();
    after();
  }
  function enter(m, from) {
    opener = from || null;
    apply(m);
    if (canFs() && !fsEl()) {
      try {
        var p = stage.requestFullscreen ? stage.requestFullscreen() : stage.webkitRequestFullscreen();
        if (p && p.catch) p.catch(function () {}); /* CSS fallback stays on */
      } catch (e) {}
    }
    if (exitBtn) { try { exitBtn.focus({ preventScroll: true }); } catch (e) {} }
  }
  function exit() {
    if (!mode) return;
    var el = fsEl();
    if (el) {
      try {
        var p = document.exitFullscreen ? document.exitFullscreen() : document.webkitExitFullscreen();
        if (p && p.catch) p.catch(function () {});
      } catch (e) {}
    }
    apply(null);
    if (opener) { try { opener.focus({ preventScroll: true }); } catch (e) {} }
    opener = null;
  }
  for (var i = 0; i < btns.length; i++) {
    btns[i].addEventListener('click', function (e) {
      var m = this.getAttribute('data-fs');
      if (mode === m) exit(); else enter(m, this);
      e.stopPropagation();
    });
  }
  if (exitBtn) exitBtn.addEventListener('click', function (e) { e.stopPropagation(); exit(); });
  var toChart = stage.querySelector('.v4-fs-tochart');
  if (toChart) toChart.addEventListener('click', function (e) { e.stopPropagation(); enter('chart', this); });
  document.addEventListener('keydown', function (e) {
    if ((e.key === 'Escape' || e.key === 'Esc') && mode) exit();
  });
  function onFsChange() { if (!fsEl() && mode) exit(); else kick(); }
  document.addEventListener('fullscreenchange', onFsChange);
  document.addEventListener('webkitfullscreenchange', onFsChange);
  /* The controls only exist in the split layout; if the screen rotates to
     portrait while full screen, stay full screen (exit button is still there). */
  /* ---- 13 Nov 2026 fixes ---- */
  /* Fix 4: "Keep screen on" in full screen. The Fullscreen API only shows
     the stage, and the CSS fallback covers the page header, so the same
     button (same listeners, same wake lock code) moves into the stage's
     top-right bar beside Exit while full screen, and back afterwards. */
  var bar = stage.querySelector('.v4-fs-bar');
  var wake = document.getElementById('wakeBtn');
  var wakeHome = wake ? wake.parentNode : null, wakeNext = wake ? wake.nextSibling : null;
  function placeWake() {
    if (!wake || !bar || !wakeHome) return;
    if (mode) { if (wake.parentNode !== bar) bar.insertBefore(wake, bar.firstChild); }
    else if (wake.parentNode !== wakeHome) wakeHome.insertBefore(wake, wakeNext && wakeNext.parentNode === wakeHome ? wakeNext : null);
  }
  function barW() {
    if (!bar) return;
    var w = mode ? Math.ceil(bar.getBoundingClientRect().width) : 0;
    if (w > 0) stage.style.setProperty('--v4-fs-bar-w', w + 'px');
  }
  if (wake && window.MutationObserver) new MutationObserver(function () { if (mode) barW(); })
    .observe(wake, { childList: true, characterData: true, subtree: true, attributes: true, attributeFilter: ['hidden'] });

  /* Fix 1: full-screen price never clips. CSS sizes it; if a long price
     still does not fit the stage width, shrink it to fit. */
  var priceEl = document.getElementById('price');
  function fitPrice() {
    if (!priceEl) return;
    priceEl.style.fontSize = '';
    if (mode !== 'price') return;
    var cs = getComputedStyle(stage);
    var avail = stage.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
    var w = priceEl.scrollWidth;
    if (avail > 0 && w > avail) priceEl.style.fontSize = (parseFloat(getComputedStyle(priceEl).fontSize) * avail / w * 0.96) + 'px';
  }

  /* Fix 2: live, draggable BTC price pill in full-screen chart mode.
     Text mirrors the hero price + 24h change (same feed, no new fetch).
     Pointer events (mouse + touch), kept inside the chart box; the
     position is remembered for the session as fractions of the free space. */
  var pill = document.getElementById('pxPill');
  var pillVal = document.getElementById('pxPillVal'), pillChg = document.getElementById('pxPillChg');
  var chgEl = document.getElementById('chg');
  var plot = stage.querySelector('.v4-plot');
  var KEY = 'ps-clock-pxpill', pos = null, drag = null;
  try { var sv = JSON.parse(sessionStorage.getItem(KEY) || 'null'); if (sv && isFinite(sv.fx) && isFinite(sv.fy)) pos = { fx: sv.fx, fy: sv.fy }; } catch (e) {}
  function syncPill() {
    if (!pill || !priceEl) return;
    var t = (priceEl.textContent || '').trim();
    pillVal.innerHTML = '<span class="v4-px-sym">\u20bf</span> ' + (t || '\u2014').replace(/</g, '&lt;');
    var c = chgEl ? (chgEl.textContent || '').replace(/\s*\u00b7\s*24h\s*$/, '').trim() : '';
    pillChg.textContent = c && c !== '\u2014' ? c : '';
    pillChg.className = 'v4-px-chg' + (chgEl && /\bup\b/.test(chgEl.className) ? ' up' : chgEl && /\bdown\b/.test(chgEl.className) ? ' down' : '');
    pill.setAttribute('aria-label', 'Live BTC price ' + (t || '') + (c ? ', ' + c + ' over 24 hours' : '') + '. Use arrow keys to move (Shift for bigger steps), Home to reset, or drag it.');
  }
  function bounds() {
    var box = stage.querySelector('.bc-box');
    if (!box || !plot || !pill) return null;
    var pr = plot.getBoundingClientRect(), br = box.getBoundingClientRect();
    var sr = stage.getBoundingClientRect();
    if (!br.width || !br.height) return null;
    var pw = pill.offsetWidth, ph = pill.offsetHeight, m = 6;
    var vw = window.innerWidth || sr.right, vh = window.innerHeight || sr.bottom;
    /* Stay inside the chart box and fully on screen (the 2x pill is wider,
       including a $100k / C$140k price on iPhone landscape). */
    var left = Math.max(br.left + m, sr.left + m, m);
    var top = Math.max(br.top + m, sr.top + m, m);
    var right = Math.min(br.right - m, sr.right - m, vw - m);
    var bottom = Math.min(br.bottom - m, sr.bottom - m, vh - m);
    /* Do not cover Exit or Keep screen on. */
    var barEl = stage.querySelector('.v4-fs-bar');
    if (barEl && barEl.offsetWidth) {
      var ar = barEl.getBoundingClientRect(), g = 6;
      var aL = ar.left - g, aT = ar.top - g, aR = ar.right + g, aB = ar.bottom + g;
      if (left < aR && right > aL && top < aB && bottom > aT) {
        if (bottom - aB >= ph) top = Math.max(top, aB);
        else if (aL - left >= pw) right = Math.min(right, aL);
        else if (bottom - aB > aL - left) top = Math.max(top, aB);
        else right = Math.min(right, aL);
      }
    }
    if (right < left) right = left;
    if (bottom < top) bottom = top;
    var x0 = left - pr.left, y0 = top - pr.top;
    var sx = Math.max(0, right - left - pw), sy = Math.max(0, bottom - top - ph);
    /* If the pill is wider/taller than the remaining box, pin it so as much
       as possible stays on screen instead of overflowing the right/bottom. */
    if (pw > right - left) {
      var visR = Math.min(vw - m, sr.right - m);
      x0 = Math.min(x0, visR - pw - pr.left);
      sx = 0;
    }
    if (ph > bottom - top) {
      var visB = Math.min(vh - m, sr.bottom - m);
      y0 = Math.min(y0, visB - ph - pr.top);
      sy = 0;
    }
    return { x0: x0, y0: y0, sx: sx, sy: sy };
  }
  function placePill() {
    if (!pill || mode !== 'chart') return;
    var b = bounds(); if (!b) return;
    var fx = pos ? pos.fx : 0.5, fy = pos ? pos.fy : 0.02; /* default: top centre of the chart */
    fx = Math.min(1, Math.max(0, fx)); fy = Math.min(1, Math.max(0, fy));
    pill.style.transform = 'translate(' + Math.round(b.x0 + fx * b.sx) + 'px,' + Math.round(b.y0 + fy * b.sy) + 'px)';
  }
  if (pill) {
    pill.addEventListener('pointerdown', function (e) {
      if (mode !== 'chart' || (e.pointerType === 'mouse' && e.button !== 0)) return;
      var b = bounds(); if (!b) return;
      var m = /translate\((-?[\d.]+)px,\s*(-?[\d.]+)px\)/.exec(pill.style.transform || '');
      var cx = m ? +m[1] : b.x0, cy = m ? +m[2] : b.y0;
      drag = { id: e.pointerId, dx: e.clientX - cx, dy: e.clientY - cy, b: b };
      try { pill.setPointerCapture(e.pointerId); } catch (er) {}
      pill.classList.add('dragging');
      e.preventDefault(); e.stopPropagation();
    });
    pill.addEventListener('pointermove', function (e) {
      if (!drag || e.pointerId !== drag.id) return;
      var b = drag.b;
      var x = Math.min(b.x0 + b.sx, Math.max(b.x0, e.clientX - drag.dx));
      var y = Math.min(b.y0 + b.sy, Math.max(b.y0, e.clientY - drag.dy));
      pos = { fx: b.sx ? (x - b.x0) / b.sx : 0, fy: b.sy ? (y - b.y0) / b.sy : 0 };
      pill.style.transform = 'translate(' + Math.round(x) + 'px,' + Math.round(y) + 'px)';
      e.preventDefault(); e.stopPropagation();
    });
    var endDrag = function (e) {
      if (!drag || e.pointerId !== drag.id) return;
      drag = null; pill.classList.remove('dragging');
      try { pill.releasePointerCapture(e.pointerId); } catch (er) {}
      try { if (pos) sessionStorage.setItem(KEY, JSON.stringify(pos)); } catch (er) {}
      e.stopPropagation();
    };
    pill.addEventListener('pointerup', endDrag);
    pill.addEventListener('pointercancel', endDrag);
    pill.addEventListener('click', function (e) { e.stopPropagation(); });
    /* Keyboard: arrows move ~10px (Shift: 40px), clamped to the chart box and
       saved like a drag; Home goes back to the default spot. */
    pill.addEventListener('keydown', function (e) {
      if (mode !== 'chart') return;
      var k = e.key, step = e.shiftKey ? 40 : 10, dx = 0, dy = 0;
      if (k === 'Home') {
        pos = null;
        try { sessionStorage.removeItem(KEY); } catch (er) {}
        placePill(); e.preventDefault(); e.stopPropagation(); return;
      }
      if (k === 'ArrowLeft') dx = -step; else if (k === 'ArrowRight') dx = step;
      else if (k === 'ArrowUp') dy = -step; else if (k === 'ArrowDown') dy = step;
      else return;
      var b = bounds(); if (!b) return;
      var m = /translate\((-?[\d.]+)px,\s*(-?[\d.]+)px\)/.exec(pill.style.transform || '');
      var cx = m ? +m[1] : b.x0, cy = m ? +m[2] : b.y0;
      var x = Math.min(b.x0 + b.sx, Math.max(b.x0, cx + dx));
      var y = Math.min(b.y0 + b.sy, Math.max(b.y0, cy + dy));
      pos = { fx: b.sx ? (x - b.x0) / b.sx : 0, fy: b.sy ? (y - b.y0) / b.sy : 0 };
      pill.style.transform = 'translate(' + Math.round(x) + 'px,' + Math.round(y) + 'px)';
      try { sessionStorage.setItem(KEY, JSON.stringify(pos)); } catch (er) {}
      e.preventDefault(); e.stopPropagation();
    });
    syncPill();
    if (window.MutationObserver) {
      var mo = new MutationObserver(function () { syncPill(); if (mode === 'chart') placePill(); });
      if (priceEl) mo.observe(priceEl, { childList: true, characterData: true, subtree: true });
      if (chgEl) mo.observe(chgEl, { childList: true, characterData: true, subtree: true, attributes: true, attributeFilter: ['class'] });
    }
  }
  if (priceEl && window.MutationObserver) new MutationObserver(function () { if (mode === 'price') fitPrice(); })
    .observe(priceEl, { childList: true, characterData: true, subtree: true });
  function layout() { barW(); fitPrice(); placePill(); }
  function after() {
    try { requestAnimationFrame(layout); } catch (e) { layout(); }
    setTimeout(layout, 150); setTimeout(layout, 400);
  }
  window.addEventListener('resize', function () { if (mode) after(); });
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { if (mode) layout(); });

  window.__psClockFs = { enter: enter, exit: exit, mode: function () { return mode; } };
})();
