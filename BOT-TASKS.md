Open tasks across Sunil's bots so Pepper can pick them up if bots are offline. Sections are added as each bot reports.

## Review: enhancements 4–6 (pepper-enhancements-456) before Fri Nov 27 go-live

Branch: `pepper-enhancements-456` @ `0bcd6db1` (handover parent `17b79295`; current live main was `aaed6194` on `2651cb1b` — confirm against current main before reviewing).

26 files, +970/−31.

### Scope

- **Item 4:** share links / Copy-link on `/compare/` (`compare.js` PsShare)
- **Item 5:** `recap-chart.js?v=rcp1` canvas charts on 11 recap pages, plus `recap_gen.py` changes
- **Item 6:** Desk sparklines (`spark-pack.json?v=spk1`, 24 symbols; `screener.js` pin scr9→scr10; `screener_daily.py` builds the pack; `prices.yml` copies and commits `spark-pack.json`)

### Review checklist

- Rebase / ahead-behind vs current main
- Whole-diff scope (no unrequested logo, image, style, layout, or files)
- New pins scr10 / rcp1 / spk1 were never served before (curl live)
- `prices.yml` copy-back and `git add` include `spark-pack.json` and recap files; `recap_gen` keeps the sitemap and recap `#list` in sync
- Logic fails soft if the pack is missing
- `run_all` tests as a matched pair vs clean main (handover says 17 fail on both, same set — confirm)
- Screenshots: 390px + desktop, light + dark, of Compare, a recap page, and Desk

**Result:** PASS, or one must-fix list.

### Go-live

Fri Nov 27, 5 PM ET, only on Sunil's yes. Pepper deploys (the handover's line saying Grok Bot handles go-live is wrong). Fast-forward only, no force-push, never during 9:30 AM–4 PM ET, never on Sunday.

## Layout-shift (CLS) fix for Desk and Compare — kickoff Fri Nov 27 2 PM ET

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

## Other bots

Site Launch: none. Chief of Staff, PaperStreet Portfolio, Market God, Ping Bot GitHub: pending.
