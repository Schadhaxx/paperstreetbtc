#!/usr/bin/env node
/* TA Stage 4 pack cases (21 Nov 2026): the Grok Bot Stage 4 test pack's 16
   cases, run against Pepper's JS selection logic (tlSelectLines in
   assets/js/btcchart-ta.js — the port of the pack's ref_select_lines).
   Fixtures are copies of the pack's files (tests/fixtures/ta/stage4-pack-
   cases.json + stage4-pack-today.json); the pack itself lives outside the
   repo at ~/workspace/user/files/stage4-test-pack/. Run:
     node tests/test_ta_pack_cases.js [fixtures-dir]
   With no argument it uses the repo copies; pass the pack's fixtures dir
   to run against the originals. Prints one line per case + the stale
   constants check. Text output, no chart, no network. */
var fs = require('fs');
var path = require('path');
var M = require('../assets/js/btcchart-ta.js');
var FIXDIR = process.argv[2] || path.join(__dirname, 'fixtures', 'ta');
function load(name) { return JSON.parse(fs.readFileSync(path.join(FIXDIR, name), 'utf8')); }
/* The cases file is stage4-pack-cases.json in the repo copy, cases.json in
   the pack's own fixtures dir; the $file references inside use the
   original today filename in both. */
function loadCases() {
  try { return load('stage4-pack-cases.json'); } catch (e) { return load('cases.json'); }
}
var FIX = loadCases();
var fails = 0, n = 0;
function deepEq(a, b) { return JSON.stringify(a) === JSON.stringify(b); }
function resolveFile(spec) {
  if (!spec || typeof spec !== 'object') return spec;
  if ('$file' in spec) {
    var d = load(spec['$file']);
    if ('$delete' in spec) {
      d = JSON.parse(JSON.stringify(d));
      var cur = d, p = spec['$delete'];
      for (var i = 0; i < p.length - 1; i++) cur = cur[p[i]];
      delete cur[p[p.length - 1]];
    }
    return d;
  }
  var tfs = spec.timeframes;
  if (tfs && typeof tfs === 'object' && '$file_timeframes' in tfs) {
    var out = Object.assign({}, spec);
    out.timeframes = load(tfs['$file_timeframes']).timeframes;
    return out;
  }
  if (tfs && typeof tfs === 'object') {
    var hasTf = Object.keys(tfs).some(function (k) { return tfs[k] && typeof tfs[k] === 'object' && '$tf' in tfs[k]; });
    if (hasTf) {
      var out2 = Object.assign({}, spec), nw = {};
      Object.keys(tfs).forEach(function (k) {
        var v = tfs[k];
        if (v && typeof v === 'object' && '$tf' in v) nw[v.name || k] = load(v['$tf']).timeframes[v.name || k];
        else nw[k] = v;
      });
      out2.timeframes = nw;
      return out2;
    }
  }
  return spec;
}
FIX.cases.forEach(function (c) {
  n++;
  var got;
  try {
    got = M.tlSelectLines(resolveFile(c.file), c.timeframe, c.chart_tf, c.live_price, c.now, c.candles || null);
  } catch (e) { got = 'THREW ' + e.message; }
  if (deepEq(got, c.expect)) { console.log('ok  ', c.id); }
  else {
    fails++;
    console.log('FAIL', c.id, '(rule ' + c.rule + ')');
    console.log('  got:   ', JSON.stringify(got));
    console.log('  expect:', JSON.stringify(c.expect));
  }
});
/* The stale constants must match the pack's proposal exactly. */
n++;
if (deepEq(M.tlStaleAfterMs, FIX.stale_after_ms)) { console.log('ok   stale_after_ms matches the pack proposal'); }
else { fails++; console.log('FAIL stale_after_ms', JSON.stringify(M.tlStaleAfterMs), '!=', JSON.stringify(FIX.stale_after_ms)); }
console.log('TA PACK CASES:', fails ? 'FAIL (' + fails + '/' + n + ')' : 'PASS (' + n + ' checks)');
process.exit(fails ? 1 : 0);
