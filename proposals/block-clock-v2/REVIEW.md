# Block clock V2 — REVIEW

Branch: `pepper-block-clock-v2` · Base: main `dd71e0d` (includes the OI-001
label fix, live 6 Nov 2026 morning) · Builds on item 5 (block clock V1).

## What this is

The clock page now hosts **the whole BTC popover chart, inline, full size** —
not a smaller version of it. Same file (`assets/js/btcchart.js`), same data,
same ranges, same candles, same S&P 500 / Gold / MSTR compare lines. Plus a
hash rate chart.

**Merged, 6 Nov (Sunil's pick):** the price and the chart are one clean card.
The big hero price IS the chart header — the chart lives inside the hero,
the 24h sparkline is gone (the 1D chart already shows the same 24h in full
detail), and the chart's duplicate price line hides. One price, one chart.

**USD / CAD toggle, 6 Nov:** a USD $ / CAD $ switch in the hero re-prices
BTC in Canadian dollars — hero price, 24h % (CoinGecko's CAD change),
sats per dollar, the sats tile, the ticker, and the chart (axis labels,
candle pill, tooltips, range summary, title). The chart converts at the
live USD→CAD rate; historical CAD values use today's rate, so they are
approximate — the page says so. Choice is remembered (localStorage).

## Changes

- `assets/js/btcchart.js` — inline mode. Only activates when the page has a
  `#bcInline` host element. On such a page the script mounts the chart
  (build + show + load + draw) on page load instead of opening it as a
  dialog. Guards added: the `#hdrTick` early return now also allows a
  `#bcInline` host; `open()`/`close()`/`place()` return immediately in
  inline mode; the Tab-trap/Escape keydown handler is skipped inline; the
  secret double-click (clock from the clock) is skipped inline; the header
  pill click listener is guarded. **When no `#bcInline` exists, every
  popover path is exactly as before** — the homepage/screener popover is
  untouched.
- `assets/js/btcchart.js` — CAD display hook (clock page only). The clock
  page sets `window.BC_CUR={code,rate}` before this script loads and calls
  `window.BC_setCurrency(code,rate)` on toggle. One central formatter
  (`fmt`) converts every displayed $ value at the live rate, plus the
  candle y-axis labels, the Chart.js y ticks, the candle detail pill, the
  Gold/MSTR tooltip values, and the chart title (`BTC/USD` → `BTC/CAD`);
  range summaries gain a `· CAD` marker. The series stays USD internally,
  so the shape never changes. **The popover never sets BC_CUR, so USD
  output is identical to before.**
- `clock/index.html` — loads `nav.css` (the popover's own styles) +
  `et.js?v=et2` + `btcchart.js?v=et8`; the `#bcInline` host now sits inside
  the hero (merged card) with `.hero.merged` overrides (chart card chrome
  stripped, `.bc-px` hidden); the sparkline canvas, its footer row, and
  the price-tap-to-scroll are removed; adds the hash rate section; adds the
  USD/CAD toggle in the hero (CoinGecko now fetched with `usd,cad` +
  24h changes for both; Coinbase fallback is USD-only, so the CAD button
  disables while no CAD price has ever loaded; last-good CAD values are
  kept across a failed fetch). The chart always starts in USD, even for a
  returning CAD user — the CAD rate is not known until the first fetch
  lands, and starting the chart in CAD with rate 1 would label USD values
  as C$ for the first minute while the hero (correctly) stays USD;
  `applyCurrency()` flips chart + hero to CAD together once the rate
  arrives.
- Hash rate chart — `mempool.space /api/v1/mining/hashrate/{1w,1m,3m}`,
  daily buckets, live fetch, 60s refresh, last-good values on failure (same
  rule as the rest of the page). Current hashrate shown big (≥1000 EH/s as
  ZH/s; observed ~1.03 ZH/s on 6 Nov). 3d was tried and dropped — 3 daily
  points is not a chart. Ranges: 1W/1M/3M/1Y/5Y/Max. 1y is daily buckets
  (365 points); 5y and all both return the full history (daily, back to
  2009-01-03), so 5Y is the same fetch sliced to the last 5 years and Max
  is the whole thing (6,517 points). A Log toggle sits next to the ranges:
  hashrate grew from ~0 to 1,000+ EH/s, so the Max view is a flat line on a
  linear scale — Log (floor: smallest positive value) makes the growth
  readable. Default is linear.
- Branding (6 Nov): the clock is branded as the PaperStreetBtc clock. The
  brand lockup matches the homepage header exactly (styles.css
  .brand/.logo/.brand-text): owl 40px, radius 8, "Paperstreet BTC" in
  Outfit 600 (self-hosted woff2), BTC in accent cyan #22d3ee, plus a muted
  "· Clock" descriptor. The first version (gradient pill, circular 18px
  owl, all-caps "PAPERSTREETBTC CLOCK") did not match the homepage and was
  replaced. Page title: "PaperStreetBtc Clock — Bitcoin Block Clock".
- Fees tile (6 Nov): fees were only in the rotating Network screen, visible
  ~1/4 of the time. A third tile in the grid now shows them always: fastest
  fee in sat/vB (big) + the unconfirmed transaction count (small), same
  mempool.space feed as the Network screen, updated on the same 60s cycle.
  No new fetch — it reuses the existing fees + mempool calls.
- Pins: `btcchart.js` et7→et8 on index/screener/clock, et3→et4 on
  compare/custom/recap. OI-001 pins preserved (s2.js p4, compare.js et2).

## Deliberately NOT done

- No "Open in popover" button on the clock page — the chart is here now,
  there is nothing to jump out to.
- No `#btc-chart` auto-open on index.html — nothing links to the popover
  from the clock page any more.
- No candle extension: in the popover, candles are offered for 1W–1Y and
  5Y/10Y/Max are line-only. V2 inherits that exactly. Ranges 1Y/5Y/10Y/Max
  all work as lines with compare toggles.
- CAD is clock-page only: the homepage/screener/compare popover stays USD.
  No CAD history is fetched — the chart converts USD values at the live
  rate, so historical CAD values are approximate by design.

## Merge notes (for Grok Bot)

- Apply the `btcchart.js` inline patch **and the CAD hook** on top of the
  **final merged** `btcchart.js` after items 1/4/5/8 land today — both are
  small and apply to any `btcchart.js` that still has `build()`/`open()`/
  `close()`/`place()` and a single `fmt`. Do not merge the V1-era copy
  over a newer one.
- The clock page's merged hero, hash chart, and CAD toggle are
  self-contained in `clock/index.html`; they do not touch any other page.

## Check list

1. `/clock/` loads: price, rotating panes, chart draws inline inside the
   hero (1D line by default). No sparkline, no separate chart section.
2. Chart ranges: 1D, 1W, 1M, 3M, 6M, YTD, 1Y, 5Y, 10Y, Max all draw; Log
   scale appears on 5Y/10Y/Max.
3. Candles: switch to Candles on 1W/1M/3M/6M/YTD/1Y (Daily/Weekly/Monthly
   sizes); tap a candle — the pill shows O/H/L/C.
4. Compare: + S&P 500, + Gold, + MSTR toggle lines on/off on a line range.
5. Hash rate: 1W/1M/3M/1Y/5Y/Max switch; current hashrate reads ~1 ZH/s;
   Log toggle makes the Max view readable (linear Max is flat until ~2020).
6. Branding: the top shows the homepage logo lockup exactly — owl (40px,
   radius 8) + "Paperstreet BTC" with BTC in cyan + a muted "· Clock".
7. CAD toggle: tap CAD — hero price, 24h %, sats, ticker, and chart all
   show C$ (axis labels, pill, title `BTC/CAD`, range summary `· CAD`);
   tap USD — everything back to $. Choice survives a reload. While the
   CAD price has never loaded, the CAD button is disabled and its tooltip
   says so ("CAD price loading — waiting on CoinGecko…").
8. Regression: homepage BTC pill popover still opens, draws, and closes
   normally, in USD; screener popover unchanged.
9. Phone width (390px): merged hero readable, range pills scroll, no
   horizontal overflow.
