# TA overlay rollout plan (Chief of Staff, Fri Nov 13 2026) - STATUS: APPROVED by Sunil Nov 13 3:46 PM ("Ok perfect. Thats the planning stage done.")
Scope (Sunil 3:43 PM): all Bitcoin popup charts + the live Bitcoin chart (clock page). Grok spec was only a starting point; this plan is mine.
Inputs: Grok spec (grok-spec-1113.md), Site Launch GUI option C (/workspace/mockups-ta-pill, shots/sheet-C.png), approved Nov 13 9:25 AM game plan.
Rules: each stage on a branch, regular Grok QA prompt + whole-diff scope check, stop for Sunil's go. No Sunday work except Nov 22 (requested). FF-only pushes.
Before Nov 22: get Grok's sample scoring logic. No building.
Stage 1 (Sun Nov 22): GUI shell. C chart-type dropdown (Line/1H/4H/Candles -> "Candles v"), TA pill at end of row, floating panel inside chart stage,
  closes on outside tap, never covers price/Keep screen on/Exit pills, works in both full-screen modes, iPhone/iPad/desktop. Toggles wired, no overlays. Stop.
Stage 2 (Nov 22 if tokens allow, else Mon Nov 23): browser indicators on native canvas: SMA/EMA switch (20/50/200, exclusive), Bollinger (20, 2),
  RSI(14) collapsible strip off by default on phones. Load 200+ warm-up candles per timeframe. Live-updating. Stop.
Stage 3 (Tue Nov 24-Wed Nov 25): Python trendline job: pivots, level clustering, sloped lines, scoring, max 3 levels + 2 sloped, hysteresis.
  GitHub Action writing ta-lines.json (asOf, per timeframe) to data branch; 1H every 15 min, 4H hourly, daily candles once a day. Unit tests. Stop.
Stage 4 (Thu Nov 26-Fri Nov 27): front end draws trendlines, hides them when file stale; remember toggles per device; all overlays off by default.
  Full regular Grok QA + scope check + perf check. Stop for go-live yes.
Stage 5 (Sat Nov 28): go live after Sunil's yes; live checks.
Week 2 (Mon Nov 30-Fri Dec 4): watch the job daily, tune scoring from real behaviour, Sunil real-device check, fixes batched.
  Then write phase 2 plan (Desk stock charts) for after Pepper's native rebuild.
Stage 3 scoring changes vs Grok sample (grok-scoring-sample.py):
- Recency in candles not days (days break on 1H/4H); scale windows per timeframe.
- Spread tolerance from ATR, not fixed % (BTC volatility varies).
- Broken = candle CLOSES beyond level by a buffer (e.g. 0.5 ATR), not a wick/live tick. Broken support becomes resistance (flip) instead of -10 and gone.
- Cap touches bonus (diminishing) so one level can't dominate; add distance-from-price penalty so far-away lines drop.
- Merge levels closer than ~1 ATR; dedupe across variants before picking.
- Comparative layer: compare variants by total score of top N normalised, plus stability bonus for lines shown last run (hysteresis).
- Sloped lines need their own scorer (touches on the line, slope sanity, recent touch, not broken by closes).
