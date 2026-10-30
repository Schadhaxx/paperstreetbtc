# WTI indicator chart — test-branch review note for Grok Bot + Chief of Staff

## FILE / FOLDER LIST — FIND EVERYTHING HERE

- **Test branch:** `pepper-indicator-charts-wti` (from main `7a0ab463`, NOT main, NOT live)
- **New WTI weekly data file:** `assets/data/wti-weekly.json`
- **New shared chart module:** `assets/js/screener-indicator-chart.js`
- **Gold file migration (old vs new path):**
  - OLD (deleted on this branch): `assets/js/screener-gold.js`
  - NEW (replaces it, gold + WTI both run through it): `assets/js/screener-indicator-chart.js`
  - Gold data file UNCHANGED on this branch: `assets/data/gold-weekly.json`
- **Screener page:** `screener.html`
  - Script tags changed: REMOVED `<script src="assets/js/screener-gold.js"></script>`, ADDED `<script src="assets/js/screener-indicator-chart.js"></script>`
  - Modal renamed in place: `gold-modal` / `gold-dialog` / `gold-*` ids and classes → `ind-modal` / `ind-dialog` / `ind-*` (same modal, now generic)
  - Tile CSS: `.tile[data-symbol="WTI"]` added alongside GOLD (cursor pointer + hover); box note now says "Tap the gold or WTI tile for its YTD weekly candle chart"
  - NO other script tags changed; `screener.js`, `screener-chart.js`, `btcchart.js` untouched
- **This review note itself:** `proposals/indicator-charts-wti/REVIEW.md`
- **Nothing else changed:** no `index.html`, no `btcchart.js`, no tracker/compare file, no pipeline file, no key, no other site page

## FIX AFTER GROK BOT REVIEW — STALE STATE ON SYMBOL SWITCH (this commit, test branch only)

- **Grok Bot's finding (review forwarded by Sunil ~4:29 p.m. ET, 30 Oct 2026):** one blocking bug, no other blockers. Switching between gold and WTI could leave the other chart's data on screen: (a) tap a gold candle, close it, open WTI — the gold price box stayed under the WTI title (and vice versa); (b) if gold was still loading on a slow connection when WTI opened, WTI showed gold candles labelled "Current $3,901.20 (in progress)"; (c) if WTI's data failed to load after gold, the gold chart stayed drawn under the WTI title. WTI alone and gold alone both worked. Grok Bot confirmed the rest: only five files changed, gold data unchanged, all six conditions met, WTI data internally consistent (44 weeks, no gaps, no bad values), no sideways scroll at phone width, no JavaScript errors (headless browser, not a real phone tap). He will re-check only the changes after this fix.
- **The fix, in the one shared file only (`assets/js/screener-indicator-chart.js`):**
  - New `resetModalVisuals()` — called on every modal open — clears the selected candle (`selected = -1`), hides the candle pill (`ind-pill`), hides the info popup (`ind-info-pill`), clears the source "+" state (footer text emptied, `ind-info-foot` hidden), and clears the canvas (context cleared, `_plot` deleted). So an old pill, popup, source "+" or chart can never survive a symbol switch, even while the new symbol is still loading.
  - `openModal()` now detects a symbol switch: on a switch it invalidates any in-flight load, empties `weeks`, clears `loadedSymbol`, and starts a fresh load. A same-symbol reopen keeps its loaded weeks and redraws, but still resets the selection/pill first.
  - Token-guarded async load: `loadData()` increments `state.loadToken` and captures it; its success and failure handlers return immediately if the token no longer matches or the current symbol differs. A stale response therefore draws nothing, sets no current line, and leaves no old chart on screen.
  - Failed load for the new symbol now clears the previous chart: the failure handler empties `weeks`, clears `loadedSymbol`, calls `resetModalVisuals()`, and only then shows the plain error + Retry — never the old symbol's chart under the new title.
  - `draw()` also refuses to draw weeks whose `loadedSymbol` differs from the modal's current symbol (belt-and-braces against a resize redraw after a switch).
  - No other behaviour changed: same-symbol loads, cached redraws, "+" note behaviour, and the shipped-file-only rule (no browser-fetch fallback) are untouched.
- **Date-format fix (same commit, minor, non-blocking):** the WTI source note showed `2026-10-30T15:42 ET` (the `asOf` field in `assets/data/wti-weekly.json`, which the modal footer prints verbatim). Changed to `30 Oct 2026, 3:42 p.m. ET`, the format used everywhere else. Grep confirmed no other ISO-style date/time (`T HH:MM`) remains in the WTI JSON; the week `monday`/`sunday` fields are plain calendar dates, not datetimes, and were left alone.
- **Verification for this fix (headless harness, all passing):** (1) gold candle selected → close → open WTI: WTI title, WTI candles only (44), gold pill hidden, no gold current label; (2) gold load started, WTI opened before it resolved, stale gold resolved late: WTI drawn only, no gold candles, no "Current $3,901.20", title stays WTI; (3) gold drawn, WTI load fails: canvas cleared (`_plot` deleted), pill hidden, plain error only, no gold chart under the WTI title. Reverse direction also checked (WTI candle → close → gold: gold title, 44 candles, gold label only, pill hidden). Regression re-run: gold alone 44 candles with "Current $3,901.20", WTI alone 44 candles with "Current $104.24 (in progress)". `node --check` passes. NOT verified: painted-browser / real phone tap — that remains Grok Bot's check, as before.
- **Files in this fix commit:** `assets/js/screener-indicator-chart.js` (the fix), `assets/data/wti-weekly.json` (one-line `asOf` format change only — no candle value changed), `proposals/indicator-charts-wti/REVIEW.md` (this section). `screener.html`, `assets/data/gold-weekly.json`, and the gold data are NOT touched by this commit.

## WHAT THIS IS

WTI first, one indicator at a time, exactly as Grok Bot conditioned (30 Oct 2026 reply, forwarded by Sunil ~3:41 p.m. ET). 10-Year and VIX are NOT built here — no US10Y/VIX chart, data file, or config entry on this branch. Weekly candles only. Manual refresh only when Sunil asks — there is no automatic refresh in this build. The data date is always shown in the modal (top "+" blurb and bottom source "+" blurb).

## THE SIX GROK BOT CONDITIONS — HOW EACH IS MET

1. **One at a time, WTI first; weekly only; manual refresh; data date shown.**
   Only WTI was added. Only weekly candles (YTD, UTC Monday–Sunday weeks). No refresh job, no pipeline change, no auto-update. The modal shows "data as of 30 Oct 2026, 3:42 p.m. ET" in both blurbs, and the file note in `assets/data/wti-weekly.json` says "Manual refresh only, when Sunil asks."
2. **Latest week labelled in progress.**
   The last WTI candle (week of 26 Oct 2026) was built from an intraday/in-progress daily bar retrieved Fri 30 Oct 2026 ~3:42 p.m. ET, NOT a final close. The modal's current line reads "Current $104.24 (in progress)", the candle-tap pill for that week appends "Latest week in progress, as of 30 Oct 2026, 3:42 p.m. ET — close is not a final daily close", the top blurb says "The latest week is in progress, not a final close", and the file note says the same. The word "daily close" is never used for this week's close anywhere in the WTI code, modal, or file note.
3. **Source naming (and the 10-Year correction, noted for later).**
   WTI modal source is stated explicitly as Yahoo CL=F (NYMEX front-month futures, continuous series) in the top blurb, the bottom source blurb, and the JSON `source` field. The 10-Year source correction (Yahoo `^TNX`, not Treasury par yield) is NOT implemented here because 10-Year is not built on this branch — it is recorded as a required change for the 10-Year build, not silently assumed done.
4. **Continuous front-month note.**
   The WTI top blurb, bottom source blurb, and JSON note all state: "WTI is a continuous front-month series — there are gaps where contracts roll over."
5. **Data checks before shipping (see DATA CHECKS below).**
   Counts verified (44 weeks / 209 trading days), last week reconciled against the screener's live WTI tile price with the difference explained (not hidden), and two point spot-checks against second sources that could actually be read. A full second-source OHLC re-verification was NOT possible in this environment and is stated plainly below — it is not claimed.
6. **One shared chart module, no three copies; browser-fetch fallback dropped; "+" behaviour; rollback.**
   `screener-indicator-chart.js` is the single module. Gold was migrated onto it (old file deleted) and WTI was added as a second CONFIG entry in the same file — no `screener-wti.js` copy exists. The Yahoo browser-fetch fallback is GONE from the module (the only `fetch` call is `fetch(cfg.dataUrl)` for the shipped file); if the shipped file is missing, the modal shows a plain error with Retry and never invents candles. "+" behaviour is unchanged: tapping a tile (not its "+") opens the chart; tapping "+" opens only the note pill. WTI is $/barrel, so no "$" issue arises here (the yield "$" rule applies to the future 10-Year build). Rollback = delete `assets/data/wti-weekly.json`, `assets/js/screener-indicator-chart.js`, and `proposals/indicator-charts-wti/REVIEW.md`, restore `assets/js/screener-gold.js` and the gold modal in `screener.html` from main `7a0ab463`, and remove the indicator-chart script tag — i.e. revert this branch's commit. The change is isolated to the hidden screener (leaf-only, not advertised); no other page is affected.

## DATA CHECKS

- **Counts:** WTI file = 44 weeks, trading days sum to 209 (verified by script, same 44/209 shape as gold). First week is partial (1 trading day, 2 Jan 2026, week starting Mon 29 Dec 2025) — labelled partial in the modal and the pill, not dropped. Last week: 26 Oct–1 Nov 2026, open $102.61, high $104.99, low $99.44, close $104.24 (in progress), 5 trading days.
- **Reconciliation vs the screener's live WTI tile:** the tile read ~$104.74 at the 2 p.m. 30 Oct price check and ~$104.76 at the 1:26 p.m. live check, while the weekly close is $104.24. This is NOT hidden and NOT an error in either number: the tile is a live pipeline quote at check time, while $104.24 is the intraday snapshot at ~3:42 p.m. ET on a Friday afternoon when WTI was moving (second sources below show WTI around $104.20–$104.35 that day). The modal labels the snapshot's time so the two numbers are never confused.
- **Spot-check 1 (exact close match):** week of 2 Mar 2026, supplied close $90.90 — matches Meyka's 7 Mar 2026 report that WTI "settled at $90.90 after a 35% weekly jump". Exact match, $0.00 difference.
- **Spot-check 2 (exact high match, close differs by timing/contract):** week of 26 Oct 2026, supplied high $104.99 — matches SeasonalMarketNews' CL quote for 30 Oct 2026 (open $102.80, high $104.99, low $102.43). Their intraday/close readings that day ($104.35, and $104.20 in other 30 Oct reports) are $0.11–$0.15 above the $104.24 snapshot close, consistent with a different snapshot time and a December-contract quote vs the continuous series — direction and range agree, the close is not claimed as an exact match.
- **Supporting check (not counted as a spot-check):** FXLeaders, 31 Mar 2026, put WTI at $102.24–$103.00; the supplied week of 30 Mar 2026 opens at $102.60, inside that range.
- **What could NOT be checked:** no full second-source weekly OHLC dataset for CL=F was readable from this environment (EIA spot prices are a different series — spot, not front-month futures — so they were not used as an OHLC check). The two point checks above are the full extent of the second-source verification; Grok Bot's review should not read them as a full re-verification.

## KNOWN CORRECTION — GOLD'S FILE NOTE (recorded, NOT changed on this branch)

Gold's shipped file note (`assets/data/gold-weekly.json`, live on main) calls the final week's close a 30 Oct daily close ($3,901.20). That pull was likewise a Friday intraday pull, so the same in-progress labelling Grok Bot required for WTI should be applied to gold's file note and modal on main — as a separate, Sunil-approved correction, not silently fixed inside this WTI test branch. This branch does NOT change `assets/data/gold-weekly.json` or the live gold chart; gold's behaviour here is identical to main except that it now runs through the shared module (same data, same values, same "+" behaviour — verified by the harness below).

## VERIFICATION (headless, this branch)

- `node --check` passes on `assets/js/screener-indicator-chart.js` and `assets/js/screener.js`.
- Stub-DOM harness loading the shared module with the shipped files only (no browser fetch): WTI draws 45 canvas rects (44 candle bodies + current-label background), month labels Jan–Oct all present, current label "Current $104.24 (in progress)", title "WTI — YTD weekly candles"; GOLD draws the same 45 rects, months Jan–Oct, current label "Current $3,901.20", title "Gold — YTD weekly candles". Gold values in the harness match main's gold file exactly (first week $4,340.00 / $4,414.80 / $4,319.70 / $4,329.60; last week $4,012.20 / $4,097.20 / $3,900.20 / $3,901.20).
- Static checks: no `screener-gold.js` reference remains in `screener.html`; no Yahoo URL in the shared module (only the shipped-file fetch); no US10Y/VIX chart, config, or data file on this branch; `git status` shows only screener files (see diff summary in the delivery report).
- NOT verified headless (needs Grok Bot's painted-browser review on this test branch, as Grok Bot proposed): actual tap behaviour at 390px, the in-progress pill wording on a real phone, and the modal's look with both blurbs hidden. No live-browser check was done by this build, and nothing here is live.

## DIFF SUMMARY

- `assets/data/wti-weekly.json` — NEW, 44 weekly candles
- `assets/js/screener-indicator-chart.js` — NEW, the single shared module (gold + WTI configs)
- `assets/js/screener-gold.js` — DELETED (replaced by the shared module)
- `screener.html` — modal renamed gold→ind, script tag swapped, WTI tile made clickable, box note updated
- `proposals/indicator-charts-wti/REVIEW.md` — NEW, this note
