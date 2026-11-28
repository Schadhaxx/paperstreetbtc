#!/usr/bin/env node
/* TA Stage 4 trendline unit tests (21 Nov 2026): the pure functions in
   assets/js/btcchart-ta.js — header validation + per-timeframe checks,
   per-timeframe staleness (pack rule 6: 2x interval + grace, measured
   from the last bar OPEN), the chart->timeframe map, sloped prices in
   candle-index space, the ref-port selector (tlSelectLines, run against
   the pack's cases in test_ta_pack_cases.js), the browser multi-tf
   selector (tlSelectLinesForChart, same-or-higher), and labels.
   Text output, no chart, no network. Run: node tests/test_ta_trendlines.js */
var M = require('../assets/js/btcchart-ta.js');
var fails = 0, n = 0;
function chk(name, ok, detail) { n++; if (ok) { console.log('ok', name); } else { fails++; console.log('FAIL', name, detail === undefined ? '' : String(detail).slice(0, 200)); } }
function close(a, b, tol) { if (a === null || b === null) return a === b; return Math.abs(a - b) <= (tol || 1e-9 * Math.max(1, Math.abs(b))); }

/* --- a minimal valid schema-1 file (same shape as the job emits) --- */
function tf(asOf, levels, sloped, missS, missR) {
  return {asOf: asOf, atr: 700, lastClose: 77500, levels: levels, sloped: sloped,
    missingSupport: !!missS, missingResistance: !!missR};
}
function lvl(price, kind, ext, brk) {
  return {price: price, kind: kind, score: 2.5, rawScore: 4.0, distAtr: 2.0,
    touches: 3, lastTouch: '2026-10-29T00:00:00Z', ageCandles: 5,
    broken: !!brk, held: false, extreme: !!ext};
}
function slp(kind, slope, anchorT, anchorP, priceNow) {
  return {kind: kind, slope: slope, anchor: {t: anchorT, price: anchorP},
    touches: 5, score: 5.0, rawScore: 6.0, distAtr: 1.0, priceNow: (priceNow === undefined ? anchorP : priceNow),
    broken: false, held: false};
}
function validFile() {
  return {v: 1, kind: 'ta-lines', asOf: '2026-10-30T20:00:00Z', timeframes: {
    '1h': tf('2026-10-30T19:00:00Z',
      [lvl(79200, 'resistance', false, false), lvl(78400, 'resistance', false, true), lvl(76300, 'support', false, false), lvl(74800, 'support', true, false)],
      [slp('support', 30, '2026-10-30T08:00:00Z', 75500), slp('resistance', -20, '2026-10-30T10:00:00Z', 79800)], false, false),
    '4h': tf('2026-10-30T16:00:00Z',
      [lvl(79500, 'resistance', false, false)],
      [slp('support', 120, '2026-10-30T00:00:00Z', 74000), slp('support', 90, '2026-10-29T20:00:00Z', 73000)], true, false),
    '1d': tf('2026-10-30T00:00:00Z',
      [lvl(81000, 'resistance', false, false), lvl(75000, 'support', false, false)],
      [slp('support', -35.2898, '2025-02-28T00:00:00Z', 78167.81, 56676)], false, false)}};
}

/* --- tlValidate: header only; partial files fail closed per timeframe --- */
chk('validate: real-shape file is valid', M.tlValidate(validFile()).ok);
chk('validate: null is invalid', !M.tlValidate(null).ok);
chk('validate: wrong version is invalid', !M.tlValidate({v: 2, kind: 'ta-lines', timeframes: validFile().timeframes}).ok);
chk('validate: wrong kind is invalid', !M.tlValidate({v: 1, kind: 'nope', timeframes: validFile().timeframes}).ok);
chk('validate: no timeframes object is invalid', !M.tlValidate({v: 1, kind: 'ta-lines'}).ok);
(function () { var f = validFile(); delete f.timeframes['4h']; chk('validate: partial file (missing 4h) is header-valid — per-tf fail-closed', M.tlValidate(f).ok); })();

/* --- tlTfOk: the ref's _tf_ok (keys + arrays); caps are the job's --- */
chk('tfOk: real timeframe is ok', M.tlTfOk(validFile().timeframes['1h']));
(function () { var f = validFile(); delete f.timeframes['1h'].sloped; chk('tfOk: missing sloped key is not ok', !M.tlTfOk(f.timeframes['1h'])); })();
(function () { var f = validFile(); f.timeframes['1h'].levels = 'nope'; chk('tfOk: levels not an array is not ok', !M.tlTfOk(f.timeframes['1h'])); })();
(function () { var f = validFile(); f.timeframes['1h'].levels.push(lvl(80000, 'resistance', false, false)); chk('tfOk: 5 levels is ok — caps are the job\u2019s validate(), the front end draws what is in the file', M.tlTfOk(f.timeframes['1h'])); })();
(function () { var f = validFile(); f.timeframes['1d'].asOf = 'junk'; chk('tfOk: bad asOf string is ok (staleness handles it, not validity)', M.tlTfOk(f.timeframes['1d'])); })();

/* --- tlIsStale: pack rule 6 — 2x the interval + grace, from the bar open --- */
var NOW = Date.parse('2026-10-30T20:00:00Z');
chk('stale: 1h at exactly 2h20m is fresh', !M.tlIsStale('1h', NOW - (2 * 3600 + 20 * 60) * 1000, NOW));
chk('stale: 1h at 2h20m + 1 s is stale', M.tlIsStale('1h', NOW - (2 * 3600 + 20 * 60) * 1000 - 1000, NOW));
chk('stale: 1h at 55 min is fresh (a fresh file\u2019s asOf is already 0-60 min old)', !M.tlIsStale('1h', NOW - 55 * 60 * 1000, NOW));
chk('stale: 1h at 10 min is fresh', !M.tlIsStale('1h', NOW - 10 * 60 * 1000, NOW));
chk('stale: 4h at exactly 8h30m is fresh', !M.tlIsStale('4h', NOW - (8 * 3600 + 30 * 60) * 1000, NOW));
chk('stale: 4h at 8h30m + 1 s is stale', M.tlIsStale('4h', NOW - (8 * 3600 + 30 * 60) * 1000 - 1000, NOW));
chk('stale: 4h at 5 h is fresh (a fresh 4h file is 4-8 h old — last complete bucket)', !M.tlIsStale('4h', NOW - 5 * 3600 * 1000, NOW));
chk('stale: 1d at exactly 50 h is fresh', !M.tlIsStale('1d', NOW - 50 * 3600 * 1000, NOW));
chk('stale: 1d at 50 h + 1 s is stale', M.tlIsStale('1d', NOW - 50 * 3600 * 1000 - 1000, NOW));
chk('stale: 1d at 5 h is fresh', !M.tlIsStale('1d', NOW - 5 * 3600 * 1000, NOW));
chk('stale: bad asOf is stale', M.tlIsStale('1h', NaN, NOW));
chk('stale: unknown tf is stale', M.tlIsStale('2h', NOW - 1000, NOW));

/* --- tlChartTf --- */
chk('chartTf: 1D line -> 1h', M.tlChartTf({rng: '1D', CT: 'line'}) === '1h');
chk('chartTf: 1D 1h candles -> 1h', M.tlChartTf({rng: '1D', CT: '1h'}) === '1h');
chk('chartTf: 1D 4h candles -> 4h', M.tlChartTf({rng: '1D', CT: '4h'}) === '4h');
chk('chartTf: 1W 4h candles -> 4h', M.tlChartTf({rng: '1W', RGCT: 'candles', RGGRAN: '4h'}) === '4h');
chk('chartTf: 1W line -> 1d', M.tlChartTf({rng: '1W', RGCT: 'line'}) === '1d');
chk('chartTf: 1W daily candles -> 1d', M.tlChartTf({rng: '1W', RGCT: 'candles', RGGRAN: 'daily'}) === '1d');
chk('chartTf: 1M weekly candles -> 1d', M.tlChartTf({rng: '1M', RGCT: 'candles', RGGRAN: 'weekly'}) === '1d');
chk('chartTf: 1M monthly candles -> 1d', M.tlChartTf({rng: '1M', RGCT: 'candles', RGGRAN: 'monthly'}) === '1d');
chk('chartTf: 3M line -> 1d', M.tlChartTf({rng: '3M', RGCT: 'line'}) === '1d');
chk('chartTf: 6M/YTD/1Y -> 1d', M.tlChartTf({rng: '6M', RGCT: 'line'}) === '1d' && M.tlChartTf({rng: 'YTD', RGCT: 'line'}) === '1d' && M.tlChartTf({rng: '1Y', RGCT: 'candles', RGGRAN: 'daily'}) === '1d');
chk('chartTf: 5Y/10Y/Max -> null', M.tlChartTf({rng: '5Y', RGCT: 'line'}) === null && M.tlChartTf({rng: '10Y', RGCT: 'line'}) === null && M.tlChartTf({rng: 'Max', RGCT: 'line'}) === null);
chk('chartTf: no state -> null', M.tlChartTf(null) === null && M.tlChartTf({}) === null);

/* --- tlSlopedPriceAt: candle-index space, not wall-clock position --- */
var sl1 = slp('support', -39.1838, '2026-10-31T21:00:00Z', 77283.19);
chk('sloped: price at anchor is the anchor price', close(M.tlSlopedPriceAt(sl1, Date.parse('2026-10-31T21:00:00Z'), '1h'), 77283.19));
chk('sloped: 1h line 12 h after anchor', close(M.tlSlopedPriceAt(sl1, Date.parse('2026-11-01T09:00:00Z'), '1h'), 77283.19 - 39.1838 * 12));
var slD = slp('support', -35.2898, '2025-02-28T00:00:00Z', 78167.81);
chk('sloped: 1d line 10 d after anchor', close(M.tlSlopedPriceAt(slD, Date.parse('2025-03-10T00:00:00Z'), '1d'), 78167.81 - 35.2898 * 10));
var slW = slp('support', -100, '2026-10-30T00:00:00Z', 70000);
chk('sloped: Friday anchor to Monday is 3 daily candles, not 1', close(M.tlSlopedPriceAt(slW, Date.parse('2026-11-02T00:00:00Z'), '1d'), 69700));
chk('sloped: 4h line 8 h after anchor is 2 intervals', close(M.tlSlopedPriceAt(slp('resistance', -50, '2026-10-30T00:00:00Z', 80000), Date.parse('2026-10-30T08:00:00Z'), '4h'), 79900));

/* --- tlSelectLines: the ref port — rules 1, 3, 4, 5, 6, 8 --- */
var LAST = Date.parse('2026-10-30T20:00:00Z'); /* last visible candle time */
var r = M.tlSelectLines(validFile(), '1h', '1h', 77500, NOW, null);
chk('select: all 6 1h lines draw when on the right side of live close', r.length === 6, JSON.stringify(r));
chk('select: broken:true resistance draws as a normal line', r.some(function (l) { return l.price === 78400 && l.kind === 'resistance' && l.style === 'ranked'; }));
chk('select: EXT draws with style ext + label range low', r.some(function (l) { return l.price === 74800 && l.style === 'ext' && l.label === 'range low'; }));
chk('select: sloped lines fall back to priceNow with no candles', (function () {
  var s = r.filter(function (l) { return l.price === 75500 || l.price === 79800; });
  return s.length === 2;
})(), JSON.stringify(r));
chk('select: 1d lines draw on a 1h chart, labelled 1d (rule 5 same-or-higher)', (function () {
  var d = M.tlSelectLines(validFile(), '1d', '1h', 77500, NOW, null);
  return d.length === 3 && d.every(function (l) { return l.tf_label === '1d'; });
})());
chk('select: 1h lines do NOT draw on a 1d chart (rule 5 lower tf)', M.tlSelectLines(validFile(), '1h', '1d', 77500, NOW, null).length === 0);
chk('select: support above a 76000 live close is omitted (rule 3)', M.tlSelectLines(validFile(), '1h', '1h', 76000, NOW, null).every(function (l) { return l.price !== 76300; }));
chk('select: resistance below an 80000 live close is omitted (rule 3)', M.tlSelectLines(validFile(), '1h', '1h', 80000, NOW, null).every(function (l) { return l.price !== 79200; }));
chk('select: line exactly at live close draws (rule 3, equal allowed)', M.tlSelectLines(validFile(), '1h', '1h', 76300, NOW, null).some(function (l) { return l.price === 76300; }));
chk('select: missingSupport=true does NOT hide sloped supports (rule 1)', (function () {
  var d = M.tlSelectLines(validFile(), '4h', '4h', 77500, NOW, null);
  return d.filter(function (l) { return l.kind === 'support'; }).length === 2;
})());
chk('select: stale timeframe draws nothing (rule 6)', (function () {
  var f = validFile(); f.timeframes['1h'].asOf = '2026-10-30T17:00:00Z'; /* 3 h old > 2h20m */
  return M.tlSelectLines(f, '1h', '1h', 77500, NOW, null).length === 0;
})());
chk('select: invalid header draws nothing', M.tlSelectLines({v: 2, kind: 'ta-lines', timeframes: {}}, '1h', '1h', 77500, NOW, null).length === 0);
chk('select: partial file — present fresh 1h still draws', (function () {
  var f = validFile(); delete f.timeframes['4h'];
  return M.tlSelectLines(f, '1h', '1h', 77500, NOW, null).length === 6;
})());
/* The pack's gap case, inline: five 1h candles with a weekend-sized hole. */
var gapFile = {v: 1, kind: 'ta-lines', asOf: '2026-11-23T01:30:00Z', timeframes: {
  '1h': {asOf: '2026-11-23T01:00:00Z', lastClose: 60, atr: 5, levels: [], sloped: [{kind: 'support', slope: -10, anchor: {t: '2026-11-20T21:00:00Z', price: 100}, touches: 3, score: 1, rawScore: 1, distAtr: 0.5, priceNow: 60, broken: false, held: false}], missingSupport: true, missingResistance: true},
  '4h': {asOf: '2026-11-23T00:00:00Z', lastClose: 55700, atr: 800, levels: [], sloped: [], missingSupport: false, missingResistance: false},
  '1d': {asOf: '2026-11-21T00:00:00Z', lastClose: 55700, atr: 800, levels: [], sloped: [], missingSupport: false, missingResistance: false}}};
var gapCandles = [[1795208400000, 100, 101, 99, 100], [1795212000000, 90, 101, 99, 90], [1795215600000, 80, 101, 99, 80], [1795392000000, 70, 101, 99, 70], [1795395600000, 60, 101, 99, 60]];
chk('select: gap case edge is 60 by index (4 steps), not wall-clock (~52 h)', (function () {
  var g = M.tlSelectLines(gapFile, '1h', '1h', 60, '2026-11-23T01:30:00Z', gapCandles);
  return g.length === 1 && g[0].endpoints && g[0].endpoints[0].price === 100 && g[0].endpoints[1].price === 60 && g[0].endpoints[1].t === '2026-11-23T01:00:00Z';
})());
chk('select: anchor not in the candle list omits the sloped line (spec rule 8)', (function () {
  var f = JSON.parse(JSON.stringify(gapFile)); f.timeframes['1h'].sloped[0].anchor.t = '2026-11-20T20:00:00Z';
  return M.tlSelectLines(f, '1h', '1h', 60, '2026-11-23T01:30:00Z', gapCandles).length === 0;
})());
chk('select: gap case with no candles falls back to priceNow', (function () {
  var g = M.tlSelectLines(gapFile, '1h', '1h', 60, '2026-11-23T01:30:00Z', null);
  return g.length === 1 && g[0].price === 60 && !g[0].endpoints;
})());

/* --- tlSelectLinesForChart: browser multi-tf selection --- */
var B = M.tlSelectLinesForChart(validFile(), '1h', 77500, NOW, LAST);
chk('browser: 1h chart draws 12 lines (1h 6 + 4h 3 + 1d 3)', B.drawn.length === 12 && B.omitted.length === 0, 'drawn=' + B.drawn.length);
chk('browser: 1h chart freshTfs are all three', B.freshTfs.join(',') === '1h,4h,1d' && B.perTf['1h'] === 'live' && B.perTf['4h'] === 'live' && B.perTf['1d'] === 'live');
chk('browser: 4h chart draws 6 lines (4h 3 + 1d 3), no 1h', (function () {
  var b4 = M.tlSelectLinesForChart(validFile(), '4h', 77500, NOW, LAST);
  return b4.drawn.length === 6 && b4.drawn.every(function (l) { return l.tf !== '1h'; }) && b4.freshTfs.join(',') === '4h,1d';
})());
chk('browser: 1d chart draws 3 lines (1d only)', (function () {
  var b1 = M.tlSelectLinesForChart(validFile(), '1d', 77500, NOW, LAST);
  return b1.drawn.length === 3 && b1.drawn.every(function (l) { return l.tf === '1d'; }) && b1.freshTfs.join(',') === '1d';
})());
chk('browser: stale 1h still draws 4h + 1d (6 lines), perTf 1h stale', (function () {
  var f = validFile(); f.timeframes['1h'].asOf = '2026-10-30T17:00:00Z';
  var b = M.tlSelectLinesForChart(f, '1h', 77500, NOW, LAST);
  return b.drawn.length === 6 && b.freshTfs.join(',') === '4h,1d' && b.perTf['1h'] === 'stale' && b.perTf['4h'] === 'live';
})());
chk('browser: all tfs stale draws nothing, freshTfs empty', (function () {
  var f = validFile();
  f.timeframes['1h'].asOf = '2026-10-30T17:00:00Z';
  f.timeframes['4h'].asOf = '2026-10-30T11:00:00Z'; /* 9 h > 8h30m */
  f.timeframes['1d'].asOf = '2026-10-28T17:00:00Z'; /* 51 h > 50h */
  var b = M.tlSelectLinesForChart(f, '1h', 77500, NOW, LAST);
  return b.drawn.length === 0 && b.freshTfs.length === 0;
})());
chk('browser: invalid header is fileOk false, reason bad schema', (function () {
  var b = M.tlSelectLinesForChart({v: 2, kind: 'ta-lines', timeframes: {}}, '1h', 77500, NOW, LAST);
  return !b.fileOk && b.fileReason === 'bad schema';
})());
chk('browser: partial file (missing 4h) still draws 1h + 1d (9 lines)', (function () {
  var f = validFile(); delete f.timeframes['4h'];
  var b = M.tlSelectLinesForChart(f, '1h', 77500, NOW, LAST);
  return b.drawn.length === 9 && b.perTf['4h'] === 'missing' && b.freshTfs.join(',') === '1h,1d';
})());
chk('browser: 1d sloped edge uses the 1d interval (Feb 2025 anchor, ~56647)', (function () {
  var s = B.drawn.filter(function (l) { return l.type === 'sloped' && l.tf === '1d'; });
  return s.length === 1 && close(s[0].edgePrice, 56646.88, 1);
})());

/* --- tlLabel --- */
chk('label: ranked support is just the price', M.tlLabel({kind: 'support', price: 76300, extreme: false, tf: '1h'}, '1h') === '$76,300');
chk('label: ranked resistance is just the price', M.tlLabel({kind: 'resistance', price: 79200, extreme: false, tf: '1h'}, '1h') === '$79,200');
chk('label: EXT support is "range low"', M.tlLabel({kind: 'support', price: 74800, extreme: true, tf: '1h'}, '1h') === 'range low $74,800');
chk('label: EXT resistance is "range high"', M.tlLabel({kind: 'resistance', price: 81000, extreme: true, tf: '1d'}, '1d') === 'range high $81,000');
chk('label: foreign timeframe is prefixed', M.tlLabel({kind: 'resistance', price: 65286, extreme: false, tf: '1d'}, '1h') === '1d $65,286');
chk('label: foreign EXT is prefixed and labelled', M.tlLabel({kind: 'support', price: 57655, extreme: true, tf: '1d'}, '1h') === '1d range low $57,655');

/* --- tlLabel: anchored to the level's own USD price (Job 4, 22 Nov 2026) ---
   The old fmtP path converted USD->CAD at the LIVE rate, so the same fixed
   level drifted C$83,548 -> 83,637 -> 83,646 as the FX rate ticked. tlLabel
   no longer takes a formatter: the label is always the level's own USD
   price, so it changes only when the file changes. */
chk('label: a level ignores a live-rate CAD formatter (Job 4 anchor)', M.tlLabel({kind: 'support', price: 60000, extreme: false, tf: '1d'}, '1d', function (v) { return 'C$' + Math.round(v * 1.39247).toLocaleString('en-US'); }) === '$60,000');
chk('label: the same level labels identically at another FX rate (Job 4 anchor)', M.tlLabel({kind: 'support', price: 60000, extreme: false, tf: '1d'}, '1d', function (v) { return 'C$' + Math.round(v * 1.39410).toLocaleString('en-US'); }) === '$60,000');
chk('label: a sloped line ignores a live-rate CAD formatter (Job 4 anchor)', M.tlLabel({type: 'sloped', kind: 'resistance', edgePrice: 75860, extreme: false, tf: '1h'}, '1h', function (v) { return 'C$' + Math.round(v * 1.39410).toLocaleString('en-US'); }) === '$75,860');

/* --- tlLabel: sloped lines use edgePrice ($NaN fix, 21 Nov 2026) --- */
chk('label: every sloped line in the fixture labels its drawn right-edge value (within $1)', (function () {
  var s = B.drawn.filter(function (l) { return l.type === 'sloped'; });
  if (s.length !== 5) return false;
  return s.every(function (l) {
    var lab = M.tlLabel(l, '1h');
    if (!lab || lab.indexOf('NaN') >= 0) return false;
    var num = Number(lab.replace(/^(1h|4h|1d) /, '').replace(/[$,]/g, ''));
    return isFinite(num) && Math.abs(num - l.edgePrice) <= 1;
  });
})());
chk('label: sloped line on its own tf labels just the price', M.tlLabel({type: 'sloped', kind: 'support', edgePrice: 75860, extreme: false, tf: '1h'}, '1h') === '$75,860');
chk('label: foreign-tf sloped line is prefixed', M.tlLabel({type: 'sloped', kind: 'support', edgePrice: 56646.88, extreme: false, tf: '1d'}, '1h') === '1d $56,647');
chk('label: sloped line with NaN edgePrice hides its label (never $NaN)', M.tlLabel({type: 'sloped', kind: 'support', edgePrice: NaN, extreme: false, tf: '1h'}, '1h') === '');
chk('label: sloped line with missing edgePrice hides its label', M.tlLabel({type: 'sloped', kind: 'resistance', extreme: false, tf: '1h'}, '1h') === '');

console.log('TA TRENDLINES:', fails ? 'FAIL (' + fails + '/' + n + ')' : 'PASS (' + n + ' checks)');
process.exit(fails ? 1 : 0);
