# prices.yml patch — current-week candle pipeline (for Grok's web edit)

App API returns 403 for workflow files, so this patch is applied by
hand on GitHub as Schadhaxx, in the recap job (the main-branch job
that already stages in /tmp/stage, runs tools, and `git add`s
`recap/` + `assets/data/btc-daily.json opens.json vehicle-daily.json`).

After the vehicle step, in the stage, add:

    python3 tools/stock_weekly.py --out-dir assets/data
    python3 tools/indicator_weekly.py --out-dir assets/data
    python3 tools/stock_weekly.py --check-only
    python3 tools/indicator_weekly.py --check-only

And extend the job's `git add` line with:

    assets/data/wti-weekly.json assets/data/gold-weekly.json
    assets/data/us10y-weekly.json assets/data/vix-weekly.json
    assets/data/stock-weekly-*.json

Commit only when changed (the existing job already does this for
its other files). Cadence proposal (Pepper's, not a Sunil decision):
run with the recap job as-is; the indicator tool self-gates to
once/day and the stock tool only changes after a completed session,
so this produces at most one candle-data commit per day, not one
every 5 minutes. Do NOT add a separate 5-minute candle job.
