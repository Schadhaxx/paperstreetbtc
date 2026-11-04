# Current-week candle refresh — Saturday review (test branch only, NOT live)

Branch: `pepper-current-week-candle`, base main `03dc9cc`.
Sunil, 4 Nov 2026: build the full current-week candle (not a live-price
line), for the 4 market indicators AND the 7 stock weekly charts, for
Saturday implementation with everything else. Gate unchanged: Grok Bot
diff review + Chief of Staff coordination + Sunil's yes. Nothing here
is live.

## The gap (verified on main before building)
All shipped weekly files were 30 Oct 2026 snapshots. The screener
table refreshes every 5 minutes from prices.json, but the candle
charts did not move. Example at check time: WTI live $87.69 vs the
shipped chart close $104.24 (an intraday snapshot, labelled a close
in its own note — see preserved note below).

## What was built
- **New tool `tools/indicator_weekly.py`** (stdlib only, same pattern
  as `tools/stock_weekly.py`): Yahoo symbols WTI `CL=F`, GOLD `GC=F`,
  US10Y `^TNX`, VIX `^VIX`; UTC Monday–Sunday weeks (matching the
  shipped indicator files — stocks use ET dates, do not conflate).
  Append-only: every shipped week is kept verbatim; weeks after the
  last shipped Sunday are appended, plus the current week. Current
  week = open of first bar, max high, min low, last close, days =
  bar count; file `inProgress` + `asOf` updated; the note gains a
  "latest week in progress, its close is not a final close" sentence.
  Fails loud (exit 1, writes nothing) on Yahoo error / null OHLC /
  inconsistent bars, except null-OHLC rows skipped ONLY for weekends
  and NYSE holidays. Self-gating: if the last week is the current
  week and `asOf` is today (ET), it prints "already rebuilt today"
  and writes nothing; if it was rebuilt on an earlier day, it
  refreshes that one candle in place instead of appending a
  duplicate. At most one pipeline commit per day.
- **Stock data regenerated with the EXISTING `tools/stock_weekly.py`**
  (no tool change): all previously shipped weeks byte-identical for
  all 7 symbols (0 changed old weeks); each gains the current week
  2–8 Nov 2026 with days 2 (completed sessions Mon 2 + Tue 3 Nov;
  Wed 4 Nov not complete before 16:15 ET, so cutoff = 2026-11-03).
- **Module `assets/js/screener-indicator-chart.js`**: data pins
  bumped (gold v2→v3, wti/us10y/vix v1→v2, `STOCK_V`
  '20261030r'→'20261104'); WTI's hardcoded in-progress string
  replaced with null (the label now comes from the data file's
  `inProgress`, which the module already renders); indicator
  sub-blurbs' stale "data to 30 Oct 2026" dates removed.

## Trial values (run 4 Nov ~2:36 p.m. ET, Yahoo)
Indicators, all now 45 weeks, asOf "4 Nov 2026, 2:36 PM ET", current
week 2–8 Nov 2026, days 3 (Mon–Wed bars):
- WTI O 102.39 / H 102.75 / L 87.13 / C ~87.85 (Yahoo in-progress
  close moved 87.81–87.85 between runs — in-progress, not final)
- GOLD O 3890.0 / H 4080.8 / L 3889.0 / C 4071.9
- US10Y O 4.904 / H 4.968 / L 4.869 / C ~4.884–4.886
- VIX O 19.05 / H 21.91 / L 16.67 / C ~16.74–16.77
Stocks, current week 2–8 Nov 2026, days 2:
- IBIT 43.9 / 44.15 / 43.29 / 44.05 · META 614.44 / 624.84 / 606.41 /
  621.03 · MSTR 132.22 / 138.41 / 129.34 / 135.63 · MU 890.54 /
  892.08 / 829.24 / 855.1 · PLTR 186.52 / 187.55 / 165.25 / 175.4 ·
  SPCX 137.01 / 142.74 / 135.72 / 141.31 · TSLA 404.66 / 414.23 /
  396.53 / 398.5

## Preserved weeks — pending Grok Bot + Chief of Staff review (NOT overwritten)
The tool recomputes ONLY the last shipped week's close from Yahoo
and, on a mismatch, appends a note sentence — it never overwrites:
- WTI week of 2026-10-26: shipped close 104.24 vs Yahoo recomputed
  104.12 (preserved).
- GOLD week of 2026-10-26: shipped close 3901.2 vs Yahoo recomputed
  3898.9 (preserved — exactly the flagged $2.30 difference; the
  31 Oct decision to leave the gold last-candle label for Grok/Chief
  review stands, this build does not relitigate it).
- US10Y and VIX last shipped weeks matched Yahoo; no preserved note.

## Pipeline patch (for Grok's Saturday web edit — App API cannot push workflow files)
See `proposals/current-week-candle/prices-patch.md`. In short: in
the recap job (the main-branch job that already stages in /tmp/stage
and `git add`s recap/ + btc-daily/opens/vehicle-daily), after the
vehicle step run `python3 tools/stock_weekly.py --out-dir assets/data`
and `python3 tools/indicator_weekly.py --out-dir assets/data` in the
stage, validate with both tools' `--check-only`, and add the 11
weekly JSONs to the job's `git add` line, committing only when
changed. Proposed cadence (Pepper's proposal, not a Sunil decision):
daily after-close updates, not every 5 minutes — the indicator tool
is self-gating to once/day, and the stock tool only changes after a
completed session, so a 5-minute job would produce at most a daily
commit. OVERLAP FLAG: Chief's Fri 6 Nov ~7:30 p.m. job (weekly
screener candle data refresh + comparison-chart toggle fix) covers
this same ground — Saturday should pick ONE route so the work is
not built twice.

## Verification so far
- `tools/indicator_weekly.py --check-only` re-run 4 Nov: all four
  files "current week already rebuilt today — file unchanged"
  (idempotency confirmed, no duplicate week appended).
- `tools/stock_weekly.py` diff: 0 changed old weeks, all 7 symbols.
- Module syntax-checked. Browser check on the githack copy (WTI
  in-progress candle ~$87–88, not $104.24; one stock's 2-day candle)
  is still to be recorded here — see the note-only update after it.

## Rollback
Revert the 11 weekly JSONs + the module pin bumps to main. The new
tool file is additive only and can stay or be removed; no live data
depends on it until the pipeline patch lands.
