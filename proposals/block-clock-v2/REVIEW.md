# Block clock V2 — REVIEW

Branch: `pepper-block-clock-v2` · Base: main `dd71e0d` (includes the OI-001
label fix, live 6 Nov 2026 morning) · Builds on item 5 (block clock V1).

## What this is

The clock page now hosts **the whole BTC popover chart, inline, full size** —
not a smaller version of it. Same file (`assets/js/btcchart.js`), same data,
same ranges, same candles, same S&P 500 / Gold / MSTR compare lines. Plus a
hash rate chart, and a tap on the hero price scrolls to the chart.

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
- `clock/index.html` — loads `nav.css` (the popover's own styles) +
  `et.js?v=et2` + `btcchart.js?v=et7`; adds the `#bcInline` chart section
  with `.bc-inline` overrides (dialog → page section, ✕ hidden); adds the
  hash rate section; tap on the hero price scrolls to the chart.
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
- Pins: `btcchart.js` et6→et7 on index/screener, et2→et3 on
  compare/custom/recap. OI-001 pins preserved (s2.js p4, compare.js et2).

## Deliberately NOT done

- No "Open in popover" button on the clock page — the chart is here now,
  there is nothing to jump out to.
- No `#btc-chart` auto-open on index.html — nothing links to the popover
  from the clock page any more.
- No candle extension: in the popover, candles are offered for 1W–1Y and
  5Y/10Y/Max are line-only. V2 inherits that exactly. Ranges 1Y/5Y/10Y/Max
  all work as lines with compare toggles.

## Merge notes (for Grok Bot)

- Apply the `btcchart.js` inline patch on top of the **final merged**
  `btcchart.js` after items 1/4/5/8 land today — the patch is small and
  applies to any `btcchart.js` that still has `build()`/`open()`/`close()`/
  `place()`. Do not merge the V1-era copy over a newer one.
- The clock page's `#bcInline` section and hash chart are self-contained in
  `clock/index.html`; they do not touch any other page.

## Check list

1. `/clock/` loads: price, sparkline, rotating panes, chart draws inline
   (1D line by default).
2. Chart ranges: 1D, 1W, 1M, 3M, 6M, YTD, 1Y, 5Y, 10Y, Max all draw; Log
   scale appears on 5Y/10Y/Max.
3. Candles: switch to Candles on 1W/1M/3M/6M/YTD/1Y (Daily/Weekly/Monthly
   sizes); tap a candle — the pill shows O/H/L/C.
4. Compare: + S&P 500, + Gold, + MSTR toggle lines on/off on a line range.
5. Hash rate: 1W/1M/3M/1Y/5Y/Max switch; current hashrate reads ~1 ZH/s;
   Log toggle makes the Max view readable (linear Max is flat until ~2020).
6. Branding: the top shows the homepage logo lockup exactly — owl (40px,
   radius 8) + "Paperstreet BTC" with BTC in cyan + a muted "· Clock".
6. Tap the hero price — page scrolls to the chart.
7. Regression: homepage BTC pill popover still opens, draws, and closes
   normally; screener popover unchanged.
8. Phone width (390px): chart section readable, range pills scroll, no
   horizontal overflow.
