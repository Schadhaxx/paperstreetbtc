#!/usr/bin/env node
/* Skunkworks floor prototype (test branch only): the panel's floor maths.
   Loads the real assets/js/btcchart-panel.js in a vm sandbox and checks
   the P._floor test hook against the shipped assets/data/ta-floor.json
   fixture. floorAt uses the JSON's rounded slope (4dp), so values are
   compared with a 5-cent tolerance, not exact equality.
   Break rule (28 Nov 2026, Grok Bot test pack): ONLY a completed weekly
   close 2% or more below the floor breaks it; the in-progress week never
   does, and a stale j.broken flag is ignored.
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

chk('panel exposes P._floor test hook (at/broken/isWeekComplete/weekMonday/evaluateBreak/display)',
  P._floor && typeof P._floor.at === 'function' && typeof P._floor.broken === 'function'
  && typeof P._floor.isWeekComplete === 'function' && typeof P._floor.weekMonday === 'function'
  && typeof P._floor.evaluateBreak === 'function' && typeof P._floor.display === 'function');
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

/* The headline rule on the 26 Nov snapshot: the 23 Nov week is in
   progress (Thu close -3.1%), so it must NOT break the floor. */
const ev = F.evaluateBreak(fix);
chk('fixture is NOT broken (in-progress week must not break)', F.broken(fix) === false, F.broken(fix));
chk('broken(fix, 2026-11-26) is false', F.broken(fix, '2026-11-26') === false);
chk('evaluateBreak: lastCompletedWeek 2026-11-16', ev.lastCompletedWeek === '2026-11-16', ev.lastCompletedWeek);
chk('evaluateBreak: lastCompletedSunday 2026-11-22', ev.lastCompletedSunday === '2026-11-22', ev.lastCompletedSunday);
chk('evaluateBreak: lastCompletedClose $61,161.91', close(ev.lastCompletedClose, 61161.91), ev.lastCompletedClose);
chk('evaluateBreak: floorAtLastCompleted $62,217.68', close(ev.floorAtLastCompleted, 62217.68), ev.floorAtLastCompleted);
chk('evaluateBreak: pctAtLastCompleted -1.7%', close(ev.pctAtLastCompleted, -1.7, 0.05), ev.pctAtLastCompleted);
chk('evaluateBreak: inProgressWeek 2026-11-23', ev.inProgressWeek === '2026-11-23', ev.inProgressWeek);
chk('evaluateBreak: inProgressClose $60,495.57', close(ev.inProgressClose, 60495.57), ev.inProgressClose);
chk('evaluateBreak: inProgressPct -3.1%', close(ev.inProgressPct, -3.1, 0.05), ev.inProgressPct);
chk('evaluateBreak: inProgressWouldBreakIfCompleted true', ev.inProgressWouldBreakIfCompleted === true);
chk('evaluateBreak: maxUnderPct -1.7% (completed weeks only)', close(ev.maxUnderPct, -1.7, 0.05), ev.maxUnderPct);
chk('evaluateBreak: floorNow $62,440.91', close(ev.floorNow, 62440.91), ev.floorNow);
chk('evaluateBreak: breakTrigger $60,973.33', close(ev.breakTrigger, 60973.33), ev.breakTrigger);
chk('evaluateBreak: dashInProgress true', ev.dashInProgress === true);
chk('evaluateBreak: lineIsRed false', ev.lineIsRed === false);
chk('stale broken=true flag is ignored', F.broken(Object.assign({}, fix, { broken: true })) === false);
chk('null / bad input fails closed', F.at(null, '2026-11-23') === null && F.broken(null) === false && F.evaluateBreak(null).broken === false);

/* Display fields: label, as-of Sunday, source pass-through, break rule. */
const disp = F.display(fix);
chk('display: label is Trend support (weekly closes)', disp.label === 'Trend support (weekly closes)', disp.label);
chk('display: asOf 2026-11-22', disp.asOf === '2026-11-22', disp.asOf);
chk('display: source passes through', disp.source === fix.source, disp.source);
chk('display: breakRule', disp.breakRule === 'Completed weekly close (Monday-Sunday UTC) 2% or more below the floor. An in-progress week does not count.', disp.breakRule);
chk('display: brokenNote null when not broken', disp.brokenNote === null, disp.brokenNote);

/* Week helpers: Monday-start UTC, date-only vs datetime asOf. */
chk('weekMonday of Thu 26 Nov is Mon 23 Nov', F.weekMonday('2026-11-26') === '2026-11-23', F.weekMonday('2026-11-26'));
chk('weekMonday of Sun 22 Nov 23:59 UTC is Mon 16 Nov', F.weekMonday('2026-11-22T23:59:59Z') === '2026-11-16', F.weekMonday('2026-11-22T23:59:59Z'));
chk('weekMonday of Mon 23 Nov 00:00 UTC is Mon 23 Nov', F.weekMonday('2026-11-23T00:00:00Z') === '2026-11-23', F.weekMonday('2026-11-23T00:00:00Z'));
chk('date-only Sunday: week complete', F.isWeekComplete('2026-11-16', '2026-11-22') === true);
chk('date-only Saturday: week in progress', F.isWeekComplete('2026-11-16', '2026-11-21') === false);
chk('datetime Sunday 23:59 UTC: week still in progress', F.isWeekComplete('2026-11-16', '2026-11-22T23:59:59Z') === false);
chk('datetime Monday 00:00 UTC: week complete', F.isWeekComplete('2026-11-16', '2026-11-23T00:00:00Z') === true);

/* Synthetic break cases (flat $10,000 floor). */
function synth(weeks, asOf) {
  return { anchor: { date: '2026-01-05', low: 10000 }, slopePerWeek: 0.0, asOf: asOf, source: 'synthetic', weeks: weeks };
}
const wks = [['2026-01-05', 11000], ['2026-01-12', 10500], ['2026-01-19', 9700]];
chk('completed week 3% under: broken', F.broken(synth(wks, '2026-01-25'), '2026-01-25') === true);
chk('completed week 3% under: lineIsRed true', F.evaluateBreak(synth(wks, '2026-01-25'), '2026-01-25').lineIsRed === true);
chk('completed week 3% under: brokenNote set', F.display(synth(wks, '2026-01-25'), '2026-01-25').brokenNote === 'Broken: a completed weekly close finished 2% or more below this line.');
chk('same 3% dip, week in progress (Thu): NOT broken', F.broken(synth(wks, '2026-01-22'), '2026-01-22') === false);
chk('in-progress dip: inProgressWouldBreakIfCompleted true', F.evaluateBreak(synth(wks, '2026-01-22'), '2026-01-22').inProgressWouldBreakIfCompleted === true);
chk('exactly -2.0% completed: breaks', F.broken(synth([['2026-01-05', 11000], ['2026-01-19', 9800]], '2026-01-25'), '2026-01-25') === true);
chk('9800.01 completed (just inside): does not break', F.broken(synth([['2026-01-05', 11000], ['2026-01-19', 9800.01]], '2026-01-25'), '2026-01-25') === false);
chk('exactly -2.0% in progress: does not break', F.broken(synth([['2026-01-05', 11000], ['2026-01-19', 9800]], '2026-01-22'), '2026-01-22') === false);

console.log('TA FLOOR JS TESTS', n, 'FAIL', f);
process.exit(f ? 1 : 0);
