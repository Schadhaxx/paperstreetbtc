# Vehicle toggle — follow-up fixes, 29 Oct 2026 (test branch only)

Approved by Sunil 29 Oct 2026 ~8:39 a.m. ET (items 1 and 5 of the Day 4
decision list). No main change, no deploy.

## 1. Compare failure-path fix (approved)

**Problem (Day 4 report §b):** `compare.js` `vehApply(m)` set `VEH = m`
before fetching `vehicle-daily.json`, and the fetch catch only logged a
console warning. On any later `draw()` (range/series change) the Compare
note read "You are in IBIT/FBTC mode" while the lines were still spot
values.

**Fix (`assets/js/compare.js`):**
- New flag `VEHFAIL` (declared alongside `VEH`, `VEHD`).
- In the fetch catch: `VEH = 'SPOT'`, `VEHFAIL = true`,
  `sessionStorage.setItem('psVehicle', 'SPOT')`, sleeve series restored
  to spot values (`SER[k].v = VAL[k]`), then `draw()`.
- `draw()` now appends a visible notice to the Compare note when the
  flag is set: "Vehicle data unavailable — showing Spot BTC." Because
  the notice is driven by the flag (not by a one-off DOM write), later
  redraws keep it instead of clearing it.
- On a later successful ETF fetch, `VEHFAIL` is cleared, so the notice
  does not stick after recovery.
- The ETF-mode note text is suppressed in the failure case because
  `VEH` is back to `'SPOT'`; the failure notice replaces it, it does
  not sit alongside a contradictory mode note.

**Verification:** `node --check assets/js/compare.js` passes. The Day 4
harness was re-run after the fix (see §3). The fix itself is browser
code (Chart/DOM-bound) and was not executed headlessly; the browser
failure-path check (load Compare with `vehicle-daily.json` unavailable)
remains a Day 5 browser item.

## 2. prices.yml live-quote change (approved, test branch only)

**Change (`.github/workflows/prices.yml`, live-quote loop only):**
- Before: `['MSTR','STRC','TSLA','PLTR','SPY','QQQ','BRK.B','GLD']`
- After: `['MSTR','STRC','TSLA','PLTR','SPY','QQQ','BRK.B','GLD','IBIT','FBTC']`
- No other workflow step changed. The history/Tiingo symbol maps were
  not touched (they cover daily closes, not live quotes). The loop's
  existing behaviour is unchanged: a bad or missing quote keeps the
  previous price, and `stocks_ok` simply counts successful quotes in
  the run (it will read 10/10 instead of 8/8 once both new symbols
  return quotes).

**Verification status — NOT yet verified, plainly:** a test-branch
`prices.yml` change cannot be verified from the test branch. The
workflow's triggers are schedule + `workflow_dispatch` only (no push
trigger), and scheduled runs execute the default branch's workflow, so
the test-branch edit runs nowhere on its own. A manual dispatch
against the test branch was NOT run: it would check out the data
branch and write `prices.json`, which is a live-data effect outside
this test-branch-only approval. Live Finnhub quotes for IBIT/FBTC can
only be verified once this change lands on main and a scheduled run
(or an authorised dispatch) returns quotes for both symbols. Until
then, every ETF price shown is a latest close from
`vehicle-daily.json` (series ends 2026-10-28) and every ETF label says
so. Finnhub symbols `IBIT`/`FBTC` are standard tickers, but that is
not a substitute for the pipeline verification above.

## 3. Harness re-run after the Compare fix

`node proposals/vehicle-toggle-day4/test-vehicle-day4.js`:
**ALL CHECKS PASSED — 100 passes, 0 failures** (same matrix as Day 4:
2,496 NAVs, base $100,000 every mode, month-end, weekends, holidays,
missing-quote fallback, 156 dividend buys, Compare replica = book.js
1,664 checks, spot regression to the cent).

One harness assertion was updated to match the newly approved state,
and is flagged here rather than hidden: the check formerly asserting
"no prices.yml IBIT/FBTC change (deliberately outstanding)" now
asserts the live-quote list includes IBIT and FBTC. That is the only
reason the first re-run showed 99/100; after the assertion update the
run is 100/100. The harness footer line about the Compare failure path
was also updated (it no longer calls it a known issue).

## 4. Decisions recorded in this follow-up (unchanged by this work)

- Popover chart: STAYS Spot BTC, with its current note. That popover
  is the chart that opens when you click the BTC live pill / BTC price;
  there is no other popover chart.
- Compare benchmark: Spot BTC is ALWAYS the benchmark. The dashed
  benchmark line stays Spot regardless of vehicle mode.
- Static copy: kept as-is. "$40k BTC", "40% BTC", and "Spot BTC is the
  hurdle" wording stays in ETF mode (target-weight/hurdle copy; the
  values themselves already relabel).

## 5. Still open for Day 5 review

- Browser failure-path check for the Compare fix (see §1).
- Browser painted-state confirm for the one-tick transient
  (downgraded in Day 4: stale stat overwritten before paint).
- Live-quote verification for IBIT/FBTC once the prices.yml change
  lands on main (see §2).
- Final deploy approval: separate, after Grok Bot + Chief of Staff
  review of the test branch. Nothing in this follow-up deploys or
  authorises a deploy.
