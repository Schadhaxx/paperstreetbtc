# Daily Bollinger — prices.yml wiring (for Grok Bot)

**Prepared by Pepper, Sat 7 Nov 2026. NOT applied.** Workflow files
(`.github/workflows/prices.yml`) return 403 via the GitHub App API, so
this change must go through the GitHub web edit as Schadhaxx. The
branch `pepper-daily-bollinger` already carries the tool, the daily
files, the JS switch and the tests — this note is the only missing
piece. Apply it after Sunil has seen the preview and approved the
feature for live.

## What it does

Runs `tools/screener_daily.py` in the **recap job** (the job that
already rebuilds daily files on final closes and pushes them to main),
so the 11 screener daily files (`assets/data/stock-daily-*.json`,
`assets/data/ind-daily-*.json`) stay current alongside
`btc-daily.json` / `vehicle-daily.json`. The screener modal's Daily
Bollinger reads them with `cache:'no-store'`, so a fresh file is
picked up on the next modal open — no JS pin bump is needed when the
files are regenerated (the `?v=20261107` pin only changes if the file
shape changes).

## Why the recap job (not the prices job)

- It runs on final closes (`final_close == '1'`), which is exactly
  when a daily close becomes final. The prices job runs every 5 min
  and would regenerate the files mid-session.
- It already has the staging/validate/test/commit pattern and pushes
  to main (fast-forward only). The daily-files step follows the
  `opens` / `vehicle` steps: `continue-on-error: true`, never blocks
  the recap or the prices job.
- The tool fails loud and writes nothing on a Yahoo error, a missing
  session, or a stock weekly-consistency failure — so a bad run
  leaves the previous daily files in place and the JS falls back to
  weekly bands.

## The diff (against main c9340ef7, .github/workflows/prices.yml)

Add this step **after** the "IBIT/FBTC vehicle closes" step in the
`recap` job (around line 595), before "Commit and push":

```yaml
      - name: Screener daily closes (validated; never blocks the recap or prices)
        id: screener_daily
        continue-on-error: true
        timeout-minutes: 2
        run: |
          mkdir -p /tmp/screener-daily
          python3 tools/screener_daily.py --out-dir /tmp/screener-daily --weekly-dir assets/data && python3 tools/screener_daily.py --check-only --out-dir /tmp/screener-daily --weekly-dir assets/data || { echo "::warning::screener-daily update skipped; the modal falls back to weekly bands"; exit 0; }
          changed=0
          for f in stock-daily-TSLA.json stock-daily-PLTR.json stock-daily-MSTR.json stock-daily-IBIT.json stock-daily-MU.json stock-daily-META.json stock-daily-SPCX.json ind-daily-wti.json ind-daily-gold.json ind-daily-us10y.json ind-daily-vix.json; do
            if ! cmp -s "/tmp/screener-daily/$f" "assets/data/$f"; then cp "/tmp/screener-daily/$f" "assets/data/$f.tmp" && mv "assets/data/$f.tmp" "assets/data/$f"; echo "updated $f"; changed=1; fi
          done
          echo "changed=$changed" >> $GITHUB_OUTPUT
```

Then, in the "Commit and push" step:

1. `if:` — add `|| steps.screener_daily.outputs.changed == '1'` to
   the existing condition.
2. `git add` — append the 11 daily files:
   `assets/data/stock-daily-*.json assets/data/ind-daily-*.json`
   (or list them explicitly, matching the step above).
3. Commit message — append the screener-daily flag, following the
   existing pattern:
   `[ "${{ steps.screener_daily.outputs.changed }}" = 1 ] && msg="${msg:+$msg + }screener-daily"`

No other step changes. No new secrets (Yahoo needs no key, same as
`btc_daily.py`). No change to the prices job, the stall job, or the
weekly files.

## Things Grok Bot should know before applying

- **The weekly files are the consistency reference.** The tool reads
  the shipped weekly files (`assets/data/stock-weekly-*.json`,
  `gold-weekly.json`, `wti-weekly.json`, `us10y-weekly.json`,
  `vix-weekly.json`) and checks each daily close on a week's last
  session against that week's close. A stock mismatch over $0.01 is a
  hard error (nothing written). An indicator mismatch is reported,
  not fatal — see below.
- **Known indicator mismatches (expected, reported — not errors).**
  The tool logs them as `NOTE … weekly-consistency notes` and still
  writes the files. WTI week of 26 Oct (daily 104.12 vs weekly
  104.24) and GOLD week of 26 Oct (daily 3898.90 vs weekly 3901.20)
  are the two flagged intraday-snapshot shipped values (Sunil, 31 Oct:
  leave for Grok Bot + Chief). The week of 2 Nov indicator closes
  differ because the weekly files were refreshed ~3:40 p.m. ET on
  6 Nov, before the 4 p.m. close (intraday snapshot vs final close).
  **Three VIX weeks are pre-existing shipped-value discrepancies:**
  week of 2 Feb (daily 20.37 vs weekly 17.76), 15 Jun (16.40 vs
  16.78), 29 Jun (16.15 vs 15.81). Verified 7 Nov: for the Feb 2 week,
  Yahoo's current OHLC matches the weekly file's open/high/low but
  the weekly close 17.76 matches NO daily close in that week — a bad
  or stale weekly close, likely a Yahoo restatement or a bad weekly
  build. The daily Bollinger uses the current Yahoo daily closes,
  which is the right source. These three are worth a look when the
  weekly files are next rebuilt, but they do not block this wiring.
- **The indicator weekly files' latest-week close is an intraday
  snapshot** (no completed-session cutoff in `tools/indicator_weekly.py`;
  a fix is ready but uncommitted in Pepper's `~/workspace/ps-weekly`).
  That is why the 2 Nov week indicator closes differ — expected.
- **SPCX has 103 daily closes** (listing 12 Jun 2026). The tool
  writes the file from day one; the JS draws no daily bands until 20
  daily closes are available for a given week.
- **VIX has 216 daily closes vs 214 for the others** — VIX trades on
  NYSE holidays (25 May, 7 Sep). Expected, not an error.
- **The tool is stdlib-only, no network except Yahoo.** It never
  invents or interpolates a close.

## Test plan (for the Grok Bot run)

1. In the branch checkout: `python3 tests/test_screener_daily.py`
   (11 tests) and `node tests/test_daily_bollinger.js` (29 tests).
2. `python3 tools/screener_daily.py --check-only` on the branch's
   daily files — expect `screener-daily OK 11 files` plus the
   indicator NOTE lines above.
3. After applying the workflow edit: watch one recap run. Expect the
   `screener_daily` step to succeed (or warn-and-continue, never red)
   and the daily files' `asOf` to advance to the latest final close.
4. Open the preview (see `~/workspace/your_files/daily-bollinger-progress-2026-11-07.md`)
   and flip the Bollinger switch Weekly → Daily on TSLA: the note
   should read "Bollinger (daily, 20 closes, 2σ): SMA $380.42 · upper
   $417.67 · lower $343.18" (values move as new closes land).
