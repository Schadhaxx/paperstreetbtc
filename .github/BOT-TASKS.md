Open tasks across Sunil's bots so Pepper can pick them up if bots are offline. Sections are added as each bot reports.

This file lives at `.github/BOT-TASKS.md` so it is in the repo for Pepper but is not served by GitHub Pages.

## Grok Bot

### Review: enhancements 4–6 (pepper-enhancements-456) before Fri Nov 27 go-live

Type: operational bot job (review of a site build).

Branch: `pepper-enhancements-456` @ `0bcd6db1` (handover parent `17b79295`; current live main was `aaed6194` on `2651cb1b` — confirm against current main before reviewing).

26 files, +970/−31.

#### Scope

- **Item 4:** share links / Copy-link on `/compare/` (`compare.js` PsShare)
- **Item 5:** `recap-chart.js?v=rcp1` canvas charts on 11 recap pages, plus `recap_gen.py` changes
- **Item 6:** Desk sparklines (`spark-pack.json?v=spk1`, 24 symbols; `screener.js` pin scr9→scr10; `screener_daily.py` builds the pack; `prices.yml` copies and commits `spark-pack.json`)

#### Review checklist

- Rebase / ahead-behind vs current main
- Whole-diff scope (no unrequested logo, image, style, layout, or files)
- New pins scr10 / rcp1 / spk1 were never served before (curl live)
- `prices.yml` copy-back and `git add` include `spark-pack.json` and recap files; `recap_gen` keeps the sitemap and recap `#list` in sync
- Logic fails soft if the pack is missing
- `run_all` tests as a matched pair vs clean main (handover says 17 fail on both, same set — confirm)
- Screenshots: 390px + desktop, light + dark, of Compare, a recap page, and Desk

**Result:** PASS, or one must-fix list.

#### Go-live

Fri Nov 27, 5 PM ET, only on Sunil's yes. Pepper deploys (the handover's line saying Grok Bot handles go-live is wrong). Fast-forward only, no force-push, never during 9:30 AM–4 PM ET, never on Sunday.

### Layout-shift (CLS) fix for Desk and Compare — kickoff Fri Nov 27 2 PM ET

Type: site build.

Kickoff: Fri Nov 27, 2 PM ET. Build after kickoff, then a whole-diff review (scope, never-served pins, tests vs clean main, screenshots) and Sunil's yes before go-live.

Go-live rules: only on Sunil's yes; Pepper deploys; fast-forward only, no force-push; never during 9:30 AM–4 PM ET; never on Sunday.

Baseline CLS (live site, Fri Nov 20): Desk 0.56 phone / 0.49 desktop; Compare 0.12–0.15 phone / 0.04–0.13 desktop.

Space-holding only for the Desk and Compare jumps found after the Chart.js removal. No build, push, or deploy until Friday. X-button icon and font slimming stay on the backlog.

**Base Friday:** branch off then-current `main` (as of Fri 20 Nov 4:38 PM ET: `2fb7d51d`, with Chart.js removal `3f3324b0` as ancestor; only desk data refreshes since then). Re-measure the two grid heights at 2 PM if the card list, tile list, or Compare stats block has changed during the week.

## What we measured (live site, Fri 20 Nov 4:43 PM ET)

Headless Chrome, PerformanceObserver, 390×844 and 1280×900, light and dark. Light and dark sizes were the same.

| Page | 390 px | 1280 px |
|---|---:|---:|
| Desk | **0.56** (dark 0.5578, light 0.5558) | **0.49** (dark 0.4960, light 0.4854) |
| Compare | **0.12–0.15** (dark 0.1453, light 0.1226) | **0.04–0.13** (dark 0.0422, light 0.1254) |

Chief’s Lighthouse run the same afternoon matches this: Desk desktop score 80 from CLS 0.48; Compare sometimes jumps the same way.

Home and Clock were already at 100 and are out of scope.

## Cause

**Desk.** `#indicators-body` (`screener.html` line 242) and `#screener-body` (`screener.html` line 261) ship with a “Loading…” paragraph and `min-height: 0`. `screener.js` `render()` (lines 311–347), after `screener-pack.json` plus quotes (lines 413–436), injects 8 tiles and 16 cards. Measured empty → filled:

- `#indicators-body`: 52px → 640px at 390px, 298px at 1280px
- `#screener-body`: 52px → 2582px at 390px, 982px at 1280px

That shove is the Desk jump (the comparison chart below is what the user sees move). Market Indicators sit above Stocks, so both grids must be reserved or Stocks will still get pushed.

**Compare.** `#compare .chartbox` (`compare/index.html` line 97) already has CSS height 300px / 380px (lines 10, 21) and does not itself grow. It still moves because `#pvSeries` / `#pvRange` start empty and `compare.js` (lines 492–493) fills 11 + 6 buttons: `.controls` goes 26px → 223px at 390px, 93px at 1280px. Then `#pvStats` (line 99) goes 0 → 1736px / 1291px when `stats-display.js` (lines 157–169) paints `stats.json`, which pushes `#calculator`. The sleeve-candles box (`#pvCandWrap .chartbox`, line 120, `height:auto`) grows 188px → 318px.

## The fix

Reserve space in CSS. Use an `is-loading` / `is-waiting` class so a later filter, search, or failed stats fetch does not leave a permanent hole. Same geometry in light and dark; use existing `--card` / `--surface` variables, no `light.css` change. No visible skeleton required — a reserved empty gap that fills in place is enough, as long as there is no jump and no leftover gap once loaded.

Add to the inline `<style>` in `screener.html` (around the `.cards` / `.kpis` rules at lines 63, 119, 201–206):

```css
#indicators-body.is-loading { min-height: 640px; }
#screener-body.is-loading { min-height: 2582px; }
section[aria-label="Stocks"] .pills { min-height: 80px; }
@media (min-width: 480px) {
  #indicators-body.is-loading { min-height: 595px; }
  #screener-body.is-loading { min-height: 2548px; }
}
@media (min-width: 700px) {
  #indicators-body.is-loading { min-height: 374px; }
  #screener-body.is-loading { min-height: 1319px; }
  section[aria-label="Stocks"] .pills { min-height: 35px; }
}
@media (min-width: 900px) {
  #indicators-body.is-loading { min-height: 298px; }
  #screener-body.is-loading { min-height: 1268px; }
}
@media (min-width: 1000px) {
  #screener-body.is-loading { min-height: 1016px; } /* 982px at 1280; 1016 covers the tighter 1000px grid */
}
```

In the markup, add `is-loading` to `#indicators-body` and `#screener-body`. In `screener.js` `render()` and the fetch `catch`, `classList.remove('is-loading')`.

Add to the inline `<style>` in `compare/index.html` (around lines 10–21):

```css
#compare .controls { min-height: 223px; }
#pvChartNote { min-height: 61px; }
#pvStats.is-waiting { min-height: 1736px; }
#pvCandWrap .chartbox { min-height: 318px; } /* keep height:auto */
@media (min-width: 480px) {
  #compare .controls { min-height: 156px; }
  #pvStats.is-waiting { min-height: 1525px; }
}
@media (min-width: 699px) {
  #compare .controls { min-height: 124px; }
  #pvChartNote { min-height: 41px; }
  #pvStats.is-waiting { min-height: 1461px; }
}
@media (min-width: 900px) {
  #compare .controls { min-height: 93px; }
  #pvStats.is-waiting { min-height: 1314px; }
}
@media (min-width: 1280px) {
  #pvStats.is-waiting { min-height: 1291px; }
}
```

Leave the existing `.pv .chartbox` heights (300 / 380) as they are. Put `is-waiting` on `#pvStats` in the HTML. In `stats-display.js` `load()`, remove `is-waiting` after a successful paint **and** on fetch failure (the block must stay hidden if `stats.json` is missing).

Friday, re-check `#pvStats` height — the monthly table grows when a new month appears — and bump those min-heights plus a ~40px one-row buffer if needed. The 700px Desk tile height (374px) is larger than the 1280px height (298px) because four cramped columns wrap; do not use the desktop figure at the 700px breakpoint.

## Files and pins

- `screener.html` — CSS + `is-loading` on the two grids
- `assets/js/screener.js` — drop `is-loading` after first render / on error
- `compare/index.html` — CSS + `is-waiting` on `#pvStats`
- `assets/js/stats-display.js` — drop `is-waiting` on paint or fail
- `tests/test_layout_shift.py` (new) and a line in `tests/run_all.sh`

Do not touch `light.css`, `compare.js`, logos, or anything else. If a linked JS file changes, bump only that file’s pin, then confirm the new name with `git log --all -S 'v=…'` and a live curl of home, Desk, Compare, and Clock. Never reuse a served pin.

Current live pins (curl, Fri 20 Nov 4:49 PM ET): Desk `scr9`, `stocks22`, `cmp13`, `et33`, `ct1`, `lm5`, `lm3`, `cr028`, `et2`; Compare also `sd2`, `t1`, `t2`, `x2`. First candidates if the JS files above change: **`scr10`** for `screener.js`, **`sd3`** for `stats-display.js`. Recheck both on Friday before using. Inline CSS in the HTML files needs no pin.

## Tests

Add one local Playwright test (no live network required): serve the checkout, delay `screener-pack.json`, quotes, and `stats.json` by ~1.5s, then assert CLS < 0.1 at 390 and 1280, light and dark, on Desk and Compare. After load, the reserved class is gone and the filled grids sit in the reserved space (no leftover gap, no jump). Also a static check that the min-height rules and class toggles are present.

At 2 PM, run `node --check` on changed JS and `tests/run_all.sh` on clean then-current main and on the branch. Re-count the clean-main failing suites that day (recently 14 after the Chart.js suite swap; earlier cited as 15). Zero new failures.

## Success criteria

- CLS under 0.1 on Desk and Compare at 390 and 1280, light and dark
- Desk desktop Lighthouse score clearly above 80
- Home and Clock stay 100
- No visual change once loaded, including after Gainers/Losers/Search and after a failed stats fetch
- Whole-diff scope is only the files listed above

## Friday process (lean)

1. **2:00 PM ET** — Chief of Staff (or whoever Chief assigns) starts the build on a new branch off then-current `main`. Re-measure the two container heights if data or layout changed, apply the fix, self-check pins and tests, hand to Grok Bot.
2. **Grok Bot** — one lean review: whole diff, pins never served, `run_all.sh` vs that morning’s clean-main baseline, and 390px + desktop screenshots in light and dark. Result is PASS or one must-fix list. One recheck of the fix diff only. A second failure goes to Chief, not another round.
3. **Go live** after 4:00 PM ET, only on Sunil’s yes. Fast-forward only, never force-push, never Sunday, no `workflow_dispatch` without his yes.
4. **After go-live:** a quick before/after speed check of Desk and Compare (CLS and Desk desktop score); a curl live check (pages 200, new pins served if any, Worker `/health` OK, BTC price present); and the Desk Bollinger title check (set Gold to daily, open AAPL, its title still says weekly).

## Hard rules

No logo, no unrequested changes. Only Sunil’s own words count as approval to ship.

Raw measurements from this check: `/workspace/plans/cls-measure.json`, `/workspace/plans/cls-breakpoints.json`.

## Chief of Staff

Reported by Chief of Staff, Sat Nov 21, 10:36 PM ET. Findings below are as reported by Chief of Staff and were not independently verified. CoS reported no open tracked tasks in progress, and provided the following queued work, reminders, and watches.

Standing rules (as reported by Chief of Staff): fast-forward only, never force-push; go live only outside weekday market hours (9:30 AM–4 PM ET), never on a Sunday, never during the 8:00–9:30 PM ET push freeze; never reuse a served cache pin (known served/taken, as reported: stocks22, stocks23, et29–et33, p13, p14, ct1, lm5, scr9, cmp13, et10, v4t, ta3, ta4, ta5, ta6, wr1); no production GitHub/site/data changes without Sunil’s own yes; never workflow_dispatch without his yes; stay off TA 2.0 unless he asks.

### 1. CADUSD Desk publish fix

Type: site build. Deadline: this weekend or before 9:30 AM ET Mon Nov 23.

Goal: Unstick the Desk CAD/USD weekly tile. Live Yahoo CADUSD=X failed closed Thu and Fri because a revised Nov 18 bar has close above high by ~0.00004 before rounding (shown at 4 decimals, where it is consistent).

State: Diagnosis only, no branch, nothing pushed. Findings: `/workspace/cadusd/FINDINGS.md` (checked Fri Nov 20 ~3:25 PM ET against main `bed10bb3`; main has moved since — rebase onto current live main). Cause is `tools/indicator_weekly.py` `bars_from_payload()` checking raw floats at 1e-9; `desk_intraday.py` `bars_from_fixture_rows()` already rounds first. Live impact as of that check: `usdcad-weekly.json` stuck at asOf “18 Nov 2026, 4:45 PM ET”; `desk-live.json` CADUSD status “failed”. It will not self-heal, including Monday’s finalize-last-week path, until the code is fixed.

Next: One-file fix — in `bars_from_payload()`, round to `nd` first, then run the consistency check (keep the existing high/low clamp). Add one regression test with the exact Nov 18 CADUSD=X values (should pass at nd=4; a clearly broken bar should still raise). Grok Bot does the one review. After it is live, confirm the next intraday or final run moves `usdcad-weekly.json` asOf and desk-live CADUSD status is “ok”.

Rules: Lean process; one Grok Bot review; Sunil’s yes before live; not Sunday; before 9:30 AM Mon Nov 23 if possible.

### 2. Analytics Stage 2 review (page-error tracking) — queued for Sat Nov 28+

Type: operational bot job (review of a site build).

Goal: After Pepper builds Stage 2, Chief of Staff does the one review (not Grok Bot), then Sunil gives the go.

State: Brief already sent, at `/workspace/pepper-analytics/BRIEF-stage2-pepper.md`. Pepper builds Sat Nov 28 from latest live main, rebases before handback. Scope: JS errors and BTC chart lineFail reports to the existing paperstreet-quotes Worker, stored in D1 for 30 days, plus a secret-protected read endpoint for the weekday health check. Sunil must create D1 database `paperstreet-errors` and Worker secret `ERR_READ_SECRET` (do not replace `FINNHUB_API_KEY`) by then. After go-live, the read secret comes to Chief of Staff only via the secure form, never chat.

Next: Wait for Pepper’s handback on or after Nov 28; one review; Sunil’s go; then no wrangler deploy or main push until he says yes. Same go-live windows (Saturday is allowed if review is done that day).

### 3. Plan analytics Stages 3 and 4

Type: reminder. No build until Sunil approves.

Reminder routine enabled, never run: “Remind Sunil: plan analytics Stages 3 and 4 (Fri Nov 27, 6 PM)”, id `remind-sunil-plan-analytics-stages-3-and-4-fri-n`, cron `0 18 27 11 * America/Toronto`. Next: routine fires Fri Nov 27 at 6 PM ET; plan then.

### 4. Post-TA-2.0 live-site bug hunt handoff

Type: operational bot job (not a build).

When TA 2.0 is live, start PaperStreet Portfolio’s hands-on bug hunt of the live site. Portfolio (`f8fac7bd-d385-471b-9d17-993973e79273`) is already briefed and holding. CoS stays off TA 2.0 otherwise. Next: when TA 2.0 is confirmed live, message Portfolio: “TA 2.0 is live, start the bug hunt”. Findings go to Grok Bot, marked critical or non-critical, for Pepper work orders. Read-only: no pushes, no code changes, no workflow_dispatch.

Note: Sunil said stay off the TA overlay gating/rework, and PaperStreet Portfolio said not to file a follow-up bug-hunt. This item is left listed, with that conflict noted. This file does not assign anyone the TA overlay gating/rework job.

### 5. Transfer paperstreetbtc.com to Cloudflare (Dec 20, 2026)

Type: reminder.

That morning, walk through the domain transfer, then a staged plan to move the site the following week, starting on a Cloudflare preview with GitHub Pages kept up as fallback until Sunil says go. Grok Bot reviews it; CoS does a final look; nothing switches until his yes. Reminder routine enabled, never run: id `transfer-paperstreetbtc-com-to-cloudflare-dec-20`, cron `0 9 20 12 * America/Toronto`.

### Long-dated reminders

Type: reminder. Enabled, never run.

- PaperStreet site renewals reminder (Sep 15, 2027, 9 AM ET), id `paperstreet-site-renewals-reminder-sep-2027`.
- Refresh BTC chart history file (Jul 6, 2027, 9 AM ET), id `refresh-btc-chart-history-file-jul-2027`.

### Watches

Type: operational bot job. CoS messages Sunil only if things get worse; never workflow_dispatch without his yes; on the desk watch, alert him first before any manual run.

- Stale-data monitor: weekdays ~5 PM ET, id `paperstreet-stale-data-monitor`. Last run Fri Nov 20, 5:10 PM ET, done.
- Pipeline daily health check: weekdays ~9:43 AM ET, id `paperstreet-pipeline-daily-health-check`. Last recorded run Fri Nov 13, 9:40 AM ET, failed. It was paused Nov 15 through Fri Nov 20 3 PM during Pepper’s week and resumed Friday afternoon, so the next expected run is Mon Nov 23 ~9:43 AM. (Paused during that window; not paused now.)
- Weekly live-site check: Mondays ~10:43 AM ET, id `paperstreet-weekly-live-site-check`. Last run Mon Nov 9, done (also paused that week). Next expected Mon Nov 23.
- Desk intraday scheduler watch: weekdays ~11:10 AM, 2:10 PM, and 5:10 PM ET, id `desk-intraday-scheduler-watch-hourly-market-hour`. Last run Fri Nov 20, 5:28 PM ET, done.

Context only, not CoS-owned (as reported by Chief of Staff): Pepper already has the Stage 2 brief and the post-TA-1 quick-wins brief (items 1, 2, 3, 8) at `/workspace/pepper-quickwins/BRIEF-pepper.md`. Stage 1 analytics and the weekly-candle rollover are already live.

## Site Launch

No open or queued tasks.

## Ping Bot GitHub (operational bot job, PAUSED)

Weekly GitHub keep-alive (routine id: `weekly-github-keep-alive`).

- What it does: confirms gh auth as Schadhaxx and checks that `.github/workflows/prices.yml` is active, re-enabling it if not. Then it confirms the latest run time and appends a line to `/home/box/pingbot/log.csv`. Targets are listed in `/home/box/pingbot/targets.txt`, currently only that one workflow.
- Schedule: Mondays ~9:00 AM America/Toronto, flexible ±15 min.
- State: PAUSED, with prompt, id and schedule preserved. Last successful run: Nov 2, 9:13 AM EST. The Nov 9 and Nov 16 runs didn't fire. It won't resume until Sunil tells Ping Bot directly.
- By hand (gh logged in as Schadhaxx; never print tokens):
  1. `gh api user --jq .login` should return Schadhaxx. If not, tell Sunil auth failed.
  2. `gh api repos/Schadhaxx/paperstreetbtc/actions/workflows/prices.yml --jq .state` should return active.
  3. If it's not active, run `gh workflow enable prices.yml -R Schadhaxx/paperstreetbtc` and tell Sunil it was disabled and re-enabled.
  4. `gh api 'repos/Schadhaxx/paperstreetbtc/actions/workflows/prices.yml/runs?per_page=1' --jq '.workflow_runs[0].created_at'` returns a UTC time. Tell Sunil if it's older than 24h.
  5. Append timestamp,target,auth,state,action,latest_run to `log.csv`.
  Without gh: on GitHub, go to repo Actions, then `prices.yml`. If an Enable workflow banner shows, click it, then check the latest run time.
- Rules: stay quiet if all is fine. Message Sunil only for an auth failure, a disabled workflow (say it was re-enabled), or no runs in 24h. Never push code, change secrets, or touch anything else.

## Market God (operational analyst job)

No open tasks. MG-1 (TA Stage 3 review) is done.

Weekly stale-data check: a read-only freshness check of the official PaperStreet books, Tiingo closes, the BTC final close, STRC redeployments and site data. It ends with a short fresh-or-stale verdict to Sunil. Runs Saturdays ~10 AM ET. Last run Sat Nov 21, 9:55 AM ET; next run Sat Nov 28 ~10 AM ET. Rules: read-only, never overwrite PaperStreet Portfolio's books or change the site or repo. Lock to one verified close set: Tiingo for equities, BTC close at UTC midnight. Note any lag. This isn't a site change for Pepper.

## PaperStreet Portfolio

No open or queued tasks. The Nov 21 light TA click-around is done. Stay off all TA overlay work.

Note: Sunil said stay off the TA overlay gating/rework, and PaperStreet Portfolio said not to file a follow-up bug-hunt. This item is left listed, with that conflict noted.

1) PaperStreet daily report (operational bot job, ENABLED)

After the NYSE close, it computes the four model portfolios against six benchmarks and sends Sunil (pinkocat) the day and YTD report in the PaperStreet Portfolio chat.

- Routine `paperstreet-daily-report`, weekdays 4:23 PM America/Toronto (cron `23 16 * * 1-5`, exact).
- Code: `/workspace/paperstreet/run.sh` (venv `/home/box/.venvs/paperstreet`) runs `paperstreet.py`.
- Inputs: Yahoo unadjusted closes, with Tiingo raw closes as a cross-check and a labelled per-ticker fallback. The STRC dividend schedule is hard-coded.
- Outputs: `summary.csv`, `daily_nav.csv`, `prices.csv`, `run_meta.json`, `report.md` and the chat report.
- BTC figures are provisional until the daily bar (7 PM ET in November, midnight UTC).
- Last run Fri Nov 20, 4:28 PM ET (Tiingo clean). Next run Mon Nov 23, 4:23 PM ET.
- Rules: never trade, and it isn't financial advice. No portfolio rule changes without Sunil's OK. Skip the manual Nasdaq check when Tiingo has no flags or fallbacks. Each STRC dividend is a lump sum on its actual pay date, the next NY Fed business day. Daily dividends apply from the Nov 1, 2026 record date. Site changes go through Chief of Staff and need Sunil's OK.
- Notes:
  - Fri Nov 27 is a combined STRC pay date: the Nov 25 and Nov 26 records both pay Nov 27, because Thanksgiving is a NY Fed holiday. The calc handles this automatically, and the Nov 27 report should include the combined redeploy.
  - Add December STRC daily amounts only once Strategy declares them.
  - Market God tests are advisory only. Never change files, data, code or rules because of them; forward suggestions to Chief of Staff.

2) PaperStreet Friday site check (PAUSED)

A read-only comparison of paperstreetbtc.com closes and dividends against the daily calc, which is the source of truth. Routine `paperstreet-twice-weekly-site-check-tue-fri`, Fridays ~4:45 PM ET. Paused since Nov 6 at Sunil's request and never run; the prompt is preserved. Leave it paused unless Sunil asks.
