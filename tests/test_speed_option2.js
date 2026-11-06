#!/usr/bin/env node
/* Speed Option 2: home YTD without Chart.js; BTC pill eager; panel lazy. */
const fs = require('fs');
const path = require('path');
const R = path.resolve(__dirname, '..');
let n = 0, f = 0;
function chk(name, ok) { n++; if (!ok) { f++; console.log('FAIL', name); } else console.log('ok', name); }

const idx = fs.readFileSync(path.join(R, 'index.html'), 'utf8');
const s2 = fs.readFileSync(path.join(R, 'assets/js/s2.js'), 'utf8');
const pill = fs.readFileSync(path.join(R, 'assets/js/btcchart.js'), 'utf8');
const panel = fs.readFileSync(path.join(R, 'assets/js/btcchart-panel.js'), 'utf8');

chk('index.html does not eager-load chart.umd', !/chart\.umd\.min\.js/.test(idx));
chk('index.html loads s2.js?v=p6', /s2\.js\?v=p6/.test(idx));
chk('index.html loads btcchart.js?v=et7', /btcchart\.js\?v=et7/.test(idx));
chk('s2.js has no new Chart(', !/new Chart\s*\(/.test(s2));
chk('s2.js draws native canvas', /getElementById\('ytdChart'\)/.test(s2) && /getContext\('2d'\)/.test(s2));
chk('s2.js keeps BACKUP_LBL / fallback_sources', /BACKUP_LBL/.test(s2) && /fallback_sources/.test(s2));
chk('s2.js exposes __YTD_SERIES for parity', /__YTD_SERIES/.test(s2));
chk('btcchart.js is eager pill (decorate + paint)', /function decorate/.test(pill) && /function paint/.test(pill));
chk('btcchart.js lazy-loads btcchart-panel.js', /btcchart-panel\.js\?v=et7/.test(pill));
chk('btcchart.js does not embed candle/drawDaily', !/function drawDaily/.test(pill) && !/function drawCandles1D/.test(pill));
chk('btcchart-panel.js has open/close/drawDaily', /function open\b/.test(panel) && /function close\b/.test(panel) && /function drawDaily/.test(panel));
chk('btcchart-panel.js lazy needChart for Chart.js', /function needChart/.test(panel));
chk('panel wires into __BTCP', /window\.__BTCP/.test(panel) && /P\.open\s*=\s*open/.test(panel));

chk('s2.js has pointer/touch hover', /pointerdown/.test(s2) && /touchstart/.test(s2));
chk('s2.js wraps long legend labels', /wrapWords/.test(s2));
chk('s2.js reads theme CSS vars', /themeColors/.test(s2) && /--muted/.test(s2));
chk('s2.js smooth tension paths', /traceLine/.test(s2) && /tension: 0\.3/.test(s2));
chk('btcchart.js shows accessible load error', /setAttribute\('role','alert'\)/.test(pill) && /Chart unavailable/.test(pill) && /btcChartRetry/.test(pill));
chk('btcchart.js dedupes open while loading', /pendingFrom/.test(pill) && /loadPanel\(\)\.then/.test(pill));
chk('panel needChart dedupes Chart.js inject', /var chartP=null/.test(panel) && /chart\.umd\.min\.js/.test(panel));
chk('no STRF/STRK/STRD in new files', !/\bSTR[FKD]\b/.test(s2+pill+panel));

// every html that had btcchart still points at et6
const htmls = [];
function walk(d) {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    if (e.name === '.git' || e.name === 'node_modules') continue;
    const p = path.join(d, e.name);
    if (e.isDirectory()) walk(p);
    else if (e.name.endsWith('.html')) htmls.push(p);
  }
}
walk(R);
let bad = 0;
for (const h of htmls) {
  const t = fs.readFileSync(h, 'utf8');
  if (!/btcchart\.js/.test(t)) continue;
  if (!/btcchart\.js\?v=et7/.test(t)) { bad++; console.log('FAIL stale btcchart bust', path.relative(R, h)); }
}
chk('all btcchart.html refs use ?v=et7', bad === 0);

console.log('SPEED OPTION2 TESTS', n, 'FAIL', f);
process.exit(f ? 1 : 0);
