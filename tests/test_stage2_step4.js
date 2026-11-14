#!/usr/bin/env node
/* Stage 2 Step 4 (8 Nov 2026): side-by-side parity — native line vs Chart.js.
   The rigorous browser comparison (50 views: every range x linear/log x
   comparisons x desktop/phone, probe_step4.py) found two real differences
   and both are fixed in the panel; this test locks the fixes in.
   - (a) Linear y-axis tick density: the old nativeNiceTicks target of 4 gave
     $1,000 steps on 1W (7 ticks) where Chart.js uses $500 (11 ticks), and
     $2,000 on 1M (7) where Chart.js uses $1,000 (11); YTD+SPX gave step 10
     (7 ticks) vs Chart.js step 5 (11). nativeNiceTicks now replicates
     Chart.js exactly: maxTicks = min(11, ceil(plotH/14.4)), step =
     chartNiceNum(span/(maxTicks-1)), with the single k>g recompute.
     The 13 cases below are the real data min/max from the shipped daily
     files (btc-daily.json end 2026-11-05, comparisons rebased to 100) and
     the 1D mock intraday closes, with the expected ticks read off live
     Chart.js in the browser probe. All 13 match Chart.js exactly.
   - (b) Log gridlines: Chart.js does NOT draw the minor 1/2/5 gridlines on
     non-compare log (only powers of 10); the native drew 19 rows. The log
     axis bounds now extend to the Chart.js tick grid (logGridCeil/Floor over
     significands 1..10,15,20 per decade) and a gridline is drawn only where
     the yTick callback returns a label (drawnY), so the drawn set matches
     Chart.js's autoSkip result in every observed view.
   - Tooltip values match Chart.js at the same index (verified in the
     browser probe: YTD $63,802 / $78,335 / $76,500, Max+all four lines
     identical incl. +109,285,614%, 1D $80,924 / $79,488 / $76,500). The
     1-3 index offsets at middle fractions in the probe are the pre-existing
     plot-box geometry difference (native plot is ~17px right / ~8px down /
     ~23px smaller than Chart.js's chartArea), not a tooltip difference.
   - Now point: livePrice updates on a live tick and the end tooltip shows
     the new price with the 'Now (live)' title (browser probe).
   - Pin bumped et24 -> et25 (panel content changed): all 16 HTML callers
     pin et25, and the stub loads the panel with et25.
   - The YTD hero chart (s2.js) is out of scope: it must still use Chart.js.
*/
const fs = require('fs'), path = require('path');
const R = path.join(__dirname, '..');
let n = 0, f = 0;
const chk = (name, ok, info) => { n++; if (!ok) { f++; console.log('FAIL', name, info === undefined ? '' : JSON.stringify(info)); } else console.log('PASS', name); };

const panel = fs.readFileSync(path.join(R, 'assets/js/btcchart-panel.js'), 'utf8');
const stub = fs.readFileSync(path.join(R, 'assets/js/btcchart.js'), 'utf8');
const s2 = fs.readFileSync(path.join(R, 'assets/js/s2.js'), 'utf8');

/* Extract the pure helpers from the panel source and eval them (same pattern
   the Step 2/3 tests use for structural checks, but behavioural here). */
function grab(name) {
  const i = panel.indexOf('function ' + name);
  if (i < 0) throw new Error('missing function ' + name);
  const j = panel.indexOf('{', i);
  let depth = 0, k = j;
  while (true) { const c = panel[k]; if (c === '{') depth++; else if (c === '}') { depth--; if (depth === 0) break; } k++; }
  return panel.slice(i, k + 1);
}
const sigMatch = panel.match(/var LOG_SIG=\[[^\]]+\];/);
if (!sigMatch) throw new Error('missing LOG_SIG');
eval(sigMatch[0] + '\n' + grab('chartNiceNum') + '\n' + grab('nativeNiceTicks') + '\n' + grab('logGridCeil') + '\n' + grab('logGridFloor'));
const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b);

/* (a) Linear ticks — 13 cases, real data min/max, expected = live Chart.js.
   plotH 318 is the native desktop plot height (both desktop and phone give
   maxTicks 11: ceil(318/14.4)=23 and ceil(319/14.4)=23, capped at 11). */
const LIN = [
  ['1W', 75942.12, 80405.29, [75500, 76000, 76500, 77000, 77500, 78000, 78500, 79000, 79500, 80000, 80500]],
  ['1M', 75942.12, 84011.97, [75000, 76000, 77000, 78000, 79000, 80000, 81000, 82000, 83000, 84000, 85000]],
  ['3M', 62818.65, 86602.91, [60000, 65000, 70000, 75000, 80000, 85000, 90000]],
  ['6M', 58558.86, 86602.91, [55000, 60000, 65000, 70000, 75000, 80000, 85000, 90000]],
  ['YTD', 58558.86, 96929.33, [55000, 60000, 65000, 70000, 75000, 80000, 85000, 90000, 95000, 100000]],
  ['1Y', 58558.86, 105996.59, [50000, 60000, 70000, 80000, 90000, 100000, 110000]],
  ['5Y', 15787.28, 124752.53, [0, 20000, 40000, 60000, 80000, 100000, 120000, 140000]],
  ['10Y', 702.03, 124752.53, [0, 20000, 40000, 60000, 80000, 100000, 120000, 140000]],
  ['Max', 0.06, 124752.53, [0, 20000, 40000, 60000, 80000, 100000, 120000, 140000]],
  ['1D', 75126.65, 81780.75, [75000, 76000, 77000, 78000, 79000, 80000, 81000, 82000]],
  ['YTD+SPX', 66.9177, 114.22, [65, 70, 75, 80, 85, 90, 95, 100, 105, 110, 115]],
  ['YTD+GLD', 66.9177, 122.5127, [60, 70, 80, 90, 100, 110, 120, 130]],
  ['Max+ALL', 85.6677, 178217900, [0, 20000000, 40000000, 60000000, 80000000, 100000000, 120000000, 140000000, 160000000, 180000000]],
];
LIN.forEach(function (c) {
  chk('linear ticks match Chart.js: ' + c[0], eq(nativeNiceTicks(c[1], c[2], 318), c[3]),
    { got: nativeNiceTicks(c[1], c[2], 318), want: c[3] });
});
/* The 1W case is the regression that motivated the fix: the old target-of-4
   gave $1,000 steps (7 ticks); Chart.js uses $500 (11 ticks). */
chk('1W uses $500 steps (11 ticks), not the old $1,000/7',
  nativeNiceTicks(75942.12, 80405.29, 318).length === 11 &&
  nativeNiceTicks(75942.12, 80405.29, 318)[1] - nativeNiceTicks(75942.12, 80405.29, 318)[0] === 500);
/* The k>g recompute cases (1Y, 5Y, 10Y, Max, Max+ALL) must not exceed 11 ticks. */
['1Y', '5Y', '10Y', 'Max', 'Max+ALL'].forEach(function (nm) {
  const c = LIN.filter(function (x) { return x[0] === nm; })[0];
  chk('k>g recompute keeps ' + nm + ' at <=11 ticks', nativeNiceTicks(c[1], c[2], 318).length <= 11);
});
/* chartNiceNum is Chart.js function B exactly. */
chk('chartNiceNum(665.41) = 1000 (1D step)', chartNiceNum(665.41) === 1000);
chk('chartNiceNum(4.8) = 5 (YTD+SPX step)', chartNiceNum(4.8) === 5);
chk('chartNiceNum(48.22) = 50 (span/10 for YTD+SPX, then recompute to 5)', chartNiceNum(48.22) === 50);
chk('nativeNiceTicks signature takes the plot height (Chart.js tick limit)', /function nativeNiceTicks\(min,max,plotH\)\{/.test(panel));
chk('nativeNiceTicks uses maxTicks = min(11, ceil(plotH/14.4))', /Math\.min\(11,Math\.ceil\(\(plotH\|\|320\)\/14\.4\)\)/.test(panel));
chk('nativeNiceTicks recomputes the step when the tick count exceeds maxTicks-1', /if\(k>g\)step=chartNiceNum\(k\*step\/g\);/.test(panel));

/* (b) Log grid bounds — the Chart.js tick grid (wo: significands 1..10,15,20). */
chk('logGridCeil(124752.53) = 150000 (Max-log axis max)', logGridCeil(124752.53) === 150000);
chk('logGridCeil(180000000) = 200000000 (Max-log+compare axis max)', logGridCeil(180000000) === 200000000);
chk('logGridFloor(15787.28) = 10000 (5Y-log axis min)', logGridFloor(15787.28) === 10000);
chk('logGridFloor(702.03) = 700 (10Y-log axis min)', logGridFloor(702.03) === 700);
chk('logGridFloor(0.06) = 0.06 (Max-log axis min; 6e-2 is on the grid)', logGridFloor(0.06) === 0.06);
chk('logGridCeil(0.06) = 0.06 (already on the grid)', logGridCeil(0.06) === 0.06);
chk('LOG_SIG is the Chart.js log tick grid (1..10, 15, 20)', eq(LOG_SIG, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 20]));
/* Gridlines only where a label is drawn (Chart.js autoSkip removes the rest). */
chk('log axis bounds extend to the grid before the log mapping',
  /if\(!\(lo>0\)\)lo=1;\n      lo=logGridFloor\(lo\);hi=logGridCeil\(hi\);/.test(panel));
chk('Y gridline/label loop skips ticks the yTick callback nulls',
  /var s=yTickDaily\(v,sx,LOG\);\n      if\(s==null\)return;\n      drawnY\.push\(v\);/.test(panel));
chk('drawn y-ticks are collected and reported in the layout hook',
  /drawnY\.push\(v\)/.test(panel) && /yTicks:drawnY/.test(panel));
chk('yTickDaily comment records that null = no label and no gridline',
  /null = no label and no gridline/.test(panel));

/* Tooltip values + Now point (structural; values verified in the browser probe). */
chk('drawDailyTooltip shows Now (live) on the last point', /'Now \(live\) · '\+d\[i\]\[0\]/.test(panel));
chk('drawDailyTooltip shows each comparison line with % change', /'S&P 500 '\+cmp\.S\[i\]\.toLocaleString/.test(panel) && /'Gold '\+curSym\(\)\+curVal\(cmp\.G\[i\]\)/.test(panel) && /'MSTR '\+curSym\(\)\+curVal\(cmp\.M\[i\]\)/.test(panel));
chk('draw1D tooltip shows Now (live) on the last point', /'Now \(live\)'/.test(panel));
chk('live Now point is drawn on the BTC line when hasLive', /hasLive/.test(panel) && /Now/.test(panel));

/* Pin bumped et24 -> et25 (panel content changed in Step 4). */
chk('stub loads the panel with et25', /btcchart-panel\.js\?v=et25/.test(stub));
const fs2 = require('fs');
const html = [];
function walk(d) {
  fs2.readdirSync(d).forEach(function (e) {
    const p = path.join(d, e);
    if (fs2.statSync(p).isDirectory()) { if (e !== 'node_modules' && e !== '.git') walk(p); }
    else if (/\.html$/.test(e)) html.push(p);
  });
}
walk(R);
let et25 = 0, other = [];
html.forEach(function (p) {
  const s = fs2.readFileSync(p, 'utf8');
  const m = s.match(/btcchart\.js\?v=([a-z0-9]+)/g) || [];
  m.forEach(function (x) { if (x === 'btcchart.js?v=et25') et25++; else other.push(p + ':' + x); });
});
chk('all 16 callers pin et25', et25 === 16 && other.length === 0, 'et25=' + et25 + ' other=' + JSON.stringify(other));

/* YTD hero chart (s2.js) is out of scope: it must still use Chart.js. */
chk('s2.js (YTD hero) still uses Chart.js', /new Chart\(/.test(s2));

console.log('\n' + n + ' checks, ' + f + ' failed');
process.exit(f ? 1 : 0);
