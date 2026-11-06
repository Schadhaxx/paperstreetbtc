window.psC=window.psC||function(d,l){return document.documentElement.getAttribute('data-theme')==='light'?l:d;};
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
      dataUrl: 'assets/data/gold-weekly.json?v=3',
      format: fmtMoney,
      currentPrefix: 'Current ',
      subBlurb: 'Weekly candles. Tap a candle for its week.',
      lastInProgress: null
    },
    WTI: {
      symbol: 'WTI',
      title: 'WTI — YTD weekly candles',
      dataUrl: 'assets/data/wti-weekly.json?v=2',
      format: fmtMoney,
      currentPrefix: 'Current ',
      subBlurb: 'Weekly candles. Tap a candle for its week.',
      lastInProgress: null
    },
    US10Y: {
      symbol: 'US10Y',
      title: '10-Year — YTD weekly candles',
      dataUrl: 'assets/data/us10y-weekly.json?v=2',
      format: fmtYield,
      currentPrefix: 'Current ',
      subBlurb: 'Weekly candles. Tap a candle for its week.',
      lastInProgress: null,
      ppChange: true,
    },
    VIX: {
      symbol: 'VIX',
      title: 'VIX — YTD weekly candles',
      dataUrl: 'assets/data/vix-weekly.json?v=2',
      format: fmtPoints,
      currentPrefix: 'Current ',
      subBlurb: 'Weekly candles. Tap a candle for its week.',
      lastInProgress: null,
      ptsChange: true,
    }
  };

  // Stock cards (not indicator tiles). The dashed line is the shipped
  // weekly close ("Close $…"), never the live card price. "Current $…
  // YTD …" is drawn from the card's own merged row. Cache-bust STOCK_V
  // whenever the JSON is regenerated.
  var STOCK_V = '20261104';
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

  // Candle enhancements (test branch, 4 Nov 2026): Bollinger (mockup 3),
  // high/low lines (5), drawdown shading (7), pattern hints (9). All
  // OFF by default; the modal's toggle row flips them. Nothing here
  // invents a value: everything is computed from the shipped weekly
  // candles only. High/low lines use SHOWN weeks only — the shipped
  // file is YTD, so they are not a lifetime ATH or a full 52-week
  // history; the note under the chart says so plainly.
  var ENH = { boll: false, lines: false, drawdown: false, patterns: false, volume: false, zoom: false, stats: false };
  function fmtVol(v) {
    if (typeof v !== 'number' || !isFinite(v)) return '—';
    if (v >= 1e6) return (v / 1e6).toFixed(1) + 'M';
    if (v >= 1e3) return Math.round(v / 1e3) + 'K';
    return String(Math.round(v));
  }
  function enhStats(weeks) {
    var chgs = [], best = null, worst = null, wins = 0, i, c, m, sd;
    for (i = 0; i < weeks.length; i++) {
      if (!(weeks[i].open > 0)) continue;
      c = weeks[i].close / weeks[i].open - 1; chgs.push(c);
      if (c >= 0) wins++;
      if (best === null || c > best.c) best = { c: c, label: weeks[i].label };
      if (worst === null || c < worst.c) worst = { c: c, label: weeks[i].label };
    }
    if (!chgs.length) return null;
    m = 0; chgs.forEach(function (x) { m += x; }); m /= chgs.length;
    sd = 0; chgs.forEach(function (x) { sd += (x - m) * (x - m); });
    sd = chgs.length > 1 ? Math.sqrt(sd / (chgs.length - 1)) : 0;
    return { best: best, worst: worst, win: wins / chgs.length * 100, vol: sd * 100, n: chgs.length };
  }
  function enhBoll(weeks) {
    var sma = [], up = [], lo = [], i, j, w, m, sd, sum;
    for (i = 0; i < weeks.length; i++) {
      if (i < 19) { sma.push(null); up.push(null); lo.push(null); continue; }
      sum = 0; for (j = i - 19; j <= i; j++) sum += weeks[j].close;
      m = sum / 20; sd = 0;
      for (j = i - 19; j <= i; j++) sd += (weeks[j].close - m) * (weeks[j].close - m);
      sd = Math.sqrt(sd / 19);
      sma.push(m); up.push(m + 2 * sd); lo.push(m - 2 * sd);
    }
    return { sma: sma, up: up, lo: lo };
  }
  function enhDrawdown(weeks) {
    var peak = -Infinity, peakIdx = 0, best = 0, bestPeak = 0, bestTrough = 0, i, dd;
    for (i = 0; i < weeks.length; i++) {
      if (weeks[i].close > peak) { peak = weeks[i].close; peakIdx = i; }
      dd = peak > 0 ? (peak - weeks[i].close) / peak : 0;
      if (dd > best) { best = dd; bestPeak = peakIdx; bestTrough = i; }
    }
    return { pct: best, peak: bestPeak, trough: bestTrough };
  }
  function enhPattern(weeks, i) {
    if (i <= 0) return null;
    var w = weeks[i], p = weeks[i - 1];
    var body = Math.abs(w.close - w.open), range = w.high - w.low;
    if (!(range > 0)) return null;
    var upSh = w.high - Math.max(w.open, w.close), loSh = Math.min(w.open, w.close) - w.low;
    var prevBodyUp = p.close >= p.open;
    var eps = 1e-9;
    if (!prevBodyUp && w.close >= w.open && w.open <= p.close + eps && w.close >= p.open - eps) return 'Bullish engulfing';
    if (prevBodyUp && w.close < w.open && w.open >= p.close - eps && w.close <= p.open + eps) return 'Bearish engulfing';
    if (loSh >= 2 * body - eps && upSh <= 0.5 * body + eps) return 'Hammer';
    if (body <= 0.10 * range + eps) return 'Doji';
    return null;
  }
  function enhHLine(ctx, yv, padL, cssW, padR, color, dash, label, labelColor) {
    ctx.save(); ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.setLineDash(dash);
    ctx.beginPath(); ctx.moveTo(padL, yv); ctx.lineTo(cssW - padR, yv); ctx.stroke(); ctx.setLineDash([]);
    ctx.font = 'bold 11px -apple-system, system-ui, sans-serif';
    var tw = ctx.measureText(label).width, bx = cssW - padR - tw - 10, by = yv - 8;
    if (by < 14) by = yv + 16;
    ctx.fillStyle = psC('#0b1226','#f1f5f9'); ctx.fillRect(bx - 4, by - 11, tw + 8, 16);
    ctx.fillStyle = labelColor; ctx.fillText(label, bx, by); ctx.restore();
  }

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
      return { monday: new Date(w.monday), sunday: new Date(w.sunday), label: w.label, days: w.days, open: w.open, high: w.high, low: w.low, close: w.close, volume: (typeof w.volume === 'number' ? w.volume : null) };
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
    // Mockup 2 zoom: when on, only the last 12 weeks are drawn.
    // Computations that need history (Bollinger) still use the full
    // series, then are sliced to the shown window; range stats and
    // drawdown are recomputed on the shown window, by design.
    var viewStart = 0, viewWeeks = state.weeks;
    if (ENH.zoom && state.weeks.length > 12) { viewStart = state.weeks.length - 12; viewWeeks = state.weeks.slice(viewStart); }
    var hasVol = ENH.volume && viewWeeks.some(function (w) { return typeof w.volume === 'number' && w.volume > 0; });
    var volH = hasVol ? 56 : 0;
    var enhLabelYs = [];
    var padL = 62, padR = 8, padT = 10, padB = 30;
    var plotW = cssW - padL - padR, plotH = cssH - padT - padB - (volH ? volH + 8 : 0);
    var volTop = padT + plotH + 8;
    var lo = Infinity, hi = -Infinity;
    viewWeeks.forEach(function (w) { lo = Math.min(lo, w.low); hi = Math.max(hi, w.high); });
    if (state.base && typeof state.base.value === 'number' && isFinite(state.base.value)) {
      lo = Math.min(lo, state.base.value); hi = Math.max(hi, state.base.value);
    }
    var fullBands = ENH.boll ? enhBoll(state.weeks) : null;
    var bands = fullBands ? { sma: fullBands.sma.slice(viewStart), up: fullBands.up.slice(viewStart), lo: fullBands.lo.slice(viewStart) } : null;
    if (bands) {
      bands.up.forEach(function (v) { if (v != null) hi = Math.max(hi, v); });
      bands.lo.forEach(function (v) { if (v != null) lo = Math.min(lo, v); });
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
    ctx.fillStyle = psC('#94a3b8','#475569');
    ctx.strokeStyle = psC('rgba(255,255,255,0.08)','rgba(15,23,42,.10)');
    for (var g = 0; g <= 4; g++) {
      var v = lo + (hi - lo) * g / 4;
      var yy = y(v);
      ctx.beginPath(); ctx.moveTo(padL, yy); ctx.lineTo(cssW - padR, yy); ctx.stroke();
      ctx.fillText(fmt(v), 4, yy + 4);
    }
    var n = viewWeeks.length;
    var slot = plotW / n;
    var bw = Math.max(2, Math.min(14, slot * 0.6));
    var ddInfo = ENH.drawdown ? enhDrawdown(viewWeeks) : null;
    if (ddInfo) {
      var runPeak = -Infinity;
      ctx.fillStyle = ENH.boll ? 'rgba(239,68,68,0.07)' : 'rgba(239,68,68,0.10)';
      viewWeeks.forEach(function (w, i) {
        if (w.close > runPeak) runPeak = w.close;
        if (w.close < runPeak) ctx.fillRect(padL + slot * i, y(runPeak), slot, Math.max(0, y(w.close) - y(runPeak)));
      });
    }
    var seenMonths = {};
    viewWeeks.forEach(function (w, i) {
      var cx = padL + slot * i + slot / 2;
      var up = w.close >= w.open;
      var col = up ? '#22c55e' : '#ef4444';
      ctx.strokeStyle = col; ctx.fillStyle = col; ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.moveTo(cx, y(w.high)); ctx.lineTo(cx, y(w.low)); ctx.stroke();
      var top = y(Math.max(w.open, w.close)), bot = y(Math.min(w.open, w.close));
      ctx.fillRect(cx - bw / 2, top, bw, Math.max(1, bot - top));
      if (i === state.selected) {
        ctx.strokeStyle = psC('#ffffff','#0f172a'); ctx.lineWidth = 1.5;
        ctx.strokeRect(cx - bw / 2 - 3, y(w.high) - 3, bw + 6, y(w.low) - y(w.high) + 6);
      }
      var thu = new Date(w.monday.getTime() + 3 * 86400000);
      var mkey = thu.getUTCFullYear() + '-' + thu.getUTCMonth();
      if (!seenMonths[mkey]) {
        seenMonths[mkey] = true;
        ctx.fillStyle = psC('#94a3b8','#475569');
        ctx.font = '10px -apple-system, system-ui, sans-serif';
        var lab = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][thu.getUTCMonth()];
        ctx.fillText(lab, Math.max(padL, Math.min(cx - 9, cssW - padR - 22)), cssH - 10);
        ctx.font = '11px -apple-system, system-ui, sans-serif';
      }
    });
    // Enhancements, drawn over the candles: Bollinger bands (mockup 3)
    // and high/low lines (mockup 5). High/low use shown weeks only.
    if (bands && bands.up[n - 1] != null) {
      ctx.save();
      ctx.fillStyle = ENH.drawdown ? 'rgba(196,181,253,0.07)' : 'rgba(196,181,253,0.10)';
      ctx.beginPath();
      var started = false;
      viewWeeks.forEach(function (w, i) {
        if (bands.up[i] == null) return;
        var x = padL + slot * i + slot / 2;
        if (!started) { ctx.moveTo(x, y(bands.up[i])); started = true; } else ctx.lineTo(x, y(bands.up[i]));
      });
      for (var bi = n - 1; bi >= 0; bi--) { if (bands.lo[bi] == null) continue; ctx.lineTo(padL + slot * bi + slot / 2, y(bands.lo[bi])); }
      ctx.closePath(); ctx.fill();
      function bandLine(arr) {
        ctx.beginPath(); var st = false;
        viewWeeks.forEach(function (w, i) {
          if (arr[i] == null) return;
          var x = padL + slot * i + slot / 2;
          if (!st) { ctx.moveTo(x, y(arr[i])); st = true; } else ctx.lineTo(x, y(arr[i]));
        });
        ctx.stroke();
      }
      ctx.strokeStyle = psC('#c4b5fd','#7c3aed'); ctx.lineWidth = 1.4;
      bandLine(bands.up); bandLine(bands.lo);
      ctx.strokeStyle = psC('#facc15','#ca8a04'); ctx.setLineDash([5, 4]);
      bandLine(bands.sma);
      ctx.restore();
    }
    var shownHi = -Infinity, shownLo = Infinity;
    viewWeeks.forEach(function (w) { shownHi = Math.max(shownHi, w.high); shownLo = Math.min(shownLo, w.low); });
    if (ENH.lines) {
      enhHLine(ctx, y(shownHi), padL, cssW, padR, psC('#f97316','#ea580c'), [6, 4], 'Highest shown ' + fmt(shownHi), psC('#f97316','#ea580c'));
      enhHLine(ctx, y(shownLo), padL, cssW, padR, psC('#94a3b8','#475569'), [6, 4], 'Lowest shown ' + fmt(shownLo), psC('#cbd5e1','#64748b'));
      enhLabelYs = [(y(shownHi) - 8 < 14 ? y(shownHi) + 16 : y(shownHi) - 8), (y(shownLo) - 8 < 14 ? y(shownLo) + 16 : y(shownLo) - 8)];
    }
    // Mockup 1 volume pane (under the price plot, same x slots).
    if (hasVol) {
      var maxVol = 0, volSum = 0, volCnt = 0;
      viewWeeks.forEach(function (w) { if (typeof w.volume === 'number' && w.volume > 0) { maxVol = Math.max(maxVol, w.volume); volSum += w.volume; volCnt++; } });
      var avgVol = volCnt ? volSum / volCnt : 0;
      viewWeeks.forEach(function (w, i) {
        if (!(typeof w.volume === 'number' && w.volume > 0)) return;
        var cx = padL + slot * i + slot / 2;
        var bh = maxVol > 0 ? w.volume / maxVol * volH : 0;
        ctx.save(); ctx.globalAlpha = 0.55; ctx.fillStyle = w.close >= w.open ? psC('#22c55e','#15803d') : psC('#ef4444','#b91c1c');
        ctx.fillRect(cx - bw / 2, volTop + volH - bh, bw, bh); ctx.restore();
      });
      if (avgVol > 0 && maxVol > 0) {
        ctx.save(); ctx.strokeStyle = psC('#94a3b8','#475569'); ctx.setLineDash([4, 3]);
        ctx.beginPath(); ctx.moveTo(padL, volTop + volH - avgVol / maxVol * volH); ctx.lineTo(cssW - padR, volTop + volH - avgVol / maxVol * volH); ctx.stroke(); ctx.restore();
      }
      ctx.fillStyle = psC('#94a3b8','#475569'); ctx.font = '10px -apple-system, system-ui, sans-serif';
      ctx.fillText('Vol', 4, volTop + 10);
    }
    // Current line: horizontal dashed cyan at the latest weekly
    // close, read from the shipped data (never hardcoded), labelled
    // at the LEFT end, by the y-axis. For WTI the latest week is in
    // progress, so the label says so — its close is not a daily close.
    var current = viewWeeks[n - 1].close;
    var cy = y(current);
    ctx.save();
    ctx.strokeStyle = psC('#22d3ee','#0891b2'); ctx.lineWidth = 1.5; ctx.setLineDash([6, 4]);
    ctx.beginPath(); ctx.moveTo(padL, cy); ctx.lineTo(cssW - padR, cy); ctx.stroke();
    ctx.setLineDash([]);
    var curLab = state.cfg.currentPrefix + fmt(current);
    if (state.cfg.lastInProgress || state.progressNote) curLab += ' (in progress)';
    ctx.font = 'bold 11px -apple-system, system-ui, sans-serif';
    var tw = ctx.measureText(curLab).width;
    var lx = padL + 6;
    var ly = cy - 8;
    if (ly < 14) ly = cy + 16;
    ctx.fillStyle = psC('#22d3ee','#0891b2');
    ctx.fillRect(lx - 4, ly - 11, tw + 8, 16);
    ctx.fillStyle = psC('#0b1226','#f1f5f9');
    ctx.fillText(curLab, lx, ly);
    ctx.restore();
    if (state.base && typeof state.base.value === 'number' && isFinite(state.base.value)) {
      var by = y(state.base.value);
      ctx.save();
      ctx.strokeStyle = psC('rgba(148,163,184,0.9)','rgba(15,23,42,.35)');
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
      enhLabelYs.forEach(function (ey) { if (Math.abs(bly - ey) < 16) bly = (bly < ey) ? Math.max(14, bly - 16) : Math.min(by + 14, cssH - padB - 4); });
      if (Math.abs(bly - ly) < 16 && bx < lx + tw + 10) bly = (bly < ly) ? Math.min(by + 14, cssH - padB - 4) : bly;
      ctx.fillStyle = psC('rgba(15,23,42,0.88)','#f1f5f9');
      ctx.fillRect(bx - 3, bly - 10, Math.min(btw + 6, cssW - padR - bx + 3), 14);
      ctx.fillStyle = psC('#cbd5e1','#0f172a');
      ctx.fillText(blab, bx, bly);
      ctx.restore();
    }
    // Pattern hints (mockup 9): a small gold dot on a candle whose
    // shape matches a named pattern. The pill names it and says
    // plainly it is not a prediction.
    var patCount = 0;
    if (ENH.patterns) {
      viewWeeks.forEach(function (w, i) {
        var pat = enhPattern(state.weeks, viewStart + i);
        if (!pat) return;
        patCount++;
        var cx = padL + slot * i + slot / 2;
        var bullish = pat === 'Bullish engulfing' || pat === 'Hammer';
        var dy = bullish ? y(w.low) + 9 : y(w.high) - 9;
        ctx.save(); ctx.fillStyle = psC('#ffffff','#0f172a'); ctx.strokeStyle = psC('#0b1226','#f1f5f9'); ctx.lineWidth = 1;
        ctx.beginPath(); ctx.arc(cx, dy, 3.5, 0, 2 * Math.PI); ctx.fill(); ctx.stroke(); ctx.restore();
      });
    }
    var note = el('ind-enh-note');
    if (note) {
      var lines = [];
      if (ENH.boll) lines.push(bands && bands.up[n - 1] != null ? 'Bollinger (20, 2σ): SMA ' + fmt(bands.sma[n - 1]) + ' · upper ' + fmt(bands.up[n - 1]) + ' · lower ' + fmt(bands.lo[n - 1]) : 'Bollinger needs 20 weeks; this chart has ' + n + '.');
      if (ENH.lines) lines.push('Highest shown ' + fmt(shownHi) + ' · lowest shown ' + fmt(shownLo) + ' — shown weeks only, not a lifetime high/low.');
      if (ENH.drawdown && ddInfo) lines.push('Max drawdown ' + (ddInfo.pct * 100).toFixed(1) + '% · ' + viewWeeks[ddInfo.peak].label + ' → ' + viewWeeks[ddInfo.trough].label + '.');
      if (ENH.patterns) lines.push(patCount ? patCount + ' pattern hint' + (patCount === 1 ? '' : 's') + ' marked (white dots). Tap a candle to see its pattern.' : 'No pattern hints on these weeks.');
      if (ENH.stats) { var st = enhStats(viewWeeks); if (st) lines.push('Range stats (' + st.n + ' weeks): best ' + (st.best.c * 100).toFixed(2) + '% (' + st.best.label + ') · worst ' + (st.worst.c * 100).toFixed(2) + '% (' + st.worst.label + ') · up weeks ' + st.win.toFixed(0) + '% · weekly volatility ' + st.vol.toFixed(2) + '%.'); }
      if (ENH.volume) {
        if (hasVol) {
          var vs = 0, vc = 0; viewWeeks.forEach(function (w) { if (typeof w.volume === 'number' && w.volume > 0) { vs += w.volume; vc++; } });
          lines.push('Volume: latest week ' + fmtVol(viewWeeks[n - 1].volume) + ' · average ' + fmtVol(vc ? vs / vc : 0) + '.');
        } else lines.push('Volume: no volume data in the shipped file for this symbol.');
      }
      if ((ENH.boll || ENH.drawdown) && (state.cfg.lastInProgress || state.progressNote)) lines.push('Bollinger/drawdown include the in-progress latest week.');
      if (lines.length) { note.textContent = lines.join(' '); note.style.display = 'block'; }
      else { note.style.display = 'none'; note.textContent = ''; }
    }
    state.viewWeeks = viewWeeks; state.viewStart = viewStart;
    canvas._plot = { padL: padL, slot: slot, n: n };
  }

  function onCanvasTap(e) {
    var canvas = el('ind-canvas');
    if (!canvas || !canvas._plot) return;
    if (state.infoOpen) { hideInfo(); return; }
    var rect = canvas.getBoundingClientRect();
    var x = (e.clientX - rect.left) - canvas._plot.padL;
    var idx = Math.floor(x / canvas._plot.slot);
    var vw = state.viewWeeks || state.weeks;
    if (idx < 0 || idx >= vw.length) return;
    state.selected = idx;
    var w = vw[idx];
    var chg = (w.close / w.open - 1) * 100;
    var isLast = idx === vw.length - 1;
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
      if (ENH.patterns) { var pat = enhPattern(state.weeks, (state.viewStart || 0) + idx); if (pat) html += '<br>Pattern hint: ' + pat + ' — a shape, not a prediction.'; }
      if (typeof w.volume === 'number' && w.volume > 0) html += '<br>Volume ' + fmtVol(w.volume) + '.';
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
    if (canvas) {
      canvas.addEventListener('click', onCanvasTap);
      // Mockup 2 scrub: drag across the chart and the pill follows
      // candle by candle. A tap still works exactly as before.
      var scrubbing = false;
      canvas.addEventListener('pointerdown', function () { scrubbing = true; });
      canvas.addEventListener('pointerup', function () { scrubbing = false; });
      canvas.addEventListener('pointercancel', function () { scrubbing = false; });
      canvas.addEventListener('pointermove', function (e) { if (scrubbing) onCanvasTap({ clientX: e.clientX }); });
    }
    var pill = el('ind-pill');
    if (pill) pill.addEventListener('click', function () { pill.style.display = 'none'; });
    var topBtn = el('ind-info-top');
    if (topBtn) topBtn.addEventListener('click', function () {
      var sub = el('ind-sub');
      toggleInfo(sub ? sub.textContent : '');
    });
    var infoPill = el('ind-info-pill');
    if (infoPill) infoPill.addEventListener('click', function () { hideInfo(); });
    document.querySelectorAll('#ind-enh button').forEach(function (b) {
      b.addEventListener('click', function () {
        var k = b.getAttribute('data-enh');
        if (!(k in ENH)) return;
        ENH[k] = !ENH[k];
        if (k === 'zoom') state.selected = -1;
        b.setAttribute('aria-pressed', ENH[k] ? 'true' : 'false');
        b.classList.toggle('active', ENH[k]);
        draw();
      });
    });
  });

  // Exposed for the headless verification harness only.
  window.IndicatorChart = { CONFIGS: CONFIGS, STOCKS: STOCKS, enhBoll: enhBoll, enhDrawdown: enhDrawdown, enhPattern: enhPattern, enhStats: enhStats, fmtVol: fmtVol };
})();
