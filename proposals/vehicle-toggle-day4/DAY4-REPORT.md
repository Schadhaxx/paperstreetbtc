# Vehicle toggle — Day 4 headless testing (test branch only, no deploy)

Branch: `pepper-vehicle-toggle-day1`. No main change, no deploy, no
`prices.yml` change, no ledger/weight/$100k-start change, no fee
deducted, no message to Grok Bot / Chief of Staff / Site Launch.

Harness: `proposals/vehicle-toggle-day4/test-vehicle-day4.js`
(run: `node proposals/vehicle-toggle-day4/test-vehicle-day4.js`).
Data: real data-branch `history.json` (208 sessions, 2025-12-31 to
2026-10-28) + Day 1 `assets/data/vehicle-daily.json`, both unchanged
by Day 4.

## Result — HEADLESS MATRIX: ALL CHECKS PASSED (100 checks, 0 failures)

Plus 1 known issue reported as INFO in the harness (Compare failure
path, §5) and 1 open decision (popover chart, §6). Neither is a
matrix failure. Browser/visual verification is still outstanding and
is listed in §7 — it is the remaining Day 4 work, not done here,
because this environment has no live-browser task.

## 1. Full matrix: 4 sleeves × 3 vehicles × Live / Month-end / Close

Close NAVs — every session (208) × every sleeve/vehicle (12) = 2,496
NAVs, all finite and positive, none blank, none NaN, no crash:

| Sleeve | Spot 2026-10-28 | IBIT 2026-10-28 | FBTC 2026-10-28 |
|---|---|---|---|
| Berkshire Killer | $97,640.65 | $97,677.48 | $97,682.13 |
| Hodler Jam Sandwich | $95,331.57 | $95,391.75 | $95,400.02 |
| Hedge Fund Killer | $95,742.85 | $95,789.65 | $95,796.16 |
| Saylor Moon | $104,013.87 | $104,013.87 | $104,013.87 |

- Base invariant: every sleeve starts at exactly $100,000.00 in every
  mode at 2025-12-31 (re-basing, locked Day 2/3).
- Holdings consistency: at the latest close, units × prices + receivable
  cash == NAV to the cent for all 12 sleeve/vehicle combinations
  (e.g. IBIT Berkshire BTC units 852.0037, FBTC Berkshire 554.9201,
  vs spot 0.4834 — the re-based denominations, as designed).
- Saylor Moon identical in every mode at every session (0 differing
  sessions of 208) — it has no BTC slice, as required.
- Month-end matrix: all 11 `B.points()` dates (2025-12-31, 2026-01-30,
  02-27, 03-31, 04-30, 05-29, 06-30, 07-31, 08-31, 09-30, 10-28) × 12
  combos, all finite/positive, and month-end NAV == close NAV at the
  same session (one engine, no separate month-end path).
  Berkshire month-end example: Jan 30 Spot $95,638.82 / IBIT $95,443.71 /
  FBTC $95,499.51; Jun 30 Spot $79,632.62 / IBIT $79,688.49 / FBTC
  $79,654.73; Sep 30 Spot $94,691.14 / IBIT $94,636.51 / FBTC $94,612.15.
- Live-simulated matrix (s6 semantics, pre-`prices.yml`): holdings as
  of a non-session day (2026-10-29), priced at latest closes (ETF =
  latest vehicle close, spot/other = latest history close). Live NAV
  == 2026-10-28 close NAV for all 12 combos, as expected: no dividend
  event settles between 2026-10-28 and 2026-10-29, and no live quote
  is simulated headlessly. Live stock/ETF quotes themselves still
  need the browser flow (§7); live spot BTC is never substituted for
  an ETF price in any code path checked.
- Dividend buys: 156 settled buys checked across all sleeves/vehicles.
  Every ETF-mode BTC buy is priced at the pay session's vehicle close,
  every spot-mode BTC buy at the spot close, Hedge Fund 50/50 splits
  are exact to the cent in both modes, Saylor has no BTC buy, and
  dividend cash is identical across modes for every event (STRC
  holdings are mode-independent).

## 2. Weekends and holidays — ETF flat, spot live

- Weekends: every Saturday/Sunday in range (86 weekend days × 2
  vehicles = 172 checks) prices at the prior session close, 0 bad.
  Named checks: 2026-01-03/04 = Fri 2026-01-02 close;
  2026-10-24/25 = Fri 2026-10-23 close (IBIT $45.96, FBTC $70.61).
- Holidays: 7 NYSE holidays in range — 2026-01-19, 02-16, 04-03,
  05-25, 06-19, 07-03, 09-07 — none is a history session, and each
  prices at the prior session close, 0 bad.
- Spot side: spot has no weekend/holiday closes in history by
  construction; the live spot price comes from the browser live
  route (CoinGecko → Coinbase), not from a close, so spot "keeps
  moving" is a browser-flow property, listed in §7 for confirmation.

## 3. Missing-quote fallback — latest close, labelled, never spot

- `vehiclePriceOnOrBefore` on 2026-11-02 (after series end) returns
  the 2026-10-28 close for both vehicles (IBIT $46.14, FBTC $70.85),
  never blank, never the spot BTC price ($81,249.31).
- Homepage failure path (vehicle.js): on a vehicle-file failure the
  mode is forced back to Spot and ETF buttons stay disabled, with the
  label "Vehicle data unavailable — showing Spot BTC". It never shows
  spot values while claiming ETF mode. Verified statically.
- Compare failure path: see §5 — this is the one path that does NOT
  yet meet that standard.

## 4. Spot regression RE-RUN — PASS, to the cent

Spot NAV at 2026-10-28 recomputed with the full vehicle mapping in
place, vs the Day 1 baseline snapshot:

| Sleeve | Recomputed spot | Day 1 baseline |
|---|---|---|
| Berkshire Killer | $97,640.65 | $97,640.65 |
| Hodler Jam Sandwich | $95,331.57 | $95,331.57 |
| Hedge Fund Killer | $95,742.85 | $95,742.85 |
| Saylor Moon | $104,013.87 | $104,013.87 |

Spot via `navV(SPOT)` is identical to legacy `nav` for every sleeve.
This is the third consecutive pass of the same gate (Days 2, 3, 4).

## 5. Flagged Day 3 items — findings

### (a) One-tick transient — DOWNGRADED, not user-visible (headless analysis)

Construction confirmed: `index.html` loads s2.js before s6.js (both
defer, document order), so s2's `psvehicle` listener runs first: it
rebuilds chart lines and renders once with the previous mode's
`liveNow` stats if live prices are present. BUT s6's listener then
renders with the new vehicle and synchronously dispatches `pslive`,
and s2's `pslive` listener re-applies the new live state and
re-renders — all inside the same `psvehicle` dispatch, i.e. the same
JavaScript task, before the browser can paint. The intermediate stale
stat is written to the DOM and overwritten before any frame; the
`setTimeout(..., 0)` refresh in s2 is a redundant second refresh, not
the fix. No code change required on this item. Browser verification
(§7) should still confirm the painted state after a switch, but the
risk is low: the final DOM state after the dispatch is correct.
When no live prices are present (`liveNow` null), there is no
transient at all — the first render already uses the new mode's
close values.

### (b) Compare failure path — REAL ISSUE, fix before deploy (small)

`compare.js` `vehApply(m)` sets `VEH = m` immediately, then fetches
`vehicle-daily.json`. On fetch failure the catch only logs
`console.warn('vehicle data unavailable, Compare stays Spot')` — it
does NOT reset `VEH` to SPOT and does NOT redraw. Consequences:

- On first load with an ETF mode in sessionStorage: lines stay spot
  and the note still reads spot, so nothing is mislabelled yet
  (no redraw happens on the failure path).
- On any later `draw()` (range change, series toggle): the note now
  reads "You are in IBIT/FBTC mode — BTC sleeve priced in IBIT/FBTC
  at its latest close" while the lines are still spot values. That
  is a mislabel, reachable only when the vehicle file fails to load
  on the Compare page — a rare edge, and the homepage already
  handles the same failure correctly (forced Spot, disabled buttons).

Recommended fix (one function, before deploy, not a matrix re-run):
in the `vehApply` catch, set `VEH = 'SPOT'`, reset sessionStorage
to SPOT, call `draw()`, and add a visible note line "Vehicle data
unavailable — showing Spot BTC." Until that fix lands, this is the
only known correctness issue found in Day 4 headless testing. It
does not affect any mode where the vehicle file loads normally.

## 6. Popover chart stays Spot — OPEN DECISION, unchanged

`btcchart.js` keeps the popover chart itself on Spot BTC, with the
visible note: "Vehicle mode applies to Pulse, tracker, holdings and
Compare. This chart stays Spot BTC." The popover toggle changes the
shared mode; it does not re-price the chart series. Day 4 records
this as an open decision for Sunil and does not change it
unilaterally. If Sunil expects the popover chart line itself to
switch to IBIT/FBTC, that is a further Day 3-scope change (chart
series switch in `btcchart.js`), not a Day 4 fix.

## 7. What remains — browser verification (NOT done here)

This environment has no live-browser task, so the following are
explicitly outstanding and must be run by the parent before any
deploy decision:

1. Desktop + phone width: toggle clicks in both placements (tracker
   under BTC live pill, popover top), one re-render switching Pulse /
   tracker / holdings / VS / Compare together, no half-switched page.
2. Painted state after a vehicle switch (see §5a): confirm the final
   Now/YTD stats match the new mode, no stale spot value visible.
3. Fresh-tab Spot default; same-tab homepage → Compare keeps mode;
   session-only behaviour (new tab resets to Spot).
4. Popover note visible in ETF mode; popover chart line stays Spot
   (§6 decision).
5. Vehicle-file-failure path on the homepage (ETF buttons disabled,
   Spot shown) and, after the §5b fix, on Compare (visible notice,
   Spot shown).
6. Live flow once `prices.yml` adds IBIT/FBTC: ETF live quotes, not
   latest closes, with labels updated; weekend live behaviour (ETF
   flat at Friday close, spot live).
7. Mobile: toggle + popover on the phone sheet, tracker on small
   screens.

## 8. Deploy blockers — summary

- MUST FIX before deploy: §5b Compare failure-path reset + visible
  notice (small, one function). After that fix, re-run this harness
  (it will still pass) plus browser item 5 above.
- MUST LAND before deploy (already known, own approval): `prices.yml`
  live-quote list change (add IBIT, FBTC). Until then every ETF
  price is a latest close (series ends 2026-10-28) and every ETF
  label says so — honest, but not a live ETF price.
- OPEN DECISION before deploy: §6 popover chart (Spot vs vehicle
  series) — Sunil's call.
- NOT blockers: §5a transient (self-healing, no fix needed); the
  Finnhub-not-Stooq cross-check limit (a reviewer specifically
  requiring Stooq would still count that sub-item open; the
  full-series Finnhub check itself passed with zero flags).
- Otherwise: headless matrix, spot regression, weekend/holiday,
  missing-quote, dividend, and Compare-replica checks (1,664
  session checks, 0 differing) all pass. Nothing in Day 4 headless
  testing stops a deploy once §5b is fixed and the browser items in
  §7 are confirmed.
