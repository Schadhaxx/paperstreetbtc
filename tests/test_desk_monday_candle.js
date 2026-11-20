#!/usr/bin/env node
/* Desk Monday-candle append (16 Nov 2026): when the shipped weekly file
   still ends at last week, the modal appends the fresh desk-live candle
   as a new in-progress week — on the FIRST TRADING DAY of the week, not
   calendar Monday. A holiday Monday shifts it to Tuesday; Mon+Tue closed
   shifts it to Wednesday. There is NO holiday calendar: the desk-live
   feed is the signal (the job skips holidays, so on a closed day there
   is no fresh publish and the freshness guard fails closed; on the first
   trading day the fresh entry appears and the week it names — still
   dated to that week's Monday — appends). Loads the real
   assets/js/screener-indicator-chart.js in a vm sandbox.
   Run: node tests/test_desk_monday_candle.js */
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
chk('exports deskLiveNewWeek', typeof IC.deskLiveNewWeek === 'function');

// Shipped weeks (Date fields, as state.weeks holds them): last week 9-15 Nov.
const wk = (monday, sunday, close) => ({ monday: SD(monday), sunday: SD(sunday), label: monday + ' – ' + sunday, days: 5, open: 340, high: 360, low: 335, close: close, volume: 100 });
const shipped = [wk('2026-11-02', '2026-11-08', 344), wk('2026-11-09', '2026-11-15', 356.27)];
const ov = (asOfMs, days) => ({ monday: '2026-11-16', sunday: '2026-11-22', open: 357.1, high: 357.1, low: 352.8, close: 353.09, volume: 14955750, days: days === undefined ? 1 : days, asOfMs: asOfMs });

// (1) Normal Monday: Mon 16 Nov 12:45 PM ET, desk-live 5 min old -> appends.
const mon1245 = Date.UTC(2026, 10, 16, 17, 45);
const w1 = IC.deskLiveNewWeek(shipped, ov(mon1245 - 5 * 60000), mon1245);
chk('Monday: appends', w1 !== null);
chk('Monday: label', w1 && w1.label === '16 Nov 2026 – 22 Nov 2026');
chk('Monday: OHLC + days', w1 && w1.open === 357.1 && w1.high === 357.1 && w1.low === 352.8 && w1.close === 353.09 && w1.days === 1);
chk('Monday: shipped weeks not mutated', shipped.length === 2 && shipped[1].close === 356.27);
chk('Monday: appended week covers today + takes live paint', w1 && IC.weekCoversToday(w1, mon1245) === true && IC.liveWeekFor(w1, 360, mon1245).close === 360);
chk('Monday: appended week volume carried', w1 && w1.volume === 14955750);

// (2) Holiday Monday -> Tuesday: Tue 17 Nov 10:00 AM ET, fresh desk-live, days 1 -> appends.
const tue1000 = Date.UTC(2026, 10, 17, 15, 0);
chk('Tue after holiday Mon: appends', IC.deskLiveNewWeek(shipped, ov(tue1000 - 5 * 60000), tue1000) !== null);
// (3) Mon+Tue closed -> Wednesday: Wed 18 Nov 10:00 AM ET -> appends.
const wed1000 = Date.UTC(2026, 10, 18, 15, 0);
chk('Wed after Mon+Tue closed: appends', IC.deskLiveNewWeek(shipped, ov(wed1000 - 5 * 60000), wed1000) !== null);
// (4) The holiday itself: Mon 16 Nov 10:00 AM ET, desk-live last published Fri 13 Nov 4:45 PM ET -> no append.
const mon1000 = Date.UTC(2026, 10, 16, 15, 0);
const fri1645 = Date.UTC(2026, 10, 13, 21, 45);
chk('holiday Monday (stale desk-live): no append', IC.deskLiveNewWeek(shipped, ov(fri1645), mon1000) === null);
chk('no desk-live: no append', IC.deskLiveNewWeek(shipped, null, mon1245) === null);
// Sunday night before the new week: Sun 15 Nov 11:59 PM ET -> no append (week not started).
const sun2359 = Date.UTC(2026, 10, 16, 4, 59);
chk('Sunday night before: no append', IC.deskLiveNewWeek(shipped, ov(sun2359 - 5 * 60000), sun2359) === null);

// (5) File already has the current week: patch path owns it, no duplicate.
const shippedCur = [wk('2026-11-09', '2026-11-15', 356.27), wk('2026-11-16', '2026-11-22', 353.09)];
chk('current week already shipped: no append', IC.deskLiveNewWeek(shippedCur, ov(mon1245 - 5 * 60000), mon1245) === null);
// (6) File more than a week stale: gap -> fail closed.
const shippedOld = [wk('2026-10-26', '2026-11-01', 344), wk('2026-11-02', '2026-11-08', 344)];
chk('file two weeks stale: no append', IC.deskLiveNewWeek(shippedOld, ov(mon1245 - 5 * 60000), mon1245) === null);

// (7) Malformed entries -> fail closed.
const fresh = ov(mon1245 - 5 * 60000);
chk('bad sunday (missing): no append', IC.deskLiveNewWeek(shipped, Object.assign({}, fresh, { sunday: null }), mon1245) === null);
chk('bad sunday (before monday): no append', IC.deskLiveNewWeek(shipped, Object.assign({}, fresh, { sunday: '2026-11-15' }), mon1245) === null);
chk('bad monday (garbage): no append', IC.deskLiveNewWeek(shipped, Object.assign({}, fresh, { monday: 'soon' }), mon1245) === null);
chk('bad days (0): no append', IC.deskLiveNewWeek(shipped, ov(mon1245 - 5 * 60000, 0), mon1245) === null);
chk('bad days (6): no append', IC.deskLiveNewWeek(shipped, ov(mon1245 - 5 * 60000, 6), mon1245) === null);
chk('bad OHLC (high < open): no append', IC.deskLiveNewWeek(shipped, Object.assign({}, fresh, { high: 100 }), mon1245) === null);
chk('bad OHLC (low > close): no append', IC.deskLiveNewWeek(shipped, Object.assign({}, fresh, { low: 400 }), mon1245) === null);
chk('stale asOf (25 min): no append', IC.deskLiveNewWeek(shipped, ov(mon1245 - 25 * 60000), mon1245) === null);
chk('empty weeks: no append', IC.deskLiveNewWeek([], fresh, mon1245) === null);

console.log(n - f + '/' + n + ' passed');
if (f) process.exit(1);
