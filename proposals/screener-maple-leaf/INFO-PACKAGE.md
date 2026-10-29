> **HIDDEN EXPERIMENTAL FEATURE — This screener is NOT advertised anywhere on the site. It is reachable ONLY by double-clicking (desktop) or double-tapping (iPhone/iPad/mobile) the footer Canadian maple leaf. It is experimental, it may be changed or removed at any time, and it is not part of the main PaperStreet tracker. Do not announce it, link it, or list it on the site unless Sunil explicitly says to.**

> **Correction 29 Oct 2026: SpaceX was wrongly shown as private. SpaceX is public as SPCX (IPO 12 June 2026, $135), 28 Oct close $145.23. META (Meta Platforms / Facebook) added, 28 Oct close $612.49. Screener now has 7 rows, all public; the Private filter was removed.**

> **Chart added 29 Oct 2026: an interactive "Comparison chart" now sits below the table on the screener page, built with the site's own vendored Chart.js. It shows bars for the seven symbols with a toggle between "Day change %" (default) and "YTD %"; bars are green for positive and red for negative, tooltips show symbol, name, and the exact %, and clicking a bar highlights that row in the table (clicking a table row highlights the matching bar). The chart reads its values from screener-pack.json (pack v2) only — no second copy of the numbers and no invented price series. In YTD view, MU, SPCX, and META are omitted and a note says so, because the pack holds no Dec 31 value for them.**

> **29 Oct 2026 cache fix: pack fetch now uses ?v=2 (pack v3) so the live page cannot keep serving a cached v1 pack after an update.**

> **29 Oct 2026 two-box update (pack v5): the screener is now TWO boxes, not one list. Stocks box: the same 7 stocks, unchanged in content. Market Indicators box (new, titled exactly "Market Indicators"): WTI crude oil ($/barrel), Gold spot ($/oz), 10-Year Treasury Yield (%), and VIX (points — an index level, not a price). The per-row Status column is GONE: each table now has ONE status line below it, for the whole table, because all rows in a table trade on the same clock. If one symbol's quote is missing, that below-table line says so plainly instead of claiming Live for all. Signed-number colours, everywhere (table day/YTD, summary pills, chart bars): positive green #22c55e, negative red #ef4444, signed zero black #000000 — with a flagged conflict: pure black is near-invisible on this dark page, see the section below. The comparison chart is STOCKS ONLY: Market Indicators are not charted, because dollars, % and VIX points do not share an axis. Gold spot is NOT live yet (see below); WTI, 10Y and VIX go live only once the Yahoo pipeline block in the section below is applied by web edit — until then they show honest 28 Oct 2026 closes, never a Live label. Pack fetch is now ?v=4 (pack v5).**

> **29 Oct 2026 live-price fix: the screener was showing only the 28 Oct 2026 snapshot while every row was labelled "Live data" — that was the error, and Sunil caught it. It now reads the site's own pipeline prices.json on page load (and every 5 minutes while open) for TSLA, PLTR, MSTR and IBIT, recomputing day change vs the prior close and YTD vs the pack's Dec 31 value; during market hours those rows are labelled Live, outside hours they show the latest pipeline close dated honestly. MU, SPCX and META have no pipeline quote, so they honestly show their 28 Oct 2026 close, never a live label. The table, summary pills and chart all use the same merged rows; pack fetch is now ?v=3 (pack v4, row statuses corrected to "28 Oct close").**

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

## 29 Oct 2026 — Two boxes, Market Indicators, no Status column, sign colours

### Layout
- Stocks box: TSLA, PLTR, MSTR, IBIT, MU, SPCX, META — same seven rows, same 28 Oct 2026 closes, same search / filter / sort controls (those controls apply to the Stocks box only).
- Market Indicators box, titled exactly "Market Indicators", separate section below the comparison chart: WTI, GOLD, US10Y, VIX. It always shows all four; it has no search/filter/sort.
- Comparison chart: stocks only, Day change % / YTD % as before. Market Indicators are not in it, because $/barrel, $/oz, % and VIX points cannot share one axis without implying they are comparable. The chart note says so on the page.

### Market Indicators rows (28 Oct 2026 closes, YTD n/a for all four)
| Symbol | Name | Level | Day change | YTD |
|---|---|---|---|---|
| WTI | WTI Crude Oil | $102.78 /barrel | +$2.88 (+2.88%, vs 27 Oct $99.90) | n/a |
| GOLD | Gold Spot | $4,067.29 /oz | +$6.45 (+0.16%, vs 27 Oct $4,060.84) | n/a |
| US10Y | 10-Year Treasury Yield | 5.05% | +0.06 pp (+1.20%, vs 27 Oct 4.99%) | n/a |
| VIX | CBOE Volatility Index (VIX) | 16.91 points | −0.61 pts (−3.48%, vs 27 Oct 17.52) | n/a |

WTI is the NYMEX front-month futures quote — that is the usual WTI quote, not a substitution. Gold is spot (OANDA XAU/USD), $/troy ounce, not COMEX futures. The 10-Year Yield is the U.S. Treasury daily par yield; its day change is shown in percentage points (pp) plus the relative % so a yield is never presented as a dollar price. VIX is the Cboe index level in points, not a price; no VIX ETF (VIXY/VIXM) was substituted.

### Status: one line below each table, no per-row Status column
The Status column was removed entirely — from the table, from the pack (pack v5 rows carry no status field), and from the page. Each table's single status line, below that table, reads:
- Market hours, pipeline fresh, all rows quoted: "Live — site pipeline, market hours."
- Outside market hours, all rows quoted: "<date> close — site pipeline, not a live quote." (e.g. "29 Oct 2026 close — site pipeline, not a live quote.")
- No pipeline quote at all: "28 Oct 2026 closes from the data pack — not live quotes."
- Mixed (one symbol's quote missing, the normal Gold case until a spot feed exists): "Live for WTI, US10Y, VIX · 28 Oct 2026 closes for GOLD (no pipeline quote)." — or the same shape with a dated close instead of Live outside hours. The line never claims Live for a table that is not wholly live.
- Pipeline fetch fails on the load: "Pipeline quotes unavailable on this load — rows show their 28 Oct 2026 closes, not live quotes." (both tables).
The top of the page no longer carries a status claim; the below-table lines are the only status.

### Signed-number colours (Sunil's rule, applied everywhere)
Positive green #22c55e, negative red #ef4444, signed zero black #000000 — in the table (day change AND YTD change, each coloured by its own sign; previously the YTD cell wrongly followed the day sign, now fixed), in the biggest-gainer/loser pills, and in the chart bars (a zero bar is now black, previously it was green).
CONFLICT, flagged not hidden: pure black #000000 is near-invisible on this page's dark background (#070b18 page, #121a2e cards/chart). The rule is applied literally as Sunil stated, so a signed zero value or zero chart bar will be very hard to read on the dark page. If Sunil wants zeros readable, the readable neutral on this page is the default light text #e8eef7 — that would need his explicit approval as a change to the rule, it was NOT substituted silently. 'n/a' is not a signed number, so it keeps the default light text, not black. No row currently has a signed zero, so no live row is affected today; the conflict only bites if a zero day/YTD value ever appears.

### Live routes — what is proven, what is blocked, what is pending
- Finnhub's /quote endpoint is US-stocks-only (Finnhub's own docs: "Get real-time quote data for US stocks"). Adding WTI/Gold/10Y/VIX to the existing Finnhub symbol list would NOT work — that one-line change is explicitly NOT the route for these four.
- WTI, 10Y, VIX — live-ready via Yahoo chart, pending a workflow edit (parent applies, see below). Yahoo symbols, verified in public listings: WTI <- CL=F (NYMEX front-month), 10Y <- ^TNX, VIX <- ^VIX. The screener code already maps pipeline keys WTI / US10Y / VIX to these rows, so once the pipeline writes those keys the rows go Live automatically on the next pipeline run, with no further screener change.
- Gold spot — BLOCKED for live, honestly snapshot-only. Yahoo has no working spot ticker (XAUUSD=X returns no data; GC=F is COMEX futures, not spot, and mapping it into the spot row would silently swap the series and jump ~$15). Finnhub does list OANDA XAU/USD as a forex symbol, but its /quote endpoint does not carry forex, and its forex endpoints are reported as paid-tier / 403 on a free key — not a proven clean route. So GOLD has no pipeline key, and its below-table line will name it as the snapshot row while the other three go live. If Sunil accepts COMEX futures as the gold row, that row must be relabelled "Gold (COMEX futures)" first — it was NOT relabelled or remapped silently. A FRED-style daily yield feed was not needed for the 10Y (Yahoo ^TNX covers it) and is not the proposed route.

### Pipeline change for the parent (GitHub web edit — workflow files cannot be pushed via the App API)
In .github/workflows/prices.yml, in the "Fetch prices" step, AFTER the Finnhub symbol loop and BEFORE the CoinGecko BTC block, insert the Yahoo indicators block (keyless, same get() helper and same keep-previous-on-failure rule as the Finnhub loop; keys are screener keys, not Yahoo tickers):
```
          # --- market indicators (Yahoo chart, keyless) ---
          # Finnhub /quote is US-stocks-only, so it cannot carry these.
          # Yahoo chart meta is the same source the history rebuild uses.
          # Gold spot deliberately NOT mapped: Yahoo has no working XAUUSD
          # spot ticker (GC=F is futures, not spot) — do not map GC=F
          # into GOLD silently.
          for key, sym in [('WTI', 'CL%3DF'), ('US10Y', '%5ETNX'), ('VIX', '%5EVIX')]:
              try:
                  m = get(f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1d')['chart']['result'][0]['meta']
                  c_, pc_ = m.get('regularMarketPrice'), m.get('chartPreviousClose')
                  if isinstance(c_, (int, float)) and c_ > 0 and isinstance(pc_, (int, float)) and pc_ > 0:
                      out['stocks'][key] = {'c': c_, 'pc': pc_, 't': m.get('regularMarketTime')}; ok += 1
                  else: print(key, 'bad Yahoo meta, keeping previous')
              except Exception as e: print(key, 'Yahoo failed, keeping previous:', type(e).__name__)
```
After this lands, stocks_ok should read 16 (13 stocks + WTI + US10Y + VIX); GOLD is not counted. No Finnhub list change is needed for this update — the 13-symbol Finnhub list is unchanged.
