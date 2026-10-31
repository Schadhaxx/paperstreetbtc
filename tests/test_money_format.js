#!/usr/bin/env node
/* Money-formatter fixtures (brief 31 Oct 2026, item A5): negative money reads
   "-$153.50", never "$-153.50". Extracts the real formatter bodies from the
   shipped sources and runs them, so a regression in the source fails here. */
const fs = require('fs'), path = require('path');
const R = path.join(__dirname, '..');
let n = 0, f = 0;
const chk = (name, ok, info) => { n++; if (!ok) { f++; console.log('FAIL', name, info === undefined ? '' : JSON.stringify(info)); } else console.log('PASS', name); };
const src = (p) => fs.readFileSync(path.join(R, p), 'utf8');
const fn = (text, name) => { const m = text.match(new RegExp('function ' + name + '\\([^)]*\\) \\{[\\s\\S]*?\\n  \\}')); if (!m) throw new Error('formatter not found: ' + name); return eval('(' + m[0] + ')'); };
// screener-indicator-chart.js: fmtMoney
const fmtMoney = fn(src('assets/js/screener-indicator-chart.js'), 'fmtMoney');
chk('fmtMoney(-153.50) = -$153.50', fmtMoney(-153.50) === '-$153.50', fmtMoney(-153.50));
chk('fmtMoney(153.50) = $153.50', fmtMoney(153.50) === '$153.50');
chk('fmtMoney(1234567.89) grouped', fmtMoney(1234567.89) === '$1,234,567.89');
chk('fmtMoney(0) = $0.00', fmtMoney(0) === '$0.00');
chk('fmtMoney(NaN) = em dash', fmtMoney(NaN) === '—');
chk('fmtMoney("x") = em dash (non-number)', fmtMoney('x') === '—');
const cardMoney = fn(src('assets/js/screener-indicator-chart.js'), 'cardMoney');
chk('cardMoney(-153.50) = -$153.50', cardMoney(-153.50) === '-$153.50', cardMoney(-153.50));
chk('cardMoney(153.5) = $153.50', cardMoney(153.5) === '$153.50');
chk('cardMoney(NaN) = em dash', cardMoney(NaN) === '—');
chk('cardMoney(Infinity) = em dash', cardMoney(Infinity) === '—');
// screener.js: money + dayText (dayText needs pct from the same file)
const scr = src('assets/js/screener.js');
const money = fn(scr, 'money');
chk('money(-153.50) = -$153.50', money(-153.50) === '-$153.50', money(-153.50));
chk('money(153.50) = $153.50', money(153.50) === '$153.50');
chk('money(null) = em dash', money(null) === '—');
chk('money(true) = em dash (boolean rejected)', money(true) === '—');
const pctM = scr.match(/function pct\([^)]*\) \{[\s\S]*?\n  \}/);
const dayM = scr.match(/function dayText\([^)]*\) \{[\s\S]*?\n  \}/);
if (!pctM || !dayM) throw new Error('dayText/pct not found');
const dayText = eval('(function(){' + pctM[0] + '\n' + dayM[0] + '\nreturn dayText;})()');
chk('dayText(-153.50) starts -$153.50, never $-', dayText({ dayChange: -153.50, dayChangePct: -5 }).startsWith('-$153.50'), dayText({ dayChange: -153.50, dayChangePct: -5 }));
chk('dayText(+153.50) starts +$153.50', dayText({ dayChange: 153.50, dayChangePct: 5 }).startsWith('+$153.50'));
// compare.js: usd arrow
const cmp = src('assets/js/compare.js');
const usdM = cmp.match(/usd=\([^)]*\)=>[^;]+;/);
if (!usdM) throw new Error('usd not found');
const usd = eval('(' + usdM[0].replace(/^usd=/, '').replace(/;$/, '') + ')');
chk('usd(-153.50,2) = -$153.50', usd(-153.50, 2) === '-$153.50', usd(-153.50, 2));
chk('usd(153.50,2) = $153.50', usd(153.50, 2) === '$153.50');
chk('usd(NaN) = em dash', usd(NaN) === '—');
console.log('MONEY TESTS', n, 'FAIL', f); process.exit(f ? 1 : 0);
