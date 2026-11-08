#!/usr/bin/env node
/* Stage 2 Step 1 (8 Nov 2026): structural guards for the native line renderer scaffold.
   - The scaffold section exists in btcchart-panel.js, with the two line-view stubs
     (draw1DNative, drawDailyNative) plus the shared helper stubs.
   - The stubs are inert: they contain "not yet implemented" and no `new Chart(`.
   - The Chart.js path is still active: both `new Chart(` call sites exist, draw()
     still routes to draw1D/drawDaily, NATIVE_LINE is false.
   - The candle views, popup logic, and data pipeline are untouched.
   - The panel pin stays et19 in all 16 HTML callers (test branch only; the panel
     is behaviourally unchanged — the scaffold adds dead code only).
   - The YTD hero chart (s2.js) is out of scope: it must still use Chart.js.
*/
const fs = require('fs'), path = require('path');
const R = path.join(__dirname, '..');
let n = 0, f = 0;
const chk = (name, ok, info) => { n++; if (!ok) { f++; console.log('FAIL', name, info === undefined ? '' : JSON.stringify(info)); } else console.log('PASS', name); };

const panel = fs.readFileSync(path.join(R, 'assets/js/btcchart-panel.js'), 'utf8');
const s2 = fs.readFileSync(path.join(R, 'assets/js/s2.js'), 'utf8');

/* Scaffold exists */
chk('panel has Stage 2 scaffold section', /Stage 2 native line renderer — Step 1 skeleton/.test(panel));
chk('panel has draw1DNative stub', /function draw1DNative\(pts\)/.test(panel));
chk('panel has drawDailyNative stub', /function drawDailyNative\(d,cmp\)/.test(panel));
chk('panel has nativeNiceTicks stub', /function nativeNiceTicks\(min,max,n\)/.test(panel));
chk('panel has nativeTraceLine stub', /function nativeTraceLine\(ctx,xs,ys,tension\)/.test(panel));
chk('panel has nativeGradientFill stub', /function nativeGradientFill\(ctx,x,y,w,h\)/.test(panel));
chk('panel has nativeTooltipBind stub', /function nativeTooltipBind\(c\)/.test(panel));
chk('panel has nativeTooltipHide stub', /function nativeTooltipHide\(\)/.test(panel));
chk('panel has nativeResize stub', /function nativeResize\(\)/.test(panel));
chk('panel has NATIVE_LINE flag', /var NATIVE_LINE=false;/.test(panel));

/* Stubs are inert: every stub body says "not yet implemented" */
const stubCount = (panel.match(/Stage 2 Step 1 — skeleton, not yet implemented \(Steps 2–3\)/g) || []).length;
chk('all 8 stubs marked not yet implemented', stubCount === 8, 'found ' + stubCount);
const scaffold = panel.slice(panel.indexOf('===== Stage 2 native line renderer'), panel.indexOf('===== end Stage 2 Step 1 skeleton ====='));
chk('scaffold contains no new Chart(', !/new Chart\s*\(/.test(scaffold));
chk('scaffold never sets touch-action none', !/touchAction\s*=\s*['"]none['"]/.test(scaffold));
chk('scaffold never calls setPointerCapture', !/setPointerCapture\s*\(/.test(scaffold));

/* Chart.js path still active */
const chartCalls = (panel.match(/ch=new Chart\(c,\{type:'line'/g) || []).length;
chk('both Chart.js call sites still exist (draw1D + drawDaily)', chartCalls === 2, 'found ' + chartCalls);
chk('draw1D still guards on window.Chart', /function draw1D\(\)\{\s*\n\s*if\(!window\.Chart\)return;/.test(panel));
chk('drawDaily still guards on window.Chart', /function drawDaily\(\)\{if\(!DATA\|\|!window\.Chart\)return;/.test(panel));
chk('draw() still routes to draw1D/drawDaily', /function draw\(\)\{if\(rng==='1D'\)\{draw1D\(\);\}/.test(panel));
chk('draw() does not call the native stubs', !/draw1DNative\(|drawDailyNative\(/.test(panel.replace(scaffold, '')));

/* Untouched: candles, popup, data pipeline */
chk('panel keeps drawCandles1D', /function drawCandles1D\(/.test(panel));
chk('panel keeps drawCandlesRange', /function drawCandlesRange\(/.test(panel));
chk('panel keeps bindCandListeners', /function bindCandListeners\(/.test(panel));
chk('panel keeps endPress (round-3 pill fix)', /function endPress\(\)/.test(panel));
chk('panel keeps open/close/place', /function open\(from\)/.test(panel) && /function close\(\)/.test(panel) && /function place\(\)/.test(panel));
chk('panel keeps getData + getIntraday', /function getData\(\)/.test(panel) && /function getIntraday\(\)/.test(panel));
chk('panel keeps needChart', /function needChart\(\)/.test(panel));

/* Pin stays et19 in all 16 callers */
const pages = ['index.html', 'screener.html', 'compare/index.html', 'clock/index.html', 'recap/index.html',
  'recap/2026-01/index.html', 'recap/2026-02/index.html', 'recap/2026-03/index.html', 'recap/2026-04/index.html',
  'recap/2026-05/index.html', 'recap/2026-06/index.html', 'recap/2026-07/index.html', 'recap/2026-08/index.html',
  'recap/2026-09/index.html', 'recap/2026-10/index.html', 'recap/2026-11/index.html'];
let et19 = 0, other = [];
pages.forEach(function (p) {
  const html = fs.readFileSync(path.join(R, p), 'utf8');
  const m = html.match(/btcchart\.js\?v=([a-z0-9]+)/g) || [];
  m.forEach(function (x) { if (x === 'btcchart.js?v=et19') et19++; else other.push(p + ':' + x); });
});
chk('all 16 callers still pin et19', et19 === 16 && other.length === 0, 'et19=' + et19 + ' other=' + JSON.stringify(other));

/* YTD hero chart out of scope: still Chart.js */
chk('s2.js still uses Chart.js (out of scope)', /new Chart\s*\(/.test(s2));

console.log('STAGE2 STEP1 TESTS', n, 'FAIL', f);
process.exit(f ? 1 : 0);
