#!/usr/bin/env node
/* Comparison chart: rebase math, range rules, SPCX exclusion, shipped daily file. */
const fs = require('fs'), path = require('path');
const R = path.join(__dirname, '..');
let n = 0, f = 0;
const chk = (name, ok, info) => { n++; if (!ok) { f++; console.log('FAIL', name, info === undefined ? '' : JSON.stringify(info)); } };
const src = fs.readFileSync(path.join(R, 'assets/js/screener-chart.js'), 'utf8');
const start = src.indexOf('var CmpMath = (function () {');
const end = src.indexOf('})();', start);
if (start < 0 || end < 0) { console.log('FAIL CmpMath block missing'); process.exit(1); }
const CmpMath = eval(src.slice(start + 'var CmpMath = '.length, end + 5));
const { cmpRebase, commonTarget, lastOnOrBefore, shiftMonths, rankDesc, cmpMoney, fmtPct } = CmpMath;

chk('shiftMonths 30 Oct -1 = 30 Sep', shiftMonths('2026-10-30', -1) === '2026-09-30');
chk('shiftMonths 30 Oct -3 = 30 Jul', shiftMonths('2026-10-30', -3) === '2026-07-30');
chk('shiftMonths 30 Oct -6 = 30 Apr', shiftMonths('2026-10-30', -6) === '2026-04-30');
chk('shiftMonths 31 Mar -1 clamps to 28 Feb', shiftMonths('2026-03-31', -1) === '2026-02-28');
chk('YTD target is 31 Dec 2025', commonTarget('ytd', '2026-10-30') === '2025-12-31');
chk('Since listing target is 12 Jun 2026', commonTarget('listing', '2026-10-30') === '2026-06-12');
chk('1M target', commonTarget('1M', '2026-10-30') === '2026-09-30');

const dates = ['2026-01-02', '2026-01-05', '2026-06-12', '2026-10-30'];
const closes = [110, 121, 90, 100];
const ytd = cmpRebase(dates, closes, '2025-12-31', 100);
chk('YTD starts at 0%', ytd && ytd.pcts[0] === 0 && ytd.dates[0] === '2025-12-31');
chk('YTD end is (last/base-1)', ytd && Math.abs(ytd.pcts[ytd.pcts.length - 1] - 0) < 1e-9, ytd && ytd.pcts);
chk('YTD second point is +10%', ytd && Math.abs(ytd.pcts[1] - 10) < 1e-9);

const win = cmpRebase(dates, closes, '2026-01-05', null);
chk('window starts on the session at 0%', win && win.dates[0] === '2026-01-05' && win.pcts[0] === 0);
chk('window end uses that session as the base', win && Math.abs(win.pcts[win.pcts.length - 1] - (100 / 121 - 1) * 100) < 1e-9);

chk('no line before a symbol exists', cmpRebase(['2026-06-12'], [160.95], '2025-12-31', null) === null);
chk('explicit base is not used once the series has started', (function () {
  const rb = cmpRebase(['2026-06-12', '2026-06-15'], [160.95, 150], '2026-06-12', 999);
  return rb && rb.base === 160.95 && rb.pcts[0] === 0 && Math.abs(rb.pcts[1] - (150 / 160.95 - 1) * 100) < 1e-9;
})());
chk('lastOnOrBefore misses a later listing', lastOnOrBefore(['2026-06-12'], '2026-04-30') === null);
chk('lastOnOrBefore hits the session', lastOnOrBefore(['2026-06-12', '2026-07-30'], '2026-07-30') === '2026-07-30');

const ranked = rankDesc([{ sym: 'A', pct: 1 }, { sym: 'B', pct: 3 }, { sym: 'C', pct: null }]);
chk('rank best first, missing last', ranked.map(function (r) { return r.sym; }).join(',') === 'B,A,C');
chk('cmpMoney negative is -$1,234.50', cmpMoney(-1234.5) === '-$1,234.50', cmpMoney(-1234.5));
chk('cmpMoney positive has no minus', cmpMoney(10) === '$10.00');
chk('cmpMoney rejects junk', cmpMoney(NaN) === '\u2014' && cmpMoney('x') === '\u2014');
chk('fmtPct signs', fmtPct(1) === '+1.00%' && fmtPct(-2) === '-2.00%' && fmtPct(0) === '0.00%');
chk('fmtPct never uses $-', fmtPct(-2).indexOf('$-') === -1);

const HOLIDAYS = {
  '2026-01-01': 1, '2026-01-19': 1, '2026-02-16': 1, '2026-04-03': 1, '2026-05-25': 1,
  '2026-06-19': 1, '2026-07-03': 1, '2026-09-07': 1, '2026-11-26': 1, '2026-12-25': 1
};
function isSession(iso) {
  const d = new Date(iso + 'T12:00:00Z');
  const wd = d.getUTCDay();
  return wd !== 0 && wd !== 6 && !HOLIDAYS[iso];
}
function gaps(dates) {
  const have = {};
  dates.forEach(function (d) { have[d] = 1; });
  const bad = [];
  let d = new Date(dates[0] + 'T12:00:00Z');
  const end = new Date(dates[dates.length - 1] + 'T12:00:00Z');
  while (d <= end) {
    const iso = d.toISOString().slice(0, 10);
    if (isSession(iso) && !have[iso]) bad.push(iso);
    d = new Date(d.getTime() + 86400000);
  }
  return bad;
}

const doc = JSON.parse(fs.readFileSync(path.join(R, 'assets/data/cmp-daily.json'), 'utf8'));
const pack = JSON.parse(fs.readFileSync(path.join(R, 'assets/data/screener-pack.json'), 'utf8'));
const packRow = {};
(pack.rows || []).forEach(function (r) { packRow[r.symbol] = r; });
const STOCKS = ['TSLA', 'PLTR', 'MSTR', 'IBIT', 'MU', 'META', 'SPCX'];
chk('asOf is 30 Oct 2026', doc.asOf === '2026-10-30' && doc.unit === 'usd');

STOCKS.forEach(function (sym) {
  const s = doc.symbols[sym];
  chk(sym + ' present', !!s);
  if (!s) return;
  const dates = s.dates, closes = s.closes;
  chk(sym + ' ascending unique', dates.length === closes.length && dates.join() === dates.slice().sort().join() && new Set(dates).size === dates.length);
  chk(sym + ' no session gaps', gaps(dates).length === 0, gaps(dates).slice(0, 6));
  chk(sym + ' base matches pack', Math.abs(s.baseClose - packRow[sym].baseClose) <= 0.01, [s.baseClose, packRow[sym].baseClose]);
  const weekly = JSON.parse(fs.readFileSync(path.join(R, 'assets/data/stock-weekly-' + sym + '.json'), 'utf8'));
  const wlast = weekly.weeks[weekly.weeks.length - 1].close;
  chk(sym + ' last close matches weekly', Math.abs(closes[closes.length - 1] - wlast) <= 0.01, [closes[closes.length - 1], wlast]);
  chk(sym + ' last date is asOf', dates[dates.length - 1] === doc.asOf);
  if (s.basis === 'ytd') {
    chk(sym + ' series starts 2 Jan', dates[0] === '2026-01-02' && s.baseDate === '2025-12-31');
    const rb = cmpRebase(dates, closes, '2025-12-31', s.baseClose);
    const end = rb.pcts[rb.pcts.length - 1];
    const want = (closes[closes.length - 1] / s.baseClose - 1) * 100;
    chk(sym + ' YTD start is 0%', rb.pcts[0] === 0 && rb.dates[0] === '2025-12-31');
    chk(sym + ' YTD end matches last/base', Math.abs(end - want) < 1e-6, [end, want]);
    if (Math.abs(packRow[sym].price - closes[closes.length - 1]) <= 0.01) {
      chk(sym + ' YTD end matches card', Math.abs(end - packRow[sym].ytdPct) < 0.02);
    } else {
      console.log('NOTE', sym, 'card price', packRow[sym].price, 'is', pack.asOf, 'daily last', closes[closes.length - 1], 'is', doc.asOf);
    }
  } else {
    chk(sym + ' listing series', dates[0] === '2026-06-12' && Math.abs(closes[0] - s.baseClose) <= 0.01 && Math.abs(s.baseClose - 160.95) <= 0.01);
    chk(sym + ' not given a YTD line', cmpRebase(dates, closes, '2025-12-31', null) === null);
    const rb = cmpRebase(dates, closes, '2026-06-12', null);
    chk(sym + ' listing starts at 0%', rb && rb.pcts[0] === 0 && rb.dates[0] === '2026-06-12');
    chk(sym + ' hidden on 6M', lastOnOrBefore(dates, '2026-04-30') === null);
    chk(sym + ' present on 3M', lastOnOrBefore(dates, '2026-07-30') !== null);
  }
});

['SPY', 'QQQ', 'BTC'].forEach(function (sym) {
  const s = doc.symbols[sym];
  chk(sym + ' benchmark present', !!s && s.kind === 'benchmark' && s.dates.length > 50);
  if (!s) return;
  chk(sym + ' ascending', s.dates.join() === s.dates.slice().sort().join());
  if (sym !== 'BTC') chk(sym + ' no session gaps', gaps(s.dates).length === 0, gaps(s.dates).slice(0, 4));
  else {
    const have = {};
    s.dates.forEach(function (d) { have[d] = 1; });
    let miss = 0, d = new Date(s.dates[0] + 'T12:00:00Z'), end = new Date(s.dates[s.dates.length - 1] + 'T12:00:00Z');
    while (d <= end) {
      if (!have[d.toISOString().slice(0, 10)]) miss++;
      d = new Date(d.getTime() + 86400000);
    }
    chk('BTC has no calendar gaps', miss === 0, miss);
  }
});

const page = fs.readFileSync(path.join(R, 'screener.html'), 'utf8');
const chart = src;
chk('page has no $- money', page.indexOf('$-') === -1);
['STRF', 'STRK', 'STRD', 'Sunil', 'Manual refresh'].forEach(function (w) {
  chk('chart js hides ' + w, chart.indexOf(w) === -1);
  chk('compare section hides ' + w, page.split('Comparison chart')[1].indexOf(w) === -1);
});

console.log('cmp js checks', n, 'fail', f);
process.exit(f ? 1 : 0);
