#!/usr/bin/env node
/* Lazy BTC panel split (7 Nov 2026, rebuilt from main c9340ef7): btcchart.js is the eager pill only;
   the chart panel lives in btcchart-panel.js?v=et24 and loads on first
   open (or on page load on /clock/). Forked from btcchart.js et15 —
   live-feel, 1W 4H candles, FLIP morph, CAD and inline mount must survive.
   s2.js / the YTD chart are NOT part of this split (separate candidate). */
const fs = require('fs');
const path = require('path');
const R = path.resolve(__dirname, '..');
let n = 0, f = 0;
function chk(name, ok) { n++; if (!ok) { f++; console.log('FAIL', name); } else console.log('ok', name); }

const pill = fs.readFileSync(path.join(R, 'assets/js/btcchart.js'), 'utf8');
const panel = fs.readFileSync(path.join(R, 'assets/js/btcchart-panel.js'), 'utf8');
const s2 = fs.readFileSync(path.join(R, 'assets/js/s2.js'), 'utf8');

// --- eager pill ---
chk('eager: decorate + paint present', /function decorate/.test(pill) && /function paint/.test(pill));
chk('eager: Variant A chip (SVG rising line + Chart, not bare chevron)',
  /<svg[^>]*>.*Chart<\/span>/.test(pill) && !/insertAdjacentHTML\('beforeend','<span class="lp-cv"[^>]*>▾/.test(pill));
chk('eager: CAD survives (CUR/curVal/fmt/BC_setCurrency via __BTCP)',
  /var CUR=window\.BC_CUR/.test(pill) && /window\.BC_setCurrency/.test(pill) &&
  /curVal=function/.test(pill) && /window\.__BTCP=\{[^}]*fmt/.test(pill));
chk('eager: no panel code (drawDaily/getData/build/CB4H/morph/mountInline)',
  !/function drawDaily/.test(pill) && !/function drawCandles1D/.test(pill) &&
  !/function getData/.test(pill) && !/function build\(/.test(pill) &&
  !/CB4H/.test(pill) && !/morphToPill/.test(pill) && !/function mountInline/.test(pill) &&
  !/bucketCloseCountdown/.test(pill) && !/new Chart\s*\(/.test(pill));
chk('eager: no bare early return killing the clock (inline host path kept)',
  !/if\s*\(!pill\)\s*return;/.test(pill) && /INLINEHOST/.test(pill) &&
  /if\(!pill&&!INLINEHOST\)return;/.test(pill) && /if\(INLINE\)loadPanel/.test(pill));
chk('eager: lazy-loads panel at et24', /btcchart-panel\.js\?v=et24/.test(pill));
chk('eager: dedupes open while loading (pendingFrom + shared loadPanel)',
  /pendingFrom/.test(pill) && /loadPanel\(\)\.then/.test(pill) && /if\(P\.panelP\)return P\.panelP/.test(pill));
chk('eager: accessible load error (role=alert, tabindex -1, focus, retry)',
  /setAttribute\('role','alert'\)/.test(pill) && /setAttribute\('tabindex','-1'\)/.test(pill) &&
  /Chart unavailable/.test(pill) && /btcChartRetry/.test(pill) && /el\.focus\(\)/.test(pill));
chk('eager: Chart.js failure in panel surfaces the same retry alert',
  /P\.showErr=showErr/.test(pill));

// --- lazy panel ---
chk('panel: open/close/drawDaily/draw1D/drawRange present',
  /function open\b/.test(panel) && /function close\b/.test(panel) &&
  /function drawDaily/.test(panel) && /function draw1D/.test(panel) && /function drawRange/.test(panel));
chk('panel: getData + getIntraday present', /function getData/.test(panel) && /function getIntraday/.test(panel));
chk('panel: lazy needChart for Chart.js', /function needChart/.test(panel) && /chart\.umd\.min\.js/.test(panel));
chk('panel: needChart failure cleanup + retry (chartP=null, dead tag removed)',
  /var chartP=null/.test(panel) && /chartP=null/.test(panel) &&
  /removeChild\(s\)/.test(panel) && /querySelectorAll\('script\[src\*="chart\.umd\.min\.js"\]'\)/.test(panel));
chk('panel: wires into __BTCP (open/close/onLive/redraw/panelReady)',
  /var P=window\.__BTCP/.test(panel) && /P\.open=open/.test(panel) &&
  /P\.close=close/.test(panel) && /P\.panelReady=true/.test(panel) && /P\.onLive=function/.test(panel));
chk('panel: uses bridge fmt, defines no own USD-only formatter',
  /fmt\(live\.usd\)/.test(panel) && !/function fmt/.test(panel) &&
  !/style:'currency',currency:'USD'/.test(panel));
chk('panel: FLIP morph survives (morphToPill, double rAF, resize on transitionend, reduced-motion)',
  /function morphToPill/.test(panel) && /requestAnimationFrame\(function\(\)\{requestAnimationFrame/.test(panel) &&
  /ch\.resize/.test(panel) && /reducedMotion/.test(panel));
chk('panel: live-feel survives (live last candle, countdown, EXPERIMENTAL, tick flash)',
  /bucketCloseCountdown/.test(panel) && /Last candle is live/.test(panel) &&
  /this bucket closes in/.test(panel) && /EXPERIMENTAL/.test(panel) &&
  /RGLIVE/.test(panel) && /#22c55e/.test(panel));
chk('panel: 1W 4H candles survive (CB4H, UTC buckets, complete only, last 42)',
  /CB4H/.test(panel) && /agg4hFromHourly/.test(panel) && /slice\(-42\)/.test(panel) &&
  /CB4H_ERR/.test(panel));
chk('panel: inline mount survives (bcInline, mountInline on load)',
  /getElementById\('bcInline'\)/.test(panel) && /function mountInline/.test(panel) &&
  /if\(INLINE\)mountInline\(\);/.test(panel));
chk('panel: exposes _needChart test hook', /P\._needChart=needChart/.test(panel));

// --- scope: s2.js untouched by this split ---
chk('s2.js untouched (still Chart.js YTD — separate candidate)',
  /new Chart\s*\(/.test(s2));

// --- pins: all 16 HTML refs on et24, panel pin matches ---
const htmls = [];
(function walk(d) {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    if (e.name === '.git' || e.name === 'node_modules') continue;
    const p = path.join(d, e.name);
    if (e.isDirectory()) walk(p);
    else if (e.name.endsWith('.html')) htmls.push(p);
  }
})(R);
let bad = 0, refs = 0;
for (const h of htmls) {
  const t = fs.readFileSync(h, 'utf8');
  if (!/btcchart\.js/.test(t)) continue;
  refs++;
  if (!/btcchart\.js\?v=et24/.test(t)) { bad++; console.log('FAIL stale btcchart pin', path.relative(R, h)); }
  if (/btcchart\.js\?v=et15/.test(t)) { bad++; console.log('FAIL still et15', path.relative(R, h)); }
}
chk('all btcchart.html refs use ?v=et24 (16 files)', bad === 0 && refs === 16);
chk('no burned btcchart pins (et5/et6/et7/et8/et12/et13/et14/et15/et21/et22/et23) in new files',
  !/btcchart(?:-panel)?\.js\?v=et(?:5|6|7|8|12|13|14|15|21|22|23)\b/.test(pill + panel));

// --- no other Strategy preferreds ---
chk('no STRF/STRK/STRD in new files', !/\bSTR[FKD]\b/.test(pill + panel));

console.log('SPEED LAZY-PANEL TESTS', n, 'FAIL', f);
process.exit(f ? 1 : 0);
