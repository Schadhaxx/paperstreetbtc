# Python supercharge, slice 1 — review note for Grok Bot + Chief of Staff

**Status:** proposal for review. Test branch only. Nothing here is live, the
live pipeline (`.github/workflows/prices.yml`) is NOT changed, and nothing
deploys without Grok Bot + Chief of Staff review and Sunil's separate yes.

**Branch:** `pepper-python-supercharge-s1` (based on main `a4a0a76f`)
**Spec:** `python-supercharge-slice1-prelim-spec.md` (4 Nov 2026, preliminary)
**Plan:** `python-supercharge-plan-2026-10-27.md`, Part 4 item 1

## What slice 1 is, in one line

Before any new price bar goes live, a Python check passes or holds it — and a
small health file says, in one place, when each price last updated, from
which source, and whether anything is being held. This closes the gap the
2 Nov failure exposed (bad bars patched after the fact).

## What was built (3 files, nothing else)

- `tools/validate.py` — the gate. Stdlib only, pure checks, runnable locally.
  CLI: `python3 tools/validate.py --history <candidate> --prices <candidate>
  [--prev-history <published>] [--prev-prices <published>]
  [--ledger <assets/js/ledger.js>] --out-health <health.json>
  [--publish-to <dir>] [--now <ISO>]`. Exit 0 = publish, 1 = held, 2 = usage
  error (a required input file is missing).
- `tests/test_validate.py` — 54 checks, no network, no browser. Run with
  `python3 tests/test_validate.py` (exit 0 = all pass).
- This review note. No change to `prices.yml`, no site change, no new vendor,
  no API key anywhere near site JavaScript or logs.

## The 7 checks

| # | Check | On failure |
|---|-------|------------|
| 1 | parse — files parse as JSON, required shape (`v` = 1, `closes`, `stocks`), sane sizes; a candidate must never shrink the history (data loss) | hold |
| 2 | sessions — every expected NYSE session present from first to last close (holidays excepted, holiday set reused from `tools/stock_weekly.py`); a missing session fails, it does not silently publish a gap; a close dated in the future also fails | hold |
| 3 | values — no null or non-positive close on a session claimed final; no dropped symbols; live quotes (`c`, `pc`, `t`) finite and positive | hold |
| 4 | jumps — a single-session move over 35% is a split suspect, held for review | hold |
| 5 | tiingo — Yahoo vs Tiingo beyond the existing thresholds (>0.05% stocks, >0.3% BTC) | **flag only, never holds** (see below) |
| 6 | provisional — a fallback-sourced BTC close must carry its provisional tag (OI-001: tag by actual fallback source, not just by time) | hold |
| 7 | dividends — STRC record dates before pay dates, no duplicate ex-dates; history `divs` amounts finite and positive | hold |

On ANY hard failure: hold — keep the previous published file, do not publish
the bad bar, record the reason in health.json. The Actions run itself fails,
so the existing failure-email channel already surfaces it. No new alerting
in slice 1.

## Design decisions (for your review)

1. **Check 5 (Tiingo) does not block.** The gate must not block the pipeline
   on a reference-only failure. A Tiingo disagreement is recorded in the
   validation output and in health.json, but the run still publishes. This
   matches today's pipeline, where a Tiingo difference is a `::warning::`,
   never an error. (The existing prices.yml cross-check against an
   independent source, with different tolerances, is separate and untouched.)
2. **Check 6 enforces the direction the pipeline actually records**
   (fallback source => tagged). It does NOT require the converse
   (provisional => a `fallback_sources` entry), because a close can be
   provisional simply because Yahoo's final bar has not arrived yet. Proof:
   on today's real data, 2026-11-06 is provisional with no `fallback_sources`
   BTC entry. Requiring the converse would fail the gate on good data.
3. **Hold scope is the whole run, not per-symbol.** Partial publishes are
   how inconsistent pages happen. (Spec open question 4 — Grok decides.)
4. **Check 7 needs the STRC ledger** (`assets/js/ledger.js`) as an input;
   without it the STRC part is skipped, not failed. Amount adjudication
   (flat $0.0333 vs published $0.03/$0.04) is deliberately NOT checked — that
   is an open dividend decision, and validation must not fail a run over it.
5. **The holiday set is reused from `tools/stock_weekly.py`** (imported, with
   an embedded copy as fallback). It needs extending each year, same as the
   weekly tools. A weekday beyond the set with no bar is treated as a missing
   session (fail, not silent) — the safe direction.
6. **A missing session trips both check 1 (shrink) and check 2 (sessions).**
   Intentional defence in depth: the shrink rule also catches a rebuild that
   lost early history without leaving a gap in its own range.

## health.json format (frozen in this review)

Written on the **data branch**, alongside `history.json` / `prices.json`
(spec recommendation; see open question 1). Plain values only:

```json
{
  "last_run": "2026-11-06T23:30:00Z",
  "status": "ok",
  "hold_reason": "sessions: missing sessions: 2026-11-04",
  "symbols": {
    "BTC":  {"last_close_date": "2026-11-06", "price_age_minutes": 150,
             "source": "yahoo", "provisional": true},
    "TSLA": {"last_close_date": "2026-11-06", "price_age_minutes": 150,
             "source": "yahoo", "provisional": false},
    "IBIT": {"last_close_date": "2026-11-06", "price_age_minutes": 30,
             "source": "live", "provisional": false}
  },
  "validation": [
    {"check": "parse", "status": "pass", "detail": "215 closes, 17 live stocks"},
    {"check": "tiingo", "status": "flag", "detail": "..."}
  ]
}
```

- `status` is `ok` or `held`; `hold_reason` appears only when held.
- Per symbol: `last_close_date` (latest date with that symbol),
  `price_age_minutes` (minutes from that date's 16:00 ET session close to the
  run, clamped at 0; for live-only symbols, minutes from the quote timestamp),
  `source` (`yahoo`, a fallback name such as `coinbase` /
  `yahoo-unchecked-frozen`, or `live` for intraday quotes in `prices.json`),
  `provisional` (BTC: in `btc_provisional`; others: a `fallback_sources`
  entry on that date).
- `validation` lists all 7 checks with `pass` / `fail` / `flag` / `skip`.
- Site display ("data is 12 minutes old", "BTC provisional") is NOT in
  slice 1 — the file is written only. Display is a later, small frontend
  slice.

## Verification

- `tests/test_validate.py`: **54 checks, 0 failed.** Pass/fail matrix:
  good data passes (exit 0, status ok, all 7 checks ran); each bad-data
  class holds (exit 1, status held, the right check named in `hold_reason`,
  the previous file kept byte-identical) — truncated JSON, missing session,
  zero close, null close, +50% jump, BTC fallback untagged, provisional tag
  for a date with no close, pay-before-record, duplicate ex-date, history
  shrink. Tiingo disagreement flags but does NOT hold (exit 0, candidate
  still published). No ledger supplied → dividends skips, run still passes.
  $0.03 amounts do not fail (open decision). CLI smoke test as a real
  subprocess passes.
- **Real data:** run against today's actual data-branch `history.json`
  (215 closes) + `prices.json` + the real `ledger.js` (44 STRC entries):
  **all 7 checks pass, exit 0.** Tiingo: 45 reference values within
  tolerance. No missing sessions, no null/non-positive closes, no >35%
  jumps. Malformed JSON end-to-end: exit 1, held, with a clear hold_reason.
- Runs from any working directory; `py_compile` clean.

## Proposed prices.yml wiring (NOT applied — for your review)

Build to a temp dir, run the gate, commit only on exit 0:

```yaml
- name: Validate before publishing (slice 1)
  run: |
    python3 tools/validate.py \
      --history work/history.json --prices work/prices.json \
      --prev-history <data-branch history.json> \
      --prev-prices <data-branch prices.json> \
      --ledger assets/js/ledger.js \
      --out-health work/health.json
    # exit 0: commit history.json + prices.json + health.json
    # exit 1: commit only health.json (hold visible), fail the run
```

This is a minimal addition (one step), not a prices.yml rewrite. The
recap job's staging validation stays separate (spec open question 2).

## Open questions for Grok + Chief (from the spec)

1. Health file location confirmed: data branch alongside history/prices
   (recommended here), or main `assets/data/`?
2. Should the recap job's staging validation and this prices-job gate share
   one `validate.py`, or stay separate (recap tests already exist)?
3. Weekly-file validation in slice 1 or deferred? (Not built: validate weekly
   JSONs for monotonic weeks and unchanged old weeks.)
4. Hold behaviour: hold the whole run (recommended here), or hold only the
   offending symbol and publish the rest?
