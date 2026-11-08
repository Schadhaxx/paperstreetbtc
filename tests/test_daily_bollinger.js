#!/usr/bin/env node
/* Daily Bollinger Weekly/Daily switch: tests for enhBollDaily in
   assets/js/screener-indicator-chart.js. Loads the real file in a vm
   sandbox with DOM stubs (the IIFE only needs addEventListener at load
   time) and checks it against the real generated daily + weekly files.

   Run: node tests/test_daily_bollinger.js
*/
const fs = require('fs'), path = require('path'), vm = require('vm');
const R = path.join(__dirname, '..');
let n = 0, f = 0;
const chk = (name, ok, info) => { n++; if (!ok) { f++; console.log('FAIL', name, info === undefined ? '' : JSON.stringify(info)); } else console.log('PASS', name); };

/* ---- load the real chart file in a sandbox ---- */
const src = fs.readFileSync(path.join(R, 'assets/js/screener-indicator-chart.js'), 'utf8');
const windowStub = {
  addEventListener: () => {},
  psC: (d, l) => d,
};
const documentStub = {
  addEventListener: () => {},
  documentElement: { getAttribute: () => 'dark' },
  getElementById: () => null,
  querySelectorAll: () => [],
  querySelector: () => null,
  createElement: () => ({ appendChild: () => {}, setAttribute: () => {}, style: {} }),
  createTextNode: () => ({}),
  body: { appendChild: () => {} },
};
const sandbox = {
  window: windowStub,
  document: documentStub,
  fetch: () => Promise.reject(new Error('no network in test')),
  console,
};
sandbox.window.document = documentStub;
vm.createContext(sandbox);
vm.runInContext(src, sandbox);
const IC = windowStub.IndicatorChart;
chk('IndicatorChart exposes enhBollDaily', typeof IC.enhBollDaily === 'function');
chk('IndicatorChart still exposes enhBoll', typeof IC.enhBoll === 'function');

/* ---- helpers ---- */
function loadJson(p) { return JSON.parse(fs.readFileSync(path.join(R, p), 'utf8')); }
function weeksOf(weeklyDoc) {
  return weeklyDoc.weeks.map(w => ({ ...w, sunday: w.sunday, monday: w.monday }));
}
function dailySMA(days, endIdx) {
  let s = 0; for (let i = endIdx - 19; i <= endIdx; i++) s += days[i].close;
  return s / 20;
}
function dailyBand(days, endIdx) {
  const m = dailySMA(days, endIdx);
  let sd = 0; for (let i = endIdx - 19; i <= endIdx; i++) sd += (days[i].close - m) ** 2;
  sd = Math.sqrt(sd / 19);
  return { sma: m, up: m + 2 * sd, lo: m - 2 * sd };
}
function lastDailyIdx(days, sunday) {
  let ans = -1;
  for (let i = 0; i < days.length; i++) if (days[i].date <= sunday) ans = i;
  return ans;
}

/* ---- TSLA: daily vs weekly on real data ---- */
const tslaW = loadJson('assets/data/stock-weekly-TSLA.json');
const tslaD = loadJson('assets/data/stock-daily-TSLA.json');
const tslaWeeks = weeksOf(tslaW);
const tslaDays = tslaD.days;
chk('TSLA daily file has 214 days', tslaDays.length === 214, tslaDays.length);
chk('TSLA weekly file has 45 weeks', tslaWeeks.length === 45, tslaWeeks.length);

const dB = IC.enhBollDaily(tslaWeeks, tslaDays);
const wB = IC.enhBoll(tslaWeeks);
const last = tslaWeeks.length - 1;
chk('TSLA daily bands non-null at last week', dB.sma[last] != null && dB.up[last] != null && dB.lo[last] != null);
chk('TSLA weekly bands non-null at last week', wB.sma[last] != null);
// Independent check: daily SMA at the last week = mean of the 20 daily
// closes ending on the last session (2026-11-06, the in-progress week's
// last completed session; the week's Sunday is 2026-11-08).
const li = lastDailyIdx(tslaDays, tslaWeeks[last].sunday);
chk('TSLA last daily idx is 2026-11-06', tslaDays[li].date === '2026-11-06', tslaDays[li].date);
const exp = dailyBand(tslaDays, li);
chk('TSLA daily SMA matches independent calc', Math.abs(dB.sma[last] - exp.sma) < 1e-9, { got: dB.sma[last], exp: exp.sma });
chk('TSLA daily upper matches independent calc', Math.abs(dB.up[last] - exp.up) < 1e-9);
chk('TSLA daily lower matches independent calc', Math.abs(dB.lo[last] - exp.lo) < 1e-9);
// Weekly vs Daily actually differ at the last week (the switch changes
// the bands, it is not a no-op).
chk('TSLA daily SMA differs from weekly SMA', Math.abs(dB.sma[last] - wB.sma[last]) > 1, { daily: dB.sma[last], weekly: wB.sma[last] });
chk('TSLA daily upper differs from weekly upper', Math.abs(dB.up[last] - wB.up[last]) > 1, { daily: dB.up[last], weekly: wB.up[last] });
// Daily bands hug price more closely in this period (narrower than weekly).
const dW = dB.up[last] - dB.lo[last], wW = wB.up[last] - wB.lo[last];
chk('TSLA daily band narrower than weekly band', dW < wW, { dailyWidth: dW, weeklyWidth: wW });
console.log('TSLA last week — weekly SMA/upper/lower:', wB.sma[last].toFixed(2), wB.up[last].toFixed(2), wB.lo[last].toFixed(2));
console.log('TSLA last week — daily  SMA/upper/lower:', dB.sma[last].toFixed(2), dB.up[last].toFixed(2), dB.lo[last].toFixed(2));
console.log('TSLA last week close:', tslaWeeks[last].close, 'daily last close:', tslaDays[li].close);

// Mapping check on a mid-chart week: week 30 (sunday 2026-07-26).
const w30 = 30;
const li30 = lastDailyIdx(tslaDays, tslaWeeks[w30].sunday);
const exp30 = dailyBand(tslaDays, li30);
chk('TSLA week 30 daily SMA matches independent calc', Math.abs(dB.sma[w30] - exp30.sma) < 1e-9);
chk('TSLA week 30 daily upper matches independent calc', Math.abs(dB.up[w30] - exp30.up) < 1e-9);

/* ---- fewer than 20 daily closes -> null ---- */
const shortDays = tslaDays.slice(0, 10);
const shortB = IC.enhBollDaily(tslaWeeks, shortDays);
chk('short daily file (10 closes) -> all bands null', shortB.sma.every(v => v === null) && shortB.up.every(v => v === null));
// 19 closes: still null everywhere (need 20).
const b19 = IC.enhBollDaily(tslaWeeks, tslaDays.slice(0, 19));
chk('19 daily closes -> all bands null', b19.sma.every(v => v === null));
// Exactly 20 closes: bands appear only at the week whose last session
// is on/after the 20th daily close (2026-01-30, week of 2026-01-26).
const b20 = IC.enhBollDaily(tslaWeeks, tslaDays.slice(0, 20));
const firstNonNull = b20.sma.findIndex(v => v !== null);
chk('20 daily closes -> first band at week of 2026-01-26', firstNonNull === 4, firstNonNull);
chk('20 daily closes -> weeks before that are null', b20.sma.slice(0, 4).every(v => v === null));

/* ---- SPCX: only 22 weeks, 103 daily closes ---- */
const spcxW = loadJson('assets/data/stock-weekly-SPCX.json');
const spcxD = loadJson('assets/data/stock-daily-SPCX.json');
const spcxWeeks = weeksOf(spcxW);
const spcxDays = spcxD.days;
chk('SPCX daily file has 103 days', spcxDays.length === 103, spcxDays.length);
chk('SPCX weekly file has 22 weeks', spcxWeeks.length === 22, spcxWeeks.length);
const sB = IC.enhBollDaily(spcxWeeks, spcxDays);
const sW = IC.enhBoll(spcxWeeks);
const sLast = spcxWeeks.length - 1;
chk('SPCX daily bands non-null at last week', sB.sma[sLast] != null);
chk('SPCX weekly bands non-null at last week (22 weeks >= 20)', sW.sma[sLast] != null);
// Daily bands exist for MORE weeks than weekly bands (daily needs 20
// daily closes ≈ 4 weeks of trading; weekly needs 20 weeks).
const sFirstDaily = sB.sma.findIndex(v => v !== null);
const sFirstWeekly = sW.sma.findIndex(v => v !== null);
chk('SPCX daily bands start earlier than weekly bands', sFirstDaily < sFirstWeekly, { daily: sFirstDaily, weekly: sFirstWeekly });
const sLi = lastDailyIdx(spcxDays, spcxWeeks[sLast].sunday);
const sExp = dailyBand(spcxDays, sLi);
chk('SPCX daily SMA matches independent calc', Math.abs(sB.sma[sLast] - sExp.sma) < 1e-9);
console.log('SPCX last week — weekly SMA/upper/lower:', sW.sma[sLast].toFixed(2), sW.up[sLast].toFixed(2), sW.lo[sLast].toFixed(2));
console.log('SPCX last week — daily  SMA/upper/lower:', sB.sma[sLast].toFixed(2), sB.up[sLast].toFixed(2), sB.lo[sLast].toFixed(2));

/* ---- VIX: no volume, closes only — Bollinger still works ---- */
const vixW = loadJson('assets/data/vix-weekly.json');
const vixD = loadJson('assets/data/ind-daily-vix.json');
const vixWeeks = weeksOf(vixW);
const vixDays = vixD.days;
chk('VIX daily file has 216 days', vixDays.length === 216, vixDays.length);
const vB = IC.enhBollDaily(vixWeeks, vixDays);
const vLast = vixWeeks.length - 1;
chk('VIX daily bands non-null at last week', vB.sma[vLast] != null);
const vLi = lastDailyIdx(vixDays, vixWeeks[vLast].sunday);
const vExp = dailyBand(vixDays, vLi);
chk('VIX daily SMA matches independent calc', Math.abs(vB.sma[vLast] - vExp.sma) < 1e-9);
console.log('VIX last week — daily SMA/upper/lower:', vB.sma[vLast].toFixed(2), vB.up[vLast].toFixed(2), vB.lo[vLast].toFixed(2));

/* ---- US10Y: 3-decimal closes ---- */
const yW = loadJson('assets/data/us10y-weekly.json');
const yD = loadJson('assets/data/ind-daily-us10y.json');
const yB = IC.enhBollDaily(weeksOf(yW), yD.days);
chk('US10Y daily bands non-null at last week', yB.sma[yB.sma.length - 1] != null);

console.log(`\n${n - f}/${n} PASS`);
process.exit(f ? 1 : 0);
