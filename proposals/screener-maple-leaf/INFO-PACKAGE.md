> **HIDDEN EXPERIMENTAL FEATURE — This screener is NOT advertised anywhere on the site. It is reachable ONLY by double-clicking (desktop) or double-tapping (iPhone/iPad/mobile) the footer Canadian maple leaf. It is experimental, it may be changed or removed at any time, and it is not part of the main PaperStreet tracker. Do not announce it, link it, or list it on the site unless Sunil explicitly says to.**

> **Correction 29 Oct 2026: SpaceX was wrongly shown as private. SpaceX is public as SPCX (IPO 12 June 2026, $135), 28 Oct close $145.23. META (Meta Platforms / Facebook) added, 28 Oct close $612.49. Screener now has 7 rows, all public; the Private filter was removed.**

> **Chart added 29 Oct 2026: an interactive "Comparison chart" now sits below the table on the screener page, built with the site's own vendored Chart.js. It shows bars for the seven symbols with a toggle between "Day change %" (default) and "YTD %"; bars are green for positive and red for negative, tooltips show symbol, name, and the exact %, and clicking a bar highlights that row in the table (clicking a table row highlights the matching bar). The chart reads its values from screener-pack.json (pack v2) only — no second copy of the numbers and no invented price series. In YTD view, MU, SPCX, and META are omitted and a note says so, because the pack holds no Dec 31 value for them.**

> **29 Oct 2026 cache fix: pack fetch now uses ?v=2 (pack v3) so the live page cannot keep serving a cached v1 pack after an update.**

# Stock Screener — Maple Leaf Pack: Information Package for the Grok Bot

## Hidden and experimental — status

This screener is hidden by design: there is no menu link, no button, and no announcement for it anywhere on the site — the only way in is the footer maple leaf double-click / double-tap. It is experimental, not a launched site feature, and Grok Bot / Chief of Staff should treat it as an experiment to review, not as part of the main PaperStreet tracker. It may be changed or removed at any time, and removal is by deleting the pack (as documented below) — nothing needs to be reverted.

## What was built

A standalone stock screener page, opened by double-clicking the Canadian maple leaf in the footer of the main page. It covers seven names: TSLA, PLTR, MSTR, IBIT, MU, SPCX (SpaceX), and META (Meta Platforms / Facebook). It is a screener view only — no buy/sell recommendation, no trade button, and no live price feed.

## How to open it

Double-click the footer maple leaf (the red leaf at the bottom of the main page). It opens `screener.html` in a new tab. A title hint on the leaf says "Double-click for the stock screener". Single clicks do nothing new.

## The seven rows (closes as of 28 Oct 2026)

| Symbol | Name | Price | Day change | YTD |
|---|---|---|---|---|
| TSLA | Tesla | $404.22 | −$3.24 (−0.79%, vs 27 Oct $407.46) | −10.11% (31 Dec 2025 $449.72) |
| PLTR | Palantir | $196.81 | −$1.92 (−0.97%, vs 27 Oct $198.73) | +10.72% (31 Dec 2025 $177.75) |
| MSTR | Strategy | $145.16 | +$3.76 (+2.66%, vs 27 Oct $141.40) | −4.47% (31 Dec 2025 $151.95) |
| IBIT | iShares Bitcoin Trust | $46.14 | +$0.44 (+0.96%, vs 27 Oct $45.70) | −7.07% (31 Dec 2025 $49.65) |
| MU | Micron Technology | $983.23 | +$54.47 (+5.86%, vs 27 Oct $928.76) | n/a — no Dec 31 price in site data, so none is shown |
| SPCX | Space Exploration Technologies (SpaceX) | $145.23 | −$3.35 (−2.25%, vs 27 Oct $148.58) | n/a — not public on 31 Dec 2025 (IPO 12 June 2026 at $135), so none is shown |
| META | Meta Platforms (Facebook) | $612.49 | −$7.70 (−1.24%, vs 27 Oct $620.19) | n/a — no Dec 31 price in site data, so none is shown |

Summary pills on the page: biggest gainer MU +5.86%, biggest loser SPCX −2.25%.

Two honest limits, stated on the page itself: MU's and META's year-to-date figures are shown as "n/a" because no 31 Dec 2025 price for them is in the site data — no price was invented. SPCX's year-to-date figure is likewise "n/a" because SpaceX was not public on 31 Dec 2025. MU's day move is noted in one plain line as following memory-chip news (SK hynix), with no recommendation attached.

## Features borrowed from the site

Site style throughout: background #070b18, text #e8eef7, Inter/Outfit, orange #f97316, cyan #22d3ee, card #121a2e, border #1e293b, Benchmark-button pill style, and the "Not financial advice / Not an offer to buy or sell" disclaimer. The screener itself has a search box, filter pills (All / Gainers / Losers), and sortable columns (Price, Day change, YTD — click a header to sort; SPCX sorts by its $145.23 price like any other row).

## Files added (additive only)

- `screener.html` — the standalone screener page.
- `assets/data/screener-pack.json` — the whole data pack (the seven rows plus metadata: pack "maple-leaf-screener", version 2, asOf "2026-10-28", sources, removable: true).
- `assets/js/screener.js` — renders the table from the data pack only; no live price API, no other data source.
- `assets/js/screener-chart.js` — the interactive comparison chart; reads the same data pack only, no second copy of the numbers.
- `assets/js/maple-screener.js` — the leaf double-click only; it opens screener.html in a new tab and sets the title hint via JavaScript.
- `index.html` — ONE added script tag for `assets/js/maple-screener.js`, near the other script tags. No other index.html change.

## What was NOT changed

The leaf SVG itself was not altered. No existing site logic, page, ledger, or data file was modified. No live price feed was added — the screener shows the 28 Oct 2026 closes above and says so on the page. Nothing was sent to any external service.

## Removable by design — how to shut it off and delete it

The pack is fully additive, so removal is deletion, not a revert:

1. Delete `screener.html`.
2. Delete `assets/data/screener-pack.json`.
3. Delete `assets/js/screener.js`.
4. Delete `assets/js/screener-chart.js`.
5. Delete `assets/js/maple-screener.js`.
6. Remove the one `maple-screener.js` script tag from `index.html`.

That is the whole removal. No existing file's logic was modified, so no old version needs restoring, and with the script tag gone the footer leaf simply does nothing on double-click again. No feature flag in existing code is needed because nothing existing was changed.

## Deploy status

This pack was built on a test branch first, for Sunil's review. Deploy is by Sunil's immediate instruction — this package does not deploy anything itself.
