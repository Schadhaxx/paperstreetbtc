#!/usr/bin/env node
/* Skunkworks TA 2.0 (test branch only): the panel's sloped-line maths.
   Loads the real assets/js/screener-indicator-chart.js in a vm sandbox
   and checks the IndicatorChart._ta.valueAt test hook against the
   shipped assets/data/ta-lines-desk.json fixture. valueAt uses the
   JSON's rounded slope (2dp), so the end-price comparison allows a
   50-cent tolerance; the anchor and extrapolated values are exact.
   Also checks the fixture shape for all 24 Desk symbols.
   Run: node tests/test_ta_lines_desk.js */
const fs = require('fs'), path = require('path'), vm = require('vm');
const R = path.join(__dirname, '..');
let n = 0, f = 0;
const chk = (name, ok, info) => { n++; if (!ok) { f++; console.log('FAIL', name, info === undefined ? '' : JSON.stringify(info)); } else console.log('PASS', name); };
const close = (a, b, tol) => a != null && b != null && Math.abs(a - b) <= (tol || 0.01);

const fix = JSON.parse(fs.readFileSync(path.join(R, 'assets/data/ta-lines-desk.json'), 'utf8'));
const src = fs.readFileSync(path.join(R, 'assets/js/screener-indicator-chart.js'), 'utf8');
const doc = { addEventListener() {}, documentElement: { getAttribute: () => 'dark' }, getElementById: () => null,
  querySelectorAll: () => [], querySelector: () => null, createElement: () => ({ appendChild() {}, setAttribute() {}, style: {} }),
  createTextNode: () => ({}), body: { appendChild() {} } };
const win = { addEventListener() {}, psC: (d) => d, document: doc };
const sb = { window: win, document: doc, fetch: () => Promise.reject(new Error('no net')), console };
vm.createContext(sb); vm.runInContext(src, sb);
const IC = win.IndicatorChart;

chk('panel exposes _ta.valueAt hook', IC._ta && typeof IC._ta.valueAt === 'function');
const at = IC._ta.valueAt;
const gold = fix.GOLD;
const ln = gold.sloped[0];

chk('gold sloped line is support +15.14/wk, 11 touches',
  ln && ln.type === 'support' && ln.slope === 15.14 && ln.touches === 11, ln);
chk('value at anchor idx 135 = $2,304.20', close(at(ln, 135), 2304.2), at(ln, 135));
chk('value at last idx 263 ~= endPrice $4,242.24 (50c tolerance)',
  close(at(ln, 263), 4242.24, 0.50), at(ln, 263));
chk('value at idx 0 = $260.30 (extrapolated back)', close(at(ln, 0), 260.3), at(ln, 0));
chk('value at idx 200 = $3,288.30', close(at(ln, 200), 3288.3), at(ln, 200));
chk('null / bad input fails closed',
  at(null, 135) === null && at(ln, 'x') === null && at({}, 135) === null &&
  at({ anchor: [135, 2304.2] }, 135) === null && at(ln, NaN) === null);

chk('fixture: 24 symbols', Object.keys(fix).length === 24, Object.keys(fix).length);
const EXPECTED = ['TSLA', 'PLTR', 'MSTR', 'IBIT', 'MU', 'META', 'SPCX', 'BRK.B', 'AAPL', 'AMZN',
  'MSFT', 'NFLX', 'SPOT', 'XYZ', 'GOOGL', 'NVDA', 'GOLD', 'WTI', 'US10Y', 'VIX', 'DIA', 'QQQ', 'USDCAD', 'DXY'];
chk('fixture: all 24 expected symbols present', EXPECTED.every((s) => s in fix),
  EXPECTED.filter((s) => !(s in fix)));
let shapeOk = true;
for (const s of EXPECTED) {
  const e = fix[s];
  if (!e || !Array.isArray(e.levels) || e.levels.length > 3) shapeOk = false;
  if (!e || !Array.isArray(e.sloped) || e.sloped.length > 2) shapeOk = false;
  for (const lv of (e && e.levels) || []) {
    if (typeof lv.price !== 'number' || !isFinite(lv.price) ||
        (lv.type !== 'support' && lv.type !== 'resistance')) shapeOk = false;
  }
}
chk('fixture: every symbol has <=3 levels, <=2 sloped, well-formed entries', shapeOk);
chk('fixture: GOLD levels are the verified full-series numbers',
  JSON.stringify(gold.levels.map((l) => l.price)) === JSON.stringify([3152.03, 3506.77, 5510.15]),
  gold.levels.map((l) => l.price));

console.log(n - f + '/' + n + ' checks passed');
process.exit(f ? 1 : 0);
