#!/usr/bin/env node
/* Skunkworks TA 2.0 (test branch only): the Desk modal's weekly moving
   averages (SMA/EMA, periods 20/50/200). Loads the real
   assets/js/screener-indicator-chart.js in a vm sandbox and checks the
   IndicatorChart.enhMA test hook against hand-computed cases and the
   shipped weekly files. The Desk files hold 47 weeks (SPCX 24), so a
   50- or 200-period MA has no value anywhere — all nulls, never a
   partial-period line.
   Run: node tests/test_ta_lines_desk_ma.js */
const fs = require('fs'), path = require('path'), vm = require('vm');
const R = path.join(__dirname, '..');
let n = 0, f = 0;
const chk = (name, ok, info) => { n++; if (!ok) { f++; console.log('FAIL', name, info === undefined ? '' : JSON.stringify(info)); } else console.log('PASS', name); };
const close = (a, b, tol) => a != null && b != null && Math.abs(a - b) <= (tol || 0.01);
const W = (closes) => closes.map((c) => ({ close: c }));
const allNull = (arr) => Array.isArray(arr) && arr.every((v) => v === null);

const src = fs.readFileSync(path.join(R, 'assets/js/screener-indicator-chart.js'), 'utf8');
const doc = { addEventListener() {}, documentElement: { getAttribute: () => 'dark' }, getElementById: () => null,
  querySelectorAll: () => [], querySelector: () => null, createElement: () => ({ appendChild() {}, setAttribute() {}, style: {} }),
  createTextNode: () => ({}), body: { appendChild() {} } };
const win = { addEventListener() {}, psC: (d) => d, document: doc };
const sb = { window: win, document: doc, fetch: () => Promise.reject(new Error('no net')), console };
vm.createContext(sb); vm.runInContext(src, sb);
const IC = win.IndicatorChart;
const ma = IC && IC.enhMA;

chk('panel exposes enhMA hook', typeof ma === 'function');

// SMA: hand-computed.
chk('SMA 3 on [10,20,30,40,50] = [null,null,20,30,40]',
  JSON.stringify(ma(W([10, 20, 30, 40, 50]), 'sma', 3)) === JSON.stringify([null, null, 20, 30, 40]),
  ma(W([10, 20, 30, 40, 50]), 'sma', 3));
chk('SMA 5 on [10,11,12,13,14] = [null,null,null,null,12]',
  JSON.stringify(ma(W([10, 11, 12, 13, 14]), 'sma', 5)) === JSON.stringify([null, null, null, null, 12]),
  ma(W([10, 11, 12, 13, 14]), 'sma', 5));

// EMA: seed is the SMA of the first `period` closes, k = 2/(period+1).
// Period 3, k = 0.5: seed idx2 = 11, idx3 = 13*.5 + 11*.5 = 12,
// idx4 = 14*.5 + 12*.5 = 13.
chk('EMA 3 on [10,11,12,13,14] = [null,null,11,12,13]',
  JSON.stringify(ma(W([10, 11, 12, 13, 14]), 'ema', 3)) === JSON.stringify([null, null, 11, 12, 13]),
  ma(W([10, 11, 12, 13, 14]), 'ema', 3));
chk('EMA 5 on [10,11,12,13,14] = [null,null,null,null,12] (seed only)',
  JSON.stringify(ma(W([10, 11, 12, 13, 14]), 'ema', 5)) === JSON.stringify([null, null, null, null, 12]),
  ma(W([10, 11, 12, 13, 14]), 'ema', 5));
chk('EMA 3 on [10,20,30,40] = [null,null,20,30]',
  JSON.stringify(ma(W([10, 20, 30, 40]), 'ema', 3)) === JSON.stringify([null, null, 20, 30]),
  ma(W([10, 20, 30, 40]), 'ema', 3));

// 200-period handling: never a partial line.
const c47 = Array.from({ length: 47 }, (_, i) => i + 1);
chk('SMA 200 on 47 closes = all null, length 47',
  allNull(ma(W(c47), 'sma', 200)) && ma(W(c47), 'sma', 200).length === 47);
chk('EMA 200 on 47 closes = all null',
  allNull(ma(W(c47), 'ema', 200)));
chk('SMA 50 on 47 closes = all null (47 < 50)',
  allNull(ma(W(c47), 'sma', 50)));
const c200 = Array.from({ length: 200 }, (_, i) => i + 1);
const ma200 = ma(W(c200), 'sma', 200);
chk('SMA 200 on 200 closes: null before idx 199, value 100.5 at 199',
  ma200.slice(0, 199).every((v) => v === null) && close(ma200[199], 100.5), ma200[199]);

// Bad input fails closed; unknown type falls back to SMA.
chk('null / empty weeks -> []', JSON.stringify(ma(null, 'sma', 20)) === '[]' && JSON.stringify(ma([], 'sma', 20)) === '[]');
chk('period 1 -> all null', allNull(ma(W([10, 20, 30]), 'sma', 1)));
chk('unknown type behaves as SMA',
  JSON.stringify(ma(W([10, 20, 30, 40]), 'bogus', 3)) === JSON.stringify(ma(W([10, 20, 30, 40]), 'sma', 3)));
chk('non-finite close poisons its windows, never NaN',
  ma(W([10, 20, NaN, 40, 50]), 'sma', 3).every((v) => v === null));

// Real shipped files: gold (47 weeks) and SPCX (24 weeks).
const goldWeeks = JSON.parse(fs.readFileSync(path.join(R, 'assets/data/gold-weekly.json'), 'utf8')).weeks;
const goldCloses = goldWeeks.map((w) => w.close);
const meanLast = (arr, k) => arr.slice(-k).reduce((a, b) => a + b, 0) / k;
const goldSma20 = ma(goldWeeks, 'sma', 20);
chk('gold: 47 weeks', goldWeeks.length === 47, goldWeeks.length);
chk('gold SMA 20 last = mean of last 20 closes',
  close(goldSma20[46], meanLast(goldCloses, 20)), goldSma20[46]);
chk('gold SMA 20 first value at idx 19 = mean of first 20 closes',
  close(goldSma20[19], goldCloses.slice(0, 20).reduce((a, b) => a + b, 0) / 20), goldSma20[19]);
const goldEma20 = ma(goldWeeks, 'ema', 20);
chk('gold EMA 20 last is finite and differs from SMA 20 last',
  isFinite(goldEma20[46]) && Math.abs(goldEma20[46] - goldSma20[46]) > 0.01,
  { ema: goldEma20[46], sma: goldSma20[46] });
chk('gold EMA 20 seeds on SMA at idx 19',
  close(goldEma20[19], goldSma20[19]), goldEma20[19]);
chk('gold SMA 50 = all null (47 weeks)', allNull(ma(goldWeeks, 'sma', 50)));
chk('gold EMA 200 = all null', allNull(ma(goldWeeks, 'ema', 200)));
const spcxWeeks = JSON.parse(fs.readFileSync(path.join(R, 'assets/data/stock-weekly-SPCX.json'), 'utf8')).weeks;
chk('SPCX: 24 weeks, SMA 20 last = mean of last 20 closes',
  spcxWeeks.length === 24 &&
  close(ma(spcxWeeks, 'sma', 20)[23], meanLast(spcxWeeks.map((w) => w.close), 20)),
  spcxWeeks.length);

console.log(n - f + '/' + n + ' checks passed');
process.exit(f ? 1 : 0);
