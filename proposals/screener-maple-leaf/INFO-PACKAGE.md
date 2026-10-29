> **29 Oct 2026 YTD fix (pack v6): Sunil was right — META and MU traded all through 2025, so they now have true YTD figures. META base 31 Dec 2025 $660.09 → YTD −7.21% at the 28 Oct close $612.49. MU base 31 Dec 2025 $285.41 → YTD +244.50% at the 28 Oct close $983.23. SPCX was NOT public on 31 Dec 2025, so it has NO true YTD: its YTD column now shows return since its 12 Jun 2026 first trading close $160.95 → −9.77% at $145.23, labelled "Since listing 12 Jun 2026" in the cell, in the Stocks box note, and in the chart note — never presented as Dec 31 YTD, and SPCX is excluded from the YTD chart for that reason. The $135 IPO price was NOT used as the base. Pack fetch is now ?v=5 (pack v6).**

> **HIDDEN EXPERIMENTAL FEATURE — This screener is NOT advertised anywhere on the site. It is reachable ONLY by double-clicking (desktop) or double-tapping (iPhone/iPad/mobile) the footer Canadian maple leaf. It is experimental, it may be changed or removed at any time, and it is not part of the main PaperStreet tracker. Do not announce it, link it, or list it on the site unless Sunil explicitly says to.**

> **Correction 29 Oct 2026: SpaceX was wrongly shown as private. SpaceX is public as SPCX (IPO 12 June 2026, $135), 28 Oct close $145.23. META (Meta Platforms / Facebook) added, 28 Oct close $612.49. Screener now has 7 rows, all public; the Private filter was removed.**

> **Chart added 29 Oct 2026: an interactive "Comparison chart" now sits below the table on the screener page, built with the site's own vendored Chart.js. It shows bars for the seven symbols with a toggle between "Day change %" (default) and "YTD %"; bars are green for positive and red for negative, tooltips show symbol, name, and the exact %, and clicking a bar highlights that row in the table (clicking a table row highlights the matching bar). The chart reads its values from screener-pack.json (pack v2) only — no second copy of the numbers and no invented price series. In YTD view, SPCX is omitted and a note says why (its figure is since-listing, not YTD); META and MU are now included, since their 31 Dec 2025 bases were added 29 Oct 2026 (pack v6).**

> **29 Oct 2026 cache fix: pack fetch now uses ?v=2 (pack v3) so the live page cannot keep serving a cached v1 pack after an update.**

> **29 Oct 2026 two-box update (pack v5): the screener is now TWO boxes, not one list. Stocks box: the same 7 stocks, unchanged in content. Market Indicators box (new, titled exactly "Market Indicators"): WTI crude oil ($/barrel), Gold (COMEX futures from 29 Oct 2026 — spot at pack v5 time; see gold update below) ($/oz), 10-Year Treasury Yield (%), and VIX (points — an index level, not a price). The per-row Status column is GONE: each table now has ONE status line below it, for the whole table, because all rows in a table trade on the same clock. If one symbol's quote is missing, that below-table line says so plainly instead of claiming Live for all. Signed-number colours, everywhere (table day/YTD, summary pills, chart bars): positive green #22c55e, negative red #ef4444, signed zero black #000000 — with a flagged conflict: pure black is near-invisible on this dark page, see the section below. The comparison chart is STOCKS ONLY: Market Indicators are not charted, because dollars, % and VIX points do not share an axis. Gold (then spot) is NOT live yet (see below; now COMEX futures — see gold update below); WTI, 10Y and VIX go live only once the Yahoo pipeline block in the section below is applied by web edit — until then they show honest 28 Oct 2026 closes, never a Live label. Pack fetch is now ?v=4 (pack v5).**

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
| MU | Micron Technology | $983.23 | +$54.47 (+5.86%, vs 27 Oct $928.76) | +244.50% (31 Dec 2025 $285.41) |
| SPCX | Space Exploration Technologies (SpaceX) | $145.23 | −$3.35 (−2.25%, vs 27 Oct $148.58) | −9.77% SINCE LISTING (first trading close 12 Jun 2026 $160.95 — NOT a Dec 31 YTD) |
| META | Meta Platforms (Facebook) | $612.49 | −$7.70 (−1.24%, vs 27 Oct $620.19) | −7.21% (31 Dec 2025 $660.09) |

Summary pills on the page: biggest gainer MU +5.86%, biggest loser SPCX −2.25%.

Two honest limits, stated on the page itself (UPDATED 29 Oct 2026 — the n/a figures below are superseded): MU's and META's year-to-date figures were first shown as "n/a" because no 31 Dec 2025 price for them was in the site data. They now have true YTD figures from verified 31 Dec 2025 closes (MU $285.41, META $660.09 — see the YTD fix section). SPCX still has no Dec 31 YTD, because SpaceX was not public on 31 Dec 2025; its figure is return since listing, labelled as such, never as YTD. MU's day move is noted in one plain line as following memory-chip news (SK hynix), with no recommendation attached.

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
| GOLD | Gold (COMEX futures) | $4,051.60 /oz | -$23.00 (-0.56%, vs 27 Oct $4,074.60) | n/a |
| US10Y | 10-Year Treasury Yield | 5.05% | +0.06 pp (+1.20%, vs 27 Oct 4.99%) | n/a |
| VIX | CBOE Volatility Index (VIX) | 16.91 points | −0.61 pts (−3.48%, vs 27 Oct 17.52) | n/a |

WTI is the NYMEX front-month futures quote — that is the usual WTI quote, not a substitution. Gold is COMEX futures (GC=F), $/troy ounce, not spot (changed 29 Oct 2026 — see gold update below). The 10-Year Yield is the U.S. Treasury daily par yield; its day change is shown in percentage points (pp) plus the relative % so a yield is never presented as a dollar price. VIX is the Cboe index level in points, not a price; no VIX ETF (VIXY/VIXM) was substituted.

### Status: one line below each table, no per-row Status column
The Status column was removed entirely — from the table, from the pack (pack v5 rows carry no status field), and from the page. Each table's single status line, below that table, reads:
- Market hours, pipeline fresh, all rows quoted: "Live — site pipeline, market hours."
- Outside market hours, all rows quoted: "<date> close — site pipeline, not a live quote." (e.g. "29 Oct 2026 close — site pipeline, not a live quote.")
- No pipeline quote at all: "28 Oct 2026 closes from the data pack — not live quotes."
- Mixed (one symbol's quote missing): "Live for WTI, US10Y, VIX · 28 Oct 2026 closes for GOLD (no pipeline quote)." — or the same shape with a dated close instead of Live outside hours. The line never claims Live for a table that is not wholly live.
- Pipeline fetch fails on the load: "Pipeline quotes unavailable on this load — rows show their 28 Oct 2026 closes, not live quotes." (both tables).
The top of the page no longer carries a status claim; the below-table lines are the only status.

### Signed-number colours (Sunil's rule, applied everywhere)
Positive green #22c55e, negative red #ef4444, signed zero black #000000 — in the table (day change AND YTD change, each coloured by its own sign; previously the YTD cell wrongly followed the day sign, now fixed), in the biggest-gainer/loser pills, and in the chart bars (a zero bar is now black, previously it was green).
CONFLICT, flagged not hidden: pure black #000000 is near-invisible on this page's dark background (#070b18 page, #121a2e cards/chart). The rule is applied literally as Sunil stated, so a signed zero value or zero chart bar will be very hard to read on the dark page. If Sunil wants zeros readable, the readable neutral on this page is the default light text #e8eef7 — that would need his explicit approval as a change to the rule, it was NOT substituted silently. 'n/a' is not a signed number, so it keeps the default light text, not black. No row currently has a signed zero, so no live row is affected today; the conflict only bites if a zero day/YTD value ever appears.

### Live routes — what is proven, what is blocked, what is pending
- Finnhub's /quote endpoint is US-stocks-only (Finnhub's own docs: "Get real-time quote data for US stocks"). Adding WTI/Gold/10Y/VIX to the existing Finnhub symbol list would NOT work — that one-line change is explicitly NOT the route for these four.
- WTI, 10Y, VIX — live-ready via Yahoo chart, pending a workflow edit (parent applies, see below). Yahoo symbols, verified in public listings: WTI <- CL=F (NYMEX front-month), 10Y <- ^TNX, VIX <- ^VIX. The screener code already maps pipeline keys WTI / US10Y / VIX to these rows, so once the pipeline writes those keys the rows go Live automatically on the next pipeline run, with no further screener change.
- Gold spot — WAS BLOCKED for live, honestly snapshot-only (superseded 29 Oct 2026, see gold update below). Yahoo has no working spot ticker (XAUUSD=X returns no data). Finnhub does list OANDA XAU/USD as a forex symbol, but its /quote endpoint does not carry forex, and its forex endpoints are reported as paid-tier / 403 on a free key — not a proven clean route. So GOLD had no pipeline key under the spot label, and its below-table line named it as the snapshot row while the other three go live. Sunil then approved COMEX futures (29 Oct 2026, "Go with gold comex Futures"), so the row was relabelled and re-based — see gold update below — and GOLD now goes live via GC=F once the parent's separate pipeline edit lands. A FRED-style daily yield feed was not needed for the 10Y (Yahoo ^TNX covers it) and is not the proposed route.

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

## 29 Oct 2026 — YTD fix: META and MU get true YTD, SPCX gets since-listing (pack v6)

Sunil pointed out it was weird that META, MU and SPCX had no YTD numbers. He was right for META and MU, and partly right for SPCX — fixed properly, nothing invented:
- META: 31 Dec 2025 close $660.09 (UNADJUSTED close, matching the site's Yahoo unadjusted convention — the $658.40 figure seen in some tables is the dividend-adjusted close and was NOT used). Sources converging on $660.09: Digrin "Real price" for Dec 2025, financecharts 12/31/2025 close, companiesmarketcap 31 Dec 2025 price, daytrading Dec 2025 close, Motley Fool year-end figure — and a cross-check: Finnhub's YTD at its live price $624.52 is −5.39%, which implies a base of $660.08, matching $660.09 to the cent. YTD at the pack close: $612.49 vs $660.09 = −7.21% (red).
- MU: 31 Dec 2025 close $285.41 (unadjusted; Digrin "Real price" $285.41 vs adjusted $285.25). Sources converging on $285.41: Digrin, Momoview, Macrotrends year close $285.20 (adjusted, close to it), and multiple 13F holdings prices at 31 Dec 2025 ($285.41) — and the same Finnhub cross-check: Finnhub YTD at $934.27 is +227.34%, which implies a base of $285.41 exactly. YTD at the pack close: $983.23 vs $285.41 = +244.50% (green).
- SPCX: NO Dec 31 YTD exists and none was faked. Base used is the first trading close, 12 June 2026: $160.95 (Axi, stockmarketwatch, TradingView/Benzinga, financer — all agree; opened $150, IPO priced $135 on 11 June). The $135 IPO price was NOT used as the base, because it was never a traded close. Return at the pack close: $145.23 vs $160.95 = −9.77% (red), shown in the YTD column ONLY with the label "Since listing 12 Jun 2026" in the cell itself, plus the Stocks box note and the SPCX row note. SPCX is excluded from the YTD comparison chart, because a since-listing return must not sit on a YTD axis. If the first-trading close had not verified, SPCX would have stayed n/a — it verified three-plus ways, so it did not need to.
- Live behaviour: when a pipeline quote arrives, META/MU YTD recomputes vs their Dec 31 bases and SPCX recomputes vs $160.95, keeping its since-listing label — so live YTD values will move after the pack snapshot, which is correct.
- Sign colours apply to all three new figures (green positive, red negative, black signed zero, as in the two-box update).
- No Finnhub-derived YTD shortcut was used: the bases above are actual closes, and the Finnhub YTD figures are cited only as an independent cross-check that lands on the same bases.


## 29 Oct 2026 — Gold now COMEX futures (pack v7, Sunil: "Go with gold comex Futures")

- Label everywhere is now exactly "Gold (COMEX futures)": the Market Indicators row name, the row note, the box note, the page disclaimer, and this package. Unit stays $/troy oz — COMEX futures are quoted per troy ounce, so no unit change was needed. Day change is shown the same way as before, YTD stays n/a.
- The snapshot WAS replaced, because the old snapshot was a spot figure and keeping it under a futures label would have been a silent series swap. Old (spot, removed): $4,067.29, prev $4,060.84, +$6.45 (+0.16%). New (COMEX futures, verified): 28 Oct 2026 close $4,051.60, 27 Oct $4,074.60, day change -$23.00 (-0.56%). Source: Yahoo GC=F daily series (COMEX front-month, Dec 2026 contract) — the 28 Oct bar is high $4,097.2 / low $4,036.9 / close $4,051.6, corroborated by the published COMEX daily-bar summaries for that session. The $4,073.72 settle figure seen in one report was NOT used: it conflicts with the Yahoo GC=F series and with the published 28 Oct bar close, and Yahoo GC=F is the series the pipeline will write.
- Live merging for GOLD is enabled in the screener code with no special-casing: mergeList() is generic by symbol, so once the pipeline writes a GOLD key (GC=F, via the parent's separate prices.yml edit), the GOLD row goes Live in market hours / dated pipeline close outside hours automatically, with no further screener change. Until that pipeline edit lands, GOLD shows its honest 28 Oct 2026 futures close from the pack, never a Live label.
- The quoted pipeline block in the section above is the block as landed for WTI/US10Y/VIX (commit f5cc6f4); the parent's separate edit adds GOLD (GC=F) to it. That quoted block is a historical record of the WTI/US10Y/VIX edit, not the current pipeline text for GOLD.
- Pack fetch buster bumped ?v=5 → ?v=6 (pack v7) so the new futures snapshot is not served from cache.
