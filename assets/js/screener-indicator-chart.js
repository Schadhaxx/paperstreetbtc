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
// EXPERIMENTAL LIVE FEEL (branch pepper-live-feel-exp, Nov 2026, NOT live):
// when a tile row's _src is 'live' (fresh quote + market hours, as judged
// by screener.js), the modal's dashed line moves to that live price and,
// ONLY when the shipped file marks its last week in progress, that last
// candle's close/high/low follow the live price for display. The shipped
// weeks are never mutated and no price is ever invented: a stale or
// out-of-hours quote keeps the shipped close line and a "Market closed"
// status. See proposals/live-feel-experimental/REVIEW.md.
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
  function fmtFx(v) {
    return v.toFixed(4);
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
  // "dailyUrl" is the daily-closes file for the Bollinger Weekly/Daily
  // switch (Nov 2026): 20 daily closes ending on each week's last
  // session. DAILY_V is bumped when the daily files are regenerated.
  var DAILY_V = '20261107';
  var CONFIGS = {
    GOLD: {
      symbol: 'GOLD',
      title: 'Gold — YTD weekly candles',
      dataUrl: 'assets/data/gold-weekly.json?v=3',
      dailyUrl: 'assets/data/ind-daily-gold.json?v=' + DAILY_V,
      format: fmtMoney,
      currentPrefix: 'Current ',
      subBlurb: 'Weekly candles. Tap a candle for its week.',
      lastInProgress: null
    },
    WTI: {
      symbol: 'WTI',
      title: 'WTI — YTD weekly candles',
      dataUrl: 'assets/data/wti-weekly.json?v=2',
      dailyUrl: 'assets/data/ind-daily-wti.json?v=' + DAILY_V,
      format: fmtMoney,
      currentPrefix: 'Current ',
      subBlurb: 'Weekly candles. Tap a candle for its week.',
      lastInProgress: null
    },
    US10Y: {
      symbol: 'US10Y',
      title: '10-Year — YTD weekly candles',
      dataUrl: 'assets/data/us10y-weekly.json?v=2',
      dailyUrl: 'assets/data/ind-daily-us10y.json?v=' + DAILY_V,
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
      dailyUrl: 'assets/data/ind-daily-vix.json?v=' + DAILY_V,
      format: fmtPoints,
      currentPrefix: 'Current ',
      subBlurb: 'Weekly candles. Tap a candle for its week.',
      lastInProgress: null,
      ptsChange: true,
    },
    // DIA (SPDR Dow Jones Industrial Average ETF, USD) replaced the
    // DJIA index tile (points) on 13 Nov 2026.
    DIA: {
      symbol: 'DIA',
      title: 'DIA — YTD weekly candles',
      dataUrl: 'assets/data/dia-weekly.json?v=1',
      dailyUrl: 'assets/data/ind-daily-dia.json?v=' + DAILY_V,
      format: fmtMoney,
      currentPrefix: 'Current ',
      subBlurb: 'SPDR Dow Jones Industrial Average ETF. Weekly candles. Tap a candle for its week.',
      lastInProgress: null
    },
    QQQ: {
      symbol: 'QQQ',
      title: 'QQQ — YTD weekly candles',
      dataUrl: 'assets/data/qqq-weekly.json?v=1',
      dailyUrl: null,
      format: fmtMoney,
      currentPrefix: 'Current ',
      subBlurb: 'Weekly candles. Tap a candle for its week.',
      lastInProgress: null
    },
    USDCAD: {
      symbol: 'USDCAD',
      title: 'CAD/USD — YTD weekly candles',
      dataUrl: 'assets/data/usdcad-weekly.json?v=cadusd1',
      dailyUrl: null,
      format: fmtFx,
      currentPrefix: 'Current ',
      subBlurb: 'USD per 1 CAD. Weekly candles. Tap a candle for its week.',
      lastInProgress: null
    },
    DXY: {
      symbol: 'DXY',
      title: 'DXY — YTD weekly candles',
      dataUrl: 'assets/data/dxy-weekly.json?v=1',
      dailyUrl: null,
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
  var STOCK_V = '20261109';
  function stockCfg(sym, basis) {
    var listing = basis === 'listing';
    return {
      symbol: sym,
      stock: true,
      basis: basis,
      title: listing ? (sym + ' — since listing') : (sym + ' — YTD weekly candles'),
      dataUrl: 'assets/data/stock-weekly-' + sym + '.json?v=' + STOCK_V,
      dailyUrl: 'assets/data/stock-daily-' + sym + '.json?v=' + DAILY_V,
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
    SPCX: stockCfg('SPCX', 'listing'),
    'BRK.B': stockCfg('BRK.B', 'ytd'),
    AAPL: stockCfg('AAPL', 'ytd'),
    AMZN: stockCfg('AMZN', 'ytd'),
    MSFT: stockCfg('MSFT', 'ytd'),
    NFLX: stockCfg('NFLX', 'ytd'),
    SPOT: stockCfg('SPOT', 'ytd'),
    XYZ: stockCfg('XYZ', 'ytd'),
    GOOGL: stockCfg('GOOGL', 'ytd'),
    NVDA: stockCfg('NVDA', 'ytd')
  };
  function cardMoney(v) {
    if (typeof v !== 'number' || !isFinite(v)) return '—';
    return (v < 0 ? '-$' : '$') + Math.abs(v).toFixed(2);
  }
  function cardPct(v) {
    if (typeof v !== 'number' || !isFinite(v)) return '—';
    return (v > 0 ? '+' : '') + v.toFixed(2) + '%';
  }

  var state = { cfg: null, weeks: [], loading: false, selected: -1, footerText: '', infoOpen: false, infoText: '', loadedSymbol: '', loadToken: 0, rows: [], indRows: [], base: null, progressNote: null, resolvedSub: '', livePrice: null, liveOn: false, livePrev: null, drawStart: 0, pulseTimer: null, dailyDays: null, dailyBoll: null, dailyError: null, dailyLoading: false, loadedDailySymbol: '', deskLive: null, deskLiveToken: 0, deskLiveTimer: null, deskLiveAt: 0 };


  // --- Experimental live feel: pure helpers (also exposed for harness) ---
  // Display copy of the last week with the live price applied, or the
  // week unchanged. Never mutates the shipped week object.
  function applyLiveWeek(w, price) {
    if (!w || typeof price !== 'number' || !isFinite(price)) return w;
    return { monday: w.monday, sunday: w.sunday, label: w.label, days: w.days,
      open: w.open, high: Math.max(w.high, price), low: Math.min(w.low, price), close: price,
      volume: (typeof w.volume === 'number' ? w.volume : null) };
  }
  // Candle date guardrail (9 Nov 2026, Sunil): a live price may only be
  // painted onto a candle whose Monday-Sunday range contains TODAY, so a
  // stale file (last week 2-8 Nov, today 9 Nov) can never bend last
  // week's candle or mark it live / in progress.
  // TIMEZONE: "today" is the calendar date in America/New_York (ET,
  // DST-correct via nyOffsetHours) - market weeks and the live quote are
  // ET. The file's monday/sunday are plain YYYY-MM-DD dates (UTC-midnight
  // Dates once loaded), compared as dates.
  // Fails closed: unknown today or candle dates -> false (no live price).
  function isoDay(v) {
    if (v instanceof Date) { var tv = v.getTime(); return isFinite(tv) ? v.toISOString().slice(0, 10) : null; }
    if (typeof v === 'string' && /^\d{4}-\d{2}-\d{2}/.test(v)) return v.slice(0, 10);
    return null;
  }
  function etTodayISO(nowMs) {
    var t = (nowMs === undefined) ? Date.now() : nowMs;
    if (typeof t !== 'number' || !isFinite(t)) return null;
    return new Date(t + nyOffsetHours(t) * 3600000).toISOString().slice(0, 10);
  }
  function weekCoversToday(w, nowMs) {
    if (!w) return false;
    var m = isoDay(w.monday), s = isoDay(w.sunday), t = etTodayISO(nowMs);
    if (!m || !s || !t || m > s) return false;
    return t >= m && t <= s;
  }
  // The only way the live price reaches a candle: guarded copy, or the
  // week unchanged.
  function liveWeekFor(w, price, nowMs) {
    return weekCoversToday(w, nowMs) ? applyLiveWeek(w, price) : w;
  }
  function displayWeeks() {
    if (!state.weeks.length) return [];
    if (!state.liveOn || !state.progressNote && !(state.cfg && state.cfg.lastInProgress)) return state.weeks;
    if (!state.liveOn) return state.weeks;
    var out = state.weeks.slice();
    out[out.length - 1] = liveWeekFor(out[out.length - 1], state.livePrice);
    return out;
  }
  function isInProgress() {
    return !!(state.progressNote || (state.cfg && state.cfg.lastInProgress));
  }
  // --- desk-live.json overlay (5-min current-week candle, stage 2) ---
  // The 5-min Desk job publishes desk-live.json to the data branch
  // (next to prices.json) with the current week's candle per symbol,
  // refreshed every 5 min in market hours. The modal overlays that
  // candle on the last week from the Pages weekly file — but ONLY when
  // the entry is fresh (asOf < ~20 min old) AND its monday is the week
  // being drawn. Otherwise it is ignored and the modal silently falls
  // back to the Pages candle (which the final run keeps current).
  // A missing/unreadable desk-live.json is also a silent fallback,
  // never an error: the Pages file is the source of truth and the
  // overlay is a freshness bonus. The existing applyLiveWeek still
  // patches the close from prices.json on top (see draw()).
  var DESK_LIVE_URL = 'https://raw.githubusercontent.com/Schadhaxx/paperstreetbtc/data/desk-live.json';
  var DESK_LIVE_MAX_AGE_MS = 20 * 60 * 1000; // ~20 min
  var DESK_LIVE_POLL_MS = 5 * 60 * 1000; // re-poll every 5 min while open
  function deskLiveFileFor(cfg) {
    // Basename of the weekly file, e.g. "dia-weekly.json" or
    // "stock-weekly-TSLA.json". Matching by file (not by symbol key)
    // is what maps the overlay key CADUSD to the page's USDCAD, whose
    // file is usdcad-weekly.json.
    if (!cfg || typeof cfg.dataUrl !== 'string') return null;
    var u = cfg.dataUrl.split('?')[0];
    var i = u.lastIndexOf('/');
    return i >= 0 ? u.slice(i + 1) : u;
  }
  function deskLiveEntryFor(data, cfg) {
    if (!data || typeof data !== 'object' || !data.symbols || typeof data.symbols !== 'object') return null;
    var file = deskLiveFileFor(cfg);
    var syms = data.symbols, entry = null, k;
    if (file) {
      for (k in syms) {
        if (syms[k] && syms[k].file === file) { entry = syms[k]; break; }
      }
    }
    if (!entry && cfg && typeof cfg.symbol === 'string') {
      // Fallback: direct symbol key, with the CADUSD -> USDCAD map.
      var key = cfg.symbol === 'USDCAD' ? 'CADUSD' : cfg.symbol;
      if (syms[key]) entry = syms[key];
    }
    if (!entry || entry.status !== 'ok') return null;
    if (typeof entry.open !== 'number' || !isFinite(entry.open) ||
        typeof entry.high !== 'number' || !isFinite(entry.high) ||
        typeof entry.low !== 'number' || !isFinite(entry.low) ||
        typeof entry.close !== 'number' || !isFinite(entry.close)) return null;
    if (typeof entry.monday !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(entry.monday)) return null;
    if (entry.high < Math.max(entry.open, entry.close) || entry.low > Math.min(entry.open, entry.close)) return null;
    return entry;
  }
  function deskLiveFresh(asOfMs, nowMs) {
    if (typeof asOfMs !== 'number' || !isFinite(asOfMs)) return false;
    var t = (nowMs === undefined) ? Date.now() : nowMs;
    if (typeof t !== 'number' || !isFinite(t)) return false;
    // Allow up to 60s of clock skew the other way; the entry must not
    // be from the future beyond that, nor older than ~20 min.
    return asOfMs <= t + 60000 && (t - asOfMs) < DESK_LIVE_MAX_AGE_MS;
  }
  // The overlaid week: the desk-live candle, or the shipped week
  // unchanged. Never mutates the input week. The shipped label/days
  // are kept; the desk-live OHLC (and volume when present) win.
  function deskLiveWeekFor(w, nowMs) {
    var ov = state.deskLive;
    if (!ov || !w) return w;
    if (!deskLiveFresh(ov.asOfMs, nowMs)) return w;
    if (isoDay(ov.monday) !== isoDay(w.monday)) return w;
    return { monday: w.monday, sunday: w.sunday, label: w.label, days: (typeof ov.days === 'number' ? ov.days : w.days),
      open: ov.open, high: ov.high, low: ov.low, close: ov.close,
      volume: (typeof ov.volume === 'number' ? ov.volume : (typeof w.volume === 'number' ? w.volume : null)) };
  }
  function fetchDeskLive() {
    if (!state.cfg) return;
    var token = ++state.deskLiveToken;
    var cfg = state.cfg;
    fetch(DESK_LIVE_URL + '?t=' + Date.now(), { cache: 'no-store' })
      .then(function (res) { if (!res.ok) throw new Error('no desk-live file'); return res.json(); })
      .then(function (data) {
        if (token !== state.deskLiveToken || !state.cfg || state.cfg.symbol !== cfg.symbol) return; // stale response: ignore
        var asOfMs = (typeof data.asOf === 'string') ? Date.parse(data.asOf) : NaN;
        var entry = deskLiveEntryFor(data, cfg);
        if (!entry || !deskLiveFresh(asOfMs)) { state.deskLive = null; }
        else {
          state.deskLive = { monday: entry.monday, open: entry.open, high: entry.high, low: entry.low, close: entry.close,
            volume: (typeof entry.volume === 'number' ? entry.volume : null),
            days: (typeof entry.days === 'number' ? entry.days : null), asOfMs: asOfMs };
        }
        state.deskLiveAt = Date.now();
        var m = el('ind-modal');
        if (m && m.classList.contains('open') && state.weeks.length && state.loadedSymbol === cfg.symbol) draw();
      })
      .catch(function () {
        if (token !== state.deskLiveToken || !state.cfg || state.cfg.symbol !== cfg.symbol) return; // stale failure: ignore
        // Silent fallback: no desk-live file (or a bad one) just means
        // the Pages weekly candle stands. No error is shown.
        state.deskLive = null;
        state.deskLiveAt = Date.now();
      });
  }
  // Throttled re-fetch: only when > ~4 min since the last fetch, so a
  // burst of visibilitychange events cannot hammer the file.
  function deskLiveMaybeRefresh() {
    if (!state.cfg) return;
    var now = Date.now();
    if (state.deskLiveAt && now - state.deskLiveAt < 4 * 60 * 1000) return;
    fetchDeskLive();
  }
  function startDeskLiveTimer() {
    stopDeskLiveTimer();
    state.deskLiveTimer = setInterval(function () {
      var m = el('ind-modal');
      if (!m || !m.classList.contains('open')) { stopDeskLiveTimer(); return; }
      fetchDeskLive();
    }, DESK_LIVE_POLL_MS);
  }
  function stopDeskLiveTimer() { if (state.deskLiveTimer) { clearInterval(state.deskLiveTimer); state.deskLiveTimer = null; } }
  // US daylight saving time (post-2007 rules): second Sunday of March
  // 07:00 UTC to first Sunday of November 06:00 UTC. Returns the
  // America/New_York UTC offset in hours (-4 EDT, -5 EST) for a UTC instant.
  function nyOffsetHours(utcMs) {
    var d = new Date(utcMs), y = d.getUTCFullYear();
    var mar1Dow = new Date(Date.UTC(y, 2, 1)).getUTCDay();
    var secondSunMar = 1 + ((7 - mar1Dow) % 7) + 7;
    var dstStart = Date.UTC(y, 2, secondSunMar, 7, 0, 0);
    var nov1Dow = new Date(Date.UTC(y, 10, 1)).getUTCDay();
    var firstSunNov = 1 + ((7 - nov1Dow) % 7);
    var dstEnd = Date.UTC(y, 10, firstSunNov, 6, 0, 0);
    return (utcMs >= dstStart && utcMs < dstEnd) ? -4 : -5;
  }
  // Week close, anchored to the DISPLAYED week (the last week in
  // state.weeks), not to "next Friday". Stocks: that week's Friday at
  // 4 p.m. New York time (DST-correct via nyOffsetHours — the old code
  // hardcoded 21:00 UTC, which is an hour late during daylight saving
  // time). Indicators: that week's Sunday midnight UTC. Once the target
  // has passed the week is closed — the countdown never rolls forward
  // to next week. Holidays and early closes are NOT adjusted: there is
  // no holiday calendar in this file, so the target is the REGULAR
  // scheduled Friday close, not a guaranteed exchange close on a
  // holiday week — and the UI says so (see countdownText), not just
  // this comment, per Grok Bot's final correction 6 Nov 2026.
  function nextWeekClose(isStock) {
    var last = state.weeks && state.weeks.length ? state.weeks[state.weeks.length - 1] : null;
    var now = Date.now(), target;
    if (isStock) {
      var monday = last && last.monday ? new Date(last.monday) : null;
      if (!monday || isNaN(monday)) {
        // No displayed week yet (harness / before load): fall back to the
        // current week's Monday from now, DST-correct below.
        var nd = new Date(now), dow = nd.getUTCDay();
        monday = new Date(Date.UTC(nd.getUTCFullYear(), nd.getUTCMonth(), nd.getUTCDate() - (dow === 0 ? 6 : dow - 1)));
      }
      var friday = new Date(monday.getTime() + 4 * 86400000);
      // NY offset for that Friday (noon UTC is safely past the 2 a.m. DST switch).
      var refMs = Date.UTC(friday.getUTCFullYear(), friday.getUTCMonth(), friday.getUTCDate(), 12, 0, 0);
      var off = nyOffsetHours(refMs);
      target = new Date(Date.UTC(friday.getUTCFullYear(), friday.getUTCMonth(), friday.getUTCDate(), 16 - off, 0, 0));
      return { t: target, label: 'regular scheduled Friday 4 p.m. ET', closed: now >= target.getTime() };
    }
    var sunday = last && last.sunday ? new Date(last.sunday) : null;
    if (!sunday || isNaN(sunday)) {
      var nd2 = new Date(now), dow2 = nd2.getUTCDay();
      sunday = new Date(Date.UTC(nd2.getUTCFullYear(), nd2.getUTCMonth(), nd2.getUTCDate() + ((7 - dow2) % 7)));
    }
    target = new Date(Date.UTC(sunday.getUTCFullYear(), sunday.getUTCMonth(), sunday.getUTCDate() + 1, 0, 0, 0));
    return { t: target, label: 'Sunday midnight UTC', closed: now >= target.getTime() };
  }
  function countdownText() {
    var isStock = !!(state.cfg && state.cfg.stock);
    var nc = nextWeekClose(isStock);
    if (nc.closed) {
      // The week has closed. If the data file still says the week is in
      // progress (state.progressNote set — the pipeline only clears
      // inProgress once the final close arrives), the final bar hasn't
      // landed yet: say the final weekly data is pending, instead of
      // implying the week isn't finished (the in-progress note) or that
      // everything is final (a bare "Week closed"). Grok Bot's final
      // correction, 6 Nov 2026 (optional copy improvement).
      if (state.progressNote) return 'Week closed — final weekly data pending';
      return 'Week closed';
    }
    var ms = Math.max(0, nc.t - Date.now());
    var dd = Math.floor(ms / 86400000), hh = Math.floor(ms / 3600000) % 24, mm = Math.floor(ms / 60000) % 60;
    // Stocks: the target is the REGULAR scheduled close. There is no
    // holiday calendar here, so the limitation is stated in the visible
    // text (not just in a comment): on a holiday/early-close week the
    // actual close differs. Indicators close on a Sunday-midnight UTC
    // data cutoff, not an exchange close, so no caveat applies there.
    var caveat = isStock ? '; holidays/early closes not covered' : '';
    return 'Week closes in ' + dd + 'd ' + hh + 'h ' + mm + 'm (' + nc.label + caveat + ')';
  }
  function refreshLiveStatus() {
    var modal = el('ind-modal');
    if (!modal || !modal.classList.contains('open') || !state.weeks.length || state.loading) return;
    var liveEl = el('ind-liveprice');
    if (state.liveOn) {
      var f = state.cfg.format(state.livePrice);
      if (liveEl) {
        liveEl.textContent = 'Live ' + f;
        liveEl.style.display = 'inline-block';
        if (state.livePrev !== null && state.livePrice !== state.livePrev) {
          liveEl.style.color = state.livePrice >= state.livePrev ? '#22c55e' : '#ef4444';
          setTimeout(function () { if (liveEl) liveEl.style.color = ''; }, 700);
        }
      }
      setStatus('LIVE · ' + countdownText() + ' · Tap a candle for its week.');
    } else {
      if (liveEl) liveEl.style.display = 'none';
      var last = state.weeks[state.weeks.length - 1];
      setStatus('Market closed · Last close ' + state.cfg.format(last.close) + ' · ' + countdownText() + ' · Tap a candle for its week.');
    }
  }
  function refreshLive() {
    if (!state.cfg) return;
    var list = state.cfg.stock ? state.rows : state.indRows, row = null;
    (list || []).forEach(function (r) { if (r.symbol === state.cfg.symbol) row = r; });
    var wasOn = state.liveOn, wasPrice = state.livePrice;
    state.liveOn = !!(row && row._src === 'live' && typeof row.price === 'number' && isFinite(row.price));
    state.livePrice = state.liveOn ? row.price : null;
    if (state.liveOn) state.livePrev = wasPrice;
    var modal = el('ind-modal');
    var open = !!(modal && modal.classList.contains('open'));
    if (open && state.weeks.length) {
      if (state.liveOn && !wasOn) state.drawStart = performance.now();
      draw();
      refreshLiveStatus();
    }
    // Pulse: redraw on a slow tick only while the modal is open, live,
    // and the user has not asked for reduced motion. Stopped on close.
    // The status line (with its week-close countdown) refreshes on the
    // same tick, throttled to every 30s, so the countdown counts down
    // between 5-minute feed refreshes instead of freezing.
    var reduced = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (open && state.liveOn && !reduced && !state.pulseTimer) {
      state.pulseTimer = setInterval(function () {
        var m = el('ind-modal');
        if (!m || !m.classList.contains('open') || !state.liveOn) { stopPulse(); return; }
        draw();
        var now = Date.now();
        if (!state.lastStatusAt || now - state.lastStatusAt >= 30000) {
          state.lastStatusAt = now;
          refreshLiveStatus();
        }
      }, 700);
    } else if ((!open || !state.liveOn) && state.pulseTimer) stopPulse();
  }
  function stopPulse() { if (state.pulseTimer) { clearInterval(state.pulseTimer); state.pulseTimer = null; } }

  // Candle enhancements (test branch, 4 Nov 2026): Bollinger (mockup 3),
  // high/low lines (5), drawdown shading (7), pattern hints (9). All
  // OFF by default; the modal's toggle row flips them. Nothing here
  // invents a value: everything is computed from the shipped weekly
  // candles only. High/low lines use SHOWN weeks only — the shipped
  // file is YTD, so they are not a lifetime ATH or a full 52-week
  // history; the note under the chart says so plainly.
  var ENH = { boll: false, lines: false, drawdown: false, patterns: false, volume: false, zoom: false };
  function fmtVol(v) {
    if (typeof v !== 'number' || !isFinite(v)) return '—';
    if (v >= 1e6) return (v / 1e6).toFixed(1) + 'M';
    if (v >= 1e3) return Math.round(v / 1e3) + 'K';
    return String(Math.round(v));
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
  // Bollinger Weekly/Daily switch (Nov 2026): the DAILY bands use the
  // same 20-close, +/-2 sigma recipe, but from DAILY closes instead of
  // weekly closes. For each week, the 20 daily closes ending on that
  // week's last session (the last daily close on or before the week's
  // Sunday). The in-progress latest week uses the daily closes as of
  // the latest completed session. Returns {sma, up, lo} aligned to
  // weeks, null where fewer than 20 daily closes are available up to
  // that week. One set at a time — this REPLACES the weekly bands when
  // the Daily mode is selected, it never draws alongside them.
  // dailyDays: [{date: 'YYYY-MM-DD', close: number}] ascending.
  // weeks: state.weeks (sunday is a Date) or raw weeks (sunday a string).
  function enhBollDaily(weeks, dailyDays) {
    var sma = [], up = [], lo = [], i, j, m, sd, sum, idx;
    function sunStr(w) {
      var s = w.sunday;
      if (s instanceof Date) return s.toISOString().slice(0, 10);
      return String(s).slice(0, 10);
    }
    function lastIdx(sunday) {
      var loI = 0, hiI = dailyDays.length - 1, ans = -1, mid;
      while (loI <= hiI) {
        mid = (loI + hiI) >> 1;
        if (dailyDays[mid].date <= sunday) { ans = mid; loI = mid + 1; }
        else hiI = mid - 1;
      }
      return ans;
    }
    for (i = 0; i < weeks.length; i++) {
      idx = lastIdx(sunStr(weeks[i]));
      if (idx < 19) { sma.push(null); up.push(null); lo.push(null); continue; }
      sum = 0; for (j = idx - 19; j <= idx; j++) sum += dailyDays[j].close;
      m = sum / 20; sd = 0;
      for (j = idx - 19; j <= idx; j++) sd += (dailyDays[j].close - m) * (dailyDays[j].close - m);
      sd = Math.sqrt(sd / 19);
      sma.push(m); up.push(m + 2 * sd); lo.push(m - 2 * sd);
    }
    return { sma: sma, up: up, lo: lo };
  }
  // Bollinger mode: 'weekly' (20 weekly closes, the original) or
  // 'daily' (20 daily closes ending on each week's last session).
  // Default weekly — the switch only appears while Bollinger is on,
  // and a symbol change resets it to weekly.
  var bollMode = 'weekly';
  function syncBollModeUI() {
    var sw = el('ind-boll-mode');
    if (sw) sw.style.display = ENH.boll ? 'inline-flex' : 'none';
    document.querySelectorAll('[data-bollmode]').forEach(function (b) {
      var on = b.getAttribute('data-bollmode') === bollMode;
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
      b.classList.toggle('active', on);
    });
  }
  function loadDailyBoll() {
    var cfg = state.cfg;
    if (!cfg || !cfg.dailyUrl || !state.weeks.length) return;
    if (state.dailyLoading) return;
    if (state.dailyDays && state.loadedDailySymbol === cfg.symbol) {
      state.dailyBoll = enhBollDaily(state.weeks, state.dailyDays);
      state.dailyError = null;
      draw();
      return;
    }
    state.dailyLoading = true;
    state.dailyError = null;
    // cache:'no-store' — the daily file is regenerated on final closes
    // (like vehicle-daily.json, book.js B.loadVehicle), so a cached copy
    // would draw yesterday's bands. The ?v= pin only changes on a shape
    // change, not on each regeneration.
    fetch(cfg.dailyUrl, { cache: 'no-store' })
      .then(function (res) { if (!res.ok) throw new Error('no daily file'); return res.json(); })
      .then(function (data) {
        state.dailyLoading = false;
        if (!state.cfg || state.cfg.symbol !== cfg.symbol) return; // stale response: ignore
        var days = (data && data.days) || [];
        if (!days.length) throw new Error('empty daily file');
        // Freshness: the daily file's last close should be within 10 days
        // of the weekly file's last session. A much older file would draw
        // stale bands — fall back to weekly instead.
        var lastDaily = days[days.length - 1].date;
        var lastWeek = state.weeks[state.weeks.length - 1];
        var lastSun = lastWeek ? (lastWeek.sunday instanceof Date ? lastWeek.sunday.toISOString().slice(0, 10) : String(lastWeek.sunday).slice(0, 10)) : null;
        if (lastSun) {
          var gap = (new Date(lastSun + 'T00:00:00Z') - new Date(lastDaily + 'T00:00:00Z')) / 86400000;
          if (!(gap >= 0 && gap <= 10)) throw new Error('stale daily file');
        }
        state.dailyDays = days;
        state.loadedDailySymbol = cfg.symbol;
        state.dailyBoll = enhBollDaily(state.weeks, days);
        state.dailyError = null;
        draw();
      })
      .catch(function () {
        state.dailyLoading = false;
        if (!state.cfg || state.cfg.symbol !== cfg.symbol) return; // stale failure: ignore
        state.dailyDays = null; state.dailyBoll = null;
        state.dailyError = 'Daily data could not be loaded — showing weekly bands.';
        bollMode = 'weekly';
        syncBollModeUI();
        draw();
      });
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
    var liveEl = el('ind-liveprice');
    if (liveEl) liveEl.style.display = 'none';
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
    if (state.progressNote && Array.isArray(data.weeks) && weekCoversToday(data.weeks[data.weeks.length - 1])) line = line.replace('Tap a candle for its week.', 'Latest week in progress. Tap a candle for its week.');
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
    // 5-min desk-live overlay: fetch the current-week candle in
    // parallel with the weekly file, and re-poll every 5 min while
    // the modal is open. A missing/stale file is a silent fallback.
    fetchDeskLive();
    startDeskLiveTimer();
    if (switched) {
      state.resolvedSub = '';
      state.base = null;
      state.progressNote = null;
      state.loadToken++;
      state.weeks = [];
      state.loadedSymbol = '';
      // A new symbol starts on weekly Bollinger with no daily data:
      // the daily file is per-symbol and is fetched on demand.
      bollMode = 'weekly';
      state.dailyDays = null; state.dailyBoll = null; state.dailyError = null;
      state.dailyLoading = false; state.loadedDailySymbol = '';
      syncBollModeUI();
      loadData();
    } else if (state.weeks.length && state.loadedSymbol === cfg.symbol) {
      state.drawStart = performance.now();
      draw();
      refreshLiveStatus();
      if (cfg.stock) renderCardLine();
    } else {
      state.weeks = [];
      loadData();
    }
  }
  function closeModal() {
    var m = el('ind-modal');
    if (!m) return;
    stopPulse();
    stopDeskLiveTimer();
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
    // cache:'no-store' — the weekly file is regenerated by the Desk
    // intraday refresh every 15 min during market hours (like the daily
    // file above), so a cached copy would draw a stale candle. The ?v=
    // pin only changes on a shape change, not on each regeneration.
    fetch(cfg.dataUrl, { cache: 'no-store' })
      .then(function (res) { if (!res.ok) throw new Error('no static file'); return res.json(); })
      .then(function (data) {
        if (token !== state.loadToken || !state.cfg || state.cfg.symbol !== cfg.symbol) return; // stale response: ignore
        state.weeks = weeksFromStatic(data);
        state.loadedSymbol = cfg.symbol;
        // In-progress marking is not stock-only: indicator files carry
        // inProgress too when their last week is partial (see the
        // current-week-candle branch). applyStockMeta only sets it for
        // stocks, so capture it here for every symbol.
        if (typeof data.inProgress === 'string' && data.inProgress) state.progressNote = data.inProgress;
        applyStockMeta(cfg, data);
        state.drawStart = performance.now();
        // Loading is done: clear the flag BEFORE refreshLive() so
        // refreshLiveStatus() actually runs (it returns early while
        // loading) and the status line shows the LIVE / Market-closed
        // state with its week-close countdown on first open — instead
        // of the old code, which set the status here and then clobbered
        // it with a plain "Tap a candle" line below.
        state.loading = false;
        refreshLive();
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
    /* Short landscape (iPhone landscape, viewport <500px tall, 8 Nov 2026,
       round 3): the dialog is bottom-anchored and only ~227px of the
       280px canvas was visible. A 240px canvas fits fully inside the
       taller dialog (max-height raised to 100vh-24px in screener.html),
       so the whole chart — including the date axis — is visible without
       scrolling. The dialog is already full width (812px), so the chart
       stays wide. */
    var shortLand = window.innerWidth > window.innerHeight && window.innerHeight < 500;
    var cssH = shortLand ? 240 : ((window.innerWidth > window.innerHeight && window.innerHeight >= 600) ? 360 : 280);
    canvas.width = Math.round(cssW * dpr);
    canvas.height = Math.round(cssH * dpr);
    canvas.style.height = cssH + 'px';
    var ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, cssW, cssH);
    // Mockup 2 zoom: when on, only the last 12 weeks are drawn.
    // Computations that need history (Bollinger) still use the full
    // series, then are sliced to the shown window; drawdown is
    // recomputed on the shown window, by design.
    var viewStart = 0, viewWeeks = state.weeks;
    if (ENH.zoom && state.weeks.length > 12) { viewStart = state.weeks.length - 12; viewWeeks = state.weeks.slice(viewStart); }
    var hasVol = ENH.volume && viewWeeks.some(function (w) { return typeof w.volume === 'number' && w.volume > 0; });
    var volH = hasVol ? 56 : 0;
    var enhLabelYs = [];
    // Right margin 24, not 8: the in-progress last candle sits at the
    // far right of the plot, and its live dashed outline extends 5px
    // past the body on each side. With an 8px margin the outline ran
    // to the canvas edge and read as clipped; 24px leaves it (and the
    // LIVE tag) visibly clear of the edge.
    var padL = 62, padR = 24, padT = 10, padB = 30;
    var plotW = cssW - padL - padR, plotH = cssH - padT - padB - (volH ? volH + 8 : 0);
    var volTop = padT + plotH + 8;
    // Display copy: the shown weeks with the in-progress last week
    // extended to the live price (display only — the shipped week is
    // never mutated). When not live, dw is exactly viewWeeks.
    var dw = viewWeeks.slice();
    // 5-min desk-live overlay first (fresh + monday-matching only),
    // then the live-price close patch on top, as before.
    if (dw.length) dw[dw.length - 1] = deskLiveWeekFor(dw[dw.length - 1]);
    if (state.liveOn && isInProgress() && typeof state.livePrice === 'number' && isFinite(state.livePrice) && dw.length) {
      dw[dw.length - 1] = liveWeekFor(dw[dw.length - 1], state.livePrice);
    }
    var lo = Infinity, hi = -Infinity;
    dw.forEach(function (w) { lo = Math.min(lo, w.low); hi = Math.max(hi, w.high); });
    if (state.base && typeof state.base.value === 'number' && isFinite(state.base.value)) {
      lo = Math.min(lo, state.base.value); hi = Math.max(hi, state.base.value);
    }
    var fullBands = null;
    if (ENH.boll) {
      if (bollMode === 'daily' && state.dailyBoll) fullBands = state.dailyBoll;
      else fullBands = enhBoll(state.weeks);
    }
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
    var n = dw.length;
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
    // Draw-in: candles grow body-first over ~450ms from drawStart
    // (open, fresh load, or the moment the chart goes live). Reduced
    // motion draws instantly. The live candle never grows: it is
    // already moving with the price.
    var reducedM = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
    var prog = reducedM || !state.drawStart ? 1 : Math.min(1, (performance.now() - state.drawStart) / 450);
    dw.forEach(function (w, i) {
      var cx = padL + slot * i + slot / 2;
      var up = w.close >= w.open;
      var col = up ? '#22c55e' : '#ef4444';
      ctx.strokeStyle = col; ctx.fillStyle = col; ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.moveTo(cx, y(w.high)); ctx.lineTo(cx, y(w.low)); ctx.stroke();
      var top = y(Math.max(w.open, w.close)), bot = y(Math.min(w.open, w.close));
      var isLiveCandle = state.liveOn && isInProgress() && i === n - 1 && weekCoversToday(w);
      var grow = (reducedM || isLiveCandle) ? 1 : Math.max(0, Math.min(1, prog * n - i));
      var mid = (top + bot) / 2, half = (bot - top) / 2 * grow;
      ctx.fillRect(cx - bw / 2, mid - half, bw, Math.max(1, half * 2));
      if (isLiveCandle) {
        // Dashed outline + LIVE tag on the live candle only. The
        // pulsing dot sits to the LEFT of the LIVE text (dot, gap,
        // text — centred on the candle), not on top of it: the old
        // code drew the dot at the candle centre, where it covered
        // the V in LIVE.
        ctx.save();
        ctx.strokeStyle = '#22d3ee'; ctx.lineWidth = 1.5; ctx.setLineDash([4, 4]);
        ctx.strokeRect(cx - bw / 2 - 5, y(w.high) - 8, bw + 10, y(w.low) - y(w.high) + 16);
        ctx.setLineDash([]);
        var pulse = reducedM ? 0 : (0.5 + 0.5 * Math.sin(Date.now() / 300));
        ctx.globalAlpha = 0.35 + 0.65 * pulse;
        ctx.fillStyle = '#22c55e';
        ctx.beginPath(); ctx.arc(cx - 17, y(w.high) - 24, 5, 0, 2 * Math.PI); ctx.fill();
        ctx.globalAlpha = 1;
        ctx.font = 'bold 11px -apple-system, system-ui, sans-serif';
        ctx.fillStyle = '#22c55e';
        ctx.fillText('LIVE', cx - 8, y(w.high) - 20);
        ctx.restore();
      }
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
    // Current line: horizontal dashed cyan. EXPERIMENTAL LIVE FEEL: when
    // the tile row is live, this line moves to the live price; otherwise
    // it is exactly the old shipped-close line. The filled price labels
    // that used to sit on it (left "Live $x"/"Current $x" box, right green
    // "LIVE $x" box) were removed 9 Nov 2026 (Sunil: they covered the
    // chart and repeat the header "Live $x" / card "Current $x").
    var current = state.liveOn ? state.livePrice : dw[n - 1].close;
    var cy = y(current);
    ctx.save();
    ctx.strokeStyle = psC('#22d3ee','#0891b2'); ctx.lineWidth = 1.5; ctx.setLineDash([6, 4]);
    ctx.beginPath(); ctx.moveTo(padL, cy); ctx.lineTo(cssW - padR, cy); ctx.stroke();
    ctx.setLineDash([]);
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
      if (ENH.boll) {
        var modeLab = bollMode === 'daily' ? 'daily, 20 closes' : 'weekly, 20 weeks';
        var needLab = bollMode === 'daily'
          ? 'Bollinger (daily) needs 20 daily closes before this week.'
          : 'Bollinger needs 20 weeks; this chart has ' + n + '.';
        lines.push(bands && bands.up[n - 1] != null ? 'Bollinger (' + modeLab + ', 2σ): SMA ' + fmt(bands.sma[n - 1]) + ' · upper ' + fmt(bands.up[n - 1]) + ' · lower ' + fmt(bands.lo[n - 1]) : needLab);
      }
      if (ENH.boll && state.dailyError) lines.push(state.dailyError);
      if (ENH.lines) lines.push('Highest shown ' + fmt(shownHi) + ' · lowest shown ' + fmt(shownLo) + ' — shown weeks only, not a lifetime high/low.');
      if (ENH.drawdown && ddInfo) lines.push('Max drawdown ' + (ddInfo.pct * 100).toFixed(1) + '% · ' + viewWeeks[ddInfo.peak].label + ' → ' + viewWeeks[ddInfo.trough].label + '.');
      if (ENH.patterns) lines.push(patCount ? patCount + ' pattern hint' + (patCount === 1 ? '' : 's') + ' marked (white dots). Tap a candle to see its pattern.' : 'No pattern hints on these weeks.');
      if (ENH.volume) {
        if (hasVol) {
          var vs = 0, vc = 0; viewWeeks.forEach(function (w) { if (typeof w.volume === 'number' && w.volume > 0) { vs += w.volume; vc++; } });
          lines.push('Volume: latest week ' + fmtVol(viewWeeks[n - 1].volume) + ' · average ' + fmtVol(vc ? vs / vc : 0) + '.');
        } else lines.push('Volume: no volume data in the shipped file for this symbol.');
      }
      if ((ENH.boll || ENH.drawdown) && (state.cfg.lastInProgress || state.progressNote)) lines.push(bollMode === 'daily' && ENH.boll ? 'Daily Bollinger for the in-progress week uses the latest completed session.' : 'Bollinger/drawdown include the in-progress latest week.');
      if (lines.length) { note.textContent = lines.join(' '); note.style.display = 'block'; }
      else { note.style.display = 'none'; note.textContent = ''; }
    }
    state.viewWeeks = viewWeeks; state.viewStart = viewStart;
    canvas._plot = { padL: padL, slot: slot, n: n };
    if (prog < 1 && !reducedM) requestAnimationFrame(function () { draw(); });
  }

  function onCanvasTap(e, isScrub) {
    var canvas = el('ind-canvas');
    if (!canvas || !canvas._plot) return;
    if (state.infoOpen) { hideInfo(); return; }
    var rect = canvas.getBoundingClientRect();
    var tapX = e.clientX - rect.left;
    var x = tapX - canvas._plot.padL;
    var idx = Math.floor(x / canvas._plot.slot);
    var vw = state.viewWeeks || state.weeks;
    // Forgiving right edge: the in-progress last candle's live outline
    // extends past its slot, and a finger tap on it (or in the right
    // margin) lands just past the last slot — idx == vw.length, which
    // the old code dropped silently. If the tap is still inside the
    // canvas, it meant the last candle. The left (y-axis) edge is not
    // clamped: tapping the axis labels selects nothing.
    if (idx >= vw.length) {
      if (tapX >= 0 && tapX <= canvas.clientWidth) idx = vw.length - 1;
      else return;
    }
    if (idx < 0 || idx >= vw.length) return;
    // Toggle-off (round 3, 8 Nov 2026): tapping the already-selected
    // candle dismisses the pill. Before this, a re-tap just re-selected
    // the same candle and the pill could never be dismissed that way —
    // the only dismiss was tapping the pill itself. Not during a scrub:
    // pointermove calls this while dragging, and dismissing mid-scrub
    // would fight the drag.
    if (!isScrub && idx === state.selected) {
      var pill = el('ind-pill');
      if (pill) pill.style.display = 'none';
      state.selected = -1;
      draw();
      return;
    }
    state.selected = idx;
    var w = vw[idx];
    // 5-min desk-live overlay: if the tapped candle is the
    // in-progress last candle, show the overlaid desk-live values
    // (display only — the shipped week is never mutated), so the pill
    // matches the drawn chart.
    if (idx === vw.length - 1) w = deskLiveWeekFor(w);
    // Live display: if the tapped candle is the in-progress last
    // candle and the modal is live, show the live-extended values
    // (display only — the shipped week is never mutated).
    if (idx === vw.length - 1 && state.liveOn && isInProgress() && typeof state.livePrice === 'number' && isFinite(state.livePrice)) {
      w = liveWeekFor(w, state.livePrice);
    }
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
      var lastCur = isLast && weekCoversToday(w);
      if (lastCur && state.liveOn && isInProgress()) html += '<br><i>Latest week is live — its close follows the live price and is not a final close.</i>';
      else if (lastCur && state.cfg.lastInProgress) html += '<br><i>Latest week ' + state.cfg.lastInProgress + ' — close is not a final daily close.</i>';
      else if (lastCur && state.progressNote) html += '<br><i>Latest week is ' + state.progressNote + '.</i>';
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
    var tile = e.target.closest ? e.target.closest('.tile[data-symbol]') : null;
    if (tile && CONFIGS[tile.getAttribute('data-symbol')]) {
      var cfg = CONFIGS[tile.getAttribute('data-symbol')];
      if (state.cfg && state.cfg.symbol === cfg.symbol && state.weeks.length) { state.cfg = cfg; openModal(cfg); }
      else { state.weeks = []; openModal(cfg); }
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
      state.weeks = []; loadData(); fetchDeskLive(); return;
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
    refreshLive();
  });
  window.addEventListener('screener-ind-rows', function (e) {
    state.indRows = (e && e.detail) || [];
    refreshLive();
  });
  document.addEventListener('visibilitychange', function () {
    // 5-min desk-live overlay: when the tab comes back, re-fetch the
    // current-week candle (throttled) so the modal shows fresh data
    // without waiting for the next 5-min poll.
    if (document.visibilityState !== 'visible') return;
    var modal = el('ind-modal');
    if (!modal || !modal.classList.contains('open') || !state.weeks.length) return;
    deskLiveMaybeRefresh();
  });
  document.addEventListener('DOMContentLoaded', function () {
    var canvas = el('ind-canvas');
    if (canvas) {
      // Round 3 press-end dismiss (8 Nov 2026): the tap logic runs on
      // press end (pointerup/pointercancel/touchend/touchcancel) via
      // endPress, using the pointerdown position, so it works even when
      // the browser never dispatches a click for the tap — which is what
      // happens for real finger taps on iOS. Before this, the canvas tap
      // was click-only, and onCanvasTap had no toggle-off at all, so a
      // same-candle re-tap could never dismiss the pill. A press only
      // counts as a drag when the scrub actually moved the selection;
      // how far the finger moved does not matter. The click handler is
      // only a fallback, suppressed via pressDone so a tap is never
      // applied twice. The press is armed on touchstart as well as
      // pointerdown.
      var scrubbing = false, scrubChanged = false, downX = 0, downY = 0, pressDone = false, SCRUB_PX = 24;
      var endPress = function () {
        if (pressDone) return;
        pressDone = true;
        if (scrubChanged) return;
        onCanvasTap({ clientX: downX }, false);
      };
      var armPress = function (x, y) {
        scrubbing = true; scrubChanged = false; pressDone = false;
        downX = x; downY = y;
      };
      canvas.addEventListener('click', function (e) { if (pressDone) { pressDone = false; return; } onCanvasTap(e, false); });
      canvas.addEventListener('pointerdown', function (e) { armPress(e.clientX, e.clientY); });
      canvas.addEventListener('touchstart', function (e) { if (!e.touches || !e.touches.length) return; var t = e.touches[0]; armPress(t.clientX, t.clientY); }, { passive: true });
      canvas.addEventListener('pointerup', function () { scrubbing = false; endPress(); });
      canvas.addEventListener('pointercancel', function () { scrubbing = false; endPress(); });
      canvas.addEventListener('touchend', function () { scrubbing = false; endPress(); }, { passive: true });
      canvas.addEventListener('touchcancel', function () { scrubbing = false; endPress(); }, { passive: true });
      // Mockup 2 scrub: drag across the chart and the pill follows
      // candle by candle. Small movements (<= SCRUB_PX) do not move the
      // selection, so a tap is not mistaken for a scrub.
      canvas.addEventListener('pointermove', function (e) {
        if (!scrubbing) return;
        var d = Math.max(Math.abs(e.clientX - downX), Math.abs(e.clientY - downY));
        if (d <= SCRUB_PX) return;
        var before = state.selected;
        onCanvasTap({ clientX: e.clientX }, true);
        if (state.selected !== before) scrubChanged = true;
      });
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
        if (k === 'boll') {
          syncBollModeUI();
          if (ENH.boll && bollMode === 'daily') loadDailyBoll();
        }
        draw();
      });
    });
    // Bollinger Weekly/Daily switch: one set at a time. Shown only
    // while Bollinger is on (syncBollModeUI). Daily loads the symbol's
    // daily file on demand; a failed load falls back to weekly.
    document.querySelectorAll('[data-bollmode]').forEach(function (b) {
      b.addEventListener('click', function () {
        var m = b.getAttribute('data-bollmode');
        if (m !== 'weekly' && m !== 'daily') return;
        if (!ENH.boll) return;
        bollMode = m;
        syncBollModeUI();
        if (m === 'daily') loadDailyBoll();
        else draw();
      });
    });
  });

  // Exposed for the headless verification harness only.
  window.IndicatorChart = { CONFIGS: CONFIGS, STOCKS: STOCKS, applyLiveWeek: applyLiveWeek, weekCoversToday: weekCoversToday, liveWeekFor: liveWeekFor, deskLiveWeekFor: deskLiveWeekFor, deskLiveFresh: deskLiveFresh, deskLiveEntryFor: deskLiveEntryFor, etTodayISO: etTodayISO, nextWeekClose: nextWeekClose, countdownText: countdownText, nyOffsetHours: nyOffsetHours, enhBoll: enhBoll, enhBollDaily: enhBollDaily, enhDrawdown: enhDrawdown, enhPattern: enhPattern, fmtVol: fmtVol };
})();
