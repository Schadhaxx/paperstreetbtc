# Candle ranges, Day 3 — SMA / EMA / Bollinger exploration (test branch only, NOT live)

**Branch:** `pepper-candle-ranges-day1` (same branch as Day 1 + Day 2 + the 1Y fix).
**Base:** remote head `2fa4bedd` before this push. No main change, no deploy.
**Status: EXPLORATION ONLY.** This ports the 27 Oct playground prototype's overlays
into the real chart so Sunil can see them in place. It is NOT a decided build:
Sunil, with Grok Bot + Chief of Staff, decides whether any of the three stays,
changes, or is dropped. Nothing here ships to the live site without Sunil's
final approval, as with every other candle-ranges item.

## What was ported (from the playground prototype)

Three separate toggles in a new "Overlays" row in the BTC chart popover,
next to the existing Chart / Size controls:

- **SMA 20 (candles shown)** — yellow `#facc15`, same colour as the playground.
- **EMA 20 (candles shown)** — cyan `#22d3ee`, same colour as the playground.
- **Bollinger (20, 2σ)** — a filled band (`rgba(248,113,113,0.10)`) plus
  upper/lower lines (`rgba(248,113,113,0.8)`) and a faint mid line
  (`rgba(248,113,113,0.45)`), same colours as the playground.

All three are **off by default** and visible **only in range candle view**
(1W, 1M, 3M, 6M, YTD, 1Y). They do not appear in line view, and they do
not appear in 1D at all.

## The granularity caveat — stated in the UI, not buried

All three overlays are calculated on the **displayed candle closes only**.
"20" therefore means **20 candles of whatever size is shown**:

- Daily candles → a 20-day SMA/EMA.
- Weekly candles → a 20-**week** SMA/EMA.
- Monthly candles → a 20-**month** SMA/EMA.

The buttons say "(candles shown)" for exactly this reason, the chart title
gains the active overlay names, and the note under the chart (when any
overlay is on) states: "Overlays are calculated on the candles shown:
20 means 20 candles of the size shown, not 20 days, unless the size is
daily." This is not a 20-day indicator on a weekly or monthly chart,
and it must not be presented as one.

Maths (playground semantics preserved exactly):

- SMA = mean of the last 20 closes.
- EMA = seeded on the first close, k = 2/(20+1), returned only from the
  20th candle on.
- Bollinger = SMA ± 2 × population standard deviation (divide by 20) of
  the same 20 closes.

The first 19 candles have **no overlay value** — nothing is padded or
invented for them. Consequence worth knowing before deciding: on views
with fewer than 20 candles, an overlay simply does not draw. That
includes 1W daily (7–8 candles) and 1Y monthly (~13 candles). It is
correct behaviour under the no-invention rule, but it means the toggles
look like they do nothing on those views.

## What was NOT changed

- **1D intraday is unchanged.** Its candle drawing, pill, and controls are
  untouched; the only 1D-path line added is a call that hides the
  overlay row (already hidden for 1D, since 1D is not a range).
- **Pill, grey-out rule, label logic:** untouched. Overlays draw after
  the candles and before the selection outline, so the outline stays on
  top; the pill still shows High / Low / Change for the tapped candle.
  SPX / Gold / MSTR stay greyed out in candle view.
- **Clear / redraw rule (same as the Day 1 fix):** switching ranges,
  granularities, or back to Line repaints through `draw()`, and the
  overlay row is hidden outright in the line view — including the
  candle-failure fallback path, where the chart type is still set to
  candles but no candles are drawn. Overlay lines therefore cannot
  survive into a line view, and toggling an overlay re-runs the range
  draw with the new set. The price range is extended to include overlay
  values so overlay lines are never clipped by the candle-only range.
- **No other file touched:** no `prices.yml`, screener, or vehicle code;
  no main change; no message to Grok Bot / Chief of Staff / Site Launch.

## Verification

- `node --check` on `assets/js/btcchart.js`: passes.
- `proposals/candle-ranges-day3/test-overlays.js`: extracts
  `calcSMA` / `calcEMA` / `calcBollinger` from the shipped file (not
  transcriptions) and runs 15 checks, 0 failures — flat series gives
  the flat value, SMA 1..20 = 10.5 at index 19, EMA converges toward a
  step without jumping to it, Bollinger width is 0 on a flat series
  and grows with volatility, mid = SMA, and all three are all-null on
  a series shorter than 20.
- **Not claimed:** browser verification. As with Day 1 / Day 2, the
  painted popover — overlay lines at phone width, toggle row layout
  with three long button labels, switching ranges/granularities with
  overlays on, and the pill over an overlay line — needs a browser
  check on the test-branch preview by an eligible parent before this
  is called done.

## Decision needed (for Sunil / Grok Bot + Chief of Staff)

1. Keep all three, keep a subset, or drop overlays entirely?
2. If kept, is the "(candles shown)" labelling clear enough, or does
   the granularity caveat need stronger wording (e.g. a per-view label
   like "20-week SMA" on weekly charts)?
3. Accept that overlays draw nothing on sub-20-candle views (1W daily,
   1Y monthly), or prefer a shorter window for those views (a new
   decision, not in this exploration)?
