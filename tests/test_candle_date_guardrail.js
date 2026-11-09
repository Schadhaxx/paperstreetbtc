#!/usr/bin/env node
/* Candle date guardrail (9 Nov 2026): the live price may only be painted
   onto a candle whose Monday-Sunday range contains today (America/New_York).
   Loads the real assets/js/screener-indicator-chart.js in a vm sandbox.
   Run: node tests/test_candle_date_guardrail.js */
const fs = require('fs'), path = require('path'), vm = require('vm');
const R = path.join(__dirname, '..');
let n = 0, f = 0;
const chk = (name, ok, info) => { n++; if (!ok) { f++; console.log('FAIL', name, info === undefined ? '' : JSON.stringify(info)); } else console.log('PASS', name); };
const src = fs.readFileSync(path.join(R, 'assets/js/screener-indicator-chart.js'), 'utf8');
const doc = { addEventListener() {}, documentElement: { getAttribute: () => 'dark' }, getElementById: () => null,
  querySelectorAll: () => [], querySelector: () => null, createElement: () => ({ appendChild() {}, setAttribute() {}, style: {} }),
  createTextNode: () => ({}), body: { appendChild() {} } };
const win = { addEventListener() {}, psC: (d) => d, document: doc };
const sb = { window: win, document: doc, fetch: () => Promise.reject(new Error('no net')), console };
vm.createContext(sb); vm.runInContext(src, sb);
const IC = win.IndicatorChart;
const SD = (iso) => vm.runInContext('new Date(' + JSON.stringify(iso) + ')', sb);   // page-realm Date, like state.weeks
chk('exports guard helpers', ['weekCoversToday', 'liveWeekFor', 'etTodayISO'].every(k => typeof IC[k] === 'function'));

// Stale file: last week 2-8 Nov (TSLA final 358.22), today Mon 9 Nov 11:30 AM ET.
const stale = { monday: '2026-11-02', sunday: '2026-11-08', label: '2 Nov 2026 – 8 Nov 2026', days: 5, open: 404.66, high: 414.23, low: 338.15, close: 358.22, volume: 1 };
const cur = { monday: '2026-11-09', sunday: '2026-11-15', label: '9 Nov 2026 – 15 Nov 2026', days: 1, open: 360.25, high: 380.07, low: 360.02, close: 379.3, volume: 1 };
const mon1130 = Date.UTC(2026, 10, 9, 16, 30);   // Mon 9 Nov 11:30 AM EST
const live = 500;                                 // above high -> would move close + high
const sOut = IC.liveWeekFor(stale, live, mon1130);
chk('stale: same object returned (untouched)', sOut === stale);
chk('stale: close/high/low unchanged', sOut.close === 358.22 && sOut.high === 414.23 && sOut.low === 338.15);
chk('stale: not current (no live/in-progress mark)', IC.weekCoversToday(stale, mon1130) === false);
const lowLive = IC.liveWeekFor(stale, 100, mon1130);
chk('stale: low not extended either', lowLive.low === 338.15 && lowLive.close === 358.22);
// Same with loaded (Date) weeks, as state.weeks holds them.
const staleD = Object.assign({}, stale, { monday: SD(stale.monday), sunday: SD(stale.sunday) });
chk('stale (Date fields): untouched', IC.liveWeekFor(staleD, live, mon1130) === staleD);
chk('stale (Date fields): Sun 8 Nov still current', IC.weekCoversToday(staleD, Date.UTC(2026, 10, 8, 20, 0)) === true);

// Current file: 9-15 Nov, today 9 Nov -> normal update.
const cOut = IC.liveWeekFor(cur, live, mon1130);
chk('current: covers today', IC.weekCoversToday(cur, mon1130) === true);
chk('current: close = live, high extended, low kept', cOut !== cur && cOut.close === 500 && cOut.high === 500 && cOut.low === 360.02 && cOut.open === 360.25);
chk('current: shipped week not mutated', cur.close === 379.3 && cur.high === 380.07);
const curD = Object.assign({}, cur, { monday: SD(cur.monday), sunday: SD(cur.sunday) });
chk('current (Date fields): updates', IC.liveWeekFor(curD, 350, mon1130).low === 350);

// Unknown dates / unknown today -> fail closed.
chk('no monday: no live', IC.liveWeekFor(Object.assign({}, cur, { monday: undefined }), live, mon1130).close === 379.3);
chk('bad sunday: no live', IC.liveWeekFor(Object.assign({}, cur, { sunday: 'soon' }), live, mon1130).close === 379.3);
chk('invalid Date: no live', IC.liveWeekFor(Object.assign({}, cur, { monday: SD('x') }), live, mon1130).close === 379.3);
chk('monday after sunday: no live', IC.weekCoversToday({ monday: '2026-11-15', sunday: '2026-11-09' }, mon1130) === false);
chk('NaN now: no live', IC.liveWeekFor(cur, live, NaN).close === 379.3);
chk('null week: safe', IC.liveWeekFor(null, live, mon1130) === null && IC.weekCoversToday(null, mon1130) === false);

// Sunday/Monday boundary, ET calendar date (EST = UTC-5 in Nov).
const sun2359 = Date.UTC(2026, 10, 9, 4, 59);   // Sun 8 Nov 11:59 PM ET (already Mon in UTC)
const mon0000 = Date.UTC(2026, 10, 9, 5, 0);    // Mon 9 Nov 12:00 AM ET
chk('ET today Sun 11:59 PM = 2026-11-08', IC.etTodayISO(sun2359) === '2026-11-08');
chk('boundary Sun 11:59 PM ET: old week still current', IC.weekCoversToday(stale, sun2359) === true && IC.weekCoversToday(cur, sun2359) === false);
chk('boundary Mon 12:00 AM ET: old week frozen', IC.weekCoversToday(stale, mon0000) === false && IC.liveWeekFor(stale, live, mon0000) === stale);
chk('boundary Mon 12:00 AM ET: new week current', IC.weekCoversToday(cur, mon0000) === true);
chk('Monday itself inside range', IC.weekCoversToday(cur, Date.UTC(2026, 10, 9, 14, 30)) === true);
chk('Sunday itself inside range', IC.weekCoversToday(cur, Date.UTC(2026, 10, 15, 20, 0)) === true);
// DST side: Sun 1 Nov 11:30 PM EST (04:30Z Mon 2 Nov) is still 1 Nov in ET.
chk('ET date across DST end', IC.etTodayISO(Date.UTC(2026, 10, 2, 4, 30)) === '2026-11-01');
chk('summer EDT offset', IC.etTodayISO(Date.UTC(2026, 6, 6, 3, 30)) === '2026-07-05');

// Source audit: every live-to-candle site goes through the guard.
const calls = (src.match(/applyLiveWeek\(/g) || []).length;
chk('applyLiveWeek only defined + called inside liveWeekFor', calls === 2, calls);
chk('isLiveCandle guarded', /isLiveCandle = state\.liveOn && isInProgress\(\) && i === n - 1 && weekCoversToday\(w\)/.test(src));
chk('in-progress line label guarded', /\(in progress\)'/.test(src) && /progressNote\) && weekCoversToday\(dw\[n - 1\]\)\) curLab/.test(src));
chk('pill live/in-progress notes guarded', /var lastCur = isLast && weekCoversToday\(w\)/.test(src) && !/if \(isLast && state\.(liveOn|cfg\.lastInProgress|progressNote)/.test(src.replace(/else if \(isLast && state/g, 'X')) && !/else if \(isLast && state\.(cfg\.lastInProgress|progressNote)/.test(src));
chk('subtitle in-progress note guarded', /state\.progressNote && Array\.isArray\(data\.weeks\) && weekCoversToday\(data\.weeks\[data\.weeks\.length - 1\]\)/.test(src));
chk('timezone stated in a comment', /TIMEZONE: "today" is the calendar date in America\/New_York/.test(src));

console.log(`\n${n - f}/${n} passed`);
process.exit(f ? 1 : 0);
