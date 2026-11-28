#!/usr/bin/env node
/* Skunkworks floor prototype (test branch only): the panel's floor maths.
   Loads the real assets/js/btcchart-panel.js in a vm sandbox and checks
   the P._floor test hook against the shipped assets/data/ta-floor.json
   fixture. floorAt uses the JSON's rounded slope (4dp), so values are
   compared with a 5-cent tolerance, not exact equality.
   Run: node tests/test_ta_floor.js */
const fs = require('fs'), path = require('path'), vm = require('vm');
const R = path.join(__dirname, '..');
let n = 0, f = 0;
const chk = (name, ok, info) => { n++; if (!ok) { f++; console.log('FAIL', name, info === undefined ? '' : JSON.stringify(info)); } else console.log('PASS', name); };
const close = (a, b, tol) => a != null && b != null && Math.abs(a - b) <= (tol || 0.05);

const fix = JSON.parse(fs.readFileSync(path.join(R, 'assets/data/ta-floor.json'), 'utf8'));
const src = fs.readFileSync(path.join(R, 'assets/js/btcchart-panel.js'), 'utf8');
const doc = { addEventListener() {}, documentElement: { getAttribute: () => 'dark' }, getElementById: () => null,
  querySelectorAll: () => [], querySelector: () => null, createElement: () => ({ appendChild() {}, setAttribute() {}, style: {} }),
  createTextNode: () => ({}), body: { appendChild() {} } };
const P = { $: (id) => null, U: (p) => p, RAW: '', pill: null, menu: null,
  live: { usd: null, chg: null }, fmt: (v) => '$' + Math.round(v),
  curVal: (v) => v, curSym: () => '$', cadTag: () => '', CUR: { code: 'USD', rate: 1 },
  mp: null, panelReady: false };
const sb = { window: null, document: doc, console, fetch: () => Promise.reject(new Error('no net')), addEventListener() {} };
sb.window = sb; sb.window.__BTCP = P;
vm.createContext(sb); vm.runInContext(src, sb);

chk('panel exposes P._floor test hook', P._floor && typeof P._floor.at === 'function' && typeof P._floor.broken === 'function');
const F = P._floor;

chk('floor at anchor = $15,787.28', close(F.at(fix, '2022-11-21'), 15787.28), F.at(fix, '2022-11-21'));
chk('floor at binding low = $25,162.65', close(F.at(fix, '2023-09-11'), 25162.65), F.at(fix, '2023-09-11'));
chk('floor at Jun 2026 touch = $57,753.22', close(F.at(fix, '2026-06-29'), 57753.22), F.at(fix, '2026-06-29'));
chk('floor now = $62,440.91', close(F.at(fix, '2026-11-23'), 62440.91), F.at(fix, '2026-11-23'));
chk('floor +52w = $74,048.51', close(F.at(fix, '2027-11-22'), 74048.51), F.at(fix, '2027-11-22'));
chk('floor before the anchor = null', F.at(fix, '2021-11-15') === null, F.at(fix, '2021-11-15'));
chk('floor mid-week uses its Monday', close(F.at(fix, '2026-11-25'), 62440.91), F.at(fix, '2026-11-25'));
chk('floor matches every JSON week line', fix.weeks.filter(function (w) { return w[0] >= fix.anchor.date; }).every(function (w) {
  return close(F.at(fix, w[0]), fix.anchor.low + fix.slopePerWeek * (Math.round((new Date(w[0] + 'T00:00:00Z') - new Date(fix.anchor.date + 'T00:00:00Z')) / (7 * 864e5))), 0.05);
}));
chk('fixture is broken (23 Nov close 3.12% under the floor)', F.broken(fix) === true);
const noFlag = (lc) => { const o = Object.assign({}, fix, { lastClose: lc }); delete o.broken; return o; };
chk('last close at the trigger breaks it', F.broken(noFlag(61192.09)) === true);
chk('last close above the trigger does not', F.broken(noFlag(61500)) === false);
chk('last close 3% under breaks it', F.broken(noFlag(60300)) === true);
chk('broken flag on the JSON is honoured', F.broken(Object.assign({}, fix, { broken: true })) === true);
chk('broken without a trigger falls back to floorNow x 0.98',
  F.broken({ anchor: fix.anchor, slopePerWeek: fix.slopePerWeek, floorNow: 62440.91, lastClose: 61192.08 }) === true &&
  F.broken({ anchor: fix.anchor, slopePerWeek: fix.slopePerWeek, floorNow: 62440.91, lastClose: 61192.10 }) === false);
chk('null / bad input fails closed', F.at(null, '2026-11-23') === null && F.broken(null) === false);

console.log('TA FLOOR JS TESTS', n, 'FAIL', f);
process.exit(f ? 1 : 0);
