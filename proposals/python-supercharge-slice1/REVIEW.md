# Python supercharge, slice 1 — review note for Grok Bot + Chief of Staff

**Status:** rework 2, for final review (Grok Bot review #2). Test branch only.
Nothing here is live, the live pipeline (`.github/workflows/prices.yml`) is
NOT changed, and nothing deploys without Grok Bot + Chief of Staff review
and Sunil's separate yes.

**Branch:** `pepper-python-supercharge-s1` (rebased onto main `eb9edfd9`,
the 7 Nov data refresh; live-feel, OI-001, themes, clock light/CAD/inline,
4H candles, calculator, logos, domain config and financial rules preserved —
the rebase ported only the slice-1 files, no older files wholesale)
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
  [--publish-to <dir>] [--now <ISO>]`. Exit 0 = publish, 1 = held,
  2 = usage error (a required input file is missing).
- `tests/test_validate.py` — 86 checks, no network, no browser. Run with
  `python3 tests/test_validate.py` (exit 0 = all pass).
- This review note. No change to `prices.yml`, no site change, no new vendor,
  no API key anywhere near site JavaScript or logs.

## The 8 checks

| # | Check | On failure |
|---|-------|------------|
| 1 | parse — files parse as JSON, required shape (`v` = 1, `closes`, `stocks`), sane sizes; a candidate must never shrink the history (data loss) | hold |
| 2 | sessions — every expected NYSE session present from first to last close (holidays excepted, holiday set reused from `tools/stock_weekly.py`); a missing session fails, it does not silently publish a gap; a close dated in the future also fails | hold |
| 3 | values — no null or non-positive close on a session claimed final; no dropped symbols; live quotes (`c`, `pc`, `t`) finite and positive | hold |
| 4 | jumps — a single-session move over 35% is a split suspect, held for review | hold |
| 5 | tiingo — Yahoo vs Tiingo beyond the existing thresholds (>0.05% stocks, >0.3% BTC) | **flag only, never holds** (see below); but a **malformed or mismatched confirmation fails** (bad value, missing timestamp, date/symbol with no published close, or a BTC confirmation for a provisional date — confirmations only exist for final closes) |
| 6 | provisional — a fallback-sourced BTC close must carry its provisional tag **while its UTC day is still open** (OI-001); once the day is final the tag is dropped by the pipeline even when the close still came from a fallback, and that passes (see "Check 6 corrected" below) | hold (untagged fallback on an open day); a stale tag on a final date only flags |
| 7 | dividends — STRC record dates before pay dates, no duplicate ex-dates; history `divs` amounts finite and positive | hold |
| 8 | inclusion — the candidate must contain every date and symbol the published file had (a dropped date/symbol fails even when the counts look right), and every session must carry all core symbols (`BTC MSTR STRC TSLA PLTR SPY QQQ BRK.B GLD`); a changed value is reported, and a Yahoo final bar replacing a fallback value is legitimate and passes | hold (dropped date/symbol, missing core symbol) |

On ANY hard failure: hold — keep the previous published file, do not publish
the bad bar, record the reason in health.json. The Actions run itself fails,
so the existing failure-email channel already surfaces it. No new alerting
in slice 1.

## What rework 2 changed (Grok Bot review #2)

1. **Atomic publish.** The gate now stages the complete generation, validates
   the staged copies, and publishes ONE consistent snapshot. `main()` copies
   the candidates into a staging directory inside `--publish-to`, runs all 8
   checks on the staged copies, writes health.json into staging, and only
   then calls `publish_snapshot()`, which installs `history.json` +
   `prices.json` + `health.json` together: each file is read fully into
   memory first, written to a temp file (fsync'd), and installed with an
   atomic rename; if any install step fails, the files already installed
   are rolled back to their previous contents and `PublishError` is raised.
   The old pair stays, or the new pair lands whole — never a mixed pair.
   A test injects a failure between the two writes (patched `os.replace`
   raises on the 2nd call) and proves the published history/prices/health
   stay byte-identical to the previous snapshot, with no temp files left.
   In the workflow the same snapshot is ONE data-branch commit of all three
   files (the commit is the atomic unit; the local publish mirrors it).
   On a hold, only `health.json` is published, so the hold is visible while
   the published data stays untouched.
2. **Safe health writes.** `health.json` is written only through
   `atomic_write()` (temp file in the same directory, flush + fsync, rename
   over the destination, fsync the directory) — a reader never sees a
   partial health file, and a failure mid-write leaves the previous health
   file byte-identical (tested with the same injected failure).
3. **Inclusion (check 8, new).** Sets are compared, not sizes: every
   published date and every published symbol (per date, and every live
   symbol in prices.json) must still be there, and every session must carry
   all core symbols. Tests prove a dropped symbol fails even when the counts
   look right (TSLA removed from every session; a dropped date with an
   identical count; a dropped live symbol).
4. **Legitimate Yahoo replacements allowed.** A changed value vs the
   published file is reported in the inclusion detail, never failed. When
   the previous source was a fallback and the new source is Yahoo/primary,
   it is named a legitimate Yahoo replacement (the pipeline logs these in
   `revisions_ignored` and drops the fallback tag). Tested: a Yahoo final
   BTC 76,200 replacing a published Coinbase 75,731.04 passes, exit 0.
5. **Tiingo confirmations validated (check 5).** A confirmation is now
   validated against the published BTC value, the provisional dates, and
   the reference tolerance — not just compared. Malformed (non-numeric or
   non-positive `v`, missing/unparseable `t`, entry not an object) or
   mismatched (date with no published close, symbol with no close on that
   date, BTC confirmation for a provisional date) now FAILS instead of
   passing silently. A tolerance disagreement still only flags. A recorded
   miss (`v: null` with a valid timestamp) still passes — Tiingo may be
   down or out of calls, and the pipeline explicitly never blocks on it.
   When a candidate value changed vs the previously published file and the
   confirmation matches the OLD published value instead, the flag says so
   ("stale after a Yahoo replacement") instead of looking like a live
   disagreement.

## Check 6 corrected — the original build held on today's real data

The first build required fallback source => tagged, unconditionally. That is
wrong against the pipeline and the site, and real data proves it: the data
branch head (run 2026-11-07 00:20Z) has `2026-11-06: BTC coinbase` in
`fallback_sources` with `btc_provisional: []` — the original gate held on
that file (`provisional: 2026-11-06: BTC fallback-sourced (coinbase) but not
tagged provisional`).

Why: `btc_provisional` is **time-based, not source-based**. The pipeline
lists a date there exactly while its UTC day has not ended
(`final_btc(d)`: now >= date + 1 day + 20 min UTC). Once the day is final the
tag is dropped even when the close still came from a fallback — the
`fallback_sources` entry remains as provenance, and the site label keys on
it (`assets/js/s2.js`: `isBtcFb` reads `fallback_sources`; `BTCPROV =
!!BTCFB || inWin`), so the OI-001 "from backup source until Yahoo's final
bar" label still shows correctly. Check 6 now mirrors the pipeline: an
untagged fallback fails only while its UTC day is still open; an untagged
fallback on a final date passes; a tag left on a final date only flags (a
run straddling the 00:20 UTC boundary could produce one transiently). The
converse is still not required (provisional does not need a
`fallback_sources` entry): a close can be provisional simply because
Yahoo's final bar has not arrived yet.

## Design decisions (for your review)

1. **Check 5 (Tiingo) does not block on disagreement.** The gate must not
   block the pipeline on a reference-only failure. A Tiingo disagreement is
   recorded in the validation output and in health.json, but the run still
   publishes. This matches today's pipeline, where a Tiingo difference is a
   `::warning::`, never an error. (The existing prices.yml cross-check
   against an independent source, with different tolerances, is separate and
   untouched.) What changed in rework 2 is only that a *malformed or
   mismatched* confirmation now fails — a confirmation that cannot
   correspond to any published value is a corrupt file, not a disagreement.
2. **Hold scope is the whole run, not per-symbol.** Partial publishes are
   how inconsistent pages happen. (Spec open question 4 — Grok decides.)
3. **Check 7 needs the STRC ledger** (`assets/js/ledger.js`) as an input;
   without it the STRC part is skipped, not failed. Amount adjudication
   (flat $0.0333 vs published $0.03/$0.04) is deliberately NOT checked — that
   is an open dividend decision, and validation must not fail a run over it.
4. **The holiday set is reused from `tools/stock_weekly.py`** (imported, with
   an embedded copy as fallback). It needs extending each year, same as the
   weekly tools. A weekday beyond the set with no bar is treated as a missing
   session (fail, not silent) — the safe direction.
5. **A missing session trips parse (shrink), sessions, and inclusion.**
   Intentional defence in depth: the shrink rule also catches a rebuild that
   lost early history without leaving a gap in its own range, and inclusion
   names the dropped date. Likewise a dropped date orphans its Tiingo
   reference, so check 5 fails too — a dangling confirmation must not pass
   silently.
6. **A missing Tiingo confirmation is not a failure.** Tiingo only
   cross-checks final closes, may be down, out of calls, or unconfigured,
   and the pipeline explicitly never blocks on it. Only a confirmation that
   IS present but malformed/mismatched fails.

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
- `validation` lists all 8 checks with `pass` / `fail` / `flag` / `skip`.
- Site display ("data is 12 minutes old", "BTC provisional") is NOT in
  slice 1 — the file is written only. Display is a later, small frontend
  slice.

## Verification

- `tests/test_validate.py`: **86 checks, 0 failed** (54 original + 32 new).
  Pass/fail matrix: good data passes (exit 0, status ok, all 8 checks ran);
  each bad-data class holds (exit 1, status held, the right check named in
  `hold_reason`, the previous file kept byte-identical) — truncated JSON,
  missing session, zero close, null close, +50% jump, BTC fallback untagged
  on an open day, provisional tag for a date with no close, pay-before-record,
  duplicate ex-date, history shrink. Tiingo disagreement flags but does NOT
  hold (exit 0, candidate still published). No ledger supplied → dividends
  skips, run still passes. $0.03 amounts do not fail (open decision). CLI
  smoke test as a real subprocess passes.
- **New in rework 2:** failure injected between the two publish writes
  leaves the old history/prices/health byte-identical with no temp files
  left, and the clean path lands the whole new snapshot (also end-to-end
  through `main()` with `--publish-to`, exit 1 on publish failure);
  mid-write health failure leaves the previous health file intact;
  a hold publishes health.json only; TSLA dropped from every session fails
  inclusion with counts unchanged; a dropped date fails even when the count
  matches; a dropped live symbol fails; a Yahoo final replacing a Coinbase
  close passes with the Tiingo flag noting the stale confirmation; a
  fallback BTC close on a final date, untagged, passes; a stale provisional
  tag flags but does not hold; five malformed/mismatched Tiingo classes fail
  (non-numeric value, date with no close, symbol with no close, missing
  timestamp, BTC confirmation for a provisional date); a recorded Tiingo
  miss (`v: null`) passes.
- **Real data:** run against the current data-branch `history.json`
  (215 closes) + `prices.json` + the real `ledger.js` (44 STRC entries):
  **all 8 checks pass, exit 0.** Tiingo: 46 reference values within
  tolerance. No missing sessions, no null/non-positive closes, no >35%
  jumps. (The original build held on this same file — see "Check 6
  corrected" above.) Malformed JSON end-to-end: exit 1, held, with a clear
  hold_reason. A `--publish-to` run on the real data lands
  history+prices+health together with no staging/temp leftovers.
- Runs from any working directory; `py_compile` clean.

## Proposed prices.yml wiring (NOT applied — for your review)

Build to a temp dir, run the gate with `--publish-to` pointing at the
data-branch checkout, commit only on exit 0 — one commit of all three files:

```yaml
- name: Validate before publishing (slice 1)
  run: |
    python3 tools/validate.py \
      --history work/history.json --prices work/prices.json \
      --prev-history <data-branch history.json> \
      --prev-prices <data-branch prices.json> \
      --ledger assets/js/ledger.js \
      --out-health work/health.json \
      --publish-to <data-branch checkout>
    # exit 0: the gate staged, validated and installed history.json +
    #   prices.json + health.json as one snapshot; commit all three together
    # exit 1: only health.json was installed (hold visible), fail the run
```

This is a minimal addition (one step), not a prices.yml rewrite. The
recap job's staging validation stays separate (spec open question 2).

## Open questions for Grok + Chief (from the spec)

1. Health file location confirmed: data branch alongside history/prices
   (recommended here), or main `assets/data/`? — settled default for this
   review: data branch (health/stats/reports live on the data branch).
2. Should the recap job's staging validation and this prices-job gate share
   one `validate.py`, or stay separate (recap tests already exist)?
3. Weekly-file validation in slice 1 or deferred? (Not built: validate weekly
   JSONs for monotonic weeks and unchanged old weeks.)
4. Hold behaviour: hold the whole run (recommended here), or hold only the
   offending symbol and publish the rest? — settled default for this review:
   whole-run validation holds.
5. **New (rework 2):** a stale provisional tag on a final date only flags
   (run-time straddle at the 00:20 UTC boundary). Should it ever hold, or is
   flag-only right?
6. **New (rework 2):** a BTC Tiingo confirmation for a provisional date now
   fails — the pipeline never writes one (it only cross-checks final
   closes), so this fires only on a corrupt or hand-edited file. Confirm
   that fail (not flag) is the right severity.
7. **New (rework 2):** the gate's `--publish-to` installs the snapshot and
   the workflow then commits all three files in one commit. Confirm that
   single-commit shape is acceptable, or say if health.json should be
   committed separately.
