# Vehicle Toggle — Day 5 Review Package

**For: Grok Bot + Chief of Staff review**
**Branch: `pepper-vehicle-toggle-day1` (test branch only)**

## Status

**Built and verified, READY TO BE CHECKED — NOT live.**

- The frontend toggle exists only on the test branch `pepper-vehicle-toggle-day1`. It has not been deployed to the live site, and nothing in this package deploys it or authorises a deploy.
- The `prices.yml` live-quote change (adding IBIT and FBTC to the live-quote symbol list) is on **main** as commit `75cfaf44`. That change is **pipeline only**: it lets the scheduled prices workflow fetch IBIT/FBTC live quotes into the data branch. It is **not** a frontend deploy — the toggle itself is still test-branch only, and the live site shows no vehicle toggle.
- Per the standing test-branch review rule: **all versions of this job live on the test branch, one commit each, in order; main only has the final deployed version.** Review this job on the test branch, not on main.

## Day-by-day summary (remote commits, test branch)

| Day | Remote commit | What it contains |
| --- | --- | --- |
| Day 1 — data + baseline | `b56a0f6` | IBIT/FBTC Yahoo daily-close backfill, 2025-12-31 to 2026-10-28, 208 sessions, as `assets/data/vehicle-daily.json` (a separate vehicle series; no spot BTC close touched or overwritten). Spot-regression baseline snapshot at 28 Oct closes: Berkshire $97,640.65, Hodler $95,331.57, Hedge Fund $95,742.85, Saylor Moon $104,013.87. |
| Day 2 — ledger mapping | `9e4f1e5a` | `assets/js/book.js` only: the ledger engine parameterised by price series (`buildTimeline(priceAt)`, `loadVehicleData`, `atV`, `navV`, `eventsV`, `vehiclePriceOnOrBefore`). All existing callers unchanged. No change to main, `prices.yml`, `ledger.js` (weights, $100k start, STRC list), `index.html`, or any frontend file. |
| Cross-check | `50883e00` | Full-series independent cross-check report (see "Cross-check" below). `vehicle-daily.json` unchanged by the cross-check. |
| Day 3 — frontend | `a300ae77` | Shared toggle module `assets/js/vehicle.js` plus wiring in `index.html`, `styles.css`, `assets/css/nav.css`, `assets/js/s6.js`, `assets/js/s2.js`, `assets/js/btcchart.js`, `assets/js/compare.js` (10 files, +422/−16). |
| Day 4 — testing | `47c3a31` | Day 4 review package (`proposals/vehicle-toggle-day4/DAY4-REPORT.md`) and headless harness (`proposals/vehicle-toggle-day4/test-vehicle-day4.js`), plus the browser visual test on the `a300ae77` preview (see "What was verified"). |
| Follow-up — Compare failure-path fix | `b126146f` | Fix in `assets/js/compare.js` (see "Follow-up fix") plus the Day 4 harness update. |
| Follow-up — report | `1542befd` | Follow-up report (`proposals/vehicle-toggle-day4/FOLLOWUP-FIXES-2026-10-29.md`), including the correction that the `prices.yml` change could not be pushed via the GitHub App API (403 for workflow files) and was later landed on main via a web edit as `75cfaf44`. Current test-branch head at the time of this package. |

## What the toggle does

- One **global visitor toggle, default Spot BTC**, with IBIT and FBTC options, placed in the tracker under the BTC live pill and above "Portfolios now", styled like the existing Benchmark buttons, and also at the top of the BTC chart popover.
- Selecting IBIT/FBTC re-prices the BTC sleeve **everywhere the portfolio is shown** — Pulse, tracker NOW/YTD, holdings rows (relabeled "BTC (IBIT)" / "BTC (FBTC)", vehicle units × vehicle price), VS benchmark, and the Compare portfolio line.
- Sleeve weights, the $100,000 Jan 1 2026 start, and non-BTC holdings stay the same. Saylor Moon is unchanged in every mode (it holds no BTC). Spot BTC remains the default **and** the hurdle/benchmark.
- ETF mode is market-hours only: the BTC part is flat on weekends at the Friday ETF close. ETF returns differ slightly from spot (fees already baked into the ETF price/NAV daily — no fee is subtracted again — plus premium/discount).
- Persistence is session-only (per tab); a fresh tab starts in Spot BTC. A persistent "You are in IBIT/FBTC mode" label appears under the toggle and in the Pulse, tracker, and Compare footnotes while in ETF mode.

## Locked decisions (do not re-litigate in review unless Sunil reopens them)

1. **Rebasing, not price-swapping** (locked by Sunil, 29 Oct ~8:07 a.m. ET). Keeping spot units × ETF price would wrongly read Berkshire's BTC slice at base as ~$22.7k instead of $40k. Instead the BTC slice is re-denominated in vehicle units at the 31 Dec vehicle close ($40,000 / $49.65 = 805.64 IBIT units), so every sleeve starts at exactly $100,000 in every mode and then tracks the vehicle return.
2. **In ETF mode, STRC dividends buy the ETF** (locked 29 Oct ~7:49 a.m. ET), not spot BTC. Dividend buys follow the same re-basing, at the pay session's ETF close (Hedge Fund 50/50 ETF/MSTR; Saylor unchanged).
3. **Session-only persistence + persistent mode label** (Day 1 defaults, approved 29 Oct ~8:01 a.m. ET).
4. **Popover chart stays Spot BTC** (decided 29 Oct ~8:39 a.m. ET). The popover is the chart that opens when clicking the BTC live pill / BTC price; there is no other popover chart. The chart itself stays Spot, with the note: "Vehicle mode applies to Pulse, tracker, holdings and Compare. This chart stays Spot BTC."
5. **Spot BTC is ALWAYS the benchmark** (decided 29 Oct ~8:39 a.m. ET). The Compare dashed benchmark line stays Spot regardless of vehicle mode.
6. **Static copy stays as-is** (decided 29 Oct ~8:39 a.m. ET). "$40k BTC", "40% BTC", "Spot BTC is the hurdle" wording is target-weight/hurdle copy and is kept in ETF mode — **while portfolio BTC values in ETF mode ARE IBIT/FBTC-based** (units, prices, and NAVs relabel and re-price). The static words do not change the numbers underneath.
7. **`prices.yml` live-quote change approved** (29 Oct ~8:39 a.m. ET) and landed on main as `75cfaf44` (see Status). Live-quote verification is still pending (see "Still open").

## Cross-check (Finnhub, not Stooq — limit stated plainly)

- The Day 1/Day 2 full-series Stooq cross-check could not be completed: Stooq's public CSV endpoint was unfetchable from the working environment (connection drops/hangs). **This is not a login issue** — Stooq's daily CSV needs no login, and no Stooq login was attempted.
- The gap was closed with an independent source instead: **Finnhub daily candles** (a separate vendor from Yahoo, which supplied the backfill). Caveat: Finnhub is also the pipeline's live-quote vendor, so it is independent of the Yahoo daily-close source, not of every vendor the project touches.
- Result: **208/208 sessions per vehicle verified, zero flags over 0.05%** (207 sessions via Finnhub daily candles, 2025-12-31 to 2026-10-27, plus 2026-10-28 via a Finnhub current-price snippet, corroborated by YCharts). Max difference 0.0128% (IBIT) / 0.0090% (FBTC), sub-cent rounding. No change to `vehicle-daily.json` was needed or made.
- **Limit for reviewers:** a reviewer specifically requiring Stooq would still count that sub-item open; it would need a Stooq fetch from an environment where Stooq's CSV endpoint is reachable.

## Follow-up fix (after Day 4)

- **Problem found in Day 4 review:** `compare.js` `vehApply(m)` set the vehicle mode before fetching `vehicle-daily.json`, and on fetch failure the catch only logged a console warning — so a later redraw could show the "You are in IBIT/FBTC mode" note over spot lines.
- **Fix (commit `b126146f`):** in the catch, reset to SPOT, reset sessionStorage to SPOT, restore spot sleeve series, set a `VEHFAIL` flag, and redraw; `draw()` appends a visible **"Vehicle data unavailable — showing Spot BTC"** notice while the flag is set. A later successful ETF fetch clears it, and the contradictory ETF-mode note is suppressed since the mode is back to SPOT. `node --check` passes.
- **Harness re-run after the fix: ALL CHECKS PASSED, 100/100.** One harness assertion was updated and flagged, not hidden: the check formerly asserting "no prices.yml IBIT/FBTC change (deliberately outstanding)" now asserts the list includes IBIT/FBTC, reflecting the approved change.

## What was verified

- **Spot regression — passed to the cent, three consecutive passes** (Day 2, Day 4, and the post-fix re-run): Berkshire $97,640.65, Hodler $95,331.57, Hedge Fund $95,742.85, Saylor $104,013.87 at 28 Oct closes.
- **Full matrix — 2,496 NAVs:** 4 sleeves × 3 vehicles × every session, all finite, positive, no blanks, no crashes. Base invariant: every sleeve exactly $100,000 in every mode at 2025-12-31. Month-end: all 11 month-end dates × 12 combos finite, month-end NAV == close NAV at the same session.
- **Vehicle NAVs at 28 Oct:** IBIT — Berkshire $97,677.48, Hodler $95,391.75, Hedge Fund $95,789.65, Saylor $104,013.87; FBTC — $97,682.13, $95,400.02, $95,796.16, $104,013.87.
- **Weekends:** every Sat/Sun in range (172 checks) prices at the prior session close. **Holidays:** 7 NYSE holidays in range, each prices at the prior session close. **Missing-quote fallback:** price after series end = latest close (IBIT $46.14, FBTC $70.85), never blank, never the spot BTC price.
- **Dividend buys — 156 settled buys checked:** ETF-mode buys at the pay session's vehicle close, Hedge Fund 50/50 exact to the cent, Saylor has no BTC buy, dividend cash identical across modes for every event.
- **Compare replica == book.js:** 1,664 session checks, 0 differing. **Saylor Moon identical in every mode at every session** (0 differing of 208).
- **Browser visual test — PASSED** (on the `a300ae77` preview): toggle placement under the BTC LIVE pill, one-click switching with no second click/reload, mode label in all footnotes, popover row synced both ways with the chart staying Spot, fresh-tab Spot default, spot values sane on return to Spot. IBIT browser values: Berkshire $97,677, Hodler $95,392, Hedge $95,790, Saylor $104,014; FBTC: $97,682 / $95,400 / $95,796.
- **One-tick transient — downgraded, not user-visible** (Day 4 finding): s2's listener runs before s6's and renders once with the previous mode's stats, but s6 then renders with the new vehicle and synchronously dispatches the live refresh, and s2 re-applies and re-renders inside the same dispatch before the browser can paint. No code change required; browser painted-state confirmation is still listed under "Still open".

## Still open at review time (do not read these as done)

1. **Browser Compare failure-path check** — load Compare with `vehicle-daily.json` unavailable and confirm the visible "Vehicle data unavailable — showing Spot BTC" notice appears and the lines stay spot. This is browser work being checked separately by the parent; it is **not** claimed as passed here.
2. **Browser painted-state confirm** for the downgraded one-tick transient (above) — also being checked separately; not claimed as passed here.
3. **Live-quote verification** — until a scheduled prices run returns IBIT/FBTC quotes (`stocks_ok` 10/10 instead of 8/8), live ETF prices are unverified. Until then, ETF prices shown in the test-branch preview are latest closes from `vehicle-daily.json` (series ends 2026-10-28) and every ETF label says so.
4. **Sunil's final deploy approval** — required after this review, and only then. **Deploy is NOT authorised by this package.** When deploy is approved, it covers the frontend toggle going to main (the `prices.yml` change is already on main as `75cfaf44` and does not need to be re-landed), followed by live verification of Pulse, tracker, holdings, Compare, and the popover in all three modes.

## Reviewer checklist — what Grok Bot + Chief of Staff should check on the test branch

- [ ] **Spot regression:** on the test branch, Spot mode still reproduces the Day 1 baseline to the cent ($97,640.65 / $95,331.57 / $95,742.85 / $104,013.87 at 28 Oct closes). Any spot difference is a blocker.
- [ ] **Base invariant:** every sleeve starts at exactly $100,000 in Spot, IBIT, and FBTC modes at 2025-12-31 (rebasing, not price-swapping).
- [ ] **One-click switching:** on the test-branch preview, switching Spot → IBIT → FBTC → Spot re-renders Pulse, tracker, holdings, VS, and Compare together, with no reload and no blank values; the persistent mode label follows the mode.
- [ ] **Holdings relabel:** in ETF mode, the BTC row reads "BTC (IBIT)" / "BTC (FBTC)" with vehicle units × vehicle price, and the price label says latest close (Oct 28) until live quotes verify.
- [ ] **Benchmark and popover:** the Compare dashed benchmark line stays Spot in every mode; the popover chart stays Spot in every mode, with its note intact.
- [ ] **Static copy:** "$40k BTC" / "40% BTC" / "Spot BTC is the hurdle" wording is unchanged in ETF mode, while the portfolio values underneath are IBIT/FBTC-based.
- [ ] **Failure path:** with `vehicle-daily.json` unavailable, Compare falls back to Spot with the visible "Vehicle data unavailable — showing Spot BTC" notice (browser check; see "Still open" item 1).
- [ ] **Weekends/holidays:** ETF values on a weekend or holiday session equal the prior session close (harness covers this; spot-check one weekend in the preview if convenient).
- [ ] **Dividend example:** Berkshire's first settled dividend event (pay session 2026-02-02, cash $185.57 in every mode) buys the ETF at the pay session's ETF close in ETF mode (IBIT 4.1965 units at $44.22; FBTC 2.7334 units at $67.89) and spot BTC at $78,688.77 in Spot mode.
- [ ] **Cross-check limit:** confirm the Finnhub-instead-of-Stooq limit (above) is acceptable, or flag Stooq as still required before deploy.
- [ ] **Deploy gate:** confirm this package authorises **review only**. The final proposal/decision back to Sunil is a Grok Bot + Chief of Staff product, and deploy needs Sunil's separate final approval.

---
*Test branch only. No main change, no deploy, no message sent by this package. Prepared Thu 29 Oct 2026 for Grok Bot + Chief of Staff review.*
