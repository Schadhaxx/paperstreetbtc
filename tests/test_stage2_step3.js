#!/usr/bin/env node
/* Stage 2 Step 3 (8 Nov 2026): structural guards for the native range line.
   - drawDailyNative is IMPLEMENTED (daily closes 1W-Max, S&P/Gold/MSTR
     comparisons rebased to 100, linear/log scale, axes, labels, tooltip).
   - NATIVE_LINE flag wires drawDaily to the native renderer; the Chart.js
     path stays as the fallback (both `new Chart(` call sites still exist).
   - Comparison rebasing: BTC 100*p/a, S&P 100*v/s0, Gold 100*v/g0,
     MSTR 100*v/m0. Log scale: log10 mapping, ticks at 1/2/5 x 10^k,
     labels only where the yTick callback passes.
   - spanGaps: S&P and MSTR bridge nulls (one path); Gold breaks at nulls.
   - Fill only when non-compare AND linear (Chart.js fill:!LOG, fill:false
     when comparing). Live "Now" dot on the BTC line when hasLive.
   - Tooltip follows the round-3 press-end model (shared nativeTooltipBind)
     and is inert during candle views (F3); the show/hide redraw dispatches
     on the layout kind (redrawNativeLine), guarded on lineDrawn so a scroll
     after switching back to the Chart.js fallback cannot repaint the
     native line over it.
   - Pin bumped et24 -> et24 (rebase onto main; main also used et24) in Step 4 (panel content changed): all 16
     HTML callers pin et24, and the stub loads the panel with et24.
   - The YTD hero chart (s2.js) is out of scope: it must still use Chart.js.
*/
const fs = require('fs'), path = require('path');
const R = path.join(__dirname, '..');
let n = 0, f = 0;
const chk = (name, ok, info) => { n++; if (!ok) { f++; console.log('FAIL', name, info === undefined ? '' : JSON.stringify(info)); } else console.log('PASS', name); };

const panel = fs.readFileSync(path.join(R, 'assets/js/btcchart-panel.js'), 'utf8');
const stub = fs.readFileSync(path.join(R, 'assets/js/btcchart.js'), 'utf8');
const s2 = fs.readFileSync(path.join(R, 'assets/js/s2.js'), 'utf8');

/* Step 3 native section exists */
chk('panel has drawDailyNative implemented', /function drawDailyNative\(d,cmp\)\{/.test(panel));
chk('drawDailyNative returns true on success', /function drawDailyNative\(d,cmp\)\{[\s\S]*?return true;\n  \}catch/.test(panel));
chk('drawDailyNative has no "not yet implemented" marker', !/function drawDailyNative[\s\S]{0,400}not yet implemented/.test(panel));
chk('panel has yTickDaily (Chart.js yTick callback replicated)', /function yTickDaily\(v,sx,log\)\{/.test(panel));
chk('yTickDaily replicates the compare % format', /var q=v-100;return \(q>0\?'\+':'\'\)\+\(Math\.abs\(q\)>=1000\?Math\.round\(q\)\.toLocaleString\('en-US'\):Math\.round\(q\)\)\+'%';/.test(panel));
chk('yTickDaily replicates the log mantissa filter', /\[1,2,5\]\.indexOf\(Math\.round\(m\*1000\)\/1000\)<0/.test(panel));
chk('yTickDaily replicates the log power-of-10 filter', /Math\.abs\(l-Math\.round\(l\)\)>1e-6/.test(panel));
chk('panel has drawDailyTooltip', /function drawDailyTooltip\(ctx,i,d,cmp,reb,xs,ysMap,W,padT,plotH\)/.test(panel));
chk('drawDailyTooltip shows Now (live) on the last point', /'Now \(live\) · '\+d\[i\]\[0\]/.test(panel));
chk('drawDailyTooltip shows each comparison line with % change', /'S&P 500 '\+cmp\.S\[i\]\.toLocaleString/.test(panel) && /'Gold '\+curSym\(\)\+curVal\(cmp\.G\[i\]\)/.test(panel) && /'MSTR '\+curSym\(\)\+curVal\(cmp\.M\[i\]\)/.test(panel));
chk('drawDailyTooltip draws colour chips in compare mode', /ctx\.fillRect\(lx,ty\+6\+j\*14\+2,8,8\)/.test(panel));
chk('panel has redrawNativeLine dispatcher', /function redrawNativeLine\(\)\{/.test(panel));
chk('redrawNativeLine guards on lineDrawn', /function redrawNativeLine\(\)\{\n  if\(!lineDrawn\|\|!lineGeom\)return;/.test(panel));
chk('redrawNativeLine dispatches on layout kind', /if\(lineGeom\.kind==='daily'&&linePts&&linePts\.d\)drawDailyNative\(linePts\.d,linePts\.cmp\);/.test(panel));
chk('tooltip show/hide redraw via redrawNativeLine', /function show\(i\)\{if\(i===lineHover\)return;lineHover=i;redrawNativeLine\(\);\}/.test(panel) && /function hide\(\)\{if\(lineHover===-1\)return;lineHover=-1;redrawNativeLine\(\);\}/.test(panel));
chk('nativeTooltipHide redraws via redrawNativeLine', /function nativeTooltipHide\(\)\{\n  if\(lineHover===-1\)return;\n  lineHover=-1;\n  redrawNativeLine\(\);\n\}/.test(panel));
chk('draw1DNative layout carries kind 1d', /lineGeom=\{kind:'1d',pad/.test(panel));
chk('drawDailyNative layout carries kind daily', /lineGeom=\{kind:'daily',pad/.test(panel));

/* NATIVE_LINE flag + wiring for the range views */
chk('drawDaily routes to drawDailyNative when NATIVE_LINE is true',
  /if\(NATIVE_LINE\)\{if\(ch\)\{ch\.destroy\(\);ch=null;\}nativeOK=drawDailyNative\(d,\{sx:sx,S:S,G:G,M:M,s0:s0,g0:g0,m0:m0,hasLive:hasLive,log:LOG\}\);lineDrawn=nativeOK;\}/.test(panel));
chk('drawDaily falls back to Chart.js when native fails or flag is off',
  /if\(!nativeOK\)\{if\(ch\)ch\.destroy\(\);ch=new Chart\(c,\{type:'line',data:\{labels:lab,datasets:ds\},options:opts\}\);lineDrawn=false;window\.__BTC_LINE_LAYOUT=null;window\.__BTC_LINE_HOVER=-1;cancelNativeResize\(\);\}\}/.test(panel));
chk('drawDaily guard relaxed for the native path (no Chart.js needed when native is on)',
  /function drawDaily\(\)\{if\(!DATA\)return;if\(!NATIVE_LINE&&!window\.Chart\)return;/.test(panel));
chk('draw-failure isolation records __BTC_DRAWERR for the daily line', /window\.__BTC_DRAWERR=\{where:'drawDailyNative'/.test(panel));

/* Comparison rebasing + log scale */
chk('BTC rebased to 100 at the first close', /btcY=d\.map\(function\(p\)\{return 100\*p\[1\]\/a;\}\);/.test(panel));
chk('S&P rebased to 100 at its first non-null value', /spxY=cmp\.S\?cmp\.S\.map\(function\(v\)\{return v!=null&&cmp\.s0\?100\*v\/cmp\.s0:null;\}\):null;/.test(panel));
chk('Gold rebased to 100 at its first non-null value', /gldY=cmp\.G\?cmp\.G\.map\(function\(v\)\{return v!=null&&cmp\.g0\?100\*v\/cmp\.g0:null;\}\):null;/.test(panel));
chk('MSTR rebased to 100 at its first non-null value', /mstrY=cmp\.M\?cmp\.M\.map\(function\(v\)\{return v!=null&&cmp\.m0\?100\*v\/cmp\.m0:null;\}\):null;/.test(panel));
chk('log scale maps log10 values to the plot', /Y=function\(v\)\{return T\+ih\*\(1-\(Math\.log10\(v\)-llo\)\/\(lhi-llo\)\);};/.test(panel));
chk('log ticks at 1/2/5 x 10^k within range', /\[1,2,5\]\.forEach\(function\(m\)\{var tv=m\*pw;if\(tv>=lo\*\(1-1e-9\)&&tv<=hi\*\(1\+1e-9\)\)yTicks\.push\(tv\);\}\);/.test(panel));
chk('y-axis label margin: longest label measured and L widened (Max+compare labels fit)', /maxLabW/.test(panel) && /Math\.max\(62,Math\.ceil\(maxLabW\)\+12\)/.test(panel));
chk('y-axis label margin: comment explains the Max+compare clipping fix', /sizes the left margin to fit the widest y-axis label/.test(panel));
chk('linear scale uses nativeNiceTicks with the plot height (Chart.js tick limit)', /var ticks=nativeNiceTicks\(lo,hi,ih\);/.test(panel));
chk('x labels show the year for n>400, else month-day', /n>400\?lab\[i\]\.slice\(0,4\):lab\[i\]\.slice\(5\)/.test(panel));

/* spanGaps + fill + dots */
chk('S&P and MSTR bridge nulls (spanGaps true)', /traceDS\(spxYs,true\)/.test(panel) && /traceDS\(mstrYs,true\)/.test(panel));
chk('Gold breaks at nulls (spanGaps false)', /traceDS\(gldYs,false\)/.test(panel));
chk('fill only when non-compare and linear', /if\(!sx&&!LOG\)\{/.test(panel));
chk('comparison line colours match Chart.js', /ctx\.strokeStyle='#c4b5fd';ctx\.lineWidth=1\.6;traceDS\(spxYs,true\);/.test(panel) && /ctx\.strokeStyle='#facc15';ctx\.lineWidth=1\.6;traceDS\(gldYs,false\);/.test(panel) && /ctx\.strokeStyle='#f97316';ctx\.lineWidth=1\.6;traceDS\(mstrYs,true\);/.test(panel));
chk('live Now dot on the BTC line when hasLive', /if\(hasLive\)\{ctx\.beginPath\(\);ctx\.arc\(xs\[n-1\],btcYs\[n-1\],4,0,Math\.PI\*2\);ctx\.fillStyle='#22d3ee';ctx\.fill\(\);\}/.test(panel));
chk('hovered dots on every visible dataset at the hovered index', /var dots=\[\['#22d3ee',btcYs\],\['#c4b5fd',spxYs\],\['#facc15',gldYs\],\['#f97316',mstrYs\]\];/.test(panel));
chk('daily parity hook carries kind, sx and log', /window\.__BTC_LINE_LAYOUT=\{kind:'daily'/.test(panel) && /sx:sx,log:LOG\};/.test(panel));

/* Chart.js fallback still present */
const chartCalls = (panel.match(/ch=new Chart\(c,\{type:'line'/g) || []).length;
chk('both Chart.js call sites still exist as fallback (draw1D + drawDaily)', chartCalls === 2, 'found ' + chartCalls);

/* F3 — tooltip safety: no scroll trap */
chk('native tooltip never sets touch-action none', !/touchAction\s*=\s*['"]none['"]/.test(panel));
chk('native tooltip never calls setPointerCapture', !/setPointerCapture\s*\(/.test(panel));

/* Untouched: 1D native line still implemented (Step 2 regression) */
chk('draw1DNative still implemented', /function draw1DNative\(pts\)\{[\s\S]*?return true;\n  \}catch/.test(panel));
chk('panel keeps drawCandles1D + drawCandlesRange', /function drawCandles1D\(/.test(panel) && /function drawCandlesRange\(/.test(panel));
chk('panel keeps endPress (round-3 pill fix)', /function endPress\(\)/.test(panel));
chk('panel keeps needChart', /function needChart\(\)/.test(panel));

/* Pin bumped et24 -> et24 (rebase onto main; main also used et24) in Step 4 (panel content changed) */
chk('stub loads the panel with et24', /btcchart-panel\.js\?v=et24/.test(stub));
chk('stub does not load the panel with et20', !/btcchart-panel\.js\?v=et20/.test(stub));
const pages = ['index.html', 'screener.html', 'compare/index.html', 'clock/index.html', 'recap/index.html',
  'recap/2026-01/index.html', 'recap/2026-02/index.html', 'recap/2026-03/index.html', 'recap/2026-04/index.html',
  'recap/2026-05/index.html', 'recap/2026-06/index.html', 'recap/2026-07/index.html', 'recap/2026-08/index.html',
  'recap/2026-09/index.html', 'recap/2026-10/index.html', 'recap/2026-11/index.html'];
let et24 = 0, other = [];
pages.forEach(function (p) {
  const html = fs.readFileSync(path.join(R, p), 'utf8');
  const m = html.match(/btcchart\.js\?v=([a-z0-9]+)/g) || [];
  m.forEach(function (x) { if (x === 'btcchart.js?v=et24') et24++; else other.push(p + ':' + x); });
});
chk('all 16 callers pin et24', et24 === 16 && other.length === 0, 'et24=' + et24 + ' other=' + JSON.stringify(other));

/* YTD hero chart out of scope: still Chart.js */
chk('s2.js still uses Chart.js (out of scope)', /new Chart\s*\(/.test(s2));

console.log('STAGE2 STEP3 TESTS', n, 'FAIL', f);
process.exit(f ? 1 : 0);
