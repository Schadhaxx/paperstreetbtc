# Candle ranges Day 1 — browser-test fix report (29 Oct 2026)

Test branch only (`pepper-candle-ranges-day1`). No main change, no deploy,
no spec/default/1D-behaviour change beyond the bug fixes below.

## 1. CLEAR BUG — FIXED: stale 4H pill / stale 4H canvas after switching to Line

Browser test (preview commit ae3d8e3c, reproduced twice): on 1D, open a 4H
pill, switch 4H → Line. The line chart rendered, but the old 4H pill stayed
over it. Clicking the pill's ✕ removed the pill but REVERTED the canvas to
the old 4H candles, even though Line was still selected and the header/footer
described Line mode. Re-clicking Line restored the correct line chart.

### Root cause

The pill and the canvas listeners are shared between the 1D candle view and
the 1W/1M range candle view, and nothing tied them to the *current* chart
type:

- Switching to Line never cleared the pill: the 1D line path and `drawDaily`
  created the Chart.js line chart but never hid the `bcSel` pill element or
  reset `CANDSEL`.
- Dismissing the pill always called `redrawCandles()`, which unconditionally
  repainted `CAND` — still the old 4H candle array — onto the canvas,
  destroying the line chart's painted output while the Line state (header,
  footer, selected button) stayed Line.
- The canvas listeners had the same hole: they were attached once to the
  shared canvas and used stale `CANDGEOM` even in a line view, so a click or
  hover on the line chart could also resurrect old candles.

### Fix (all in `assets/js/btcchart.js`)

- New rule, enforced in one place: switching chart type ALWAYS clears pill +
  selection + guide; dismissing a pill NEVER changes the chart type and
  NEVER touches the canvas unless a candle view is currently active.
- New helpers: `candViewActive()` (true only for 1D with CT != Line, or
  1W/1M with RGCT == Candles), `hideCandPill()`, `clearCandState()`
  (CANDSEL = CANDHOV = -1 + hide pill), and `dismissCandInfo()` (clear state;
  redraw only if a candle view is active and its candle array exists).
- Pill tap and pill ✕ now call `dismissCandInfo()` instead of
  `CANDSEL=-1; redrawCandles(); showCandInfo(-1);`.
- Canvas mousemove / mouseleave / click now return early when no candle
  view is active, so the line chart's canvas is never repainted by candle
  code. Same-candle tap (dismissal) goes through `dismissCandInfo()`, which
  clears the hover guide as well as the selection — this also fixes the
  single-observation faint dashed guide left after same-candle dismissal on
  1W, in all three dismissal paths (pill tap, ✕, same-candle tap).
- `redrawCandles()` itself is now guarded: if no candle view is active it
  only hides the pill and returns.
- The 1D line path and `drawDaily()` (the line view for every other range)
  call `clearCandState()` before drawing, so no pill can survive a switch
  to Line from any entry point (type button, range button, or fallback).

## 2a. MINOR — FIXED: 1M Daily x-axis labels running together

On 1M Daily, the first candle (Sep 28) and the month-change candle (Oct 1)
sat ~18px apart, and both date labels were drawn unconditionally, so they
read as "Sep 28Oct 1". `drawCandlesRange` now applies the same 62px spacing
guard the live 1D view uses: a date label is skipped if it would land
within 62px of the previous one (the first label is always drawn).

## 2b. MINOR — FIXED: duplicate "Candles" label in the granularity row

The 1M granularity row read "Chart Line Candles Candles Weekly Daily"
because the granularity group label span (`bcCgGranLab`) also said
"Candles". The duplicate label is removed: that span now reads "Size", so
the row reads "Chart Line Candles Size Weekly Daily". The span's id and its
show/hide logic in `syncCg()` are unchanged.

## 2c. MINOR — FIXED: 1M Daily x-axis too sparse (only "Sep 28")

Browser retest on 829ce4a4: the 2a guard fixed the collision but overcorrected.
On 1M Candles → Size: Daily (31 daily candles), the axis showed only "Sep 28"
legibly, unlike the 1M Line view (09-28, 10-03, 10-08, 10-13, 10-18, 10-23,
10-28). 1W and 1M Weekly were sparse for the same reason.

### Root cause (not just "the guard is too aggressive")

`drawCandlesRange` only ever *considered* labels at the first candle and at
ET month changes — two candidates on 1M Daily (Sep 28, Oct 1). Oct 1 was then
killed by the guard: it was clamped to L+30 = 92px while Sep 28 was also
clamped to 92px, ~27px apart, under the 62px threshold. And the separate
last-candle label on a second row never drew at all, because the last
candle's x (= W−R) fails that row's `x < W−R−32` test. So the guard was not
the whole story — the candidate set was.

### Fix (all in `assets/js/btcchart.js`)

- New `rangeLabelIndices(n, iw)`: evenly spaced label indices, first and
  last always included, at most one label per ~64px of plot width
  (count = min(n, max(2, floor(iw/64))), indices rounded evenly across
  0..n−1). `drawCandlesRange` labels exactly those indices, in one row.
- The 62px guard stays as a safety net, tightened to 56px for this view
  only (labels are ~40px wide, so 56px centre spacing still leaves a clear
  gap; 56px is what lets the last label survive its 24px edge clamp at
  wide widths, where it otherwise sat 61px from its neighbour).
- Edge clamp narrowed from L+30 / W−R−30 to 24px from the canvas edge
  (the label's half-width): the old L+30 clamp pushed the first label 30px
  right, which would have made the second label fail the guard again.
  The 1D view's own clamp is unchanged.
- The separate last-candle second-row label is removed — the last candle
  is now in the main label row, so it cannot be skipped by its own x test.

### Label sets produced (headless, `rangeLabelIndices` extracted from the
shipped file, not a transcription; dates shown are the test series'
relative positions — the live chart's own candle times set the actual dates)

- 31 candles, popover width 640 (plot 566px): indices
  [0, 4, 9, 13, 17, 21, 26, 30] — 8 labels, every ~4–5 days, first to last,
  minimum centre spacing 63px, guard passes on all.
- 31 candles, width 500: [0, 6, 12, 18, 24, 30] — 6 labels, ~6 days apart.
- 31 candles, phone width 390: [0, 10, 20, 30] — 4 labels, ~10 days apart.
- 31 candles, width 800: [0, 3, 6, 9, 12, 15, 18, 21, 24, 27, 30] — 11 labels,
  minimum spacing 61px, guard passes on all.
- 7 candles (1W): all 7 at width 640; [0, 2, 4, 6] at phone width 390.
- 5 candles (1M Weekly): all 5 at width 640; [0, 1, 3, 4] at phone width 390.
- `node --check assets/js/btcchart.js`: passes. Browser re-test still
  needed (parent) on the new commit below.

## What was NOT changed

No spec, default, or 1D behaviour change: 1W/1M control, defaults (Line,
1M Weekly), SPX/Gold/MSTR grey-out rule, and the 1D Line/1H/4H + pill are
untouched. No main, prices.yml, screener, or vehicle code touched.

## Verification

- `node --check assets/js/btcchart.js`: passes.
- `proposals/candle-ranges-day1/test-agg.js` (aggregation harness, unchanged):
  passes (all checks + ALL CHECKS PASSED).
- Browser re-test still needed (parent): the 4H pill → Line sequence, all
  three pill dismissal paths on 1D and 1W, the 1M Daily axis, and the
  granularity row, on the new commit below.
