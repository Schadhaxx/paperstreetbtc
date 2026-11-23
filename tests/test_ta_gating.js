#!/usr/bin/env node
/* TA drawing fixes Stage 1 (21 Nov 2026) unit tests: the per-view gating
   pure functions in assets/js/btcchart-ta.js — taIsLineView, taGated,
   taMaGated — over the full range x type matrix, plus the Job 1 range
   expansion helper tlExpandLoHi. The agreed lists live in
   ~/workspace/your_files/ta-gating-pass-sheet-2026-11-22.md:
   - Trendlines: NO LONGER gated anywhere (Job 1, 21 Nov 2026 — the Line
     y-range expands to include the drawn lines, so they draw on Line
     1D/1W; the Stage 1 gating on Line 1D/1W is removed).
   - Bollinger gated on EVERY range (Sunil, 21 Nov ~19:16) until the
     indicator-window rework.
   - SMA 20/50 gated on 1W only; SMA 200 gated on 1D, 1W only — YTD/1Y
     KEPT (Sunil, 21 Nov ~19:16); 6M UNDECIDED — left as is, not gated.
     EMA 50 gated on 1W, EMA 200 on 1D/1W (same as the SMA twins);
     EMA 20 never gated.
   - RSI gated on every view for now. The MA group switch is never gated.
   Text output, no chart, no network. Run: node tests/test_ta_gating.js */
var M = require('../assets/js/btcchart-ta.js');
var fails = 0, n = 0;
function chk(name, ok, detail) { n++; if (ok) { console.log('ok', name); } else { fails++; console.log('FAIL', name, detail === undefined ? '' : String(detail).slice(0, 200)); } }

/* --- view states, shaped like window.__BCTA.state() --- */
function st1D(ct) { return {rng: '1D', CT: ct, RGCT: 'line', RGGRAN: 'daily'}; }
function stRange(rng, type, gran) {
  return {rng: rng, CT: 'line', RGCT: type === 'candles' ? 'candles' : 'line', RGGRAN: gran || 'daily'};
}
var RANGES = ['1D', '1W', '1M', '3M', '6M', 'YTD', '1Y', '5Y', '10Y', 'Max'];
var BB_GATED = ['1D', '1W', '1M', '3M', '6M', 'YTD', '1Y', '5Y', '10Y', 'Max'];
var MA200_GATED = ['1D', '1W'];

/* --- taIsLineView --- */
chk('line view: 1D Line', M.taIsLineView(st1D('line')) === true);
chk('line view: 1D 1H candles is not Line', M.taIsLineView(st1D('1h')) === false);
chk('line view: 1D 4H candles is not Line', M.taIsLineView(st1D('4h')) === false);
chk('line view: 1M Line', M.taIsLineView(stRange('1M', 'line')) === true);
chk('line view: 1M Candles is not Line', M.taIsLineView(stRange('1M', 'candles')) === false);
chk('line view: 5Y is Line (Line-only range)', M.taIsLineView(stRange('5Y', 'line')) === true);
chk('line view: unknown state is not Line', M.taIsLineView(null) === false && M.taIsLineView({}) === false);

/* --- trendlines: NOT gated anywhere (Job 1 ungreyed Line 1D/1W) --- */
RANGES.forEach(function (rng) {
  var line = rng === '1D' ? st1D('line') : stRange(rng, 'line');
  var cand = rng === '1D' ? st1D('1h') : (rng === '5Y' || rng === '10Y' || rng === 'Max' ? null : stRange(rng, 'candles'));
  chk('tl NOT gated on Line ' + rng, M.taGated('tl', line) === false, 'got ' + M.taGated('tl', line));
  if (cand) chk('tl NOT gated on Candles ' + rng, M.taGated('tl', cand) === false);
});
chk('tl NOT gated on 5Y/10Y/Max Line (off by design, untouched)', ['5Y', '10Y', 'Max'].every(function (rng) { return M.taGated('tl', stRange(rng, 'line')) === false; }));

/* --- Job 1: tlExpandLoHi — the bounded y-range expansion --- */
function L(price) { return {type: 'level', price: price}; }
function S(edge) { return {type: 'sloped', edgePrice: edge}; }
chk('expand: no lines -> null', M.tlExpandLoHi([], 80000, 87000) === null);
chk('expand: lines inside range -> null', M.tlExpandLoHi([L(83000), L(85000)], 80000, 87000) === null);
chk('expand: line just below -> extends lo', JSON.stringify(M.tlExpandLoHi([L(79000)], 80000, 87000)) === JSON.stringify({lo: 79000, hi: 87000}));
chk('expand: line just above -> extends hi', JSON.stringify(M.tlExpandLoHi([L(90000)], 80000, 87000)) === JSON.stringify({lo: 80000, hi: 90000}));
chk('expand: both sides within one span', JSON.stringify(M.tlExpandLoHi([L(75000), L(92000)], 80000, 87000)) === JSON.stringify({lo: 75000, hi: 92000}));
chk('expand: far line capped at one span per side', JSON.stringify(M.tlExpandLoHi([L(60000), L(120000)], 80000, 87000)) === JSON.stringify({lo: 73000, hi: 94000}));
chk('expand: sloped lines use edgePrice', JSON.stringify(M.tlExpandLoHi([S(78000), S(89000)], 80000, 87000)) === JSON.stringify({lo: 78000, hi: 89000}));
chk('expand: bad range -> null', M.tlExpandLoHi([L(79000)], 87000, 80000) === null && M.tlExpandLoHi([L(79000)], NaN, 87000) === null);
chk('expand: non-finite prices ignored', M.tlExpandLoHi([L(NaN), L(79000)], 80000, 87000) !== null);

/* --- Bollinger: gated on every range, both views --- */
RANGES.forEach(function (rng) {
  var want = BB_GATED.indexOf(rng) >= 0;
  var line = rng === '1D' ? st1D('line') : stRange(rng, 'line');
  chk('bb ' + (want ? 'gated' : 'kept') + ' on Line ' + rng, M.taGated('bb', line) === want);
  if (rng !== '5Y' && rng !== '10Y' && rng !== 'Max') {
    var cand = rng === '1D' ? st1D('1h') : stRange(rng, 'candles');
    chk('bb ' + (want ? 'gated' : 'kept') + ' on Candles ' + rng, M.taGated('bb', cand) === want);
  }
});

/* --- RSI: gated everywhere --- */
RANGES.forEach(function (rng) {
  var line = rng === '1D' ? st1D('line') : stRange(rng, 'line');
  chk('rsi gated on ' + rng, M.taGated('rsi', line) === true);
});
chk('rsi gated on 1D 1H candles too', M.taGated('rsi', st1D('1h')) === true);

/* --- MA group switch: never gated --- */
RANGES.forEach(function (rng) {
  chk('ma switch NOT gated on ' + rng, M.taGated('ma', stRange(rng, 'line')) === false);
});

/* --- SMA 20/50: gated on 1W only --- */
['sma20', 'sma50'].forEach(function (k) {
  RANGES.forEach(function (rng) {
    var want = rng === '1W';
    chk(k + (want ? ' gated' : ' kept') + ' on ' + rng, M.taMaGated(k, stRange(rng, 'line')) === want);
  });
});

/* --- SMA 200: gated on 1D, 1W only; YTD/1Y kept, 6M undecided, NOT gated --- */
RANGES.forEach(function (rng) {
  var want = MA200_GATED.indexOf(rng) >= 0;
  chk('sma200 ' + (want ? 'gated' : 'kept') + ' on ' + rng, M.taMaGated('sma200', stRange(rng, 'line')) === want);
});
chk('sma200 NOT gated on 6M (undecided, left as is)', M.taMaGated('sma200', stRange('6M', 'line')) === false);
chk('sma200 NOT gated on YTD/1Y (kept, Sunil 21 Nov)', M.taMaGated('sma200', stRange('YTD', 'line')) === false && M.taMaGated('sma200', stRange('1Y', 'line')) === false);

/* --- EMA 20 never gated; EMA 50 on 1W only; EMA 200 on 1D/1W --- */
chk('ema20 never gated', RANGES.every(function (rng) { return M.taMaGated('ema20', stRange(rng, 'line')) === false; }));
RANGES.forEach(function (rng) {
  chk('ema50 ' + (rng === '1W' ? 'gated' : 'kept') + ' on ' + rng, M.taMaGated('ema50', stRange(rng, 'line')) === (rng === '1W'));
});
RANGES.forEach(function (rng) {
  var want = rng === '1D' || rng === '1W';
  chk('ema200 ' + (want ? 'gated' : 'kept') + ' on ' + rng, M.taMaGated('ema200', stRange(rng, 'line')) === want);
});

/* --- unknown keys / unknown views fail open (not gated) --- */
chk('unknown switch key is not gated', M.taGated('nope', stRange('1D', 'line')) === false);
chk('unknown MA key is not gated', M.taMaGated('sma99', stRange('1D', 'line')) === false);
chk('unknown state is not gated', M.taGated('tl', null) === false && M.taGated('bb', {}) === false && M.taMaGated('sma200', null) === false);

console.log('TA GATING:', fails ? 'FAIL (' + fails + '/' + n + ')' : 'PASS (' + n + ' checks)');
process.exit(fails ? 1 : 0);
