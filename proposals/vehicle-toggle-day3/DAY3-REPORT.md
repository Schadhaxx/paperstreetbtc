# Vehicle toggle Day 3 — FRONTEND (test branch only, no deploy)

Branch: `pepper-vehicle-toggle-day1`. No main change, no deploy, no
`prices.yml` change, no ledger weight / $100k-start / non-BTC / Saylor
change, no fee deducted, no message to Grok Bot / Chief of Staff / Site
Launch.

## One shared toggle, not three

State protocol (the "component"): `sessionStorage['psVehicle']` (session
only, approved Day 1) + a window `psvehicle` CustomEvent. Every toggle
on the page listens to the same event, so one click switches everything
together — there is no per-section mode that can drift.

- `assets/js/vehicle.js` (new): tracker toggle UI, state, and the
  `book.js` vehicle-data load. ETF buttons stay disabled until
  `vehicle-daily.json` has loaded; if it fails, the mode is forced back
  to Spot and the buttons stay disabled with an explanatory label. It
  never shows spot values while claiming ETF mode.
- Tracker toggle: under the BTC live pill, above "Portfolios now"
  (`#pfLive`), Benchmark-button styling, default Spot BTC.
- BTC chart popover toggle (`assets/js/btcchart.js`): a Vehicle row at
  the top of the dialog, same three buttons. On pages without
  `vehicle.js` (Compare) it falls back to sessionStorage + the event.
  **The popover chart itself stays Spot BTC** — a note in the dialog
  says so. The toggle there controls the shared mode (Pulse, tracker,
  holdings, Compare), it does not re-price the chart series.
- Persistent mode label (approved Day 1 default): "You are in IBIT
  mode" / "You are in FBTC mode" appears in the tracker mode line, in
  the Pulse note, in the tracker note, in the Compare chart note, and
  as "BTC (IBIT)" / "BTC (FBTC)" on holdings rows. Spot mode reads
  "Spot BTC — the hurdle".
- Persistence: session-only (sessionStorage). A fresh tab starts in
  Spot; moving homepage → Compare in the same tab keeps the mode.

## What one re-render switches

Homepage (`assets/js/s6.js` + `assets/js/s2.js`, via Day 2 `book.js`):

- Pulse: values from `atV` + vehicle price, % move vs `navV` prior
  close (was spot `nav`).
- Tracker NOW/YTD + Vs benchmark: sleeve values from `atV`, prior
  close from `navV`; YTD chart paths rebuilt from `navV`. The
  benchmark line stays Spot BTC (the hurdle) in every mode.
- Holdings rows: vehicle units × vehicle price, BTC row relabelled
  "BTC (IBIT)" / "BTC (FBTC)", price label "IBIT · latest close
  Oct 28" (or "(latest available)" if the series ends before the
  latest history session).
- Month-end mode works the same way (vehicle close at the month-end
  session).

Compare page (`assets/js/compare.js`): the sleeve lines follow the
shared session mode (initial mode read from sessionStorage, later
changes via the popover toggle). The sleeve series are recomputed with
the same re-basing as `book.js` — BTC units = $weight / vehicle base
close, STRC cash buys the vehicle at the pay session's vehicle close
in ETF mode. Benchmarks, including Spot BTC, are untouched.

## Weekend / missing-quote rules

- Weekend/holiday: ETF price is the last vehicle close on or before
  the date (`vehiclePriceOnOrBefore`) — flat at the Friday close,
  spot keeps moving. Verified headless for Sat/Sun 2026-01-03/04.
- Missing quote: latest available vehicle close is used and labelled
  "latest close <date>" / "(latest available)". Never blank, never
  silently back to spot. (Until the `prices.yml` change lands, "latest
  close" is the honest label for every ETF price — see below.)

## Pre-prices.yml limitation (deliberate, not an oversight)

The `prices.yml` live-quote change (add IBIT, FBTC to the live-quote
list) is NOT in this commit — pipeline change, own approval, as
briefed. Until it lands, Day 3 previews use latest-close vehicle
prices (series ends 2026-10-28) and every ETF label says so. Live
spot BTC is never substituted for an ETF price.

## Verification

- `node --check` passes on all five changed JS files.
- Headless harness `proposals/vehicle-toggle-day3/test-vehicle-frontend.js`:
  ALL CHECKS PASSED. It proves book.js `navV` still matches the Day 2
  NAVs (IBIT 28 Oct: Berkshire $97,677.48, Hodler $95,391.75, Hedge
  Fund $95,789.65; FBTC: $97,682.13, $95,400.02, $95,796.16; Saylor
  $104,013.87 in every mode), the Compare replica matches book.js to
  the cent at base ($100,000) and at 28 Oct for every sleeve/vehicle,
  and the weekend-flat/latest-close semantics.
- Harness honesty: the Compare check runs a transcription of the
  compare.js replica against the same inputs — compare.js itself is
  browser-bound (Chart/DOM) and was not executed here. During the
  harness run it caught a real shape difference: compare.js carries
  its own ledger copy whose STRC rows are [ex, pay, $/share], while
  book.js rows are [record, ex, pay, $/share]. The production
  compare.js code already uses its own shape correctly; the harness
  initially fed it the book.js shape (NaN), which is how the
  difference was confirmed. The live Compare page still needs the
  Day 4 browser check below.
- **No browser/visual test was run in Day 3** (this environment has
  no live-browser task). That is Day 4's first job, not a skipped
  detail: desktop + phone-width toggle clicks in both places, one
  re-render switching Pulse/tracker/holdings/VS/Compare together,
  popover note visible in ETF mode, session-only behaviour in a fresh
  tab, and the vehicle-file-failure path (ETF buttons disabled, Spot
  shown).

## Files changed

- NEW `assets/js/vehicle.js`
- `index.html` (vehicle.js script tag only)
- `styles.css` (vehicle-toggle/mode styles only)
- `assets/css/nav.css` (popover vehicle row styles only)
- `assets/js/s6.js` (vehicle-aware Pulse/tracker/holdings)
- `assets/js/s2.js` (vehicle-aware YTD paths, psvehicle rebuild)
- `assets/js/btcchart.js` (popover vehicle row + note)
- `assets/js/compare.js` (vehicle sleeve series + psvehicle follow)
- NEW `proposals/vehicle-toggle-day3/DAY3-REPORT.md` (this file)
- NEW `proposals/vehicle-toggle-day3/test-vehicle-frontend.js`

NOT changed: `main`, `prices.yml`, `ledger.js`, `book.js`,
`vehicle-daily.json`, any price or weight.

## Known issues / Day 4 must check

1. Browser visual test not yet done (see above) — desktop, phone
   width, both toggle placements, Compare page, fresh-tab default.
2. One-tick transient in the YTD stats: on a vehicle switch, s2
   rebuilds the chart lines immediately and refreshes the Now/YTD
   stats on the next tick (its listener runs before s6's). Verify in
   the browser that no stale spot Now value lingers.
3. Compare page if `vehicle-daily.json` fails to load: the chart
   stays Spot with only a console warning, while the popover toggle
   may still show the ETF button active until reload. Day 4 should
   decide whether that failure path needs a visible Compare-page
   notice or whether the homepage failure path (disabled buttons)
   is sufficient.
4. `prices.yml` live-quote list change still outstanding (own
   approval) before any deploy; until then ETF prices are latest
   closes, labelled as such.
