#!/usr/bin/env node
/* Job 10 (22 Nov 2026): 1D Line comparison — CmpIntraMath pure-block
   unit tests (trim / align / rebase / stale rule), extracted from
   assets/js/btcchart-panel.js the same way test_cmp.js extracts
   CmpMath. Fixture sessions are synthetic Fri 20 Nov 2026 (EST) and
   Fri 17 Jul 2026 (EDT), 27 bars, matching the Yahoo payload shape
   verified live (range=2d&interval=15m, 27 bars, 0 nulls). */
const fs = require('fs'), path = require('path');
const R = path.join(__dirname, '..');
let n = 0, f = 0;
const chk = (name, ok, info) => { n++; if (!ok) { f++; console.log('FAIL', name, info === undefined ? '' : JSON.stringify(info)); } };
const src = fs.readFileSync(path.join(R, 'assets/js/btcchart-panel.js'), 'utf8');
const start = src.indexOf('var CmpIntraMath = (function () {');
const end = src.indexOf('})();', start);
if (start < 0 || end < 0) { console.log('FAIL CmpIntraMath block missing'); process.exit(1); }
const CmpIntraMath = eval(src.slice(start + 'var CmpIntraMath = '.length, end + 5));
const { etParts, sessionDateET, sessionOpenMs, sessionCloseEndMs, isEarlyClose, trimToSession, alignToPts, firstValue, holdFlat, rebaseTo100, isFresh } = CmpIntraMath;

/* --- ET math (EST + EDT) --- */
/* Fri 20 Nov 2026 9:30 AM EST = 14:30 UTC; 4:15 PM EST = 21:15 UTC. */
chk('sessionOpenMs EST is 14:30 UTC', sessionOpenMs('2026-11-20') === Date.UTC(2026, 10, 20, 14, 30));
chk('sessionCloseEndMs EST is 21:15 UTC', sessionCloseEndMs('2026-11-20') === Date.UTC(2026, 10, 20, 21, 15));
/* Fri 17 Jul 2026 9:30 AM EDT = 13:30 UTC; 4:15 PM EDT = 20:15 UTC. */
chk('sessionOpenMs EDT is 13:30 UTC', sessionOpenMs('2026-07-17') === Date.UTC(2026, 6, 17, 13, 30));
chk('sessionCloseEndMs EDT is 20:15 UTC', sessionCloseEndMs('2026-07-17') === Date.UTC(2026, 6, 17, 20, 15));
chk('etParts 14:30 UTC is 9:30 ET on 20 Nov', (function () { const p = etParts(Date.UTC(2026, 10, 20, 14, 30)); return p.date === '2026-11-20' && p.mins === 570; })());
chk('etParts 21:00 UTC is 16:00 ET on 20 Nov', (function () { const p = etParts(Date.UTC(2026, 10, 20, 21, 0)); return p.date === '2026-11-20' && p.mins === 960; })());
chk('etParts 13:30 UTC is 9:30 ET on 17 Jul (EDT)', (function () { const p = etParts(Date.UTC(2026, 6, 17, 13, 30)); return p.date === '2026-07-17' && p.mins === 570; })());
chk('sessionDateET is the ET date', sessionDateET(Date.UTC(2026, 10, 20, 19, 0)) === '2026-11-20');
chk('sessionDateET 02:00 UTC is still the ET previous date', sessionDateET(Date.UTC(2026, 10, 21, 2, 0)) === '2026-11-20');

/* --- Fixtures: 27 BTC points, Fri 20 Nov 2026, 9:30 AM-4 PM ET --- */
function btcPts(dateISO, utcHour, base, step) {
  /* 27 points, 15-min apart, starting at utcHour:30 UTC on the date. */
  const out = [];
  const t0 = Date.UTC(2026, dateISO[1], dateISO[2], utcHour, 30, 0);
  for (let i = 0; i < 27; i++) out.push({ t: t0 + i * 900000, v: base + i * step });
  return out;
}
const PTS_NOV = btcPts([2026, 10, 20], 14, 60000, 45); /* 14:30-21:00 UTC, $60,000 -> $61,170 */
const PTS_JUL = btcPts([2026, 6, 17], 13, 118000, -20); /* 13:30-20:00 UTC (EDT), $118,000 -> $117,480 */
function barsFrom(pts, base, step) { return pts.map(function (p, i) { const c = base + i * step; return [p.t, c - 1, c + 1, c - 2, c]; }); }
const SPX_BARS = barsFrom(PTS_NOV, 5980, 1.5);  /* 5,980 -> 6,019 */
const GOLD_BARS = barsFrom(PTS_NOV, 3525, -0.5); /* 3,525 -> 3,512 */
const MSTR_BARS = barsFrom(PTS_NOV, 210, 0.8);   /* 210 -> 230.8 */

/* --- trimToSession --- */
chk('trim keeps all 27 EST session points', trimToSession(PTS_NOV, '2026-11-20').length === 27);
chk('trim keeps all 27 EDT session points', trimToSession(PTS_JUL, '2026-07-17').length === 27);
chk('trim drops pre-open, post-close and other-day points', (function () {
  const pts = [
    { t: Date.UTC(2026, 10, 20, 14, 15), v: 59900 }, /* 9:15 AM ET */
    { t: Date.UTC(2026, 10, 20, 21, 15), v: 61200 }, /* 4:15 PM ET */
    { t: Date.UTC(2026, 10, 19, 14, 30), v: 59000 }, /* previous day */
    { t: Date.UTC(2026, 10, 20, 14, 30), v: 60000 }, /* 9:30 AM ET — kept */
    { t: Date.UTC(2026, 10, 20, 21, 0), v: 61170 }   /* 4:00 PM ET — kept */
  ];
  const out = trimToSession(pts, '2026-11-20');
  return out.length === 2 && out[0].t === Date.UTC(2026, 10, 20, 14, 30) && out[1].t === Date.UTC(2026, 10, 20, 21, 0);
})());
chk('trim of a wrong session is empty', trimToSession(PTS_NOV, '2026-11-19').length === 0);
chk('trim skips null and non-finite points', trimToSession([null, { t: NaN, v: 1 }, { t: Date.UTC(2026, 10, 20, 14, 30), v: 60000 }], '2026-11-20').length === 1);
chk('trim of empty is empty', trimToSession([], '2026-11-20').length === 0);

/* --- alignToPts --- */
chk('align maps every bar to its point', (function () { const a = alignToPts(PTS_NOV, SPX_BARS); return a.length === 27 && a[0] === 5980 && a[26] === 6019; })());
chk('align leaves a missing bar null', (function () {
  const bars = SPX_BARS.slice(); bars[10] = null;
  const a = alignToPts(PTS_NOV, bars);
  return a.length === 27 && a[10] === null && a[9] === 5993.5 && a[11] === 5996.5;
})());
chk('align leaves a non-finite close null', (function () {
  const bars = SPX_BARS.slice(); bars[5] = [PTS_NOV[5].t, 1, 2, 3, null];
  return alignToPts(PTS_NOV, bars)[5] === null;
})());
chk('align ignores bars outside the window', (function () {
  const bars = [[Date.UTC(2026, 10, 20, 22, 0), 1, 2, 3, 9999]].concat(SPX_BARS);
  const a = alignToPts(PTS_NOV, bars);
  return a.length === 27 && a.indexOf(9999) === -1;
})());

/* --- firstValue / rebaseTo100 --- */
chk('firstValue skips nulls', firstValue([null, null, 42, 43]) === 42);
chk('firstValue of all nulls is null', firstValue([null, null]) === null);
chk('rebaseTo100 anchors at 100', (function () { const r = rebaseTo100([60000, 60600, 59400], 60000); return r[0] === 100 && r[1] === 101 && r[2] === 99; })());
chk('rebaseTo100 keeps nulls null', (function () { const r = rebaseTo100([60000, null, 60600], 60000); return r[1] === null && r[2] === 101; })());
chk('rebaseTo100 with no base is all null', rebaseTo100([60000, 60600], null).every(function (v) { return v === null; }));

/* --- isFresh: the stale rule --- */
function doc(session, asOf, withSymbols) {
  return { v: 1, kind: 'cmp-intraday', asOf: asOf, session: session, sessionOpen: session + 'T14:30:00Z', symbols: withSymbols === false ? undefined : { SPX: { bars: SPX_BARS }, GOLD: { bars: GOLD_BARS }, MSTR: { bars: MSTR_BARS } }, failed: [] };
}
/* Live session: Fri 20 Nov 2 PM ET (19:00 UTC), asOf 10 min old -> fresh. */
chk('live session fresh under 30 min', isFresh(doc('2026-11-20', '2026-11-20T18:50:00Z'), Date.UTC(2026, 10, 20, 19, 0)).ok === true);
/* Live session, asOf 45 min old -> stale. */
chk('live session stale over 30 min', isFresh(doc('2026-11-20', '2026-11-20T18:15:00Z'), Date.UTC(2026, 10, 20, 19, 0)).ok === false);
/* Completed session: Fri 20 Nov 5 PM ET (22:00 UTC), asOf 4:30 PM -> fresh. */
chk('completed session fresh after the close', isFresh(doc('2026-11-20', '2026-11-20T21:30:00Z'), Date.UTC(2026, 10, 20, 22, 0)).ok === true);
/* Completed session, asOf from the previous day's run is still today's file -> fresh (asOf age is not capped after the close). */
chk('completed session fresh with an old asOf', isFresh(doc('2026-11-20', '2026-11-20T21:30:00Z'), Date.UTC(2026, 10, 21, 2, 0)).ok === true);
/* Last session: Sat 21 Nov 10 AM ET, session Fri 20 Nov, asOf Fri 4:30 PM -> fresh. */
chk('last session fresh on Saturday', isFresh(doc('2026-11-20', '2026-11-20T21:30:00Z'), Date.UTC(2026, 10, 21, 15, 0)).ok === true);
/* Last session: Sun 22 Nov -> fresh. */
chk('last session fresh on Sunday', isFresh(doc('2026-11-20', '2026-11-20T21:30:00Z'), Date.UTC(2026, 10, 22, 15, 0)).ok === true);
/* Last session: Mon 23 Nov 9 AM ET (before the open) -> fresh. */
chk('last session fresh Monday before the open', isFresh(doc('2026-11-20', '2026-11-20T21:30:00Z'), Date.UTC(2026, 10, 23, 14, 0)).ok === true);
/* Last session: Mon 23 Nov 10 AM ET (after the open) -> stale. */
chk('last session stale Monday after the open', isFresh(doc('2026-11-20', '2026-11-20T21:30:00Z'), Date.UTC(2026, 10, 23, 15, 0)).ok === false);
/* Last session: Tue 24 Nov, asOf Fri 4:30 PM (4 days old) -> stale. */
chk('last session stale over 4 days', isFresh(doc('2026-11-20', '2026-11-20T21:30:00Z'), Date.UTC(2026, 10, 24, 15, 0)).ok === false);
/* Holiday (must-fix 27 Nov 2026): Thu 26 Nov is Thanksgiving — no
   session today, so the Wed 25 Nov file stays fresh all day, including
   after 9:30 AM ET (before the fix it went stale at the open and 1D
   compare stayed off). */
chk('last session fresh on a holiday after the open', isFresh(doc('2026-11-25', '2026-11-25T21:30:00Z'), Date.UTC(2026, 10, 26, 20, 0)).ok === true);
chk('last session fresh on a holiday before the open', isFresh(doc('2026-11-25', '2026-11-25T21:30:00Z'), Date.UTC(2026, 10, 26, 14, 0)).ok === true);
/* Early close (must-fix 27 Nov 2026): Fri 27 Nov closes 1:00 PM ET,
   so the close end is 1:15 PM ET (18:15 UTC, EST), not 4:15 PM. */
chk('sessionCloseEndMs early close is 18:15 UTC', sessionCloseEndMs('2026-11-27') === Date.UTC(2026, 10, 27, 18, 15));
/* Early-close live session: Fri 27 Nov noon ET, asOf 10 min old -> fresh. */
chk('early-close live session fresh under 30 min', isFresh(doc('2026-11-27', '2026-11-27T16:50:00Z'), Date.UTC(2026, 10, 27, 17, 0)).ok === true);
/* Early-close completed session: Fri 27 Nov 2 PM ET, asOf the 1:15 PM
   final tick -> fresh (before the fix the file went stale from ~1:45 PM
   until 4:15 PM, because the close end was 4:15 PM and the 30-min rule
   kept failing on the final tick). */
chk('early-close completed session fresh at 2 PM ET', isFresh(doc('2026-11-27', '2026-11-27T18:15:00Z'), Date.UTC(2026, 10, 27, 19, 0)).ok === true);
chk('early-close completed session fresh at 1:45 PM ET', isFresh(doc('2026-11-27', '2026-11-27T18:15:00Z'), Date.UTC(2026, 10, 27, 18, 45)).ok === true);
/* Future session -> stale. */
chk('future session stale', isFresh(doc('2026-11-23', '2026-11-23T14:30:00Z'), Date.UTC(2026, 10, 20, 19, 0)).ok === false);
/* Bad shapes -> stale. */
chk('bad v stale', isFresh(doc('2026-11-20', '2026-11-20T18:50:00Z'), Date.UTC(2026, 10, 20, 19, 0)).ok === true && isFresh({ v: 2, kind: 'cmp-intraday', asOf: '2026-11-20T18:50:00Z', session: '2026-11-20', symbols: {} }, Date.UTC(2026, 10, 20, 19, 0)).ok === false);
chk('bad kind stale', isFresh({ v: 1, kind: 'ta-lines', asOf: '2026-11-20T18:50:00Z', session: '2026-11-20', symbols: {} }, Date.UTC(2026, 10, 20, 19, 0)).ok === false);
chk('bad session stale', isFresh({ v: 1, kind: 'cmp-intraday', asOf: '2026-11-20T18:50:00Z', session: '20 Nov', symbols: {} }, Date.UTC(2026, 10, 20, 19, 0)).ok === false);
chk('bad asOf stale', isFresh({ v: 1, kind: 'cmp-intraday', asOf: 'soon', session: '2026-11-20', symbols: {} }, Date.UTC(2026, 10, 20, 19, 0)).ok === false);
chk('no symbols stale', isFresh(doc('2026-11-20', '2026-11-20T18:50:00Z', false), Date.UTC(2026, 10, 20, 19, 0)).ok === false);
chk('null doc stale', isFresh(null, Date.UTC(2026, 10, 20, 19, 0)).ok === false);
/* EDT live session: Fri 17 Jul 2 PM EDT (18:00 UTC), asOf 10 min old -> fresh. */
chk('live session fresh in EDT', isFresh(doc('2026-07-17', '2026-07-17T17:50:00Z'), Date.UTC(2026, 6, 17, 18, 0)).ok === true);

/* --- holdFlat (Must-fix 27 Nov 2026, Market God re-test item 1) --- */
/* Early-close Fri 27 Nov: bars end 1 PM, BTC runs to 4 PM — the compare
   line must hold flat from its last bar to the right edge. */
chk('holdFlat fills trailing nulls with the last value', (function () {
  const out = holdFlat([100, 101, 102, null, null, null]);
  return out.length === 6 && out[3] === 102 && out[4] === 102 && out[5] === 102;
})());
chk('holdFlat keeps interior nulls (bridged/gapped by the renderer)', (function () {
  const out = holdFlat([100, null, 102, null, null]);
  return out[1] === null && out[3] === 102 && out[4] === 102;
})());
chk('holdFlat all-null stays all-null', holdFlat([null, null]).every(function (v) { return v === null; }));
chk('holdFlat no trailing nulls returns an equal copy', (function () {
  const out = holdFlat([100, 101, 102]);
  return out.length === 3 && out[0] === 100 && out[2] === 102;
})());
chk('holdFlat does not mutate its input', (function () {
  const inp = [100, 101, null, null]; holdFlat(inp);
  return inp[2] === null && inp[3] === null;
})());
chk('holdFlat on the early-close shape: 15 bars then 12 BTC points flat', (function () {
  /* 27 BTC session points (9:30 AM-4 PM ET); bars only for the first 15
     (9:30 AM-1 PM ET), then nulls to the 4 PM edge. */
  const bars = SPX_BARS.slice(0, 15);
  const aligned = alignToPts(PTS_NOV, bars);
  const held = holdFlat(aligned);
  return aligned.length === 27 && aligned[15] === null && aligned[26] === null
    && held[15] === aligned[14] && held[26] === aligned[14] && held[14] === aligned[14];
})());

/* --- yTickDaily compare % labels (Must-fix 27 Nov 2026, item 2) --- */
/* The reported axis read +3%, +3%, +1%, +1%, 0%, 0% — neighbouring nice
   ticks rounded to the same integer. One decimal keeps them distinct. */
const yTickSrc = (function () {
  const s = src.indexOf('function yTickDaily(v,sx,log){');
  const e = src.indexOf('\n}\n', s);
  if (s < 0 || e < 0) return null;
  return src.slice(s, e + 3);
})();
chk('yTickDaily extractable from the panel', yTickSrc !== null);
if (yTickSrc) {
  const curVal = function (v) { return v; }, curSym = function () { return '$'; };
  const yTickDaily = eval('(' + yTickSrc + ')');
  const labels = [102.6, 102.9, 101.4, 101.1, 100.4, 100.1].map(function (v) { return yTickDaily(v, true, false); });
  chk('one-decimal % labels are all distinct on the reported ticks', new Set(labels).size === 6, labels);
  chk('one-decimal % labels read +2.6% / +0.1%', labels[0] === '+2.6%' && labels[5] === '+0.1%', labels);
  chk('negative % label keeps its sign', yTickDaily(99.5, true, false) === '-0.5%');
}

/* --- isEarlyClose (Must-fix 27 Nov 2026, item 1 header) --- */
chk('isEarlyClose: 2026-11-27 true, 2026-11-20 false, 2026-12-24 true',
    isEarlyClose('2026-11-27') === true && isEarlyClose('2026-11-20') === false && isEarlyClose('2026-12-24') === true);

console.log('test_cmp_intraday.js: ' + (n - f) + '/' + n + ' passed');
process.exit(f ? 1 : 0);
