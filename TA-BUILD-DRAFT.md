# TA build — working draft (Pepper's review, Sun Nov 15 2026)

**Status: DRAFT — this is the official working draft at this stage.** It records Sunil's notes, the corrected chart-type labels, and Pepper's review of Chief of Staff's brief. It directs the build on branch `pepper-ta-1`. Chief of Staff reviews this branch Fri Nov 20 10 AM ET.

**Source:** Chief of Staff's brief, branch `docs/ta-brief`, file `docs/ta-brief/BRIEF-pepper.md` (reference only — do not merge that branch). Rollout plan approved by Sunil Nov 13 3:46 PM ET. GUI = mockup option C (Sunil chose C).

## The job
Add an expandable TA pill to the Bitcoin charts (popups + `/clock/`) with four overlays, all off by default, toggles remembered per device:
1. Bollinger Bands (20, 2σ)
2. Moving average — SMA | EMA switch, period 20 | 50 | 200 (one at a time)
3. RSI (14), thin strip under the chart
4. Smart Trendlines — support/resistance levels + sloped lines, computed by a Python job, drawn by the browser

Browser maths for Bollinger/SMA/EMA/RSI on the native canvas, no Chart.js. Smart Trendlines via `tools/ta_lines.py` + workflow `ta-lines.yml` writing `ta-lines.json` to the data branch. No AI in the job.

**Schedule:** build Mon Nov 16 – Thu Nov 19 on branch `pepper-ta-1`. Hand back to Chief of Staff by Thu Nov 19, 11:59 PM ET. Chief reviews + fixes Fri Nov 20 10 AM ET, then regular Grok QA, then Sunil's go. **Branch only. No go-live. No workflow runs (no `workflow_dispatch`) without Sunil's explicit yes.** Sunil approves the plan, not the code. **Token budget is the binding constraint:** weekends drain Grok to ~80% and Muse to ~60%; the remaining tokens are reserved for site maintenance and operations in a high-stress week. Keep the build tight — minimise rework and iteration.

**Where TA appears:** every BTC popup chart + `/clock/` inline (both full-screen modes). Same code: `assets/js/btcchart-panel.js`. **NOT on the Desk charts** (`screener.html`, `screener-chart.js`, `screener-indicator-chart.js`). Do not touch them. Note: `screener.html` loads `btcchart.js` for its Live BTC pill, so the BTC popover there does get TA — that is expected.

---

## Workflow & roles (Sunil, Mon Nov 16 ~00:14 — refined plan, approved)
**The flow:** This draft IS the build plan. Sunil + Pepper refine it through conversations this week → send it to Chief for revisions → Chief revises it and sends it back to Pepper → Pepper builds all stages (first build) → Chief reviews and takes over as master builder → Grok Bot reviews (around the Friday Grok token reset) and takes it home.
- **Pepper (Muse) — builds all stages (first build).** The only token supply left (Grok is on fumes). Builds Stages 1–4 on branch `pepper-ta-1` from the Chief-revised plan, and hands back to Chief. This is a handover-week arrangement, not permanent — once Grok Bot's tokens recover, it goes back to being the primary builder with Pepper assisting.
- **Site Launch — GUI master builder.** Has basically already built the GUI (the option C mockup). Pepper communicates with Site Launch **through Sunil** for GUI adjustments — Pepper does not redesign the GUI. Surface GUI issues early in Stage 1 so the round-trip (Pepper → Sunil → Site Launch → back) does not block the build.
- **Chief of Staff — project manager, then master builder.** Wrote the brief, manages the plan, revises this build plan and sends it back to Pepper. Reviews on Fri Nov 20 10 AM ET, then takes over as master builder.
- **Grok Bot — first approver, then takes it home.** The primary bot, in charge in principle; nothing goes live without its approval (and Sunil's go). Reviews after the Friday token reset and finishes the job.
- **Concern:** Grok Bot is on fumes. If it cannot do a real review, the first-approver step is a formality and the real gate is Chief (Fri) + Sunil. Either reserve Grok Bot enough tokens for a genuine review, or be explicit that Chief's Friday review is the substantive check.
- **Build start:** Pepper builds after Chief's revisions come back (not necessarily Monday after 10 AM). The exact start depends on when the revisions arrive. Nov 22 is moveable, so there is flexibility — do not rush to hit a date.
- **Conflicts:** if the Chief-revised plan conflicts with the refined plan (or any two instructions conflict), Pepper flags it to Sunil and does not proceed on the disputed point until Sunil decides. Sunil is CEO — he decides who wins the argument.
- **Authority (Sunil, Mon Nov 16 ~00:23):** Pepper is allowed — and expected — to challenge Chief of Staff's plan and speak clearly when Pepper thinks it is wrong. Chief outranks Pepper but is NOT Pepper's superior; Sunil is. If Sunil agrees with Pepper's judgement, Pepper effectively acts as Chief's superior in that decision. Do NOT treat Chief's plan as untouchable or defer to it when Pepper disagrees — raise the judgement to Sunil and let him decide.

---

## CORRECTED chart-type labels — the fix (Sunil, Sun Nov 15 ~23:23)

Sunil spotted this looking at the option C GUI shell: **"Candles" was treated as separate from 1H and 4H. Something looked off.** Confirmed in the mockup source (`ta-mock.js:37-39`) and the live button rows (`btcchart-panel.js:726-727`). Overall GUI still good — Sunil approved option C. This is a labelling fix, not a redesign. **The build must use the corrected scheme below, not the mockup's labels.**

### The error
The labels mix chart **type** and candle **size** as if they are the same kind of choice.
- On 1D the live buttons are Line / 1H / 4H. "1H" and "4H" sit at the same level as "Line", as if they are chart types — but they are candle **sizes**. The "Candles" type is invisible there; it is implied by picking 1H or 4H.
- On the ranges the buttons are Line / Candles / Size (4H / Daily / Weekly / Monthly). There "Candles" **is** the type and the size is separate.
- Same concept, different level depending on the range. That is why it looks off — "Candles" reads as a separate thing from 1H and 4H, when 1H and 4H *are* candles.

Related, in the mockup itself: the chart-type pill reads the active type button and appends " candles" only for 1H/4H. So 1D shows "1H candles" / "4H candles" (good), but a range candle view shows just "Candles" with **no size** — you cannot tell from the pill whether you are on Daily, Weekly, Monthly or 4H. The brief intends "Candles · Weekly" (type · size) but the mockup does not do it.

### The corrected scheme (directs Stage 1)
Use **one hierarchy everywhere — Type first, then Size.**
- **Type:** Line / Candles.
- **Size** (only when Candles is on): 1H / 4H / Daily / Weekly / Monthly — only the sizes the current range allows.
- **Menu:** on 1D, offer Line, then Candles with a size choice of 1H / 4H. Do **not** list "1H" and "4H" as if they are types. On ranges, keep the existing Line / Candles / Size structure — that part is already correct.
- **Pill label:** always show type + size for candles — "1H candles", "4H candles", "Candles · Daily", "Candles · Weekly", "Candles · Monthly". Never a bare "Candles" with no size. Never a bare "1H" / "4H" with no "candles".
- Note: the brief's menu spec (§4) still lists the 1D options flat as "Line, 1H, 4H". The build restructures that to the Type-then-Size form above. Confirm with Chief on Monday.

---

## Candle inset — item 1 of the TA build (Sunil, Mon Nov 16 ~00:26)
Sunil decided (in the BTC chart cleanup side chat) that cleanup item 1 is rolled into the TA work as item 1. **Inset the first and last candles from the plot edges by half a slot**, so every candle sits fully inside the plot. It is done in **Stage 1, before the Stage 2 overlays are drawn** — the overlays must be built on the final geometry, so the indicator lines align with the inset candles. The candle inset changes the x positions of the candles, so Stage 2's overlay drawing must use the same inset x positions. The rest of the chart cleanup (items 2–16) stays on hold while tokens go to TA work.

---

## Build path — four stages, in order, one commit per stage

Do not start a stage until the previous one meets its acceptance criteria. Keep the per-stage commits so each stage can be reviewed on its own.

**Stage 1 — GUI shell, no overlays.** First, the **candle inset (item 1)** — inset the first and last candles from the plot edges by half a slot, so every candle sits fully inside the plot (see the Candle inset note above). Then the chart-type pill + menu (using the corrected labels above), TA pill, floating panel, RSI strip container. Toggles wired to state, saved per device. Nothing drawn yet. Panel is a child of the chart stage/dialog (never `body`) so it renders in Fullscreen-API mode. It must never cover the price pill, Keep screen on (`#wakeBtn`), Exit, Price clock, Switch to chart, or the theme dot. iPhone chart height unchanged with RSI off. Works in popover (desktop), bottom sheet (phone), clock inline, both full-screen modes. Existing tests pass.

**Stage 2 — Browser indicators.** SMA/EMA (20/50/200, one at a time), Bollinger (20, 2σ), RSI (14, Wilder smoothing), computed in plain JS, drawn on `#bcC` after the price series, in every native view (1D line, 1D 1H/4H candles, range line, range candles all sizes). **Warm-up:** at least 200 extra candles before the visible window per timeframe. If warm-up data cannot be loaded, draw only from the point where it is valid. **Never draw a wrong value.** Live updates: when the live price ticks, indicators recompute and redraw, no flicker, no full refetch. **BTC only** — when a comparison asset (S&P/Gold/MSTR) is on, hide the overlays with the one-line note (proposed default, confirm Monday). Respect the log scale. RSI strip draws the line + 30/70, collapse tab works, shares x positions with the main plot. Tooltip/scrub shows indicator values for the hovered candle. New test file `tests/test_ta_indicators.js` with reference values. Acceptance: unit tests match reference values; overlays line up in every view, light/dark, 390px/iPad/desktop; drawing with all overlays on adds < ~4 ms per frame on desktop (report measured numbers); overlays off = pixel-identical chart to main.

**Stage 3 — Python Smart Trendlines job (backend).** Build `tools/ta_lines.py`, `tests/test_ta_lines.py`, `.github/workflows/ta-lines.yml`. Pivots (fractal swing highs/lows), horizontal levels (cluster pivot prices, ATR-based tolerance, merge within ~1 ATR), sloped lines (pivot pairs, 3+ touches, sane slope), scoring per the rollout plan (recency in **candles** not days, ATR spread tolerance, close-based breaks with flips, capped/diminishing touch bonus, distance-from-price penalty, comparative layer with hysteresis, caps 3 levels + 2 sloped per timeframe). **Start with the minimal version (Stage 3a)** — see the Stage 3a note below. Add the comparative layer + hysteresis only if the basic version flickers, and only with Chief's agreement (it defers binding rules). Data: Coinbase Exchange candles (1h, 1d); build 4h by aggregating 1h in UTC 4h buckets the same way the front end does; daily seeded from `assets/data/btc-daily.json`. Schedule: 1h every 15 min, 4h recompute after each hour, 1d once a day just after 00:05 UTC. Output `ta-lines.json` on the data branch (schema 1, per-timeframe `asOf`, `lastClose`, `atr`, `levels`, `sloped`). **Workflow written but NEVER run** — running it is Sunil's call. Acceptance: offline unit tests pass; running locally against live candles gives sensible lines (screenshot in handback); workflow written but never run.

**Stage 4 — Front end draws trendlines.** Fetch `ta-lines.json` from the data branch only when Trends is on. Pick the timeframe for the current view: 1D Line/1H = `1h`; 1D 4H + 1W 4H = `4h`; 1W daily, 1M, 3M, 6M, YTD, 1Y = `1d`; 5Y/10Y/Max = Trends disabled with "Not available on this range". Draw horizontal levels as full-width lines (green support, red resistance) with a small right-edge price label; sloped lines between anchors, extended to the right edge; clip to the plot. **Stale rule:** if `asOf` is older than 3× the timeframe's update interval (1h >45 min, 4h >3 h, 1d >36 h), hide the lines and show "Trendlines updating…" in the panel. Missing file or bad JSON: hide quietly, same note. Never an error over the chart. Toggles remembered per device, all off by default. Acceptance: lines line up at every range; stale/missing/bad-JSON cases hide the lines with the panel note; full test run, scope check, screenshots, perf note. **Stop here. No go-live. Hand back.**

---

## Suggestions — Pepper's review of the plan (directs the build)

**1. Stage 1 is the highest-risk stage — gate it hard.** The chart-type pill replaces core switching behaviour (state `CT`, `RGCT`, `RGGRAN`, fallbacks, the 4H fallback message on 1W, BTC-only candles). Safest approach: keep the old buttons in the DOM (hidden) and have the menu drive them, so picking an option behaves exactly like tapping today's buttons. Do not start Stage 2 until every range × type combination is verified identical to today. This is the acceptance test that matters most.

**2. Measure performance on a phone, not just desktop.** The <4 ms per frame budget is stated for desktop, but the primary device is iPhone. Add a phone-emulation perf number to the handback alongside the desktop one. If all overlays on is noticeably slower on a phone, say so plainly rather than only reporting desktop.

**3. Warm-up data is a real fetch — confirm it does not slow first load (Stage 2).** 200+ warm-up candles per timeframe means, for example, ~8 days of 1H candles for the 1D view and ~33 days of 1H (aggregated to 4H) for the 1W 4H view. Reuse the existing fetch helpers and caches as the brief says, and confirm the first-load time does not regress. The fallback is already correct: draw only from the point where the data is valid, never a wrong value.

**4. Market God research is NOT in this build — keep it out.** The scrub-triggered TA read, the narrative layer (one-line stance + falsification levels), the two bot takes side by side, Desk as a TA surface, and the handoff pipe are research, not this job. They are a later phase. In particular, the handoff pipe (site → bot → read back) is a new integration/dependency that needs scoping before anyone builds it. Do not let any of it creep into Stages 1–4.

**5. Keep the TA hooks in `btcchart-panel.js` small.** The Chart.js removal (Chief's job, Wed Nov 18) edits the same file. Small hooks keep the rebase easy. Rebase onto current main before handback (the brief requires it).

---

## Token burn — grading the stages (Pepper, Sun Nov 15 ~23:40)
Read the full brief, rollout plan, Grok spec, and scoring sample. Graded on token burn (most → least).
- **Stage 2 (browser indicators): HIGHEST.** Most new logic (SMA/EMA/Bollinger/RSI + Wilder smoothing), 200-candle warm-up per timeframe, drawing in every view, live-tick recompute, tooltip integration, reference-value unit tests, biggest screenshot surface. Most iteration-prone — if the math or warm-up is off, it eats tokens in fix rounds.
- **Stage 3 (Python trendlines): HIGH but contained.** The algorithm is the most complex single piece and the most likely to need tuning, but it is one self-contained file with no screenshots and offline tests. The comparative layer + hysteresis is the part most likely to burn tokens (see Stage 3a below).
- **Stage 1 (GUI shell): MEDIUM-HIGH.** Moderate code, but it touches the big panel file, replaces core switching, and needs every range × type combo verified plus the overlap check.
- **Stage 4 (draw trendlines): LOWEST.** Small code, reuses Stage 2, fixture tests. Cheapest by a clear margin.
**Biggest savers:** trim the §9 screenshot matrix (phone 390 dark + desktop 1440 light for most states; full matrix only where it actually catches bugs); test the Stage 2 math offline first (unit tests, text output) before drawing anything; start Stage 3 with the minimal version (Stage 3a); one review pass at handback, not per-stage; do not re-read the big files (use targeted reads after Stage 1); build directly, no subagents (a sequential build with dependencies is cheaper direct than fanning out).

---

## Stage 3a — minimal trendlines (regular Grok's review + Pepper's verdict, Sun Nov 15 ~23:52)
Regular Grok broke down the smart trendline tool and scoring (pivots → cluster → score → top N; sample scoring = `grok-scoring-sample.py`) and the Stage 3 improvements. Pepper reviewed it. **Verdict: Grok is right.**
- **Core is textbook and reliable.** Pivot-based support/resistance (find swing highs/lows, cluster nearby pivots into levels, score, keep the strongest few, optionally fit sloped lines) is standard, not speculative.
- **The sample scoring's flaws are real, and the Stage 3 improvements fix them.** Recency in days is meaningless across timeframes (7 days = 168 candles on 1h, 7 on 1d) — candles are correct. Fixed % spread does not scale with volatility — ATR is correct. `is_broken` uses the live price, so a wick or tick would kill a level — close-based break with a buffer is correct. -10 for broken is wrong because a broken support often becomes resistance — the flip is correct. Touches are linear and unbounded — diminishing returns is correct.
- **Comparative layer + hysteresis is the speculative part and the easiest to over-engineer.** It is a stability feature, not an accuracy feature. It exists to stop flicker; if the simple version is already stable, it is unnecessary.
- **Minimal version (Stage 3a) — the recommended start:** detect pivots; cluster with a fixed ATR-based tolerance; score only on touches (diminishing), recency in candles, and not-broken-on-close (with flip); take the top 3 horizontal levels (+ 1–2 obvious sloped lines if straightforward). No comparative variants, no hysteresis, no distance penalty yet. Ship it and watch stability.
- **Stability trigger (when to add the comparative layer + hysteresis):** if the top-3 set changes by more than one line between consecutive runs (with only one new candle), that is flicker — then add them. If the set is stable run to run, do not add them.
- **Refinements:** pivot lookback k=3 (brief) is more sensitive than Grok's usual 5–10 — a tuning knob if the lines look noisy. The 4h aggregation must match the front end's `agg4hFromHourly` exactly (same UTC bucket boundaries), or 4h levels will not line up with the 4h candles. Sloped lines are the fiddliest part of the minimal version — if troublesome, ship horizontal levels first and add sloped as a follow-up. The distance penalty is a small fix if far-away levels show up.
- **FLAG — needs Chief's agreement:** Stage 3a defers two binding scoring rules from the approved rollout plan (the comparative layer and the hysteresis). That is a plan change, so it needs Chief's agreement on Monday (and Sunil's). Recommended, not yet decided.

---

## Stage 2 approach — math first, offline (Pepper, Sun Nov 15 ~23:58 — approved by Sunil)
The key move: prove the math offline before touching the chart. That is what keeps Stage 2 (the highest token-burn stage) from eating tokens in "draw it, screenshot it, see it's wrong" loops.
1. **Read the code needed, targeted not full re-reads.** The native renderers (`draw1DNative`, `drawDailyNative`, `drawCandles1D`, `drawCandlesRange`) — the x/y mapping and where to hook the TA draw after the price series. The fetch helpers for 1h/4h/daily — how candles are fetched and cached, so the warm-up window can be extended. Panel.js was already read for Stage 1; these are greps, not re-reads.
2. **Math + unit tests first, offline.** Write SMA, EMA, Bollinger (20, 2σ), RSI (14, Wilder smoothing) as pure functions in the new `btcchart-ta.js`, plus `tests/test_ta_indicators.js` with hand-checked reference values. Run with node. Fix until green. Text output, cheap. No chart, no screenshots yet.
3. **Warm-up data.** Extend the existing fetch to pull 200+ extra candles before the visible window per timeframe. Daily reads further back from the daily series; 1H/4H reuse the Coinbase helpers and page back (4H warm-up comes from extra 1h candles aggregated the same way the front end does). Absolute rule: if warm-up cannot load, draw only from the valid point. **Never a wrong value.** Check the first visible candle has a valid value.
4. **Draw.** Hook into the native renderers so the TA draw runs right after the price series, using the same x/y mapping so the lines line up. Respect log scale. RSI strip draws the line plus 30/70 in the strip container from Stage 1, sharing x positions with the main plot. Colours from the mockup (MA pink, Bollinger violet, RSI violet), light-mode variants via `psC`.
5. **Live ticks, comparison, tooltip.** On a tick, recompute the affected window and redraw — no full refetch, no flicker. Comparison on (S&P/Gold/MSTR) hides the overlays with the note (proposed default, pending Monday). Tooltip/scrub shows the indicator values for the hovered candle/point.
6. **Verify cheapest first.** Unit tests (already green) → one phone 390 dark screenshot, all overlays on → one desktop 1440 light screenshot → a programmatic before/after all-off pixel diff (reported as text) to prove pixel-identical → a perf number in ms/frame (desktop + phone emulation). Only expand the screenshots if something looks off.
**Biggest risks:** the warm-up fetch (does it slow first load?) and the math (killed by the math-first order). The warm-up fetch is the part not yet verified against the existing code — it is checked in step 1.

---

## Screenshots — the token-saving plan (Pepper, Sun Nov 15 ~23:59 — approved by Sunil)
The brief's §9 matrix (phone + SE + iPad both ways + desktop, light and dark, every state, before-and-after pairs) is the biggest hidden token cost — every image reviewed costs tokens. This plan replaces it. It is a deviation from §9, Sunil-approved; Chief sees it here.
- **Automated checks instead of eyeballing.** The overlap check is already automated (`overlap-check.json`, text not an image) — use it for panel overlap. The "pixel-identical all-off" check is a programmatic image diff, reported as text ("0 pixels differ"). Do not eyeball what a script can check. This is the biggest saver.
- **Two core setups, not the full matrix.** Phone 390 dark (primary device, primary theme) plus desktop 1440 light (the other extreme) for most states. iPad, SE, and the second theme only spot-checked — only if the core shots show a layout issue that might differ there, or only for the panel and fullscreen states where iPad layout actually differs.
- **Screenshots live in the handback folder, not in chat.** They go in `handback/ta/` (or a zip), as the brief already says. Chief reviews the folder. Only the two or three key shots are shown to Sunil in chat (phone dark all-on, desktop light panel open). The rest never enter the conversation, so they cost nothing here.
- **Reuse the mockup render scripts** (`mockups/render.py` / `make-sheets.py`). They already generate the shots and the overlap-check JSON. Do not rebuild screenshot tooling.
- **One "all on" shot per core setup, not one per overlay alone.** The overlays are drawn independently, so if all-on lines up, each alone will too. Only screenshot an overlay alone if the all-on shot shows a problem with it.

---

## Concerns / open questions — for Monday 10 AM and Chief

**1. Nov 22 — moveable, not a hard deadline (Sunil, Sun Nov 15 ~23:36).** The rollout plan puts Stage 1 on Sun Nov 22, but the handover builds Mon–Thu Nov 16–19 this week. Sunil: the date is moveable, there is a lot of flexibility, and if the build cannot make Nov 22 that is OK. Do not rush or cut corners to hit Nov 22.

**2. Trendlines cannot be verified end-to-end until the workflow runs.** The workflow is written but never run (Sunil's call). Stage 4 can only be tested with a locally generated `ta-lines.json` fixture. The handback must state this plainly: the trendline path is untested against real scheduled data until the workflow runs.

**3. Comparison-on behaviour needs a decision (Monday).** When S&P/Gold/MSTR comparison is on, the chart is in % rebased mode. Proposed default: hide TA with the note "TA shows on BTC alone. Turn off comparisons to see it." Alternative: draw TA on the BTC line in % terms. Chief asked Sunil to confirm — this is one of the pending Monday items.

**4. Build-through vs per-stage go (Monday).** The approved plan had Sunil stopping for his go after each stage; this week Sunil asked for build-through to the Friday review. Keep the per-stage commits so each stage can still be reviewed and approved on its own. Chief asked Sunil to confirm.

**5. Chart.js removal lands Wed Nov 18, same file.** `btcchart-panel.js` is edited by both the TA build and the Chart.js removal. Coordinate the rebase; if the removal is on main by Thursday, rebase onto it before handback.

**6. Three small calls (Monday, Chief asked Sunil):** (a) TA tools hide while S&P/Gold/MSTR comparison is on; (b) trendlines off on 5Y/10Y/Max; (c) each chart view uses the trendlines matching its timeframe. Sunil to say "fine" if all work.

---

## Out of scope for this build
- Desk charts and Desk TA (the Desk is explicitly out of scope; a phase 2 plan for Desk stock charts comes later, after the native rebuild).
- Market God research items (see suggestion 4 above).
- No volume bars, no event dots, no new ranges/buttons beyond the chart-type pill and TA pill.
- No data or price changes. No new libraries or CDNs.

## Files and pins
- **New:** `assets/js/btcchart-ta.js` (all TA maths, drawing, panel, chart-type menu logic, state — loaded lazily from the panel, own pin). `tools/ta_lines.py`, `tests/test_ta_lines.py`, `tests/test_ta_indicators.js`, `tests/fixtures/ta/*`, `.github/workflows/ta-lines.yml`.
- **Changed, small hooks only:** `assets/js/btcchart-panel.js` (hooks to draw overlays after each native draw, row-2 markup for the two pills, RSI strip container, live-tick redraw). `assets/js/btcchart.js` (panel pin line only + anything strictly needed for a TA hook). Every HTML page that loads `btcchart.js` — pin change only. `clock/clock-v4.css` / `clock-v4.js` + pin lines — only if needed so the panel sits correctly in the stage/full-screen bar. CSS rules for pills/panel/strip (existing panel style block or a new small stylesheet). `tests/run_all.sh` — only to add the new test lines.
- **Do not touch:** Desk (`screener*.js`, Desk charts), `s2.js`, `compare.js`, `s5.js`, Worker (`worker/`), `prices.yml`, `desk-intraday.yml`, any data files, `CNAME`, logos/images, `chart-theme.js`, Chart.js vendor files.
- **Pins:** new TA family `ta1`, `ta2`, … (`btcchart.js?v=ta1`, `btcchart-panel.js?v=ta1`, `btcchart-ta.js?v=ta1`, `clock-v4.* ?v=ta1` if changed). **Never reuse a pin that has ever been served.** Before handback, check each was never used: `git log --all --oneline -S'v=ta1'` must show only your own commits. Burned as of Nov 15: btcchart.js et26 and before, panel et24 and before, clock v4f–v4l, s2 p6–p9. (Note: main has since moved — clock is now v4p, btcchart et27 — re-check pins at build time.)
- **Tests (handback):** `node --check` on every changed/added JS file; `python3 -m py_compile tools/ta_lines.py`; new unit tests pass; `bash tests/run_all.sh` on main first (baseline) then on the branch — no new failures; existing BTC chart tests stay green (`test_speed_option2.js`, `test_stage2_step2-4.js`, `test_candle_date_guardrail.js`, `test_clock_light_mode.py`, `test_clock_cad_fallback.py`); screenshots (phone 390×844 + SE 375×667, iPad portrait/landscape, desktop 1440×900, light + dark, clock normal/full-screen chart/full-screen price, popover desktop + bottom sheet phone, states closed/panel open/each overlay alone/all on/RSI collapsed/candles/1D/1Y, before-and-after all-off pairs); overlap-check JSON (target 0 hits); whole-diff scope check (`git diff --stat origin/main...HEAD` — every file must be on the allowed list).

## Handback
Send the checklist in brief §11 to Sunil to pass to Chief of Staff. Screenshots in `handback/ta/` on the branch only if small (<10 MB total), else zip through Sunil. Chief removes `handback/` before anything goes live.
