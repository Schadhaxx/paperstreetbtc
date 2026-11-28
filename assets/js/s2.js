const sleeves = {
  berkshire: { name: 'Berkshire Killer', color: '#22d3ee' },
  hodlr: { name: 'Hodler Jam Sandwich', color: '#38bdf8' },
  hf: { name: 'Hedge Fund Killer', color: '#0ea5e9' },
  saylor: { name: 'Saylor Moon', color: '#67e8f9' }
};

function pathStartYear(iso){
  const d = iso || (window.PSLEDGER && PSLEDGER.base) || '';
  if (!d) return new Date().getFullYear();
  const y = +String(d).slice(0, 4), m = +String(d).slice(5, 7);
  return m === 12 ? y + 1 : y;
}
function setPathYear(iso){
  const el = document.getElementById('pathYear');
  if (el) el.textContent = String(pathStartYear(iso));
}
setPathYear();

// Everything below is computed on page load by PSBook (book.js) from the site's ledger (ledger.js) and its own daily closes (history.json):
// points = January 1st, 2026 start (2025-12-31 close), each completed month-end session close, and the latest close. No stored NAVs.
let labels = [], ISO = [], paths = {}, vals = {}, benchmarks = {}, LASTC = null, BTCPROV = false, BTCFB = null;
/* Vehicle toggle, Day 3: paths are rebuilt from book.js navV when the
   shared 'psvehicle' event fires. Benchmarks stay Spot BTC (the hurdle)
   in every mode; only the sleeve lines are re-priced. */
let BKREF = null, vehicle = 'SPOT', vehLoaded = false;
const BACKUP_LBL = 'Spot BTC (backup close)';
const isBtcFb = (fs, d) => { const base = String((fs[d] && fs[d].BTC) || 'yahoo').split('-')[0]; return base !== 'yahoo' && base !== 'ffill'; };
const PROVNOTE = () => BTCFB ? (' · BTC close ' + BTCFB + ' from backup source until Yahoo\'s final bar') : (BTCPROV ? (' · BTC close provisional until ' + ET.btcCloseLabel(B_LAST)) : '');
let B_LAST = null;
const MN3 = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
function buildFromBook(B){
  ISO = B.points();
  setPathYear(ISO[0] || (window.PSLEDGER && PSLEDGER.base));
  labels = ISO.map((d, i) => i === 0 ? '1 Jan' : (+d.slice(8)) + ' ' + MN3[+d.slice(5, 7) - 1]);
  Object.keys(sleeves).forEach(k => { vals[k] = ISO.map(d => (vehicle !== 'SPOT' && vehLoaded && B.tlV && B.tlV[vehicle]) ? B.navV(k, d, vehicle) : B.nav(k, d)); paths[k] = vals[k].map(v => Math.round(v / 10) / 100);
    sleeves[k].now = vals[k].at(-1); sleeves[k].ytd = (sleeves[k].now / 100000 - 1) * 100; });
  Object.keys(B.BM).forEach(k => { benchmarks[k] = ISO.map(d => Math.round(B.bench(k, d) * 100) / 100); });
  LASTC = B.close(B.last);
  // OI-001: backup-source label keyed on fallback_sources (not time-window alone). Missing entry = Yahoo.
  const fs = B.H.fallback_sources || {};
  const fbDates = Object.keys(fs).filter(d => isBtcFb(fs, d)).sort();
  BTCFB = fbDates.length ? fbDates[fbDates.length - 1] : null;
  B_LAST = B.last;
  const inWin = (B.H.btc_provisional || []).indexOf(B.last) >= 0 && Date.now() < Date.parse(B.last + 'T00:00:00Z') + 864e5 && !isBtcFb(fs, B.last);
  BTCPROV = !!BTCFB || inWin;
  benchNames.btc = BTCFB ? BACKUP_LBL : (inWin ? ('Spot BTC (close provisional until ' + ET.btcCloseLabel(B.last) + ')') : 'Spot BTC');
}
const benchColors = { btc: '#64748b', spy: '#94a3b8', qqq: '#cbd5e1', brk: '#a8a29e', gold: '#d4b06a', mstr: '#f97316' };
const benchNames = { btc: 'Spot BTC', spy: 'SPY', qqq: 'QQQ', brk: 'BRK.B', gold: 'Gold (GLD)', mstr: 'MSTR' };

// Live 'Now' point: benchmark live index = latest-close index x live/close (keeps SPY/QQQ total-return reinvestment already in the series)
// Gold (GLD) = latest-close GLD index x live GLD / GLD close
function closeOf(k){ return LASTC[{ btc: 'BTC', spy: 'SPY', qqq: 'QQQ', brk: 'BRK.B', mstr: 'MSTR', gold: 'GLD' }[k]]; }
let liveNow = null; // { sleeves:{key:$}, bench:{key:index} } or null -> latest close
let meView = null; // month-end mode: { n: points kept from history, extra: optional computed point }
function applyLive(st){
  if(!st || !ISO.length) return;
  meView = null;
  if (st.mode === 'me' && st.me) {
    const i = ISO.indexOf(st.meDate);
    if (i >= 0) meView = { n: i + 1 };
    else { const bench = {}; const m = { btc: 'BTC', spy: 'SPY', qqq: 'QQQ', brk: 'BRK.B', gold: 'GLD', mstr: 'MSTR' };
      Object.keys(benchmarks).forEach(k => { bench[k] = Math.round(benchmarks[k].at(-1) * st.me[m[k]] / closeOf(k) * 100) / 100; });
      const p = st.meDate.split('-'); meView = { n: labels.length, extra: { label: (+p[2]) + ' ' + ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][+p[1]-1], sleeves: st.sleeves, bench } }; }
    liveNow = null;
    const asof = document.getElementById('ytdAsOf'); if (asof) asof.textContent = st.label;
    render();
    return;
  }
  const anyLive = st.btc || st.stocksLive || st.spy || st.qqq || st.brk || st.gold || st.mstr;
  if(!anyLive){ liveNow = null; }
  else {
    const bench = {};
    Object.keys(benchmarks).forEach(k => { const lp = st[k]; const base = benchmarks[k].at(-1);
      bench[k] = lp ? Math.round(base * lp / closeOf(k) * 100) / 100 : base; });
    liveNow = { sleeves: st.sleeves, bench, btcTime: st.btcTime, stkTime: st.stocksLive ? st.stkTime : null };
  }
  const asof = document.getElementById('ytdAsOf');
  if (asof) asof.textContent = (st.label || asof.textContent) + (liveNow ? ' · Live value now. Chart reference points: month-end closes through ' + st.meLabel + '.' : '') + (BTCPROV ? PROVNOTE() : '');
  render();
}
window.addEventListener('pslive', e => applyLive(e.detail));
window.addEventListener('psvehicle', e => {
  vehicle = e.detail.vehicle || 'SPOT'; vehLoaded = !!e.detail.loaded;
  if (!BKREF) return;
  buildFromBook(BKREF); render();
  /* s6 re-renders synchronously on the same event, but its listener was
     registered after s2's, so refresh the live Now/YTD stats on the
     next tick, once PSLive.state() is vehicle-aware. */
  setTimeout(() => { if (window.PSLive) applyLive(window.PSLive.state()); }, 0);
});
function ytdLbl(){ const l = document.getElementById('ytdLbl'); if (l) l.textContent = (liveNow && !meView && window.PSLiveLabel && PSLiveLabel()) ? (window.PSMktOpen && PSMktOpen() ? 'YTD (live)' : 'YTD (BTC live)') : 'YTD'; }

let selected = new Set(['berkshire']);
let currentBench = 'btc';

/* ---- Stage 4: native YTD hero (Stage 2 helpers, copied here with an s2-
   prefix so they cannot collide with btcchart-panel.js, which shares the
   global scope on the homepage). The native chart is the only renderer:
   Chart.js and its fallback were removed on 20 Nov 2026. drawNativeYTD
   returns false on any failure (e.g. a canvas under 40px); the resize /
   visibility redraw below then retries it. ---- */
let nativeDrawn = false; /* true while the native YTD chart is on the canvas */
let s2Hover = -1; /* hovered month index, -1 = none */
var s2KeepHover = false; /* true only during the fonts.ready redraw: the
  tooltip must stay open if fonts finish while it is showing */
let nativeGeom = null; /* {lbls, datasets, xs, plot} of the last native draw */
/* Theme-aware colour helper (same rule as window.psC in index.html /
   compare.js); defined locally so s2.js works standalone in tests. */
var s2C = (typeof psC === 'function') ? psC : function(d, l){
  return document.documentElement.getAttribute('data-theme') === 'light' ? l : d;
};

function s2NiceNum(x){
  /* Chart.js 4 niceNum (from the formerly vendored Chart.js build, function B), copied from
     btcchart-panel.js: round to the nearest integer when within x/1000,
     then a 1/2/5/10 step at the decade below x. */
  var r = Math.round(x);
  if (Math.abs(x - r) < x / 1e3) x = r;
  var p = Math.pow(10, Math.floor(Math.log10(x)));
  var s = x / p;
  return (s <= 1 ? 1 : s <= 2 ? 2 : s <= 5 ? 5 : 10) * p;
}
function s2NiceTicks(min, max, plotH){
  /* Chart.js linear-scale tick generation, replicated exactly (formerly
     vendored Chart.js 4 build), copied from btcchart-panel.js. */
  if (!(max > min)) { max = min + 1; }
  var mt = Math.min(11, Math.ceil((plotH || 320) / 14.4));
  if (mt < 2) mt = 2;
  var g = mt - 1, span = max - min, step = s2NiceNum(span / g);
  var k = Math.ceil(max / step) - Math.floor(min / step);
  if (k > g) step = s2NiceNum(k * step / g);
  var t0 = Math.floor(min / step) * step, t1 = Math.ceil(max / step) * step, out = [];
  for (var v = t0; v <= t1 + step * 0.01; v += step) out.push(Math.round(v * 1000) / 1000);
  return out;
}
function s2TraceLine(ctx, xs, ys, tension, bounds){
  /* Chart.js splineCurve (Catmull-Rom), matching the vendored Chart.js
     _updateBezierControlPoints exactly, copied from btcchart-panel.js
     (nativeTraceLine). Control points are clamped to the plot bounds
     (capBezierPoints, on by default). The caller must have begun the path. */
  var n = xs.length;
  if (n < 1) return;
  ctx.moveTo(xs[0], ys[0]);
  if (n === 1) return;
  if (!tension || n === 2) { for (var i = 1; i < n; i++) ctx.lineTo(xs[i], ys[i]); return; }
  function spline(pX, pY, cX, cY, nX, nY, t){
    var d01 = Math.sqrt(Math.pow(cX - pX, 2) + Math.pow(cY - pY, 2));
    var d12 = Math.sqrt(Math.pow(nX - cX, 2) + Math.pow(nY - cY, 2));
    var s01 = d01 / (d01 + d12), s12 = d12 / (d01 + d12);
    if (isNaN(s01)) s01 = 0;
    if (isNaN(s12)) s12 = 0;
    var fa = t * s01, fb = t * s12;
    return { prev: { x: cX - fa * (nX - pX), y: cY - fa * (nY - pY) },
             next: { x: cX + fb * (nX - pX), y: cY + fb * (nY - pY) } };
  }
  function clamp(v, lo, hi){ return Math.max(Math.min(v, hi), lo); }
  var cp1x = [], cp1y = [], cp2x = [], cp2y = [], j;
  for (j = 0; j < n; j++){
    var p = Math.max(0, j - 1), q = Math.min(n - 1, j + 1);
    var c = spline(xs[p], ys[p], xs[j], ys[j], xs[q], ys[q], tension);
    cp1x[j] = c.prev.x; cp1y[j] = c.prev.y; cp2x[j] = c.next.x; cp2y[j] = c.next.y;
  }
  if (bounds){
    for (j = 0; j < n; j++){
      cp1x[j] = clamp(cp1x[j], bounds.l, bounds.r); cp1y[j] = clamp(cp1y[j], bounds.t, bounds.b);
      cp2x[j] = clamp(cp2x[j], bounds.l, bounds.r); cp2y[j] = clamp(cp2y[j], bounds.t, bounds.b);
    }
  }
  for (var i = 0; i < n - 1; i++){
    ctx.bezierCurveTo(cp2x[i], cp2y[i], cp1x[i + 1], cp1y[i + 1], xs[i + 1], ys[i + 1]);
  }
}
function s2FmtVal(v){
  if (v == null || isNaN(v)) return '—';
  return (+v).toFixed(2).replace(/\.?0+$/, '');
}
function s2RoundRect(ctx, x, y, w, h, r){
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y); ctx.arcTo(x + w, y, x + w, y + r, r);
  ctx.lineTo(x + w, y + h - r); ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
  ctx.lineTo(x + r, y + h); ctx.arcTo(x, y + h, x, y + h - r, r);
  ctx.lineTo(x, y + r); ctx.arcTo(x, y, x + r, y, r);
  ctx.closePath();
}

function drawNativeYTD(lbls, datasets){
  /* Draws the YTD hero natively on #ytdChart, reading the same dataset
     objects render() builds (label, data, borderColor,
     backgroundColor, borderWidth, tension, fill, pointRadius,
     pointHoverRadius, borderDash). Returns true on success, false on any
     failure (a later resize retries it). Grid/tick/legend
     colours match compare.js (dark #1e293b grid, #9aa6bc ticks; light
     rgba(15,23,42,.08) grid, #475569 ticks). The hover tooltip keeps
     compare.js's dark box in both themes, as compare.js does. */
  try{
    var cv = document.getElementById('ytdChart');
    if (!cv || !cv.getContext) return false;
    var ctx = cv.getContext('2d');
    cv.style.display = 'block'; cv.style.width = '100%'; cv.style.height = '100%';
    var dpr = window.devicePixelRatio || 1;
    var W = cv.clientWidth, H = cv.clientHeight;
    if (!(W > 40) || !(H > 40)) return false;
    cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    var FONT = '12px Inter, system-ui, -apple-system, "Segoe UI", sans-serif';
    var TFONT = '11px Inter, system-ui, -apple-system, "Segoe UI", sans-serif';
    var BFONT = '700 12px Inter, system-ui, -apple-system, "Segoe UI", sans-serif';
    /* Grid/tick/legend colours, matching compare.js (dark grid #1e293b,
       light grid rgba(15,23,42,.08); ticks #9aa6bc / #475569). Dark mode
       is unchanged. Note: compare.js's native YGRID is a constant
       rgba(255,255,255,.05) — invisible in light mode — so the hero uses
       compare.js's light x-grid colour for both axes, keeping the grid
       visible but soft. */
    var TICK = s2C('#9aa6bc', '#475569');
    var GRID = s2C('#1e293b', 'rgba(15,23,42,.08)');
    /* data range over all visible series */
    var lo = Infinity, hi = -Infinity;
    datasets.forEach(function(ds){
      ds.data.forEach(function(v){ if (v != null && !isNaN(v)){ if (v < lo) lo = v; if (v > hi) hi = v; } });
    });
    if (!isFinite(lo)) return false;
    /* legend layout (top, the Chart.js default position), wrapping rows.
       A single label wider than the canvas (the long backup-source
       benchmark label at phone width) wraps onto extra lines instead of
       overflowing — the wording is unchanged, only the line breaks. */
    ctx.font = FONT;
    var gap = 16, rowH = 20;
    function s2WrapLabel(text, maxW){
      var words = String(text).split(' '), lines = [], line = '';
      function pushWord(wd){
        /* A single word wider than maxW is split mid-word so it can never
           overflow the box (real labels are fine; only an unbreakable name
           would hit this). Progress is guaranteed: each cut removes at
           least one character. */
        while (wd.length > 1 && ctx.measureText(wd).width > maxW){
          var cut = 1;
          while (cut < wd.length && ctx.measureText(wd.slice(0, cut + 1)).width <= maxW) cut++;
          lines.push(wd.slice(0, cut));
          wd = wd.slice(cut);
        }
        var t = line ? line + ' ' + wd : wd;
        if (line && ctx.measureText(t).width > maxW){ lines.push(line); line = wd; }
        else line = t;
      }
      words.forEach(pushWord);
      if (line) lines.push(line);
      return lines;
    }
    var items = datasets.map(function(ds){
      var lines = s2WrapLabel(ds.label, Math.max(40, W - 16));
      var w = 16;
      lines.forEach(function(ln){ var lw = 16 + ctx.measureText(ln).width; if (lw > w) w = lw; });
      return { ds: ds, lines: lines, w: w, h: lines.length * rowH };
    });
    var rows = [], row = [], rowW = 0, rowHgt = rowH;
    items.forEach(function(it){
      var w = it.w + (row.length ? gap : 0);
      if (row.length && rowW + w > W){ rows.push({ items: row, h: rowHgt }); row = []; rowW = 0; rowHgt = rowH; }
      row.push(it); rowW += (row.length === 1 ? it.w : w);
      if (it.h > rowHgt) rowHgt = it.h;
    });
    if (row.length) rows.push({ items: row, h: rowHgt });
    var legendH = 4 + rows.reduce(function(s, r){ return s + r.h; }, 0) + 6;
    var legInfo = { rows: rows.length, maxLineW: Math.max.apply(null, items.map(function(it){ return it.w; })), canvasW: W };
    /* y ticks (Chart.js nice ticks) */
    var ticks = s2NiceTicks(lo, hi, H - legendH - 18);
    var yTop = ticks[ticks.length - 1], yBot = ticks[0];
    ctx.font = TFONT;
    var yLabW = 0;
    ticks.forEach(function(t){ var w = ctx.measureText(s2FmtVal(t)).width; if (w > yLabW) yLabW = w; });
    var padL = yLabW + 8, padR = 8, padT = legendH, padB = H - 18;
    var plot = { l: padL, r: W - padR, t: padT, b: padB };
    var toY = function(v){ return padT + (1 - (v - yBot) / (yTop - yBot)) * (padB - padT); };
    var n = lbls.length;
    var xs = [];
    for (var i = 0; i < n; i++) xs.push(padL + (n === 1 ? 0.5 : i / (n - 1)) * (W - padL - padR));
    /* legend */
    ctx.font = FONT; ctx.textBaseline = 'middle'; ctx.textAlign = 'left';
    var legY = 4;
    rows.forEach(function(rw){
      var x = 0;
      rw.items.forEach(function(it){
        var ds = it.ds;
        var cy = legY + rowH / 2;
        ctx.strokeStyle = ds.borderColor; ctx.lineWidth = ds.borderWidth || 2;
        ctx.setLineDash(ds.borderDash || []);
        ctx.beginPath(); ctx.moveTo(x, cy); ctx.lineTo(x + 12, cy); ctx.stroke();
        ctx.setLineDash([]);
        if (!ds.borderDash){
          ctx.beginPath(); ctx.arc(x + 6, cy, 3, 0, Math.PI * 2);
          ctx.fillStyle = ds.borderColor; ctx.fill();
        }
        ctx.fillStyle = TICK;
        it.lines.forEach(function(ln, li){
          ctx.fillText(ln, x + 16, legY + li * rowH + rowH / 2);
        });
        x += it.w + gap;
      });
      legY += rw.h;
    });
    /* y gridlines + labels */
    ctx.font = TFONT;
    ticks.forEach(function(t){
      var y = toY(t);
      ctx.strokeStyle = GRID; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(W - padR, y); ctx.stroke();
      ctx.fillStyle = TICK; ctx.textAlign = 'right';
      ctx.fillText(s2FmtVal(t), padL - 6, y);
    });
    ctx.textAlign = 'left';
    /* x gridlines + labels (auto-skip so labels never overlap) */
    var maxLW = 0;
    lbls.forEach(function(l){ var w = ctx.measureText(l).width; if (w > maxLW) maxLW = w; });
    var maxShown = Math.max(1, Math.floor((W - padL - padR) / (maxLW + 10)));
    var step = Math.max(1, Math.ceil(n / maxShown));
    ctx.textAlign = 'center'; ctx.textBaseline = 'alphabetic';
    for (var xi = 0; xi < n; xi++){
      if (xi % step !== 0) continue;
      ctx.strokeStyle = GRID; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(xs[xi], padT); ctx.lineTo(xs[xi], padB); ctx.stroke();
      ctx.fillStyle = TICK;
      ctx.fillText(lbls[xi], xs[xi], H - 5);
    }
    ctx.textAlign = 'left';
    /* series */
    var ysByDs = datasets.map(function(ds){
      return ds.data.map(function(v){ return (v == null || isNaN(v)) ? null : toY(v); });
    });
    datasets.forEach(function(ds, di){
      var ys = ysByDs[di];
      var px = [], py = [];
      for (var j = 0; j < n; j++){ if (ys[j] != null){ px.push(xs[j]); py.push(ys[j]); } }
      if (!px.length) return;
      if (ds.fill && ds.backgroundColor && px.length > 1){
        ctx.beginPath();
        s2TraceLine(ctx, px, py, ds.tension || 0, plot);
        ctx.lineTo(px[px.length - 1], padB); ctx.lineTo(px[0], padB); ctx.closePath();
        ctx.fillStyle = ds.backgroundColor; ctx.fill();
      }
      ctx.beginPath();
      s2TraceLine(ctx, px, py, ds.tension || 0, plot);
      ctx.strokeStyle = ds.borderColor; ctx.lineWidth = ds.borderWidth || 2;
      ctx.setLineDash(ds.borderDash || []); ctx.lineJoin = 'round'; ctx.lineCap = 'round';
      ctx.stroke(); ctx.setLineDash([]);
      if (ds.pointRadius){
        for (var k = 0; k < n; k++){
          if (ys[k] == null) continue;
          ctx.beginPath(); ctx.arc(xs[k], ys[k], ds.pointRadius, 0, Math.PI * 2);
          ctx.fillStyle = ds.borderColor; ctx.fill();
        }
      }
    });
    /* hover (index mode): guide line + enlarged points + one tooltip with
       every visible line at that month, like Chart.js interaction
       mode 'index', intersect false. */
    var tipInfo = null;
    if (s2Hover >= 0 && s2Hover < n){
      var hx = xs[s2Hover];
      ctx.strokeStyle = 'rgba(148,163,184,.35)'; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(hx, padT); ctx.lineTo(hx, padB); ctx.stroke();
      var topY = Infinity, botY = -Infinity;
      datasets.forEach(function(ds, di){
        var y = ysByDs[di][s2Hover];
        if (y == null) return;
        if (y < topY) topY = y; if (y > botY) botY = y;
        if (ds.pointRadius){
          ctx.beginPath(); ctx.arc(hx, y, ds.pointHoverRadius || 5, 0, Math.PI * 2);
          ctx.fillStyle = ds.borderColor; ctx.fill();
          ctx.beginPath(); ctx.arc(hx, y, (ds.pointHoverRadius || 5) + 1.5, 0, Math.PI * 2);
          ctx.strokeStyle = 'rgba(7,11,24,.9)'; ctx.lineWidth = 1.5; ctx.stroke();
        }
      });
      var title = lbls[s2Hover];
      var trows = datasets.map(function(ds){
        return { c: ds.borderColor, n: ds.label, v: s2FmtVal(ds.data[s2Hover]) };
      });
      ctx.font = BFONT;
      var tw = ctx.measureText(title).width;
      ctx.font = FONT;
      /* Tooltip width is capped at the plot area (not the canvas): a long
         series label (the backup-source benchmark label at phone width)
         wraps onto extra lines instead of pushing the box past the canvas
         edge and clipping. The box also starts at or right of the plot's
         left edge (padL), so it never covers the y-axis numbers. The
         value stays right-aligned on the first line; continuation lines
         are label-only. */
      var maxTw = Math.max(40, W - padL - 4);
      var rowH = 17;
      trows.forEach(function(r){
        r.vw = ctx.measureText(r.v).width;
        var w = 10 + 4 + ctx.measureText(r.n).width + 8 + r.vw;
        if (w > tw) tw = w;
      });
      tw += 20;
      if (tw > maxTw){
        tw = maxTw;
        trows.forEach(function(r){
          r.lines = s2WrapLabel(r.n, Math.max(20, tw - 24 - 10 - 8 - r.vw));
        });
      } else {
        trows.forEach(function(r){ r.lines = [r.n]; });
      }
      var th = 8 + 15 + 4 + trows.reduce(function(s, r){ return s + r.lines.length * rowH; }, 0) + 8;
      var tx = hx + 12;
      if (hx > padL + (W - padL - padR) * 0.6) tx = hx - 12 - tw;
      tx = Math.max(padL, Math.min(tx, W - tw - 4));
      var ty = topY - th - 10;
      if (ty < padT) ty = Math.min(botY + 12, H - th - 4);
      ty = Math.max(4, ty);
      tipInfo = { x: tx, y: ty, w: tw, h: th, rows: trows.length, plotL: padL };
      s2RoundRect(ctx, tx, ty, tw, th, 8);
      /* Fully opaque fill: at phone width the box spans almost the whole
         plot, and the old .94 alpha let the y-axis numbers bleed through. */
      ctx.fillStyle = 'rgba(7,11,24,1)'; ctx.fill();
      ctx.strokeStyle = 'rgba(148,163,184,.35)'; ctx.lineWidth = 1; ctx.stroke();
      ctx.font = BFONT; ctx.fillStyle = '#e8eef7'; ctx.textBaseline = 'middle';
      ctx.fillText(title, tx + 10, ty + 8 + 7);
      ctx.font = FONT;
      var ry = ty + 8 + 15 + 4 + 8;
      trows.forEach(function(r){
        ctx.fillStyle = r.c;
        ctx.fillRect(tx + 10, ry - 4, 10, 8);
        ctx.fillStyle = '#9aa6bc';
        r.lines.forEach(function(ln, li){
          ctx.fillText(ln, tx + 24, ry + li * rowH);
        });
        ctx.fillStyle = '#e8eef7'; ctx.textAlign = 'right';
        ctx.fillText(r.v, tx + tw - 10, ry);
        ctx.textAlign = 'left';
        ry += r.lines.length * rowH;
      });
      ctx.textBaseline = 'alphabetic';
    }
    nativeGeom = { lbls: lbls, datasets: datasets, xs: xs, plot: plot };
    window.__S2_NATIVE_LEGEND = legInfo;
    window.__S2_NATIVE_LAYOUT = { labels: lbls.slice(), series: datasets.map(function(ds){ return ds.label; }), points: n, hover: s2Hover };
    window.__S2_NATIVE_HOVER = s2Hover;
    window.__S2_NATIVE_TOOLTIP = tipInfo;
    return true;
  }catch (e){ return false; }
}

function s2NearestIndex(e){
  if (!nativeGeom) return -1;
  var cv = document.getElementById('ytdChart');
  var r = cv.getBoundingClientRect();
  var x = ((e.touches && e.touches[0] ? e.touches[0].clientX : e.clientX) - r.left);
  var xs = nativeGeom.xs, best = 0, bd = Infinity;
  for (var i = 0; i < xs.length; i++){
    var d = Math.abs(xs[i] - x);
    if (d < bd){ bd = d; best = i; }
  }
  return best;
}
function s2SetHover(idx){
  if (!nativeDrawn || !nativeGeom) return;
  if (idx !== s2Hover){
    s2Hover = idx;
    drawNativeYTD(nativeGeom.lbls, nativeGeom.datasets);
    window.__S2_NATIVE_HOVER = s2Hover;
  }
}
(function s2WireHover(){
  var cv = document.getElementById('ytdChart');
  if (!cv) return;
  cv.addEventListener('mousemove', function(e){ s2SetHover(s2NearestIndex(e)); });
  cv.addEventListener('mouseleave', function(){ s2SetHover(-1); });
  cv.addEventListener('touchstart', function(e){ s2SetHover(s2NearestIndex(e)); }, { passive: true });
  cv.addEventListener('touchmove', function(e){ s2SetHover(s2NearestIndex(e)); }, { passive: true });
  cv.addEventListener('touchend', function(){
    setTimeout(function(){ s2SetHover(-1); }, 1000);
  }, { passive: true });
})();

/* Resize: coalesced via requestAnimationFrame (the Stage 2 nativeResize
   pattern — iOS fires many resize events while the toolbar collapses).
   Re-rendering is idempotent (stats/buttons recompute identically).
   The redraw is NOT gated on a previous successful draw: if the first
   draw failed because the canvas was under 40px (hidden tab, collapsed
   layout), a later resize or the tab becoming visible retries the native
   draw instead of staying blank until a click. */
var s2Raf = 0;
function s2Resize(){
  if (s2Raf) return;
  var f = function(){ s2Raf = 0; render(); };
  s2Raf = window.requestAnimationFrame ? window.requestAnimationFrame(f) : setTimeout(f, 16);
}
window.addEventListener('resize', s2Resize);
document.addEventListener('visibilitychange', function(){ if (!document.hidden) s2Resize(); });
try{
  if (window.ResizeObserver){
    var _cv = document.getElementById('ytdChart');
    if (_cv && _cv.parentElement) new ResizeObserver(s2Resize).observe(_cv.parentElement);
  }
}catch (e){}

function render() {
  if (!ISO.length) return;
  // Stats from first selected sleeve
  const first = [...selected][0];
  const s0 = sleeves[first];
  let nowV = liveNow ? liveNow.sleeves[first] : s0.now;
  if (meView) nowV = meView.extra ? meView.extra.sleeves[first] : vals[first][meView.n - 1];
  const s = { now: nowV, ytd: (nowV / 100000 - 100 / 100) * 100 };
  if (!liveNow && !meView) s.ytd = s0.ytd;
  document.getElementById('stat-start').textContent = '$100,000';
  document.getElementById('stat-now').textContent = '$' + Math.round(s.now).toLocaleString('en-US');
  const ytdEl = document.getElementById('stat-ytd');
  ytdEl.textContent = (s.ytd >= 0 ? '+' : '') + s.ytd.toFixed(2) + '%';
  ytdEl.className = 'stat-value ' + (s.ytd >= 0 ? 'pos' : 'neg');

  const ser = (arr, liveV) => meView ? (meView.extra ? arr.concat([liveV]) : arr.slice(0, meView.n)) : (liveNow ? arr.concat([liveV]) : arr);
  const benchEnd = ser(benchmarks[currentBench], meView ? (meView.extra && meView.extra.bench[currentBench]) : (liveNow && liveNow.bench[currentBench])).at(-1);
  const vs = s.ytd - (benchEnd - 100); // YTD difference vs benchmark, percentage points
  const vsEl = document.getElementById('stat-vs');
  vsEl.textContent = (vs >= 0 ? '+' : '') + vs.toFixed(2) + ' pp';
  vsEl.className = 'stat-value ' + (vs >= 0 ? 'pos' : 'neg');

  document.querySelectorAll('.sleeve-btn').forEach(b => {
    b.classList.toggle('active', selected.has(b.dataset.sleeve));
  });
  document.querySelectorAll('.bench-selector .bench-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.bench === currentBench);
  });

  const datasets = [];
  selected.forEach(key => {
    datasets.push({
      label: sleeves[key].name,
      data: ser(paths[key], meView ? (meView.extra && Math.round(meView.extra.sleeves[key] / 10) / 100) : (liveNow && Math.round(liveNow.sleeves[key] / 10) / 100)),
      borderColor: sleeves[key].color,
      backgroundColor: sleeves[key].color + '18',
      borderWidth: 2.5,
      tension: 0.3,
      fill: selected.size === 1,
      pointRadius: 3,
      pointHoverRadius: 5
    });
  });
  datasets.push({
    label: benchNames[currentBench],
    data: ser(benchmarks[currentBench], meView ? (meView.extra && meView.extra.bench[currentBench]) : (liveNow && liveNow.bench[currentBench])),
    borderColor: benchColors[currentBench],
    borderWidth: 1.5,
    borderDash: [5, 4],
    tension: 0.25,
    fill: false,
    pointRadius: 0
  });

  const lbls = meView ? (meView.extra ? labels.concat([meView.extra.label]) : labels.slice(0, meView.n)) : (liveNow ? labels.concat(['Now']) : labels.slice());
  ytdLbl();
  /* Native only (Chart.js removed 20 Nov 2026). A failed draw (canvas
     under 40px, hidden tab) leaves nativeDrawn false; s2Resize retries. */
  if (!s2KeepHover) s2Hover = -1;
  nativeDrawn = !!drawNativeYTD(lbls, datasets);
  window.__S2_NATIVE_DRAWN = nativeDrawn;
}

document.querySelectorAll('.sleeve-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const key = btn.dataset.sleeve;
    if (selected.has(key) && selected.size > 1) selected.delete(key);
    else selected.add(key);
    render();
  });
});

document.querySelectorAll('.bench-selector .bench-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    currentBench = btn.dataset.bench;
    render();
  });
});

if (window.PSBook) PSBook.ready.then(B => { BKREF = B; buildFromBook(B); render(); if (window.PSLive) applyLive(window.PSLive.state()); }).catch(() => {});

/* Webfont: the first draw can measure labels in the fallback font if Inter
   has not finished loading yet. Redraw once the document fonts are ready
   so text is measured (and wrapped) in the right font. Fires once;
   render() is idempotent and returns early before the book loads, so this
   is safe at any time. Browsers without document.fonts skip it. */
try{
  if (document.fonts && document.fonts.ready && typeof document.fonts.ready.then === 'function'){
    document.fonts.ready.then(function(){
      window.__S2_FONTS_REDRAW = true;
      /* Keep an open tooltip open: render() normally clears the hover
         (the dataset may have changed), but the fonts redraw re-measures
         the same data, so preserve it for this one redraw only. */
      s2KeepHover = true;
      render();
      s2KeepHover = false;
    }).catch(function(){});
  }
}catch (e){}
