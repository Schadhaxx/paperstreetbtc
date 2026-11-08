# Python supercharge, slice 3 — review note for Grok Bot + Chief of Staff

**Status:** proposal for review — REWORK #2 for a final review. Test branch
only. Nothing here is live, the live pipeline
(`.github/workflows/prices.yml`) is NOT changed, and nothing deploys
without Grok Bot + Chief of Staff review and Sunil's separate yes.

**Branch:** `pepper-python-supercharge-s3-r2` (rebased onto main `eb9edfd`;
the original branch `pepper-python-supercharge-s3` was based on `a4a0a76f`.
The rebase had one conflict, in `compare/index.html`: live-feel had
bumped btcchart `et11` → `et13` while this slice inserts the
stats-display script tag. Resolved by keeping `et13` and the script
tag. No other file conflicted — the `eb9edfd` delta vs `a4a0a76f` is a
data refresh plus live-feel, no code this slice touches.)
**Plan:** `python-supercharge-plan-2026-10-27.md`, Part 4 item 3 (Part 2A)
**Slices 1–2:** `pepper-python-supercharge-s1` (validate gate),
`pepper-python-supercharge-s2` (Tiingo un-stall) — this slice fits both;
see "How slice 3 fits with slices 1–2" below.

## What changed in rework #2 (Grok Bot review #2 — all addressed)

1. **Spot labelling.** The rendered section now states visibly, at the
   top, that the figures use the Spot BTC book, not the selected ETF
   vehicle. Exact wording (in `stats.json` as `spot_note`, rendered
   in-page by `stats-display.js`):
   > "Spot BTC book — these figures use the Spot BTC book, not the
   > selected ETF vehicle (IBIT/FBTC)."
2. **The existing explanatory note now renders in-page.** The
   `stats.json` note ("Pre-computed by Python; the site displays these
   numbers, it does not re-derive them. Spot mode only.") is rendered
   directly under the Spot note — it was previously carried in the
   file but never displayed. Verified visible in-page in all 4
   Playwright combos (see Verification).
3. **Modelled dividend label (CONFIRMED by Sunil — built as approved).**
   The per-day $/share is NEVER presented as a guaranteed daily
   payment. Exact rendered wording:
   > "Next STRC payment: Nov 9 — **modelled ~$0.0333/share**
   > (Berkshire $6.75 · Hodler $3.37 · HF $3.37 · Saylor $16.87).
   > 25 daily payments left in Nov — Nov total $1.00/share declared.
   > Modelled — the per-day $/share is approximate, pending
   > source-confirmed payable precision; the declared monthly total
   > stands."
   The declared monthly total ($1.00/share November) is retained as
   declared. In `stats.json` every upcoming payment carries
   `per_share_modelled: true`, the calendar carries `per_share_note`
   with the caveat above, and each month total carries
   `declared: true`. The label applies everywhere the per-day amount
   appears (stats.json, rendered calendar, this note).
4. **Generate-after-validation.** The tool's contract (documented in
   its docstring and here, and reflected in the proposed wiring — NOT
   applied): generate stats ONLY after slice 1's validate gate has
   passed on the history being used, and only when that validated
   history has changed. `stats.json` records which history it was
   computed from and when: `history_sha256` (SHA-256 of the
   history.json file read), `history_first` / `history_last` (first
   and last sessions), `history_sessions`, `as_of` (last session) and
   `generated` (UTC run time), plus a `validation` field stating the
   contract. A published stats.json can always be traced back to its
   exact input history.
5. **CSV column order documented.** Exact order, fixed (NOT
   alphabetical): `date, BTC, MSTR, STRC, TSLA, PLTR, SPY, QQQ, BRK.B,
   GLD` — the 9 closes in history.json order. Stated in the tool's
   header comment (`CSV_COLUMNS`), in this note, and asserted by the
   tests. (The original build sorted the symbols alphabetically, which
   did NOT match this order; the tool now uses the fixed order.)
6. **No workflow wiring.** `prices.yml` is NOT changed. The proposed
   wiring below stays a proposal only.

Settled defaults (already decided, built to these): Spot-only stats
clearly labelled; sample-return volatility annualised by √252;
closes-only CSV; generate stats only when validated history changes.

## What slice 3 is, in one line

Python pre-computes the stats the site used to leave to the visitor's
phone — monthly returns, best/worst days, drawdown from peak, volatility,
a Pulse context line, the STRC dividend calendar, price badges — and a
one-click CSV export, all from the history that is already stored. The
site displays the numbers; it does not calculate them.

## What was built (6 files, nothing else)

- `tools/stats.py` — the tool. Stdlib only, no network, no key.
  CLI: `python3 tools/stats.py --history <history.json> --ledger <ledger.js>
  --out-stats <stats.json> --out-csv <history.csv> [--now <ISO>]`.
  Exit 0 = written, 1 = input unreadable, 2 = usage error. Records
  `history_sha256` / `history_first` / `history_last` /
  `history_sessions` / `as_of` / `generated` in stats.json, carries the
  Spot note, and marks each upcoming dividend per-day amount
  `per_share_modelled: true`.
- `tests/test_stats.py` — 62 checks, no network. Run with
  `python3 tests/test_stats.py` (exit 0 = all pass). It runs the Node
  display test too, when `node` is available.
- `tests/test_stats_display.js` — the display test (Node). Renders a
  stats.json through the pure `PSStats.render()` and asserts the HTML
  carries the pre-computed numbers — including the Spot note and the
  modelled dividend label. Expectations are derived from the stats file
  itself, so it stays valid as the data moves.
- `assets/js/stats-display.js` — the minimal display. `PSStats.render(S)`
  is pure (stats object in, HTML string out); a small loader fetches
  stats.json from the data branch and fills `#pvStats`. If the fetch
  fails (stats.json not published yet) the section stays hidden. It
  renders the Spot note and the explanatory note at the top, and the
  modelled dividend label with its caveat.
- `compare/index.html` — a `#pvStats` container under the chart note, a
  small `.pv-stats` style block (plus `.pv-spot-note`), and the script tag
  (`stats-display.js?v=sd2`). No change to compare.js.
- This review note. No change to `prices.yml`, no site change beyond the
  Compare display above, no new vendor, no API key anywhere.

## The stats (all pre-computed, Spot mode only)

Per series — 4 sleeves + 6 benchmarks (BTC, SPY, QQQ, BRK.B, MSTR, GLD):

| Stat | Definition |
|---|---|
| Monthly returns | Last session of each month vs the prior month-end; the current month is month-to-date and marked `*` |
| Best / worst day | Largest single-session % move, with its date |
| Drawdown from peak | Latest value vs its all-time high; plus the worst peak-to-trough drawdown and its date |
| Volatility | Annualised standard deviation of daily returns (sample std × √252) |
| YTD | Value vs the 31 Dec 2025 base close |

Sleeve NAVs replicate `assets/js/book.js` exactly (initial units at the
base close, STRC cash dividends receivable from the ex-date until the pay
session, cash buying the sleeve's dividend assets at the pay session's
close). Benchmarks replicate `book.js` too: SPY/QQQ total return
(distributions reinvested at the ex-date close), the rest price return,
all indexed to 100 at the base close. The display table shows YTD, the
current month, best/worst day, drawdown and volatility; the monthly table
shows sleeves only (benchmark monthly returns are in stats.json).

**Pulse context, per sleeve:** "$X above/below the Jan 1 start, $Y below
its peak (peak $Z on <date>)" — e.g. Berkshire Killer today: $89,923,
$10,077 below the Jan 1 start, $13,972 below its peak ($103,895 on
Jan 14). The values are the $100,000 sleeves from the book.

**Dividend calendar (STRC only):** the next payment (record, ex, pay
date, pay session when known, $/share, and the cash each sleeve gets —
STRC shares held at the ex-date × $/share, read from the timeline), the
count of daily payments left in the month, and the month total. November
reads $1.00/share declared (the full month, paid + upcoming), with 25
daily payments left, the next paying Mon Nov 9. The per-day $/share is
MODELLED / APPROXIMATE — "modelled ~$0.0333/share", pending
source-confirmed payable precision — never a guaranteed daily payment;
the declared $1.00/share monthly total stands. Pay dates past the last
close have no pay session yet (shown as the scheduled date).

**Price badges:** from closes only (see decision 1). Today: one badge —
"BTC crossed below $80,000 · Nov 5" (Nov 4 close $80,405, Nov 5 close
$75,942). A sleeve at its all-time high gets a "new high" badge; none
is at a high today.

**CSV export:** `history.csv` — one row per session, date + the 9 closes
in this exact fixed order (NOT alphabetical):
`date, BTC, MSTR, STRC, TSLA, PLTR, SPY, QQQ, BRK.B, GLD`. It is
history.json as a CSV, nothing more.

## Design decisions (for your review)

1. **Badges come from closes, not live prices.** The plan says "checks
   every 5 minutes", but a live-price badge would flicker (cross $80k,
   fall back, cross again). A close-based badge is stable and verifiable.
   The check runs whenever the stats are regenerated (on each history
   update), not every 5 minutes.
2. **Badges live in stats.json, not prices.json.** The plan says
   prices.json, but the fetch job rewrites prices.json every 5 minutes,
   so a badge written there would be clobbered. The site already reads
   stats.json for the table, so the badges ride along. If you prefer a
   merge into prices.json, that is a wiring change, not a tool change.
3. **Month totals are the full declared month.** November reads
   $1.00/share (paid + upcoming), matching the declared aggregate; the
   upcoming list shows what is still to come (25 payments, $0.83/share
   remaining). The alternative — totalling only the upcoming remainder —
   would read $0.83 and look like a different declaration.
4. **Spot mode only.** The stats describe the book's default model
   ($100,000 sleeves, buy-and-hold). Vehicle (IBIT/FBTC) stats are not
   in this slice; the sleeve NAVs in Spot mode are the ones the book
   defines.
5. **The display degrades silently.** Until the pipeline publishes
   stats.json, the loader's fetch fails and the section stays hidden —
   the Compare page is unchanged for visitors. No "stats unavailable"
   message, no broken table.
6. **A Tiingo-final date is used as published.** Slice 2's `tiingo_final`
   field is not special-cased here: a frozen value is a published value,
   and the stats use it like any other close. Verified: adding a
   `tiingo_final` entry to the history does not change any stat.
7. **The CSV is closes only.** It is history.json as a CSV, not sleeve
   NAVs. If you want NAVs in the export too, that is a small addition.

## How slice 3 fits with slices 1–2

The stats are computed from the PUBLISHED history — i.e. after slice 1's
validate gate passes, so a held run never produces stats from bad data.
Slice 2's Tiingo-final values are published values (decision 6 above).
The tool reads the same two inputs slice 1 uses (data-branch
history.json + `assets/js/ledger.js`); it does not need prices.json.

## Verification

- `tests/test_stats.py`: **62 checks, 0 failed** (was 52 in the
  original build; +10 new: modelled flag + note on the synthetic
  calendar, declared flag on month totals, Spot note, explanatory
  note, `history_sha256` pinning the input history, as-of/source
  info, modelled label on every upcoming payment, declared November
  total, CSV header in fixed order). A tiny synthetic history + ledger
  where every stat is hand-computed in the test (NAV series incl. a
  dividend receivable, monthly +9.08%, best +11.11% / worst −5.21%,
  drawdown −1.83%, max −5.21%, volatility vs an independent
  `statistics.stdev` reference, Pulse arithmetic, calendar with a pay
  session that does not exist yet, badges incl. a round crossing and a
  sleeve high, CSV round-trip). Real data: BTC YTD matches a hand
  calculation from the raw closes (−13.46%); monthly returns compound
  to the YTD; SPY total return beats its price return (distributions
  reinvested); bounds hold on all 10 series; November totals
  $1.00/share; 25 upcoming payments; next pays Mon Nov 9; the CSV
  round-trips history.json exactly; the display contract (every field
  stats-display.js reads is present) holds; CLI errors exit 1/2.
- `tests/test_stats_display.js` (Node, also run by the Python suite):
  **83 checks, all pass.** Renders today's stats.json and asserts the
  HTML carries the numbers (YTD, best/worst, drawdown, vol, monthly,
  Pulse $, badge, dividend, CSV link), with no `undefined`/`null`
  leaking, and empty stats rendering nothing — plus the Spot note
  ("Spot BTC book … not the selected ETF vehicle"), the explanatory
  note rendered in-page, and the dividend per-day amount in its
  modelled form ("modelled ~$0.0333/share") with the caveat
  ("pending source-confirmed payable precision") visible.
- **In-page check (Playwright, rework #2): 4/4 combos pass**
  (1280px + 390px × dark + light, route interception with a REAL
  stats.json generated from the live data-branch history, as before).
  In every combo the Spot note and the explanatory note are VISIBLE in
  the rendered section, the modelled label and its caveat are VISIBLE,
  the declared $1.00/share total is retained, no horizontal overflow
  at 390px, and the only console errors are the sandbox-blocked live
  feeds (`ERR_TUNNEL_CONNECTION_FAILED`).
- **Real data (2026-11-06, re-generated from the current data-branch
  history):** 215 closes; 10 series; 25 upcoming STRC payments;
  1 badge. Berkshire −10.12% YTD, Hodler −11.28%, HF −11.55%,
  Saylor −1.88%; BTC −13.46%, SPY +8.67%, QQQ +7.16%, BRK.B +13.58%,
  MSTR −15.15%, Gold −6.00%. (Sleeve/BTC YTDs moved a few hundredths
  vs the original build because the data-branch history's Nov 6 closes
  were refreshed after it; the values are hand-checked against the
  current history.)
- **No regressions:** `tests/test_cmp.js` (108 checks, 7 fail),
  `tests/test_oi001_label.js` (31 checks, 3 fail),
  `tests/test_cmp_daily.py` (17 checks, 1 fail) and
  `tests/test_freeze.py` (191 checks, 1 fail) give the SAME results on
  this branch as on clean main `eb9edfd` — the failures are pre-existing
  (stale daily-vs-weekly closes, and the one known freeze failure the
  slice-2 note already records). This branch touches no data file and
  no compare.js. `prices.yml` is untouched.

## Proposed prices.yml wiring (NOT applied — for your review)

One step in the fetch job, after the history is built and the slice-1
gate passes, writing to the data branch alongside history.json:

```yaml
- name: Pre-computed stats + CSV (slice 3)
  run: |
    python3 tools/stats.py \
      --history work/history.json \
      --ledger assets/js/ledger.js \
      --out-stats work/stats.json \
      --out-csv work/history.csv
    # commit stats.json + history.csv to the data branch with the history
```

The tool only changes its outputs when the history changes, so running
it on each history update is enough (it need not run every 5 minutes).
The display needs no wiring: it fetches stats.json from the data branch
and stays hidden until the file exists. The step runs AFTER slice 1's
validate gate passes on the history being used, and only when that
validated history changed; the tool records the input history's SHA-256
in stats.json (`history_sha256`), so the published stats can always be
traced to the exact validated history they were computed from.

## Open questions for Grok + Chief

1. Badges in stats.json (built here) or merged into prices.json (as the
   plan says)? The fetch job rewrites prices.json every 5 minutes, so a
   merge needs care.
2. Homepage Pulse: the Pulse context values are in stats.json — should
   the homepage Pulse pick them up (a small s6.js addition), or keep
   Pulse live-only and the context on Compare?
3. Monthly table shows sleeves only; benchmarks' monthly returns are in
   stats.json but not displayed. Fine, or add a benchmark monthly view?

Settled in rework #2 (no longer open): volatility is sample std of daily
returns × √252; the tool runs only when the validated history changes
(after the slice-1 gate); stats are Spot-only; the CSV is closes only
with the fixed column order above.
