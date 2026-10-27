# Python supercharge plan — for Chief of Staff + Grok Bot review
## PaperStreet BTC site — how Python can make the website more advanced, still free and automated
## Prepared by Muse (Pepper) at Sunil's direction, Tue 27 Oct 2026, morning (America/Toronto)
## Status: IDEAS + RECOMMENDATIONS ONLY — no implementation, no deploy, no code change

**Who should decide this, and when.** This plan is for **Chief of Staff to review, in coordination with Grok Bot**, as part of the Friday 30 Oct 2026 handover, and to consider in decision-making over the next couple of weeks. Grok Bot must not decide these ideas alone, and Muse must not implement them from this plan alone. Each idea needs a Grok Bot + Chief of Staff final proposal back to Sunil, and Sunil's approval, before any build or deploy.

**One important fact first, in simple terms.** Python does NOT run in a visitor's browser. JavaScript is the shop window — what you see on paperstreetbtc.com. Python is the kitchen behind the shop. Every 5 minutes on weekdays, GitHub Actions runs Python, Python pulls Yahoo / Finnhub / Tiingo / Stooq / Coinbase / CoinGecko, checks the numbers, cleans them, calculates things, and leaves neat JSON files in the repo (`history.json`, `prices.json`, static daily files). The website then just displays those files. That is why Python can "supercharge" the site without changing what a visitor's phone has to do — and without paying for data. The phone does less work, the site gets faster, and the numbers get checked before anyone sees them.

**What is already Python, for free.** `tools/btc_daily.py`, `gold_daily.py`, `recap_gen.py`, `recap_lib.py`, `datatest.py` — plain Python, standard library only (no paid libraries, no pandas, no `yfinance`), plus inline Python in `.github/workflows/prices.yml`, running in GitHub Actions (free for a public repo), using free keyless sources (Yahoo chart API, Stooq CSV, Coinbase and CoinGecko public endpoints) plus Finnhub / Tiingo keys held server-side only. You do not need a new stack. You need better Python around the free sources you already have.

---

## Part 1 — Recommendations rolled in from 27 Oct morning (data pipeline)

These are the recommendations Sunil asked to be rolled into Friday's report on 27 Oct ~10:05 a.m. and ~10:30 a.m. They are repeated here so Chief of Staff has them in one place with the supercharge ideas below.

1. **Let Tiingo un-stall the recap, without replacing Yahoo.** If Yahoo's final has not arrived in 48+ hours, allow a Tiingo-confirmed value to freeze, but only with a visible tag, e.g. "Tiingo-final, Yahoo pending". The site keeps moving, Yahoo can still replace it later, nothing is ever presented as Yahoo-final when it is not. Why Tiingo is not primary in the first place: history consistency (every ledger close back to Dec 31, 2025 is a Yahoo unadjusted close; Tiingo BTC Oct 23 $81,083.72 vs Yahoo $81,074.19, Oct 26 $80,010.75 vs $80,008.79); Tiingo is not cleaner for every symbol (STRC dividend June 15, 2026 reads 1.916667 in Tiingo vs declared 0.958333, double); call limits (9 Tiingo calls per run, last 7 days only); BTC day definition does not line up exactly (Yahoo UTC bar ending midnight UTC / 8 p.m. ET vs Tiingo resampled 1-day price); key is server-side only, never in site JavaScript, a URL, or a log. Do not switch wholesale to Tiingo, do not rewrite history to Tiingo closes.
2. **Fix OI-001 labelling on the frontend only.** Show a price as provisional when its source is a fallback, based on the actual `fallback_sources` tag, not just on time. Frontend-only, no pipeline change — the safe route already preferred. Backend `prices.yml` change stays rejected as unsafe. For packaging after the Sat 31 Oct review (existing OI-001 timetable).
3. **Give live stocks a second source, and make staleness visible.** Live BTC has CoinGecko → Coinbase → keep last price; live stocks are Finnhub-only → keep last price. Add Yahoo market price or Stooq as a live fallback for stocks. At minimum, show a "last updated X minutes ago" age if a live price goes stale past 30 minutes.
4. **Keep Tiingo as verifier, widen it only for newly final dates.** If Recommendation 1 is approved, raise the call budget for newly final dates only, keep the key server-side only. Do not raise it to cover a full backfill.
5. **Make stalls alert, not just fail.** A recap stall currently shows up as a failed Actions run. Add a "recap stalled >48h" note in the next price check, or a dedicated alert. Prefer a route that leaves account settings untouched, per the standing settings rule.

---

## Part 2 — How Python supercharges the site, in simple terms

Think of it like this: today, Python mostly *fetches* prices and *stores* them. Tomorrow, Python can also *check* them, *calculate* things from them, and *prepare* answers — so the website does not have to do that work on your phone, and you do not have to do it by hand.

That gives you three kinds of supercharge, all still free and automated:

**A. Make existing tools more powerful, very easily (Python prepares, JavaScript displays)**
These are the easiest wins, because the site already shows the data — Python just pre-calculates a smarter version of it, once, in Actions, instead of the browser calculating it every time someone opens the page.

- **Tracker / Compare, with real stats:** Python pre-computes, for each sleeve and each benchmark, the monthly returns, best and worst days, biggest fall from a peak (drawdown), and how bumpy the ride has been (volatility). The chart stays the same, but underneath it you get a small stats table that is already calculated when the page loads — faster on an iPhone, no extra work for the phone.
- **Pulse, with context:** Python already knows the weekend move. It could also pre-compute "this sleeve is $X above its January 1 start, $Y below its peak" — one line, ready to display, no live calculation.
- **Dividend calendar, automatic:** Python reads the dividend list in `history.json` and builds the next payment dates, amounts, and what happens if the Strategy vote passes (daily from Nov 2) vs if it does not (semi-monthly / quarterly stays). No hand-updating a calendar.
- **Price badges, automatic:** Python checks every 5 minutes whether BTC crossed a round number you care about ($80,000, $85,000, $90,000, and so on) or whether a sleeve hit a new high, and writes that flag into `prices.json`. The site just shows the badge. No new live feed needed.
- **CSV export, one click:** Python turns `history.json` into a clean CSV download. If you ever want the data in a spreadsheet yourself, you get it in one click — without anyone maintaining a spreadsheet by hand. The repo JSON stays the source of truth; the CSV is just an export.

**B. New tools you do not have today (Python runs them offline, the site shows the result)**
These are tools that would be too slow or too messy to build in the browser alone, but are easy for Python to run behind the scenes once a day (or once an hour) in Actions.

- **What-if backtester:** "What if lump sums had used the close instead of the open? What if I had used IBIT instead of spot BTC? What if DCA had been weekly instead of monthly?" Python replays the ledger offline with different rules, using the same stored closes, and writes the difference in dollars and percent. You can compare rules without touching the live site, and without guessing. This is the safe way to test CR-005 and the vehicle toggle before anyone builds them live.
- **Anomaly detective:** A daily Python check that looks for splits, absurd one-day jumps (over 35% usually means a split, not a real move), missing sessions, dividend doubles like the Tiingo STRC case, and stale prices — and writes a short health report. Instead of discovering a bad bar when the site stalls, you get a one-line flag the morning it appears.
- **Health / status file:** Python writes a tiny status JSON next to `prices.json`: last successful run, how old each price is, which source each symbol came from, which dates are provisional. The site reads it and can show "data is 12 minutes old" or "BTC is provisional — fallback source" — honest, visible, and automatic.
- **Screener / index:** Python builds a small searchable index of all closes, so a future "find a date / find a price" feature on the site is instant, instead of searching through a huge JSON file in the browser.
- **Backfill machine:** The MSTR long-range file (2010 to now, 4,073 closes) was built from Yahoo by hand-style work. Python can do that same pattern for any future gap — a script that takes a symbol, a start date, and a free source (Yahoo / Stooq), and writes a clean static file, checked for splits and jumps, ready for review. No hand-building the next one.

**C. Make the pipeline itself smarter (Python checks, then publishes)**
This is the least visible supercharge, and the most valuable for smooth operations.

- **Validate before publishing, not patch after:** Check every new bar before it goes live — session missing? Jump absurd? Yahoo vs Stooq disagree by more than a small amount? If yes, keep the previous file, flag it, do not publish the bad bar. That turns the Oct 23 manual patch into an automatic hold.
- **Move logic out of the workflow file into proper Python modules:** A lot of history-building logic currently lives as inline Python inside `prices.yml`, which is hard to test. Moving it into `tools/` — where `btc_daily.py` already lives — lets you run the same checks locally, add small tests (`datatest.py` is already a start), and change one place instead of hunting through YAML.
- **Smarter caching, so free limits last longer:** Tiingo is limited to 9 calls per run, Finnhub is limited too. Python already caches Tiingo references in `history.json`. The same idea can be used everywhere: only fetch what is new, only re-check what just became final, never re-fetch a whole history to answer one question.

---

## Part 3 — What Python cannot fix for free (honest limit)

Real-time live stock quotes, minute by minute. Finnhub's free tier is limited, Yahoo's intraday endpoint is unofficial, delayed, and can break without warning, and the proper real-time feeds (Polygon, Alpha Vantage premium, and so on) are paid. That is why the site does what it does now: daily closes free and automated, live prices cached every 5 minutes, not true real-time. Python will not change that trade-off — it makes the free daily pipeline more reliable, faster, and smarter, but it does not turn a free feed into a paid real-time feed.

If you ever decide you actually need true real-time stocks, that is a separate paid decision for Chief of Staff — not something Python alone can conjure for free.

---

## Part 4 — Suggested order for Chief of Staff (easiest first, still free)

1. Validate before publishing + health/status file (Part 2C + Part 2B health file) — smallest change, biggest reliability gain, no new vendor.
2. Tiingo un-stall with a visible tag + OI-001 frontend labelling (Part 1, Recommendations 1–2) — fixes the only case where the current layering actually stops the site advancing, and the labelling gap that makes a fallback look final.
3. Pre-computed tracker / Compare stats + dividend calendar + CSV export (Part 2A) — visible improvements for visitors, no new data needed, just Python calculating what is already stored.
4. What-if backtester + anomaly detective (Part 2B) — the tools that let CR-005, the vehicle toggle, and the Strategy dividend change be tested safely before they are built live.
5. Live stocks second source + staleness age + stall alerts (Part 1, Recommendations 3 and 5) — closes the live-price gaps, still free.

**What NOT to do:** Do not switch primary to Tiingo wholesale; do not rewrite history to Tiingo closes; do not expose any API key in site JavaScript, a URL, or a log; do not make a backend `prices.yml` change for OI-001; do not treat a Tiingo flag as an automatic correction; do not implement or deploy any idea in this plan from this plan alone — each needs a Grok Bot + Chief of Staff final proposal back to Sunil, and Sunil's approval, before build/deploy.

**Full file locations (to be pushed with this plan):**
- Test branch `pepper-candle-interactive`: `proposals/python-supercharge/PLAN.md`
- `pepper-results` branch: `oct27/python-supercharge-plan-2026-10-27.md`

**Companion documents:**
- Data-source recommendations: test branch `proposals/data-source-recommendations/RECOMMENDATIONS.md`; `pepper-results` `oct27/data-source-recommendations-2026-10-27.md`
- Decision log: test branch `proposals/decision-log-takeover/DECISION-LOG.md`; `pepper-results` `oct27/decision-log-takeover-2026-10-26-27.md`
- Review rule: review from the test branch, not main — main only has the final deployed version.
