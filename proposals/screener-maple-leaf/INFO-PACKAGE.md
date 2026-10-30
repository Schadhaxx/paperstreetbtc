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

## 29 Oct 2026 — YTD column removed from Market Indicators only (Sunil: "Get rid of the ytd column for market indicators")

- The Market Indicators box (WTI, Gold (COMEX futures), US10Y, VIX) no longer has a YTD column at all — header, rows, and the box's YTD note are gone. The table is now Symbol / Name / Level / Day change, with the status line below the table unchanged.
- The Stocks box is untouched: it keeps its YTD column exactly as before, including META/MU true YTD and SPCX "Since listing 12 Jun 2026". The stocks-only comparison chart is untouched, including its YTD view.
- Day change in the Market Indicators box keeps the signed-number colour rule (green positive, red negative, black signed zero). No pack change was needed (indicators' ytdPct values were already null and are simply no longer rendered), so the pack fetch buster was not bumped.

## 29 Oct 2026 — Long name notes moved behind a "+" pill (Sunil: cleaner tables)

- In both tables, the long descriptive text that used to sit under a row's Name is no longer rendered inline. The Name stays as a single clean line, with a small "+" button beside it only on rows that actually have such text. Tapping/clicking "+" opens a rounded pill popup containing that row's text word for word — nothing shortened, paraphrased, or dropped. The pill dismisses by tapping the pill itself, tapping "+" again, tapping elsewhere, or pressing Escape.
- Rows with a "+": Stocks — MU, SPCX. Market Indicators — WTI, GOLD, US10Y, VIX. Rows with no long name text (TSLA, PLTR, MSTR, IBIT, META) get no "+".
- Pill texts, exactly as in the pack: MU — "Day move followed memory-chip news (SK hynix). YTD vs 31 Dec 2025 close $285.41."; SPCX — "Public since 12 June 2026 IPO at $135; first trading close $160.95. YTD column shows return since that first close, NOT from 31 Dec 2025."; WTI — "NYMEX front-month futures — the usual WTI quote, $/barrel."; GOLD — "COMEX gold futures (GC=F), $/troy oz. Pack close only until the pipeline writes GOLD."; US10Y — "U.S. Treasury daily par yield, %. Day change in percentage points."; VIX — "Index level in points, not a price. No VIX ETF substituted."
- The "+" is a real button with an accessible label ("More about SYMBOL"), not bare text. Column sets are unchanged (Stocks 5 columns, Market Indicators 4 columns), day-change colours are unchanged, and the SPCX "Since listing 12 Jun 2026" label in its YTD cell is untouched — that is a YTD basis label, not a name note, so it stays visible. Search/filter/sort and the chart row-highlight behaviour are unchanged (the "+" click also triggers the existing row-click bar highlight on Stocks rows, as any row click does).
- No pack change was needed (the texts already lived in the pack's note fields and are simply no longer rendered inline), so the pack fetch buster was not bumped — pack stays v7, ?v=6.

## 30 Oct 2026 — Live-clock split: WTI/GOLD on futures hours, stocks/US10Y/VIX on stock hours; BTC live pill at the top of the page (Sunil, 30 Oct morning)

- CLOCK SPLIT: the two boxes no longer share one clock. Stocks are Live only Mon–Fri 9:30 a.m.–4:00 p.m. ET with a fresh pipeline quote. Market Indicators split by instrument: WTI and GOLD (COMEX futures) are Live in CME Globex futures hours — Sunday 6:00 p.m. ET through Friday 5:00 p.m. ET, excluding the daily 5:00–6:00 p.m. ET maintenance break — while US10Y and VIX stay on stock hours. A row is Live only when its own pipeline quote is fresh (<30 min, by that symbol's own pipeline timestamp where present — Finnhub quote time / Yahoo regularMarketTime — else the file stamp); a stale quote never reads Live, even in hours. Outside its hours, a row shows the latest pipeline value with a dated label, never labelled Live.
- STATUS LINES: each table still has ONE status line below it, but the indicators line now names which rows are Live and which are dated, and never claims the whole indicators table is Live when it is not. Exact wordings, from the shipped code: weekday 7:30 a.m. ET with fresh futures quotes — "Live for WTI, GOLD · 29 Oct 2026 close for US10Y, VIX."; weekday 10 a.m. ET all fresh — "Live — site pipeline, market hours."; weekday 5:30 p.m. ET (futures break) — "30 Oct 2026 close for WTI, GOLD · 29 Oct 2026 close for US10Y, VIX — site pipeline, not a live quote."; Saturday — all dated, never Live. Dated rows are grouped by the date their own quote belongs to, so a morning file carrying yesterday's stock closes says yesterday, not today. The stocks status line is unchanged in behaviour.
- PIPELINE WEEKEND NOTE (no pipeline change in this job): the pipeline writes prices every 5 min Mon–Fri UTC plus Sat 00:00–01:59 UTC (Fri evening ET); Sunday UTC has only a read-only stall check. That aligns with futures hours in practice: futures are closed Saturday and Sunday daytime (when the file would go stale anyway), and by Sunday 6:00 p.m. ET open the Monday-UTC runs are already writing fresh quotes every 5 min — so Sunday-evening futures Live is not blocked by the schedule, it just needs the first post-open run (within ~5 min) to land.
- BTC LIVE PILL AT THE TOP OF THE SCREENER PAGE (Sunil: "Make bitcoin pill at the top of this page too. Same as the one that you can click on on the homepage banner and get a chart"): the screener page now carries the homepage's own Live BTC pill at the top — live BTC price + 24h change, clickable to open the same BTC chart popover as the homepage (1D Line on open, ranges, chart types, SPX/Gold/MSTR overlays). It reuses the homepage code, not a second chart: screener.html includes nav.css (pill + popover styles) and btcchart.js?v=et4, with the same hdrTick/hdrPx/hdrChg ids, so btcchart.js paints it and opens its popover; with no homepage price widget on this page, btcchart.js fetches the same CoinGecko (Coinbase fallback) feed itself, every 60 seconds. The popover on the screener page is Spot BTC only — no vehicle row, per the 29 Oct popover removal. The screener page still works standalone: its pack/pipeline merge, tables, "+" pills, comparison chart, and clock-split status lines are untouched by the pill.
- UNCHANGED: column sets (Stocks 5, Indicators 4), "+" pill notes, day-change colours, search/filter/sort, comparison chart behaviour, pack file (still v7, fetch buster not bumped — no pack change), and every main-site file. No Grok Bot contact; screener stays hidden/leaf-only.

## 30 Oct 2026 — Jazzed redesign LIVE (Sunil: "implement it live", from the mockup he approved that morning)

- DESIGN: the live screener page now uses the mockup's modern dark-fintech design (gradient header glow, large price type, rounded cards and pills, KPI tiles, generous spacing) instead of plain tables. Source design: workspace/your_files/screener-jazzed-mockup.html. No company logos or trademarks were copied; the styling is generic.
- IPHONE-FIRST: one column at 390px, no horizontal scroll, no shrunken desktop table. Stocks render as cards stacked one per row on a phone (2 columns at 700px+, 3 at 1000px+); indicators render as KPI tiles (2 across on a phone, 4 across at 700px+). Touch targets: BTC pill 56px tall, search/sort/filter buttons 48px, "+" buttons 44px circles.
- LAYOUT ORDER (follows the mockup): header with the BTC live pill, Market Indicators tiles, Stocks cards, then the comparison chart, then the disclaimer. The chart itself is unchanged in data and behaviour.
- STOCKS CARDS: symbol, name (+ "+" button only where a pack note exists: MU, SPCX), large price, day-change pill, YTD (SPCX still labelled "Since listing 12 Jun 2026"), and a "Day move only" bar whose width is relative to the largest absolute day move among the visible cards — it shows only today's move size, never price history, and no history has been invented.
- BIGGEST-FALLER HIGHLIGHT: a card gets a red-tinted border when its day change is -5% or worse (the mockup's rule, applied to live values).
- INDICATOR TILES: symbol name + unit, large level, day change, and the "+" note button (all four indicators). No YTD on indicators, as before.
- SORT: the old table-header sorting is replaced by Day / YTD sort buttons above the stock cards (same sort logic, largest first on first click); search and All/Gainers/Losers filters are unchanged.
- CHART HIGHLIGHT ADAPTED, NOT REMOVED: clicking a stock card highlights the matching chart bar, and clicking a chart bar highlights the matching stock card — the code was updated from table rows (tr/td) to cards (data-symbol); a tap on a card's "+" note button is a note, not a chart highlight.
- UNCHANGED, ALL OF IT: pipeline merge (5-min refresh while open), live-clock split (stocks stock-hours, WTI/GOLD futures-hours, US10Y/VIX stock-hours, per-symbol <30 min freshness, honest status lines naming live vs dated rows, never labelling a dated close Live), BTC live pill opening the real BTC chart popover (Spot BTC only, 1D Line on open), "+" note pill texts word for word, gainer/loser pills, comparison chart (stocks-only, Day/YTD toggle), hidden leaf-only nature (no links or announcements added), pack v7 (?v=6, unchanged), btcchart.js pin (?v=et4, unchanged — btcchart.js itself was not touched). No new asset pin was needed: the new styling is inline in screener.html.
- Files changed in this push: screener.html, assets/js/screener.js, assets/js/screener-chart.js, proposals/screener-maple-leaf/INFO-PACKAGE.md only. No index.html, btcchart.js, tracker, or compare file was changed.

## 30 Oct 2026 — Gold YTD weekly candle chart: tap the gold tile (Sunil: "Make me a ytd, weekly candle chart for gold, when i click on the gold pill, in the maple leaf screener")

- WHAT IT DOES: tapping/clicking the GOLD Market Indicator tile itself opens a modal showing GOLD as WEEKLY candles for YTD only (1 Jan 2026 to the latest week). Tap a candle for its week (UTC Monday–Sunday) and open / high / low / close in a pill. Dismiss by the ✕ button, tapping outside the dialog, or Escape. iPhone-first: the modal is one column at 390px, canvas fills the dialog width.
- GOLD SERIES: COMEX gold futures (GC=F), $/troy oz — the screener's gold series, NOT spot. Weekly candles are UTC Monday–Sunday weeks (same bucketing as the BTC candle ranges); week labels are UTC. Candle colours match the site: green #22c55e, red #ef4444. YTD only in this first version; no other ranges were added.
- TILE vs "+" SPLIT: the tile's "+" button keeps its existing job (the note pill, exact pack text) and does NOT open the chart; the chart opens only from tapping the tile outside the "+" button. The box note now says so: "Tap the gold tile for its YTD weekly candle chart; tap its + for its note."
- DATA HONESTY — READ THIS: no static gold history was shipped, because no gold daily-OHLC series could be downloaded in the build environment (Yahoo's chart domain was blocked for the build tool). The modal therefore fetches Yahoo GC=F daily OHLC live in the visitor's browser (no key, same series the pipeline uses) and aggregates it to weekly candles in-page. If that live fetch fails, the modal says so plainly with a Retry button and shows NO chart — it never invents candles and never labels a failure as live. A future dated static file (assets/data/gold-weekly.json) would be tried as a fallback only; none exists yet, and no pipeline change was made in this job. CONSEQUENCE FOR REVIEW: the weekly aggregation code was verified headless (Monday–Sunday bucketing, pre-YTD days excluded, null closes skipped, no flat candle for empty input), but the live Yahoo fetch from a visitor's browser has NOT been proven in this environment and must be confirmed in live verification — if the browser fetch is blocked by CORS, the modal will show its error state instead of candles, and that is the honest failure to fix next (e.g. a pipeline-written weekly file).
- UNCHANGED: BTC pill/popover, clock split + honest status lines, "+" pills, search/filter/sort, comparison chart, hidden leaf-only nature, pack v7, btcchart.js?v=et4. screener.js itself was NOT changed — the tile click handling lives entirely in the new assets/js/screener-gold.js, which only listens for clicks on the gold tile.
- Files changed in this push: screener.html, assets/js/screener-gold.js (new), proposals/screener-maple-leaf/INFO-PACKAGE.md only.

## 30 Oct 2026 — Gold candles FIXED: data now shipped with the screener (Sunil: "Make sure the candle data is in the gold pill. Don't mess around with my bitcoin chart on the top")

- WHY: the gold modal as first shipped (main 9d6c5802) fetched Yahoo GC=F in the visitor's browser — and that fetch FAILED live on 30 Oct 2026 (verified 1:24–1:26 p.m. ET: load error, Retry also failed). So the chart could not draw at all. This fix ships the candle data with the screener instead of depending on a browser fetch.
- WHAT CHANGED: new file assets/data/gold-weekly.json (dated 30 Oct 2026) holds 44 YTD weekly candles, 209 trading days, 2 Jan–30 Oct 2026, Yahoo GC=F COMEX futures $/troy oz, UTC Monday–Sunday weeks. assets/js/screener-gold.js now reads that shipped file FIRST and draws from it with no browser fetch; the Yahoo browser fetch is kept only as a later fallback, never as the primary. The modal is labelled with its data date in two places — the gold-sub line ("Candles are shipped with this page, data as of 30 Oct 2026 — a dated snapshot, not a live quote") and the status line — so a static snapshot never pretends to be live. First week is partial (1 trading day, 2 Jan 2026, week starting Mon 29 Dec 2025) and is labelled as such in the status line and in the tap-a-candle pill; it was not dropped.
- RECONCILIATION ($0.10, same source, not invented): the 30 Oct daily close from the same Yahoo pull was $3,901.20, while the weekly list gave the final week's close as $3,901.10. The shipped file uses $3,901.20 for the final week (week of 26 Oct 2026: open $4,012.20, high $4,097.20, low $3,900.20, close $3,901.20). First week verified: open $4,340.00, high $4,414.80, low $4,319.70, close $4,329.60.
- VERIFIED HEADLESS: node --check passes; a stub-DOM harness fetched ONLY the shipped file (Yahoo never called), drew 44 candle bodies, and the first-candle pill showed "Week 29 Dec 2025 – 4 Jan 2026 (UTC, 1 trading day — partial week), Open $4,340.00 · High $4,414.80 · Low $4,319.70 · Close $4,329.60, Week change -0.24%".
- BITCOIN CHART ON TOP UNTOUCHED, per Sunil's instruction: index.html, btcchart.js, and every tracker/compare file were not changed (diff = 0). Only screener files changed in this push: assets/js/screener-gold.js, assets/data/gold-weekly.json (new), screener.html (gold-sub data-date line only), proposals/screener-maple-leaf/INFO-PACKAGE.md. Gold "+" still opens only its note; BTC pill popover (Spot only, 1D Line) unchanged.

## 30 Oct 2026 — Gold modal adjustments: blurbs behind "+", clean month x-axis, current-price line (Sunil: "There's two big blurbs. Top and bottom. Hide them with a +. Popup on a popup. The date labels on the x axis look messy make it look clean. Have a price line going hottest marked the current price, touching the X axis.")

- READING OF SUNIL'S WORDS (implemented as stated here so Sunil can correct it): "hottest" is read as the horizontal current-price line across the chart; "touching the X axis" is read as the line spanning the full chart width (the standard current-price line), not a vertical line. The modal title "Gold — YTD weekly candles" stays visible at all times.
- BLURBS HIDDEN BEHIND "+": the top description blurb and the bottom source/footer blurb are no longer always visible. Each is replaced by a small "+" button in the same pill style as the screener's "+" note pills (40px circle): top-right of the modal header area for the top blurb, bottom-right of the modal for the footer blurb. Tapping a "+" opens a small popup pill INSIDE the modal (popup on a popup) with that blurb's text word for word — top blurb: "COMEX gold futures (GC=F), $/troy oz. Weekly candles, UTC Monday–Sunday weeks, 1 Jan 2026 to the latest week. Candles are shipped with this page, data as of 30 Oct 2026 — a dated snapshot, not a live quote. Tap a candle for its week and open / high / low / close."; bottom blurb: the full source line set on load (Yahoo GC=F, shipped file, data as of 30 Oct 2026, 44 weekly candles, YTD, dated snapshot not live, first week partial). Dismissal: tap the pill again, tap elsewhere in the modal, the pill's ✕, or Escape (Escape dismisses the popup first, the modal second). The chart stays fully visible and clean with both blurbs hidden. Loading and error states are NOT blurbs and stay visible, never hidden behind a "+".
- CLEAN X-AXIS: weekly date labels are now one label per month only — the first candle of that month, labelled with the 3-letter month (Jan, Feb, Mar … Oct), no rotation, no stacking. The month is taken from the week's Thursday (Monday + 3 days), which puts the partial first week (Mon 29 Dec 2025, trading day 2 Jan) under Jan, not Dec. All 44 candles still draw; only label density changed. Tapping a candle still shows its full week + O/H/L/C pill, unchanged.
- CURRENT-PRICE LINE: a horizontal dashed cyan (#22d3ee) line spans the full chart width at the latest weekly close, read from the shipped gold-weekly.json (not hardcoded): latest week of 26 Oct 2026, close $3,901.20, labelled "Current $3,901.20" at the line's right end on a cyan label. Cyan stands out against the green/red candles without obscuring them.
- VERIFIED HEADLESS: node --check passes on screener-gold.js; a stub-DOM harness (shipped file only, no browser fetch) passed 17 checks: both blurbs hidden by default, each "+" opens a popup with the exact original text, chart still draws 44 candles, x-axis shows exactly 10 month labels Jan–Oct with no duplicates, dashed current-price line present at $3,901.20 with its label, candle-tap pill unchanged, tap-elsewhere and Escape dismissal of the info popup, gold "+" note still note-only.
- BITCOIN CHART ON TOP UNTOUCHED: index.html, btcchart.js, and every tracker/compare file were not changed in this push. Only screener gold files changed: assets/js/screener-gold.js, screener.html (modal "+" buttons, info pill, footer row), proposals/screener-maple-leaf/INFO-PACKAGE.md. The shipped assets/data/gold-weekly.json data itself did NOT change.
