# REVIEW — VIX YTD weekly candle chart (test branch, NOT live)

## FILE / FOLDER LIST — find everything here
- **Test branch:** `pepper-indicator-charts-vix` (from main `aa15378`, US10Y live)
- **New VIX data file:** `assets/data/vix-weekly.json`
- **Shared chart module (reused, NOT copied):** `assets/js/screener-indicator-chart.js` — VIX added as a fourth config entry alongside GOLD, WTI and US10Y
- **Screener page:** `screener.html` — CSS tile selectors + box note only (VIX tile made clickable/hoverable; note now says "Tap the gold, WTI, 10-year or VIX tile") and the shared-module script tag buster `?v=us10y1` → `?v=vix1`
- **Review note itself:** `proposals/indicator-charts-vix/REVIEW.md` (this file)
- **NOT changed on this branch:** `assets/data/gold-weekly.json`, `assets/data/wti-weekly.json`, `assets/data/us10y-weekly.json`, `assets/data/screener-pack.json` (the VIX "+" note already reads "Index level in points, not a price. No VIX ETF substituted." — it already matches the chart, so no pack change was needed), `index.html`, `assets/js/btcchart.js`, tracker/compare files, pipeline files, `proposals/screener-maple-leaf/INFO-PACKAGE.md`
- **Status:** TEST BRANCH ONLY. NOT deployed to main, NOT live. HOLD here for Grok Bot's checks, as Sunil instructed 30 Oct 2026 ~7:08 p.m. ET.

## What was built
Tap the VIX Market Indicator tile itself (not its "+") opens "VIX — YTD weekly candles": YTD weekly candles only, UTC Monday–Sunday weeks, month-only x-axis (Jan–Oct), dashed cyan current-level line labelled at the LEFT by the y-axis, top/bottom blurbs hidden behind "+" popups inside the modal, candle-tap pill with week + O/H/L/C in points, iPhone-first. The tile's "+" still opens only its note. BTC chart/popover untouched. Clock-split status lines untouched. No browser-fetch fallback: shipped JSON only, plain error + Retry if missing.

## VIX rules (no dollars, no "price", no ETF)
- VIX is an index level in **points**, shown to **2 decimals** with a "pts" unit everywhere in the modal/pill (gridlines, current line, pill O/H/L/C), so a bare number can never be misread as a dollar value.
- The modal text never calls VIX a price and never uses "$": verified by grep over the VIX config strings and format output (the only remaining "price" mentions in the module file are pre-existing generic comments about dollar-price symbols, not VIX modal text).
- **No VIX ETF is substituted** — stated in the sub-blurb, the footer note, the JSON note, and the pre-existing "+" note.
- Week change in the pill is a relative % (like gold/WTI), NOT pp-first: pp-first is a yields-only rule (US10Y), and does not apply to an index level.

## Final close, NOT in progress (like US10Y, unlike WTI)
The ^VIX pull was retrieved Fri 30 Oct 2026 ~7:20 p.m. ET, after the regular session ended, with a full-day close for 30 Oct of **19.42 points**. The current line reads "Current 19.42 pts" with NO "(in progress)" label, and `lastInProgress` is null for VIX. Do NOT copy WTI's in-progress label onto this chart. (Gold's last candle, by contrast, was a Friday intraday pull — that separate correction is still outstanding on main and is not changed here.)

## Day-count investigation — 215 days, RESOLVED (not a data error)
Gold, WTI and US10Y each have 209 trading days YTD. VIX has **215 trading days: 211 in Yahoo's data plus 4 days Cboe calculated VIX on days Yahoo has no bar for** (see Cboe rebuild below). The extra days are real closes in the source series, not null or duplicate bars:
- **Week of 26 May 2026 counts 5 for VIX, 4 for the others.** The extra day is Mon 25 May 2026: Cboe VIXCLS (via FRED, reproduced in a second source) lists a VIX close of **16.59** that day, then 17.01 (26 May), 16.29 (27 May), 15.74 (28 May), 15.32 (29 May). The supplied weekly candle closes at **15.32**, matching the Friday close in both sources, and its open/high/low (16.81 / 17.23 / 15.22) bracket those daily closes plausibly. The stock, futures and yield series are closed that Monday, so they count 4.
- **Week of 7 Sep 2026 counts 5 for VIX, 4 for the others.** The extra day is Mon 7 Sep 2026: Cboe VIXCLS lists **15.30** that day, then 15.72 (8 Sep), 16.46 (9 Sep), 17.84 (10 Sep), 15.84 (11 Sep). The supplied weekly candle closes at **15.84**, matching the Friday close in both sources.
- The four holiday weeks below were rebuilt from Cboe's own daily history (VIX_History.csv, downloaded 30 Oct 2026) and now also count 5 for VIX, taking the total from 211 to 215. Only the Good Friday week (30 Mar) still counts 4 for VIX, matching the other indicators.
- Conclusion: ship **215 days**. The JSON note records this, so a reviewer comparing day counts does not mistake it for a bug.

### Cboe rebuild, 30 Oct 2026 (on top of the FRED fix)
Yahoo ^VIX has no bar for 19 Jan, 16 Feb, 19 Jun or 3 Jul 2026, but Cboe calculated VIX on all four days. These four weeks were rebuilt from Cboe's daily history, days set to 5 each, highs/lows recomputed from the Cboe daily bars (all four listed values verified against the CSV):
- Week of 19 Jan: was O 19.94 / H 20.99 / L 15.27 / C 16.09 / 4 days → now **O 18.63 / H 20.99 / L 15.27 / C 16.09 / 5 days** (Cboe Mon 19 Jan: O 18.63, H 19.59, L 18.28, C 18.84).
- Week of 16 Feb: was O 21.74 / H 22.96 / L 18.48 / C 19.09 / 4 days → now **O 20.73 / H 22.96 / L 18.48 / C 19.09 / 5 days** (Cboe Mon 16 Feb: O 20.73, H 21.62, L 20.37, C 21.20).
- Week of 15 Jun: was O 16.78 / H 18.84 / L 15.77 / C 16.40 / 4 days → now **O 16.78 / H 18.84 / L 15.77 / C 16.78 / 5 days** (Cboe Fri 19 Jun: O 17.04, H 17.27, L 16.72, C 16.78).
- Week of 29 Jun: was O 18.60 / H 19.45 / L 15.79 / C 16.15 / 4 days → now **O 18.60 / H 19.45 / L 15.75 / C 15.81 / 5 days** (Cboe Fri 3 Jul: O 15.78, H 16.01, L 15.75, C 15.81).
- Full Cboe comparison of all 44 weeks: every week matches Cboe's daily-history aggregation within 0.05 on every field, EXCEPT two explained cases, neither changed in this commit: (a) the first partial week (29 Dec 2025) — shipped YTD scope counts only 2 Jan 2026 (1 day), while Cboe's week also contains 29–31 Dec 2025, so its Cboe open (14.69) and low (13.99) differ from the shipped 14.85 / 14.46 by design; (b) the final week (26 Oct) — Cboe's file ends 29 Oct, so its aggregation (H 19.84, C 17.20) omits the 30 Oct Yahoo bar (H 23.93, C 19.42), which rests on Yahoo alone.

## Data
- Source: Yahoo ^VIX (CBOE Volatility Index), index points, 2 decimals as retrieved.
- **44 weekly candles, 215 trading days**, 2 Jan – 30 Oct 2026. First week partial (1 trading day, 2 Jan 2026, week starting Mon 29 Dec 2025) — labelled, not dropped. Every week satisfies low ≤ min(open, close) and high ≥ max(open, close); no null/NaN values (script-checked).
- Last week (26 Oct 2026): open 19.66, high 23.93, low 16.21, close **19.42** (final close, see above).
- Reconciliation vs the tile: the 30 Oct final close of 19.42 points sits above tile levels seen earlier on 30 Oct (e.g. 18.41 at the 7:50 a.m. ET live check) — a dated snapshot final close vs an intraday tile reading at a different time, not a data error. The modal is labelled a dated snapshot, not a live quote, as with gold/WTI/US10Y.

## Second-source spot checks (read, not invented)
- Week of 26 May 2026 close **15.32** matches Cboe VIXCLS daily closes (FRED series, via a second published table) for that week, including the 25 May close of 16.59.
- Week of 7 Sep 2026 close **15.84** matches the same Cboe VIXCLS table for that week, including the 7 Sep close of 15.30.
- Week of 5 Oct 2026 close **14.84** matches the same table (5 Oct 15.52, 6 Oct 15.01, 7 Oct 15.08, 8 Oct 15.41, 9 Oct 14.84).
- Week of 2 Mar 2026 close **29.49** matches the same table (2 Mar 21.44, 3 Mar 23.57, 4 Mar 21.15, 5 Mar 23.75, 6 Mar 29.49).
- The FRED table itself runs to 29 Oct 2026, so only the final week (close 30 Oct) rests on the Yahoo ^VIX pull alone — stated plainly, not claimed otherwise.

## Conditions (Grok Bot's conditions, applied to VIX)
1. **One at a time, weekly only, manual refresh, data date shown:** only VIX built; no other indicator added. Weekly candles only. No refresh job or pipeline change. Modal and file say "data as of 30 Oct 2026".
2. **Latest week is a FINAL close — NOT in progress:** see above. `lastInProgress` is null for VIX.
3. **Source named correctly in the modal:** "Yahoo ^VIX (CBOE Volatility Index)" — in the modal sub-blurb, the footer source line, and the JSON source field. The "+" note already matches (points, no ETF), so no pack change.
4. **No continuous-series roll note needed:** that note is WTI-specific (front-month roll gaps). VIX has no equivalent note; its day-count note above covers the calendar difference instead.
5. **Data checks (see above):** 44 weeks / 215 days (resolved, not an error), first week partial labelled, full Cboe comparison done for all 44 weeks (see Cboe rebuild above).
6. **One shared module, fallback dropped, "+" behaviour, rollback:** VIX is a config entry in `screener-indicator-chart.js` (fmtPoints, footNote); no `screener-vix.js` copy exists. No Yahoo URL in the module. Tile opens chart, "+" opens note only. **Rollback:** delete `assets/data/vix-weekly.json`, remove the VIX config entry from the shared module, revert the `screener.html` CSS/box-note/script-buster lines, and restore from main `aa15378`.

## Verification (headless harness — see below)
- `node --check` passes on the shared module.
- VIX draws 44 candles, current line "Current 19.42 pts" at the left, month labels Jan–Oct, no "$" and no "price" wording in VIX modal text.
- Gold still draws 44 candles ("Current $3,901.20"); WTI still draws 44 ("Current $104.24 (in progress)"); US10Y still draws 44 ("Current 4.929%") — unchanged.
- Stale-state fix holds with FOUR symbols: gold → WTI → US10Y → VIX ends on VIX only; a slow gold load resolving after a switch to VIX is ignored; a failed VIX load after gold clears the canvas and shows plain error + Retry only.
- **NOT verified:** painted-browser / real phone tap — that is Grok Bot's test-branch review, as with WTI/US10Y.
