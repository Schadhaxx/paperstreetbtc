// Headless check for Day 2 candle-ranges code in assets/js/btcchart.js.
// Extracts aggDailyCandles + mergeDailyCandles from the SHIPPED file (not a
// transcription) and checks monthly aggregation, weekly aggregation over a
// 3M-style window, batched-window merge/dedup/sort, and edge cases.
// Run: node proposals/candle-ranges-day2/test-agg-day2.js
var fs = require('fs');
var path = require('path');
var src = fs.readFileSync(path.join(__dirname, '..', '..', 'assets', 'js', 'btcchart.js'), 'utf8');
var m = src.match(/function aggDailyCandles\(daily,mode\)\{[\s\S]*?\n\}/);
if (!m) { console.error('FAIL: aggDailyCandles not found in btcchart.js'); process.exit(1); }
eval(m[0]);
var m2 = src.match(/function mergeDailyCandles\(chunks\)\{[\s\S]*?\n\}/);
if (!m2) { console.error('FAIL: mergeDailyCandles not found in btcchart.js'); process.exit(1); }
eval(m2[0]);
var fails = 0;
function check(name, cond, extra) {
  if (cond) console.log('PASS ' + name);
  else { fails++; console.log('FAIL ' + name + (extra !== undefined ? ' :: ' + JSON.stringify(extra) : '')); }
}
function day(y, mo, d, o, h, l, c) {
  return { t: Date.UTC(y, mo - 1, d), o: o, h: h, l: l, c: c };
}
// Two calendar months: Sep 28-30 + Oct 1-3, 2026, values distinguishable.
var sepOct = [
  day(2026, 9, 28, 100, 110, 95, 108),
  day(2026, 9, 29, 108, 115, 105, 112),
  day(2026, 9, 30, 112, 112, 90, 95),   // September low lives here
  day(2026, 10, 1, 95, 120, 94, 118),   // October high lives here
  day(2026, 10, 2, 118, 119, 110, 111),
  day(2026, 10, 3, 111, 113, 100, 102)
];

// 1. Monthly aggregation: exactly 2 buckets, calendar-month boundaries.
var mo = aggDailyCandles(sepOct, 'monthly');
check('monthly: 2 buckets', mo.length === 2, mo.length);
check('monthly[0] (Sep): open = Sep 28 open', mo[0].o === 100, mo[0]);
check('monthly[0] (Sep): close = Sep 30 close', mo[0].c === 95, mo[0]);
check('monthly[0] (Sep): high = max of Sep highs', mo[0].h === 115, mo[0]);
check('monthly[0] (Sep): low = min of Sep lows', mo[0].l === 90, mo[0]);
check('monthly[0]: spans Sep 28-30', mo[0].end - mo[0].t === 2 * 864e5, mo[0].end - mo[0].t);
check('monthly[1] (Oct): open/close/high/low', mo[1].o === 95 && mo[1].c === 102 && mo[1].h === 120 && mo[1].l === 94, mo[1]);
check('monthly: buckets ordered', mo[0].t < mo[1].t);

// 2. Monthly: partial month at the window edge stays partial, never padded.
var partial = aggDailyCandles([day(2026, 10, 26, 50, 55, 48, 52), day(2026, 10, 27, 52, 53, 49, 51)], 'monthly');
check('monthly partial: 1 bucket, correct values', partial.length === 1 && partial[0].o === 50 && partial[0].c === 51 && partial[0].h === 55 && partial[0].l === 48, partial);

// 3. Monthly: month boundary is UTC, not ET — Oct 1 00:00 UTC is still
// Sep 30 evening in ET, but must start the October bucket.
var utcEdge = aggDailyCandles([day(2026, 9, 30, 10, 11, 9, 10), day(2026, 10, 1, 10, 12, 10, 11)], 'monthly');
check('monthly UTC boundary: Oct 1 UTC starts a new bucket', utcEdge.length === 2, utcEdge.length);

// 4. Weekly still correct over a longer (3M-style) window: 3 full weeks.
var threeWeeks = [];
for (var w = 0; w < 3; w++) {
  for (var d = 0; d < 7; d++) {
    var base = 100 + w * 10 + d;
    threeWeeks.push(day(2026, 10, 5 + w * 7 + d, base, base + 5, base - 5, base + 1));
  }
}
var wk = aggDailyCandles(threeWeeks, 'weekly');
check('weekly 3-week window: 3 buckets', wk.length === 3, wk.length);
check('weekly[1]: open = first day, close = last day', wk[1].o === 110 && wk[1].c === 117, wk[1]);
check('weekly[1]: high/low span the week', wk[1].h === 121 && wk[1].l === 105, wk[1]);

// 5. Batched merge: overlapping windows, shared boundary day deduped
// (later window wins), result sorted oldest-first, no duplicates.
var winA = [day(2026, 1, 1, 10, 11, 9, 10), day(2026, 1, 2, 10, 11, 9, 10), day(2026, 1, 3, 10, 11, 9, 10)];
var winB = [day(2026, 1, 3, 20, 22, 19, 21), day(2026, 1, 4, 21, 23, 20, 22)];
var merged = mergeDailyCandles([winA, winB]);
check('merge: 4 unique days, not 5', merged.length === 4, merged.length);
check('merge: boundary day from later window', merged[2].o === 20 && merged[2].c === 21, merged[2]);
check('merge: sorted oldest-first', merged[0].t < merged[1].t && merged[1].t < merged[2].t && merged[2].t < merged[3].t, merged.map(function (p) { return p.t; }));
check('merge: out-of-order input still sorted', (function () {
  var rev = mergeDailyCandles([[day(2026, 1, 4, 1, 2, 1, 1)], [day(2026, 1, 1, 1, 2, 1, 1)]]);
  return rev.length === 2 && rev[0].t < rev[1].t;
})());
check('merge: empty chunks -> []', JSON.stringify(mergeDailyCandles([[], []])) === '[]');

// 6. Regression: daily identity and weekly behaviour unchanged by Day 2.
var d = aggDailyCandles(sepOct, 'daily');
check('daily regression: identity', d.length === sepOct.length && d[0].o === 100 && d[5].c === 102, d.length);
check('monthly empty -> []', JSON.stringify(aggDailyCandles([], 'monthly')) === '[]');

console.log(fails === 0 ? 'ALL CHECKS PASSED' : fails + ' CHECKS FAILED');
process.exit(fails === 0 ? 0 : 1);
