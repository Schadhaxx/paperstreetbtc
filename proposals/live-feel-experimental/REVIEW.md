# Live feel for candle charts — EXPERIMENTAL, test branch only

Branch: `pepper-live-feel-exp` (base: main `03dc9cc`).
Status: EXPERIMENTAL. Not for deploy without Grok Bot + Chief of Staff
review and Sunil's separate yes. Nothing here is live; nothing on
paperstreetbtc.com changes from this branch.

## What it is

The live-feel set from the 4 Nov mockups, built for real on two surfaces:

1. Screener weekly candle modal (`assets/js/screener-indicator-chart.js`,
   + a small event addition in `assets/js/screener.js`, + modal markup in
   `screener.html`, module pin `stocks2` -> `stocks3`).
2. Homepage BTC popover range candles (`assets/js/btcchart.js`,
   pins `et5` -> `et6` on index/screener, `et1` -> `et2` on
   compare/custom/recap).

Both surfaces are marked EXPERIMENTAL in the UI itself: an orange
EXPERIMENTAL chip sits in the screener modal header and in the popover
header, and both status/note lines start with "Experimental live feel".

## Features (both surfaces, unless noted)

- Live price line: dashed cyan line at the live price with a LIVE tag.
  Screener: tag at the right end; shipped-close line is unchanged when
  not live. Popover: tag at the right end of range candle views.
- Live last candle (display only, never written back):
  - Screener: ONLY when the shipped file marks its last week in
    progress (data `inProgress`, or the WTI `lastInProgress` label).
    Its close follows the live price; high/low extend to it.
  - Popover: ONLY for daily/weekly/monthly range buckets that contain
    today. Close follows the live CoinGecko price; high/low extend.
- Tick flash: the price label flashes green on an up-tick, red on a
  down-tick, then settles (screener modal live price; popover `bcPx`).
- Countdown: screener status line counts to the week close (Sunday
  midnight UTC for indicators, Friday 4 p.m. ET for stocks); popover
  note counts to the bucket close (midnight UTC / Monday / month 1st).
- Draw-in: screener candles grow in over ~450ms on open, fresh load,
  and the moment the chart goes live; popover range candles fade in on
  a new set (1D candles already faded). `prefers-reduced-motion` draws
  instantly, with no pulse, on both surfaces.
- Pulse: screener only — a pulsing dot + LIVE tag on the live candle,
  redrawn on a 700ms tick while the modal is open and live. The popover
  deliberately has NO 1Hz canvas pulse: its candle redraw rebinds
  listeners, so the popover pulse is the 60-second tick flash + LIVE
  tag instead.
- New-week / new-day rollover: NOT fabricated. If a week rolls over
  while the modal is open, no candle is invented (its Monday open is
  unknown to the browser); the status line keeps counting to the next
  close and the live line keeps tracking the price. The first real
  candle arrives with the next weekly file.

## Live rules (the honesty gates — do not weaken these in review)

- Screener live state comes ONLY from the tile row's `_src` verdict in
  `screener.js` (fresh quote < 30 min AND market hours: stock hours for
  stocks/US10Y/VIX, Globex hours for GOLD/WTI). A stale or out-of-hours
  quote keeps the shipped close line and a "Market closed" status.
  The modal never fetches Yahoo itself (that fallback failed live
  30 Oct 2026 and was dropped); it reuses the 5-minute `prices.json`
  refresh `screener.js` already runs, via a new `screener-ind-rows`
  event (the old `screener-rows` event carries stock rows only).
- Popover live state comes ONLY from the existing CoinGecko 60-second
  poll (`live.usd`), which the 1D line and range line views already
  used. BTC trades weekends, so the popover can be live at any hour
  the feed is fresh; a failed feed leaves the shipped candles alone.
- Shipped weeks are NEVER mutated: the screener builds a display copy
  (`displayWeeks()`); the popover builds a display copy per draw.
  No price is ever invented between real updates.
- This branch deliberately revises one old rule, narrowly: the module
  header used to say the dashed line is "never the live card price".
  That is still true for every final week. The line moves ONLY for a
  live, in-progress week, and the status line says so.

## Deliberately unchanged

- Default charts, shipped weekly files, pipeline, prices job: untouched.
- 1D candle views (1H/4H complete buckets) and the 1W 4H view: unchanged
  (their buckets are complete-only by Saturday design).
- Compare page, sleeve candles, enhancement toggles: untouched (this
  branch is based on main, not on the enhancements branch).
- `compare.js`: untouched.

## Verification so far

- `node --check` passes on all three changed JS files.
- Headless harness (`window.IndicatorChart` helpers): live-week
  up/down extension, original week unmutated, next-close targets
  (Monday 00:00 UTC / Friday 21:00 UTC, both future), countdown shape.
- Browser check on the test branch (githack, read-only): PENDING at
  push time — see the Sunday checklist below. Note: a night/weekend
  check will correctly show the screener in "Market closed" state;
  the screener LIVE state can only be observed in market hours.

## Sunday checklist for Grok Bot + Chief of Staff

1. In market hours, open the test-branch screener, tap GOLD (Globex)
   and a stock tile: live line + LIVE tag + pulse appear; price label
   flashes on the 5-minute refresh; status counts to the week close.
2. Out of hours / weekend: same tiles show "Market closed" and the
   shipped close line — never a pulsing stale price.
3. Popover (any hour the feed is fresh): open 1W Candles and 1M
   Candles — last candle carries the live price, dashed outline, LIVE
   tag + line; note counts to the bucket close; price flashes on ticks.
4. Phone width (390px): modal + popover, tags not colliding with
   high/low labels; reduced-motion: instant draw, no pulse.
5. Confirm or change: should the live feel be always-on (as built) or
   behind a toggle? Should the screener pulse stay at 700ms?

## Merge notes

- Module pin `stocks3` collides with the enhancements branch's
  `stocks4` and the current-week branch's data pins — same file,
  different changes; Grok merges by hand, one item at a time.
- `btcchart` pins `et6`/`et2` collide with the screener-fix,
  pill-expand, and block-clock branches (different regions of the
  same file); the 4H branch's `et7`/`et3` sit on top of this file's
  later state — merge order matters, do not take pins at face value.
- `screener.js` change is additive (one extra event dispatch); it
  does not change any tile behaviour.

## Rollback

Delete the branch. No main commit, no data change, no live change to
undo. To remove the feature from a merged tree, revert the three JS
files + the `screener.html` modal markup + the pins.

## Fixes, 6 November 2026 (branch pepper-live-feel-fixes)

Sunil accelerated this to go live Fri 6 Nov (was Sunday 8 Nov). The three
open niggles from the 5 Nov market-hours check are fixed, screener modal
only — the BTC popover is untouched.

1. **Week-close countdown in the live state.** Root cause, two bugs:
   `loadData()` called `refreshLive()` while `state.loading` was still
   true, so `refreshLiveStatus()` returned early and never set the live
   status; then `setStatus('Tap a candle for its week.')` clobbered
   whatever was there. Fix: clear `loading` before `refreshLive()` and
   drop the clobbering `setStatus` (the tap instruction now rides in
   the status line itself, and in `#ind-sub` for stocks). The countdown
   also ticks: the 700ms pulse refreshes the status line every 30s, so
   it counts down between 5-minute feed refreshes instead of freezing.
   Status now reads, e.g.: "Experimental live feel — LIVE · Week closes
   in 6d 22h 15m (Friday 4 p.m. ET) · Tap a candle for its week."
2. **In-progress last candle partly clipped.** The chart's right margin
   was 8px; the live candle's dashed outline extends 5px past the body,
   so it ran to the canvas edge and read as clipped (confirmed by pixel
   scan: drawn content at x=319 of a 320px canvas). Fix: `padR` 8 → 24,
   so the last candle and its outline sit ~20px clear of the edge.
   Also fixed while there: the live candle's pulsing dot was drawn at
   the candle centre, on top of the "LIVE" text (covering the V). The
   dot now sits left of the text (dot, gap, text — centred on the
   candle) so the tag reads cleanly.
3. **Tap on last candle gave no detail.** The tap hit-test ends at the
   last slot (`cssW - padR`); the live outline extends past it, so a
   tap on the outline or right margin computed idx == n and was dropped
   silently (reproduced: centre/body taps worked, outline-right and
   margin taps gave nothing). Fix: a tap inside the canvas just past
   the last slot now selects the last candle. The left (y-axis) edge is
   not clamped — tapping axis labels still selects nothing.

Merge: branch `pepper-live-feel-fixes` is the live-feel branch merged
onto main `a4a0a76f`. `btcchart.js` keeps main's V2 inline mode + CAD
display and adds live-feel's tick flash, live-bucket extension and
EXPERIMENTAL chip (also in `BC_setCurrency`, so a currency toggle does
not drop the chip). `screener-indicator-chart.js` keeps main's
enhancements (Bollinger, high/low lines, volume pane, drawdown,
patterns, zoom) and adds live-feel on top via a display copy of the
shown weeks (last week live-extended); draw-in kept; tap pill shows the
live note plus patterns and volume. Pins bumped for the merged files:
`btcchart` et11 → et12 (16 callers), `screener-indicator-chart`
stocks4 → stocks5. Verified: `tests/verify_live_feel_fixes.py`,
19/20 Playwright checks pass (TSLA + GOLD, 390px + 1280px, live and
closed states); the one miss is environmental — the sandbox blocks
Coinbase, so the popover falls back to daily closes there; with a
stubbed Coinbase feed the popover shows the live bucket text and
countdown ("Last candle is live — its close is the live price; this
bucket closes in 1h 11m").
