# Python supercharge, slice 5 — review note for Grok Bot + Chief of Staff

**Status:** proposal for review (round 2 rework). Test branch only.
Nothing here is live, the live pipeline
(`.github/workflows/prices.yml`) is NOT changed, and nothing deploys
without Grok Bot + Chief of Staff review and Sunil's separate yes.

**Branch:** `pepper-python-supercharge-s5` — same branch name, rebased
onto main `eb9edfd` (a data refresh only vs the live-feel commit
`7028936`: `assets/data/opens.json`, `assets/data/vehicle-daily.json`,
`recap/2026-11/index.html`, `recap/months.js`; no code changes). The
rebase was clean; the branch now carries the rework as a second commit
on top of the rebased original. All 4 refreshed data files are in the
branch tree, so it matches main `eb9edfd` + slice 5.
**Plan:** `python-supercharge-plan-2026-10-27.md`, Part 4 item 5 (Part 1 recs 3 + 5)
**Slices 1–4:** `pepper-python-supercharge-s1` (validate gate),
`pepper-python-supercharge-s2` (Tiingo un-stall),
`pepper-python-supercharge-s3` (pre-computed stats),
`pepper-python-supercharge-s4` (backtester + anomaly detective) — this
slice fits them; see "How slice 5 fits with slices 1–4" below.

## What changed in round 2 (Grok Bot review #2 rework)

Grok Bot's review #2 verdict, point by point:

1. **Prior close from bar timestamps, not `closes[-2]`.** Done —
   the prior close is now the close of the daily bar whose session
   (ET date of its timestamp) is the latest one strictly before the
   quote's session. `closes[-2]` can select the wrong day when the
   latest bar is not the quote's session (e.g. a missing session, or
   the bar list ending before the quote's session). See Part 1.
2. **Quote timestamp / session / regular-hours freshness validated
   before accepting Yahoo.** Done — a quote whose timestamp is not in
   regular hours (09:30–16:00 ET, weekday), whose session is not the
   expected session (today, ET), or which is more than 30 min old is
   rejected before any price is looked at. See Part 1.
3. **Invalid / stale responses retain the previous quote.** Unchanged
   behaviour, now with a named rejection reason in the report — never
   a Yahoo value written into prices.json unless it passes every
   check above.
4. **Safe finite-only writes.** Done — both tools serialise with
   `allow_nan=False` (a NaN / Infinity anywhere raises before the
   target is touched) and publish by write-to-temp + atomic rename,
   so a failed run can never leave a partial file. Health fields are
   preserved exactly as before (slice 1's file, `alerts` only).
5. **Alerts last (settled default).** The stall-alert step runs LAST
   in the proposed wiring — after the validate gate and after the
   prices + health writes — so nothing overwrites the `alerts` field.
   See Part 3 and the wiring.
6. **Mobile table fix (was a layout note, now required).** Done — the
   expanded tracker card's table no longer clips the Value / Original
   / Live columns at 390 px in the stale state. Wrapping + a
   contained scroll box inside the card. Measured, see Part 2b.
7. **Real Yahoo success — NOW VERIFIED.** The sandbox DOES reach
   Yahoo (the "sandbox blocks fetches" assumption from round 1 was
   wrong). A live Yahoo chart call for MSTR succeeded and the CLI
   applied it end-to-end. See Verification.

## What slice 5 is, in one line

Live stocks get a second source (Yahoo chart meta when Finnhub fails),
a stale price is labelled with how old it is instead of being shown as
live, and a pipeline stall surfaces as a note instead of failing
silently. Nothing here is a new real-time feed — the plan's honest
limit (Part 3) stands: Python does not turn a free feed into a paid
real-time feed.

## What was built (8 files, nothing else)

- `tools/live_fallback.py` — the Yahoo fallback tool. Stdlib only, no
  key (Yahoo chart is keyless). CLI: `python3 tools/live_fallback.py
  --prices <prices.json> --failed <MSTR,TSLA,...> [--out <prices.json>]
  [--dry-run] [--now <ISO>]`. Exit 0 = done, 1 = input unreadable /
  unwritable (file untouched), 2 = usage error.
- `tools/stall_alert.py` — the stall alert tool. Stdlib only, no
  network, no key. CLI: `python3 tools/stall_alert.py
  --history <history.json> [--prices <prices.json>]
  [--health <health.json>] [--out-health <health.json>]
  [--out <alerts.json>] [--now <ISO>]`. Exit 0 = scan complete
  (alerts or not), 1 = input unreadable / unwritable, 2 = usage error.
- `assets/js/s6.js` — the staleness display (Part 2, minimal) plus the
  holdings-table wrapper for the mobile fix (Part 2b).
  `s6.js?v=p4` → `p5` on `index.html` (its only caller).
- `index.html` — s6.js pin bump only.
- `styles.css` — the mobile table fix (Part 2b): contained scroll box
  + wrapping label text. No other rule changed.
- `tests/test_live_fallback.py` — 39 checks, no network (stubbed Yahoo).
- `tests/test_stall_alert.py` — 27 checks, no network.
- This review note. No change to `prices.yml`, no new vendor, no API
  key anywhere near site JavaScript or logs.

## Part 1 — live stocks second source (Yahoo chart meta)

Live BTC already has a fallback chain (CoinGecko → Coinbase → keep last
price). Live stocks were Finnhub-only → keep last price. Now, for each
symbol Finnhub fails on, the tool fetches Yahoo chart meta
(`regularMarketPrice`, `regularMarketTime`, daily bars with timestamps)
and, if the quote passes every check below, writes it into prices.json
with a `'src': 'Yahoo'` tag so the site can show where it came from.

**Why Yahoo, not Stooq:** Stooq gives daily closes, not a live intraday
price — using it would present yesterday's close as a live price, which
is exactly the dishonesty this slice is meant to prevent. Yahoo chart
meta gives `regularMarketPrice`, a real live price during market hours,
keyless and free, from a source the pipeline already trusts (the history
rebuild and the market indicators use it).

**Acceptance checks, in order** (a quote failing any one is rejected
and the previous value is kept, with the reason in the report):

1. **Timestamp / session / freshness first.** `regularMarketTime`
   must be a real time, no more than 5 min in the future (clock
   skew), no more than 30 min old (the site's own stale threshold),
   on a weekday, inside regular hours 09:30–16:00 ET, and from the
   same ET session as `now` (the expected session). A quote from
   after hours, a weekend, yesterday's close, or a stale poll is
   rejected before any price is looked at — it can never become a
   live price. `--now` pins "now" (default: current UTC time) so a
   run is reproducible and testable.
2. **Prior close from bar timestamps.** The prior close is the close
   of the daily bar whose session (ET date of its timestamp) is the
   latest one strictly before the quote's session — never
   `closes[-2]`. Across a holiday or a missing session that stays
   right: e.g. bars ending Fri with a Monday quote take Friday's
   close, where `closes[-2]` would take Thursday's. If no bar
   precedes the quote's session, or the immediately-preceding bar's
   close is missing / invalid, there is no prior close and the quote
   is rejected (an older session's close is NOT substituted — the
   sanity band must be measured against the session right before
   the quote). The request uses `range=10d&interval=1d` (was 5d) so
   the prior session's bar survives a long holiday stretch.
3. **Price sanity.** The Yahoo price must be positive and finite, and
   within 25% of that prior close (the same sanity band compare.js
   uses for lump-sum opens).

**A fallback price is never invented and never a stale price presented
as live.** If Yahoo fails or returns a bad / stale / wrong-session
quote, the previous value is kept (today's behaviour) and the symbol
is reported as still stale — the site then labels it stale (Part 2)
instead of showing a frozen price as live.

**Safe writes.** prices.json is serialised with `allow_nan=False`
(a non-finite number anywhere raises before the target is touched)
and published by write-to-temp + atomic rename (`os.replace`), so a
failed run can never leave a partial file.

**Known limit:** regular hours here are the plain 09:30–16:00 ET
window — there is no holiday / early-close calendar in the repo, so
the tool cannot tell an early-close day from a regular session. A
fresh afternoon quote on an early-close day (e.g. 14:00 ET, after the
13:00 early close) is ACCEPTED, not rejected, as long as it passes the
regular-hours rule (09:30–16:00 ET, same ET session, ≤30 min old,
≤5 min in the future) — so on such a day a quote timestamped after the
market has closed can still be shown as live until 16:00 ET. That is
the limitation to disclose, not a rejection. No calendar is built in
this pass. (Corrected per Grok Bot review, 6 Nov 2026: the earlier
wording wrongly claimed such quotes were rejected and the previous
price kept, labelled stale.)

**Call budget:** only for Finnhub-failed symbols (typically 0). Worst
case, Finnhub fully down, 13 Yahoo calls — the same keyless endpoint
the indicators already call 4 times per run. No budget issue.

## Part 2 — staleness display (homepage, s6.js only)

The site already had a staleness concept: stock quotes count as live
only while the market is open AND prices.json is < 30 min old
(`stocksFresh()`), and `cacheLabel()` showed "(stale)" when the market
was open and prices.json was > 30 min old. What was missing was the
age, and per-stock staleness. Two minimal changes:

1. `cacheLabel()` now reads "Stocks: cached · updated 3:45 PM (stale —
   last updated 42 min ago)" when stale. The age comes from `cacheUpd`
   (the prices.json `updated` timestamp), never guessed.
2. Each stock's label (`src[T]`, shown as its price source) now names a
   fallback source and its own staleness: "cached 3:45 PM · Yahoo" for
   a Yahoo-supplied quote, and "cached 3:45 PM (stale, 42 min ago)"
   when that quote's own timestamp is > 30 min old during market
   hours. A single frozen quote must not read as live just because
   prices.json itself is fresh — that is the case Part 1 creates when
   both sources fail, and this label is what makes it visible.

Both use the actual timestamps (`cacheUpd` for the file, `q.t` for the
quote). Outside market hours neither shows stale — an old quote after
the close is normal, not an anomaly (the same rule slice 4's detective
uses). The screener already labels per-symbol live vs close, so no
change was needed there.

## Part 2b — mobile table fix (round 2, required)

**The problem (round 1 layout note):** at 390 px, when stale, the
expanded tracker card's table widened to 448 px inside a ~340 px card,
pushing the Value / Original / Live columns past the card's right edge
where they were clipped. The page itself did not scroll — the columns
were simply unreachable. The cause was the per-stock label from Part 2:
`cached 1:15 PM (stale, 45 min ago)` is long, and
`.pf-tbl em { white-space: nowrap }` forbade it from wrapping, so the
Price column forced the whole table wider than the card.

**The fix (two layers, both in this slice):**

1. **Wrapping.** `.pf-tbl em` is now `white-space: normal` with
   `overflow-wrap: break-word`, and table cells get
   `overflow-wrap: break-word` — the long label wraps inside the
   Price cell instead of forcing the table wide. Desktop is
   unaffected (wrapping only bites when the cell is constrained).
2. **Contained scrolling (backstop).** s6.js now wraps the table in
   `<div class="pf-tbl-wrap">`, styled `overflow-x: auto;
   max-width: 100%` and hidden until the card opens (the open/close
   toggle moved from the table to the wrapper; the table itself is
   always `display: table`). If a table is ever wider than its card
   again, it scrolls horizontally INSIDE the card — the columns stay
   reachable, and nothing can clip past the card's edge again.

**Measured (Playwright, STALE fixture, 390 px, dark + light):**
card 342 px, table 308 px, wrapper 308 px, wrapper scrollWidth =
clientWidth = 308 (no scrolling needed — wrapping fixed it; the
scroll box is the backstop), all five headers (Asset / Price / Value
/ Original / Live) inside the card, no page overflow. Before the fix:
table 448 px in a ~340 px card. See Verification.

## Part 3 — stall alerts (health.json + Actions log)

A recap stall today is silent — the recap simply does not advance, and
nothing says so except btc_daily.py's `::error::` in the recap job log.
This tool is the notification, riding on existing channels only: an
`alerts` field in health.json (slice 1's file, data branch) plus
`::warning::` lines in the Actions log. No account, notification, or
email setting is touched, and no new alerting system is created.

| # | Alert | Definition |
|---|---|---|
| 1 | `recap_stalled` (error) | A BTC date in `btc_provisional` more than 48 h after its UTC day ended — the same clock btc_daily.py uses — that is NOT in `tiingo_final`. The recap cannot advance past it, and slice 2 has not un-stalled it. |
| 2 | `recap_tiingo_final` (info) | A date in `tiingo_final` (still provisional). NOT a stall — the recap advanced on it. The alert notes the un-stall so a human knows the recap is running on a confirmed-but-not-Yahoo-final value; it does not re-stall it. |
| 3 | `prices_stale` (warning) | `now` is inside the fetch window (weekday, 03:55–21:30 ET — the same gate prices.yml uses) and prices.json `updated` is more than 60 min old. The fetch job has not succeeded in over an hour. Outside the window an old prices.json is normal and is not flagged. |

health.json: this tool owns the `alerts` field only. It reads an
existing health.json (written by slice 1's validate.py), sets its
`alerts` list, preserves every other field, and writes it back. When
there are no alerts, `alerts` is `[]` — always present after this tool
runs, so a reader can tell the check ran. Writes are safe (round 2):
serialised with `allow_nan=False` and published by write-to-temp +
atomic rename, so a failed run can never leave a partial file.

**Alerts run last (settled default).** This step runs LAST in the job —
after the validate gate and after the prices + health writes — so
nothing after it overwrites the `alerts` field. The wiring below has
it as the final step, and the tool's docstring says so.

This is a REPORTER, not a gate: it never holds a run, never changes a
price, and exits 0 whether or not alerts were found. The recap stall's
hard signal stays btc_daily.py's `::error::` (exit 3); this tool prints
`::warning::` for all its alerts so its own step does not look failed.

## How slice 5 fits with slices 1–4

- **Slice 1 (validate):** the gate still checks published data. A
  Yahoo-fallback stock entry gains only an extra `'src'` field; `c`,
  `pc`, `t` are unchanged in shape. Verified with the actual slice-1
  gate against the live data-branch history + a prices.json carrying
  a Yahoo `'src'` entry: **exit 0, health output identical with and
  without the Yahoo entry**. (The gate reports status `held` for a
  pre-existing live-data reason — 2026-11-06 BTC fallback-sourced but
  not tagged provisional — the same with plain prices.json, so it is
  not caused by this slice.) No gate change.
- **Slice 2 (Tiingo un-stall):** the stall alert reads `tiingo_final`
  and excludes those dates from the stall alert (they get the info
  note instead). It only reads history.json — it never writes it and
  cannot re-stall a frozen date. The un-stall mechanism is untouched.
- **Slice 3 (stats):** stats are computed from published closes; a
  Yahoo fallback price is a live quote in prices.json, not a close in
  history.json, so it cannot change a stat. No interaction.
- **Slice 4 (anomaly detective):** the detective is the data reporter
  (a quote > 30 min old in market hours is a stale finding); the stall
  alert is the pipeline reporter (the recap / fetch job not advancing).
  They agree on the 30-min stale threshold but check different things.
  Verified with the actual slice-4 detective against the live history
  + a Yahoo-entry prices.json: **no anomalies found**. A Yahoo
  fallback price (fresh `t`) is not flagged stale; a kept-previous
  price (old `t`) is — correctly, because it IS stale.

## Verification

- `tests/test_live_fallback.py`: **39 checks, 0 failed** (23 original,
  reworked for timestamp fixtures + pinned `--now`, + 13 new, + 3
  CLI determinism fixes). No network (stubbed Yahoo). Original 23
  still cover: valid Yahoo applied with `'src': 'Yahoo'`; unfailed
  symbols untouched; Yahoo fetch failure / empty result / bad price /
  missing prior close / missing timestamp all keep the previous value;
  +26% vs prior close rejected, +25% (band edge) applied; BRK.B fetched
  as BRK-B; both-fail keeps both; mixed outcomes correct; CLI
  end-to-end (exit 0 when Yahoo fails, file unchanged, `--dry-run`
  writes nothing, malformed prices.json exit 1, missing `--failed`
  exit 2). New r2 checks: prior close from a missing session's bars
  (Fri's close, not `closes[-2]`'s Thu); holiday gap (Fri bar before
  a Tue session); after-hours (17:30 ET), weekend (Sat), stale
  (45 min old), future (+10 min), and wrong-session quotes all
  rejected with a named reason; 09:30 open accepted, 09:29
  pre-market rejected; atomic write (valid data written, no temp
  files left, NaN raises with the target untouched); CLI with a
  non-finite prices.json exits 1 with the file byte-identical, bad
  `--now` exits 2.
- `tests/test_stall_alert.py`: **27 checks, 0 failed** (24 original +
  3 new). Original 24 still cover: clean run; recap stall found;
  48 h boundary; fresh provisional; Tiingo-final info note only;
  stalled + Tiingo-final together; prices 90 min old in-window
  flagged, 30 min not; 60-min boundary; night / Saturday not flagged;
  no prices.json; health update preserves fields, sets `last_run`
  only when absent, does not mutate its input; CLI end-to-end. New r2
  checks: CLI with a non-finite health.json exits 1 with the file
  byte-identical and no temp files left; clean write exits 0, fields
  kept, no temp files left.
- **Real Yahoo, live (NEW — verified 6 Nov 2026 evening, this
  sandbox).** The round-1 assumption that the sandbox blocks external
  fetches was wrong: `curl` to Yahoo chart returned HTTP 200, and the
  CLI end-to-end run with `--now 2026-11-06T21:10:00Z` (quote 10 min
  old) applied a real fallback: `MSTR: fallback Yahoo 128.93`,
  written as `{'c': 128.93, 'pc': 129.3000030517578, 'src': 'Yahoo',
  't': 1793998801}` — price 128.93, prior close 129.30 (the Nov 5 bar,
  derived from its timestamp), regularMarketTime 1793998801
  (16:00:01 ET — inside regular hours on the minute-granularity
  check). Exit 0. The live response also confirms the bar shape the
  derivation relies on: 10 dated bars for `range=10d`, last bar
  Nov 6 09:30 ET close 128.93, prior bar Nov 5 close 129.30.
- **In-page display (Playwright, real homepage, route-intercepted
  fixtures, clock frozen Fri 2026-11-06 14:00 ET): 8/8 combos pass**
  — STALE + FRESH × desktop 1280 + 390 px × dark + light. STALE
  (prices 45 min old): the note reads "Stocks: cached · updated
  1:15 PM ET (stale — last updated 45 min ago)" and the MSTR row
  reads "$128.93 cached 1:15 PM ET · Yahoo (stale, 45 min ago)".
  FRESH (5 min old): no stale text anywhere. Mobile fix measured at
  390 px STALE (both themes): card 342 px, table 308 px, wrapper
  308 px, wrapper scrollWidth = clientWidth (no scroll needed),
  every header inside the card, no page overflow. (This supersedes
  the round-1 Node stub check — 7/7 then — with the stronger in-page
  verification; `node --check` on the modified s6.js is clean.)
  Note: `page.clock.install` must be given a datetime, not raw ms —
  with a ms int, `new Date()` returned a garbage year in this
  Chromium build and the market-open check failed; the check script
  uses a datetime.
- **Real data (2026-11-07, live data branch):** stall_alert.py
  against history.json (215 closes, no provisional, no
  `tiingo_final`) + prices.json (updated 2026-11-07T00:40:17Z):
  **no stalls, exit 0**. Slice-1 validate.py passes on the
  Yahoo-entry prices.json (above). Slice-4 anomaly.py reports no
  anomalies on the live history + Yahoo-entry prices.json.
- **Not verified live:** the first real Finnhub failure has not
  happened yet — the Yahoo call itself is now proven (above), but
  the end-to-end Finnhub-fails-then-Yahoo-saves path in the Actions
  log is still unwatched. When the first Finnhub failure happens,
  someone should watch that run's log.

## Proposed prices.yml wiring (NOT applied — for your review)

Two additions, no rewrite. In the "Fetch prices" step, after the
Finnhub loop, collect the symbols Finnhub failed on and call the
fallback tool (fetched from main, as slice 2's tool is):

```yaml
      - name: Live-stock fallback (slice 5 — Yahoo when Finnhub fails)
        if: steps.gate.outputs.run == '1'
        run: |
          cd work
          git fetch -q --depth 1 origin main
          git show FETCH_HEAD:tools/live_fallback.py > /tmp/live_fallback.py
          # FAILED is the comma-separated list the Finnhub loop recorded
          python3 /tmp/live_fallback.py --prices prices.json --failed "$FAILED" \
            || echo "::warning::live-fallback failed; prices.json unchanged, keep-last-price as today"
```

The Finnhub loop needs one small addition: record each symbol that
fails or returns bad data into `FAILED` (it already prints those
cases). And a stall-alert step as the LAST step of the job, after the
validate gate (which writes health.json) and after the prices +
health writes, updating health.json:

```yaml
      - name: Stall alerts (slice 5 — recap / prices stalls into health.json)
        # LAST step in the job: alerts merge last, so nothing after this
        # step overwrites the alerts field (settled default).
        run: |
          cd work
          git fetch -q --depth 1 origin main
          git show FETCH_HEAD:tools/stall_alert.py > /tmp/stall_alert.py
          python3 /tmp/stall_alert.py --history history.json --prices prices.json \
            --health health.json --out-health health.json
          # exit 0 whether or not alerts were found; the alerts field is the output
```

The s6.js display ships with the site (pin `p5`); it degrades
gracefully — a prices.json without `'src'` fields renders exactly as
today, and the age label only appears when a price is actually stale.

## Open questions for Grok + Chief

1. **Fallback source:** Yahoo chart meta (proposed here) or Stooq?
   Stooq gives daily closes, not live prices — it cannot be a live
   fallback without presenting a stale close as live. If you prefer a
   different second source, the tool's fetcher is the only thing that
   changes.
2. **Sanity band:** 25% from the prior close (same as compare.js opens).
   Accept, or prefer a tighter band for live quotes?
3. **Prices-stall threshold:** 60 min inside the fetch window. Accept,
   or prefer a shorter/longer window? (The failed fetch run already
   emails; this is the durable health.json record.)
4. **~~Health file wiring order~~ — SETTLED (round 2):** stall-alert
   runs LAST, after the validate gate and the prices + health writes,
   so nothing overwrites the `alerts` field. validate.py is not
   changed. No action needed unless you prefer validate.py to
   preserve an existing `alerts` field instead.
5. **The first real Finnhub failure** has not happened yet. The Yahoo
   call itself is now verified live (see Verification), but the
   Finnhub-fails-then-Yahoo-saves path in the Actions log is still
   unwatched. When it happens, who watches the log — Grok Bot,
   Chief, or Pepper?
6. **~~s6.js in-page render~~ — CLOSED (round 2):** browser-checked
   8/8 (desktop + 390 px, dark + light, STALE + FRESH), including the
   mobile table fix measured at 390 px.
7. **Early-close days (corrected 7 Nov 2026 — the earlier wording
   was wrong):** the quote check uses the plain 09:30–16:00 ET
   window (no holiday / early-close calendar exists in the repo), so
   a fresh afternoon quote on an early-close day is ACCEPTED — the
   tool cannot tell an early-close day from a regular session, and a
   quote timestamped after the 13:00 early close but within the
   regular-hours rule can be shown as live until 16:00 ET. Accept
   that limitation, or is a holiday calendar worth adding later?
