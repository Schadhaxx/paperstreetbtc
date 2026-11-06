# Python supercharge, slice 2 — review note for Grok Bot + Chief of Staff

**Status:** proposal for review. Test branch only. Nothing here is live, the
live pipeline (`.github/workflows/prices.yml`) is NOT changed, and nothing
deploys without Grok Bot + Chief of Staff review and Sunil's separate yes.

**Branch:** `pepper-python-supercharge-s2` (based on main `a4a0a76f`)
**Plan:** `python-supercharge-plan-2026-10-27.md`, Part 4 item 2 (Part 1 recs 1, 2, 4)
**Slice 1:** `pepper-python-supercharge-s1` (validate-before-publishing) — this
slice is designed to fit it; see "How slice 2 fits with slice 1" below.

## What slice 2 is, in one line

When Yahoo's final bar for a session never arrives, the recap stalls — the
pipeline fills the BTC close from a fallback, marks the date provisional, and
the recap (built from FINAL closes only) never advances past it. After 48+
hours, a Tiingo-confirmed value freezes the recap so the site keeps moving,
visibly tagged "Tiingo-final, Yahoo pending". Yahoo can still replace it
later. The OI-001 labelling half of this slice is already live (deployed
Fri 6 Nov 2026 morning); this is the un-stall half.

## What was built (7 files, nothing else)

- `tools/tiingo_unstall.py` — the freeze tool. Stdlib only, runnable locally.
  CLI: `python3 tools/tiingo_unstall.py --history <candidate>
  [--prev-history <published>] [--out <out>] [--now <ISO>]
  [--max-calls N] [--stall-hours N] [--dry-run]`. Exit 0 = done (frozen,
  carried, or nothing to do), 1 = input unreadable/unwritable (file
  untouched), 2 = usage error.
- `tools/recap_gen.py` — Tiingo-final dates count as final for the recap
  (they were previously excluded as provisional, so the recap could not
  advance). The recap note names them separately: "Tiingo-final (confirmed
  by Tiingo, Yahoo's final bar pending): Nov 4." High/low "(provisional)"
  markers cover them too.
- `tools/recap_lib.py` — `expected_months(C, prov, tf=None)`; a Tiingo-final
  date counts as final for the expected-months list (optional parameter,
  backward compatible).
- `tools/btc_daily.py` — a Tiingo-final date no longer trips the 48 h stall
  alarm (exit 3) and no longer pauses appending later days, while STAYING in
  the provisional list (it is still waiting for Yahoo). It takes
  history.json's frozen value, so btc-daily.json and history.json agree on
  the value (one canonical value); a Yahoo bar of its own, if present, wins.
- `tests/test_recap.py` — the "ME is a FINAL close" check now accepts a
  Tiingo-final ME.
- `tools/datatest.py` — passes the tiingo_final set to `expected_months`
  (one line, consistency only).
- `tests/test_tiingo_unstall.py` — 34 checks, no network, no key. Run with
  `python3 tests/test_tiingo_unstall.py` (exit 0 = all pass).
- This review note. No change to `prices.yml`, no site change, no new vendor,
  no API key anywhere near site JavaScript or logs.

## The freeze, precisely

A BTC date is stalled when it is in `btc_provisional` more than 48 h after
its UTC day ended (the same clock `btc_daily.py` uses). For each stalled
date, oldest first, the tool fetches the Tiingo close for that date ONLY and
checks it against the value already published (the fallback value):

- Tiingo agrees within 0.3% (the BTC reference tolerance) and the value is
  sane (positive, finite, within 40% of the previous session — the same band
  `build_history` uses): the date is recorded in a new top-level field:

```json
"tiingo_final": {"2026-11-02": {"BTC": 75799.14, "tiingo": 75801.55,
                                "diff_pct": 0.0032,
                                "confirmed": "2026-11-04T23:30:00Z"}}
```

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
   Tiingo-final value ("Spot BTC (close from backup source until Yahoo's
   final bar)"), which is accurate. The specific "Tiingo-final, Yahoo
   pending" wording is in the data (the `tiingo_final` field) and on the
   recap page note; a frontend slice can render it elsewhere later.
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
5. **A Tiingo-final month can finalize.** If a Tiingo-final date is the last
   session of a month, `recap_gen.py` finalizes that month on it (with the
   Tiingo-final note on the page). The alternative — leaving the month
   "month to date" forever until Yahoo arrives — would mean the recap had
   not really advanced. Flagged here as a decision for Grok + Chief; the
   code is one condition in `recap_gen.py` if you prefer the other way.
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
(`tools/validate.py` from the `pepper-python-supercharge-s1` branch) against
a synthetic full history (every NYSE session 2025-12-31..2026-11-06) with a
Tiingo-final date: **all 7 checks pass, exit 0** (check 6 provisional:
pass — the date is fallback-tagged AND in `btc_provisional`, exactly the
direction check 6 enforces). No slice-1 change is needed. One follow-up for
Grok + Chief: whether validate.py should gain a check that `tiingo_final`
entries are well-formed (date in provisional, value matches closes, tag
present) — the gate does not inspect the new field today, so a malformed
freeze would pass silently. That check belongs in slice 1's file, not here,
so it is a question, not a change in this branch.

## Verification

- `tests/test_tiingo_unstall.py`: **34 checks, 0 failed.** No network, no
  key (stubbed Tiingo responses; the `btc_daily` stall behaviour is
  exercised through `--check-only`, which never fetches). Pass/fail matrix:
  no stalled dates (no-op); fresh provisional < 48 h (not frozen, no call);
  agree within 0.3% (frozen, 1 call, value/tag/provisional untouched,
  `tiingo_ref` cached); exactly +0.3% (frozen — threshold is strictly
  greater); disagree +1.33% (NOT frozen, disagreement recorded); Tiingo
  returns nothing / fetch fails (NOT frozen, no crash); Tiingo +50% vs
  previous session (NOT frozen, sanity band); already frozen, value
  unchanged (carried forward, 0 calls); frozen value changed (re-verified,
  re-frozen at the new value; disagrees → old freeze dropped); Yahoo
  replaced it (dropped from `tiingo_final`); no key (no new freeze,
  carry-forward still works); budget 5 for 6 newly stalled (oldest 5
  frozen, 6th skipped); stall boundary (exactly 48 h: frozen; 1 minute
  before: not stalled); CLI end-to-end (exit 0 without a key,
  carry-forward written to `--out`, `--dry-run` writes nothing, malformed
  history.json → exit 1, file untouched); `btc_daily --check-only`
  (stalled fallback → exit 3; Tiingo-final → exit 0, named in the log);
  validate-gate fit (see above).
- **End-to-end recap (staging copy, real data):** history truncated to
  Nov 4 with Nov 4 provisional + fallback-sourced. Without `tiingo_final`,
  `recap_gen.py` builds through Nov 3 (stalled). With `tiingo_final` for
  Nov 4, it builds through Nov 4 (`ME='2026-11-04'`), the page carries
  "Tiingo-final (confirmed by Tiingo, Yahoo's final bar pending): Nov 4",
  and `tests/test_recap.py` passes **276/276** against it. Without
  `tiingo_final` the same staging run reports "up to date (through
  2026-11-05)" with zero Tiingo-final mentions — the normal path is
  unchanged.
- **Real data:** slice-1 validate.py against today's actual data-branch
  `history.json` (215 closes) + `prices.json` + the real `ledger.js`:
  **all 7 checks pass, exit 0** (unchanged behaviour — no stall today).
- **No regressions:** `tests/test_tiingo.py` 43/43; `tests/test_recap.py`
  276/276 on the real history; `tests/test_freeze.py` 191 checks with the
  SAME single failure as clean main (`FAIL 24 recap: a provisional
  btc-daily day is named in the BTC card note` — pre-existing, reproduced
  on an unmodified main checkout, not caused by this branch).
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
      - name: Tiingo un-stall (slice 2 — freeze a >48 h stalled BTC close on Tiingo confirmation)
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
Final-close check's `lastf()` treats a Tiingo-final date as final:

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

1. Month finalization on a Tiingo-final close (decision 5 above) — finalize
   the month, or hold it "month to date" until Yahoo arrives?
2. Total Tiingo budget: the reference check's 9 calls/run plus up to 5
   un-stall calls in the rare stall case (typical run: 0). Acceptable on
   the current Tiingo plan, or should the un-stall budget be lower?
3. Should slice 1's validate.py gain a well-formedness check for
   `tiingo_final` entries (see "How slice 2 fits with slice 1")?
4. Stocks: keep the tool BTC-only (recommended — only BTC stalls the
   recap), or extend to stocks for completeness?
5. The first real freeze cannot be fully proven until a stall happens. When
   it does, who watches the Actions log — Grok Bot, Chief, or Pepper?
