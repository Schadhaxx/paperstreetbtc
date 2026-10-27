# Testing — candle chart + MSTR toggle, test branch

Branch: `pepper-candle-mstr-test`
Commit tested: `a81a7941eb0027a73b7a57d118ba93faa624a24f` (btcchart.js + nav.css)
Test date: 26 Oct 2026, ~9:12 p.m. ET
Live BTC at test time: $80,187, +0.4% 24h
Preview route that worked: raw.githack.com for this branch. Localhost (127.0.0.1) was rejected by the browser environment, and jsDelivr rendered as plain text — use raw.githack for future test-branch previews.

## Syntax and aggregation (local, before push)

- `node --check assets/js/btcchart.js` — PASS, after fixing a missing close for the rebased `if(sx)` block after the MSTR dataset push.
- Aggregation test, 96 x 15-minute points:
  - 1H (per = 4): 24 candles — PASS
  - 4H (per = 16): 6 candles — PASS

## Browser visual test (all steps PASSED)

1. Live BTC header pill opens the "LIVE BTC · BTC/USD" popover. Range buttons: 1D, 1W, 1M, 3M, YTD, 1Y, 5Y, 10Y, Max. Clicking 1D works, 1D becomes pressed/highlighted.
2. 1D chart-type control: only for 1D, labelled "Chart" / "1D chart type", buttons Line, 1H, 4H. Line pressed by default. Regular intraday line rendered ($79.4k–$80.6k axis, 9:15 PM to 6:15 PM), captioned "Intraday Coinbase 15-minute candles, last 24 hours (ET); last point is the live price."
3. 1H: clicking 1H works (1H pressed). Chart changes from a line to a candle chart — not blank, not a line. Green and red candles with wicks. Caption: "Coinbase 1h candles, last 24 hours (ET). Green = close above open, Red = below." Header: "1D: BTC +0.33% · last 24 hours, 1h candles, from 9:15 PM ET ($79,952)." Candle count about 24.
4. 4H: clicking 4H works (4H pressed). Candle chart rendered, not blank, exactly 6 candles: green, green, red, green (tall), red (tall), green, left to right. Header: "1D: BTC +0.33% · last 24 hours, 4h candles, from 9:15 PM ET ($79,952)."
5. Back to Line: clicking Line restores the regular intraday line, identical in shape and $79.4k–$80.6k range to the original 1D line, Line pressed again.
6. Daily range / MSTR: clicking 1M works (1M pressed; "1M: BTC -5.0% · from 2026-09-26 ($84,406)"). The 1D chart-type control disappears on 1M — confirming it is 1D-only. Toggle row on 1M shows BTC alongside + S&P 500, + Gold, and + MSTR in full colour, all usable. Clicking + MSTR changes it to "MSTR ✕" (pressed) and adds an orange MSTR line (BTC cyan vs MSTR orange, % -change axis, MSTR ending near -12%). Returning to 1D turns all three off/greyed again, with labels "S&P 500 unavailable for 1D intraday", "Gold unavailable for 1D intraday", and "MSTR unavailable for 1D intraday".

## Issues found

- Minor visual only: slight crowding of the leftmost x-axis time label in the 1H/4H candle views (the 9:15 PM label sits close to the neighbouring label/caption area). It remained readable and did not obscure the candles. Suggested fix before deploy: small label-spacing adjustment in the candle view.
- No blank charts, missing buttons, or visible error messages in any tested state. The popover was centred and readable throughout, with a working close (✕) button. The first popover open briefly showed "Loading…" before chart data loaded — normal loading, not a blank-chart failure.
- Note on console: no browser-console readout was available in that test tool, so "no console errors" means no errors were visible in the UI, not a console-log inspection.

## Not yet done (for Site Launch / Friday review)

- Hover / tap tooltip showing O/H/L/C per candle (the code note in the 1D caption says this is for the final build).
- Mobile / phone-sheet check of the 1D control and candle charts.
- Long MSTR ranges (5Y / 10Y / Max) — MSTR data source is history closes, which covers recent ranges; long-range behaviour not yet verified.
- Label-spacing fix for the crowded leftmost x-axis label in candle views (above).
- No deploy, no main-branch change, no Grok Bot message in this test branch.

## How to preview this branch yourself

- Checkout branch `pepper-candle-mstr-test`, or open the same branch via raw.githack.com (see "Preview route that worked" above).
- Open the site, click the Live BTC pill, select 1D, and use Line / 1H / 4H. Then select 1M and use the MSTR toggle.
- Do NOT deploy to main without Friday Grok Bot + Chief of Staff review AND Sunil's final approval.
