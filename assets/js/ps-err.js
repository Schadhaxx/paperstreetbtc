/* PaperStreet page-error reporter (Stage 2 analytics, 27 Nov 2026).
   Loaded in <head> immediately before chart-theme.js on the 16 public
   pages. Installs window.onerror + unhandledrejection once, and exposes
   window.__psErr(kind, message, file, line) for the BTC chart lineFail path.
   Reports go to the paperstreet-quotes Worker POST /err (text/plain, JSON
   body, no cookies). No personal data: path is the pathname only, file is
   a basename, browser/device are parsed client-side (the raw UA is never
   sent). The whole file lives in try/catch and never throws or blocks the
   page. Sends are fire-and-forget.
   Respects the /me/ opt-out (localStorage 'ps-no-count' = '1') and skips
   automated browsers (navigator.webdriver / headless UA), so bot test runs
   do not count. A ?src= tag on arrival is kept for the tab session
   (sessionStorage 'ps-src') and rides along on every report. */
(function () {
  try {
    var EP = 'https://paperstreet-quotes.schadha08.workers.dev/err';
    var PIN = 'err1';
    var MAX_PER_LOAD = 5; // at most 5 reports per page load
    var MIN_GAP_MS = 10000; // at least 10 s apart (lineFail retries often)
    var optedOut = false;
    var isBot = false;
    try { optedOut = localStorage.getItem('ps-no-count') === '1'; } catch (e) {}
    try { isBot = !!navigator.webdriver || /HeadlessChrome|headless/i.test(navigator.userAgent || ''); } catch (e) {}
    // ?src= tag on arrival (e.g. ?src=x, ?src=email): tab session only.
    var src = '';
    try {
      var q = null;
      try { q = new URLSearchParams(location.search).get('src'); } catch (e) {}
      if (q && /^[A-Za-z0-9._-]{1,40}$/.test(q)) {
        src = q;
        try { sessionStorage.setItem('ps-src', q); } catch (e) {}
      } else {
        try { src = sessionStorage.getItem('ps-src') || ''; } catch (e) {}
      }
    } catch (e) {}
    function browser() {
      try {
        var u = navigator.userAgent || '';
        if (/Edg\//.test(u)) return 'Edge';
        if (/Firefox\//.test(u)) return 'Firefox';
        if (/Chrome\//.test(u)) return 'Chrome';
        if (/Safari\//.test(u)) return 'Safari';
      } catch (e) {}
      return 'Other';
    }
    function device() {
      try { if (/Mobi|Android|iPhone|iPad|iPod/i.test(navigator.userAgent || '')) return 'phone'; } catch (e) {}
      return 'desktop';
    }
    function base(file) {
      try {
        file = String(file || '').split('?')[0].split('#')[0];
        var i = file.lastIndexOf('/');
        return (i >= 0 ? file.slice(i + 1) : file).slice(0, 80);
      } catch (e) { return ''; }
    }
    var sent = 0;
    var lastSent = 0;
    function send(kind, message, file, line) {
      if (optedOut || isBot) return;
      if (sent >= MAX_PER_LOAD) return;
      var now = Date.now();
      if (sent > 0 && now - lastSent < MIN_GAP_MS) return;
      sent++;
      lastSent = now;
      var payload = { path: '', message: '', file: '', line: 0, browser: browser(), device: device(), pin: PIN, kind: kind, src: src };
      try { payload.path = String(location.pathname || '/').slice(0, 100); } catch (e) { payload.path = '/'; }
      try { payload.message = String(message == null ? '' : message).slice(0, 200); } catch (e) {}
      payload.file = base(file);
      var ln = parseInt(line, 10);
      payload.line = isFinite(ln) ? ln : 0;
      var body = '';
      try { body = JSON.stringify(payload); } catch (e) { return; }
      try {
        if (navigator.sendBeacon) {
          var b = new Blob([body], { type: 'text/plain' });
          if (navigator.sendBeacon(EP, b)) return;
        }
      } catch (e) {}
      try {
        fetch(EP, { method: 'POST', mode: 'cors', credentials: 'omit', keepalive: true, headers: { 'Content-Type': 'text/plain' }, body: body });
      } catch (e) {}
    }
    // One-line hook for the BTC chart lineFail path (btcchart-panel.js).
    window.__psErr = function (kind, message, file, line) {
      try { send(kind, message, file, line); } catch (e) {}
    };
    window.addEventListener('error', function (ev) {
      try { send('onerror', ev && ev.message, ev && ev.filename, ev && ev.lineno); } catch (e) {}
    });
    window.addEventListener('unhandledrejection', function (ev) {
      try {
        var r = ev && ev.reason;
        send('unhandledrejection', r && r.message !== undefined ? r.message : String(r), '', 0);
      } catch (e) {}
    });
  } catch (e) {}
})();
