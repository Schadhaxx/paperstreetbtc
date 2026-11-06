# Python supercharge, slice 4 — review note for Grok Bot + Chief of Staff

**Status:** proposal for review. Test branch only. Nothing here is live, the
live pipeline (`.github/workflows/prices.yml`) is NOT changed, and nothing
deploys without Grok Bot + Chief of Staff review and Sunil's separate yes.

**Branch:** `pepper-python-supercharge-s4` (based on main `a4a0a76f`)
**Plan:** `python-supercharge-plan-2026-10-27.md`, Part 4 item 4 (Part 2B)
**Slices 1–3:** `pepper-python-supercharge-s1` (validate gate),
`pepper-python-supercharge-s2` (Tiingo un-stall),
`pepper-python-supercharge-s3` (pre-computed stats) — this slice fits
them; see "How slice 4 fits with slices 1–3" below.

## What slice 4 is, in one line

Two offline tools, both working from the history that is already stored.
The **backtester** replays the ledger with different rules and writes the
difference in $ and % — the safe way to test CR-005 and the vehicle toggle
before anyone builds them live. The **anomaly detective** is a daily scan
for splits, absurd jumps, missing sessions, dividend doubles and stale
prices, writing a short health report. Neither invents a price.

## What was built (5 files, nothing else)

- `tools/backtest.py` — the backtester. Stdlib only, no network, no key.
  CLI: `python3 tools/backtest.py --history <history.json>
  --ledger <ledger.js> --opens <opens.json>
  [--vehicle-daily <vehicle-daily.json>] [--sleeve <key>]
  [--contributions <file> | --dca <spec>] [--price open|close]
  [--vehicle SPOT|IBIT|FBTC] [--as-of <date>] [--compare] [--out <file>]`.
  Exit 0 = done, 1 = input unreadable, 2 = usage error.
- `tools/anomaly.py` — the detective. Stdlib only, no network, no key.
  CLI: `python3 tools/anomaly.py --history <history.json>
  [--ledger <ledger.js>] [--prices <prices.json>] [--out <report.json>]
  [--now <ISO>]`. Exit 0 = scan complete (whether or not anomalies were
  found), 1 = input unreadable, 2 = usage error.
- `tests/test_backtest.py` — 34 checks, no network.
- `tests/test_anomaly.py` — 27 checks, no network.
- This review note. No change to `prices.yml`, no site change, no new
  vendor, no API key anywhere.

## Part A — the backtester

The engine replicates `assets/js/book.js` exactly: initial units at the
base close, STRC cash dividends receivable from the ex-date until the pay
session, cash buying the sleeve's dividend assets at the pay session's
price. Contributions (lump sums / DCA) buy the sleeve at target weights
under the rule being tested. A contribution that buys STRC before an
ex-date earns that dividend (the STRC holding at the ex-date is read
from the timeline, not assumed).

Rules that can vary (one run = one rule set):
- `--price open|close` — lump-sum pricing. CR-005 (current) is OPEN:
  buy at the session open, weekdays only, a weekend/holiday date held
  to the next session's open. The alternative is the session CLOSE.
- `--vehicle SPOT|IBIT|FBTC` — which price series the BTC leg uses.
  IBIT/FBTC re-base the BTC slice in vehicle units (initial BTC units =
  $weight / vehicle base close), exactly as book.js does, and dividend
  buys follow the same rule (STRC cash buys the vehicle at the pay
  session's vehicle close in ETF mode — locked 29 Oct 2026).
- `--dca monthly|weekly` — the DCA schedule. Monthly is the current
  assumption; weekly is the alternative.

`--compare` runs the baseline (open + Spot + the contributions/DCA
given) and the three plan scenarios — close-not-open, IBIT-not-spot,
weekly-not-monthly DCA — and prints the difference in $ and %.

### Assumptions, documented (not guessed silently)

1. **In ETF mode the BTC leg of an open-priced buy uses the vehicle
   CLOSE**, because no vehicle opens exist (vehicle-daily.json carries
   closes only; opens.json has no IBIT/FBTC keys). This is the same
   treatment item 3 (vehicle-following for "Your sleeve") uses for the
   sleeve lines, and the same treatment book.js uses for dividend buys.
   No vehicle price is ever synthesised from spot opens.
2. **An open that is missing, or more than 25% from that session's
   close, falls back to the close** (the same sanity rule compare.js
   uses for lump-sum opens).
3. **A weekly DCA amount matches the monthly total**: weekly = monthly
   x 12 / 52, so 52 weekly payments total about the same as 12 monthly
   payments. The comparison is about timing, not about contributing more.
4. **A contribution dated before the base is ignored; one dated after
   the last close is ignored** (it has not happened yet in the data).
   Both are listed in the output so the caller can see what was skipped.

### Real-data result (2026-11-06, monthly $500 DCA on the 1st, all sleeves)

| Sleeve | Baseline (open + Spot) | close, not open | IBIT, not spot | weekly, not monthly |
|---|---|---|---|---|
| Berkshire | $95,510.12 | −$27.51 (−0.03%) | −$153.52 (−0.16%) | −$417.20 (−0.44%) |
| Hodler | $94,519.46 | −$59.26 (−0.06%) | −$261.38 (−0.28%) | −$478.12 (−0.51%) |
| Hedge Fund Killer | $94,204.19 | −$67.70 (−0.07%) | −$204.53 (−0.22%) | −$486.82 (−0.52%) |
| Saylor Moon | $103,879.38 | −$71.05 (−0.07%) | $0.00 (0.00%) | −$494.24 (−0.48%) |

Each baseline includes $5,500 contributed. The Saylor IBIT difference is
exactly $0 — Saylor has no BTC slice, so the vehicle cannot change it.
That is a useful sanity check that the engine is doing what it claims.
The weekly-vs-monthly difference is negative in a falling market (weekly
buys on Mondays caught more of the decline than the 1st-of-month buys);
the sign would flip in a rising market, which is the point of the tool.

## Part B — the anomaly detective

A daily scan, four checks, all on the real published data:

| # | Check | Definition |
|---|---|---|
| 1 | jumps / splits | A single-session move over 35% (the same threshold validate.py holds on). Close to a round split factor (2:1, 3:1, 4:1, 5:1, 10:1, or the inverse, within 5%) is labelled a likely split; otherwise an absurd jump. |
| 2 | sessions | An expected NYSE session (weekday, not a holiday — the holiday set reused from `tools/stock_weekly.py`, same as validate.py) with no close. |
| 3 | dividends | An STRC ledger amount about twice (or half) BOTH neighbours — an isolated spike, not a regime change. The daily $0.0333 amounts and the transitional half-period do not trip it, because their neighbours are not both half/double. Plus duplicate ex-dates. This is the Tiingo STRC double (1.916667 vs the declared 0.958333) as a pattern, applied to the ledger itself. |
| 4 | stale | A symbol whose last close is not the latest session; and (when prices.json is given) a live quote older than 30 minutes — but only when `now` is in market hours (9:30–16:00 ET, weekday, not a holiday). Outside market hours the quote is the close and being hours old is normal, not an anomaly. |

Output: a JSON report (`--out`) plus a short text summary on stdout
("No anomalies found", or one line per finding). This is a REPORTER,
not a gate — a finding never holds a run on its own. Exit 0 on a
successful scan.

**Real data (2026-11-06):** no anomalies found (215 sessions, history +
ledger + prices). The one false positive found while building — a US10Y
quote 60 minutes old at 21:00 UTC on a Friday — is what led to the
market-hours gate in check 4.

## How slice 4 fits with slices 1–3

- **Slice 1 (validate):** the gate BLOCKS bad data; the detective FINDS
  anomalies and reports them. They share the 35% jump threshold and the
  holiday set, but the detective never holds a run. A jump the detective
  flags on published data is a candidate for the gate to have held —
  the two tools agree on what "absurd" means.
- **Slice 2 (Tiingo un-stall):** a Tiingo-final date is a published
  value and is used as published by the backtester (no special-casing);
  the detective reads the published closes, so a frozen value is
  checked like any other close.
- **Slice 3 (stats):** the backtester reuses slice 3's engine (the
  Python replication of book.js) and extends it with vehicle mode and
  contributions. The no-contribution Spot baseline reproduces slice 3's
  verified stats exactly (Berkshire $89,923.35, −10.08% YTD; Hodler
  $88,796.72; HF $88,510.32; Saylor $98,121.11).

## Verification

- `tests/test_backtest.py`: **34 checks, 0 failed.** Hand-computed
  NAV series on a tiny synthetic history (initial units, receivable
  cash, dividend buy, value at each session); vehicle re-basing (base
  still exactly $100,000, value tracks the vehicle); open vs close
  contribution pricing (open buys more BTC when the open is below the
  close); weekend contribution held to Monday (CR-005); before-base and
  after-last-close contributions skipped and listed; a contribution's
  STRC earns the next dividend; the BTC leg of an open-priced buy in
  ETF mode uses the vehicle close; DCA schedule generation (monthly
  dates, weekly Mondays, bad specs rejected); vehicle map rules
  (1-session lag fills, 2-session lag rejected); CLI end-to-end
  (`--compare` produces a baseline and three scenarios with non-zero
  differences, CLI errors exit 1).
- `tests/test_anomaly.py`: **27 checks, 0 failed.** Clean synthetic
  data reports nothing; a planted 2:1 split is labelled a split with
  factor 2; a planted +47% one-day jump (reverting) is an absurd jump,
  not a split; a planted 1:2 reverse split is labelled with factor 0.5;
  a planted missing Wednesday is flagged; weekends are not flagged as
  missing; a planted dividend double (1.0 vs 0.5 on both sides) is
  flagged; the transitional half-period and the daily amounts are not
  flagged; a duplicate ex-date is flagged; a symbol missing from the
  last two sessions is flagged stale; a live quote 180 minutes old
  during market hours is flagged stale, the same quote before the open
  and after the close is not; CLI end-to-end (JSON report, exit 0,
  malformed history exits 1).
- **Real data (2026-11-06):** backtester `--compare` on all four
  sleeves (table above); the no-contribution Spot baseline reproduces
  slice 3's verified stats exactly; the detective reports no anomalies
  on the real history + ledger + prices.
- **No regressions:** this branch adds 5 files and modifies none.
  `tests/test_freeze.py` gives 191 checks with the SAME single failure
  as clean main (pre-existing, recorded in the slice-2 note).
  `py_compile` clean on all four new files.

## Proposed prices.yml wiring (NOT applied — for your review)

The detective is a daily step; the backtester is on-demand (it answers
a question, it does not run on a schedule). One step in the fetch job,
after the history is built and the slice-1 gate passes, writing the
report to the data branch alongside health.json:

```yaml
- name: Anomaly detective (slice 4 — daily scan, reporter only)
  run: |
    python3 tools/anomaly.py \
      --history work/history.json \
      --ledger assets/js/ledger.js \
      --prices work/prices.json \
      --out work/anomaly-report.json
    # exit 0 whether or not anomalies were found; the report is the
    # output. A finding is a data event for a human, not a hold.
```

The backtester needs no wiring — it runs by hand (or from a manual
workflow) when someone asks "what if". If you want its comparison
published, that is a separate small step, not part of this slice.

## Open questions for Grok + Chief

1. **Detective as a hold, or report-only?** Built as report-only (the
   gate stays slice 1). If a detective finding should ever hold a run,
   that is a wiring decision, not a tool change.
2. **Where does the anomaly report live?** Proposed: data branch
   alongside health.json (as above). Or only in the Actions log?
3. **Weekly DCA day:** the weekly scenario buys on Mondays. If the
   house DCA day is different, the comparison should use it.
4. **Vehicle in the backtester:** IBIT is the plan scenario; FBTC is
   available via `--vehicle` but is not a `--compare` scenario. Add it
   to `--compare`, or keep the comparison to the three plan scenarios?
5. **Stale-quote window:** 30 minutes in market hours (9:30–16:00 ET).
   Accept, or prefer the wider fetch-gate window (03:55–21:30 ET)?
6. **Dividend-double threshold:** ~2x both neighbours within
   1.8x–2.2x. Accept, or prefer a tighter/wider band?
