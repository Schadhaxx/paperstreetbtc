# Combined preview — PREVIEW ONLY, NOT a deploy branch

Built 4 Nov 2026 at Sunil's request ("build one combined preview
with everything together") so he can play with all Saturday
items in one place. **Do NOT deploy this branch.** Grok Bot +
Chief of Staff still merge each Saturday item properly on
Saturday, one at a time, after Sunil's yes. This branch exists
only to preview; its merges were done by hand here, not by
Grok-side review, and it is not a substitute for that review.

## What is in it (sources, all test branches, base main 03dc9cc)
- Screener BTC popover fix (`pepper-screener-btc-fix`
  3d4b0d0 + 18f6585): screener loads et.js, btcchart et6,
  provCloseLabel guard.
- Compare tap-to-refresh (`pepper-compare-refresh` 49ff08f):
  Refresh button + "Data as of … close" note, no polling.
  Adapted, not copied verbatim, because Compare here also
  carries sleeve candles (see below); refresh re-runs run(),
  which resets the sleeve picker to Hodler — a preview
  quirk, not a deploy decision.
- BTC pill expand (`pepper-btc-pill-expand` bd306416):
  "↗ Chart ▾" chip, FLIP morph, reduced-motion fallback,
  nav.css cr016, btcchart et6/et2.
- Block clock V1 (`pepper-block-clock-v1` beeb380f, pill code
  d13f8fb): clock/index.html, secret double-click on the
  BTC popover price line, floating "PaperstreetBTC clock"
  pill on the screener only.
- Current-week candles (`pepper-current-week-candle`
  cd840ea): tools/indicator_weekly.py, 11 weekly JSONs at
  45 weeks (22 for SPCX), module data pins (gold v3, others
  v2, STOCK_V 20261104), WTI lastInProgress removed.
- Candle enhancements (`pepper-candle-enhancements`
  80a7762, latest at build time): all eight modal toggles
  (Bollinger, high/low, drawdown, patterns, volume, event
  dots, zoom, range stats), sleeve candles on Compare
  INCLUDING the tap-note fix and 100%-width + x-label fixes
  from 80a7762, weekly volume fields merged into the
  current-week files (current week volume fetched live for
  this preview: gold 566K, WTI 1.20M; US10Y/VIX have none,
  as indices), event dots list still EMPTY (no events
  invented).

## Known preview-only quirks
- Weekly data is frozen at build time (4 Nov); the live
  prices.json the screener tiles read is the branch's own
  snapshot, so tile prices lag live. The BTC pill itself
  still polls live.
- Compare sleeve-candle tap + width fixes are in here, but
  their browser re-check was still owed at build time —
  harness-verified only (tap leaves a week O/H/L/C note).
- Event dots toggle shows its "no events loaded" note, by
  design, until Saturday decides an event source.
- Refresh on Compare resets the sleeve picker to Hodler
  (see above).

## How it was built
Started from the enhancements tree, then merged the other
branches' changes file by file (btcchart taken from the
pill-expand version, then the screener fix + clock dblclick
applied; screener/compare HTML edited in place; weekly
JSONs = current-week files + volume fields by week).
Syntax-checked (node --check on all three JS files) and
harness-checked (Compare: 4 datasets, 203 labels, "Data as
of … close" note, picker present, tap note correct).
Browser smoke check of this combined copy was started
separately; its result is not recorded here until it lands.

## Browser smoke check — ALL SIX PASSED (3:34–3:36 p.m. EST 4 Nov, commit fcaa4c1, githack, read-only, live site untouched)
- Screener: floating "PaperstreetBTC clock" pill at bottom
  centre; Gold tile $4,075.30 (+3.42%) opened "Gold — YTD
  weekly candles" with all eight toggles; Volume on showed
  the red/green volume pane with note "Volume: latest week
  566K · average 798K" (566K = the current-week gold volume
  fetched for this preview — consistent).
- Compare: main line chart drew with lines (data as of
  3 Nov 2026 close); sleeve picker with all four sleeves
  (Hodler default) and red/green weekly bars; tapping a
  candle updated the note to "Week 2026-01-12 (2026-01-12 →
  2026-01-16, 5 sessions) · Open $104,429 · High $111,266 ·
  Low $104,429 · Close $109,492 · Week change +4.85%."
- This also browser-verifies the sleeve-candle tap fix: the
  tap code in this combined copy is the same as in
  `pepper-candle-enhancements` 80a7762 (only Compare-refresh
  additions differ). The enhancements branch in isolation
  has not had a separate browser re-check, but its tap code
  is what just passed here.
- Nothing failed in this smoke check.

## Update — BTC 4-hour candles on 1W added (4 Nov, Sunil's screenshot request)
Same 4H code as `pepper-btc-4h-candles` 94f4877, on top of
everything else in this preview: 1W Candles gains a 4H size
button (Daily stays default), Coinbase 4h bars, last 7 days
(~42 candles), pill shows the 4-hour UTC window. btcchart
pins bumped et6→et7 / et2→et3 so the new code is not served
from cache. Browser verification of 4H on this preview was
started separately; its result is not recorded here until
it lands.
