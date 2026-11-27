#!/usr/bin/env node
/* TA drawing fixes Stage 1 (21 Nov 2026) unit tests: the per-view gating
   pure functions in assets/js/btcchart-ta.js — taIsLineView, taGated,
   taMaGated — over the full range x type matrix, plus the Job 1 range
   expansion helper tlExpandLoHi. The agreed lists live in
   ~/workspace/your_files/ta-gating-pass-sheet-2026-11-22.md:
   - Trendlines: NO LONGER gated anywhere (Job 1, 21 Nov 2026 — the Line
     y-range expands to include the drawn lines, so they draw on Line
     1D/1W; the Stage 1 gating on Line 1D/1W is removed).
   - Bollinger NO LONGER gated anywhere (Job 2, 21 Nov 2026 — the
     pre-warm fetches history before the visible window, so a 20-period
     is valid from index 0 on every range).
   - SMA 20/50 gated on 1W only; SMA 200 NO LONGER gated anywhere
     (Job 2 — same pre-warm; it was already live on the longer ranges).
     EMA 50 gated on 1W, EMA 200 NO LONGER gated anywhere (Job 2 —
     SMA 200's twin); EMA 20 never gated.
   - RSI NO LONGER gated anywhere (Job 3, 22 Nov 2026 — the strip now
     has a scale, shaded 30/70 bands and a live value, and Job 2's
     pre-warm gives it its 14 closes on every view).
   - SMA 200 on 6M DECIDED (Job 8, 22 Nov 2026 — it reads right on 6M
     Line and 6M weekly candles, so it stays ungated there). The 200s
     (SMA 200, EMA 200) ARE gated on monthly-granularity candle views
     (Job 8 — a 200-month average needs 200 months of BTC history and
     only ~195 exist, so the lines can never compute there). Line views
     and daily/weekly/4h candles are unaffected.
   - Job 9 (22 Nov 2026): Bollinger + ALL six MAs gated on yearly-
     granularity candle views (10Y yearly) — the shortest, SMA/EMA 20,
     needs 20 yearly closes and only 17 exist (2010–2026). RSI is NOT
     gated there: its 14 closes are covered by the warm-up + visible.
     The monthly 200s gate (Job 8) now also covers the new 5Y/10Y
     monthly views (it keys on granularity, not range).
   The MA group switch is never gated.
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
var BB_GATED = []; /* Job 2: Bollinger ungated everywhere. */
var MA200_GATED = []; /* Job 2: SMA 200 ungated everywhere. */

/* --- taIsLineView --- */
chk('line view: 1D Line', M.taIsLineView(st1D('line')) === true);
chk('line view: 1D 1H candles is not Line', M.taIsLineView(st1D('1h')) === false);
chk('line view: 1D 4H candles is not Line', M.taIsLineView(st1D('4h')) === false);
chk('line view: 1M Line', M.taIsLineView(stRange('1M', 'line')) === true);
chk('line view: 1M Candles is not Line', M.taIsLineView(stRange('1M', 'candles')) === false);
chk('line view: 5Y Line view is Line', M.taIsLineView(stRange('5Y', 'line')) === true);
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

/* --- Bollinger: NOT gated anywhere (Job 2 ungreyed every range) --- */
RANGES.forEach(function (rng) {
  var want = BB_GATED.indexOf(rng) >= 0;
  var line = rng === '1D' ? st1D('line') : stRange(rng, 'line');
  chk('bb ' + (want ? 'gated' : 'kept') + ' on Line ' + rng, M.taGated('bb', line) === want);
  if (rng !== '5Y' && rng !== '10Y' && rng !== 'Max') {
    var cand = rng === '1D' ? st1D('1h') : stRange(rng, 'candles');
    chk('bb ' + (want ? 'gated' : 'kept') + ' on Candles ' + rng, M.taGated('bb', cand) === want);
  }
});

/* --- RSI: NOT gated anywhere (Job 3 ungreyed every view) --- */
RANGES.forEach(function (rng) {
  var line = rng === '1D' ? st1D('line') : stRange(rng, 'line');
  chk('rsi NOT gated on ' + rng, M.taGated('rsi', line) === false);
});
chk('rsi NOT gated on 1D 1H candles too', M.taGated('rsi', st1D('1h')) === false);

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

/* --- SMA 200: NOT gated anywhere (Job 2 ungreyed 1D/1W; it was already live on the longer ranges) --- */
RANGES.forEach(function (rng) {
  var want = MA200_GATED.indexOf(rng) >= 0;
  chk('sma200 ' + (want ? 'gated' : 'kept') + ' on ' + rng, M.taMaGated('sma200', stRange(rng, 'line')) === want);
});
chk('sma200 NOT gated on 1D/1W (Job 2)', M.taMaGated('sma200', stRange('1D', 'line')) === false && M.taMaGated('sma200', stRange('1W', 'line')) === false);

/* --- Job 8: the 200s ARE gated on monthly-granularity candle views --- */
/* A 200-month average needs 200 months of BTC history; only ~195 exist
   (Aug 2010–Nov 2026), so SMA/EMA 200 can never compute on a monthly
   view. Gated on monthly candles on every range that has them; Line
   views use daily closes (200-day MA) and daily/weekly/4h candles have
   enough history, so they are unaffected. */
['1W', '1M', '3M', '6M', 'YTD', '1Y'].forEach(function (rng) {
  chk('sma200 gated on monthly Candles ' + rng, M.taMaGated('sma200', stRange(rng, 'candles', 'monthly')) === true);
  chk('ema200 gated on monthly Candles ' + rng, M.taMaGated('ema200', stRange(rng, 'candles', 'monthly')) === true);
  chk('sma200 kept on daily Candles ' + rng, M.taMaGated('sma200', stRange(rng, 'candles', 'daily')) === false);
  chk('ema200 kept on weekly Candles ' + rng, M.taMaGated('ema200', stRange(rng, 'candles', 'weekly')) === false);
  chk('sma200 kept on Line ' + rng + ' (200-day MA)', M.taMaGated('sma200', stRange(rng, 'line')) === false);
  chk('ema200 kept on Line ' + rng, M.taMaGated('ema200', stRange(rng, 'line')) === false);
});
chk('sma20/ema20 NOT gated on monthly Candles (only the 200s)', M.taMaGated('sma20', stRange('6M', 'candles', 'monthly')) === false && M.taMaGated('ema20', stRange('6M', 'candles', 'monthly')) === false && M.taMaGated('sma50', stRange('6M', 'candles', 'monthly')) === false && M.taMaGated('ema50', stRange('6M', 'candles', 'monthly')) === false);
chk('monthly gate needs candles type (stale RGGRAN on Line does not gate)', M.taMaGated('sma200', {rng: '6M', CT: 'line', RGCT: 'line', RGGRAN: 'monthly'}) === false);

/* --- Job 9: Bollinger + ALL MAs gated on yearly-granularity candle views --- */
/* Only 17 yearly closes exist (2010–2026), so even the shortest MA
   (SMA/EMA 20) and the 20-period Bollinger can never compute on a yearly
   view. RSI is NOT gated: 6 warm yearly closes + 11 visible = 17, so its
   14 closes are covered and it draws from visible index 7. The Job 8
   monthly 200s gate keys on granularity, so it already covers the new
   5Y/10Y monthly views — verified here. */
['sma20', 'sma50', 'sma200', 'ema20', 'ema50', 'ema200'].forEach(function (k) {
  chk(k + ' gated on yearly Candles 10Y', M.taMaGated(k, stRange('10Y', 'candles', 'yearly')) === true);
  chk(k + ' kept on monthly Candles 10Y (only yearly gates all MAs)', M.taMaGated(k, stRange('10Y', 'candles', 'monthly')) === (k === 'sma200' || k === 'ema200'));
  chk(k + ' kept on daily Candles 10Y', M.taMaGated(k, stRange('10Y', 'candles', 'daily')) === false);
});
chk('bb gated on yearly Candles 10Y', M.taGated('bb', stRange('10Y', 'candles', 'yearly')) === true);
chk('bb kept on monthly/daily Candles 10Y', M.taGated('bb', stRange('10Y', 'candles', 'monthly')) === false && M.taGated('bb', stRange('10Y', 'candles', 'daily')) === false);
chk('rsi NOT gated on yearly Candles 10Y (14 closes covered by warm + visible)', M.taGated('rsi', stRange('10Y', 'candles', 'yearly')) === false);
chk('yearly gate needs candles type (stale RGGRAN on Line does not gate)', M.taMaGated('sma20', {rng: '10Y', CT: 'line', RGCT: 'line', RGGRAN: 'yearly'}) === false && M.taGated('bb', {rng: '10Y', CT: 'line', RGCT: 'line', RGGRAN: 'yearly'}) === false);
chk('sma200/ema200 gated on monthly Candles 5Y + 10Y (Job 8 gate covers the new views)', M.taMaGated('sma200', stRange('5Y', 'candles', 'monthly')) === true && M.taMaGated('ema200', stRange('5Y', 'candles', 'monthly')) === true && M.taMaGated('sma200', stRange('10Y', 'candles', 'monthly')) === true && M.taMaGated('ema200', stRange('10Y', 'candles', 'monthly')) === true);

/* --- Job 9: candle sizes offered per range (chart-type menu) --- */
function eq(a, b) { return JSON.stringify(a) === JSON.stringify(b); }
chk('sizes 1D', eq(M.allowedSizes('1D'), ['1h', '4h']));
chk('sizes 1W', eq(M.allowedSizes('1W'), ['daily', '4h']));
chk('sizes 1M', eq(M.allowedSizes('1M'), ['weekly', 'daily']));
chk('sizes 3M/6M/YTD gain Daily', eq(M.allowedSizes('3M'), ['monthly', 'weekly', 'daily']) && eq(M.allowedSizes('6M'), ['monthly', 'weekly', 'daily']) && eq(M.allowedSizes('YTD'), ['monthly', 'weekly', 'daily']));
chk('sizes 1Y keeps Monthly/Weekly', eq(M.allowedSizes('1Y'), ['monthly', 'weekly']));
chk('sizes 5Y Daily/Weekly/Monthly/Yearly', eq(M.allowedSizes('5Y'), ['yearly', 'monthly', 'weekly', 'daily']));
chk('sizes 10Y Daily/Monthly/Yearly', eq(M.allowedSizes('10Y'), ['yearly', 'monthly', 'daily']));
chk('sizes Max none (Line-only)', eq(M.allowedSizes('Max'), []));
chk('sizeLabel Yearly', M.sizeLabel('yearly') === 'Yearly' && M.sizeLabel('daily') === 'Daily' && M.sizeLabel('weekly') === 'Weekly' && M.sizeLabel('monthly') === 'Monthly' && M.sizeLabel('4h') === '4H candles');

/* --- EMA 20 never gated; EMA 50 on 1W only; EMA 200 NOT gated anywhere (Job 2) --- */
chk('ema20 never gated', RANGES.every(function (rng) { return M.taMaGated('ema20', stRange(rng, 'line')) === false; }));
RANGES.forEach(function (rng) {
  chk('ema50 ' + (rng === '1W' ? 'gated' : 'kept') + ' on ' + rng, M.taMaGated('ema50', stRange(rng, 'line')) === (rng === '1W'));
});
RANGES.forEach(function (rng) {
  chk('ema200 kept on ' + rng, M.taMaGated('ema200', stRange(rng, 'line')) === false);
});

/* --- unknown keys / unknown views fail open (not gated) --- */
chk('unknown switch key is not gated', M.taGated('nope', stRange('1D', 'line')) === false);
chk('unknown MA key is not gated', M.taMaGated('sma99', stRange('1D', 'line')) === false);
chk('unknown state is not gated', M.taGated('tl', null) === false && M.taGated('bb', {}) === false && M.taMaGated('sma200', null) === false);

console.log('TA GATING:', fails ? 'FAIL (' + fails + '/' + n + ')' : 'PASS (' + n + ' checks)');
process.exit(fails ? 1 : 0);
