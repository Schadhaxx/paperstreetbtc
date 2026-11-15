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
    setBtns();
    kick();
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
  document.addEventListener('keydown', function (e) {
    if ((e.key === 'Escape' || e.key === 'Esc') && mode) exit();
  });
  function onFsChange() { if (!fsEl() && mode) exit(); else kick(); }
  document.addEventListener('fullscreenchange', onFsChange);
  document.addEventListener('webkitfullscreenchange', onFsChange);
  /* The controls only exist in the split layout; if the screen rotates to
     portrait while full screen, stay full screen (exit button is still there). */
  window.__psClockFs = { enter: enter, exit: exit, mode: function () { return mode; } };
})();
