# BTC trend support (floor) — test pack

Drop this folder into `Schadhaxx/paperstreetbtc` as `tests/floor-testpack/`.
It is the contract for the `pepper-skunkworks-floor` redo. Keep the existing
swing/anchor/slope maths (`floorNow` $62,440.91 on the 26 Nov snapshot).
Change the break rule, the caption, and the old tests that encode the bug.

## Rules

- Weeks are Monday-start UTC, closing Sunday UTC. Lows are weekly close-based
  (lowest daily close in the week), never intraday.
- **Only a completed week can set `broken`.** A week is broken iff its
  completed weekly close is `<= floor * 0.98` (2% or more below the floor at
  that week). Any such completed week sets `broken=true`.
- The in-progress week may be drawn (dashed). It must never set `broken` or
  turn the line red, even if it is already >2% under.
- **Date-only `asOf`** (a `YYYY-MM-DD` daily close): the week is complete iff
  `asOf` is that week’s Sunday or later.
- **Datetime `asOf`:** the week occupies `[Mon 00:00 UTC, next Mon 00:00 UTC)`.
  Sunday 23:59 UTC is still in-progress; Monday 00:00 UTC completes it.

Current 26 Nov 2026 truth (data through Thursday): last completed week
Mon 16–Sun 22 Nov closed $61,161.91 vs floor $62,217.68 = −1.7% →
**`broken=false`**. The in-progress week (Thu close $60,495.57, −3.1%)
must not break it. Anchor Mon 21 Nov 2022 $15,787.28; binds 11 Sep 2023;
slope +$223.2231/wk. `floorNow` stays $62,440.91 (includes the open week).
`maxUnderPct` is the completed-week max (~−1.70), not the open week’s −3.12.

## Display

The chart (not only a colour change) must show:

| field | required value |
|---|---|
| `label` | `Trend support (weekly closes)` |
| `asOf` | Sunday of the last completed week (`2026-11-22` on this snapshot) |
| `source` | pass through from the data file |
| `breakRule` | `Completed weekly close (Monday-Sunday UTC) 2% or more below the floor. An in-progress week does not count.` |
| `brokenNote` | `Broken: a completed weekly close finished 2% or more below this line.` when broken, else `null` |

The toggle must not stay a bare “Floor” with no date or rule.

## Pepper API

Python `tools/ta_floor.py` should export (same names as `reference_floor.py`):
`week_monday`, `is_week_complete`, `evaluate_break`, `floor_broken`,
`display_copy`, `floor_at` / `floor_at_payload`. `compute_floor` must take
`last_date` (or `as_of`) and return `broken`, `floorNow`,
`lastCompletedClose`, `lastCompletedWeek`, `maxUnderPct` as above.

JS `P._floor` should expose: `at` (keep), `broken(j, asOf)` (recompute from
`weeks`; **ignore a stale `j.broken` flag**), `isWeekComplete`,
`weekMonday`, `evaluateBreak`, `display`.

Also update `tests/test_ta_floor.py` and `tests/test_ta_floor.js`, which
today assert `broken=true` on this snapshot.

## How to run

From this folder (or `tests/floor-testpack/` once dropped in the repo):

```bash
# Reference self-check (must pass as shipped)
python3 test_floor_pack.py --impl reference_floor.py
node test_floor_pack.js --impl reference_floor.js

# Against Pepper, once dropped in (or with an explicit repo path)
python3 test_floor_pack.py --repo ../..
node test_floor_pack.js --repo ../..
```

`--impl` / `--panel` override the Python module or `btcchart-panel.js`.
`FLOOR_IMPL`, `FLOOR_PANEL`, and `FLOOR_REPO` work too. Exit 0 = all pass.

Fixtures: `real_26nov`, `completed_week_break`, `in_progress_only_dip`,
`boundary_minus_2pct` (exactly −2.0% breaks; 9800.01 does not; the same
exact −2.0% close in-progress does not), `week_boundary_sun_mon`
(Sunday 23:59 UTC vs Monday 00:00 UTC).
