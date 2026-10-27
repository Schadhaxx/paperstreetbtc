# Candle chart + MSTR toggle — proposal for Site Launch pickup

Branch: `pepper-candle-mstr-test`
Code in this branch: `assets/js/btcchart.js`, `assets/css/nav.css`
Status: TEST BRANCH ONLY. NOT live. NOT deployed to main.
Deploy gate: HELD for Friday Grok Bot + Chief of Staff review, then Sunil's final approval.
No deploy, no main-branch change, and no Grok Bot message is authorised by this proposal alone.

## What this is

A test-branch build for the banner BTC chart (the Live BTC popover):

1. A clean 1D chart-type control, and
2. An MSTR toggle alongside the existing S&P 500 and Gold toggles.

## 1D chart-type control — Line | 1H | 4H

- Shown ONLY when the 1D range is selected. It disappears on every other range (verified on 1M).
- Three buttons in one segmented control, labelled "Chart":
  - **Line** — the regular intraday line graph, DEFAULT. This is the live Part 1 chart already on main: Coinbase 15-minute candles, last 24 hours, ET, last point live.
  - **1H** — 1-hour candles, 24 candles per 24 hours, aggregated from the same Coinbase 15-minute data (4 x 15-min = 1 hour).
  - **4H** — 4-hour candles, 6 candles per 24 hours, aggregated from the same data (16 x 15-min = 4 hours).
- Tapping Line returns to the regular line instantly — same data, different view.
- Candles are BTC only, linear scale only for candles.
- S&P 500, Gold, and MSTR toggles are OFF for 1D in all three views (Line, 1H, and 4H).
- If OHLC is missing for any candle, the chart falls back to the regular Line — never blank.
- Tooltip / hover O/H/L/C for candles is NOT yet implemented in this test branch — it is listed under "Not yet done" in TESTING.md.
- This refines the earlier 4-hour-only 1D candle proposal: 1D now offers BOTH 1H and 4H, plus Line. 15-minute candles are NOT a separate view.

## MSTR toggle

- A new MSTR button in the banner BTC chart, alongside the existing S&P 500 and Gold buttons, styled the same way (orange #f97316, matching the site's MSTR colour).
- BTC stays primary and default. MSTR is opt-in, shown as a rebased line (% change from the first close in range), so it compares performance — not $80k BTC vs $146 MSTR on one price axis.
- Daily ranges (1W, 1M, 3M, 6M, YTD, 1Y, etc.): MSTR works like S&P 500 / Gold do today.
- 1D intraday: MSTR follows the S&P 500 / Gold rule — OFF for 1D, greyed out, with the label "MSTR unavailable for 1D intraday". MSTR is market-hours only, like S&P 500 and Gold.
- Data source for MSTR in this test branch: daily closes from the data-branch `history.json` `closes[d].MSTR` (the same source the pipeline already publishes). That covers recent ranges well; long ranges (5Y / 10Y / Max) are NOT yet verified for MSTR — see TESTING.md.
- Colour / label: MSTR orange, button text "+ MSTR" when off, "MSTR ✕" when on.

## Data and code notes for Site Launch

- 1D intraday source: Coinbase 15-minute candles (`https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=900`), last 24 hours, ET. The test branch keeps OHLC (open/high/low/close) from those candles, where the live Part 1 code kept only the close.
- Aggregation: `aggCandles(pts, per)` in `btcchart.js` — per = 4 for 1H, per = 16 for 4H. Open = first 15-min open in the group, close = last 15-min close, high = max high, low = min low.
- Candle rendering in this test branch: custom canvas drawing (`drawCandles1D`), NOT the `chartjs-chart-financial` plugin. That avoids the plugin / vendored Chart.js version question for now. If Site Launch prefers the plugin, that is a separate decision — it is not required to make this test branch work.
- State: `CT` in `btcchart.js` — `'line'` (default), `'1h'`, `'4h'`. The control element is `#bcCt`, the MSTR button is `#bcMstr`, CSS for both is in `assets/css/nav.css` (`.bc-ct`, `.bc-k-mstr`).
- MSTR daily series: built in `getData()` from `history.json` closes, with `MSTRK` sorted keys and `mstrOn(d)` (same carry-forward pattern as S&P 500 / Gold).
- No other site files are changed in this test branch. No ledger, no tracker, no compare, no pipeline, no workflow change.

## What Site Launch is being asked to do

- Pick up this branch, read this proposal and TESTING.md, run the chart yourself, and either continue the build, fix anything you find, or review it for Friday.
- You do NOT need Muse, Grok Bot tokens, or a new setup step to do that — the branch and this folder are the handover.
- Do NOT deploy to main from this branch without Friday Grok Bot + Chief of Staff review AND Sunil's final approval.

## Open questions for Friday (Grok Bot + Chief of Staff)

1. Hover / tap tooltip for candles: show O/H/L/C per candle, in the same style as the daily chart tooltip?
2. Long MSTR ranges: verify 5Y / 10Y / Max behaviour, or limit MSTR to ranges where history data exists, with a "MSTR data starts …" note like Gold's late-start note?
3. Minor visual fix: leftmost x-axis time label is slightly crowded in 1H/4H candle views (see TESTING.md) — worth a small label-spacing fix before deploy?
4. Should the MSTR toggle also appear in the open-source block-clock chart? That was an open question in the original MSTR proposal and is NOT decided here.
5. Is the custom-canvas candle rendering acceptable for deploy, or should the build switch to the vendored `chartjs-chart-financial` plugin first?

## Mockups (design reference, not live code)

Site-style mockups shown to Sunil on 26 Oct 2026, in the same order as the control:
- 1-hour candles, 24 candles, last 24 hours — illustrative, anchored to real BTC levels that day.
- 4-hour candles, 6 candles, last 24 hours — same day, grouped differently.
- Chart options control, Line | 1H | 4H, shown with 4H selected.

These mockups are design reference only. The test-branch code above is the actual implementation to review, not the mockup images.

## Timeline (for context, not a commitment)

- 26 Oct 2026, evening: mockups agreed, test-branch build approved, step 2 built, pushed, and visually tested (see TESTING.md).
- 27 Oct 2026 (planned): user preview of the test branch.
- 30 Oct 2026, Friday: Grok Bot + Chief of Staff review. Deploy only after that review AND Sunil's final approval.
- Vehicle toggle work is a SEPARATE track (Pepper, starting after the Friday handover report) — it is NOT part of this proposal.
