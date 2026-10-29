# Candle Ranges — Day 1 Report (test branch only, NOT live)

Branch: `pepper-candle-ranges-day1`, from main head `8fd696f3` (vehicle toggle deploy).
Date: 29 Oct 2026. No main change, no deploy, no pipeline change, no message to
Grok Bot / Chief of Staff / Site Launch. 1D (Line / 1H / 4H + pill) is unchanged.

## 1. Data-route recommendation: in-page Coinbase daily fetch + in-page aggregation

RECOMMENDED: route (a) — fetch Coinbase BTC-USD daily candles in the browser and
aggregate them in-page, exactly as the standalone playground does.

Why, honestly:
- The live site ALREADY does this fetch. `getData()` in `btcchart.js` fetches
  `api.exchange.coinbase.com/products/BTC-USD/candles?granularity=86400` on every
  popover open, then throws away everything except the close (`c[4]`). Day 1
  simply keeps the OHLC it already downloads (`CBDAILY`: time, open `c[3]`,
  high `c[2]`, low `c[1]`, close `c[4]`, sorted oldest-first). No new vendor,
  no new request for 1W/1M, no pipeline work.
- 1W (7 days) and 1M (31 days) are far under Coinbase's 300-candle default
  window, so no batching is needed for this build.
- Weekends are included: Coinbase daily candles cover every UTC day, matching
  the site's existing daily-close series (which already extends weekends from
  Coinbase).
- A static OHLC backfill (route b) would need a new pipeline job, a new data
  file to maintain, and a staleness story — real cost for no Day 1 benefit.
  It becomes worth revisiting only if a later range needs data Coinbase cannot
  serve in-page (see §5).

Trade-offs and limits of the recommended route (stated, not hidden):
- If the Coinbase fetch fails, there is NO candle view: Day 1 falls back to the
  existing daily-closes line with a note saying so. OHLC is never reconstructed
  from closes — a close-only series cannot yield a real high or low.
- The last candle is the latest COMPLETE UTC day. Today's live price is NOT
  appended as a partial candle (it would misstate open/high/low); the note
  under the chart says this.
- 1Y needs 366 days > the 300-candle default window, so 1Y will need batched
  start/end requests (two windows) or a line fallback for the oldest ~66 days.
  That is a Day 2+ problem, not solved here. 3M/6M/YTD are all under 300 days
  for the candle count itself, but monthly/weekly aggregation still needs the
  full daily window — fine within 300 for 3M (92) and 6M (~183) and YTD, not
  for 1Y.
- Coinbase daily candles are UTC days. The site's daily closes are also UTC
  days, so this is consistent — but it is NOT the same as the NYSE-session
  series in history.json, and candle values will differ slightly from any
  session-based figure. That is expected, not an error.

## 2. What was built (Day 1)

In `assets/js/btcchart.js` only (no CSS change — the new row reuses the
existing `.bc-ct` pill-button row styling):
- A "Chart: Line | Candles" control in the BTC chart popover, shown on 1W and
  1M only. Default is Line, so the existing line view is unchanged unless the
  visitor opts into candles — the same opt-in pattern as the 1D Line default.
- 1W candles: daily candles (no choice, per spec).
- 1M candles: "Weekly | Daily" granularity buttons, default Weekly (matching
  the playground's first-listed choice). Switching range resets granularity to
  that range's default (1W → daily, 1M → weekly).
- Canvas candle drawing reusing the live 1D candle code's geometry, colours
  (green #22c55e / red #ef4444), white-outline selection, dashed hover guide,
  and the true pill (High / Low / Change, three lines, tap pill / ✕ / candle
  again to dismiss). The shared listeners and pill dismiss now redraw whichever
  candle view is active (1D or range) via a `redrawCandles()` dispatch.
- Pill title for range candles: "Weekly candle · Oct 19 – Oct 25 ET" or
  "Daily candle · Oct 26 ET" (ET is display only).
- Candles are BTC-only: S&P 500 / Gold / MSTR buttons are greyed in candle
  view, exactly as the 1D rule already does. Their line behaviour is untouched.
- Fallbacks: no Coinbase daily data, or fewer than 2 candles in window, falls
  back to the daily-closes line with a note appended, and the Chart control
  stays visible so the visitor can switch back to Line.

## 3. A decision the test caught: weekly buckets are UTC Monday–Sunday

The first version bucketed by ET weekdays. The headless test caught that this
splits weeks wrongly: a UTC Monday candle is still Sunday evening in ET, so it
landed in the previous ET week (3 buckets where 2 were expected). Fixed to UTC
Monday–Sunday buckets, because the daily candles are UTC days. ET appears only
in displayed dates (popover labels). The playground's epoch-week bucketing (Thursday start) was
NOT carried over.

## 4. Verification

- `node --check assets/js/btcchart.js` — passes.
- `proposals/candle-ranges-day1/test-agg.js` — extracts `aggDailyCandles`
  from the shipped `btcchart.js` (not a transcription) and runs 14 checks:
  daily identity, weekly open = first day open, close = last day close,
  high = max of day highs, low = min of day lows, partial-week handling,
  ordering, empty input, single day, unknown mode. ALL 14 PASS.
- NOT verified (needs a browser, which this subagent cannot operate): the
  painted popover — Chart/Candles control placement, tap-a-candle pill on
  phone width, switching Line ↔ Candles ↔ Weekly ↔ Daily without a stale
  canvas, and the Coinbase-failure fallback path. The parent should browser-
  verify on the test-branch preview before this is called done. No browser
  pass is claimed here.

## 5. What was NOT built, and next steps

- 3M, 6M, YTD, 1Y candle views: NOT built. Next step is the same pattern —
  add monthly aggregation (calendar-month buckets, UTC) and the monthly/
  weekly granularity choice per range, reusing `drawCandlesRange`.
- 1Y batching: needs the two-window Coinbase fetch (or a line fallback for
  the oldest days) — decide when 1Y is built, with the trade-off in §1.
- SMA 20 / EMA 20 / Bollinger Bands (20, 2σ): EXPLORATION ONLY, not built.
  The playground already prototypes them on displayed candle closes; porting
  them to the popover is a later step, and the "20 = 20 candles of whatever
  granularity is shown" caveat must travel with them.
- 5Y, 10Y, Max: LEFT OUT per the confirmed spec. 1D unchanged.
- No deploy is authorised by this report. Deploy still needs Sunil's final
  approval, after browser verification and Grok Bot + Chief of Staff review.
