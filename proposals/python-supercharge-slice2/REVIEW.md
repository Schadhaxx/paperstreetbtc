# Python supercharge, slice 2 — review note for Grok Bot + Chief of Staff

**Status:** rework for Grok Bot review #2 (final review). Test branch only.
Nothing here is live, the live pipeline (`.github/workflows/prices.yml`) is
NOT changed, and nothing deploys without Grok Bot + Chief of Staff review
and Sunil's separate yes.

**Branch:** `pepper-python-supercharge-s2` (rebased onto main `eb9edfd`; was
based on `a4a0a76f` — the rebase was clean, main's change since was a data
refresh only)
**Review #2 changes:** boundary is strictly MORE than 48 h; malformed Tiingo
confirmations are rejected and recorded as disagreements; renamed
Tiingo-final → Tiingo-confirmed in all user-facing text (the internal field
`tiingo_final` is kept — see "The freeze, precisely"); month finalization on
a Tiingo-confirmed close built as ALLOWED per Sunil's decision, with explicit
pending-Yahoo disclosure on the recap page.
**Plan:** `python-supercharge-plan-2026-10-27.md`, Part 4 item 2 (Part 1 recs 1, 2, 4)
**Slice 1:** `pepper-python-supercharge-s1` (validate-before-publishing) — this
slice is designed to fit it; see "How slice 2 fits with slice 1" below.

## What slice 2 is, in one line

When Yahoo's final bar for a session never arrives, the recap stalls — the
pipeline fills the BTC close from a fallback, marks the date provisional, and
the recap (built from FINAL closes only) never advances past it. More than 48
hours after the session's UTC day ends, a Tiingo-confirmed value freezes the
recap so the site keeps moving, visibly tagged "Tiingo-confirmed, Yahoo's
final bar pending". Yahoo can still replace it later. The OI-001 labelling
half of this slice is already live (deployed Fri 6 Nov 2026 morning); this is
the un-stall half.

## What was built (7 files, nothing else)

- `tools/tiingo_unstall.py` — the freeze tool. Stdlib only, runnable locally.
  CLI: `python3 tools/tiingo_unstall.py --history <candidate>
  [--prev-history <published>] [--out <out>] [--now <ISO>]
  [--max-calls N] [--stall-hours N] [--dry-run]`. Exit 0 = done (frozen,
  carried, or nothing to do), 1 = input unreadable/unwritable (file
  untouched), 2 = usage error. A stalled date freezes only strictly more
  than 48 h after its UTC day ended (exactly 48 h does not freeze). A
  malformed Tiingo confirmation (missing close, non-numeric close, wrong
  date, value outside the sanity band) is rejected and recorded as a
  disagreement — never frozen, never silently accepted.
- `tools/recap_gen.py` — Tiingo-confirmed dates count as final for the recap
  (they were previously excluded as provisional, so the recap could not
  advance). The recap note names them separately: "Tiingo-confirmed
  (Yahoo's final bar pending): Nov 4." High/low "(provisional)"
  markers cover them too. When a month finalizes on a Tiingo-confirmed
  month-end close, the page discloses it explicitly: "This month is final
  on a Tiingo-confirmed close; Yahoo's final bar is still pending."
- `tools/recap_lib.py` — `expected_months(C, prov, tf=None)`; a
  Tiingo-confirmed date counts as final for the expected-months list
  (optional parameter, backward compatible).
- `tools/btc_daily.py` — a Tiingo-confirmed date no longer trips the 48 h
  stall alarm (exit 3) and no longer pauses appending later days, while
  STAYING in the provisional list (it is still waiting for Yahoo). It takes
  history.json's frozen value, so btc-daily.json and history.json agree on
  the value (one canonical value); a Yahoo bar of its own, if present, wins.
- `tests/test_recap.py` — the "ME is a FINAL close" check now accepts a
  Tiingo-confirmed ME.
- `tools/datatest.py` — passes the tiingo_final set to `expected_months`
  (one line, consistency only).
- `tests/test_tiingo_unstall.py` — 52 checks, 0 failed, no network, no key.
  Run with `python3 tests/test_tiingo_unstall.py` (exit 0 = all pass).
  The slice-1 check-5 conflict (section 17b) is RESOLVED — see "How slice
  2 fits with slice 1".
- This review note. No change to `prices.yml`, no site change, no new vendor,
  no API key anywhere near site JavaScript or logs.

## The freeze, precisely

A BTC date is stalled when it is in `btc_provisional` strictly more than
48 h after its UTC day ended (the same clock `btc_daily.py` uses — exactly
48 h does NOT freeze; 48 h + 1 min does). For each stalled date, oldest
first, the tool fetches the Tiingo close for that date ONLY and checks it
against the value already published (the fallback value):

- Tiingo agrees within 0.3% (the BTC reference tolerance) and the value is
  sane (positive, finite, within 40% of the previous session — the same band
  `build_history` uses): the date is recorded in a new top-level field:

```json
"tiingo_final": {"2026-11-02": {"BTC": 75799.14, "tiingo": 75801.55,
                                "diff_pct": 0.0032,
                                "confirmed": "2026-11-04T23:30:00Z"}}
```

The field is named `tiingo_final` and the name is KEPT: slice 1's validate
gate, `recap_gen.py`, `btc_daily.py`, and the proposed `prices.yml` wiring
all read that name, so renaming it would break the fit for no user-visible
gain. Every user-facing string instead says "Tiingo-confirmed" — the recap
page note, the btc-daily log line, and this note — and no Tiingo-confirmed
value is ever presented as a Yahoo-final close.

- The published value NEVER changes. Tiingo confirms it; it does not replace
  it. Nothing is ever rewritten to Tiingo closes. The date STAYS in
  `btc_provisional` and its `fallback_sources` tag is left exactly as it was
  (it records which source supplied the value; Tiingo only confirmed it).
- When Yahoo's final bar eventually arrives, the existing pipeline replaces
  the value (with a `fallback (...) replaced by primary` revision entry),
  drops it from `btc_provisional`, and this tool drops it from
  `tiingo_final` on the next run. Yahoo always wins in the end.

When a date is NOT frozen — Tiingo disagrees beyond 0.3%, Tiingo returns
nothing, the fetch fails, the Tiingo value is implausible, or the call
budget is spent — the date stays stalled and provisional, exactly as today.
A disagreement is printed as a `::warning::` and recorded in the report; it
is a data event for a human, not something to freeze over. The tool never
fails the run for a disagreement.

A malformed Tiingo confirmation is rejected the same way and recorded as a
disagreement — never frozen, never silently accepted. Malformed means: the
confirmation row is missing its close, the close is non-numeric, every row
is for the wrong date, or the value is outside the sanity band. (No rows at
all is different: "Tiingo returned nothing" is an absence, recorded as a
skip, not a disagreement.) Every disagreement record carries a `reason`
field. A carried-forward freeze from the previous published history is
trusted only if it is well-formed (date in provisional, value matches the
published close, numeric Tiingo value); a malformed carried record is
dropped, never trusted, and the date is re-verified (or skipped if there is
no key / the budget is spent).

## Design decisions (for your review)

1. **The date stays in `btc_provisional`.** This was the key design call, and
   it was forced by two facts found while building:
   - `recap_gen.py` builds from FINAL closes only, excluding provisional
     dates — so removing a date from `btc_provisional` alone would NOT have
     un-stalled the recap; `recap_gen.py` would still have excluded it.
     The freeze has to be a positive record (`tiingo_final`) that the
     recap, the final-close check, and `btc_daily.py` all read.
   - Slice 1's validate gate, check 6, FAILS a run where a fallback-tagged
     date is not in `btc_provisional`. Keeping the date provisional means
     slice 1 passes unchanged — no gate change, no cross-branch edit.
   The site therefore keeps showing the OI-001 backup-source label for a
   Tiingo-confirmed value ("Spot BTC (close from backup source until Yahoo's
   final bar)"), which is accurate. The specific "Tiingo-confirmed, Yahoo's
   final bar pending" wording is in the data (the `tiingo_final` field) and
   on the recap page note; a frontend slice can render it elsewhere later.
2. **Tiingo confirms, never writes.** The tool only ever freezes the value
   the pipeline already published. If the published value and Tiingo
   disagree, nothing freezes. This is the conservative reading of plan rec 1
   ("allow a Tiingo-confirmed value to freeze") and it means the tool cannot
   inject a price the pipeline never published.
3. **Call budget: newly stalled dates only (plan rec 4).** At most
   `--max-calls` (default 5) per run, oldest first. A date already frozen is
   carried forward from the previous published history.json with NO new call,
   as long as the published value is unchanged (a changed value needs fresh
   confirmation). The fetch is also written into the existing `tiingo_ref`
   cache (same `{v, t}` shape the reference cross-check uses), so when the
   date later becomes Yahoo-final the reference check reuses it instead of
   calling again. Typical run: 0 un-stall calls (a stall is rare); worst
   case 5, on top of the reference check's existing 9.
4. **BTC only.** The recap gate is BTC-driven (`btc_provisional`); a missing
   stock bar does not stall the recap — it holds the run or keeps the
   published value. Extending to stocks is a small change (the daily
   endpoint is already in the plan's symbol list) if you ever want it.
5. **A Tiingo-confirmed month can finalize — CONFIRMED (Sunil, Nov 2026).**
   If a Tiingo-confirmed date is the last session of a month, `recap_gen.py`
   finalizes that month on it, and the page discloses it explicitly: "This
   month is final on a Tiingo-confirmed close; Yahoo's final bar is still
   pending." — in addition to the per-date note "Tiingo-confirmed (Yahoo's
   final bar pending): Oct 30." BTC-only, at most five extra calls (the
   finalization itself costs no extra calls beyond the freeze). The
   alternative — leaving the month "month to date" forever until Yahoo
   arrives — was rejected by Sunil's decision; see open question 1, now
   decided.
6. **No key, no new freeze — but the freeze is durable.** If
   `TIINGO_API_KEY` is unset, the tool prints a warning and freezes nothing
   new, but already-frozen dates are still carried forward (they were
   verified when frozen; re-confirmation every run would burn calls).
7. **The tool never fails the price update.** A read/write failure exits 1
   with history.json untouched; a disagreement or a missing key is a skip,
   exit 0. In the proposed wiring the step degrades to today's behaviour
   (recap stays stalled) with a warning, rather than failing the run.

## How slice 2 fits with slice 1 (validate gate)

The validate gate runs AFTER the un-stall step in the proposed wiring, on
the same candidate history.json. Verified with the actual slice-1 gate
(`tools/validate.py` from the `pepper-python-supercharge-s1-r2` branch —
8 checks, with the batch-corrections narrow rule) against a synthetic full
history (every NYSE session 2025-12-31..2026-11-06) with a Tiingo-confirmed
date.

**Cross-slice conflict — RESOLVED (Grok Bot correction 1).** The rework-2
gate hard-failed ANY `tiingo_ref` entry for a provisional date
("confirmation for a provisional date"), on the premise that confirmations
only exist for final closes. That premise is true of the reference
cross-check, but false of slice 2's freeze cache: when the tool freezes a
date it also writes the fetch into `tiingo_ref` (same `{v, t}` shape), so
the reference check can reuse it once the date becomes Yahoo-final. A
history exactly as this tool writes it therefore FAILED the rework-2 gate
(exit 1, hold) — every freeze would have been held.

The resolution is NARROWER than the exemption recommended here in rework 2
(it is not "exempt `tiingo_final` dates" on key presence alone): slice 1's
`check_tiingo` now permits a BTC `tiingo_ref` entry on a provisional date
ONLY with a FULLY VALIDATED `tiingo_final` freeze for that date (see
`validate.py` `_validated_freeze`): the freeze's `BTC` exactly equals the
published close, its `tiingo` exactly equals the cached reference value,
agreement within 0.3%, valid timestamps for both the cached `t` and the
freeze's `confirmed`, a finite `diff_pct` if present, and the Tiingo value
inside the sanity band vs the previous session's close. A missing record,
or any failed sub-check, still FAILS — including a recorded miss
(`v: null`) on a provisional date, which has no validated confirmation to
permit it. A fully validated freeze falls through to the normal comparison
(counted as compared; it passes). Validate BEFORE downstream tools trust a
confirmation key: the pipeline order is un-stall → validate gate →
publish → recap/`btc_daily` read the published file, so downstream tools
only ever see validated generations. `tests/test_tiingo_unstall.py`
section 17b (the hand-built as-written frozen history) now passes, and the
new 17c runs the ACTUAL `tu.unstall` with a stub getter agreeing +0.1% on
the stalled 2026-11-04, JSON round-trips its real output, and passes it
through the gate. No change to this tool was needed for the resolution —
the freeze it writes already carries everything the narrow rule validates.

Check 6 (provisional) is time-based: a provisional tag on a date whose UTC
day has ended (+20 min) is a "stale tag" FLAG (not a hold). Slice 2 keeps
the Tiingo-confirmed date in `btc_provisional` by design (decision 1
above), so a frozen history always carries that flag. The flag does not
hold the run.

Open question 4 below is answered by the same change: the gate DOES now
inspect `tiingo_final` — check 5's narrow validation fully validates the
freeze record before permitting the reference, so a malformed freeze
written by another route fails the gate instead of passing silently.

## Verification

- `tests/test_tiingo_unstall.py`: **52 checks, 0 failed.** No network, no key
  (stubbed Tiingo responses; the `btc_daily` stall behaviour is exercised
  through `--check-only`, which never fetches). Pass/fail matrix:
  no stalled dates (no-op); fresh provisional < 48 h (not frozen, no call);
  agree within 0.3% (frozen, 1 call, value/tag/provisional untouched,
  `tiingo_ref` cached); exactly +0.3% (frozen — threshold is strictly
  greater); disagree +1.33% (NOT frozen, disagreement recorded, with a
  reason); Tiingo returns nothing / fetch fails (NOT frozen, no crash);
  Tiingo +71% vs previous session (NOT frozen, sanity band, disagreement
  recorded); already frozen, value unchanged (carried forward, 0 calls);
  frozen value changed (re-verified, re-frozen at the new value; disagrees →
  old freeze dropped); Yahoo replaced it (dropped from `tiingo_final`); no
  key (no new freeze, carry-forward still works); budget 5 for 6 newly
  stalled (oldest 5 frozen, 6th skipped); stall boundary (exactly 48 h: NOT
  stalled, not frozen; 48 h + 1 min: frozen; 1 minute before: not stalled);
  malformed confirmations (missing close field, non-numeric close,
  wrong-date row → each NOT frozen, disagreement recorded with a malformed
  reason, date stays provisional, value untouched; `main()` survives one end
  to end — exit 0, warning printed, nothing frozen); CLI end-to-end (exit 0
  without a key, carry-forward written to `--out`, `--dry-run` writes
  nothing, malformed history.json → exit 1, file untouched);
  `btc_daily --check-only` (stalled fallback → exit 3; Tiingo-confirmed →
  exit 0, named in the log); validate-gate fit (freeze record alone: gate
  exit 0, no check fails, check 6 flags the by-design provisional tag;
  as-written frozen history with the `tiingo_ref` cache: gate exit 0, no
  check fails — the cross-slice conflict is RESOLVED by the narrow rule,
  section 17b; real un-stall output — the actual `tu.unstall` with a stub
  getter agreeing +0.1% on the stalled 2026-11-04, JSON round-tripped —
  passes the gate, section 17c); month finalization (see below).
- **End-to-end recap (staging copy, real data):** history truncated to
  Nov 4 with Nov 4 provisional + fallback-sourced. Without `tiingo_final`,
  `recap_gen.py` builds through Nov 3 (stalled). With `tiingo_final` for
  Nov 4, it builds through Nov 4 (`ME='2026-11-04'`), the page carries
  "Tiingo-confirmed (Yahoo's final bar pending): Nov 4",
  and `tests/test_recap.py` passes **276/276** against it. Without
  `tiingo_final` the same staging run reports "up to date (through
  2026-11-05)" with zero Tiingo-confirmed mentions — the normal path is
  unchanged.
- **End-to-end month finalization (staging copy, synthetic history through
  Fri Oct 30 2026, the last NYSE session of the month):** with Oct 30
  provisional + Tiingo-confirmed, `recap_gen.py` finalizes October (title
  "October 2026 Recap", no "month to date"), the page carries
  "Tiingo-confirmed (Yahoo's final bar pending): Oct 30" and the disclosure
  "This month is final on a Tiingo-confirmed close; Yahoo's final bar is
  still pending." Without the confirmation the same staging run stays
  month-to-date through Oct 29 with no finalization disclosure.
- **Real data:** slice-1 validate.py against today's actual data-branch
  `history.json` (215 closes) + `prices.json` + the real `ledger.js`:
  **all 7 checks pass, exit 0** (unchanged behaviour — no stall today).
- **No regressions:** `tests/test_tiingo.py` 43/43; `tests/test_recap.py`
  276/276 on the real history; `tests/test_freeze.py` 191 checks with the
  SAME single failure as clean main (`FAIL 24 recap: a provisional
  btc-daily day is named in the BTC card note` — pre-existing, reproduced
  on an unmodified main checkout, not caused by this branch; re-verified
  identical on clean main `eb9edfd` after the rebase).
- **Not verified live:** the real Tiingo API call (no key in this sandbox,
  and no stall is happening today to freeze). The request is byte-identical
  to the reference check's existing BTC call (same endpoint, same
  parameters, same raw-close parsing), and the stub tests cover the
  response handling — but the first real freeze should be watched in the
  Actions log when it happens.

## Proposed prices.yml wiring (NOT applied — for your review)

Two additions, no rewrite. The fetch job checks out only the data branch,
so the tool is fetched from main:

```yaml
      - name: Tiingo un-stall (slice 2 — freeze a strictly->48 h stalled BTC close on Tiingo confirmation)
        if: steps.gate.outputs.run == '1'
        env:
          TIINGO_API_KEY: ${{ secrets.TIINGO_API_KEY }}   # this step ONLY, same as the reference check
        run: |
          cd work
          git show HEAD:history.json > /tmp/hist_prev.json 2>/dev/null || echo '{}' > /tmp/hist_prev.json
          git fetch -q --depth 1 origin main
          git show FETCH_HEAD:tools/tiingo_unstall.py > /tmp/tiingo_unstall.py
          python3 /tmp/tiingo_unstall.py --history history.json --prev-history /tmp/hist_prev.json || echo "::warning::tiingo-unstall failed; history.json unchanged, recap stays stalled as today"
```

Placed after "Fetch prices", before "Final-close check". And the
Final-close check's `lastf()` treats a Tiingo-confirmed date as final:

```python
        def lastf(p):
            try:
                h = json.load(open(p)); pv = set(h.get('btc_provisional') or [])
                tf = set((h.get('tiingo_final') or {}).keys())
                return max(d for d in h['closes'] if d not in pv or d in tf)
            except Exception: return ''
```

The recap job needs no wiring change: it already fetches data-branch
history.json and runs `btc_daily.py` / `recap_gen.py` from main, both of
which now read `tiingo_final`. The weekend stall-check job needs no change
either. The validate gate (slice 1) runs after the un-stall step, as above.

## Open questions for Grok + Chief

1. Month finalization on a Tiingo-confirmed close (decision 5 above) —
   DECIDED (Sunil, Nov 2026): ALLOW — a Tiingo-confirmed close CAN finalize
   a month, with explicit pending-Yahoo disclosure, BTC-only, at most five
   extra calls. Built as allowed.
2. Slice-1 check 5 vs slice 2's `tiingo_ref` cache (see "How slice 2 fits
   with slice 1") — DECIDED (Grok Bot correction 1): the narrow rule. A
   BTC `tiingo_ref` entry on a provisional date is permitted ONLY with a
   fully validated `tiingo_final` freeze (exact BTC/Tiingo match, ≤0.3%,
   valid timestamps, sanity band, finite `diff_pct`) — NOT a blanket
   exemption of `tiingo_final` dates. The cache stays: dropping it would
   cost one re-fetch when the date later becomes Yahoo-final.
3. Total Tiingo budget: the reference check's 9 calls/run plus up to 5
   un-stall calls in the rare stall case (typical run: 0). Acceptable on
   the current Tiingo plan, or should the un-stall budget be lower?
4. Should slice 1's validate.py gain a well-formedness check for
   `tiingo_final` entries (see "How slice 2 fits with slice 1")? —
   ANSWERED by the narrow rule: check 5 now fully validates the
   `tiingo_final` record before permitting a provisional-date reference,
   so a malformed freeze written by another route fails the gate.
5. Stocks: keep the tool BTC-only (recommended — only BTC stalls the
   recap), or extend to stocks for completeness?
6. The first real freeze cannot be fully proven until a stall happens. When
   it does, who watches the Actions log — Grok Bot, Chief, or Pepper?
