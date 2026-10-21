const sleeves = {
  berkshire: { name: 'Berkshire Killer', now: 95130.95, ytd: -4.8691, color: '#22d3ee' },
  hodlr: { name: 'Hodler Jam Sandwich', now: 94527.28, ytd: -5.4727, color: '#38bdf8' },
  hf: { name: 'Hedge Fund Killer', now: 93886.04, ytd: -6.1140, color: '#0ea5e9' },
  saylor: { name: 'Saylor Moon', now: 100006.74, ytd: 0.0067, color: '#67e8f9' }
};

// Real Paperstreet model NAV (index, $100k start = 100) at January 1st, 2026, each month-end close, and 19 Oct 2026 close. Source: daily_nav.csv
const labels = ["1 Jan", "30 Jan", "27 Feb", "31 Mar", "30 Apr", "29 May", "30 Jun", "31 Jul", "31 Aug", "30 Sep", "19 Oct"];
const paths = {
  berkshire: [100.0, 95.64, 85.27, 85.01, 89.16, 92.42, 79.63, 75.84, 92.46, 94.69, 95.13],
  hodlr: [100.0, 97.11, 80.04, 81.4, 93.31, 90.13, 67.41, 72.25, 91.09, 98.14, 94.53],
  hf: [100.0, 97.47, 81.53, 82.02, 96.59, 93.29, 65.9, 70.64, 90.74, 98.95, 93.89],
  saylor: [100.0, 99.83, 94.13, 93.02, 107.17, 105.09, 73.74, 78.8, 97.41, 106.38, 100.01]
};
const benchmarks = {
  btc: [100.0, 96.14, 75.29, 77.97, 87.2, 83.85, 66.92, 71.78, 89.76, 95.48, 93.59],
  spy: [100.0, 101.47, 100.6, 95.63, 105.68, 111.24, 110.09, 110.13, 113.08, 112.71, 113.28],
  qqq: [100.0, 101.23, 98.86, 94.07, 108.83, 120.34, 120.16, 112.26, 116.95, 120.83, 117.33]
};
const benchColors = { btc: '#64748b', spy: '#94a3b8', qqq: '#cbd5e1' };
const benchNames = { btc: 'Spot BTC', spy: 'SPY', qqq: 'QQQ' };

// Live 'Now' point: 19 Oct close prices; benchmark live index = 19 Oct index x live/close (keeps SPY/QQQ total-return dividends already in the series)
const CLOSE1019 = { btc: 81901.5625, spy: 766.48, qqq: 718.36 };
const START1231 = { btc: 87508.8281, spy: 681.92, qqq: 614.31 };
let liveNow = null; // { sleeves:{key:$}, bench:{key:index} } or null -> static 19 Oct
function hhmm(d){return ('0'+d.getHours()).slice(-2)+':'+('0'+d.getMinutes()).slice(-2);}
function applyLive(st){
  if(!st) return;
  const anyLive = st.btc || st.stocksLive || st.spy || st.qqq;
  if(!anyLive){ liveNow = null; }
  else {
    const bench = {};
    Object.keys(CLOSE1019).forEach(k => { const lp = st[k]; const base = benchmarks[k].at(-1);
      bench[k] = lp ? Math.round(base * lp / CLOSE1019[k] * 100) / 100 : base; });
    liveNow = { sleeves: st.sleeves, bench, btcTime: st.btcTime, stkTime: st.stocksLive ? st.stkTime : null };
  }
  const asof = document.getElementById('ytdAsOf');
  if (asof) asof.textContent = (st.label || 'Last close · Oct 19, 2026') + (liveNow ? ' (history: month-end closes through Oct 19)' : '');
  if (chart) render();
}
window.addEventListener('pslive', e => applyLive(e.detail));

let selected = new Set(['berkshire']);
let currentBench = 'btc';
let chart;

function render() {
  // Stats from first selected sleeve
  const first = [...selected][0];
  const s0 = sleeves[first];
  const nowV = liveNow ? liveNow.sleeves[first] : s0.now;
  const s = { now: nowV, ytd: (nowV / 100000 - 100 / 100) * 100 };
  if (!liveNow) s.ytd = s0.ytd;
  document.getElementById('stat-start').textContent = '$100,000';
  document.getElementById('stat-now').textContent = '$' + Math.round(s.now).toLocaleString('en-US');
  const ytdEl = document.getElementById('stat-ytd');
  ytdEl.textContent = (s.ytd >= 0 ? '+' : '') + s.ytd.toFixed(2) + '%';
  ytdEl.className = 'stat-value ' + (s.ytd >= 0 ? 'pos' : 'neg');

  const benchEnd = liveNow ? liveNow.bench[currentBench] : benchmarks[currentBench].at(-1);
  const vs = s.ytd - (benchEnd - 100); // YTD difference vs benchmark, percentage points
  const vsEl = document.getElementById('stat-vs');
  vsEl.textContent = (vs >= 0 ? '+' : '') + vs.toFixed(2) + ' pp';
  vsEl.className = 'stat-value ' + (vs >= 0 ? 'pos' : 'neg');

  document.querySelectorAll('.sleeve-btn').forEach(b => {
    b.classList.toggle('active', selected.has(b.dataset.sleeve));
  });
  document.querySelectorAll('.bench-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.bench === currentBench);
  });

  const datasets = [];
  selected.forEach(key => {
    datasets.push({
      label: sleeves[key].name,
      data: liveNow ? paths[key].concat([Math.round(liveNow.sleeves[key] / 10) / 100]) : paths[key],
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
    data: liveNow ? benchmarks[currentBench].concat([liveNow.bench[currentBench]]) : benchmarks[currentBench],
    borderColor: benchColors[currentBench],
    borderWidth: 1.5,
    borderDash: [5, 4],
    tension: 0.25,
    fill: false,
    pointRadius: 0
  });

  const lbls = liveNow ? labels.concat(['Now']) : labels.slice();
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

document.querySelectorAll('.bench-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    currentBench = btn.dataset.bench;
    render();
  });
});

render();
if (window.PSLive) applyLive(window.PSLive.state());
