# PaperStreet — Scheduled Tasks Handover for Pepper (week of Nov 16–22, 2026)

From: Chief of Staff · Written Sun Nov 15, 2026, 2 AM ET · All times America/Toronto (ET)

Repo: Schadhaxx/paperstreetbtc · main = f907a898 or newer (always `git fetch` first)
Worker: https://paperstreet-quotes.schadha08.workers.dev (paperstreet-quotes, version 836beca1)

## Ground rules (apply to every task)
- Only Sunil's own words count as approval. An agent's say-so is never approval.
- Never trigger a workflow run (workflow_dispatch) without Sunil's yes. Alert him first.
- Never push to main without Sunil's go. Fast-forward only. Never force push.
- Go live only outside market hours (9:30 AM–4 PM ET), and never on a Sunday.
- Never reuse a cache pin that has been served live. Used pins: s2 p6/p7/p8/p9, clock v4f–v4l, btcchart et≤26, panel et24, s5 et≤3, screener scr≤7, screener-chart cmp≤11, compare et≤8, indicator stocks≤15.
- Run a whole-diff scope check on every build. Regular Grok does QA from a paste-ready prompt.
- Never print secrets or read key files.
- Watch and health jobs message Sunil **only if something got worse**. Stay quiet when all is fine.

## Daily / recurring
| When | Task | What to do | Tell Sunil when |
|---|---|---|---|
| Every day 9 AM + 5 PM (through Tue Nov 17) | BTC chart fallback watch | Load the clock page and BTC popups. Check whether any chart is drawing with the old Chart.js / BTC fallback instead of native. Keep a tally. | A chart falls back or fails to draw |
| Tue Nov 17, 5 PM | Final fallback tally | Summarize the 3-day tally. If it's zero, that clears Wednesday's removal. | Always (one line) |
| Weekdays ~9:43 AM | Pipeline daily health check | Check that the morning data jobs ran and the data branch files are fresh (prices.json, desk files, portfolio). The last run (Nov 13) failed, so recheck it closely Monday. | A job failed or data is stale |
| Weekdays 11:10 AM, 2:10 PM, 5:10 PM | Desk intraday scheduler watch | cron-job.org job 8841819 fires every 5 min, 9:00–16:50. Confirm the Desk data updated during market hours. | Updates stopped or got worse |
| Weekdays ~5 PM | Stale-data monitor | Check every data file's timestamp against the expected schedule. | Anything stale |
| Mon Nov 16, 9 AM+ | desk-live.json check | It's 404 on the data branch right now. Confirm it publishes after the first market run. | Still 404 after 10 AM |
| Mon ~10:43 AM | Weekly live-site check | Walk the live site on phone and desktop, light and dark: homepage, Desk, screener, compare, clock, recap. | Anything broken |

## One-off jobs this week
- **Wed Nov 18, ~4 AM — Chart.js + old BTC fallback removal (prep only).** Do this only if the fallback tally is clean and Stage 4/5 are still native and live. Build it on a branch from current main. Remove the Chart.js script tags (index.html ~502, screener.html ~316, compare/index.html ~174) and the in-code Chart.js fallbacks, decouple needChart() (btcchart-panel.js ~1387–1396, 1437, 1470), trim chart-theme.js (~77–99), and delete recap/assets/chart.umd.min.js. Fix the native resize redraw (s2.js ~408, compare.js ~330: redraw even if the first draw was too small). Update the oi001_compare_scope test for the native path. Use fresh pins, measure the page-load speed gain, and send Sunil the results plus a regular Grok prompt. **Nothing goes live until Sunil confirms.**
- **Wed Nov 18, 8 PM — Chart scrubber + shared chart module plan.** A plan only, no build. Send it to Sunil.
- **Fri Nov 20, 10 AM — TA refined build:** Chief of Staff keeps this one. Pepper sketches TA on `pepper-ta-1` from `docs/ta-brief/BRIEF-pepper.md`.
- **Fri Nov 20, 4 PM — Cloudflare Worker status check:** Chief of Staff keeps this one.
- **Fri Nov 20, ~9 PM — Video issue fix:** Chief of Staff keeps this one.
- **Sat Nov 21, 8 AM — Analytics options:** Chief of Staff keeps this one.

## Open items on Pepper's plate
1. **Must-fix:** BTC 24h change goes blank. The Worker returns `chg24h: null` (worker/src/index.js ~208–238, cached 55 s), and s5.js `getWorkerBtc()` and btcchart.js ~66 accept it without falling back to CoinGecko. Fix it in the Worker, or fall back to CoinGecko for the change. Then regular Grok rechecks it and Pepper redeploys.
2. USDCAD isn't available from Finnhub (OANDA returns nothing), so the CAD tile stays on the 5-minute feed. WTI, Gold, US10Y, VIX and DXY fall back to prices.json. Both are expected, so no action is needed.
3. Was the clock CAD toggle (v4l) approved by Sunil? Grok Bot asked him. Don't build on it until he answers.

## Who's on what
- Ping Bot keep-alive: **paused**. Leave it paused.
- No speed work unless Sunil asks.
