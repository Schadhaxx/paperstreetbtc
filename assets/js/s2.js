const sleeves = {
  berkshire: { name: 'Berkshire Killer', color: '#22d3ee' },
  hodlr: { name: 'Hodler Jam Sandwich', color: '#38bdf8' },
  hf: { name: 'Hedge Fund Killer', color: '#0ea5e9' },
  saylor: { name: 'Saylor Moon', color: '#67e8f9' }
};

// Everything below is computed on page load by PSBook (book.js) from the site's ledger (ledger.js) and its own daily closes (history.json):
// points = January 1st, 2026 start (2025-12-31 close), each completed month-end session close, and the latest close. No stored NAVs.
let labels = [], ISO = [], paths = {}, vals = {}, benchmarks = {}, LASTC = null, BTCPROV = false, BTCFB = null;
/* Vehicle toggle, Day 3: paths are rebuilt from book.js navV when the
   shared 'psvehicle' event fires. Benchmarks stay Spot BTC (the hurdle)
   in every mode; only the sleeve lines are re-priced. */
let BKREF = null, vehicle = 'SPOT', vehLoaded = false;
const BACKUP_LBL = 'Spot BTC (close from backup source until Yahoo\'s final bar)';
const isBtcFb = (fs, d) => { const base = String((fs[d] && fs[d].BTC) || 'yahoo').split('-')[0]; return base !== 'yahoo' && base !== 'ffill'; };
const PROVNOTE = () => BTCFB ? (' · BTC close ' + BTCFB + ' from backup source until Yahoo\'s final bar') : (BTCPROV ? (' · BTC close provisional until ' + ET.btcCloseLabel(B_LAST)) : '');
let B_LAST = null;
const MN3 = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
function buildFromBook(B){
  ISO = B.points();
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
    if (chartReady) render();
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
  if (chartReady) render();
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
let chartReady = false;
let _series = null; // {labels, datasets} last drawn — for hover + parity export
let _hover = -1;

/* Native canvas YTD line (Option 2): same series math as before; no Chart.js. */
function niceTicks(min, max, n){
  if (!(max > min)) { max = min + 1; }
  const span = max - min;
  const step0 = span / Math.max(1, n);
  const pow = Math.pow(10, Math.floor(Math.log10(step0)));
  const err = step0 / pow;
  const step = pow * (err >= 5 ? 5 : err >= 2 ? 2 : 1);
  const t0 = Math.floor(min / step) * step;
  const out = [];
  for (let v = t0; v <= max + step * 0.01; v += step) out.push(Math.round(v * 1000) / 1000);
  return out;
}
function drawNative(){
  const canvas = document.getElementById('ytdChart');
  if (!canvas || !_series) return;
  const wrap = canvas.parentElement || canvas;
  const cssW = Math.max(280, wrap.clientWidth || canvas.clientWidth || 600);
  const cssH = Math.max(180, +(canvas.getAttribute('height') || 220));
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.round(cssW * dpr);
  canvas.height = Math.round(cssH * dpr);
  canvas.style.width = cssW + 'px';
  canvas.style.height = cssH + 'px';
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const W = cssW, H = cssH;
  const pad = { l: 44, r: 12, t: 28, b: 28 };
  const plotW = W - pad.l - pad.r, plotH = H - pad.t - pad.b;
  const lbls = _series.labels, datasets = _series.datasets;
  let lo = Infinity, hi = -Infinity;
  datasets.forEach(ds => ds.data.forEach(v => { if (typeof v === 'number' && isFinite(v)) { if (v < lo) lo = v; if (v > hi) hi = v; } }));
  if (!isFinite(lo)) { lo = 90; hi = 110; }
  const padY = (hi - lo) * 0.08 || 1;
  lo -= padY; hi += padY;
  const yTicks = niceTicks(lo, hi, 4);
  lo = Math.min(lo, yTicks[0]); hi = Math.max(hi, yTicks[yTicks.length - 1]);
  const n = Math.max(1, lbls.length - 1);
  const xAt = i => pad.l + (n === 0 ? plotW / 2 : (i / n) * plotW);
  const yAt = v => pad.t + (1 - (v - lo) / (hi - lo)) * plotH;

  ctx.clearRect(0, 0, W, H);
  // grid + y labels
  ctx.strokeStyle = '#1e293b'; ctx.fillStyle = '#9aa6bc'; ctx.lineWidth = 1;
  ctx.font = '11px system-ui,Segoe UI,sans-serif';
  yTicks.forEach(v => {
    const y = yAt(v);
    ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(pad.l + plotW, y); ctx.stroke();
    ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
    ctx.fillText(String(v), pad.l - 6, y);
  });
  // x labels (first, mids, last)
  const xIdx = [];
  if (lbls.length <= 8) { for (let i = 0; i < lbls.length; i++) xIdx.push(i); }
  else {
    xIdx.push(0);
    const mid = Math.max(1, Math.floor((lbls.length - 1) / 4));
    for (let i = mid; i < lbls.length - 1; i += mid) xIdx.push(i);
    xIdx.push(lbls.length - 1);
  }
  ctx.textAlign = 'center'; ctx.textBaseline = 'top';
  xIdx.forEach(i => { ctx.fillText(lbls[i], xAt(i), pad.t + plotH + 6); });

  // series: fill first (single sleeve), then lines
  datasets.forEach(ds => {
    if (!ds.fill || ds.data.length < 2) return;
    ctx.beginPath();
    ds.data.forEach((v, i) => { const x = xAt(i), y = yAt(v); if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); });
    ctx.lineTo(xAt(ds.data.length - 1), pad.t + plotH);
    ctx.lineTo(xAt(0), pad.t + plotH);
    ctx.closePath();
    ctx.fillStyle = ds.backgroundColor || (ds.borderColor + '18');
    ctx.fill();
  });
  datasets.forEach(ds => {
    ctx.beginPath();
    ds.data.forEach((v, i) => { const x = xAt(i), y = yAt(v); if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); });
    ctx.strokeStyle = ds.borderColor;
    ctx.lineWidth = ds.borderWidth || 2;
    if (ds.borderDash) ctx.setLineDash(ds.borderDash); else ctx.setLineDash([]);
    ctx.stroke();
    ctx.setLineDash([]);
    if (ds.pointRadius) {
      ds.data.forEach((v, i) => {
        ctx.beginPath();
        ctx.arc(xAt(i), yAt(v), ds.pointRadius, 0, Math.PI * 2);
        ctx.fillStyle = ds.borderColor;
        ctx.fill();
      });
    }
  });

  // legend (top)
  let lx = pad.l, ly = 8;
  ctx.font = '11px system-ui,Segoe UI,sans-serif';
  ctx.textBaseline = 'middle';
  datasets.forEach(ds => {
    ctx.fillStyle = ds.borderColor;
    ctx.fillRect(lx, ly - 4, 12, 8);
    if (ds.borderDash) {
      ctx.strokeStyle = ds.borderColor; ctx.lineWidth = 1.5; ctx.setLineDash([3, 2]);
      ctx.beginPath(); ctx.moveTo(lx, ly); ctx.lineTo(lx + 12, ly); ctx.stroke(); ctx.setLineDash([]);
    }
    ctx.fillStyle = '#9aa6bc';
    ctx.textAlign = 'left';
    const lab = ds.label.length > 42 ? ds.label.slice(0, 40) + '…' : ds.label;
    ctx.fillText(lab, lx + 16, ly);
    lx += 16 + ctx.measureText(lab).width + 14;
  });

  // hover crosshair + tooltip
  if (_hover >= 0 && _hover < lbls.length) {
    const x = xAt(_hover);
    ctx.strokeStyle = 'rgba(148,163,184,.45)'; ctx.lineWidth = 1; ctx.setLineDash([3, 3]);
    ctx.beginPath(); ctx.moveTo(x, pad.t); ctx.lineTo(x, pad.t + plotH); ctx.stroke(); ctx.setLineDash([]);
    const tip = [lbls[_hover]].concat(datasets.map(ds => {
      const v = ds.data[_hover];
      return ds.label + ': ' + (typeof v === 'number' ? v.toFixed(2) : '—');
    }));
    ctx.font = '11px system-ui,Segoe UI,sans-serif';
    const tw = Math.max(...tip.map(t => ctx.measureText(t).width)) + 16;
    const th = tip.length * 14 + 10;
    let tx = x + 10, ty = pad.t + 8;
    if (tx + tw > W - 4) tx = x - tw - 10;
    if (tx < 4) tx = 4;
    ctx.fillStyle = 'rgba(15,23,42,.92)';
    ctx.strokeStyle = '#334155';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.rect(tx, ty, tw, th);
    ctx.fill(); ctx.stroke();
    ctx.fillStyle = '#e2e8f0'; ctx.textAlign = 'left'; ctx.textBaseline = 'top';
    tip.forEach((t, i) => ctx.fillText(t, tx + 8, ty + 6 + i * 14));
    datasets.forEach(ds => {
      const v = ds.data[_hover];
      if (typeof v !== 'number') return;
      ctx.beginPath();
      ctx.arc(x, yAt(v), 4, 0, Math.PI * 2);
      ctx.fillStyle = ds.borderColor;
      ctx.fill();
    });
  }

  // expose geometry for hit-testing
  canvas._ytdHit = { pad, plotW, n: lbls.length, xAt };
}
function bindHover(){
  const canvas = document.getElementById('ytdChart');
  if (!canvas || canvas._ytdBound) return;
  canvas._ytdBound = true;
  const hit = ev => {
    const h = canvas._ytdHit; if (!h || h.n < 1) return -1;
    const r = canvas.getBoundingClientRect();
    const x = (ev.clientX - r.left);
    if (x < h.pad.l || x > h.pad.l + h.plotW) return -1;
    const t = (x - h.pad.l) / h.plotW;
    return Math.max(0, Math.min(h.n - 1, Math.round(t * Math.max(1, h.n - 1))));
  };
  canvas.addEventListener('mousemove', ev => {
    const i = hit(ev);
    if (i !== _hover) { _hover = i; drawNative(); }
  });
  canvas.addEventListener('mouseleave', () => { if (_hover !== -1) { _hover = -1; drawNative(); } });
  window.addEventListener('resize', () => { if (_series) drawNative(); });
}

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
      fill: selected.size === 1,
      pointRadius: 3
    });
  });
  datasets.push({
    label: benchNames[currentBench],
    data: ser(benchmarks[currentBench], meView ? (meView.extra && meView.extra.bench[currentBench]) : (liveNow && liveNow.bench[currentBench])),
    borderColor: benchColors[currentBench],
    borderWidth: 1.5,
    borderDash: [5, 4],
    fill: false,
    pointRadius: 0
  });

  const lbls = meView ? (meView.extra ? labels.concat([meView.extra.label]) : labels.slice(0, meView.n)) : (liveNow ? labels.concat(['Now']) : labels.slice());
  ytdLbl();
  _series = { labels: lbls, datasets };
  // Parity/debug hook (same numbers Chart.js used to plot)
  window.__YTD_SERIES = { labels: lbls.slice(), datasets: datasets.map(d => ({ label: d.label, data: d.data.slice() })) };
  window.__YTD_STATS = { now: s.now, ytd: s.ytd, vs: vs, sleeve: first, bench: currentBench };
  chartReady = true;
  bindHover();
  drawNative();
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
