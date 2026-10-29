# Candle Ranges — Day 2 Report (test branch only, NOT live)

Branch: `pepper-candle-ranges-day1` (same branch as Day 1), from main head
`8fd696f3` (vehicle toggle deploy). Day 1 head: `fbc503f8`.
Date: 29 Oct 2026. No main change, no deploy, no pipeline change, no message
to Grok Bot / Chief of Staff / Site Launch. 1D (Line / 1H / 4H + pill) is
unchanged. SMA/EMA/Bollinger are NOT built in Day 2 (exploration only).

## 1. What was built (Day 2)

In `assets/js/btcchart.js` only (plus this report and the Day 2 harness):

- **3M = Monthly | Weekly candles; 6M = same format as 3M.** 6M default
  Monthly, 3M default Monthly (the first-listed choice in the confirmed spec).
- **YTD = Monthly | Weekly candles; 1Y = same format as YTD**, both
  default Monthly.
- **Monthly aggregation = calendar months in UTC**: a monthly candle's open
  is its first day's open, close is its last day's close, high is the max of
  its days' highs, low is the min of its days' lows. Partial months at the
  window edges stay partial — never padded or invented. Monthly buckets are
  UTC, like Day 1's weekly buckets: Oct 1 00:00 UTC starts the October
  bucket even though it is still Sep 30 evening in ET.
- **Same control pattern as Day 1**: the "Chart: Line | Candles" control now
  appears on 1W, 1M, 3M, 6M, YTD, and 1Y, default Line, so every existing
  line view is unchanged unless the visitor opts into candles. The "Size"
  row shows Monthly | Weekly | Daily buttons, but only the choices that
  exist for the current range are shown: 1W shows none (daily only),
  1M shows Weekly | Daily, 3M/6M/YTD/1Y show Monthly | Weekly.
- **Same pill, same grey-out**: tapping a range candle shows the true pill
  (High / Low / Change; monthly pills read "Monthly candle · Oct 2026 ET").
  SPX/Gold/MSTR buttons grey out in candle view, exactly as Day 1. The pill
  dismiss path was fixed for the new ranges: Day 1's dismiss check only
  redrew for 1W/1M, which would have left a stale selection outline on
  3M/6M/YTD/1Y — it now uses the shared candle-range list.
- **6M tab added to the popover**: the popover's range row previously had
  no 6M button (1D, 1W, 1M, 3M, YTD, 1Y, 5Y, 10Y, Max), so 6M candles would
  have had nowhere to live. Day 2 adds the 6M button between 3M and YTD,
  with a 183-day line window — so 6M now has a line view too, as a natural
  consequence (the Compare chart already had 6M). This is the one Day 2
  change outside `btcchart.js`'s candle code, and it is deliberate, not a
  scope slip: without it, "6M = same format as 3M" could not be viewed.

## 2. The 1Y data decision — batched requests, implemented

DECIDED AND BUILT: batched requests (two windows, deduped, ordered).
1Y needs 366 days vs Coinbase's ~300-candle default window, so a single
no-window fetch cannot cover it — and the same problem applies to YTD late
in the year (Jan 1 to late Oct is already ~302 days, growing to 365 by
December), even though Day 1's report assumed YTD was under 300. Day 2
therefore uses the batched route for BOTH YTD and 1Y:

- Windows of at most 250 days each, with explicit start/end parameters:
  1Y = [now−366d, now−116d] + [now−116d, now]; YTD = the same chunking over
  [Jan 1, now]. Each window is well under the 300-candle limit.
- Merge is a pure function, `mergeDailyCandles(chunks)`: dedupe by
  timestamp (a later window wins on a shared boundary day), sort
  oldest-first. It is extracted specifically so the headless harness can
  check it without fetching anything.
- Honest failure rule: if ANY window fails, the whole extended fetch fails
  and the view falls back to the daily-closes line with a note. The oldest
  days are NEVER silently dropped and candles are NEVER faked from closes.
  The failure flag is sticky for the session so a failed fetch is not
  hammered on every redraw; the visitor can still use the line view.
- Loading state: while the batched fetch is in flight the header reads
  "Loading year-to-date candles…" / "Loading 1-year candles…" and the view
  redraws automatically when it resolves (same pattern as the 1D intraday
  loading path). 3M/6M still use the single no-window Coinbase fetch
  (`CBDAILY`, 92 and 183 days — safely under 300), so no extra requests
  are added for those ranges.
- The line fallback for the oldest days was NOT used: batching works
  cleanly in-page with the same vendor and no pipeline change, so there is
  no reason to drop the oldest ~66 days of 1Y.

## 3. Verification

- `node --check assets/js/btcchart.js` — passes.
- `proposals/candle-ranges-day1/test-agg.js` — Day 1 harness, still
  ALL 14 PASS (daily identity, weekly buckets, edge cases).
- `proposals/candle-ranges-day2/test-agg-day2.js` — NEW, extracts
  `aggDailyCandles` and `mergeDailyCandles` from the shipped file (not
  transcriptions) and runs 21 checks, ALL PASS: monthly 2-bucket
  open/close/high/low, partial-month handling, UTC month boundary,
  weekly over a 3-week window, batched merge dedup (later window wins on
  the boundary day) and oldest-first sorting, out-of-order input, empty
  inputs, daily-identity regression.
- NOT verified (needs a browser, which this subagent cannot operate): the
  painted popover — 6M tab placement, Monthly | Weekly switching on
  3M/6M/YTD/1Y, the batched-fetch loading state and failure fallback, the
  monthly pill at phone width, and 1D/1W/1M regression. The parent should
  browser-verify on the test-branch preview before this is called done.
  No browser pass is claimed here.

## 4. What was NOT built, and what remains

- SMA 20 / EMA 20 / Bollinger Bands (20, 2σ): EXPLORATION ONLY, not built
  in Day 2 — the range work did not finish with spare scope for a careful
  port, and the playground prototype already covers them on displayed
  candle closes. If ported later, they stay separate toggles on displayed
  candle closes only, with the "20 = 20 candles of whatever granularity is
  shown" caveat travelling with them.
- 5Y, 10Y, Max: LEFT OUT per the confirmed spec. 1D unchanged.
- Remaining before any deploy: browser verification of this commit (see
  §3), then Grok Bot + Chief of Staff review, then Sunil's final deploy
  approval. No deploy is authorised by this report.
