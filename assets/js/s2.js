const sleeves = {
  berkshire: { name: 'Berkshire Killer', color: '#22d3ee' },
  hodlr: { name: 'Hodler Jam Sandwich', color: '#38bdf8' },
  hf: { name: 'Hedge Fund Killer', color: '#0ea5e9' },
  saylor: { name: 'Saylor Moon', color: '#67e8f9' }
};

// Everything below is computed on page load by PSBook (book.js) from the site's ledger (ledger.js) and its own daily closes (history.json):
// points = January 1st, 2026 start (2025-12-31 close), each completed month-end session close, and the latest close. No stored NAVs.
let labels = [], ISO = [], paths = {}, vals = {}, benchmarks = {}, LASTC = null, LASTSPOT = null;
const MN3 = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
function buildFromBook(B){
  ISO = B.points();
  labels = ISO.map((d, i) => i === 0 ? '1 Jan' : (+d.slice(8)) + ' ' + MN3[+d.slice(5, 7) - 1]);
  Object.keys(sleeves).forEach(k => { vals[k] = ISO.map(d => B.nav(k, d)); paths[k] = vals[k].map(v => Math.round(v / 10) / 100);
    sleeves[k].now = vals[k].at(-1); sleeves[k].ytd = (sleeves[k].now / 100000 - 1) * 100; });
  Object.keys(B.BM).forEach(k => { benchmarks[k] = ISO.map(d => Math.round(B.bench(k, d) * 100) / 100); });
  LASTC = B.close(B.last); LASTSPOT = B.goldSpot(B.last);
}
const benchColors = { btc: '#64748b', spy: '#94a3b8', qqq: '#cbd5e1', brk: '#a8a29e', gold: '#d4b06a', mstr: '#f97316' };
const benchNames = { btc: 'Spot BTC', spy: 'SPY', qqq: 'QQQ', brk: 'BRK.B', gold: 'Gold (spot)', mstr: 'MSTR' };

// Live 'Now' point: benchmark live index = latest-close index x live/close (keeps SPY/QQQ total-return reinvestment already in the series)
// Gold (spot) = latest-close gold index x live spot / spot at that close (GLD oz/share method)
function closeOf(k){ return k === 'gold' ? LASTSPOT : LASTC[{ btc: 'BTC', spy: 'SPY', qqq: 'QQQ', brk: 'BRK.B', mstr: 'MSTR' }[k]]; }
let liveNow = null; // { sleeves:{key:$}, bench:{key:index} } or null -> latest close
function hhmm(d){return ('0'+d.getHours()).slice(-2)+':'+('0'+d.getMinutes()).slice(-2);}
let meView = null; // month-end mode: { n: points kept from history, extra: optional computed point }
function applyLive(st){
  if(!st || !ISO.length) return;
  meView = null;
  if (st.mode === 'me' && st.me) {
    const i = ISO.indexOf(st.meDate);
    if (i >= 0) meView = { n: i + 1 };
    else { const bench = {}; const m = { btc: 'BTC', spy: 'SPY', qqq: 'QQQ', brk: 'BRK.B', gold: 'GOLD', mstr: 'MSTR' };
      Object.keys(benchmarks).forEach(k => { bench[k] = Math.round(benchmarks[k].at(-1) * st.me[m[k]] / closeOf(k) * 100) / 100; });
      const p = st.meDate.split('-'); meView = { n: labels.length, extra: { label: (+p[2]) + ' ' + ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][+p[1]-1], sleeves: st.sleeves, bench } }; }
    liveNow = null;
    const asof = document.getElementById('ytdAsOf'); if (asof) asof.textContent = st.label;
    if (chart) render();
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
  if (asof) asof.textContent = (st.label || asof.textContent) + (liveNow ? ' (history: month-end closes through ' + st.meLabel + ', plus the ' + labels.at(-1) + ' close)' : '');
  if (chart) render();
}
window.addEventListener('pslive', e => applyLive(e.detail));

let selected = new Set(['berkshire']);
let currentBench = 'btc';
let chart;

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
  if (chart) { chart.data.labels = lbls; chart.data.datasets = datasets; chart.update('none'); return; }
  if (typeof Chart === 'undefined') return;
  const ctx = document.getElementById('ytdChart').getContext('2d');
  chart = new Chart(ctx, {
    type: 'line',
    data: { labels: lbls, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: true, labels: { color: '#9aa6bc', boxWidth: 12 } } },
      scales: {
        x: { grid: { color: '#1e293b' }, ticks: { color: '#9aa6bc' } },
        y: { grid: { color: '#1e293b' }, ticks: { color: '#9aa6bc', callback: v => v } }
      },
      interaction: { mode: 'index', intersect: false }
    }
  });
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

if (window.PSBook) PSBook.ready.then(B => { buildFromBook(B); render(); if (window.PSLive) applyLive(window.PSLive.state()); }).catch(() => {});
