> **HIDDEN EXPERIMENTAL FEATURE — This screener is NOT advertised anywhere on the site. It is reachable ONLY by double-clicking (desktop) or double-tapping (iPhone/iPad/mobile) the footer Canadian maple leaf. It is experimental, it may be changed or removed at any time, and it is not part of the main PaperStreet tracker. Do not announce it, link it, or list it on the site unless Sunil explicitly says to.**

# Stock Screener — Maple Leaf Pack: Information Package for the Grok Bot

## Hidden and experimental — status

This screener is hidden by design: there is no menu link, no button, and no announcement for it anywhere on the site — the only way in is the footer maple leaf double-click / double-tap. It is experimental, not a launched site feature, and Grok Bot / Chief of Staff should treat it as an experiment to review, not as part of the main PaperStreet tracker. It may be changed or removed at any time, and removal is by deleting the pack (as documented below) — nothing needs to be reverted.

## What was built

A standalone stock screener page, opened by double-clicking the Canadian maple leaf in the footer of the main page. It covers six names: TSLA, PLTR, MSTR, IBIT, MU, and SpaceX. It is a screener view only — no buy/sell recommendation, no trade button, and no live price feed.

## How to open it

Double-click the footer maple leaf (the red leaf at the bottom of the main page). It opens `screener.html` in a new tab. A title hint on the leaf says "Double-click for the stock screener". Single clicks do nothing new.

## The six rows (closes as of 28 Oct 2026)

| Symbol | Name | Price | Day change | YTD |
|---|---|---|---|---|
| TSLA | Tesla | $404.22 | −$3.24 (−0.79%, vs 27 Oct $407.46) | −10.11% (31 Dec 2025 $449.72) |
| PLTR | Palantir | $196.81 | −$1.92 (−0.97%, vs 27 Oct $198.73) | +10.72% (31 Dec 2025 $177.75) |
| MSTR | Strategy | $145.16 | +$3.76 (+2.66%, vs 27 Oct $141.40) | −4.47% (31 Dec 2025 $151.95) |
| IBIT | iShares Bitcoin Trust | $46.14 | +$0.44 (+0.96%, vs 27 Oct $45.70) | −7.07% (31 Dec 2025 $49.65) |
| MU | Micron Technology | $983.23 | +$54.47 (+5.86%, vs 27 Oct $928.76) | n/a — no Dec 31 price in site data, so none is shown |
| SpaceX | SpaceX | Private — no public quote | — | — |

Summary pills on the page: biggest gainer MU +5.86%, biggest loser PLTR −0.97%.

Two honest limits, stated on the page itself: MU's year-to-date figure is shown as "n/a" because no 31 Dec 2025 price for MU is in the site data — no price was invented. SpaceX is a private company with no ticker and no public share price, so it is shown as a watch item only and price screening does not apply to it; no price or valuation was invented. MU's day move is noted in one plain line as following memory-chip news (SK hynix), with no recommendation attached.

## Features borrowed from the site

Site style throughout: background #070b18, text #e8eef7, Inter/Outfit, orange #f97316, cyan #22d3ee, card #121a2e, border #1e293b, Benchmark-button pill style, and the "Not financial advice / Not an offer to buy or sell" disclaimer. The screener itself has a search box, filter pills (All / Gainers / Losers / Private), and sortable columns (Price, Day change, YTD — click a header to sort; SpaceX always sorts last on price).

## Files added (additive only)

- `screener.html` — the standalone screener page.
- `assets/data/screener-pack.json` — the whole data pack (the six rows plus metadata: pack "maple-leaf-screener", version 1, asOf "2026-10-28", sources, removable: true).
- `assets/js/screener.js` — renders the table from the data pack only; no live price API, no other data source.
- `assets/js/maple-screener.js` — the leaf double-click only; it opens screener.html in a new tab and sets the title hint via JavaScript.
- `index.html` — ONE added script tag for `assets/js/maple-screener.js`, near the other script tags. No other index.html change.

## What was NOT changed

The leaf SVG itself was not altered. No existing site logic, page, ledger, or data file was modified. No live price feed was added — the screener shows the 28 Oct 2026 closes above and says so on the page. Nothing was sent to any external service.

## Removable by design — how to shut it off and delete it

The pack is fully additive, so removal is deletion, not a revert:

1. Delete `screener.html`.
2. Delete `assets/data/screener-pack.json`.
3. Delete `assets/js/screener.js`.
4. Delete `assets/js/maple-screener.js`.
5. Remove the one `maple-screener.js` script tag from `index.html`.

That is the whole removal. No existing file's logic was modified, so no old version needs restoring, and with the script tag gone the footer leaf simply does nothing on double-click again. No feature flag in existing code is needed because nothing existing was changed.

## Deploy status

This pack was built on a test branch first, for Sunil's review. Deploy is by Sunil's immediate instruction — this package does not deploy anything itself.
