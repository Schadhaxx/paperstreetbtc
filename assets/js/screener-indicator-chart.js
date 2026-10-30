// Shared indicator candle chart — Maple Leaf Screener (test branch
// pepper-indicator-charts-wti, 30 Oct 2026).
// ONE generic module for every Market Indicator candle chart. Do NOT
// copy this file per indicator: add a config entry in CONFIGS below
// and a shipped weekly JSON file, and wire the tile in screener.html.
// This module replaces assets/js/screener-gold.js (deleted on this
// branch): gold now runs through this module with the same data,
// values, "+" behaviour, month x-axis and left current line as before.
// Data is SHIPPED WITH the screener only. There is NO Yahoo browser
// fetch fallback in this module: that fallback failed live for gold
// on 30 Oct 2026 (load error, Retry failed), so it was dropped. If
// the shipped file is missing or unreadable, the modal says so
// plainly with a Retry button; it never invents candles and never
// labels a failure as live.
// Pattern, copied from gold: tap the indicator tile itself (not its
// "+" button) opens "SYMBOL — YTD weekly candles"; weekly candles,
// UTC Monday-Sunday weeks, YTD only; candle colours green #22c55e /
// red #ef4444; one x-axis label per month (3-letter month, first
// candle of that month by Thursday); a dashed cyan current line
// spans the chart at the latest weekly close, labelled at its LEFT
// end, by the y-axis; the top description blurb and the bottom
// source blurb each hide behind a small "+" button that opens a
// popup pill INSIDE the modal with the blurb's text word for word;
// tap a candle for its week + O/H/L/C in a pill; dismiss by close
// button, tap outside, or Escape (Escape dismisses the info popup
// first, the modal second). iPhone-first: one-column modal.
(function () {
  function fmtMoney(v) {
    return '$' + v.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }
  // Yields are in percent, never dollars: 3 decimals, so displayed
  // values match the shipped JSON exactly (the screener tile rounds
  // to 2 decimals — a display rounding difference, not a data one).
  function fmtYield(v) {
    return v.toFixed(3) + '%';
  }
  function fmtDateUTC(d) {
    var MN = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return d.getUTCDate() + ' ' + MN[d.getUTCMonth()] + ' ' + d.getUTCFullYear();
  }
  function el(id) { return document.getElementById(id); }

  // CONFIGS: one entry per indicator chart. "format" formats a price
  // level in that indicator's unit. "lastInProgress" (WTI only) is
  // the label for a latest week built from an intraday bar, not a
  // final close — it must never be called a daily close.
  var CONFIGS = {
    GOLD: {
      symbol: 'GOLD',
      title: 'Gold — YTD weekly candles',
      dataUrl: 'assets/data/gold-weekly.json?v=2',
      format: fmtMoney,
      currentPrefix: 'Current ',
      subBlurb: 'COMEX gold futures (GC=F), $/troy oz. Weekly candles, UTC Monday–Sunday weeks, 1 Jan 2026 to the latest week. Candles are shipped with this page, data as of 30 Oct 2026 — a dated snapshot, not a live quote. Tap a candle for its week and open / high / low / close.',
      lastInProgress: null
    },
    WTI: {
      symbol: 'WTI',
      title: 'WTI — YTD weekly candles',
      dataUrl: 'assets/data/wti-weekly.json?v=1',
      format: fmtMoney,
      currentPrefix: 'Current ',
      subBlurb: 'NYMEX front-month WTI futures (CL=F), $/barrel. Weekly candles, UTC Monday–Sunday weeks, 1 Jan 2026 to the latest week. WTI is a continuous front-month series — there are gaps where contracts roll over. Candles are shipped with this page, data as of 30 Oct 2026, 3:42 p.m. ET — a dated snapshot, not a live quote. The latest week is in progress, not a final close. Tap a candle for its week and open / high / low / close.',
      lastInProgress: 'in progress, as of 30 Oct 2026, 3:42 p.m. ET'
    },
    US10Y: {
      symbol: 'US10Y',
      title: '10-Year — YTD weekly candles',
      dataUrl: 'assets/data/us10y-weekly.json?v=1',
      format: fmtYield,
      currentPrefix: 'Current ',
      subBlurb: '10-Year Treasury Yield, Yahoo ^TNX (CBOE Interest Rate 10 Year T Note), in %. Weekly candles, UTC Monday–Sunday weeks, 1 Jan 2026 to the latest week. Candles are shipped with this page, data as of 30 Oct 2026 — a dated snapshot, not a live quote. The latest week is a final close, not in progress. Tap a candle for its week and open / high / low / close in %.',
      lastInProgress: null,
      ppChange: true,
      footNote: ' Source is Yahoo ^TNX (CBOE Interest Rate 10 Year T Note), not Treasury par yield. Latest week is a final close (30 Oct 2026 yield 4.929%), not in progress. Manual refresh only, when Sunil asks.'
    }
  };

  var state = { cfg: null, weeks: [], loading: false, selected: -1, footerText: '', infoOpen: false, infoText: '', loadedSymbol: '', loadToken: 0 };

  // Reset EVERYTHING the previous symbol left on screen, before the
  // new symbol's title is shown. This is the stale-state fix (Grok
  // Bot review, 30 Oct 2026): a candle pill, info popup, source "+",
  // selection or canvas from the old symbol must never survive a
  // symbol switch, even while the new symbol is still loading.
  function resetModalVisuals() {
    state.selected = -1;
    var pill = el('ind-pill');
    if (pill) pill.style.display = 'none';
    hideInfo();
    state.footerText = '';
    var footBtn = el('ind-info-foot');
    if (footBtn) footBtn.style.display = 'none';
    var canvas = el('ind-canvas');
    if (canvas) {
      var ctx = canvas.getContext('2d');
      if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
      delete canvas._plot;
    }
  }

  function showInfo(text) {
    var pill = el('ind-info-pill'), span = el('ind-info-text');
    if (!pill || !span) return;
    span.textContent = text;
    pill.style.display = 'block';
    state.infoOpen = true; state.infoText = text;
  }
  function hideInfo() {
    var pill = el('ind-info-pill');
    if (pill) pill.style.display = 'none';
    state.infoOpen = false; state.infoText = '';
  }
  function toggleInfo(text) {
    if (state.infoOpen && state.infoText === text) hideInfo();
    else showInfo(text);
  }
  function showFooterInfo(text) {
    state.footerText = text;
    var s = el('ind-status');
    if (s) s.style.display = 'none';
    var btn = el('ind-info-foot');
    if (btn) btn.style.display = 'inline-flex';
  }
  function setStatus(text, isError) {
    var s = el('ind-status');
    if (s) { s.textContent = text; s.style.color = isError ? '#ef4444' : '#94a3b8'; s.style.display = 'block'; }
  }
  function weeksFromStatic(data) {
    if (!data || !data.weeks || !data.weeks.length) throw new Error('no static weeks');
    return data.weeks.map(function (w) {
      return { monday: new Date(w.monday), sunday: new Date(w.sunday), label: w.label, days: w.days, open: w.open, high: w.high, low: w.low, close: w.close };
    });
  }

  function openModal(cfg) {
    var m = el('ind-modal');
    if (!m) return;
    var switched = !state.cfg || state.cfg.symbol !== cfg.symbol;
    state.cfg = cfg;
    var t = el('ind-title');
    if (t) t.textContent = cfg.title;
    var sub = el('ind-sub');
    if (sub) sub.textContent = cfg.subBlurb;
    m.classList.add('open');
    m.setAttribute('aria-hidden', 'false');
    // A different symbol always starts blank: clear the old pill,
    // popup, source "+" and canvas, and invalidate any load still
    // in flight for the old symbol (its response is ignored below).
    // A same-symbol reopen keeps its loaded weeks but still clears
    // the old candle selection/pill so it cannot linger either.
    resetModalVisuals();
    if (switched) {
      state.loadToken++;
      state.weeks = [];
      state.loadedSymbol = '';
      loadData();
    } else if (state.weeks.length && state.loadedSymbol === cfg.symbol) {
      draw();
    } else {
      state.weeks = [];
      loadData();
    }
  }
  function closeModal() {
    var m = el('ind-modal');
    if (!m) return;
    m.classList.remove('open');
    m.setAttribute('aria-hidden', 'true');
  }

  // Shipped file ONLY — no browser fetch fallback (see header).
  function loadData() {
    var cfg = state.cfg;
    // Token-guard the async load: a response that arrives after the
    // symbol has changed (slow connection, or a retry for the old
    // symbol) is ignored entirely — it must not draw, must not set
    // the current line, and must not leave the old chart on screen.
    var token = ++state.loadToken;
    state.loading = true;
    setStatus('Loading ' + cfg.symbol + ' weekly candles…');
    var r = el('ind-retry');
    if (r) r.style.display = 'none';
    fetch(cfg.dataUrl)
      .then(function (res) { if (!res.ok) throw new Error('no static file'); return res.json(); })
      .then(function (data) {
        if (token !== state.loadToken || !state.cfg || state.cfg.symbol !== cfg.symbol) return; // stale response: ignore
        state.weeks = weeksFromStatic(data);
        state.loadedSymbol = cfg.symbol;
        var last = state.weeks[state.weeks.length - 1];
        var foot = 'Source: ' + (data.source || cfg.symbol) + ', weekly candles shipped with the screener, data as of ' + (data.asOf || '30 Oct 2026') + ' · latest week ends ' + fmtDateUTC(last.sunday) + ' · ' + state.weeks.length + ' weekly candles, YTD — a dated snapshot, not a live quote. First week is partial: 1 trading day (2 Jan 2026), week starting 29 Dec 2025.';
        if (cfg.symbol === 'WTI') foot += ' WTI is a continuous front-month series — there are gaps where contracts roll over. Latest week in progress, as of 30 Oct 2026, 3:42 p.m. ET — its close is an intraday snapshot, not a daily close. Manual refresh only, when Sunil asks.';
        if (cfg.footNote) foot += cfg.footNote;
        state.loading = false;
        showFooterInfo(foot);
        draw();
      })
      .catch(function () {
        if (token !== state.loadToken || !state.cfg || state.cfg.symbol !== cfg.symbol) return; // stale failure: ignore
        // A failed load for the NEW symbol must clear the previous
        // chart, not leave it drawn under the new title.
        state.weeks = [];
        state.loadedSymbol = '';
        resetModalVisuals();
        state.loading = false;
        setStatus(cfg.symbol + ' weekly candles could not be loaded. Check your connection and tap Retry — no chart is shown until real data arrives.', true);
        var rr = el('ind-retry');
        if (rr) rr.style.display = 'inline-block';
      });
  }

  function draw() {
    var canvas = el('ind-canvas');
    if (!canvas || !state.weeks.length) return;
    // Never draw weeks that belong to a different symbol than the
    // one the modal is currently showing.
    if (state.loadedSymbol && state.cfg && state.loadedSymbol !== state.cfg.symbol) return;
    var dpr = window.devicePixelRatio || 1;
    var cssW = canvas.clientWidth || 320;
    var cssH = 280;
    canvas.width = Math.round(cssW * dpr);
    canvas.height = Math.round(cssH * dpr);
    canvas.style.height = cssH + 'px';
    var ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, cssW, cssH);
    var padL = 62, padR = 8, padT = 10, padB = 30;
    var plotW = cssW - padL - padR, plotH = cssH - padT - padB;
    var lo = Infinity, hi = -Infinity;
    state.weeks.forEach(function (w) { lo = Math.min(lo, w.low); hi = Math.max(hi, w.high); });
    var span = hi - lo || 1;
    lo -= span * 0.05; hi += span * 0.05;
    function y(v) { return padT + (hi - v) / (hi - lo) * plotH; }
    var fmt = state.cfg.format;
    ctx.font = '11px -apple-system, system-ui, sans-serif';
    ctx.fillStyle = '#94a3b8';
    ctx.strokeStyle = 'rgba(255,255,255,0.08)';
    for (var g = 0; g <= 4; g++) {
      var v = lo + (hi - lo) * g / 4;
      var yy = y(v);
      ctx.beginPath(); ctx.moveTo(padL, yy); ctx.lineTo(cssW - padR, yy); ctx.stroke();
      ctx.fillText(fmt(v), 4, yy + 4);
    }
    var n = state.weeks.length;
    var slot = plotW / n;
    var bw = Math.max(2, Math.min(14, slot * 0.6));
    var seenMonths = {};
    state.weeks.forEach(function (w, i) {
      var cx = padL + slot * i + slot / 2;
      var up = w.close >= w.open;
      var col = up ? '#22c55e' : '#ef4444';
      ctx.strokeStyle = col; ctx.fillStyle = col; ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.moveTo(cx, y(w.high)); ctx.lineTo(cx, y(w.low)); ctx.stroke();
      var top = y(Math.max(w.open, w.close)), bot = y(Math.min(w.open, w.close));
      ctx.fillRect(cx - bw / 2, top, bw, Math.max(1, bot - top));
      if (i === state.selected) {
        ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 1.5;
        ctx.strokeRect(cx - bw / 2 - 3, y(w.high) - 3, bw + 6, y(w.low) - y(w.high) + 6);
      }
      var thu = new Date(w.monday.getTime() + 3 * 86400000);
      var mkey = thu.getUTCFullYear() + '-' + thu.getUTCMonth();
      if (!seenMonths[mkey]) {
        seenMonths[mkey] = true;
        ctx.fillStyle = '#94a3b8';
        ctx.font = '10px -apple-system, system-ui, sans-serif';
        var lab = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][thu.getUTCMonth()];
        ctx.fillText(lab, Math.max(padL, Math.min(cx - 9, cssW - padR - 22)), cssH - 10);
        ctx.font = '11px -apple-system, system-ui, sans-serif';
      }
    });
    // Current line: horizontal dashed cyan at the latest weekly
    // close, read from the shipped data (never hardcoded), labelled
    // at the LEFT end, by the y-axis. For WTI the latest week is in
    // progress, so the label says so — its close is not a daily close.
    var current = state.weeks[n - 1].close;
    var cy = y(current);
    ctx.save();
    ctx.strokeStyle = '#22d3ee'; ctx.lineWidth = 1.5; ctx.setLineDash([6, 4]);
    ctx.beginPath(); ctx.moveTo(padL, cy); ctx.lineTo(cssW - padR, cy); ctx.stroke();
    ctx.setLineDash([]);
    var curLab = state.cfg.currentPrefix + fmt(current);
    if (state.cfg.lastInProgress) curLab += ' (in progress)';
    ctx.font = 'bold 11px -apple-system, system-ui, sans-serif';
    var tw = ctx.measureText(curLab).width;
    var lx = padL + 6;
    var ly = cy - 8;
    if (ly < 14) ly = cy + 16;
    ctx.fillStyle = '#22d3ee';
    ctx.fillRect(lx - 4, ly - 11, tw + 8, 16);
    ctx.fillStyle = '#0b1226';
    ctx.fillText(curLab, lx, ly);
    ctx.restore();
    canvas._plot = { padL: padL, slot: slot, n: n };
  }

  function onCanvasTap(e) {
    var canvas = el('ind-canvas');
    if (!canvas || !canvas._plot) return;
    if (state.infoOpen) { hideInfo(); return; }
    var rect = canvas.getBoundingClientRect();
    var x = (e.clientX - rect.left) - canvas._plot.padL;
    var idx = Math.floor(x / canvas._plot.slot);
    if (idx < 0 || idx >= state.weeks.length) return;
    state.selected = idx;
    var w = state.weeks[idx];
    var chg = (w.close / w.open - 1) * 100;
    var isLast = idx === state.weeks.length - 1;
    var pill = el('ind-pill');
    if (pill) {
      var html = '<b>Week ' + w.label + ' (UTC, ' + w.days + ' trading day' + (w.days === 1 ? ' — partial week' : 's') + ')</b><br>'
        + 'Open ' + state.cfg.format(w.open) + ' · High ' + state.cfg.format(w.high) + ' · Low ' + state.cfg.format(w.low) + ' · Close ' + state.cfg.format(w.close);
      // Yields move in percentage points: for ppChange symbols the pill
      // LEADS with the pp move, then the relative % in parentheses
      // (Sunil decision 30 Oct 2026, Grok Bot recommendation) — so
      // "-0.074 pp" cannot be misread as a 1.48-point fall. Dollar-price
      // symbols (gold, WTI) keep the old "Week change x.xx%" lead.
      if (state.cfg.ppChange) {
        var pp = w.close - w.open;
        html += '<br>Week change ' + (pp >= 0 ? '+' : '') + pp.toFixed(3) + ' pp (' + (chg >= 0 ? '+' : '') + chg.toFixed(2) + '%)';
      } else {
        html += '<br>Week change ' + (chg >= 0 ? '+' : '') + chg.toFixed(2) + '%';
      }
      if (isLast && state.cfg.lastInProgress) html += '<br><i>Latest week ' + state.cfg.lastInProgress + ' — close is not a final daily close.</i>';
      pill.style.display = 'block';
      pill.innerHTML = html;
    }
    draw();
  }

  document.addEventListener('click', function (e) {
    var btn = e.target.closest ? e.target.closest('.note-btn') : null;
    if (btn) return; // "+" note button keeps its own job.
    if (state.infoOpen) {
      var inDialog = e.target.closest ? e.target.closest('.ind-dialog') : null;
      var onInfo = e.target.closest ? (e.target.closest('#ind-info-pill') || e.target.closest('.ind-info-btn')) : null;
      if (inDialog && !onInfo) { hideInfo(); return; }
    }
    var tile = e.target.closest ? e.target.closest('.tile[data-symbol="GOLD"], .tile[data-symbol="WTI"], .tile[data-symbol="US10Y"]') : null;
    if (tile) {
      var cfg = CONFIGS[tile.getAttribute('data-symbol')];
      if (cfg) {
        if (state.cfg && state.cfg.symbol === cfg.symbol && state.weeks.length) { state.cfg = cfg; openModal(cfg); }
        else { state.weeks = []; openModal(cfg); }
      }
      return;
    }
    if (e.target.closest && e.target.closest('#ind-close')) { closeModal(); return; }
    if (e.target.closest && e.target.closest('#ind-retry')) {
      var r = el('ind-retry'); if (r) r.style.display = 'none';
      state.weeks = []; loadData(); return;
    }
    var modal = el('ind-modal');
    if (modal && modal.classList.contains('open') && e.target === modal) closeModal();
    var pill = el('ind-pill');
    if (pill && e.target === pill) pill.style.display = 'none';
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      if (state.infoOpen) { hideInfo(); return; }
      closeModal();
    }
  });
  window.addEventListener('resize', function () {
    var modal = el('ind-modal');
    if (modal && modal.classList.contains('open')) draw();
  });
  document.addEventListener('DOMContentLoaded', function () {
    var canvas = el('ind-canvas');
    if (canvas) canvas.addEventListener('click', onCanvasTap);
    var pill = el('ind-pill');
    if (pill) pill.addEventListener('click', function () { pill.style.display = 'none'; });
    var topBtn = el('ind-info-top');
    if (topBtn) topBtn.addEventListener('click', function () {
      var sub = el('ind-sub');
      toggleInfo(sub ? sub.textContent : '');
    });
    var footBtn = el('ind-info-foot');
    if (footBtn) footBtn.addEventListener('click', function () { if (state.footerText) toggleInfo(state.footerText); });
    var infoPill = el('ind-info-pill');
    if (infoPill) infoPill.addEventListener('click', function () { hideInfo(); });
  });

  // Exposed for the headless verification harness only.
  window.IndicatorChart = { CONFIGS: CONFIGS };
})();
