// Headless check for the SHIPPED aggDailyCandles in assets/js/btcchart.js.
// It extracts the function source from btcchart.js and evals it, so this test
// checks the real code, not a transcription. Run: node proposals/candle-ranges-day1/test-agg.js
var fs = require('fs');
var path = require('path');
var src = fs.readFileSync(path.join(__dirname, '..', '..', 'assets', 'js', 'btcchart.js'), 'utf8');
var m = src.match(/function aggDailyCandles\(daily,mode\)\{[\s\S]*?\n\}/);
if (!m) { console.error('FAIL: aggDailyCandles not found in btcchart.js'); process.exit(1); }
eval(m[0]);
var fails = 0;
function check(name, cond, extra) {
  if (cond) console.log('PASS ' + name);
  else { fails++; console.log('FAIL ' + name + (extra !== undefined ? ' :: ' + JSON.stringify(extra) : '')); }
}
// Daily candles: Mon 2026-10-19 .. Sun 2026-10-25 (UTC midnight stamps), then Mon 26.
// Values chosen so high/low/open/close are all distinguishable.
function day(y, mo, d, o, h, l, c) {
  return { t: Date.UTC(y, mo - 1, d), o: o, h: h, l: l, c: c };
}
var week1 = [
  day(2026, 10, 19, 100, 110, 95, 108),
  day(2026, 10, 20, 108, 115, 105, 112),
  day(2026, 10, 21, 112, 112, 90, 95),   // weekly low lives here
  day(2026, 10, 22, 95, 120, 94, 118),   // weekly high lives here
  day(2026, 10, 23, 118, 119, 110, 111),
  day(2026, 10, 24, 111, 113, 100, 102),
  day(2026, 10, 25, 102, 104, 99, 103)
];
var week2 = [day(2026, 10, 26, 103, 109, 101, 107), day(2026, 10, 27, 107, 108, 100, 101)];
var all = week1.concat(week2);

// 1. Daily mode is identity.
var d = aggDailyCandles(all, 'daily');
check('daily: same length', d.length === all.length, d.length);
check('daily: values preserved', d[2].o === 112 && d[2].h === 112 && d[2].l === 90 && d[2].c === 95, d[2]);
check('daily: end == start', d[0].end === d[0].t);

// 2. Weekly mode: two buckets (Oct 19-25, Oct 26-27 partial).
var w = aggDailyCandles(all, 'weekly');
check('weekly: 2 buckets', w.length === 2, w.length);
check('weekly[0]: open = first day open', w[0].o === 100, w[0]);
check('weekly[0]: close = last day close', w[0].c === 103, w[0]);
check('weekly[0]: high = max of day highs', w[0].h === 120, w[0]);
check('weekly[0]: low = min of day lows', w[0].l === 90, w[0]);
check('weekly[1]: partial week open/close/high/low', w[1].o === 103 && w[1].c === 101 && w[1].h === 109 && w[1].l === 100, w[1]);
check('weekly: buckets ordered by start', w[0].t < w[1].t);

// 3. Weekend days belong to the same Monday week (Sat/Sun do not split a bucket).
check('weekly[0]: spans Mon-Sun (7 days in, 1 bucket)', w[0].end - w[0].t === 6 * 864e5, w[0].end - w[0].t);

// 4. Edge cases.
check('empty input -> []', JSON.stringify(aggDailyCandles([], 'weekly')) === '[]');
check('single day weekly -> 1 bucket, identity values',
  (function () { var s = aggDailyCandles([day(2026, 10, 26, 50, 55, 48, 52)], 'weekly'); return s.length === 1 && s[0].o === 50 && s[0].h === 55 && s[0].l === 48 && s[0].c === 52; })());
check('unknown mode falls back to daily', aggDailyCandles(all, 'bogus').length === all.length);

console.log(fails === 0 ? 'ALL CHECKS PASSED' : fails + ' CHECKS FAILED');
process.exit(fails === 0 ? 0 : 1);
