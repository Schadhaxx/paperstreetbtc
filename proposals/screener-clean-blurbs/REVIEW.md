# Screener clean blurbs — review note (TEST BRANCH, NOT LIVE)

## File / folder list — for Grok Bot
- Test branch: `pepper-screener-clean-blurbs` (from current main `65dc45a`)
- Changed files (4): `screener.html`, `assets/js/screener.js` (pack buster only), `assets/js/screener-indicator-chart.js`, `assets/data/screener-pack.json` (notes + version only)
- This note: `proposals/screener-clean-blurbs/REVIEW.md`
- NOT changed: all weekly data files, all prices/numbers, BTC pill behaviour/chart, vehicle toggle, clock split, status lines, INFO-PACKAGE file

## What this is
Text-only cleanup of the visitor-facing screener blurbs, following Sunil's 31 Oct 2026 review: most blurbs were builders' audit detail, not viewer information. No numbers, no data, no behaviour changed. The audit detail stays in the internal INFO-PACKAGE, where reviewers need it — it was never deleted from there.

## Before / after — every text removed or shortened

| Location | Before | After |
|---|---|---|
| "About this page" (screener.html) | "Seven stocks, four market indicators, one honest status line each. Tap a card's + for its note. Trend bars show only the size of today's move — they are not price history." | "Seven stocks, four market indicators. Trend bars show only the size of today's move — they are not price history." |
| "How the boxes work" (screener.html) | Full paragraph: box order, US stock hours, futures vs stock hours split, indicators line naming live vs dated rows | "Each box has one status line below it, saying which rows are live and which are on a dated close." |
| "About the indicators" (screener.html) | Full paragraph: units, search/filter scope, futures hours Sun 6 p.m.–Fri 5 p.m. except 5–6 p.m. break, stock hours, tile/+ instructions | "WTI $/barrel · Gold (COMEX futures) $/troy oz · 10-Year % (day change in percentage points) · VIX points, not a price. Tap a tile for its YTD weekly candle chart." |
| "About YTD" (screener.html) | Full paragraph: Dec 31 base, SPCX first close $160.95, "true Dec 31 YTD does not exist" | "YTD is vs the 31 Dec 2025 close, except SPCX (since listing 12 Jun 2026)." |
| Bottom disclaimer (screener.html) | Legal line + status-line explanation + "no per-row status column" + "rows with no pipeline quote show their 28 Oct 2026 close" + SpaceX IPO line + gold/WTI/VIX guards | "Not financial advice. Not an offer to buy or sell any security. Gold here is COMEX futures (GC=F), not spot; WTI is the NYMEX front-month futures quote; VIX is the Cboe index level in points, not a traded price. Back to the main page." |
| Row "+" pills — MU, WTI, GOLD, US10Y, VIX (pack notes) | MU day-move news note; WTI front-month quote; GOLD COMEX + stale "Pack close only until the pipeline writes GOLD"; US10Y ^TNX note; VIX points/no-ETF note | Deleted — no "+" button renders for these rows (their names/units already carry the definition) |
| Row "+" pill — SPCX (pack note) | "Public since 12 June 2026 IPO at $135; first trading close $160.95. YTD column shows return since that first close, NOT from 31 Dec 2025." | Kept, shortened to one line: "Return since first trading close 12 Jun 2026 ($160.95) — not a 31 Dec 2025 YTD." (the YTD column label "Since listing 12 Jun 2026" is untouched) |
| Chart modal sub-blurb — GOLD | "COMEX gold futures (GC=F), $/troy oz. Weekly candles, UTC Monday–Sunday weeks, 1 Jan 2026 to the latest week. Candles are shipped with this page, data as of 30 Oct 2026 — a dated snapshot, not a live quote. Tap a candle for its week and open / high / low / close." | "Weekly candles, data to 30 Oct 2026. Tap a candle for its week." |
| Chart modal sub-blurb — WTI | NYMEX front-month paragraph incl. "continuous front-month series — gaps where contracts roll over", "data as of 30 Oct 2026, 3:42 p.m. ET — dated snapshot", "latest week in progress, not a final close" | "Weekly candles, data to 30 Oct 2026. Latest week in progress. Tap a candle for its week." (the in-progress guard is kept — the current line also still reads "(in progress)") |
| Chart modal sub-blurb — US10Y | "^TNX … Weekly candles, UTC Monday–Sunday weeks … dated snapshot … latest week is a final close, not in progress" | "Weekly candles, data to 30 Oct 2026. Tap a candle for its week." |
| Chart modal sub-blurb — VIX | "^VIX … in points … UTC Monday–Sunday weeks … dated snapshot … final close, not in progress. No VIX ETF is substituted." | "Weekly candles, data to 30 Oct 2026. Tap a candle for its week." |
| Chart modal footer "+" and paragraph | Footer "+" opened a paragraph: source label, "weekly candles shipped … data as of … latest week ends … 44 weekly candles … First week is partial: 1 trading day (2 Jan 2026)…", plus WTI roll-over/in-progress lines and US10Y/VIX footNotes ("Manual refresh only, when Sunil asks", VIX 215-vs-209 day counts and Cboe holiday days) | Deleted — button element, its listener, and the footer-paragraph builder are all removed. After a chart loads, the status line simply reads "Tap a candle for its week." |
| Pack "sources" paragraph | 1,222-character corroboration paragraph in `screener-pack.json` (`sources` field) | Verified NOT rendered anywhere on the page (no code reads the `sources` field), so the field itself is left untouched in the data file and in INFO-PACKAGE — there was no visitor-facing copy to delete, and deleting a data field would have been a data change, not a text change. Same for the weekly JSON `note` fields: never rendered, left untouched, and no longer reachable from the page now that the modal footer "+" is gone. |
| "Manual refresh only, when Sunil asks" | Present in US10Y/VIX footNotes and the WTI footer paragraph | Gone from all visitor-facing text (grep-verified below). It remains only in internal review notes, where it belongs. |

## Bitcoin pill — readability (Sunil addition, same branch)
The pill looked small because its price was 19px while the tile values it sits above are 27px, and its % change inherited a 12px rule (`.hdr-chg`, 0.75rem) from the shared stylesheet. Fixed in the screener's own inline styles only — the homepage pill and the shared stylesheet are untouched, and the pill's behaviour, chart, data and values are unchanged.

| Element | Before | After | Page standard matched |
|---|---|---|---|
| BTC pill price (`.btc-pill-row .hdr-tick`) | 19px, weight 800 | 27px, weight 850, letter-spacing −0.02em, line-height 1.1 | Indicator-tile value `.tile .v` (27px, 850, −0.02em, 1.1) |
| BTC pill % change (`.btc-pill-row .hdr-chg`, new rule) | 12px inherited from shared `.hdr-chg` | 14px, weight 800 | Indicator-tile day change `.tile .d` (14px, 800) |
| BTC pill price, desktop ≥700px | 19px (no desktop rule) | 30px | `.tile .v` desktop (30px) |
| BTC pill, phone width 390px | 19px price / 12px change | 27px / 14px, same rule (no phone-specific override) | Estimated content width ≈ 300px vs ≈ 326px available inside the pill — fits; true iPhone-width visual check remains Grok Bot's check |

## What was NOT changed
- Data and numbers: verified by script — pack numbers identical to main except notes removed/shortened and version 9 → 10; all four weekly files untouched (44 weeks each); no price, close, YTD, or day-count value changed.
- Behaviour: status lines, clock split, BTC pill click/chart, vehicle toggle, search/filter/sort, comparison chart, candle-tap pills — all untouched. The row "+" mechanism itself is untouched; it simply has no note to show except SPCX.
- Cache busters (required so the new text is actually served, not cached): pack `?v=8` → `?v=9` in `screener.js`; indicator-chart script `?v=vix1` → `?v=clean1` in `screener.html`.
- No STRF/STRK/STRD wording introduced (grep-verified). No banner text changed. No INFO-PACKAGE change.

## Checks run
- `node --check` passes on `screener.js` and `screener-indicator-chart.js`.
- Grep: no "Manual refresh only, when Sunil asks", no "YCharts", no footer-button references in page/modals; "UTC Monday" survives only in a code comment inside the indicator module, not in visitor text.
- Modal configs verified: all four subBlurbs are the one-line versions above; `footNote` field gone from the module.
- Existing tests still pass: ET 31/31, money 15/15 (unaffected areas, run as a regression sanity check).
- NOT verified here: painted-browser / real phone tap, including the BTC pill at true iPhone width — that remains Grok Bot's check, as with earlier branches. A generic subagent cannot operate a live browser.
- One fix made during this build, disclosed: an early edit left a `showFooterInfo(foot)` call pointing at a removed variable, which would have thrown when a chart loaded. It was caught by inspection, removed with the whole footer builder, and `node --check` passes — but Grok Bot's headless run should still exercise a chart load, since this branch touches that load path.

## Rollout (for Grok Bot to take over — NOT done here)
1. Grok Bot diff-only review of this branch. 2. Sunil's own yes. 3. Push to main (prices.yml is not touched by this branch, so no web-edit step is needed). 4. One live check, including the BTC pill at phone width. 5. Rollback: revert the single release commit.
