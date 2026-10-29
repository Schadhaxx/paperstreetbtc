/* Candle ranges, Day 3 (exploration): headless harness for the overlay
   maths. The three functions are EXTRACTED from the shipped
   assets/js/btcchart.js (not transcribed) and evaluated, so a drift
   between the harness and the shipped code fails loudly. Run: node
   proposals/candle-ranges-day3/test-overlays.js */
var fs = require('fs');
var src = fs.readFileSync(__dirname + '/../../assets/js/btcchart.js', 'utf8');
function extract(name) {
  var i = src.indexOf('function ' + name + '(');
  if (i < 0) throw new Error('function not found: ' + name);
  var depth = 0, j = src.indexOf('{', i);
  for (; j < src.length; j++) {
    if (src[j] === '{') depth++;
    if (src[j] === '}') { depth--; if (depth === 0) break; }
  }
  return src.slice(i, j + 1);
}
var code = ['calcSMA', 'calcEMA', 'calcBollinger'].map(extract).join('\n');
eval(code); /* defines calcSMA, calcEMA, calcBollinger in this scope */
var checks = 0, fails = 0;
function check(name, cond) {
  checks++;
  if (!cond) { fails++; console.log('FAIL: ' + name); }
  else console.log('PASS: ' + name);
}
function approx(a, b, tol) { return Math.abs(a - b) <= (tol || 1e-9); }
var flat = []; for (var i = 0; i < 25; i++) flat.push(100);
var smaFlat = calcSMA(flat, 20);
check('SMA flat series: first 19 null', smaFlat.slice(0, 19).every(function (v) { return v === null; }));
check('SMA flat series: from 20th on = 100', smaFlat.slice(19).every(function (v) { return v === 100; }));
var seq = []; for (var k = 1; k <= 21; k++) seq.push(k);
check('SMA 1..20 at index 19 = 10.5', approx(calcSMA(seq, 20)[19], 10.5));
check('SMA 1..21 at index 20 = 11.5', approx(calcSMA(seq, 20)[20], 11.5));
var emaFlat = calcEMA(flat, 20);
check('EMA flat series: first 19 null', emaFlat.slice(0, 19).every(function (v) { return v === null; }));
check('EMA flat series: from 20th on = 100', emaFlat.slice(19).every(function (v) { return v === 100; }));
var step = []; for (var s = 0; s < 20; s++) step.push(100); step.push(120);
var emaStep = calcEMA(step, 20);
check('EMA step: at index 20 above 100 and below 120 (converges, does not jump)', emaStep[20] > 100 && emaStep[20] < 120);
var bbFlat = calcBollinger(flat, 20, 2);
check('Bollinger flat: first 19 null', bbFlat.slice(0, 19).every(function (v) { return v === null; }));
check('Bollinger flat: width 0, mid = 100', bbFlat[19] && bbFlat[19].upper === 100 && bbFlat[19].lower === 100 && bbFlat[19].mid === 100);
var alt = []; for (var a = 0; a < 25; a++) alt.push(a % 2 === 0 ? 90 : 110);
var bbAlt = calcBollinger(alt, 20, 2);
check('Bollinger volatile: upper > mid > lower', bbAlt[19] && bbAlt[19].upper > bbAlt[19].mid && bbAlt[19].mid > bbAlt[19].lower);
check('Bollinger volatile: width grows with volatility (width > 0, vs flat 0)', bbAlt[19] && (bbAlt[19].upper - bbAlt[19].lower) > 0);
check('Bollinger volatile: mid = SMA of last 20 (100)', approx(bbAlt[19].mid, 100));
var short = [1, 2, 3, 4, 5];
check('Short series (<20): SMA all null', calcSMA(short, 20).every(function (v) { return v === null; }));
check('Short series (<20): EMA all null', calcEMA(short, 20).every(function (v) { return v === null; }));
check('Short series (<20): Bollinger all null', calcBollinger(short, 20, 2).every(function (v) { return v === null; }));
console.log(checks + ' checks, ' + fails + ' failures');
process.exit(fails ? 1 : 0);
