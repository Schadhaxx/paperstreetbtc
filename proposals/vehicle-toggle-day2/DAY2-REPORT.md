# Vehicle toggle — Day 2 complete (ledger mapping)

## Status — TEST BRANCH ONLY, NO DEPLOY, NO MAIN CHANGE, NO FRONTEND WIRING YET

- Branch: `pepper-vehicle-toggle-day1` (continued from Day 1; Day 2 is a second
  commit on the same test branch, it does not start a new branch)
- Base: Day 1 remote commit b56a0f6 (IBIT/FBTC backfill, baseline snapshot)
- NOT changed: `main`, `prices.yml` (live-quote list change still NOT made —
  pipeline change, needs its own approval at implementation time),
  `ledger.js` (sleeve weights, $100k start, STRC list untouched),
  `vehicle-daily.json` (Day 1 backfill untouched), any frontend file,
  `index.html` (no new script tag — the mapping lives in `book.js`, which
  is already loaded, so Day 3 wires the API, it does not add a file).
- No message to the Grok Bot, Chief of Staff, or Site Launch. No fee deducted.

## 1. What changed — `assets/js/book.js` only (plus this report + test)

The ledger engine is now parameterised by price series, in one engine —
not a second copy of the ledger logic, so spot and vehicle timelines
cannot drift apart:

- `buildTimeline(priceAt)` replaces the single hard-coded build. Spot:
  `priceAt` = history.json closes for every asset (unchanged behaviour).
  ETF: BTC = `vehicle-daily.json` close, every other asset = history close.
- New API (spot defaults preserved, all existing callers unchanged):
  - `B.loadVehicleData(vehicleJson)` — builds IBIT + FBTC timelines.
    It THROWS if a vehicle series misses any history session, so a
    partial series can never silently misprice a session (tested).
  - `B.loadVehicle()` — browser fetch of `assets/data/vehicle-daily.json`
    (Day 3 wiring; Day 2 tests call `loadVehicleData` directly).
  - `B.atV(k, d, vehicle)`, `B.navV(k, d, vehicle, pxFn?)`,
    `B.eventsV(k, vehicle)` — vehicle-aware holdings / NAV / events.
    `vehicle` = `'SPOT'` (default), `'IBIT'`, or `'FBTC'`.
  - `B.vehiclePriceOnOrBefore(v, d)` — last vehicle close on or before
    `d`: the weekend/holiday flat rule (ETF part flat at Friday close
    through the weekend, spot keeps moving).
- Existing `B.at / B.nav / B.value / B.events / B.bench / B.points`
  are untouched and still return spot values.

### Model point the parent must see — re-basing, not price-swapping

The Day 2 brief's shorthand ("BTC holding x selected vehicle price") can
be read two ways, and only one preserves the brief's own constraints
(weights and the $100k Jan 1 start untouched):

- WRONG: keep spot units and multiply by the ETF price. At base that
  reads Berkshire's BTC slice as 0.4572 spot units x $49.65 = ~$22.7k
  instead of $40k, and the sleeve no longer starts at $100,000.
- RIGHT (implemented): re-base the BTC slice in vehicle units at base.
  Berkshire BTC units become $40,000 / $49.65 = 805.64 IBIT units
  (or $40,000 / $76.23 = 524.73 FBTC units), so every sleeve still
  starts at exactly $100,000 in every mode, and then tracks the
  vehicle return. Non-BTC holdings, weights, and the $100k start are
  unchanged; only the BTC slice's unit denomination changes with mode.

Dividend buys follow the same rule, per the LOCKED decision: in ETF
mode STRC cash buys the ETF at the pay session's ETF close, in the
sleeve's existing split (Berkshire/Hodler 100% to the BTC-slice
equivalent, Hedge Fund 50/50 ETF/MSTR, Saylor Moon unchanged — no
BTC slice). In spot mode STRC cash buys spot exactly as today.

## 2. SPOT REGRESSION GATE — PASS, to the cent

Test: `proposals/vehicle-toggle-day2/test-vehicle-mapping.js` (Node,
headless; stubs window/location/fetch, feeds the real data-branch
`history.json` — 208 sessions, last 2026-10-28 — and the Day 1
`vehicle-daily.json`). Run: `node proposals/vehicle-toggle-day2/test-vehicle-mapping.js`
→ **ALL CHECKS PASSED**, exit 0.

Spot NAV at 2026-10-28, recomputed with the vehicle mapping in place,
vs the Day 1 baseline snapshot:

| Sleeve | Recomputed spot | Day 1 baseline | Match |
|---|---|---|---|
| Berkshire Killer | $97,640.65 | $97,640.65 | exact |
| Hodler Jam Sandwich | $95,331.57 | $95,331.57 | exact |
| Hedge Fund Killer | $95,742.85 | $95,742.85 | exact |
| Saylor Moon | $104,013.87 | $104,013.87 | exact |

Also passed: spot holdings units vs baseline (all within 5e-7, i.e.
snapshot rounding), spot receivable cash (Berkshire $101.22, Hodler
$50.61, Hedge Fund $50.61, Saylor $253.05), spot-via-`navV(SPOT)` ==
legacy `nav` for every sleeve, and base NAV = exactly $100,000.00 in
every mode for every sleeve.

## 3. Vehicle NAVs at 2026-10-28 (close, for Day 3 to display)

| Sleeve | Spot | IBIT mode | FBTC mode |
|---|---|---|---|
| Berkshire Killer | $97,640.65 | $97,677.48 | $97,682.13 |
| Hodler Jam Sandwich | $95,331.57 | $95,391.75 | $95,400.02 |
| Hedge Fund Killer | $95,742.85 | $95,789.65 | $95,796.16 |
| Saylor Moon | $104,013.87 | $104,013.87 | $104,013.87 |

Saylor Moon is identical in every mode, as required (no BTC slice).
ETF modes sit slightly above spot at 28 Oct — consistent with the
Day 1 tracking note (ETF cumulative −7.07%/−7.06% vs spot −7.15% over
10 months, plus dividend reinvestment at vehicle closes).

Dividend example (first settled STRC event, Berkshire, pay session
2026-02-02, cash $185.57 in every mode): spot buys 0.002358 BTC at
$78,688.77; IBIT buys 4.1965 units at $44.22; FBTC buys 2.7334 units
at $67.89. Hedge Fund 50/50 split verified in IBIT mode (cash/2 in
ETF, cash/2 in MSTR).

Weekend flat rule verified: `vehiclePriceOnOrBefore('IBIT',
'2026-01-03')` (Saturday) and `('FBTC', '2026-01-04')` (Sunday)
both return the Friday 2026-01-02 vehicle close.

## 4. Day 1 honest gap — STILL OPEN, plainly

The full-series independent cross-check of the backfill is NOT closed
by Day 2. Stooq was re-attempted once (the pipeline's documented
endpoint, `stooq.com/q/d/l/?s=ibit.us&i=d`); the fetch failed with a
network error, and that request was not retried through another tool
or endpoint. Tiingo full-series was not run (key is server-side in
GitHub Actions only, and the pipeline's Tiingo check covers only the
last 7 days). The backfill therefore still rests on Yahoo primary +
Day 1's independent sample check + session alignment + cumulative
tracking. **This must be closed before any deploy. Do not present it
as done.** Day 3 testing should include a cross-check pass via the
pipeline's own cross-check route if Stooq remains unreachable from
this environment.

## 5. What Day 3 needs

1. This branch + `book.js` API above (no other ledger change needed).
2. The Day 1 backfill, unchanged (`assets/data/vehicle-daily.json`).
3. Frontend: one shared toggle (tracker under the BTC live pill, top
   of the BTC chart popover, Benchmark-button style, default Spot),
   one re-render switching Pulse, tracker NOW/YTD, holdings rows
   (relabelled with the vehicle price), VS benchmark, and the compare
   portfolio line together, plus the persistent "You are in IBIT/FBTC
   mode" label (approved Day 1 defaults) and session-only persistence.
   Live vehicle prices come from `prices.json` IBIT/FBTC entries once
   the `prices.yml` list change lands; until then Day 3 previews use
   latest-close vehicle prices and must say so.
4. The still-open full-series cross-check (§4) closed before deploy.
5. The `prices.yml` live-quote list change (`IBIT`, `FBTC` added) —
   its own push approval at implementation time, NOT in this commit.
