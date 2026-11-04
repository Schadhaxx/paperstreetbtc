# BTC popover: 4-hour candles on 1W — test branch, for Saturday review

Built 4 Nov 2026 at Sunil's request, from his screenshot of the
1W daily-candle popover ("Add 4 hour candles to this toggle
option"). Test branch only, NOT live.

## What changes (btcchart.js only, + pin bumps)
- The range chart toggle (Chart: Line / Candles) gains a **4H**
  size button on **1W only**, next to Daily. 1W default stays
  Daily; the first-visit rule and the Line↔Candles preservation
  from the existing granularity code are unchanged, so picking
  4H sticks across Line↔Candles switches, and switching range
  tabs resets other ranges to their own defaults (4H is not
  offered on any other range, so it can never leak into 1M/3M/
  YTD/1Y).
- 4H data: Coinbase 4-hour bars, last 7 days (42 bars, under
  Coinbase's 300-bar request limit), granularity=14400, same
  candle-array shape as the daily fetch. Cache 5 minutes; a
  failed fetch is sticky for the session and falls back once
  to the line with "Coinbase 4-hour candles unavailable —
  showing daily closes", the same pattern as the YTD extended
  fetch. The 4H view does NOT depend on the daily-candle
  fetch: its branch runs before the daily window computation.
- Labels: chart title "1W · 4-hour candles", header "N
  4-hour candles, from <date>", note "Coinbase 4-hour
  candles (UTC), in 4-hour blocks… Last candle is the latest
  complete 4-hour block; today's live price is not a candle."
  Tapping a 4H candle shows its pill as "4-hour candle ·
  <date> <start> – <end> UTC" (UTC, like the other range
  candles — not ET, which shifted UTC-midnight candles a day
  in the old bug). X-axis stays date-only (month + day),
  evenly spaced, first and last included.
- Pins: btcchart et6 on index/screener, et2 on
  compare/custom/recap (same pin names as the screener-fix
  and pill-expand branches — they are cache-busters per
  branch, Grok resolves them on merge).

## What it does NOT do
- 1M 4-hour candles (31 days × 6 = 186 bars, also under the
  limit) are NOT included — Sunil's screenshot was 1W, so
  this is 1W only. Say the word and 1M follows the same
  pattern.
- 1D already had 1H/4H (Coinbase 15-min candles, last 24h);
  this does not touch 1D.
- No S&P 500 / Gold / MSTR in candle view, same rule as
  every other candle view (BTC-only).

## Saturday checks
- Browser: open the popover, 1W, Candles, tap 4H — expect
  ~42 candles, header/note as above, tap a candle for its
  4-hour pill; tap Daily to return to 7 daily candles.
- Phone width: the extra 4H button in the size row.
- Merge note: this branch touches btcchart.js only. It
  overlaps the screener-fix, pill-expand, and block-clock
  branches in that file (all three touch different regions);
  Grok merges, as with the other Saturday items. It is NOT
  the combined preview — that play copy carries the same
  4H code on top of everything else.

## Fix 4 Nov (same day): Coinbase has no 4h granularity
First browser check FAILED on the fetch: Coinbase returns
HTTP 400 "Unsupported granularity" for granularity=14400.
Its valid values are only 60/300/900/3600/21600/86400.
Fix: fetch 1h bars (8 days, 192 bars, under the 300-bar
limit) and aggregate them in code into UTC-aligned 4h
buckets (`agg4hFromHourly`, harness-verified: 50 hourly
bars → 12 complete buckets, partial bucket dropped,
O/H/L/C correct), keeping only complete buckets, last 42
(= 7 days). Size order also changed per Sunil: 4H first,
then Daily (finest first, matching Daily/Weekly/Monthly).
Failure hygiene: a failed 4h fetch now resets the size
to Daily and clears candle state before falling back, so
the toggle/pill can never claim 4h while showing something
else.
