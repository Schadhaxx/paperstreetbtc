window.psC=window.psC||function(d,l){return document.documentElement.getAttribute('data-theme')==='light'?l:d;};
// Comparison chart for the Maple Leaf screener.
// Lines are rebased daily closes (assets/data/cmp-daily.json). The last
// point of a stock uses the merged row from screener.js when that row is
// the same session or a newer one. Older snapshots do not erase a newer
// close. Day-change and YTD bars read those rows directly, so they cannot
// drift from the cards.
// Rendering is native canvas (no chart library): the line view draws
// rebased lines with end labels and a hover crosshair, the bar view draws
// horizontal day/YTD bars. A desk-live.json point (5-min current-week
// close) fills today's point when the card row does not cover today and
// the entry is fresh; see fetchDeskLive. The 5-min re-check calls
// window.ScreenerChartRefreshDeskLive() to re-fetch it; no timer lives
// in this file.
// Signed zero stays black (#000000). On this dark card that text is hard
// to see; the choice is deliberate and called out in the proposal.
(function () {
  var CmpMath = (function () {
    var YTD_BASE = '2025-12-31';
    var LISTING = '2026-06-12';
    function isNum(v) { return typeof v === 'number' && isFinite(v); }
    function pad(n) { return (n < 10 ? '0' : '') + n; }
    function fmtPct(v) {
      if (!isNum(v)) return '\u2014';
      return (v > 0 ? '+' : '') + v.toFixed(2) + '%';
    }
    function sign(v) {
      if (!isNum(v)) return '';
      if (v > 0) return 'up';
      if (v < 0) return 'down';
      return 'flat';
    }
    function cmpMoney(v) {
      if (!isNum(v)) return '\u2014';
      var s = Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      return (v < 0 ? '-$' : '$') + s;
    }
    function shiftMonths(iso, months) {
      var y = +iso.slice(0, 4), m = +iso.slice(5, 7) - 1, day = +iso.slice(8, 10);
      var dt = new Date(Date.UTC(y, m + months, 1));
      var dim = new Date(Date.UTC(dt.getUTCFullYear(), dt.getUTCMonth() + 1, 0)).getUTCDate();
      var d = Math.min(day, dim);
      return dt.getUTCFullYear() + '-' + pad(dt.getUTCMonth() + 1) + '-' + pad(d);
    }
    function lastOnOrBefore(dates, iso) {
      var found = null;
      for (var i = 0; i < dates.length; i++) {
        if (dates[i] <= iso) found = dates[i];
        else break;
      }
      return found;
    }
    function commonTarget(range, asOf) {
      if (range === 'ytd') return YTD_BASE;
      if (range === 'listing') return LISTING;
      var months = range === '1M' ? -1 : range === '3M' ? -3 : range === '6M' ? -6 : null;
      if (months === null) return YTD_BASE;
      return shiftMonths(asOf, months);
    }
    // anchorDate is the common start. explicitBase is the 31 Dec close for
    // a YTD name, because that session is not in the daily series. Returns
    // null when the symbol was not listed yet (do not invent a line).
    function cmpRebase(dates, closes, anchorDate, explicitBase) {
      if (!dates || !dates.length || !anchorDate || dates.length !== closes.length) return null;
      var startAt = -1;
      for (var i = 0; i < dates.length; i++) {
        if (dates[i] <= anchorDate) startAt = i;
        else break;
      }
      var outD = [], outP = [], base;
      if (startAt === -1) {
        if (!isNum(explicitBase) || !(explicitBase > 0)) return null;
        base = explicitBase;
        outD.push(anchorDate);
        outP.push(0);
        for (var j = 0; j < dates.length; j++) {
          if (dates[j] <= anchorDate) continue;
          outD.push(dates[j]);
          outP.push((closes[j] / base - 1) * 100);
        }
      } else {
        base = closes[startAt];
        if (!isNum(base) || !(base > 0)) return null;
        for (var k = startAt; k < dates.length; k++) {
          outD.push(dates[k]);
          outP.push((closes[k] / base - 1) * 100);
        }
      }
      if (outD.length < 2) return null;
      if (Math.abs(outP[0]) > 1e-9) return null;
      return { dates: outD, pcts: outP, base: base };
    }
    function rankDesc(rows) {
      return rows.slice().sort(function (a, b) {
        var av = isNum(a.pct) ? a.pct : -Infinity;
        var bv = isNum(b.pct) ? b.pct : -Infinity;
        if (bv !== av) return bv - av;
        return String(a.sym).localeCompare(String(b.sym));
      });
    }
    return {
      YTD_BASE: YTD_BASE, LISTING: LISTING, isNum: isNum, fmtPct: fmtPct, sign: sign,
      cmpMoney: cmpMoney, shiftMonths: shiftMonths, lastOnOrBefore: lastOnOrBefore,
      commonTarget: commonTarget, cmpRebase: cmpRebase, rankDesc: rankDesc
    };
  })();

  var STOCKS = ['TSLA', 'PLTR', 'MSTR', 'IBIT', 'MU', 'META', 'SPCX', 'BRK.B', 'AAPL', 'AMZN', 'MSFT', 'NFLX', 'SPOT', 'XYZ', 'GOOGL', 'NVDA'];
  var BENCH = ['BTC', 'SPY', 'QQQ'];
  var COLOR = {
    TSLA: psC('#22d3ee','#0891b2'), PLTR: psC('#a78bfa','#7c3aed'), MSTR: psC('#fb923c','#ea580c'), IBIT: psC('#38bdf8','#0284c7'),
    MU: psC('#facc15','#ca8a04'), META: psC('#fb7185','#e11d48'), SPCX: psC('#2dd4bf','#0d9488'),
    'BRK.B': psC('#c084fc','#7e22ce'), AAPL: psC('#60a5fa','#2563eb'), AMZN: psC('#fbbf24','#d97706'),
    MSFT: psC('#34d399','#059669'), NFLX: psC('#f87171','#dc2626'), SPOT: psC('#4ade80','#16a34a'),
    XYZ: psC('#e879f9','#a21caf'), GOOGL: psC('#38bdf8','#0369a1'), NVDA: psC('#a3e635','#65a30d'),
    BTC: psC('#94a3b8','#475569'), SPY: psC('#64748b','#334155'), QQQ: psC('#cbd5e1','#64748b')
  };
  var CMP_V = '20261031a';
  var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  var MN = { Jan: '01', Feb: '02', Mar: '03', Apr: '04', May: '05', Jun: '06', Jul: '07', Aug: '08', Sep: '09', Oct: '10', Nov: '11', Dec: '12' };

  var daily = null;
  var dailyError = false;
  var rows = [];
  var deskLive = null; // {asOfMs, bySym:{sym:{close, monday}}} or null
  var deskLiveAt = 0;
  var deskLiveToken = 0;
  var view = 'lines';
  var range = 'ytd';
  var barMetric = 'day';
  var on = {};
  var benchOn = { BTC: false, SPY: false, QQQ: false };
  var hi = null;
  var chart = null; // Chart.js instance for the bar view until it goes native; null in the line view
  var native = null; // native line geometry for hover/click/redraw, or null
  STOCKS.forEach(function (s) { on[s] = (s === 'IBIT' || s === 'MSTR'); });

  function motionOK() {
    return !(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }
  function rowBy(sym) {
    for (var i = 0; i < rows.length; i++) if (rows[i].symbol === sym) return rows[i];
    return null;
  }
  function asOf() { return (daily && daily.asOf) || '2026-10-30'; }
  function asOfLabel() { return (daily && daily.asOfLabel) || '30 Oct 2026'; }
  function todayET() {
    try {
      return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
    } catch (e) { return null; }
  }
  function parsePretty(label) {
    var p = String(label || '').split(' ');
    if (p.length !== 3 || !MN[p[1]] || !/^\d{4}$/.test(p[2])) return null;
    var day = ('0' + p[0]).slice(-2);
    return p[2] + '-' + MN[p[1]] + '-' + day;
  }
  function rowSession(row) {
    if (!row || row._src === 'snapshot') return null;
    if (row._src === 'live') return todayET();
    if (row._closeDate) return parsePretty(row._closeDate);
    return null;
  }
  // --- desk-live.json overlay (5-min current-week close) ---
  // Same source and freshness rule as the weekly-modal overlay in
  // screener-indicator-chart.js (asOf < ~20 min old, Monday matches the
  // week being drawn), adapted to daily closes: the entry's close is
  // today's point for a stock whose daily series does not reach today.
  // A missing or stale file is a silent fallback, never an error: the
  // shipped daily file is the source of truth and the overlay is a
  // freshness bonus.
  var DESK_LIVE_URL = 'https://raw.githubusercontent.com/Schadhaxx/paperstreetbtc/data/desk-live.json';
  var DESK_LIVE_MAX_AGE_MS = 20 * 60 * 1000; // ~20 min
  var DESK_LIVE_MIN_REFETCH_MS = 4 * 60 * 1000; // throttle repeat fetches
  function deskLiveFresh(asOfMs, nowMs) {
    if (typeof asOfMs !== 'number' || !isFinite(asOfMs)) return false;
    var t = (nowMs === undefined) ? Date.now() : nowMs;
    if (typeof t !== 'number' || !isFinite(t)) return false;
    // Allow up to 60s of clock skew the other way; the entry must not
    // be from the future beyond that, nor older than ~20 min.
    return asOfMs <= t + 60000 && (t - asOfMs) < DESK_LIVE_MAX_AGE_MS;
  }
  function mondayOf(iso) {
    // Monday (UTC) of the week containing an ISO date.
    var d = new Date(iso + 'T12:00:00Z');
    if (isNaN(d.getTime())) return null;
    var back = (d.getUTCDay() + 6) % 7;
    return new Date(d.getTime() - back * 86400000).toISOString().slice(0, 10);
  }
  function deskLivePointFor(sym, today) {
    if (!deskLive || !deskLive.bySym) return null;
    var e = deskLive.bySym[sym];
    if (!e) return null;
    if (!deskLiveFresh(deskLive.asOfMs)) return null;
    if (e.monday !== mondayOf(today)) return null;
    if (typeof e.close !== 'number' || !isFinite(e.close) || !(e.close > 0)) return null;
    return Math.round(e.close * 100) / 100;
  }
  function fetchDeskLive(force) {
    var now = Date.now();
    if (!force && deskLiveAt && now - deskLiveAt < DESK_LIVE_MIN_REFETCH_MS) return;
    var token = ++deskLiveToken;
    fetch(DESK_LIVE_URL + '?t=' + now, { cache: 'no-store' })
      .then(function (res) { if (!res.ok) throw new Error('no desk-live file'); return res.json(); })
      .then(function (data) {
        if (token !== deskLiveToken) return; // stale response: ignore
        var asOfMs = (data && typeof data.asOf === 'string') ? Date.parse(data.asOf) : NaN;
        var bySym = {};
        if (deskLiveFresh(asOfMs) && data && data.symbols && typeof data.symbols === 'object') {
          var syms = data.symbols, k, en;
          for (k in syms) {
            en = syms[k];
            if (!en || en.status !== 'ok') continue;
            if (typeof en.close !== 'number' || !isFinite(en.close)) continue;
            if (typeof en.monday !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(en.monday)) continue;
            bySym[k] = { close: en.close, monday: en.monday };
          }
        }
        deskLive = { asOfMs: asOfMs, bySym: bySym };
        deskLiveAt = Date.now();
        render();
      })
      .catch(function () {
        if (token !== deskLiveToken) return;
        // Silent fallback: no desk-live file (or a bad one) just means
        // the shipped daily file stands. No error is shown.
        deskLive = null;
        deskLiveAt = Date.now();
      });
  }
  // Update hook for the 5-min re-check (polling while a chart is open +
  // refresh on tab return, wired by the caller): re-fetches desk-live.json
  // and re-renders. No timer lives in this file.
  window.ScreenerChartRefreshDeskLive = function () { fetchDeskLive(true); };
  function seriesFor(sym) {
    var s = daily && daily.symbols && daily.symbols[sym];
    if (!s || !s.dates || !s.closes) return null;
    var dates = s.dates.slice();
    var closes = s.closes.slice();
    var row = rowBy(sym);
    if (row && CmpMath.isNum(row.price) && s.kind === 'stock') {
      var session = rowSession(row);
      var last = dates[dates.length - 1];
      if (session && session > last) {
        dates.push(session);
        closes.push(Math.round(row.price * 100) / 100);
      } else if (session && session === last) {
        closes[closes.length - 1] = Math.round(row.price * 100) / 100;
      }
    }
    // 5-min desk-live point: only when the row above did not already put
    // a point on today, the entry is fresh, and its Monday is the Monday
    // of the week containing today. Otherwise the shipped daily file
    // stands (desk-live.json does not exist yet on some loads; a missing
    // or stale file is a silent fallback, never an error).
    var lastD = dates[dates.length - 1];
    var today = todayET();
    if (s.kind === 'stock' && today && lastD < today) {
      var dl = deskLivePointFor(sym, today);
      if (dl !== null) {
        dates.push(today);
        closes.push(dl);
      }
    }
    return { dates: dates, closes: closes, baseClose: s.baseClose, basis: s.basis, kind: s.kind };
  }
  function selectedStocks() {
    return STOCKS.filter(function (s) { return on[s]; });
  }
  function lineModel() {
    var target = CmpMath.commonTarget(range, asOf());
    var names = selectedStocks().concat(BENCH.filter(function (s) { return benchOn[s]; }));
    var models = [], excluded = [];
    names.forEach(function (sym) {
      var ser = seriesFor(sym);
      if (!ser) { excluded.push(sym); return; }
      var anchor = target, explicit = null;
      if (range === 'ytd') {
        if (ser.basis === 'listing') { excluded.push(sym); return; }
        explicit = ser.baseClose;
      } else {
        var hit = CmpMath.lastOnOrBefore(ser.dates, target);
        if (!hit) { excluded.push(sym); return; }
        anchor = hit;
      }
      var rb = CmpMath.cmpRebase(ser.dates, ser.closes, anchor, explicit);
      if (!rb) { excluded.push(sym); return; }
      models.push({
        sym: sym, kind: ser.kind, dates: rb.dates, pcts: rb.pcts,
        pct: rb.pcts[rb.pcts.length - 1]
      });
    });
    return { models: models, excluded: excluded, target: target };
  }
  function dayPct(sym) {
    var r = rowBy(sym);
    return r && CmpMath.isNum(r.dayChangePct) ? r.dayChangePct : null;
  }
  function ytdPct(sym) {
    var r = rowBy(sym);
    if (!r || !CmpMath.isNum(r.ytdPct)) return null;
    if (r.ytdBasis === 'listing') return null;
    return r.ytdPct;
  }
  function listingPct(sym) {
    var r = rowBy(sym);
    if (r && r.ytdBasis === 'listing' && CmpMath.isNum(r.ytdPct)) return r.ytdPct;
    var ser = seriesFor(sym);
    if (!ser || ser.basis !== 'listing') return null;
    var rb = CmpMath.cmpRebase(ser.dates, ser.closes, ser.dates[0], null);
    return rb ? rb.pcts[rb.pcts.length - 1] : null;
  }
  function priceOf(sym) {
    var r = rowBy(sym);
    if (r && CmpMath.isNum(r.price)) return r.price;
    var s = daily && daily.symbols && daily.symbols[sym];
    if (s && s.closes && s.closes.length) return s.closes[s.closes.length - 1];
    return null;
  }

  function destroyChart() {
    if (chart) { chart.destroy(); chart = null; }
    native = null;
    var canvas = document.getElementById('screener-chart');
    if (canvas) {
      var g = canvas.getContext('2d');
      if (g) g.clearRect(0, 0, canvas.width, canvas.height);
    }
  }
  function hexAlpha(hex, a) {
    var n = parseInt(hex.slice(1), 16);
    return 'rgba(' + ((n >> 16) & 255) + ',' + ((n >> 8) & 255) + ',' + (n & 255) + ',' + a + ')';
  }
  function fade(hex, dim) {
    return dim ? hexAlpha(hex, 0.28) : hex;
  }

  var gridPlugin = {
    id: 'cmpGrid',
    beforeDraw: function (c) {
      if (c.options.indexAxis === 'y') return;
      var y = c.scales.y, area = c.chartArea, g = c.ctx;
      if (!y || !area) return;
      g.save();
      g.setLineDash([2, 4]);
      g.lineWidth = 1;
      (y.ticks || []).forEach(function (t) {
        var py = y.getPixelForValue(t.value);
        if (py < area.top - 1 || py > area.bottom + 1) return;
        g.strokeStyle = t.value === 0 ? psC('rgba(238,242,251,.42)','rgba(15,23,42,.35)') : psC('rgba(148,163,184,.16)','rgba(15,23,42,.10)');
        g.beginPath();
        g.moveTo(area.left, py);
        g.lineTo(area.right, py);
        g.stroke();
      });
      g.restore();
    }
  };
  // --- native canvas line view ---
  // Chart.js linear-scale tick generation, replicated the way the Stage 2
  // BTC native line does it: step = niceNum(span/(maxTicks-1)), widened
  // once if the tick count would exceed the limit.
  function cmpNiceNum(x) {
    if (!(x > 0)) return 1;
    var r = Math.round(x);
    if (Math.abs(x - r) < x / 1e3) x = r;
    var p = Math.pow(10, Math.floor(Math.log10(x)));
    var s = x / p;
    return (s <= 1 ? 1 : s <= 2 ? 2 : s <= 5 ? 5 : 10) * p;
  }
  function cmpNiceTicks(min, max, maxTicks) {
    if (!(max > min)) { max = min + 1; }
    var mt = Math.max(2, maxTicks || 6);
    var span = max - min, step = cmpNiceNum(span / (mt - 1));
    var k = Math.ceil(max / step) - Math.floor(min / step);
    if (k > mt - 1) step = cmpNiceNum(k * step / (mt - 1));
    var t0 = Math.floor(min / step) * step, t1 = Math.ceil(max / step) * step, out = [];
    for (var v = t0; v <= t1 + step * 0.01; v += step) out.push(Math.round(v * 1000) / 1000);
    return out;
  }
  function nativeSpline(ctx, xs, ys, tension, b) {
    // Chart.js splineCurve (Catmull-Rom), as in the Stage 2 BTC native
    // line: control points clamped to the plot bounds.
    var n = xs.length;
    if (n < 1) return;
    ctx.moveTo(xs[0], ys[0]);
    if (n === 1) return;
    if (!tension || n === 2) { for (var i = 1; i < n; i++) ctx.lineTo(xs[i], ys[i]); return; }
    function spline(pX, pY, cX, cY, nX, nY, t) {
      var d01 = Math.sqrt(Math.pow(cX - pX, 2) + Math.pow(cY - pY, 2));
      var d12 = Math.sqrt(Math.pow(nX - cX, 2) + Math.pow(nY - cY, 2));
      var s01 = d01 / (d01 + d12), s12 = d12 / (d01 + d12);
      if (isNaN(s01)) s01 = 0;
      if (isNaN(s12)) s12 = 0;
      var fa = t * s01, fb = t * s12;
      return { prev: { x: cX - fa * (nX - pX), y: cY - fa * (nY - pY) },
               next: { x: cX + fb * (nX - pX), y: cY + fb * (nY - pY) } };
    }
    function clamp(v, lo, hi) { return Math.max(Math.min(v, hi), lo); }
    var cp1x = [], cp1y = [], cp2x = [], cp2y = [], j;
    for (j = 0; j < n; j++) {
      var p = Math.max(0, j - 1), q = Math.min(n - 1, j + 1);
      var c = spline(xs[p], ys[p], xs[j], ys[j], xs[q], ys[q], tension);
      cp1x[j] = c.prev.x; cp1y[j] = c.prev.y; cp2x[j] = c.next.x; cp2y[j] = c.next.y;
    }
    if (b) {
      for (j = 0; j < n; j++) {
        cp1x[j] = clamp(cp1x[j], b.l, b.r); cp1y[j] = clamp(cp1y[j], b.t, b.b);
        cp2x[j] = clamp(cp2x[j], b.l, b.r); cp2y[j] = clamp(cp2y[j], b.t, b.b);
      }
    }
    for (var i = 0; i < n - 1; i++) {
      ctx.bezierCurveTo(cp2x[i], cp2y[i], cp1x[i + 1], cp1y[i + 1], xs[i + 1], ys[i + 1]);
    }
  }
  function setupCanvas(canvas, wrap) {
    // Size the backing store to the wrap (CSS pixels x devicePixelRatio,
    // capped at 2) and return a context already scaled to CSS pixels.
    var w = (wrap && wrap.clientWidth) || canvas.clientWidth || 0;
    var h = (wrap && wrap.clientHeight) || canvas.clientHeight || 0;
    if (w < 10 || h < 10) return null;
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var bw = Math.round(w * dpr), bh = Math.round(h * dpr);
    if (canvas.width !== bw || canvas.height !== bh) { canvas.width = bw; canvas.height = bh; }
    canvas.style.width = '100%';
    canvas.style.height = '100%';
    var ctx = canvas.getContext('2d');
    if (!ctx) return null;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { ctx: ctx, w: w, h: h };
  }
  function paintNativeLines() {
    if (!native || native.kind !== 'lines') return;
    var canvas = document.getElementById('screener-chart');
    var wrap = document.getElementById('cmp-canvas-wrap');
    if (!canvas) return;
    var s = setupCanvas(canvas, wrap);
    if (!s) return;
    var ctx = s.ctx, W = s.w, H = s.h;
    var labels = native.labels, rows = native.tipRows, ordered = native.ordered;
    var n = labels.length;
    var vmin = Infinity, vmax = -Infinity;
    rows.forEach(function (r) {
      r.vals.forEach(function (v) { if (CmpMath.isNum(v)) { if (v < vmin) vmin = v; if (v > vmax) vmax = v; } });
    });
    if (!isFinite(vmin)) return;
    if (vmax - vmin < 1e-9) { vmax = vmin + 1; vmin = vmin - 1; }
    var ticks = cmpNiceTicks(vmin, vmax, 6);
    var tMin = ticks[0], tMax = ticks[ticks.length - 1];
    var phone = W < 520;
    // Plot area: left from the widest y-tick label, right 96 (8 on phone)
    // for the end labels, top 8, bottom room for the month ticks.
    ctx.font = '11px -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif';
    var yW = 0;
    ticks.forEach(function (t) { yW = Math.max(yW, ctx.measureText(CmpMath.fmtPct(t)).width); });
    var padL = Math.ceil(yW) + 8, padR = phone ? 8 : 96, padT = 8, padB = 18;
    var x0 = padL, x1 = W - padR, y0 = padT, y1 = H - padB;
    function X(i) { return n <= 1 ? (x0 + x1) / 2 : x0 + (x1 - x0) * i / (n - 1); }
    function Y(v) { return y1 - (y1 - y0) * (v - tMin) / (tMax - tMin); }
    var sets = rows.map(function (r, ri) {
      var m = ordered[ri];
      var dim = native.hi && r.sym !== native.hi;
      var col = COLOR[r.sym] || psC('#94a3b8', '#475569');
      var pts = r.vals.map(function (v, i) { return CmpMath.isNum(v) ? { x: X(i), y: Y(v), v: v } : null; });
      return { sym: r.sym, kind: r.kind, col: col, dim: dim, end: m.pct, pts: pts };
    });
    native.sets = sets;
    native.geom = { x0: x0, x1: x1, y0: y0, y1: y1, n: n };
    // Y gridlines (dashed) + tick labels; the 0 line is stronger.
    ctx.textBaseline = 'middle';
    ctx.textAlign = 'right';
    ticks.forEach(function (t) {
      var py = Y(t);
      if (py < y0 - 1 || py > y1 + 1) return;
      ctx.save();
      ctx.setLineDash([2, 4]);
      ctx.lineWidth = 1;
      ctx.strokeStyle = t === 0 ? psC('rgba(238,242,251,.42)', 'rgba(15,23,42,.35)') : psC('rgba(148,163,184,.16)', 'rgba(15,23,42,.10)');
      ctx.beginPath();
      ctx.moveTo(x0, py);
      ctx.lineTo(x1, py);
      ctx.stroke();
      ctx.restore();
      ctx.fillStyle = '#94a3b8';
      ctx.fillText(CmpMath.fmtPct(t), x0 - 6, py);
    });
    // X month ticks (autoSkip: every ceil(n/limit)-th label from index 0).
    var maxTicks = phone ? 4 : 7;
    var step = Math.max(1, Math.ceil(n / maxTicks));
    ctx.textAlign = 'center';
    ctx.fillStyle = '#94a3b8';
    for (var i = 0; i < n; i += step) {
      var lab = labels[i];
      if (!lab || lab.length < 7) continue;
      ctx.fillText(MONTHS[+lab.slice(5, 7) - 1], X(i), y1 + 10);
    }
    // Highlight fill under the highlighted line, down to the 0 line.
    var hiSet = null;
    sets.forEach(function (st) { if (st.sym === native.hi) hiSet = st; });
    if (hiSet) {
      var hx = [], hy = [];
      hiSet.pts.forEach(function (p) { if (p) { hx.push(p.x); hy.push(p.y); } });
      if (hx.length > 1) {
        var yZero = Math.max(y0, Math.min(y1, Y(0)));
        ctx.save();
        ctx.beginPath();
        nativeSpline(ctx, hx, hy, 0.3, { l: x0, r: x1, t: y0, b: y1 });
        ctx.lineTo(hx[hx.length - 1], yZero);
        ctx.lineTo(hx[0], yZero);
        ctx.closePath();
        var g = ctx.createLinearGradient(0, y0, 0, y1);
        g.addColorStop(0, hexAlpha(hiSet.col, 0.38));
        g.addColorStop(1, hexAlpha(hiSet.col, 0));
        ctx.fillStyle = g;
        ctx.fill();
        ctx.restore();
      }
    }
    // Lines (spanGaps: connect across missing dates).
    sets.forEach(function (st) {
      var xs = [], ys = [];
      st.pts.forEach(function (p) { if (p) { xs.push(p.x); ys.push(p.y); } });
      if (xs.length < 2) return;
      ctx.save();
      ctx.beginPath();
      nativeSpline(ctx, xs, ys, 0.3, { l: x0, r: x1, t: y0, b: y1 });
      ctx.strokeStyle = fade(st.col, st.dim);
      ctx.lineWidth = st.sym === native.hi ? 3 : (st.kind === 'benchmark' ? 1.5 : 2);
      ctx.setLineDash(st.kind === 'benchmark' ? [5, 4] : []);
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';
      ctx.stroke();
      ctx.restore();
    });
    // End labels (same placement/collision rules as the old plugin:
    // highlight first, then stocks, then benchmarks; a label that would
    // collide with a placed label or cross another line is skipped).
    ctx.font = '700 11px -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif';
    ctx.textBaseline = 'middle';
    ctx.textAlign = 'left';
    var placed = [];
    var cands = [];
    sets.forEach(function (st) {
      var last = null;
      for (var i = st.pts.length - 1; i >= 0; i--) { if (st.pts[i]) { last = st.pts[i]; break; } }
      if (!last) return;
      var label = st.sym + ' ' + CmpMath.fmtPct(st.end);
      var dim = st.dim;
      if (dim && phone) return;
      var tw = ctx.measureText(label).width;
      var x = last.x + 6;
      if (x + tw > W - 4) x = Math.max(x0, last.x - tw - 6);
      var y = Math.max(y0 + 6, Math.min(y1 - 6, last.y));
      cands.push({ st: st, last: last, label: label, dim: dim, x: x, y: y, w: tw,
        pri: st.sym === native.hi ? 0 : (st.kind === 'benchmark' ? 2 : 1) });
    });
    cands.sort(function (a, b) { return a.pri - b.pri; });
    function crossesLine(cd) {
      for (var k = 0; k < sets.length; k++) {
        var pts = sets[k].pts;
        for (var j = 0; j < pts.length; j++) {
          var pt = pts[j];
          if (!pt || pt === cd.last) continue;
          if (pt.x >= cd.x - 2 && pt.x <= cd.x + cd.w + 2 && Math.abs(pt.y - cd.y) < 7) return true;
        }
      }
      return false;
    }
    cands.forEach(function (cd) {
      for (var p = 0; p < placed.length; p++) {
        var o = placed[p];
        if (Math.abs(o.y - cd.y) < 13 && cd.x < o.x + o.w + 4 && o.x < cd.x + cd.w + 4) return;
      }
      if (cd.pri > 0 && crossesLine(cd)) return;
      placed.push(cd);
      ctx.fillStyle = fade(cd.st.col, cd.dim);
      ctx.fillText(cd.label, cd.x, cd.y);
    });
    // Hover crosshair + dots at the hovered index (only after a hover;
    // the first paint shows the tip text but no crosshair, as before).
    if (native.tipIndex !== null && native.tipIndex !== undefined && native.tipIndex >= 0 && native.tipIndex < n) {
      var hx2 = X(native.tipIndex);
      ctx.save();
      ctx.strokeStyle = psC('rgba(148,163,184,.55)', 'rgba(15,23,42,.35)');
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(hx2, y0);
      ctx.lineTo(hx2, y1);
      ctx.stroke();
      ctx.restore();
      sets.forEach(function (st) {
        var p = st.pts[native.tipIndex];
        if (!p) return;
        ctx.save();
        ctx.beginPath();
        ctx.arc(p.x, p.y, 3.5, 0, Math.PI * 2);
        ctx.fillStyle = fade(st.col, st.dim);
        ctx.fill();
        ctx.restore();
      });
    }
  }

  function showTip(labels, idx) {
    var tip = document.getElementById('cmp-tip');
    if (!tip) return;
    if (view !== 'lines' || !native || native.kind !== 'lines' || idx === null || idx === undefined) { tip.hidden = true; return; }
    var items = [];
    native.tipRows.forEach(function (r) {
      var v = r.vals[idx];
      if (!CmpMath.isNum(v)) return;
      items.push({ sym: r.sym, pct: v, kind: r.kind });
    });
    if (!items.length) { tip.hidden = true; return; }
    items = CmpMath.rankDesc(items);
    var date = labels[idx] || '';
    var pretty = date.length >= 10 ? (+date.slice(8, 10) + ' ' + MONTHS[+date.slice(5, 7) - 1] + ' ' + date.slice(0, 4)) : date;
    var html = '<div class="cmp-tip-row"><b>' + pretty + '</b><span></span></div>';
    items.forEach(function (it) {
      html += '<div class="cmp-tip-row"><span><i class="cmp-dot" style="background:' + (COLOR[it.sym] || psC('#94a3b8','#475569')) + '"></i> ' + it.sym + '</span><b class="' + CmpMath.sign(it.pct) + '">' + CmpMath.fmtPct(it.pct) + '</b></div>';
    });
    tip.innerHTML = html;
    tip.hidden = false;
  }

  function renderLines(model) {
    var canvas = document.getElementById('screener-chart');
    var wrap = document.getElementById('cmp-canvas-wrap');
    if (!canvas) return;
    if (wrap) wrap.hidden = false;
    if (!model.models.length) {
      destroyChart();
      showTip([], null);
      return;
    }
    var seen = {}, labels = [];
    model.models.forEach(function (m) {
      m.dates.forEach(function (d) { if (!seen[d]) { seen[d] = 1; labels.push(d); } });
    });
    labels.sort();
    var ordered = model.models.slice().sort(function (a, b) {
      if (a.sym === hi) return 1;
      if (b.sym === hi) return -1;
      return 0;
    });
    var tipRows = ordered.map(function (m) {
      var map = {};
      m.dates.forEach(function (d, i) { map[d] = m.pcts[i]; });
      return { sym: m.sym, kind: m.kind, vals: labels.map(function (d) { return map[d] === undefined ? null : map[d]; }) };
    });
    if (chart) { chart.destroy(); chart = null; } // a bar chart may be showing
    native = { kind: 'lines', labels: labels, tipRows: tipRows, ordered: ordered, hi: hi, tipIndex: null };
    paintNativeLines();
    showTip(labels, labels.length - 1);
  }

  function renderBars() {
    var canvas = document.getElementById('screener-chart');
    var wrap = document.getElementById('cmp-canvas-wrap');
    if (!canvas || typeof Chart === 'undefined') return;
    if (wrap) wrap.hidden = false;
    var tip = document.getElementById('cmp-tip');
    if (tip) tip.hidden = true;
    var list = [];
    selectedStocks().forEach(function (sym) {
      var v = barMetric === 'ytd' ? ytdPct(sym) : dayPct(sym);
      if (barMetric === 'ytd' && sym === 'SPCX') return;
      if (!CmpMath.isNum(v)) return;
      list.push({ sym: sym, pct: v });
    });
    list = CmpMath.rankDesc(list);
    var labels = list.map(function (r) { return r.sym; });
    var values = list.map(function (r) { return r.pct; });
    var colors = values.map(function (v, i) {
      var base = v > 0 ? '#22c55e' : (v < 0 ? '#ef4444' : '#000000');
      if (hi && labels[i] !== hi) return hexAlpha(base, 0.35);
      return base;
    });
    var data = { labels: labels, datasets: [{ data: values, backgroundColor: colors, borderRadius: 8, barThickness: 16 }] };
    var options = {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      animation: motionOK() ? { duration: 500 } : false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: function (item) {
              return (barMetric === 'ytd' ? 'YTD ' : 'Day ') + CmpMath.fmtPct(item.parsed.x);
            }
          }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          border: { display: false },
          ticks: { color: '#94a3b8', callback: function (v) { return CmpMath.fmtPct(v); } }
        },
        y: { grid: { display: false }, border: { display: false }, ticks: { color: '#eef2fb', font: { weight: 700 } } }
      },
      onClick: function (_e, els) {
        if (els && els.length) { var sym = labels[els[0].index]; setTimeout(function () { setHighlight(sym, true); }, 0); }
      }
    };
    destroyChart();
    chart = new Chart(canvas, { type: 'bar', data: data, options: options, plugins: [gridPlugin] });
  }

  function heatColor(v, mode) {
    if (!CmpMath.isNum(v)) return psC('rgba(255,255,255,.06)','rgba(15,23,42,.06)');
    var t = Math.tanh(v / (mode === 'ytd' ? 25 : 2.5));
    if (t > 0) return 'rgba(34,197,94,' + (0.16 + t * 0.74).toFixed(3) + ')';
    if (t < 0) return 'rgba(239,68,68,' + (0.16 + (-t) * 0.74).toFixed(3) + ')';
    return psC('rgba(255,255,255,.06)','rgba(15,23,42,.06)');
  }
  function renderHeat() {
    var box = document.getElementById('cmp-heat');
    var wrap = document.getElementById('cmp-canvas-wrap');
    if (wrap) wrap.hidden = true;
    destroyChart();
    var tip = document.getElementById('cmp-tip');
    if (tip) tip.hidden = true;
    if (!box) return;
    box.hidden = false;
    box.innerHTML = selectedStocks().map(function (sym) {
      var listing = sym === 'SPCX';
      var v = barMetric === 'ytd' ? (listing ? listingPct(sym) : ytdPct(sym)) : dayPct(sym);
      var cap = barMetric === 'day' ? 'Day' : (listing ? 'Since listing' : 'YTD');
      var cls = 'cmp-tile' + (sym === hi ? ' is-hi' : '');
      return '<button type="button" class="' + cls + '" data-cmp-hit="' + sym + '" style="background:' + heatColor(v, barMetric) + '">' +
        '<span class="cmp-sym">' + sym + '</span>' +
        '<span class="cmp-px">' + CmpMath.cmpMoney(priceOf(sym)) + '</span>' +
        '<span class="cmp-ret ' + CmpMath.sign(v) + '">' + CmpMath.fmtPct(v) + '</span>' +
        '<span class="cmp-px">' + cap + '</span></button>';
    }).join('');
  }

  function spark(pcts, color) {
    if (!pcts || pcts.length < 2) return '';
    var step = Math.max(1, Math.floor(pcts.length / 28));
    var pts = [];
    for (var i = 0; i < pcts.length; i += step) pts.push(pcts[i]);
    if (pts[pts.length - 1] !== pcts[pcts.length - 1]) pts.push(pcts[pcts.length - 1]);
    var min = Math.min.apply(null, pts), max = Math.max.apply(null, pts);
    var span = (max - min) || 1, w = 72, h = 28;
    var d = pts.map(function (p, i) {
      var x = (i / (pts.length - 1)) * w;
      var y = h - ((p - min) / span) * (h - 4) - 2;
      return x.toFixed(1) + ',' + y.toFixed(1);
    }).join(' ');
    return '<svg class="cmp-spark" viewBox="0 0 72 28" aria-hidden="true"><polyline points="' + d + '" fill="none" stroke="' + color + '" stroke-width="1.6" /></svg>';
  }

  function renderBoard(model) {
    var board = document.getElementById('cmp-board');
    if (!board) return;
    var items;
    if (view === 'lines' && model) {
      items = CmpMath.rankDesc(model.models.filter(function (m) { return m.kind !== 'benchmark'; }));
    } else if (barMetric === 'day') {
      items = CmpMath.rankDesc(selectedStocks().map(function (sym) { return { sym: sym, pct: dayPct(sym), dates: [], pcts: [] }; }));
    } else {
      items = CmpMath.rankDesc(selectedStocks().filter(function (s) { return s !== 'SPCX'; }).map(function (sym) {
        return { sym: sym, pct: ytdPct(sym), dates: [], pcts: [] };
      }));
    }
    var dayTwice = view !== 'lines' && barMetric === 'day';
    board.innerHTML = items.map(function (it) {
      var day = dayPct(it.sym);
      return '<li class="cmp-row' + (it.sym === hi ? ' is-hi' : '') + '"><button type="button" data-cmp-hit="' + it.sym + '">' +
        '<i class="cmp-swatch" style="background:' + (COLOR[it.sym] || psC('#94a3b8','#475569')) + '"></i>' +
        '<span class="cmp-sym">' + it.sym + '</span>' +
        spark(it.pcts, COLOR[it.sym] || psC('#94a3b8','#475569')) +
        '<span class="cmp-ret ' + CmpMath.sign(it.pct) + '">' + CmpMath.fmtPct(it.pct) + '</span>' +
        (dayTwice ? '<span class="cmp-day"></span>' : '<span class="cmp-day ' + CmpMath.sign(day) + '">' + CmpMath.fmtPct(day) + '</span>') +
        '</button></li>';
    }).join('');
  }

  function renderStats(model) {
    var box = document.getElementById('cmp-stats');
    if (!box) return;
    var stocks = (model && view === 'lines')
      ? model.models.filter(function (m) { return m.kind !== 'benchmark'; })
      : selectedStocks().map(function (sym) {
          var pct = barMetric === 'day' ? dayPct(sym) : (sym === 'SPCX' ? null : ytdPct(sym));
          return { sym: sym, pct: pct };
        }).filter(function (m) { return CmpMath.isNum(m.pct); });
    var ranked = CmpMath.rankDesc(stocks.filter(function (m) { return CmpMath.isNum(m.pct); }));
    var best = ranked[0], worst = ranked[ranked.length - 1];
    var spread = best && worst ? best.pct - worst.pct : null;
    var up = 0, known = 0;
    STOCKS.forEach(function (sym) {
      var d = dayPct(sym);
      if (!CmpMath.isNum(d)) return;
      known++;
      if (d > 0) up++;
    });
    function cell(k, text, cls) {
      return '<div class="cmp-stat"><span>' + k + '</span><b class="' + (cls || '') + '">' + text + '</b></div>';
    }
    box.innerHTML =
      cell('Best', best ? best.sym + ' ' + CmpMath.fmtPct(best.pct) : '\u2014', best ? CmpMath.sign(best.pct) : '') +
      cell('Worst', worst ? worst.sym + ' ' + CmpMath.fmtPct(worst.pct) : '\u2014', worst ? CmpMath.sign(worst.pct) : '') +
      cell('Spread', spread === null ? '\u2014' : CmpMath.fmtPct(spread).replace('%', ' pp')) +
      cell('Up today', known ? (up + ' of ' + known) : '\u2014');
  }

  function renderNote(model) {
    var note = document.getElementById('cmp-note');
    if (!note) return;
    if (dailyError) {
      note.textContent = 'Daily history did not load. Bars and the heat map still use the cards.';
      return;
    }
    var spcxOut = model && model.excluded.indexOf('SPCX') !== -1;
    var line;
    if (view !== 'lines') {
      line = barMetric === 'ytd'
        ? 'YTD vs 31 Dec 2025. SPCX is since 12 Jun 2026, not YTD. Closes through ' + asOfLabel() + '.'
        : 'Day change vs the prior close. Closes through ' + asOfLabel() + '.';
    } else if (range === 'ytd' && spcxOut) {
      line = 'SPCX is off this YTD view (since 12 Jun 2026, not 31 Dec 2025). Closes through ' + asOfLabel() + '.';
    } else if (range === 'listing') {
      line = 'Every line starts at 0% on 12 Jun 2026, the day SPCX first traded. Closes through ' + asOfLabel() + '.';
    } else if (spcxOut) {
      line = 'SPCX listed 12 Jun 2026, after this window starts, so it is left off. Closes through ' + asOfLabel() + '.';
    } else {
      line = 'Rebased to 0% at the start of this window. Closes through ' + asOfLabel() + '.';
    }
    note.textContent = line;
  }

  function renderSummary(model) {
    var el = document.getElementById('cmp-summary');
    if (!el) return;
    var stocks = model ? model.models.filter(function (m) { return m.kind !== 'benchmark' && CmpMath.isNum(m.pct); }) : [];
    var ranked = CmpMath.rankDesc(stocks);
    if (!ranked.length) {
      el.textContent = 'Comparison chart, as of ' + asOfLabel() + '.';
      return;
    }
    var best = ranked[0], worst = ranked[ranked.length - 1];
    el.textContent = 'Best: ' + best.sym + ' ' + CmpMath.fmtPct(best.pct) + ', worst: ' + worst.sym + ' ' + CmpMath.fmtPct(worst.pct) + ', as of ' + asOfLabel() + '.';
  }

  function renderFail() {
    var fail = document.getElementById('cmp-fail');
    var heat = document.getElementById('cmp-heat');
    if (fail) fail.hidden = !(dailyError && view === 'lines');
    if (heat && view !== 'heat') heat.hidden = true;
  }

  function render() {
    paintChips();
    var metric = document.getElementById('cmp-metric');
    if (metric) metric.hidden = view === 'lines';
    var model = (!dailyError && daily) ? lineModel() : { models: [], excluded: [], target: null };
    if (!hi && view === 'lines' && model.models.length) {
      var ranked0 = CmpMath.rankDesc(model.models.filter(function (m) { return m.kind !== 'benchmark'; }));
      if (ranked0[0]) hi = ranked0[0].sym;
    }
    if (!selectedStocks().length) {
      destroyChart();
      ['cmp-canvas-wrap', 'cmp-heat', 'cmp-tip'].forEach(function (id) { var el = document.getElementById(id); if (el) el.hidden = true; });
      renderStats(model);
      renderNote(model);
      renderSummary(model);
      var board0 = document.getElementById('cmp-board');
      if (board0) board0.innerHTML = '<li class="cmp-fail">Pick at least one stock above to compare.</li>';
      return;
    }
    renderStats(model);
    renderNote(model);
    renderBoard(model);
    renderSummary(model);
    renderFail();
    var canvasLabel = document.getElementById('screener-chart');
    if (view === 'heat') {
      if (canvasLabel) canvasLabel.setAttribute('aria-label', 'Comparison heat map is shown as tiles');
      renderHeat();
    } else if (view === 'bars') {
      var heat = document.getElementById('cmp-heat');
      if (heat) heat.hidden = true;
      if (canvasLabel) canvasLabel.setAttribute('aria-label', (barMetric === 'ytd' ? 'YTD' : 'Day change') + ' comparison bars');
      renderBars();
    } else {
      var heat2 = document.getElementById('cmp-heat');
      if (heat2) heat2.hidden = true;
      if (canvasLabel) canvasLabel.setAttribute('aria-label', 'Rebased performance comparison, ' + asOfLabel());
      if (dailyError || !daily) {
        destroyChart();
        var wrap = document.getElementById('cmp-canvas-wrap');
        if (wrap) wrap.hidden = true;
      } else renderLines(model);
    }
  }

  function paintChips() {
    document.querySelectorAll('[data-cmp-range]').forEach(function (b) {
      var onR = b.getAttribute('data-cmp-range') === range;
      b.classList.toggle('is-on', onR);
      b.setAttribute('aria-pressed', onR ? 'true' : 'false');
    });
    document.querySelectorAll('[data-cmp-symbol]').forEach(function (b) {
      var sym = b.getAttribute('data-cmp-symbol');
      var onS = !!on[sym];
      b.classList.toggle('is-on', onS);
      b.setAttribute('aria-pressed', onS ? 'true' : 'false');
      var dot = b.querySelector('.cmp-dot');
      if (dot) dot.style.background = COLOR[sym] || psC('#94a3b8','#475569');
    });
    document.querySelectorAll('[data-cmp-bench]').forEach(function (b) {
      var sym = b.getAttribute('data-cmp-bench');
      var onB = !!benchOn[sym];
      b.classList.toggle('is-on', onB);
      b.setAttribute('aria-pressed', onB ? 'true' : 'false');
    });
    document.querySelectorAll('[data-cmp-view]').forEach(function (b) {
      var onV = b.getAttribute('data-cmp-view') === view;
      b.classList.toggle('is-on', onV);
      b.setAttribute('aria-selected', onV ? 'true' : 'false');
    });
    document.querySelectorAll('[data-cmp-metric]').forEach(function (b) {
      var onM = b.getAttribute('data-cmp-metric') === barMetric;
      b.classList.toggle('is-on', onM);
      b.setAttribute('aria-pressed', onM ? 'true' : 'false');
    });
  }

  function highlightCard(sym, scroll) {
    var body = document.getElementById('screener-body');
    if (!body) return;
    var found = null;
    body.querySelectorAll('.card').forEach(function (card) {
      card.classList.remove('row-highlight');
      if (card.getAttribute('data-symbol') === sym) found = card;
    });
    if (found && scroll) {
      found.classList.add('row-highlight');
      found.scrollIntoView({ block: 'center', behavior: motionOK() ? 'smooth' : 'auto' });
    } else if (found) found.classList.add('row-highlight');
  }
  function setHighlight(sym, scrollCard) {
    if (!sym) return;
    if (STOCKS.indexOf(sym) !== -1 && !on[sym]) on[sym] = true;
    if (BENCH.indexOf(sym) !== -1) benchOn[sym] = true;
    hi = sym;
    highlightCard(sym, scrollCard);
    render();
  }

  function loadDaily() {
    dailyError = false;
    var fail = document.getElementById('cmp-fail');
    if (fail) fail.hidden = true;
    fetch('assets/data/cmp-daily.json?v=' + CMP_V, { cache: 'no-cache' })
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (doc) {
        if (!doc || !doc.symbols || !doc.symbols.TSLA) throw new Error('bad file');
        daily = doc;
        dailyError = false;
        render();
      })
      .catch(function () {
        daily = null;
        dailyError = true;
        render();
      });
  }

  window.ScreenerChartUpdate = function (next) {
    rows = next || [];
    render();
  };
  window.addEventListener('screener-rows', function (e) {
    rows = (e && e.detail) || [];
    render();
  });

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-cmp-range]').forEach(function (b) {
      b.addEventListener('click', function () { range = b.getAttribute('data-cmp-range'); render(); });
    });
    document.querySelectorAll('[data-cmp-symbol]').forEach(function (b) {
      b.addEventListener('click', function () {
        var sym = b.getAttribute('data-cmp-symbol');
        on[sym] = !on[sym];
        if (!on[sym] && hi === sym) hi = null;
        render();
      });
    });
    document.querySelectorAll('[data-cmp-bench]').forEach(function (b) {
      b.addEventListener('click', function () {
        var sym = b.getAttribute('data-cmp-bench');
        benchOn[sym] = !benchOn[sym];
        render();
      });
    });
    document.querySelectorAll('[data-cmp-view]').forEach(function (b) {
      b.addEventListener('click', function () { view = b.getAttribute('data-cmp-view'); render(); });
    });
    document.querySelectorAll('[data-cmp-metric]').forEach(function (b) {
      b.addEventListener('click', function () { barMetric = b.getAttribute('data-cmp-metric'); render(); });
    });
    var chartCard = document.querySelector('.chart-card');
    if (chartCard) chartCard.addEventListener('click', function (e) {
      var hit = e.target.closest && e.target.closest('[data-cmp-hit]');
      if (!hit) return;
      setHighlight(hit.getAttribute('data-cmp-hit'), true);
    });
    var retry = document.getElementById('cmp-retry');
    if (retry) retry.addEventListener('click', loadDaily);
    // Native canvas hover/click (line view) + redraw on wrap resize.
    // touch-action pan-y keeps vertical page scroll working on touch.
    var cmpCanvas = document.getElementById('screener-chart');
    if (cmpCanvas) {
      cmpCanvas.style.touchAction = 'pan-y';
      cmpCanvas.addEventListener('pointermove', function (e) {
        if (!native || native.kind !== 'lines' || !native.geom) return;
        var r = cmpCanvas.getBoundingClientRect();
        var px = e.clientX - r.left, py = e.clientY - r.top;
        var g = native.geom;
        if (px < g.x0 || px > g.x1 || py < g.y0 || py > g.y1) return;
        var idx = Math.round((px - g.x0) / (g.x1 - g.x0) * (g.n - 1));
        idx = Math.max(0, Math.min(g.n - 1, idx));
        if (native.tipIndex !== idx) {
          native.tipIndex = idx;
          paintNativeLines();
          showTip(native.labels, idx);
        }
      });
      cmpCanvas.addEventListener('pointerleave', function () {
        if (!native || native.kind !== 'lines') return;
        native.tipIndex = null;
        paintNativeLines();
        showTip(native.labels, null);
      });
      cmpCanvas.addEventListener('click', function (e) {
        if (!native || native.kind !== 'lines' || !native.geom || !native.sets) return;
        var r = cmpCanvas.getBoundingClientRect();
        var px = e.clientX - r.left, py = e.clientY - r.top;
        var g = native.geom;
        var idx = Math.round((px - g.x0) / (g.x1 - g.x0) * (g.n - 1));
        idx = Math.max(0, Math.min(g.n - 1, idx));
        var best = null, bestD = 28;
        native.sets.forEach(function (st) {
          var p = st.pts[idx];
          if (!p) return;
          var d = Math.abs(p.y - py);
          if (d < bestD) { bestD = d; best = st.sym; }
        });
        if (best) setTimeout(function () { setHighlight(best, true); }, 0);
      });
    }
    var cmpWrap = document.getElementById('cmp-canvas-wrap');
    if (cmpWrap) {
      if (window.ResizeObserver) {
        var cmpRO = new ResizeObserver(function () {
          if (!native) return;
          render();
        });
        cmpRO.observe(cmpWrap);
      } else {
        window.addEventListener('resize', function () {
          if (!native) return;
          render();
        });
      }
    }
    loadDaily();
    fetchDeskLive();
    var body = document.getElementById('screener-body');
    if (body) body.addEventListener('click', function (e) {
      if (e.target.closest && e.target.closest('.note-btn')) return;
      var card = e.target.closest ? e.target.closest('.card') : null;
      if (!card) return;
      var sym = card.getAttribute('data-symbol');
      if (sym) setHighlight(sym, false);
    });
    loadDaily();
  });
})();
