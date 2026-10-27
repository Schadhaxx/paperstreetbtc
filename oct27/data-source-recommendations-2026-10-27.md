# Data-source recommendations — for Chief of Staff review
## PaperStreet BTC site — smooth operations and second / third source layers
## Prepared by Muse (Pepper) at Sunil's direction, Tue 27 Oct 2026, morning (America/Toronto)
## Status: RECOMMENDATIONS ONLY — no implementation, no deploy, no code change

**Who should decide this, and when.** This report is for **Chief of Staff to review**, in coordination with Grok Bot, as part of the Friday 30 Oct 2026 handover. Chief of Staff will be making a lot of decisions on changes over the next couple of weeks, and this report is intended to inform that decision-making — not to be implemented by Muse on its own, and not to be decided by Grok Bot alone. The final decision on each recommendation below comes back to Sunil, as a Grok Bot + Chief of Staff product.

**How this was prepared.** From the site's own pipeline code (` .github/workflows/prices.yml`, `tools/btc_daily.py`), the Oct 23 stall / manual patch, the Monday 26 Oct checks, and the Tue 27 Oct 10:00 a.m. price check (all-clear: live BTC $79,918, +0.59%, updated 9:58 a.m.; Pulse updated 9:55 a.m.; prices runs green; Oct 26 final in history). No API key is printed or requested in this report.

---

## 1. Where we stand today — basic picture

**Pretty good for short outages, not bulletproof for a long one.**

- **Primary sources:** Yahoo for daily closes (BTC and all stocks/ETFs); Finnhub for live stock quotes; CoinGecko for live BTC.
- **Second layer — automatic, daily history, if Yahoo gaps:** BTC daily: Coinbase, then CoinGecko. Stocks daily: Yahoo chart meta regularMarketPrice, then Finnhub quote, then Stooq CSV. If every source fails, the previous history file is kept. Values are never invented.
- **Live layer:** BTC: CoinGecko → Coinbase → keep last price. Stocks: Finnhub only → keep last price.
- **Third layer — a check, not a replacement:** Tiingo. It never writes, replaces, or freezes a close. It only cross-checks closes that just became final and flags a difference: over 0.05% for stocks, over 0.3% for BTC, for human review.
- **Long-history static files:** SPX/Gold back to 2010-08-17, BTC back to 2010-08-18, MSTR now back to 2010-08-17 (fixed 26 Oct, commit 993fce13). These are extended by later closes from history, so long ranges draw fully.

**The weak spot, in one sentence:** Yahoo is the single source of truth for a *final* close. A fallback price is marked provisional and never becomes final on its own — it waits for Yahoo's final bar to replace it. If Yahoo never arrives for more than 48 hours, the recap job stalls on purpose (exit 3 in `tools/btc_daily.py`). Live prices keep updating, but the main daily file stops advancing until a person clears it.

**Evidence — Oct 23, 2026:** Coinbase gave $81,078.04, Yahoo's final was $81,074.19 — only $3.85 / ~0.005% apart — but the stall blocked the recap, GitHub Actions `prices` runs failed from #1453 (3:55 a.m. ET 26 Oct) on the stall guard, and Sunil authorised a manual patch on 26 Oct ~10:30 a.m. (main 631b2ee8, data history 32cfadf4) instead of waiting for market close.

**Related labelling gap — OI-001, LOW, non-blocking:** `btc_provisional` is set only by time, so a post-window Coinbase-sourced close can *look* final. No wrong number was shown. Chief of Staff decision already recorded: package into the checked deploy after the Sat 31 Oct 2026 10 a.m. review; frontend-only fix keyed on `fallback_sources` preferred but untested; **backend `prices.yml` change stays rejected as unsafe.**

---

## 2. Why Tiingo is not the primary source — and why it should not simply be switched

Tiingo is written in as **reference only, on purpose**. The workflow code states it explicitly: it never writes, replaces, or freezes a close; it only cross-checks closes that just became final.

1. **History consistency.** Every close in the ledger, back to Dec 31, 2025, is a Yahoo unadjusted close. Switching primary would rewrite history slightly. Tiingo BTC was $81,083.72 on Oct 23 vs Yahoo $81,074.19 (+$9.53 / 0.012%), and $80,010.75 on Oct 26 vs Yahoo $80,008.79 (+0.0025%). Small, but it breaks the consistent baseline the whole site is built on.
2. **Tiingo is not cleaner for every symbol.** Stocks matched Yahoo to the cent on Oct 26, but Tiingo's STRC dividend for June 15, 2026 reads 1.916667 vs the declared 0.958333 — double. Tiingo has its own quirks, especially on the preferreds (STRC, STRF, STRK, STRD), which matter most right now with the Strategy daily-dividend vote on Wed 28 Oct.
3. **Call limits in the current setup.** Only 9 Tiingo calls per run, only the last 7 days, retry at most hourly. That is fine for checking newly final dates. It is not enough to be the primary feed for a full history or a backfill.
4. **BTC day definition does not line up exactly.** Yahoo's BTC day is a UTC bar ending at midnight UTC (8 p.m. ET). Tiingo's is a resampled 1-day crypto price. Close, not identical — which is why the small BTC differences above appear.
5. **Key handling.** Tiingo's key is server-side only, in GitHub Actions, never in a URL, a log, or the site's JavaScript. That is good security, and it means Tiingo can only feed the server-side daily history, not a live client-side price directly. That is not a blocker for daily closes, but it is a constraint on any live-price use.

**Conclusion on Tiingo:** Yahoo primary + Tiingo verifier is a sound design. Do not switch wholesale to Tiingo as primary. The improvement to make is in what happens when Yahoo *does not* show up — see Recommendation 1 below.

---

## 3. Recommendations, in priority order — for Chief of Staff decision

### Recommendation 1 (start here): Let Tiingo un-stall the recap, without replacing Yahoo
**Problem:** A Yahoo final that never arrives for 48+ hours stalls the recap and stops the main daily file advancing — the Oct 23 case.
**Proposal:** Allow a Tiingo-confirmed fallback to freeze, but with its own distinct tag, e.g. "Tiingo-final, Yahoo pending" — visible, not silent. The site keeps moving. Yahoo can still replace it later if it arrives. Nothing is ever presented as Yahoo-final when it is not.
**What it is not:** A switch to Tiingo as primary, a rewrite of history, or a silent promotion of a fallback to primary status.
**Decision needed from Chief of Staff:** Approve the principle (tagged Tiingo-final un-stall) and the tag wording / display, before any code is written. Implementation, if approved, is a separate Sunil-approved build/deploy step.

### Recommendation 2: Fix the OI-001 labelling on the frontend
**Problem:** A post-window Coinbase close can look final because provisional is set by time alone.
**Proposal:** Show a price as provisional when its source is a fallback, based on the actual `fallback_sources` tag, not just on time. Frontend-only, no pipeline change — the safe route Chief of Staff already preferred.
**Decision needed:** Approve the frontend-only approach and the label wording, for packaging into the checked deploy after the Sat 31 Oct review (the existing OI-001 timetable). Backend `prices.yml` change stays rejected.

### Recommendation 3: Give live stocks a second source, and make staleness visible
**Problem:** Live BTC has CoinGecko → Coinbase → keep last price. Live stocks are Finnhub-only → keep last price. A Finnhub failure leaves a stale live stock price with no automatic second source.
**Proposal:** Add Yahoo market price or Stooq as a live fallback for stocks, the same way the daily history already does. At minimum, show a "last updated X minutes ago" age on the site if a live price goes stale past 30 minutes, so a stall is visible instead of silent.
**Decision needed:** Choose fallback order and whether the age display is wanted, before implementation.

### Recommendation 4: Keep Tiingo as verifier, widen it only for newly final dates
**Problem / constraint:** 9 calls per run, last 7 days only, is enough for checking new finals but not for a full backfill.
**Proposal:** If Recommendation 1 is approved, raise the call budget for newly final dates only, and keep the key server-side only. Do not raise it to cover a full backfill — that is where limits and cost would bite, and where the STRC dividend quirk would matter most.
**Decision needed:** Approve the narrowed widening, or keep the current budget and accept that Tiingo-final un-stall would be limited to recent dates.

### Recommendation 5: Make stalls alert, not just fail
**Problem:** A recap stall currently shows up as a failed Actions run. GitHub failure emails are back on (re-enabled 26 Oct 10:38 a.m.), which is better than when they were muted, but a stall between the 5× daily price checks (10 a.m., 12 p.m., 2 p.m., 4 p.m., 6 p.m. ET, through Fri 30 Oct 3 p.m.) can still sit for hours.
**Proposal:** A simple "recap stalled >48h" note in the next price check, or a dedicated alert, so a stall is surfaced promptly rather than discovered from a failed run.
**Decision needed:** Choose the alert route (price-check note vs dedicated alert vs email filter / repo Watch — prefer a route that leaves account settings untouched, per the standing settings rule).

---

## 4. What NOT to do — recorded constraints for Chief of Staff

- Do not switch primary to Tiingo wholesale, and do not rewrite history to Tiingo closes.
- Do not expose the Tiingo key in site JavaScript, a URL, or a log. Server-side in GitHub Actions only.
- Do not make a backend `prices.yml` change for OI-001. Frontend-only, as already decided.
- Do not treat a Tiingo flag as an automatic correction. A flag means "review", not "replace".
- Do not assume price checks continue after Fri 30 Oct 3 p.m. — they are to be removed at handover unless Grok Bot decides to keep them.
- Do not implement or deploy any of Recommendations 1–5 from this report alone. Each needs a Grok Bot + Chief of Staff final proposal back to Sunil, and Sunil's approval, before build/deploy.

---

## 5. For the Friday handover

This report is folded into the Friday 30 Oct 2026, 3:05 p.m. ET handover report to the Grok Bot (job `paperstreet-friday-handover-to-grokbot`), with an instruction that Grok Bot MUST coordinate it with Chief of Staff. Grok Bot should not decide these recommendations alone, and Muse should not implement them without a separate Sunil-approved build/deploy step.

**Full file locations (pushed 27 Oct 2026):**
- Test branch `pepper-candle-interactive`: `proposals/data-source-recommendations/RECOMMENDATIONS.md`
- `pepper-results` branch: `oct27/data-source-recommendations-2026-10-27.md`

**Companion documents Grok Bot + Chief of Staff should read alongside this report:**
- Decision log (all takeover decisions, Mon 26 – Tue 27 Oct, with ACCEPT / TIGHTEN / OPEN / PROPOSAL verdicts): test branch `proposals/decision-log-takeover/DECISION-LOG.md`; `pepper-results` `oct27/decision-log-takeover-2026-10-26-27.md`
- Site Launch review log for the interactive pill chart: test branch `proposals/candle-interactive-pill/REVIEW-LOG.md`; `pepper-results` `oct27/candle-interactive-pill-review-log.md`
- Review rule: review from the test branch, not main — main only has the final deployed version.
