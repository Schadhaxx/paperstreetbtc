# Python supercharge, slice 5 — review note for Grok Bot + Chief of Staff

**Status:** proposal for review. Test branch only. Nothing here is live, the
live pipeline (`.github/workflows/prices.yml`) is NOT changed, and nothing
deploys without Grok Bot + Chief of Staff review and Sunil's separate yes.

**Branch:** `pepper-python-supercharge-s5` (based on main `70289364` — the
live-feel launch; rebased from the original `a4a0a76f` base after main moved)
**Plan:** `python-supercharge-plan-2026-10-27.md`, Part 4 item 5 (Part 1 recs 3 + 5)
**Slices 1–4:** `pepper-python-supercharge-s1` (validate gate),
`pepper-python-supercharge-s2` (Tiingo un-stall),
`pepper-python-supercharge-s3` (pre-computed stats),
`pepper-python-supercharge-s4` (backtester + anomaly detective) — this
slice fits them; see "How slice 5 fits with slices 1–4" below.

## What slice 5 is, in one line

Live stocks get a second source (Yahoo chart meta when Finnhub fails),
a stale price is labelled with how old it is instead of being shown as
live, and a pipeline stall surfaces as a note instead of failing
silently. Nothing here is a new real-time feed — the plan's honest
limit (Part 3) stands: Python does not turn a free feed into a paid
real-time feed.

## What was built (7 files, nothing else)

- `tools/live_fallback.py` — the Yahoo fallback tool. Stdlib only, no
  key (Yahoo chart is keyless). CLI: `python3 tools/live_fallback.py
  --prices <prices.json> --failed <MSTR,TSLA,...> [--out <prices.json>]
  [--dry-run]`. Exit 0 = done, 1 = input unreadable, 2 = usage error.
- `tools/stall_alert.py` — the stall alert tool. Stdlib only, no
  network, no key. CLI: `python3 tools/stall_alert.py
  --history <history.json> [--prices <prices.json>]
  [--health <health.json>] [--out-health <health.json>]
  [--out <alerts.json>] [--now <ISO>]`. Exit 0 = scan complete
  (alerts or not), 1 = input unreadable, 2 = usage error.
- `assets/js/s6.js` — the staleness display (Part 2, minimal): the
  cached-stocks label now reads "last updated X min ago" when stale,
  and a single stock's label names its fallback source and its own
  staleness. `s6.js?v=p3` → `p4` on `index.html` (its only caller).
- `index.html` — s6.js pin bump only.
- `tests/test_live_fallback.py` — 23 checks, no network (stubbed Yahoo).
- `tests/test_stall_alert.py` — 24 checks, no network.
- This review note. No change to `prices.yml`, no new vendor, no API
  key anywhere near site JavaScript or logs.

## Part 1 — live stocks second source (Yahoo chart meta)

Live BTC already has a fallback chain (CoinGecko → Coinbase → keep last
price). Live stocks were Finnhub-only → keep last price. Now, for each
symbol Finnhub fails on, the tool fetches Yahoo chart meta
(`regularMarketPrice`, `regularMarketTime`, prior close = 2nd-to-last
daily bar close — the same definition the fetch job uses for the market
indicators) and, if the price is valid, writes it into prices.json with
a `'src': 'Yahoo'` tag so the site can show where it came from.

**Why Yahoo, not Stooq:** Stooq gives daily closes, not a live intraday
price — using it would present yesterday's close as a live price, which
is exactly the dishonesty this slice is meant to prevent. Yahoo chart
meta gives `regularMarketPrice`, a real live price during market hours,
keyless and free, from a source the pipeline already trusts (the history
rebuild and the market indicators use it).

**A fallback price is never invented and never a stale price presented
as live.** The Yahoo price must be positive and finite, its prior close
must be positive and finite, and it must be within 25% of that prior
close (the same sanity band compare.js uses for lump-sum opens). If
Yahoo fails or returns a bad price, the previous value is kept (today's
behaviour) and the symbol is reported as still stale — the site then
labels it stale (Part 2) instead of showing a frozen price as live.

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
runs, so a reader can tell the check ran. Run this step AFTER the
validate gate in the proposed wiring, so the gate does not overwrite
the alerts field.

This is a REPORTER, not a gate: it never holds a run, never changes a
price, and exits 0 whether or not alerts were found. The recap stall's
hard signal stays btc_daily.py's `::error::` (exit 3); this tool prints
`::warning::` for all its alerts so its own step does not look failed.

## How slice 5 fits with slices 1–4

- **Slice 1 (validate):** the gate still checks published data. A
  Yahoo-fallback stock entry gains only an extra `'src'` field; `c`,
  `pc`, `t` are unchanged in shape. Verified with the actual slice-1
  gate against a prices.json carrying a Yahoo `'src'` entry: **all
  checks pass, exit 0**. No gate change.
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
  Verified with the actual slice-4 detective against the real history
  + a Yahoo-entry prices.json: **no anomalies found**. A Yahoo
  fallback price (fresh `t`) is not flagged stale; a kept-previous
  price (old `t`) is — correctly, because it IS stale.

## Verification

- `tests/test_live_fallback.py`: **23 checks, 0 failed.** No network
  (stubbed Yahoo). Valid Yahoo applied with `'src': 'Yahoo'`; unfailed
  symbols untouched; Yahoo fetch failure / empty result / bad price /
  missing prior close / missing timestamp all keep the previous value;
  +26% vs prior close rejected, +25% (band edge) applied; BRK.B fetched
  as BRK-B; both-fail keeps both; mixed outcomes correct; CLI
  end-to-end (exit 0 when Yahoo fails, file unchanged, `--dry-run`
  writes nothing, malformed prices.json exit 1, missing `--failed`
  exit 2).
- `tests/test_stall_alert.py`: **24 checks, 0 failed.** No network.
  Clean run (no alerts); recap stall found; 48 h boundary (exactly
  48 h not stalled, +1 min stalled); fresh provisional not stalled;
  Tiingo-final gives the info note only, never a stall alert; a stalled
  date and a Tiingo-final date together give both alerts with the right
  severities; prices 90 min old in-window flagged, 30 min not; 60-min
  boundary (exactly 60 not flagged, 61 flagged); prices old at night
  and on Saturday not flagged; no prices.json still finds the recap
  stall; health update preserves fields, sets `last_run` only when
  absent, does not mutate its input; CLI end-to-end.
- **s6.js display logic (Node, stubbed):** 7 cases, all correct —
  cacheLabel stale 42 min reads "(stale — last updated 42 min ago)",
  fresh 10 min shows no stale, market closed shows no stale even when
  old; per-stock Yahoo fresh reads "cached … · Yahoo", kept quote
  45 min old reads "(stale, 45 min ago)", Finnhub fresh is unchanged,
  stale quote with the market closed is not marked. `node --check`
  clean on the modified s6.js.
- **Real data (2026-11-07):** stall_alert.py against the live
  data-branch history.json (215 closes, provisional `2026-11-06`,
  no `tiingo_final`) + prices.json: **no stalls, exit 0** (correct —
  nothing is stalled today). Slice-1 validate.py passes on the
  Yahoo-entry prices.json (above). Slice-4 anomaly.py reports no
  anomalies on the real history + Yahoo-entry prices.json.
- **Not verified live:** the real Yahoo chart-meta call (the sandbox
  blocks external fetches; the CLI end-to-end test therefore exercises
  the keep-previous path, not a live Yahoo success). The request is
  byte-identical to the indicators' existing Yahoo call (same endpoint,
  same parameters, same `regularMarketPrice` / prior-close parsing),
  and the stub tests cover the response handling — but the first real
  Finnhub failure should be watched in the Actions log when it happens.
  The in-page s6.js render (homepage, desktop + 390 px, dark + light)
  was verified by Node logic only, not in a browser — the same gap
  slice 3 had, closed there by a Playwright check; this one still
  needs it before Grok's review.

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
cases). And a stall-alert step after the validate gate, in the same
job, updating health.json:

```yaml
      - name: Stall alerts (slice 5 — recap / prices stalls into health.json)
        run: |
          cd work
          git fetch -q --depth 1 origin main
          git show FETCH_HEAD:tools/stall_alert.py > /tmp/stall_alert.py
          python3 /tmp/stall_alert.py --history history.json --prices prices.json \
            --health health.json --out-health health.json
          # exit 0 whether or not alerts were found; the alerts field is the output
```

The s6.js display ships with the site (pin `p4`); it degrades
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
4. **Health file wiring order:** stall-alert runs AFTER the validate
   gate, so the gate does not overwrite the `alerts` field. Accept, or
   should validate.py preserve an existing `alerts` field instead?
5. **The first real Finnhub failure** cannot be fully proven until one
   happens. When it does, who watches the Actions log — Grok Bot,
   Chief, or Pepper?
6. **s6.js in-page render** still needs a browser check (desktop +
   390 px, dark + light) before this slice is considered verified —
   the Node logic check above covers the strings, not the page.
