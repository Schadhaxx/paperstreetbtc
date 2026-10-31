// Shared indicator candle chart — Maple Leaf Screener (test branch
// pepper-indicator-charts-wti, 30 Oct 2026).
// ONE generic module for every Market Indicator candle chart. Do NOT
// copy this file per indicator: add a config entry in CONFIGS below
// and a shipped weekly JSON file, and wire the tile in screener.html.
// Stock cards use the same modal: add an entry to STOCKS (not a copy
// of this file) plus assets/data/stock-weekly-<SYM>.json. Indicator
// configs, colours, month axis and current-line placement are unchanged.
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
    if (typeof v !== 'number' || !isFinite(v)) return '—';
    return (v < 0 ? '-$' : '$') + Math.abs(v).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }
  // Yields are in percent, never dollars: 3 decimals, so displayed
  // values match the shipped JSON exactly (the screener tile rounds
  // to 2 decimals — a display rounding difference, not a data one).
  function fmtYield(v) {
    return v.toFixed(3) + '%';
  }
  // VIX is an index level in points, never a dollar value: 2
  // decimals with a "pts" unit, so a bare number can
  // never be misread as a dollar value.
  function fmtPoints(v) {
    return v.toFixed(2) + ' pts';
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
      subBlurb: 'Weekly candles, data to 30 Oct 2026. Tap a candle for its week.',
      lastInProgress: null
    },
    WTI: {
      symbol: 'WTI',
      title: 'WTI — YTD weekly candles',
      dataUrl: 'assets/data/wti-weekly.json?v=1',
      format: fmtMoney,
      currentPrefix: 'Current ',
      subBlurb: 'Weekly candles, data to 30 Oct 2026. Latest week in progress. Tap a candle for its week.',
      lastInProgress: 'in progress, as of 30 Oct 2026, 3:42 p.m. ET'
    },
    US10Y: {
      symbol: 'US10Y',
      title: '10-Year — YTD weekly candles',
      dataUrl: 'assets/data/us10y-weekly.json?v=1',
      format: fmtYield,
      currentPrefix: 'Current ',
      subBlurb: 'Weekly candles, data to 30 Oct 2026. Tap a candle for its week.',
      lastInProgress: null,
      ppChange: true,
    },
    VIX: {
      symbol: 'VIX',
      title: 'VIX — YTD weekly candles',
      dataUrl: 'assets/data/vix-weekly.json?v=1',
      format: fmtPoints,
      currentPrefix: 'Current ',
      subBlurb: 'Weekly candles, data to 30 Oct 2026. Tap a candle for its week.',
      lastInProgress: null,
      ptsChange: true,
    }
  };

  // Stock cards (not indicator tiles). The dashed line is the shipped
  // weekly close ("Close $…"), never the live card price. "Current $…
  // YTD …" is drawn from the card's own merged row. Cache-bust STOCK_V
  // whenever the JSON is regenerated.
  var STOCK_V = '20261030';
  function stockCfg(sym, basis) {
    var listing = basis === 'listing';
    return {
      symbol: sym,
      stock: true,
      basis: basis,
      title: listing ? (sym + ' — since listing') : (sym + ' — YTD weekly candles'),
      dataUrl: 'assets/data/stock-weekly-' + sym + '.json?v=' + STOCK_V,
      format: fmtMoney,
      currentPrefix: 'Close ',
      subBlurb: 'Weekly candles. Tap a candle for its week.',
      lastInProgress: null
    };
  }
  var STOCKS = {
    TSLA: stockCfg('TSLA', 'ytd'),
    PLTR: stockCfg('PLTR', 'ytd'),
    MSTR: stockCfg('MSTR', 'ytd'),
    IBIT: stockCfg('IBIT', 'ytd'),
    MU: stockCfg('MU', 'ytd'),
    META: stockCfg('META', 'ytd'),
    SPCX: stockCfg('SPCX', 'listing')
  };
  function cardMoney(v) {
    if (typeof v !== 'number' || !isFinite(v)) return '—';
    return (v < 0 ? '-$' : '$') + Math.abs(v).toFixed(2);
  }
  function cardPct(v) {
    if (typeof v !== 'number' || !isFinite(v)) return '—';
    return (v > 0 ? '+' : '') + v.toFixed(2) + '%';
  }

  var state = { cfg: null, weeks: [], loading: false, selected: -1, footerText: '', infoOpen: false, infoText: '', loadedSymbol: '', loadToken: 0, rows: [], base: null, progressNote: null, resolvedSub: '' };

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
    var canvas = el('ind-canvas');
    if (canvas) {
      var ctx = canvas.getContext('2d');
      if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
      delete canvas._plot;
    }
    var cardLine = el('ind-cardline');
    if (cardLine) { cardLine.style.display = 'none'; cardLine.textContent = ''; }
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

  function renderCardLine() {
    var node = el('ind-cardline');
    if (!node) return;
    if (!state.cfg || !state.cfg.stock) { node.style.display = 'none'; node.textContent = ''; return; }
    var row = null;
    (state.rows || []).forEach(function (r) { if (r.symbol === state.cfg.symbol) row = r; });
    if (!row || typeof row.price !== 'number' || !isFinite(row.price)) { node.style.display = 'none'; node.textContent = ''; return; }
    var ytdLabel = row.ytdBasis === 'listing' ? 'Since listing' : 'YTD';
    var ytd = cardPct(row.ytdPct);
    node.textContent = '';
    node.appendChild(document.createTextNode('Current ' + cardMoney(row.price) + '  ' + ytdLabel + ' '));
    var b = document.createElement('b');
    b.className = (typeof row.ytdPct === 'number' && row.ytdPct > 0) ? 'up' : ((typeof row.ytdPct === 'number' && row.ytdPct < 0) ? 'down' : 'flat');
    b.textContent = ytd;
    node.appendChild(b);
    node.style.display = 'block';
  }
  function applyStockMeta(cfg, data) {
    var node = el('ind-cardline');
    if (!cfg.stock) {
      state.base = null; state.progressNote = null; state.resolvedSub = '';
      if (node) { node.style.display = 'none'; node.textContent = ''; }
      return;
    }
    state.base = (typeof data.baseClose === 'number' && isFinite(data.baseClose))
      ? { value: data.baseClose, label: data.baseLabel || 'Baseline' } : null;
    state.progressNote = data.inProgress || null;
    var asOf = data.asOfLabel || data.asOf || '';
    var line = cfg.basis === 'listing'
      ? 'Since listing 12 Jun 2026, not 31 Dec 2025. Data to ' + asOf + '. Tap a candle for its week.'
      : 'Weekly candles, data to ' + asOf + '. Tap a candle for its week.';
    if (state.progressNote) line = line.replace('Tap a candle for its week.', 'Latest week in progress. Tap a candle for its week.');
    state.resolvedSub = line;
    var sub = el('ind-sub');
    if (sub) sub.textContent = line;
    renderCardLine();
  }

  function openModal(cfg) {
    var m = el('ind-modal');
    if (!m) return;
    var switched = !state.cfg || state.cfg.symbol !== cfg.symbol;
    state.cfg = cfg;
    var t = el('ind-title');
    if (t) t.textContent = cfg.title;
    var sub = el('ind-sub');
    if (sub) sub.textContent = (!switched && state.resolvedSub) ? state.resolvedSub : cfg.subBlurb;
    m.setAttribute('aria-label', cfg.stock
      ? (cfg.basis === 'listing' ? cfg.symbol + ' since listing weekly candles' : cfg.symbol + ' YTD weekly candles')
      : 'Indicator YTD weekly candle chart');
    var canvas = el('ind-canvas');
    if (canvas) canvas.setAttribute('aria-label', cfg.stock ? (cfg.symbol + ' weekly candle chart') : 'Indicator weekly candle chart, year to date');
    m.classList.add('open');
    m.setAttribute('aria-hidden', 'false');
    // A different symbol always starts blank: clear the old pill,
    // popup, source "+" and canvas, and invalidate any load still
    // in flight for the old symbol (its response is ignored below).
    // A same-symbol reopen keeps its loaded weeks but still clears
    // the old candle selection/pill so it cannot linger either.
    resetModalVisuals();
    if (switched) {
      state.resolvedSub = '';
      state.base = null;
      state.progressNote = null;
      state.loadToken++;
      state.weeks = [];
      state.loadedSymbol = '';
      loadData();
    } else if (state.weeks.length && state.loadedSymbol === cfg.symbol) {
      draw();
      if (cfg.stock) renderCardLine();
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
        applyStockMeta(cfg, data);
        var last = state.weeks[state.weeks.length - 1];
        setStatus('Tap a candle for its week.');
        state.loading = false;
        draw();
      })
      .catch(function () {
        if (token !== state.loadToken || !state.cfg || state.cfg.symbol !== cfg.symbol) return; // stale failure: ignore
        // A failed load for the NEW symbol must clear the previous
        // chart, not leave it drawn under the new title.
        state.weeks = [];
        state.loadedSymbol = '';
        state.base = null;
        state.progressNote = null;
        state.resolvedSub = '';
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
    if (state.base && typeof state.base.value === 'number' && isFinite(state.base.value)) {
      lo = Math.min(lo, state.base.value); hi = Math.max(hi, state.base.value);
    }
    var span = hi - lo || 1;
    lo -= span * 0.05; hi += span * 0.05;
    var fmt = state.cfg.format;
    if (state.cfg && state.cfg.stock) {
      ctx.font = '11px -apple-system, system-ui, sans-serif';
      var axisW = Math.max(ctx.measureText(fmt(lo)).width, ctx.measureText(fmt(hi)).width);
      padL = Math.max(62, Math.ceil(axisW) + 8);
      plotW = cssW - padL - padR;
    }
    function y(v) { return padT + (hi - v) / (hi - lo) * plotH; }
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
    if (state.cfg.lastInProgress || state.progressNote) curLab += ' (in progress)';
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
    if (state.base && typeof state.base.value === 'number' && isFinite(state.base.value)) {
      var by = y(state.base.value);
      ctx.save();
      ctx.strokeStyle = 'rgba(148,163,184,0.9)';
      ctx.lineWidth = 1;
      ctx.setLineDash([2, 3]);
      ctx.beginPath(); ctx.moveTo(padL, by); ctx.lineTo(cssW - padR, by); ctx.stroke();
      ctx.setLineDash([]);
      var blab = state.base.label + ' ' + fmt(state.base.value);
      ctx.font = '10px -apple-system, system-ui, sans-serif';
      var btw = ctx.measureText(blab).width;
      var bx = Math.max(padL + 4, cssW - padR - btw - 6);
      var bly = by - 8;
      if (bly < 14) bly = by + 14;
      if (Math.abs(bly - ly) < 16 && bx < lx + tw + 10) bly = (bly < ly) ? Math.min(by + 14, cssH - padB - 4) : bly;
      ctx.fillStyle = 'rgba(15,23,42,0.88)';
      ctx.fillRect(bx - 3, bly - 10, Math.min(btw + 6, cssW - padR - bx + 3), 14);
      ctx.fillStyle = '#cbd5e1';
      ctx.fillText(blab, bx, bly);
      ctx.restore();
    }
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
      } else if (state.cfg.ptsChange) {
        // Points move in points: for ptsChange symbols (VIX only) the
        // pill LEADS with the points move, then the relative % in
        // parentheses — Grok Bot's optional item, applied 30 Oct 2026.
        // Dollar-price symbols (gold, WTI) keep the old lead.
        var pts = w.close - w.open;
        html += '<br>Week change ' + (pts >= 0 ? '+' : '') + pts.toFixed(2) + ' pts (' + (chg >= 0 ? '+' : '') + chg.toFixed(2) + '%)';
      } else {
        html += '<br>Week change ' + (chg >= 0 ? '+' : '') + chg.toFixed(2) + '%';
      }
      if (state.cfg.basis === 'listing' && idx === 0 && state.base) {
        var sameOpen = Math.abs(w.open - state.base.value) <= 0.009;
        html += sameOpen
          ? '<br>This open equals the listing close. The baseline is that first-trading close.'
          : '<br>Open is the first trade, not the ' + state.cfg.format(state.base.value) + ' listing close used as the baseline.';
      }
      if (isLast && state.cfg.lastInProgress) html += '<br><i>Latest week ' + state.cfg.lastInProgress + ' — close is not a final daily close.</i>';
      else if (isLast && state.progressNote) html += '<br><i>Latest week is ' + state.progressNote + '.</i>';
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
    var tile = e.target.closest ? e.target.closest('.tile[data-symbol="GOLD"], .tile[data-symbol="WTI"], .tile[data-symbol="US10Y"], .tile[data-symbol="VIX"]') : null;
    if (tile) {
      var cfg = CONFIGS[tile.getAttribute('data-symbol')];
      if (cfg) {
        if (state.cfg && state.cfg.symbol === cfg.symbol && state.weeks.length) { state.cfg = cfg; openModal(cfg); }
        else { state.weeks = []; openModal(cfg); }
      }
      return;
    }
    var stockCard = e.target.closest ? e.target.closest('.card[data-symbol]') : null;
    if (stockCard && STOCKS[stockCard.getAttribute('data-symbol')]) {
      var scfg = STOCKS[stockCard.getAttribute('data-symbol')];
      if (state.cfg && state.cfg.symbol === scfg.symbol && state.weeks.length) openModal(scfg);
      else { state.weeks = []; openModal(scfg); }
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
      return;
    }
    if (e.key !== 'Enter' && e.key !== ' ') return;
    var t = e.target;
    if (!t || !t.getAttribute || t.getAttribute('data-symbol') == null) return;
    if (!t.classList || !t.classList.contains('card')) return;
    var kcfg = STOCKS[t.getAttribute('data-symbol')];
    if (!kcfg) return;
    e.preventDefault();
    if (state.cfg && state.cfg.symbol === kcfg.symbol && state.weeks.length) openModal(kcfg);
    else { state.weeks = []; openModal(kcfg); }
  });
  window.addEventListener('resize', function () {
    var modal = el('ind-modal');
    if (modal && modal.classList.contains('open')) draw();
  });
  window.addEventListener('screener-rows', function (e) {
    state.rows = (e && e.detail) || [];
    var modal = el('ind-modal');
    if (modal && modal.classList.contains('open') && state.cfg && state.cfg.stock) renderCardLine();
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
    var infoPill = el('ind-info-pill');
    if (infoPill) infoPill.addEventListener('click', function () { hideInfo(); });
  });

  // Exposed for the headless verification harness only.
  window.IndicatorChart = { CONFIGS: CONFIGS, STOCKS: STOCKS };
})();
