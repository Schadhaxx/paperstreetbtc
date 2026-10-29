// Headless check for the 29 Oct 2026 1Y candle fix in assets/js/btcchart.js.
// Extracts loadExtendedDaily + fetchDailyWindow + mergeDailyCandles from the
// SHIPPED file (not transcriptions) and runs them against a stubbed fetch
// that returns one synthetic daily candle per UTC day in the requested
// window, so the coverage behaviour can be proven without a browser.
// Run: node proposals/candle-ranges-day2/test-1y-coverage.js
var fs = require('fs');
var path = require('path');
var src = fs.readFileSync(path.join(__dirname, '..', '..', 'assets', 'js', 'btcchart.js'), 'utf8');
function extract(re, name) {
  var m = src.match(re);
  if (!m) { console.error('FAIL: ' + name + ' not found in btcchart.js'); process.exit(1); }
  return m[0];
}
// The CBEXT state line, then the three functions, in dependency order.
eval(extract(/var CBEXT=null,CBEXT_P=null,CBEXT_P_DAYS=0,CBEXT_ERR=false,CBEXT_DAYS=0;/, 'CBEXT state'));
eval(extract(/function mergeDailyCandles\(chunks\)\{[\s\S]*?\n\}/, 'mergeDailyCandles'));
eval(extract(/function fetchDailyWindow\(startMs,endMs\)\{[\s\S]*?\n\}/, 'fetchDailyWindow'));
eval(extract(/function loadExtendedDaily\(days\)\{[\s\S]*?\n\}/, 'loadExtendedDaily'));

var fails = 0;
function check(name, cond, extra) {
  if (cond) console.log('PASS ' + name);
  else { fails++; console.log('FAIL ' + name + (extra !== undefined ? ' :: ' + JSON.stringify(extra) : '')); }
}
// Stub fetch: one candle per UTC day in [start, end), newest-first like
// Coinbase, in Coinbase array shape [time, low, high, open, close, volume].
// Price is the day index so opens/closes are distinguishable.
global.fetch = function (url) {
  var q = url.split('?')[1] || '';
  var params = {};
  q.split('&').forEach(function (kv) { var p = kv.split('='); params[p[0]] = decodeURIComponent(p[1]); });
  var s = Date.parse(params.start), e = Date.parse(params.end);
  var rows = [];
  for (var d = Math.floor(s / 864e5) * 864e5; d < e; d += 864e5) {
    var idx = Math.round(d / 864e5);
    rows.push([d / 1000, idx, idx + 10, idx + 2, idx + 5, 1]);
  }
  rows.reverse();
  return Promise.resolve({ ok: true, json: function () { return Promise.resolve(rows); } });
};

(async function () {
  var now = Date.now();
  // 1. YTD-sized load first (the browser-test sequence: YTD, then 1Y).
  var ytd = await loadExtendedDaily(302);
  check('YTD-sized load returns ~302 days', ytd.length >= 300 && ytd.length <= 303, ytd.length);
  check('CBEXT_DAYS records the YTD size', CBEXT_DAYS === 302, CBEXT_DAYS);
  // 2. The drawRange gate, as shipped, must now demand a reload for 1Y.
  var need = 366;
  check('gate: YTD set is insufficient for 1Y', !CBEXT || CBEXT_DAYS < need);
  check('shipped drawRange checks CBEXT_DAYS against need', /CBEXT_DAYS<need/.test(src));
  check('shipped drawRange shows a 1-year loading state', /Loading '\+\(rng==='YTD'\?'year-to-date':'1-year'\)\+' candles/.test(src));
  // 3. Loading 1Y after the YTD set genuinely covers Oct 2025.
  var full = await loadExtendedDaily(366);
  check('1Y load returns ~366 days', full.length >= 364 && full.length <= 367, full.length);
  check('1Y set covers now-366d', full[0].t <= now - 365 * 864e5, new Date(full[0].t).toISOString());
  check('1Y set ends at the latest complete day', full[full.length - 1].t > now - 2 * 864e5, new Date(full[full.length - 1].t).toISOString());
  check('CBEXT_DAYS records the 1Y size', CBEXT_DAYS === 366, CBEXT_DAYS);
  // 4. Monthly aggregation over the 1Y set: 13 buckets, last is October.
  eval(extract(/function aggDailyCandles\(daily,mode\)\{[\s\S]*?\n\}/, 'aggDailyCandles'));
  var mo = aggDailyCandles(full, 'monthly');
  check('1Y monthly: 13 buckets', mo.length === 13, mo.length);
  var last = mo[mo.length - 1];
  var ld = new Date(last.t);
  check('1Y monthly: last bucket is October (UTC)', ld.getUTCFullYear() === new Date(now).getUTCFullYear() && ld.getUTCMonth() === 9, last.t);
  // 5. The October label bug, demonstrated: UTC-midnight Oct 1 formats as
  // September in ET but October in UTC — the shipped pill/axis/header now
  // use UTC for range candles.
  var oct1 = Date.UTC(new Date(now).getUTCFullYear(), 9, 1);
  check('Oct 1 UTC formats as October in UTC', new Date(oct1).toLocaleDateString('en-US', { timeZone: 'UTC', month: 'long', year: 'numeric' }) === 'October ' + new Date(now).getUTCFullYear());
  check('Oct 1 UTC formats as September in ET (the old bug)', new Date(oct1).toLocaleDateString('en-US', { timeZone: 'America/New_York', month: 'long', year: 'numeric' }) === 'September ' + new Date(now).getUTCFullYear());
  check('shipped monthly pill uses UTC', /Monthly candle/.test(src) && /timeZone:'UTC',month:'long',year:'numeric'/.test(src));
  // 6. Pending-smaller chains to larger: reset state, start a 200-day load
  // without awaiting, then request 366 — the result must be the 366 set.
  CBEXT = null; CBEXT_P = null; CBEXT_P_DAYS = 0; CBEXT_ERR = false; CBEXT_DAYS = 0;
  var small = loadExtendedDaily(200);
  var chained = await loadExtendedDaily(366);
  await small;
  check('pending smaller load chains to the 366-day set', chained.length >= 364 && chained.length <= 367, chained.length);
  check('CBEXT_DAYS ends at 366 after chaining', CBEXT_DAYS === 366, CBEXT_DAYS);

  console.log(fails === 0 ? 'ALL CHECKS PASSED' : fails + ' CHECKS FAILED');
  process.exit(fails === 0 ? 0 : 1);
})().catch(function (e) { console.error('FAIL harness error: ' + (e && e.stack || e)); process.exit(1); });
