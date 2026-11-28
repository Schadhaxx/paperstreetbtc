#!/usr/bin/env node
/* Skunkworks 200-week MA prototype (test branch only): the panel's MA maths.
   Loads the real assets/js/btcchart-panel.js in a vm sandbox and checks
   the P._ma200 test hook against the shipped assets/data/ta-ma200.json
   fixture. The fixture's MA values are rounded to 2dp, so the hook's
   lookups are compared exactly.
   Run: node tests/test_ta_ma200.js */
const fs = require('fs'), path = require('path'), vm = require('vm');
const R = path.join(__dirname, '..');
let n = 0, f = 0;
const chk = (name, ok, info) => { n++; if (!ok) { f++; console.log('FAIL', name, info === undefined ? '' : JSON.stringify(info)); } else console.log('PASS', name); };

const fix = JSON.parse(fs.readFileSync(path.join(R, 'assets/data/ta-ma200.json'), 'utf8'));
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

chk('panel exposes P._ma200 test hook', P._ma200 && typeof P._ma200.at === 'function' && typeof P._ma200.key === 'function' && typeof P._ma200.map === 'function');
const M = P._ma200;

chk('MA now = $68,349.48 (in-progress week)', M.at(fix, '2026-11-23') === 68349.48, M.at(fix, '2026-11-23'));
chk('MA last completed week = $68,165.88', M.at(fix, '2026-11-16') === 68165.88, M.at(fix, '2026-11-16'));
chk('MA mid-week uses its Monday', M.at(fix, '2026-11-25') === 68349.48, M.at(fix, '2026-11-25'));
chk('MA at Dec 2018 touch = $3,197.67', M.at(fix, '2018-12-10') === 3197.67, M.at(fix, '2018-12-10'));
chk('MA at Nov 2022 break = $24,091.15', M.at(fix, '2022-11-21') === 24091.15, M.at(fix, '2022-11-21'));
chk('MA first week = $125.51', M.at(fix, '2014-06-09') === 125.51, M.at(fix, '2014-06-09'));
chk('MA before the first MA week = null', M.at(fix, '2014-06-02') === null, M.at(fix, '2014-06-02'));
chk('MA in 2010 (no window yet) = null', M.at(fix, '2010-08-18') === null, M.at(fix, '2010-08-18'));
chk('Monday key of a Wednesday', M.key('2026-11-25') === '2026-11-23', M.key('2026-11-25'));
chk('Monday key of a Sunday is the previous Monday', M.key('2026-11-22') === '2026-11-16', M.key('2026-11-22'));
chk('Monday key of a Monday is itself', M.key('2026-11-23') === '2026-11-23', M.key('2026-11-23'));
chk('map holds all 651 weeks', Object.keys(M.map(fix)).length === 651, Object.keys(M.map(fix)).length);
chk('MA lookup matches every fixture week row', fix.weeks.every(function (w) { return M.at(fix, w[0]) === w[3]; }));
chk('fixture headline numbers', fix.maNow === 68349.48 && fix.priceVsMaNowPct === -11.49 && fix.weeksBelow === 58 && fix.weeksTotal === 651 && fix.longestBelowWeeks === 30);
chk('null / bad input fails closed', M.at(null, '2026-11-23') === null && M.at(fix, 'not-a-date') === null && M.key('not-a-date') === null);

console.log('TA MA200 JS TESTS', n, 'FAIL', f);
process.exit(f ? 1 : 0);
