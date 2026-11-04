# Candle enhancements — Saturday review (test branch only, NOT live)

Branch: `pepper-candle-enhancements`, base main `03dc9cc`.
Sunil, 4 Nov 2026: implement mockups 3 (Bollinger specifically), 5, 7, 9,
11 for the Saturday build. "Let's burn tokens. Get it all done."
Gate unchanged: Grok Bot diff review + Chief of Staff coordination +
Sunil's yes, one item at a time. Nothing here is live.

## What was built, and where

All five are OFF by default. Nothing about the default chart changes.

### Screener candle modal (`screener.html` + `assets/js/screener-indicator-chart.js`, pin stocks2→stocks3)
A toggle row under the weekly candle chart: Bollinger (20, 2σ) ·
High / low lines · Drawdown shading · Pattern hints. Toggles stay on
across symbols in the same page session. A note under the row shows the
computed values when a toggle is on. Applies to all 11 weekly candle
charts (4 indicators + 7 stocks).

- **Bollinger (mockup 3, Bollinger specifically):** 20-week SMA ± 2
  sample standard deviations on weekly closes, purple lines + light
  fill, gold dashed SMA. Needs 20 weeks; with fewer it says so and
  draws nothing. (SPCX has 21 weeks, so it just qualifies.)
- **High / low lines (mockup 5):** orange "Highest shown" line at the
  max high over shown weeks, grey "Lowest shown" line at the min low.
  LIMITATION, stated in the chart note and here: the shipped weekly
  files are YTD only, so these are NOT a lifetime ATH and NOT a full
  52-week history. A true ATH/52-week line needs pre-2026 weekly data
  added to the shipped files — a Saturday decision, not silently
  fudged here. The existing dashed cyan current line is untouched.
- **Drawdown shading (mockup 7):** translucent red shading between
  the running peak close and each later close while it sits below
  that peak ("underwater" shading). The note gives the max drawdown
  % and its peak→trough weeks, computed from weekly closes.
- **Pattern hints (mockup 9):** a small gold dot on a weekly candle
  whose shape matches, in this priority order: bullish/bearish
  engulfing, hammer, doji. Definitions (conservative, weekly OHLC):
  engulfing = opposite-colour body fully engulfing the prior body;
  hammer = lower shadow ≥ 2× body and upper shadow ≤ 0.5× body;
  doji = body ≤ 10% of the range. Tapping a marked candle adds
  "Pattern hint: <name> — a shape, not a prediction." to its pill.
  No pattern is ever called a signal.

### Compare page (`compare/index.html` + `assets/js/compare.js`, pin et1→et2)
- **Sleeve candles (mockup 11):** a new "Sleeve candles" section below
  the line chart, with a sleeve picker (all four sleeves). Weekly
  candles (Monday–Sunday on session dates, one-session weeks are
  partial) aggregated from the SAME daily sleeve values the line
  chart shows, so it follows the range picker above and the Spot /
  IBIT / FBTC vehicle mode. Tap a candle for its week O/H/L/C +
  week change in the note below. Sleeve value in USD, $100,000 at
  31 Dec 2025, same basis as the line chart.

## Harness results (logic test, main-branch shipped weekly files)
Bollinger last values / max drawdown / pattern counts, computed by
the shipped module code in Node (not by hand):
- Gold (44 weeks): SMA $4,246.31, upper $4,654.32, lower $3,838.29;
  max drawdown 25.7%; 5 pattern hints.
- WTI (44): SMA $87.48, upper $109.71, lower $65.25; max DD 38.4%;
  8 hints.
- US10Y (44): SMA 4.81%, upper 5.34%, lower 4.27%; max DD 6.6%;
  2 hints.
- VIX (44): SMA 16.36, upper 20.27, lower 12.44; max DD 54.1%;
  11 hints.
Pattern unit checks pass: bullish engulfing, bearish engulfing,
hammer, doji each detected on a constructed candle pair (one
floating-point edge fixed with a 1e-9 tolerance). Sleeve week
grouping unit-checked: Fri 30 Oct 2026 alone in week 2026-10-26;
Mon–Wed 2–4 Nov 2026 in week 2026-11-02 with O/H/L/C as expected.

## Merge notes
- This branch does NOT include the current-week candle work
  (`pepper-current-week-candle`, separate branch, also for Saturday).
  Both touch `screener-indicator-chart.js` and its pin — Grok merges
  the two, they are different areas of the file.
- This branch bumps `compare.js` et1→et2, same as the Compare
  refresh branch (`pepper-compare-refresh`). Different changes to
  compare.js; Grok merges, do not take one pin bump as the other.
- `screener.html` on this branch does NOT include the floating
  clock pill or the screener BTC popover fix — those live on their
  own branches (`pepper-block-clock-v1`, `pepper-screener-btc-fix`).
  All three touch screener.html in different places; Grok merges.

## Rollback
Delete the toggle row + note element from screener.html, revert
`screener-indicator-chart.js` and `compare.js`/`compare/index.html`
to main, and restore the pins (stocks2, et1). No data files changed,
no live change to roll back.

## Still to verify (Saturday checks)
- Browser check on the githack copy: toggles draw on gold + one
  stock, toggles off cleanly, phone width (390px), pattern pill
  wording, sleeve candles on Compare in Spot mode.
- Phone-width pass and the ATH/52-week full-history decision are
  open for Grok Saturday.

## Update — mockups 1 and 2 added (Sunil, 4 Nov 2026: "1,2. Add those.")
Same branch, same off-by-default rule. New toggles in the modal:
Volume · Event dots · Zoom: last 12 wks · Range stats.

- **Volume (mockup 1, part 1):** a volume pane under the price
  plot (same x slots, candle-coloured bars at 55% opacity, dashed
  average line, "Vol" label). Tapping a candle appends its volume
  to the pill (83.1M / 237K style). Weekly volume = sum of Yahoo
  daily volumes for that week, added to the shipped weekly files
  in this branch only: full coverage for all 7 stocks, gold, and
  WTI (gold last week 796K in the trial data); US10Y and VIX
  report zero volume on Yahoo (indices have no volume), so the
  module shows "no volume data in the shipped file" for those
  two instead of drawing empty bars. OHLC values untouched —
  the diff on the weekly files is volume lines only (plus the
  commas they require). PIPELINE FLAG: the pipeline tools
  (`stock_weekly.py` on main, `indicator_weekly.py` on the
  current-week branch) do not yet output a volume field, so a
  future regen without a volume update would drop these fields
  and the pane would hide gracefully — Grok must add volume to
  both tools before this goes live, or volume will be a
  test-branch-only feature.
- **Event dots (mockup 1, part 2):** mechanism built, NO events
  loaded. Orange dots above a candle's high + an "Event: …"
  pill line, driven by an `EVENTS` list that is deliberately
  EMPTY. No STRC dividend, Fed, or earnings date has been
  invented, and none exists in the repo for these price candles.
  Saturday decision (from the full analysis, D2): supply a real
  event source, or ship volume without event dots. Until then
  the toggle shows "No events loaded for this symbol yet."
- **Zoom + scrub + range stats (mockup 2):** Zoom shows only the
  last 12 weeks (Bollinger still computed on the full series,
  then sliced to the window; drawdown/stats recompute on the
  shown window, by design — that is the point of range stats).
  Scrub: drag across the canvas and the pill follows candle by
  candle; a tap works exactly as before. Range stats in the note:
  best/worst week, up-week %, and weekly-change volatility
  (sample SD). Harness on gold last 12 weeks: best +5.42%,
  worst −4.23%, up weeks 33%, volatility 2.69%.
- **Clash fixes from the full analysis (applied here, not just
  suggested):** pattern dots gold → white with dark outline
  (they clashed with the gold SMA line); Bollinger + drawdown
  fills drop to 7% when both are on (they muddied together at
  10%); base-line label now shifts away from high/low labels
  too, not just the current label; Bollinger/drawdown note says
  when the values include an in-progress latest week.
- **Merge notes, updated:** this branch now also touches the 9
  weekly JSONs with volume (gold, WTI, 7 stocks). It does NOT
  touch their OHLC values or their week counts, and it does NOT
  include the current-week candles — those stay on
  `pepper-current-week-candle`. Grok merges volume fields into
  whichever weekly files go live; do not take one branch's weekly
  files as a wholesale replacement for the other's.
- **Still to verify (Saturday checks, updated):** browser check
  on the githack copy for the four new toggles (volume pane +
  average line, event toggle note, zoom 12-week view, scrub
  drag, range stats), plus the earlier toggles + Compare sleeve
  candles, at phone width.

## Browser check 1 — screener PASSED, Compare FAILED, bug found and fixed (4 Nov, 3:10–3:12 p.m. EST, commit baac7e5c)
- Screener PASSED in full: Gold tile $4,070.40 (+3.30%) opened
  "Gold — YTD weekly candles"; all four toggles off by default;
  chart drew ending at $3,901.20; Bollinger on drew bands/SMA
  with note SMA $4,246.31 · upper $4,654.32 · lower $3,838.29;
  Bollinger off restored the normal note with no bands visible.
  (Note: this check ran on baac7e5c, before the volume/zoom/
  stats toggles and the white-dot clash fix landed in fc69496 —
  those still need their own browser check.)
- Compare PARTIALLY FAILED on the same commit: the "Sleeve
  candles" section and its description appeared, but no sleeve
  picker and no candle chart drew, and the main line chart also
  showed only an empty grid. Cause found by Pepper in code
  review + a Node harness, NOT a checker-environment quirk: the
  call that redraws sleeve candles was placed AFTER draw()'s
  closing brace, so it ran in run()'s scope before the sleeve
  variables were initialised, threw a "cannot access before
  initialisation" error, and aborted run() before the initial
  line-chart draw and before the picker was built. That one
  misplaced brace explains all three symptoms at once (empty
  line chart, no picker, no candles).
- FIX: the sleeve-candle redraw call moved inside draw(), after
  the note assignment and before draw()'s closing brace.
  Harness re-run (embedded closes, network stubbed off): 4 line
  datasets, 203 labels, picker buttons for all four sleeves,
  sleeve note "Weekly candles · Hodler Jam Sandwich · YTD ·
  2025-12-31 → 2026-10-21 · 43 weeks", canvas 560×280. (43
  weeks, not 44, because the harness used embedded closes
  ending 21 Oct, not live history — expected in the harness.)
- RE-CHECK REQUIRED: Compare sleeve candles + main line chart
  on the fixed commit, in a real browser, before Saturday.
  Do not treat the harness pass as a browser pass.

## Browser check 2 — new toggles PASSED (3:20–3:21 p.m. EST 4 Nov, commit fc69496, githack, read-only, live site untouched)
Screener module, page, and weekly data are unchanged between
fc69496 and the current head, so this check stands for the
current head too.
- Gold tile $4,074.30 (−2.41% at check time) opened "Gold — YTD
  weekly candles". All eight toggles present, all off by
  default; default note "Tap a candle for its week."
- Volume PASS: on → "Vol" pane under the price chart with
  green/red volume bars and a dashed average line; note
  "Volume: latest week 796K · average 804K." Off → pane
  removed, default note restored. (796K matches the harness
  value for gold's last shipped week.)
- Zoom PASS: on → Aug–Oct axis, 12 candles, price scale
  $3,857–$4,797, versus full YTD Jan–Oct $3,815.90–$5,670.50.
- Range stats PASS: note "Range stats (44 weeks): best 7.47%
  (19 Jan 2026 – 25 Jan 2026) · worst −8.68% (16 Mar 2026 –
  22 Mar 2026) · up weeks 48% · weekly volatility 3.18%."
- Event dots: presence + off-by-default confirmed only; its
  visual effect was not separately tested in this check
  (expected: no dots, since the events list is empty — the
  toggle note is the only visible change until a real event
  source is decided Saturday).
- Nothing failed in this check. Scrub drag was built but not
  separately browser-tested; Compare re-check on the fixed
  commit is still outstanding.
