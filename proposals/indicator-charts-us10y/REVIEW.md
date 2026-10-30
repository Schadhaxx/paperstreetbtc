# REVIEW — 10-Year YTD weekly candle chart (test branch, NOT live)

## FILE / FOLDER LIST — find everything here
- **Test branch:** `pepper-indicator-charts-us10y` (from main `75b96488`, WTI live)
- **New 10-year data file:** `assets/data/us10y-weekly.json`
- **Shared chart module (reused, NOT copied):** `assets/js/screener-indicator-chart.js` — US10Y added as a third config entry alongside GOLD and WTI
- **Screener page:** `screener.html` — CSS tile selectors + box note only (US10Y tile made clickable/hoverable; note now says "Tap the gold, WTI or 10-year tile")
- **Review note itself:** `proposals/indicator-charts-us10y/REVIEW.md` (this file)
- **NOT changed on this branch:** `assets/data/gold-weekly.json`, `assets/data/wti-weekly.json`, `index.html`, `assets/js/btcchart.js`, tracker/compare files, pipeline files, `proposals/screener-maple-leaf/INFO-PACKAGE.md`, and the screener pack / tile "+" note texts (see source-naming note below)
- **Status:** TEST BRANCH ONLY. NOT deployed to main, NOT live. HOLD here for Grok Bot's checks, as Sunil instructed 30 Oct 2026 ~5:11 p.m. ET.

## What was built
Tap the US10Y Market Indicator tile itself (not its "+") opens "10-Year — YTD weekly candles": YTD weekly candles only, UTC Monday–Sunday weeks, month-only x-axis (Jan–Oct), dashed cyan current-yield line labelled at the LEFT by the y-axis, top/bottom blurbs hidden behind "+" popups inside the modal, candle-tap pill with week + O/H/L/C in %, iPhone-first. The tile's "+" still opens only its note. BTC chart/popover untouched. Clock-split status lines untouched. No browser-fetch fallback (dropped for gold/WTI already): shipped JSON only, plain error + Retry if missing.

## The six-condition equivalents (Grok Bot's conditions, applied to US10Y)
1. **One at a time, weekly only, manual refresh, data date shown:** only US10Y built; VIX is NOT built on this branch. Weekly candles only. No refresh job or pipeline change. Modal and file say "data as of 30 Oct 2026".
2. **Latest week is a FINAL close — NOT in progress (this is different from WTI/gold, on purpose):** the ^TNX pull was retrieved Fri 30 Oct 2026 ~5:11 p.m. ET, after the regular period ended, and the JSON gives a full-day close for 30 Oct: 4.929%, vs 29 Oct 4.989% (−0.060 pp). The current line reads "Current 4.929%" with NO "(in progress)" label, and `lastInProgress` is null for US10Y. Do NOT copy WTI's in-progress label onto this chart. (Gold's last candle, by contrast, was a Friday intraday pull — that separate correction is still outstanding on main and is not changed here.)
3. **Source named correctly in the modal:** "Yahoo ^TNX (CBOE Interest Rate 10 Year T Note)" — NOT "Treasury par yield". This is in the modal sub-blurb, the footer source line, and the JSON source field.
   - **Open question for a later step (not decided here):** the screener tile's "+" note still says "U.S. Treasury daily par yield, %. Day change in percentage points." That note text was deliberately NOT changed on this branch (pack text untouched, per the build instructions). Grok Bot + Sunil to decide whether the "+" note should also be corrected to ^TNX, or left as-is.
4. **No continuous-series roll note needed:** that note is WTI-specific (front-month roll gaps). US10Y has no equivalent note.
5. **Data checks (see below):** 44 weeks / 209 trading days, script-checked; first week partial labelled; second-source spot checks done for 30 Oct and 29 Oct.
6. **One shared module, fallback dropped, "+" behaviour, rollback:** US10Y is a config entry in `screener-indicator-chart.js` (fmtYield, ppChange, footNote); no `screener-us10y.js` copy exists. No Yahoo URL in the module. Tile opens chart, "+" opens note only. **Rollback:** delete `assets/data/us10y-weekly.json`, remove the US10Y config entry from the shared module, revert the `screener.html` CSS/box-note lines, and restore from main `75b96488`.

## Yield display rules (no dollars, ever, on this modal)
- Yields are in %, shown to **3 decimals** everywhere in the modal/pill (gridlines, current line, pill O/H/L/C), so displayed values match the shipped JSON exactly.
- The screener tile rounds to **2 decimals** (4.929% → 4.93%) — that is a display rounding difference, not a data difference.
- Week change in the pill shows the pp move first, then the relative % (e.g. last week: −0.074 pp, −1.48%). Day change on the tile row stays in pp plus relative %, as before.
- Grep/harness verified: no "$" anywhere in US10Y drawn text, sub-blurb, footer note, or config format output.

## Data
- Source: Yahoo ^TNX, yields in %, 3 decimals as retrieved.
- 44 weekly candles, 209 trading days, 2 Jan – 30 Oct 2026. First week partial (1 trading day, 2 Jan 2026, week starting Mon 29 Dec 2025) — labelled, not dropped.
- Last week (26 Oct 2026): open 5.003%, high 5.049%, low 4.908%, close 4.929% (final close, see condition 2).
- Full weekly list is in `assets/data/us10y-weekly.json` (monday/sunday/label/days/open/high/low/close per week).

## Data checks
- **Counts:** 44 weeks, 209 trading days, script-checked; every week has low ≤ min(open, close) and high ≥ max(open, close); no null/NaN values.
- **Reconciliation vs the screener tile:** the tile's live yield in recent checks sat in the ~4.94–4.99% range, vs this snapshot's final 4.929%. That difference is snapshot (30 Oct final close) vs live tile at check time, plus the tile's 2-decimal rounding (4.929% → 4.93%) — it is not hidden and is not a data error.
- **Second-source spot checks (read via web search, 30 Oct 2026):**
  - 30 Oct close **4.929%** — matches exactly: TradingView / dpa-AFX, "Ten-Year Treasury Yield Slumps To Lowest Level In Well Over A Month" (30 Oct 2026): yield "slumped 6.0 basis points to 4.929 percent". A second report (Morningstar / Dow Jones, Tradeweb 3 p.m. ET values) gives 4.928% for the month — a 0.001 pp source-timing/rounding difference, noted, not hidden.
  - 29 Oct close **4.989%** — matches the task's stated 29 Oct close and a published daily-close list (portfolio-terminal, 10-year closes: 29 Oct 4.989%, down 0.056 pts from 28 Oct 5.045%). Treasury's daily par yield for 29 Oct is published as 4.98% (rounded) — close to, but not the same series as, ^TNX, which is exactly why the modal names ^TNX and not par yield.
  - FRED's DGS10 table itself was NOT directly read in this build environment; the checks above are independent published Treasury-yield reports, not a FRED table pull. Grok Bot may re-check against FRED DGS10 / Fed H.15 if he wishes.
- **Stale-state fix with THREE symbols (harness, see below):** gold → WTI → US10Y switching, slow-load race, and failed-load clearing all pass on the shared module (a17b367 fix, unchanged in logic — only a config entry was added).

## Verification (headless harness, all checks passed)
- `node --check` passes on the shared module.
- Harness (stub DOM + shipped files only, no browser fetch): US10Y draws 44 candles, current line "Current 4.929%" at the left, month labels Jan–Oct, no "$" in drawn text; title, sub-blurb (^TNX, final close, not in progress), footer (^TNX, not par yield as source), 3-decimal format, and lastInProgress null all verified.
- Gold still draws 44 candles with "Current $3,901.20"; WTI still draws 44 with "Current $104.24 (in progress)" — unchanged.
- Three-symbol switch (gold → WTI → US10Y) ends on US10Y only; slow gold load resolving after a switch to US10Y is ignored; failed US10Y load after gold clears the canvas, hides the pill, and shows the plain error + Retry only.
- Two harness checks first failed only because the harness itself searched for the substrings "in progress" / "par yield" inside the phrases "not in progress" / "not Treasury par yield" — corrected in the harness, no shipped code changed, all checks then passed.

## NOT verified / NOT done
- Painted-browser / real phone tap: NOT checked by this build — that is Grok Bot's test-branch review, as with WTI.
- NOT deployed to main, NOT live, no Grok Bot contact — Sunil passes this to Grok Bot himself and we HOLD here.
- VIX: not built. Next step, when Sunil says so, is VIX on its own test branch in the same pattern.
