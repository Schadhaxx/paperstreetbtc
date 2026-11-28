#!/usr/bin/env node
/* Desk sparklines (enhancements 6): DeskSpark SVG geometry + trend
   colour + pack freshness cap, and the shipped pack's invariants.
   Pure block evalled out of screener.js, same pattern as CmpMath. */
const fs = require('fs'), path = require('path');
const R = path.join(__dirname, '..');
let n = 0, f = 0;
const chk = (name, ok, info) => { n++; if (!ok) { f++; console.log('FAIL', name, info === undefined ? '' : JSON.stringify(info)); } };
const src = fs.readFileSync(path.join(R, 'assets/js/screener.js'), 'utf8');
const start = src.indexOf('var DeskSpark = (function () {');
const end = src.indexOf('})();', start);
if (start < 0 || end < 0) { console.log('FAIL DeskSpark block missing'); process.exit(1); }
const DeskSpark = eval(src.slice(start + 'var DeskSpark = '.length, end + 5));
const { sparkSvg, isFresh } = DeskSpark;

chk('sparkSvg empty for <2 points', sparkSvg([]) === '' && sparkSvg([5]) === '' && sparkSvg(null) === '');
const up = sparkSvg([100, 102, 101, 105, 110, 108, 112, 115, 113, 118, 120, 125]);
chk('sparkSvg up is green', up.indexOf('stroke="#22c55e"') !== -1, up.slice(0, 200));
chk('sparkSvg has 12 points', (up.match(/,/g) || []).length === 12, up);
chk('sparkSvg up labels the 12-week change', up.indexOf('12 weekly closes +25.0%') !== -1, up);
const down = sparkSvg([125, 120, 118, 113, 115, 112, 108, 110, 105, 101, 102, 100]);
chk('sparkSvg down is red', down.indexOf('stroke="#ef4444"') !== -1);
const flat = sparkSvg([50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50]);
chk('sparkSvg flat is grey, not green/red', flat.indexOf('stroke="#94a3b8"') !== -1);
chk('sparkSvg is an aria-hidden svg + screen-reader text', up.indexOf('<svg class="cmp-spark"') !== -1 && up.indexOf('aria-hidden="true"') !== -1 && up.indexOf('class="cmp-sr"') !== -1);

const DAY = 86400000, now = Date.parse('2026-11-21T12:00:00Z');
chk('isFresh: pack asOf is tomorrow (week-ending Sunday)', isFresh('2026-11-22', now) === true);
chk('isFresh: 14 days old is fresh', isFresh('2026-11-22', now + 14 * DAY) === true);
chk('isFresh: 15 days old is stale', isFresh('2026-11-22', now + 16 * DAY) === false);
chk('isFresh: a week before the week is stale', isFresh('2026-11-22', now - 8 * DAY) === false);
chk('isFresh: garbage is stale', isFresh('soon', now) === false && isFresh(null, now) === false && isFresh('', now) === false);

const page = fs.readFileSync(path.join(R, 'screener.html'), 'utf8');
chk('page loads screener.js scr15', page.indexOf('assets/js/screener.js?v=scr15') !== -1);
chk('page has spark-row css', page.indexOf('.tile .spark-row') !== -1);
chk('screener.js fetches spark-pack spk1', src.indexOf("assets/data/spark-pack.json?v=spk1") !== -1);
chk('screener.js renders sparks in cards and tiles', src.indexOf('sparkFor(r.symbol)') !== -1 && src.indexOf('class="spark-row"') !== -1);

const pack = JSON.parse(fs.readFileSync(path.join(R, 'assets/data/spark-pack.json'), 'utf8'));
const syms = Object.keys(pack.symbols);
chk('pack has all 24 Desk symbols', syms.length === 24, syms);
chk('pack asOf is a date', /^\d{4}-\d\d-\d\d$/.test(pack.asOf || ''));
chk('pack weeks is 12', pack.weeks === 12);
syms.forEach((s) => {
  const c = pack.symbols[s];
  chk(s + ' has 12 finite positive closes', Array.isArray(c) && c.length === 12 && c.every((v) => typeof v === 'number' && isFinite(v) && v > 0), c);
});
const weekly = JSON.parse(fs.readFileSync(path.join(R, 'assets/data/stock-weekly-TSLA.json'), 'utf8'));
const want = weekly.weeks.slice(-12).map((w) => w.close);
chk('pack TSLA matches the shipped weekly file', JSON.stringify(pack.symbols.TSLA) === JSON.stringify(want), [pack.symbols.TSLA, want]);
const usd = JSON.parse(fs.readFileSync(path.join(R, 'assets/data/usdcad-weekly.json'), 'utf8'));
chk('pack USDCAD keeps 4-decimal closes (not rounded to cents)', JSON.stringify(pack.symbols.USDCAD) === JSON.stringify(usd.weeks.slice(-12).map((w) => w.close)));

console.log('sparkline checks', n, 'fail', f);
process.exit(f ? 1 : 0);
