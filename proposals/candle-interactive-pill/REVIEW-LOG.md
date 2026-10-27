# Interactive candle chart — review log for Site Launch
## Job: minimalist candle chart with interactive "razzle dazzle" layer + pill bubble
## Date: Tue 27 Oct 2026, morning (America/Toronto) | Status: DEPLOYED LIVE 27 Oct 2026

### What the user asked for, in order
1. 27 Oct ~07:57 EDT: "Analyze the BTC candle chart. Are the daily chart. The labels present is a little sloppy maybe you can propose a fix to that I feel like the charts are a bit static they could use a little razzle dazzle. When I clicked on a candle, I should be able to get some information. Look at that and get back to me."
2. 27 Oct ~08:08 EDT: "Build it. I want a minimalist candle chart that still has an interactive razzle dazzle layer"
3. 27 Oct ~08:13 EDT: "It's an improvement. On the X axis of the chart, date, and times overlap each other it's sloppy. When I click on the chart, I think that little blurb that gives me the high low price information at the bottom of the screen should actually be a bubble that pops up."
4. 27 Oct ~08:16 EDT (clarification, iPhone): "The day I'm on my iPhone looking at it. And when I'm on my iPhone, the date and the time is on the same writing and they overlap each other. So it's sloppy. So look at it from an iPhone point of view. Also … I clicked on it and you put the blurb at the bottom. I'm happy with what the blurb says in terms of its information, but you should like in a clean way, put that information in a bubble that pops up. That's … over top of the candle. Like make it look, you know, a little high end. This looks very like first generation gooey interface charting."
5. 27 Oct ~08:27 EDT: "I think it looks great. You've taken a very nice direction. I want you to make one minor adjustment to the information bubble when you tap on the candle. Just make it a little bit more pill form and just minimize the information slightly so it's not necessarily for like a Wall Street technical trader but somebody who understands the surface area of technical trading. Just give it a try."
6. 27 Oct ~08:30 EDT: "Give me something that looks a little bit more like a pill"
7. 27 Oct ~08:32 EDT: "Love it! Make it live. Log all of this job and changes and history for site launch to review."

### Deploy
- **Live commit (main): 0e50493afbd7ba1c74c8d1275502b47af7f21f7c**, file `assets/js/btcchart.js` only, 85 insertions, 10 deletions vs main 45a11b6.
- Main head before deploy was still 45a11b6 (candle label fix, 26 Oct 10:38 p.m. ET), so there was no divergence / no other `btcchart.js` change to lose.
- Test branch: `pepper-candle-interactive` (base main 45a11b6). Live verification on paperstreetbtc.com was requested at deploy time; see "Verification" below for its result when it lands.
- **No deploy of anything else.** No data files, no other JS/CSS, no pipeline change.

### What was built — final live behaviour (v5)
- Applies to the banner BTC chart, 1D only, chart-type control Line (default) | 1H (24 candles) | 4H (6 candles). Candles aggregated from Coinbase 15-min OHLC already fetched (`aggCandles`, per=4 for 1H, per=16 for 4H), custom canvas (`drawCandles1D`), NOT the chartjs-chart-financial plugin.
- Tap/click a candle: white outline + soft glow on the selected candle, dashed vertical guide, and a **pill popup floating over the chart**.
  - Pill shape: 999px border radius (fully rounded ends), 280px wide (max calc(100% - 24px)), gradient dark card (#0e1730 → #0a1122), 1px cyan-tinted border, deep shadow, centred text.
  - Pill content, exactly three lines, surface-level only: (1) "1-hour · Oct 26, 7:15 – 8:15 PM ET" in small grey; (2) "High $80,183 · Low $79,724" bold white; (3) Change in green/red with ▲/▼, e.g. "▲ +$346 (+0.43%)".
  - **Open and Close were deliberately dropped** in v4/v5 at the user's direction (surface-level trader, not a Wall Street terminal). Change already tells direction and size.
  - No arrow on the pill. The white outline + dashed guide already points at the candle.
  - Dismiss by: tapping the pill itself, tapping its small ✕ (top-right inside the pill), or tapping the same candle again. Switching 1H → 4H clears the old pill (no stale data).
  - Desktop hover: dashed vertical guide follows the hovered candle.
- X-axis, iPhone-first: two clean rows, never the same writing.
  - Bottom row: time only, at most 4 labels on a phone (step = ceil(candles/4) for ≤640px width), at most 6 on desktop, inset so first/last do not clip, plus a 62px minimum spacing guard that skips a label if it would collide with the previous one.
  - Upper row: date only, short ("Oct 27"), only at the first candle and when the ET day changes, clamped inside the chart.
  - Bottom margin grew 28 → 44px to give the two rows room; plot area shrinks slightly.
- Other razzle, kept minimalist: 4 price gridlines, 300ms fade-in only when a new candle set is drawn (not on hover redraws, so no flicker), caption "Tap a candle for its O/H/L/C." (caption wording was not updated in v5 — see "Review notes").

### Version history (all on test branch pepper-candle-interactive, btcchart.js only)
- **v1, commit 81fdcfde (27 Oct ~08:09):** interactive layer built. Info as a line under the chart (`#bcSel`, class `bc-nt`), time window + O/H/L/C + Change. Time labels inset, date shown on day change but in the same label as the time (e.g. "Oct 27, 12:15 AM") — this is what overlapped on iPhone.
- **v2, commit b18a9901:** X-axis split into two rows (date row above, time row below); info moved from bottom line to a dark rounded card bubble next to the candle, with arrow, O/H/L/C + Change, close ✕.
- **v3, commit 1b0d1b36 (iPhone fix):** phone time labels capped at 4 with 62px spacing guard; bubble centred over the chart on phone, larger ✕ tap target. Still O/H/L/C.
- **v4, commit c9e531de:** bubble narrower (212px), 28px radius, info cut to time + High + Low + Change (Open/Close dropped).
- **v5, commit 6252b40b (live source):** true pill — 999px radius, 280px, centred three-line content, no arrow, tap-pill-to-dismiss. This is what was deployed to main as 0e50493a.
- Mockup for the pill (user-facing, not pushed to the repo): `workspace/your_files/candle-pill-bubble-mockup.png`.

### Verification — what was actually tested, and what was not
- **v1 browser visual test, PASSED 27 Oct ~08:12 EDT** (desktop dialog width, raw.githack test branch): 1H candle Oct 26 7:15–8:15 p.m. ET O $79,742 H $80,183 L $79,724 C $80,088 Change +$346 (+0.43%); 4H candle Oct 26 12:15 p.m.–4:15 p.m. ET O $80,090 H $80,436 L $79,643 C $79,806 Change -$284 (-0.35%); time labels clean/unclipped, no blank/error. Nuance: after clearing a selection, a faint dashed guide can remain while the mouse still hovers that candle — that is the hover guide, not a stuck selection; it clears on mouseleave / range switch.
- **v3 browser visual test, PASSED 27 Oct ~08:27 EDT** (test branch, no sign-in, no changes): two-row axis clean, no overlap/clipping on 1H and 4H; bubble over the chart (not bottom line); both dismiss methods worked; no bottom info line. Examples: 1H Oct 26 6:30–7:30 p.m. ET Change +$93 (+0.12%); 4H Oct 27 12:30–4:30 a.m. ET Change +$72 (+0.09%).
- **v4 browser visual test, INCONCLUSIVE (stale cache, not a code failure), 27 Oct 08:27–08:30 EDT:** the test was served the v3 card in two fresh tabs (full OHLC table, arrow, moderately rounded rectangle), because it ran in the same minutes as the v4 push, before the raw.githack preview cache refreshed. v4 code was verified present on GitHub (commit c9e531de). Lesson for reviewers: **do not judge a test-branch preview from the branch URL immediately after a push — use the exact commit-SHA URL** (for v5: https://raw.githack.com/Schadhaxx/paperstreetbtc/6252b40b1504b3ebd865069bb8985d24ff206c95/index.html).
- **v5 browser test:** requested at ~08:31 EDT on the commit-SHA URL above; its result was still pending when this log was written. The user approved v5 from the mockup + test preview ("Love it!") before that test landed.
- **Live verification:** requested at deploy time on paperstreetbtc.com (1D → 1H, tap a candle, pill content, two-row axis, no bottom line). Its result should be appended to this log when it lands — do not assume live = verified until that result is in.
- **Browser viewport limitation (all tests):** the browser tooling could not set an exact 390px iPhone viewport, so all browser tests were at a wider dialog width. At that width 1H showed 5 time labels (not 4), with no overlap. The "at most 4 on a phone" rule is code-level (≤640px width) and still needs a **real-phone check at 390px** — the user was checking on their iPhone, and that is the authoritative phone test.

### What was NOT changed
- Line chart (1D default, and all daily ranges), daily chart, Compare chart, Pulse, tracker, ledger, data files, and the pipeline. No new data source, no new vendor, no plugin vendored.
- SPX/Gold/MSTR toggles: still off/greyed for 1D, as agreed 26 Oct. MSTR long-range fix (26 Oct, commit 993fce13, `mstr-daily.json`) is untouched and still live.
- Candle label fix (26 Oct, commit 45a11b6, label at top of canvas) is included in the base and untouched.
- No Grok Bot contact was made for this job. The Grok Bot pause (until Fri 30 Oct 2:55 p.m. ET) still applies; this log is for Site Launch review, not a Grok Bot send.

### Review notes for Site Launch — please check and report back
1. Pill on a real iPhone (390px): fully inside the chart, centred, no clipping, text not wrapping awkwardly, ✕ tappable, tap-pill-to-dismiss works on touch (not just mouse click).
2. 1H time-label count at 390px: should be ≤4, no overlap, date row clean. Confirm the 62px guard does not leave the axis too sparse on desktop.
3. Tap / dismiss on both 1H and 4H, and switching between them (no stale pill).
4. Desktop hover guide vs selected outline — no stuck guide after mouseleave.
5. Long ranges (1W/1M/1Y/5Y/10Y/Max) and MSTR/SPX/Gold lines: unchanged behaviour, no regression from the `btcchart.js` change. The change touched only the 1D candle path, but confirm.
6. Caption wording: it still says "Tap a candle for its O/H/L/C." — the pill no longer shows Open/Close. Suggest updating it to "Tap a candle for its High, Low and Change." or similar, unless the user prefers to keep it. This is a wording suggestion only, not yet changed.
7. Accessibility: pill is a div with a button ✕; keyboard / screen-reader behaviour was not tested. Flag if this needs work.
8. Friday handover report (job paperstreet-friday-handover-to-grokbot, Fri 30 Oct 3:05 p.m. ET) does NOT yet include this interactive deploy — it predates 27 Oct. If Grok Bot / Chief of Staff need it there, the handover body needs a further user-approved update; this log does not update that job.

### Files
- Live: `assets/js/btcchart.js` on main, commit 0e50493a.
- Test branch: `pepper-candle-interactive`, commits 81fdcfde → b18a9901 → 1b0d1b36 → c9e531de → 6252b40b.
- This log: also pushed to `pepper-results` as `oct27/candle-interactive-pill-review-log.md` and to the test branch as `proposals/candle-interactive-pill/REVIEW-LOG.md`, so Site Launch can find it from either branch.
- Prior candle/MSTR proposal folder (26 Oct, still relevant for the original build): test branch `proposals/candle-mstr-1d/` (PROPOSAL.md + TESTING.md).
