#!/usr/bin/env node
/* Stage 2 Step 2 (8 Nov 2026): structural guards for the native 1D line.
   Supersedes test_stage2_step1.js (the scaffold test — retired, the
   scaffold it checked no longer exists in that form).
   - draw1DNative is IMPLEMENTED (smooth curve, gradient fill, axes,
     labels, live "Now" point, tooltip); drawDailyNative is IMPLEMENTED
     in Step 3 (see test_stage2_step3.js) — this file keeps the 1D
     regression checks only.
   - NATIVE_LINE flag wires draw1D AND drawDaily to the native renderer;
     the Chart.js path stays as the fallback (both `new Chart(` call sites
     still exist).
   - Flag F1 resolved: clearLineChart() replaces the three bare
     `if(ch){ch.destroy();ch=null;}` sites; lineDrawn + redrawLine() exist;
     morph-done, onLive, and the resize listener all handle the native line.
   - Flag F5 resolved: uncapped DPR in draw1DNative (matches the candles).
   - Flag F6: the native line uses the hardcoded dark Chart.js colours.
   - No scroll trap: no `touch-action: none`, no `setPointerCapture`.
   - Pin bumped et24 -> et25 in Step 4 (panel content changed): all 16
     HTML callers pin et25, and the stub loads the panel with et25.
   - The YTD hero chart (s2.js) is out of scope: it must still use Chart.js.
*/
const fs = require('fs'), path = require('path');
const R = path.join(__dirname, '..');
let n = 0, f = 0;
const chk = (name, ok, info) => { n++; if (!ok) { f++; console.log('FAIL', name, info === undefined ? '' : JSON.stringify(info)); } else console.log('PASS', name); };

const panel = fs.readFileSync(path.join(R, 'assets/js/btcchart-panel.js'), 'utf8');
const stub = fs.readFileSync(path.join(R, 'assets/js/btcchart.js'), 'utf8');
const s2 = fs.readFileSync(path.join(R, 'assets/js/s2.js'), 'utf8');

/* Step 2 native section exists */
chk('panel has Stage 2 Step 2 native section', /Stage 2 native line renderer — Step 2: 1D line/.test(panel));
chk('panel has draw1DNative implemented', /function draw1DNative\(pts\)\{/.test(panel));
chk('draw1DNative returns true on success', /function draw1DNative\(pts\)\{[\s\S]*?return true;\n  \}catch/.test(panel));
chk('draw1DNative has no "not yet implemented" marker', !/function draw1DNative[\s\S]{0,400}not yet implemented/.test(panel));
chk('drawDailyNative implemented (Step 3 — see test_stage2_step3.js for detail)', /function drawDailyNative\(d,cmp\)\{[\s\S]*?Stage 2 Step 3 — implemented/.test(panel));
chk('panel has nativeNiceTicks implemented (Chart.js-faithful, plot-height tick limit)', /function nativeNiceTicks\(min,max,plotH\)\{[\s\S]*?Math\.pow\(10/.test(panel) && /function chartNiceNum\(x\)\{/.test(panel));
chk('panel has nativeTraceLine implemented (Chart.js splineCurve, Catmull-Rom)',
  /function nativeTraceLine\(ctx,xs,ys,tension,bounds\)\{[\s\S]*?bezierCurveTo/.test(panel) &&
  /var d01=Math\.sqrt\(Math\.pow\(cX-pX,2\)\+Math\.pow\(cY-pY,2\)\);/.test(panel) &&
  /ctx\.bezierCurveTo\(cp2x\[i\],cp2y\[i\],cp1x\[i\+1\],cp1y\[i\+1\],xs\[i\+1\],ys\[i\+1\]\);/.test(panel));
chk('panel has nativeGradientFill implemented', /function nativeGradientFill\(ctx,x,y,w,h\)\{[\s\S]*?createLinearGradient/.test(panel));
chk('panel has nativeTooltipBind implemented', /function nativeTooltipBind\(c\)\{[\s\S]*?addEventListener\('pointermove'/.test(panel));
chk('panel has nativeTooltipHide implemented', /function nativeTooltipHide\(\)\{[\s\S]*?lineHover=-1/.test(panel));
chk('panel has nativeResize implemented (rAF-coalesced)', /function nativeResize\(\)\{if\(nrRaf\)return;var f=function\(\)\{nrRaf=0;redrawLine\(\);\};nrRaf=window\.requestAnimationFrame\?window\.requestAnimationFrame\(f\):setTimeout\(f,16\);\}/.test(panel));
chk('pending resize frame cancelled by clearLineChart, both Chart.js fallbacks and close()', (panel.match(/cancelNativeResize\(\);/g)||[]).length === 4 && /function cancelNativeResize\(\)\{if\(nrRaf\)/.test(panel));
chk('panel has drawLineTooltip', /function drawLineTooltip\(ctx,p,px,py,W,padT,plotH\)/.test(panel));

/* NATIVE_LINE flag + wiring */
chk('panel has NATIVE_LINE flag (ON by default, 9 Nov 2026)', /var NATIVE_LINE=true;/.test(panel));
chk('draw1D routes to draw1DNative when NATIVE_LINE is true',
  /if\(NATIVE_LINE\)\{if\(ch\)\{ch\.destroy\(\);ch=null;\}nativeOK=draw1DNative\(pts\);lineDrawn=nativeOK;\}/.test(panel));
chk('draw1D falls back to Chart.js when native fails or flag is off',
  /if\(!nativeOK\)\{if\(ch\)ch\.destroy\(\);ch=new Chart\(c,\{type:'line'/.test(panel));
chk('draw1D guard relaxed for the native path (no Chart.js needed when native is on)',
  /function draw1D\(\)\{\n  if\(!NATIVE_LINE&&!window\.Chart\)return;/.test(panel));
chk('test hook P.setNativeLine exists', /P\.setNativeLine=function\(v\)\{NATIVE_LINE=!!v;/.test(panel));
chk('test hook window.__BTC_SET_NATIVE_LINE exists', /window\.__BTC_SET_NATIVE_LINE=P\.setNativeLine;/.test(panel));
chk('parity hook window.__BTC_LINE_LAYOUT exists', /window\.__BTC_LINE_LAYOUT=\{/.test(panel));
chk('debug hook window.__BTC_LINE_HOVER exists', /window\.__BTC_LINE_HOVER=lineHover;/.test(panel));
chk('x labels use the Chart.js step (no forced last label)', /var maxX=isPhone\(\)\?5:7,step=Math\.max\(1,Math\.ceil\(n\/maxX\)\),xIdx=\[\];/.test(panel));
chk('native draws vertical gridlines at the x ticks', /\/\* Vertical gridlines at each x tick \(Chart\.js scales\.x\.grid\)\. \*\/[\s\S]*?ctx\.beginPath\(\);ctx\.moveTo\(x,T\);ctx\.lineTo\(x,T\+ih\);ctx\.stroke\(\);/.test(panel));
chk('draw-failure isolation records __BTC_DRAWERR', /window\.__BTC_DRAWERR=\{where:'draw1DNative'/.test(panel));

/* Chart.js fallback still present */
const chartCalls = (panel.match(/ch=new Chart\(c,\{type:'line'/g) || []).length;
chk('both Chart.js call sites still exist as fallback (draw1D + drawDaily)', chartCalls === 2, 'found ' + chartCalls);
chk('drawDaily guard relaxed for the native path (no Chart.js needed when native is on)',
  /function drawDaily\(\)\{if\(!DATA\)return;if\(!NATIVE_LINE&&!window\.Chart\)return;/.test(panel));
chk('draw() still routes to draw1D/drawDaily', /function draw\(\)\{if\(rng==='1D'\)\{draw1D\(\);\}else/.test(panel));

/* Flag F1 — the ch tangle resolved */
chk('panel has clearLineChart helper', /function clearLineChart\(\)\{if\(ch\)\{ch\.destroy\(\);ch=null;\}lineDrawn=false;lineHover=-1;linePts=null;lineGeom=null;window\.__BTC_LINE_LAYOUT=null;window\.__BTC_LINE_HOVER=-1;cancelNativeResize\(\);\}/.test(panel));
chk('panel has lineDrawn flag', /var lineDrawn=false;/.test(panel));
chk('panel has redrawLine entry point', /function redrawLine\(\)\{if\(lineDrawn\)draw\(\);\}/.test(panel));
const bareCh = (panel.match(/\n\s*if\(ch\)\{ch\.destroy\(\);ch=null;\}\n/g) || []).length;
chk('no bare ch-destroy sites left outside clearLineChart (the native-branch one is inside the NATIVE_LINE branch)',
  bareCh === 0, 'found ' + bareCh);
chk('clearLineChart is called at all three former ch-destroy sites',
  (panel.match(/clearLineChart\(\);/g) || []).length === 3, 'found ' + (panel.match(/clearLineChart\(\);/g) || []).length);
chk('drawDaily clears the native line state', /function drawDaily\(\)\{if\(!DATA\)return;if\(!NATIVE_LINE&&!window\.Chart\)return;clearCandState\(\);lineDrawn=false;lineHover=-1;linePts=null;lineGeom=null;/.test(panel));
chk('morph-done handler redraws the native line', /if\(ch&&ch\.resize\)ch\.resize\(\);nativeResize\(\);\};/.test(panel));
chk('onLive redraws when the native line is showing', /if\(ch\|\|lineDrawn\|\|candViewActive\(\)\)draw\(\);/.test(panel));
chk('resize listener redraws the native line', /if\(candViewActive\(\)\)redrawCandles\(\);nativeResize\(\);\}\}\);/.test(panel));

/* Flag F5 — DPR uncapped in draw1DNative (matches the candles) */
chk('draw1DNative uses uncapped DPR (F5)', /function draw1DNative\(pts\)\{[\s\S]*?var dpr=window\.devicePixelRatio\|\|1;/.test(panel));
chk('draw1DNative does NOT cap DPR at 2', !/function draw1DNative\(pts\)\{[\s\S]*?Math\.min\(window\.devicePixelRatio/.test(panel));

/* Flag F6 — hardcoded dark Chart.js colours, not "improved" */
chk('native line colour is #22d3ee', /ctx\.strokeStyle='#22d3ee';ctx\.lineWidth=2;/.test(panel));
chk('native y labels are #9aa6bc', /ctx\.fillStyle=psC\('#9aa6bc','#475569'\);\n    ctx\.font='11px Inter, sans-serif';ctx\.textAlign='right'/.test(panel));
chk('native gridlines are rgba(255,255,255,.05)', /ctx\.strokeStyle=psC\('rgba\(255,255,255,\.05\)','rgba\(15,23,42,\.08\)'\);ctx\.fillStyle=psC\('#9aa6bc','#475569'\);/.test(panel));
chk('native gradient stops match the Chart.js fill', /g\.addColorStop\(0,'rgba\(34,211,238,\.28\)'\);[\s\S]*?g\.addColorStop\(1,'rgba\(34,211,238,0\)'\);/.test(panel));
chk('native line tension is .15 (not the YTD 0.3/0.25)', /nativeTraceLine\(ctx,xs,ys,\.15,\{l:L,t:T,r:L\+iw,b:T\+ih\}\)/.test(panel));

/* F3 — tooltip safety: no scroll trap */
chk('native tooltip never sets touch-action none', !/touchAction\s*=\s*['"]none['"]/.test(panel));
chk('native tooltip never calls setPointerCapture', !/setPointerCapture\s*\(/.test(panel));
chk('native tooltip gates on candViewActive', (panel.match(/if\(candViewActive\(\)\|\|!lineDrawn\)return;/g) || []).length >= 3);
chk('native tooltip dismisses on scroll', /window\.addEventListener\('scroll',function\(\)\{hide\(\);\}/.test(panel));
chk('native tooltip toggles off on same-point re-tap', /if\(downIdx===lineHover\)\{hide\(\);return;\}/.test(panel));
chk('native tooltip press-end is idempotent (pressDone guard — pointerup + touchend must not double-fire)',
  /var downX=0,downY=0,downIdx=-1,pressMoved=false,pressDone=false;/.test(panel) &&
  /function endLinePress\(\)\{\n    if\(pressDone\)return;/.test(panel) &&
  /downIdx=pick\(e\);pressMoved=false;pressDone=false;/.test(panel));

/* Untouched: candles, popup, data pipeline */
chk('panel keeps drawCandles1D', /function drawCandles1D\(/.test(panel));
chk('panel keeps drawCandlesRange', /function drawCandlesRange\(/.test(panel));
chk('panel keeps bindCandListeners', /function bindCandListeners\(/.test(panel));
chk('panel keeps endPress (round-3 pill fix)', /function endPress\(\)/.test(panel));
chk('panel keeps open/close/place', /function open\(from\)/.test(panel) && /function close\(\)/.test(panel) && /function place\(\)/.test(panel));
chk('panel keeps getData + getIntraday', /function getData\(\)/.test(panel) && /function getIntraday\(\)/.test(panel));
chk('panel keeps needChart', /function needChart\(\)/.test(panel));

/* Pin bumped et24 -> et25 in Step 4 (panel content changed) */
chk('stub loads the panel with et25', /btcchart-panel\.js\?v=et25/.test(stub));
chk('stub does not load the panel with et19', !/btcchart-panel\.js\?v=et19/.test(stub));
const pages = ['index.html', 'screener.html', 'compare/index.html', 'clock/index.html', 'recap/index.html',
  'recap/2026-01/index.html', 'recap/2026-02/index.html', 'recap/2026-03/index.html', 'recap/2026-04/index.html',
  'recap/2026-05/index.html', 'recap/2026-06/index.html', 'recap/2026-07/index.html', 'recap/2026-08/index.html',
  'recap/2026-09/index.html', 'recap/2026-10/index.html', 'recap/2026-11/index.html'];
let et25 = 0, other = [];
pages.forEach(function (p) {
  const html = fs.readFileSync(path.join(R, p), 'utf8');
  const m = html.match(/btcchart\.js\?v=([a-z0-9]+)/g) || [];
  m.forEach(function (x) { if (x === 'btcchart.js?v=et25') et25++; else other.push(p + ':' + x); });
});
chk('all 16 callers pin et25', et25 === 16 && other.length === 0, 'et25=' + et25 + ' other=' + JSON.stringify(other));

/* YTD hero chart out of scope: still Chart.js */
chk('s2.js still uses Chart.js (out of scope)', /new Chart\s*\(/.test(s2));

console.log('STAGE2 STEP2 TESTS', n, 'FAIL', f);
process.exit(f ? 1 : 0);
