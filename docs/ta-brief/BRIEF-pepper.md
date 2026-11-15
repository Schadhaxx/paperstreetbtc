# Build brief for Pepper: Technical Analysis (TA) on the Bitcoin charts

From: Chief of Staff, for Sunil Chadha. Written Sun Nov 15, 2026.
Build window: Mon Nov 16 to Thu Nov 19. Hand back to Chief of Staff by **Thu Nov 19, 11:59 PM ET** (or Fri Nov 20 morning at the latest). Chief of Staff reviews and fixes it on Fri Nov 20.
Repo: `Schadhaxx/paperstreetbtc`. Everything in this brief is on branch `docs/ta-brief`, folder `docs/ta-brief/`. Do not merge that branch. It is reference only.

> Sunil approves the plan, not the code. Nothing in this job goes live. You build on a branch and hand it back. Chief of Staff reviews it, then regular Grok does QA, then Sunil gives the go.

---

## 0. Where to find everything (branch `docs/ta-brief`)

| File | What it is |
|---|---|
| `docs/ta-brief/BRIEF-pepper.md` | This brief |
| `docs/ta-brief/rollout-plan.md` | The staged plan Sunil approved on Nov 13 at 3:46 PM ET. Its scoring changes (bottom section) are binding for Stage 3. |
| `docs/ta-brief/grok-spec-1113.md` | Regular Grok's original spec plus Chief's review notes. This was a starting point only. Where it differs, the rollout plan and this brief win. |
| `docs/ta-brief/grok-scoring-sample.py` | Grok's sample scoring for Smart Trendlines. It is a starting point, improved by the rules in section 5. |
| `docs/ta-brief/mockups/README.md` | Site Launch's mockup write-up (approaches A to D, the overlap check, and a build note). **Sunil chose C.** |
| `docs/ta-brief/mockups/shots/sheet-C.png` | **The GUI to build.** Option C in portrait and landscape, light and dark, full screen, and iPhone SE. |
| `docs/ta-brief/mockups/shots/C/` | Every individual option C shot, plus a `.json` file of element rectangles for each |
| `docs/ta-brief/mockups/shots/live/` | The live clock page before TA (the "today" reference) |
| `docs/ta-brief/mockups/www/clock/ta-mock.css`, `ta-mock.js` | The mockup layer: pill, panel, colours and RSI strip styling. Reuse the look, not the code. The overlay maths in it are fake. |
| `docs/ta-brief/mockups/make-sheets.py`, `render.py` | Playwright scripts that render the shots and run the overlap check. Reuse them for your own screenshots and overlap checks. |
| `docs/ta-brief/mockups/shots/overlap-check.json` | Rectangle overlap results from the mockup (44 of 44 passed) |

Only the option C shots plus the four comparison sheets were copied (A, B and D individual shots were left out to keep the repo small). To view the live mockup: `python3 -m http.server 8790 --directory docs/ta-brief/mockups/www`, then open `http://127.0.0.1:8790/clock/ta.html?a=C&s=open` (also try `s=rsi`, `s=rsicol`, `r=1Y&ct=candles`, `fs=chart`).

---

## 1. Goal

Add an expandable **TA** pill to the Bitcoin charts on paperstreetbtc.com with four independent overlays:

1. **Bollinger Bands** (20, 2σ)
2. **Moving average**: an **SMA | EMA** switch (one at a time), with period **20 | 50 | 200**
3. **RSI (14)**, shown as a thin strip under the chart
4. **Smart Trendlines**: support and resistance levels plus sloped trendlines, **computed on the Python backend** (data pipeline) and only drawn by the browser

The chart must stay readable and fast, and look native to the site in light and dark mode on iPhone, iPad and desktop.

## 2. Decisions already made (do not reopen)

- **Where TA appears:** every Bitcoin popup chart (the Live BTC pill popover on desktop and the bottom sheet on phones, on every page that loads `btcchart.js`) **and** the live Bitcoin chart on `/clock/` (inline mode, including both full-screen modes). Both are the same code: `assets/js/btcchart-panel.js`, loaded lazily by `assets/js/btcchart.js`.
- **Where it does NOT appear:** the Desk chart (`screener.html` stock charts, `screener-chart.js`, `screener-indicator-chart.js`). Do not touch it. Note that `screener.html` loads `btcchart.js` for its Live BTC pill, so the BTC popover there does get TA. That is expected.
- **GUI = mockup option C** (Sunil: "a GUI rebuild"). The chart-type buttons collapse into one compact dropdown pill, and the TA pill goes at the end of that row. There is no side panel.
- **Browser-side maths:** Bollinger, SMA/EMA and RSI are computed in the browser and drawn on the **native canvas**. **No Chart.js.** Chart.js is being removed from the BTC chart on Wed Nov 18, so do not add any Chart.js code path or plugin.
- **Backend maths:** only Smart Trendlines and scoring run in Python, as a scheduled GitHub Action that writes a JSON file to the `data` branch. There is **no AI** in the job.
- **Floating panel:** it opens under the TA pill, sits over the plot without pushing the layout, and closes on an outside tap or Esc. It **must be a child of the chart stage** (`#hero.v4-stage` on the clock page, the `.bc-w` dialog in the popover) so it renders in the browser's top layer in Fullscreen-API mode.
- **Nothing may cover** the BTC price pill (including the draggable chart-only price pill `#pxPill`), **Keep screen on** (`#wakeBtn`, which moves into the full-screen bar), **Exit full screen** (`.v4-fs-exit`), the **Price clock** pill (`.v4-fs-toprice`), **Switch to chart** (`.v4-fs-tochart`) or the **theme dot** (`#themeDot`, `.v4-theme-dot`).
- **iPhone:** option C costs 0px of chart height. Do **not** shrink or squish the iPhone chart. The only height that may change is the RSI strip, and only when the user turns RSI on. Note that no "TA slot" exists in the code yet; option C makes the room by collapsing the chart-type buttons.
- **Colours** (from the mockup, kept clear of the asset colours): MA pink `#f472b6`, Bollinger violet `#a78bfa`, support green `#22c55e`, resistance red `#f87171`, RSI violet. Pick light-mode variants with enough contrast and use `psC(dark, light)` at draw time, as the panel already does.
- **Defaults:** all overlays are **off** by default, on every device (the approved plan says RSI is off by default on phones, and Stage 4 says all overlays start off). Toggles are remembered per device (localStorage).

## 3. Current repo state (check it again before you start)

- `main` was at **f907a898** on Nov 15 at 1:26 AM ET (hero cosmetic fixes, s2.js p9). Run `git fetch` and branch from the **current tip of main**.
- Live pins as of Nov 15 (all are served, so **never reuse** any of them):
  - `btcchart.js?v=et26` (its lazy panel is `btcchart-panel.js?v=et24`, set inside btcchart.js)
  - `clock-v4.css` / `clock-v4.js?v=v4l` (v4f to v4l are all burned)
  - `s5.js et3`, `s2.js p9` (p6, p7 and p8 are burned), `screener.js scr7`, `screener-chart.js cmp11`, `compare.js et8`, `screener-indicator-chart.js stocks15`, `chart-theme.js lm1`
- Other work landing in the same window, which you rebase onto. Do **not** do any of it yourself:
  - **Wed Nov 18:** Chart.js removal branch (Chief of Staff). It removes the Chart.js fallback from `btcchart-panel.js` and other pages. If it is on main by Thursday, rebase onto it.
  - Your own pending fixes: the **BTC chg24h null fallback** (s5.js / btcchart.js) and anything left from the hero cosmetic job. Keep those on **their own branches**. Do not mix them into TA.
- Where the chart code lives:
  - `assets/js/btcchart-panel.js`: ranges `1D 1W 1M 3M 6M YTD 1Y 5Y 10Y Max`. 1D chart type is `#bcCt` (Line / 1H / 4H). Range chart type is `#bcCg` (Line / Candles plus a size: 4H / Daily / Weekly / Monthly, depending on the range). Asset toggles are `#bcLg` (BTC, + S&P 500, + Gold, + MSTR). The canvas is `#bcC`. The native renderers are `draw1DNative`, `drawDailyNative`, `drawCandles1D` and `drawCandlesRange`.
  - `clock/index.html`, `clock/clock-v4.js`, `clock/clock-v4.css`: the stage `#hero.v4-stage`, the full-screen bar `.v4-fs-bar`, and full-screen chart / price modes (`window.__psClockFs`).

## 4. GUI spec (option C)

Use `mockups/shots/sheet-C.png` as the visual reference and `mockups/www/clock/ta-mock.css` for sizes and styling.

**Row 2 of the chart controls** = asset chips, then the **chart-type pill**, then the **TA pill** (at the end).

**Chart-type pill (new, replaces the `#bcCt` / `#bcCg` button rows):**
- Its label shows the current type: `Line ⌄`, `1H candles ⌄`, `4H candles ⌄`, `Candles · Weekly ⌄` and so on. Keep it short. On phones, `Candles ⌄` is fine if space is tight.
- Tapping it opens a small menu (same look as the TA panel, anchored to the pill, closes on an outside tap or Esc) with exactly the options the current range allows today:
  - 1D: Line, 1H, 4H
  - Candle ranges (1W, 1M, 3M, 6M, YTD, 1Y): Line, Candles, then a Size group with only the sizes allowed for that range (1W: Daily / 4H; 1M: Weekly / Daily; 3M to 1Y: Monthly / Weekly)
  - 5Y / 10Y / Max: no menu. Show `Line` disabled, or hide the pill. Match today's behaviour.
- Picking an option must behave **exactly** like tapping today's buttons. That means the same state variables (`CT`, `RGCT`, `RGGRAN`), the same fallbacks, and the same rule that candles are BTC-only. The cleanest way is to keep the old buttons in the DOM (hidden) and have the menu drive them, or to call the same handlers. Existing behaviour and tests must not change.
- Mockups did not cover the chart-type menu itself, so build it in the same style as the TA panel.

**TA pill:**
- Shows `TA ⌄` when nothing is on, and `TA ②` (a cyan count badge) when overlays are on. `aria-haspopup="dialog"`, `aria-expanded`, and an aria-label like "Technical analysis, 2 on".
- Same chip style as the range and chart-type chips (border, cyan "on" state, Inter font).

**Floating TA panel:**
- It is right-aligned to the chart, opens under the pill, floats over the plot (no layout shift), and its maximum height is capped to the visible stage. It closes on an outside tap, Esc, or a second tap on the pill. Focus returns to the pill.
- Contents, in this order:
  1. **Smart Trendlines**: on/off. Add a small "as of" or "updating…" note when the data is stale (see Stage 4).
  2. **Bollinger Bands (20 · 2σ)**: on/off.
  3. **Moving average**: on/off, plus an **SMA | EMA** two-way switch and a **20 | 50 | 200** segmented choice. One MA line at a time.
  4. **RSI (14)**: on/off.
- It is a child of the stage or dialog, never `body`.
- Full-screen **price** mode hides the chart, so the TA pill and panel are hidden there.

**RSI strip:**
- A thin strip under the price plot: **50px in portrait, 38px in landscape**, with 30 and 70 guide lines and a `RSI 14 · 54 ⌄` tab that collapses it to **20px**. Same x-axis as the chart. The value shown is the latest RSI.
- Turning RSI on is the only thing that may take height from the plot.

**Overlap rule (acceptance test):** with the panel open, no rectangle overlap with the protected elements in section 2, checked by hit-testing as in `make-sheets.py` / `overlap-check.json`. Cover phone portrait, landscape, full-screen chart (both the iPhone CSS mode and Fullscreen-API mode on desktop and iPad), and iPhone SE 375×667.

## 5. Build order: stages and acceptance criteria

Make **one commit (or a small group of commits) per stage**, with the stage in the message (for example `TA stage 1: GUI shell`), so Chief of Staff can review stage by stage. Do not start a stage until the previous one meets its acceptance criteria.

### Stage 1: GUI shell (no overlays)
Build: the chart-type pill and menu, the TA pill, the floating panel, and the RSI strip container. Toggles are wired to state and saved per device. Nothing is drawn yet.
Accept when:
- [ ] Every range and chart-type combination works exactly as it does today through the new menu (Line / 1H / 4H on 1D, Line / Candles and sizes on candle ranges, BTC-only candles, the 4H fallback message on 1W).
- [ ] The TA pill count updates. The panel opens and closes (outside tap, Esc, pill), sits inside the stage, and is visible in both full-screen modes.
- [ ] The overlap check passes with no hits (see section 4).
- [ ] iPhone chart height is unchanged with RSI off (compare with `mockups/shots/live/` and `C-*-today`).
- [ ] Works in the popover (desktop), the bottom sheet (phone) and the clock page inline view.
- [ ] Existing tests still pass, especially `test_speed_option2.js` (lazy panel) and `test_stage2_step*.js`.

### Stage 2: Browser indicators on the native canvas
Build:
- **SMA / EMA** (20 / 50 / 200, one at a time), **Bollinger (20, 2σ)**, and **RSI (14, Wilder smoothing)**, computed in plain JS (no libraries) and drawn on `#bcC` after the price series, in every native view: 1D line, 1D 1H / 4H candles, range line, and range candles (all sizes).
- **Warm-up data:** each indicator must be correct from the first visible candle. Load at least **200 extra candles before the visible window** for each timeframe (for example, extra daily closes from the daily series, extra 1h / 4h candles from Coinbase, reusing the existing fetch helpers and caches). If warm-up data can't be loaded, draw only from the point where it is valid. Never draw a wrong value.
- **Live updates:** when the live price ticks into the last candle or point, the indicators recompute and redraw (no flicker, and no full refetch).
- **BTC only.** When a comparison asset (S&P / Gold / MSTR) is on, the chart is in % rebased mode. **Proposed default (confirm with Chief of Staff):** hide the overlays in that state and show a one-line note in the panel, "TA shows on BTC alone. Turn off comparisons to see it."
- Respect the log scale where the chart uses it (map values with the same y-scale as the price).
- The RSI strip draws the RSI line plus the 30 and 70 lines, the collapse tab works, and the strip shares x positions with the main plot.
- Tooltip and scrub: show the indicator values for the hovered candle or point in the existing tooltip when an overlay is on (keep it compact on phones).
Accept when:
- [ ] Unit tests (new file `tests/test_ta_indicators.js`) match reference values. Use a fixed fixture and hand-checked or independently computed numbers for SMA, EMA, Bollinger and RSI at 20 / 50 / 200 / 14, including the warm-up edge.
- [ ] Each overlay lines up with the candles and line in every view, in light and dark, at 390px / iPad / desktop.
- [ ] No noticeable slowdown. Drawing with all overlays on adds less than about 4 ms per frame on desktop. Report what you measured.
- [ ] Overlays off means a pixel-identical chart to main (or as close as fonts allow). Show before and after screenshots.

### Stage 3: Python Smart Trendlines job (backend)
Build `tools/ta_lines.py`, `tests/test_ta_lines.py` and a new workflow `.github/workflows/ta-lines.yml`. See section 6 for the job spec and the binding scoring rules.
Accept when:
- [ ] Offline unit tests pass on fixtures. They cover pivot detection, level clustering (ATR-based merge), sloped-line fit, scoring (including recency in candles, close-based breaks with flips, capped touches, the distance penalty), the comparative layer with hysteresis, the line caps (at most 3 levels and 2 sloped per timeframe), and the JSON schema plus a validator.
- [ ] Running `python3 tools/ta_lines.py --out /tmp/ta-lines.json` locally against live public candles gives sensible lines. Include a screenshot of them drawn on the chart in the handback.
- [ ] The workflow is written but **never run** (see section 6). Running it is Sunil's call.

### Stage 4: Front end draws trendlines
Build:
- Fetch `ta-lines.json` from the data branch (`https://raw.githubusercontent.com/Schadhaxx/paperstreetbtc/data/ta-lines.json`, `cache:'no-store'`, timeout, same style as `RAW` in btcchart.js) only when Trends is on.
- Pick the timeframe for the current view (see section 6). Draw horizontal levels as full-width lines (green for support, red for resistance) with a small right-edge price label. Draw sloped lines between their anchors, extended to the right edge. Clip to the plot.
- **Stale rule:** if `asOf` is older than 3 × the timeframe's update interval (1h lines older than 45 min, 4h older than 3 h, 1d older than 36 h), hide the lines and show "Trendlines updating…" in the panel. Missing file or bad JSON: hide quietly and show the same note. Never show an error over the chart.
- Toggles are remembered per device, and all overlays are off by default.
Accept when:
- [ ] Lines line up with price at every range where Trends applies. With a fixture file served locally, the stale, missing and bad-JSON cases each hide the lines with the panel note.
- [ ] Full test run, whole-diff scope check and screenshots as in section 8. A perf note is included.
- [ ] Stop here. **No go-live.** Hand back (section 10).

## 6. Backend trendline job spec (Stage 3)

**Where it sits in the pipeline:** a new, separate workflow `.github/workflows/ta-lines.yml`, kept apart from `prices.yml` so its cron can never fire the prices job, the same reason `desk-intraday.yml` is separate. It runs `tools/ta_lines.py` from main and commits **only `ta-lines.json`** to the **`data` branch**. Copy the safe pattern in `prices.yml`: fetch the data branch with retries, never create an orphan on a transient error, commit only if the content changed, and push with a fetch-rebase-retry loop. Use its own concurrency group, `ta-lines`. It must never touch `prices.json`, `history.json`, `desk-live.json` or main.

**Triggers:** `schedule` (plus `workflow_dispatch` for later manual runs). **No `push` or `pull_request` triggers**, so pushing your branch can never start it. Scheduled workflows only run from the default branch, so nothing runs until Sunil merges it.

**Schedule (BTC trades 24/7, so it runs every day):**
- 1h lines: every 15 min (`*/15 * * * *`)
- 4h lines: recompute at the first run after each hour (cheaper: recompute 4h when the minute is under 15)
- 1d lines: once a day just after 00:05 UTC (the daily close used by the chart)
- One workflow run can do all three, with an in-job gate deciding which timeframes to recompute. Unchanged timeframes keep their previous block, and their `asOf` is not touched.

**Data sources (public, no keys):** Coinbase Exchange candles `https://api.exchange.coinbase.com/products/BTC-USD/candles` with `granularity=3600` (1h, up to 300 per request, so page back) and `86400` (1d). Coinbase has no 4h granularity, so **build 4h by aggregating 1h in UTC 4-hour buckets the same way the front end does** (`agg4hFromHourly` in btcchart-panel.js). For daily, also seed from `assets/data/btc-daily.json` so the long history matches the chart. Add retries and a timeout. If a source fails, keep the previous block (do not wipe it).

**Lookbacks (starting values, tune them):** 1h uses the last 500 candles, 4h the last 500, and 1d the last 400.

**Algorithm (no AI):**
1. Pivots: fractal swing highs and lows with a timeframe-scaled window (for example k = 3 for 1h, 3 for 4h, 5 for 1d).
2. Horizontal levels: cluster pivot prices with a tolerance of `ATR(14) × factor`, not a fixed %. Merge levels closer than about 1 ATR, and dedupe across variants.
3. Sloped lines: connect pivot pairs (lows for support, highs for resistance), keep lines with 3 or more touches within tolerance, a sane slope, and no candle **close** beyond the line by more than the buffer.
4. **Scoring (binding changes to Grok's sample, from the approved rollout plan):**
   - Recency is measured **in candles, not days**, with windows scaled per timeframe.
   - Spread tolerance comes from **ATR**, not a fixed %.
   - **Broken** means a candle **closes** beyond the level by a buffer (for example 0.5 ATR), not a wick or a live tick. A broken support **flips** to resistance (and the reverse) instead of scoring −10 and disappearing.
   - The touch bonus is **capped and diminishing**, so one level can't dominate. Add a **distance-from-price penalty** so far-away lines drop out.
   - Sloped lines get **their own scorer**: touches on the line, slope sanity, a recent touch, and no breaking closes.
   - **Comparative layer:** run several variants (lookback and cluster sensitivity), compare them by the normalised total score of the top N, and add a **stability bonus for lines shown in the last run** (hysteresis, read from the previous `ta-lines.json`) so lines don't flicker.
   - **Caps:** at most **3 horizontal levels and 2 sloped lines** per timeframe.

**Output file: `ta-lines.json` on the data branch** (small, well under 20 KB):
```json
{
  "schema": 1,
  "generated": "2026-11-16T14:15:03Z",
  "source": "coinbase",
  "timeframes": {
    "1h": {
      "asOf": "2026-11-16T14:00:00Z",
      "lastClose": 91234.5,
      "atr": 412.3,
      "levels": [
        {"id": "L1", "kind": "support", "price": 90120.0, "touches": 4,
         "lastTouch": "2026-11-16T09:00:00Z", "score": 14.5, "flipped": false}
      ],
      "sloped": [
        {"id": "S1", "kind": "resistance", "t1": "2026-11-14T02:00:00Z", "p1": 93500.0,
         "t2": "2026-11-16T06:00:00Z", "p2": 92100.0, "touches": 3, "score": 11.0}
      ]
    },
    "4h": { "...": "same shape" },
    "1d": { "...": "same shape" }
  }
}
```
All times are UTC ISO 8601. Prices are in USD (the front end converts to CAD through the existing `curVal`). Include a validator in the script that refuses to write a file failing the schema, with no NaN or Infinity values (`allow_nan=False`).

**Which lines show in which view (proposed default, confirm with Chief of Staff):** 1D Line / 1H candles uses `1h`. 1D 4H candles and 1W 4H candles use `4h`. 1W daily, 1M, 3M, 6M, YTD and 1Y (line or candles) use `1d`. On 5Y / 10Y / Max, Trends is disabled with a short "Not available on this range" note.

**Rules for the job:**
- **Do not run the workflow.** No `workflow_dispatch`, no "Run workflow" button, and no manual runs of any workflow, ever, without Sunil's explicit yes, relayed by Chief of Staff.
- Do not write to the `data` branch from your machine. Test with `--out` to a local file and serve it locally.
- Workflow files may need a token with `workflow` scope to push. If your push is refused because of the workflow file, push everything else and leave the `.yml` in the handback folder as a file instead. Chief of Staff will add it. Do not go looking for other credentials.

## 7. File scope

**Allowed to change or add:**
- `assets/js/btcchart-panel.js`: **keep the changes small**. Add hooks only (the call to draw overlays after each native draw, the row-2 markup for the two pills, the RSI strip container, and the live-tick redraw). The Chart.js removal on Wed Nov 18 edits this same file, so small hooks keep the rebase easy.
- **New** `assets/js/btcchart-ta.js`: all TA maths, drawing, panel, chart-type menu logic and state. Load it from the panel (lazily, like the panel itself), with its own pin.
- **New** `assets/css` rules for the pills, panel and strip, either in the existing panel style block or a new small stylesheet loaded with the TA script. Do not restyle anything else.
- `assets/js/btcchart.js`: only the panel pin line (`btcchart-panel.js?v=...`) and anything strictly needed to pass a TA hook.
- Every HTML page that references `btcchart.js?v=et26`: **only** the pin change on that one script tag (index.html, screener.html, compare/index.html, clock/index.html, recap pages and so on). Use `rg -l "btcchart.js\?v=et26"` to find them all.
- `clock/clock-v4.css`, `clock/clock-v4.js` and their pin lines in `clock/index.html`: only if needed so the panel sits correctly in the stage and full-screen bar. Keep it minimal.
- **New** `tools/ta_lines.py`, `tests/test_ta_lines.py`, `tests/test_ta_indicators.js`, `tests/fixtures/ta/*`, `.github/workflows/ta-lines.yml`.
- `tests/run_all.sh`: only to add your new test lines.

**Do not touch:** the Desk (`screener*.js`, the Desk charts), `s2.js` / the homepage hero, `compare.js`, `s5.js` (your chg24h fix lives on its own branch), the Worker (`worker/`), `prices.yml`, `desk-intraday.yml`, any data files, `CNAME`, logos and images, `chart-theme.js`, and Chart.js vendor files. Do not add libraries or CDNs.

## 8. Pin rules

- **Never reuse a pin that has ever been served.** Every changed JS or CSS file gets a **fresh** pin, and every page that loads it is updated.
- Use a new TA pin family so collisions are impossible: `btcchart.js?v=ta1`, `btcchart-panel.js?v=ta1` and `btcchart-ta.js?v=ta1` (plus `clock-v4.* ?v=ta1` if you change the clock files). Before handback, check that each one was never used: `git log --all --oneline -S'v=ta1'` must show only your own commits. If you bump again later, go to `ta2`, `ta3` and so on.
- Burned pins as of Nov 15: btcchart.js et26 and everything before it, panel et24 and before, clock v4f to v4l, s2 p6 to p9.
- At rebase time, if main has moved the same file to a newer pin, keep a fresh pin that is higher than anything served.

## 9. Tests and checks (all required for the handback)

1. `node --check` on every changed or added JS file. `python3 -m py_compile tools/ta_lines.py`.
2. New unit tests pass: `node tests/test_ta_indicators.js`, `python3 tests/test_ta_lines.py`.
3. `bash tests/run_all.sh` on **main first** (to get your baseline), then on your branch. **No new failures.** For reference, Chief of Staff's run on main at 84252923 (Nov 15, 12:59 AM ET) had **13 suites failing before any TA work**: `cmp_daily_py`, `cmp_js`, `datatest_strict`, `headless`, `mutation`, `needchart_retry`, `oi001_compare_scope`, `oi001_label`, `reviewer_repros`, `test_freeze`, `test_freeze_liveURL`, `tiingo`, `vehicle_daily`. Your baseline may differ a little (network, time of day). Report both lists side by side.
4. Existing BTC chart tests must stay green: `test_speed_option2.js`, `test_stage2_step2.js`, `test_stage2_step3.js`, `test_stage2_step4.js`, `test_candle_date_guardrail.js`, `test_clock_light_mode.py`, `test_clock_cad_fallback.py`.
5. **Screenshots** (Playwright; reuse `mockups/render.py` / `make-sheets.py`), saved in the handback folder:
   - Phone 390×844 (plus SE 375×667), iPad 1024×1366 portrait and 1366×1024 landscape, desktop 1440×900
   - **Light and dark** for each
   - Clock page normal, **full-screen chart** (iPhone CSS mode, and Fullscreen-API mode on desktop and iPad), and full-screen price (TA hidden)
   - The popover on a regular page (for example `/`) on desktop, and the bottom sheet on the phone
   - States: closed, panel open, each overlay alone, all on, RSI collapsed, candles view with overlays, 1D view, a long range (1Y)
   - Before and after "all overlays off" pairs, to prove nothing changed
   - The overlap-check JSON for the open-panel shots (target: 0 hits)
6. **Whole-diff scope check:** `git diff --stat origin/main...HEAD` and `git diff --name-only origin/main...HEAD`. Every file must be on the allowed list in section 7. Paste the list in the handback. Explain any surprise or remove it.

## 10. Rules

- **Branch only.** Name it `pepper-ta-1`. Branch from current main, and **rebase onto the latest main before handback** (fast-forward-able onto main).
- **Never push to main. Never force push** (if you must rewrite your own branch, push a new branch `pepper-ta-2` instead). **No merge, no PR into main.**
- **No go-live.** The order is: Chief of Staff reviews and fixes on Fri Nov 20, then regular Grok does QA, then Sunil gives the go. Go-live happens only outside market hours (9:30 AM to 4 PM ET) and **never on a Sunday**.
- **No workflow runs** (no `workflow_dispatch`) without Sunil's yes.
- **Scope = TA only.** Your hero cosmetic and chg24h fixes stay on their own branches.
- No secrets in code, commits, logs or chat. The TA job needs no keys.
- Don't change behaviour outside TA. If you find a bug elsewhere, write it in the handback and don't fix it here.
- If something in this brief is unclear or seems wrong, choose the safer option, write down what you chose, and keep going. Don't stall.

## 11. Handback checklist (send this to Sunil to pass to Chief of Staff)

```
TA HANDBACK — Pepper
Branch: pepper-ta-1
Head SHA: <full sha>
Based on main: <sha>   (rebased on: <date/time ET>)
Stages done: 1 [ ] 2 [ ] 3 [ ] 4 [ ]   (per-stage commit SHAs: ...)
Not done / partial: ...
Pins used: btcchart.js ta?, btcchart-panel.js ta?, btcchart-ta.js ta?, clock ta? (each checked never served: yes/no)
Files changed (git diff --name-only origin/main...HEAD): ...
Tests: node --check OK? / test_ta_indicators / test_ta_lines / run_all main-vs-branch failure lists
Perf: ms per frame all overlays on (desktop, phone emulation)
Overlap check: hits = 0? (file path)
Screenshots: <path in repo or zip name>
Workflow file: in branch / left as file (why)
Workflow runs: none
Known issues / decisions I made on open questions: ...
Questions for Chief of Staff: ...
```

Put the screenshots in `handback/ta/` on your branch **only if** they are small (under about 10 MB total). Otherwise zip them and send the zip through Sunil. Chief of Staff will remove `handback/` before anything goes live.

## 12. Open questions (Chief of Staff will settle these with Sunil; use the proposed defaults meanwhile)

1. **Comparisons on (S&P / Gold / MSTR):** hide TA with a note (proposed), or draw it on the BTC line in % terms?
2. **Long ranges (5Y / 10Y / Max) and weekly / monthly candles:** Trends disabled there (proposed), or add weekly lines later?
3. **Build-and-review flow:** the approved plan had a stop for Sunil's go after each stage. For this week, Sunil asked for a build through to the Friday review. Keep the per-stage commits so each stage can still be reviewed and approved on its own.
