# Vehicle toggle — Day 1 complete (data + plumbing + baseline + decisions)

## Status — TEST BRANCH ONLY, NO DEPLOY, NO LEDGER/FRONTEND CHANGE

- Branch: `pepper-vehicle-toggle-day1` (from `origin/main`)
- Files in this branch only: `assets/data/vehicle-daily.json`, this report, `baseline-snapshot-2026-10-29.json`
- NOT changed: `main`, `ledger.js`, `btcchart.js`, `compare.js`, `s6.js`, `prices.yml`, any frontend file, any spot BTC close.
- No deploy. Day 2 (ledger mapping) is NOT started.

## 1. Data backfill — DONE

- File: `assets/data/vehicle-daily.json` — a SEPARATE vehicle series, in the same shape as `mstr-daily.json` (`v`, `source`, `start`, `end`, `sessions`, `vehicles.IBIT` / `vehicles.FBTC` as `[date, close]` pairs, closes rounded to cents).
- Source: Yahoo Finance chart API daily closes, unadjusted, Nasdaq sessions, ET dates — the site's usual primary source.
- Range: **2025-12-31 through 2026-10-28 — 208 sessions** for each vehicle. 2026-10-28 is the latest close (2026-10-29's session had not closed at snapshot time, ~7:53 a.m. ET).
- Anchors, verified to the cent:
  - IBIT: 2025-12-31 $49.65; 2026-10-26 $45.22; 2026-10-27 $45.70; 2026-10-28 $46.14
  - FBTC: 2025-12-31 $76.23; 2026-10-26 $69.44; 2026-10-27 $70.19; 2026-10-28 $70.85
- Session alignment: the 208 ETF dates are EXACTLY the 208 sessions in data-branch `history.json` from 2025-12-31 — no missing sessions, no extra dates. Spot BTC closes were not touched or overwritten.
- Fees: NO separate fee deduction anywhere. ETF prices already reflect ~0.25%/yr (IBIT net expense 0.25% confirmed in MarketBeat snippet; FBTC 0.25% in the data pack). Fee goes in a footnote only, not in the maths.

## 2. Cross-checks — what was checked, and the one honest gap

### Independent-source sample check — PASSED
YCharts / MarketBeat / Finnhub snippets (searched 29 Oct 2026) match the backfill to the cent on every sampled date:
- IBIT: Oct 19 $46.30, Oct 20 $46.71, Oct 21 $47.84, Oct 22 $46.06, Oct 23 $45.96, Oct 26 $45.22, Oct 27 $45.70, Oct 28 $46.14
- FBTC: Oct 19 $71.14, Oct 20 $71.72, Oct 21 $73.47, Oct 22 $70.74, Oct 23 $70.61, Oct 26 $69.44, Oct 27 $70.19, Oct 28 $70.85
- YTD returns in those snippets: IBIT −7.07%, FBTC −7.06% — identical to the backfill's cumulative return from 2025-12-31 (below).

### Spot comparison — NO data breaks, but read the timing note
- Cumulative 2025-12-31 → 2026-10-28: IBIT −7.07%, FBTC −7.06%, spot BTC (history.json) −7.15%. Tracking gap over 10 months: ~0.08–0.09 percentage points. The ETFs track spot.
- Daily-return differences vs spot are NOT a 0.05% test: median daily difference 0.47pp for both ETFs, 192/207 (IBIT) and 190/207 (FBTC) days differ by more than 0.05pp, 97–100 days by more than 0.5pp. This is expected, not a data error: ETF closes are 4 p.m. ET regular-session closes, while the site's spot BTC close for a session date is the Yahoo UTC-day bar (ending 8 p.m. ET), and weekend BTC moves land in Monday's ETF return. Day 2 must therefore compare ETF and spot values on the site's existing same-session-date convention (as this backfill does), not on intraday timing.
- Largest single-day divergences (timing, not breaks): 7 Apr 2026 ETF ≈ −1.1% vs spot +4.47%, reversing 8 Apr (ETF ≈ +3.4% vs spot −1.14%) — a BTC move after the ETF close landing in the next spot bar. Over 7–8 Apr combined the gap narrows to ~1pp.
- Sanity band: no day-to-day move over 35% in either series. The only move over 10% is 5 Feb 2026 (IBIT −13.16%, FBTC −13.22%), matching spot BTC that session (from $73,019.70 to $62,702.10, −14.1%) — a market crash, not a bad bar.

### Gap — full-series Stooq cross-check NOT completed
- Stooq (the pipeline's independent CSV source) was attempted twice: first attempt dropped the connection, the retry hung with no data returned. Stooq is therefore NOT verified from this environment today.
- Tiingo cross-check was NOT run for the full series either: the Tiingo key is server-side in GitHub Actions only and is not available to this agent, and the pipeline's Tiingo check covers only the last 7 days of newly final dates, not a 208-session backfill.
- Mitigation for Day 2: before any deploy, re-run the independent cross-check (Stooq and/or the pipeline's own cross-check) for the full series, or at minimum for any date Day 2 flags. The backfill as it stands rests on Yahoo primary + the independent sample check above + session alignment + cumulative tracking. Do NOT present the Stooq check as done.

## 3. Live-quote plumbing — CONFIRMED ROUTE, one small change needed at implementation time

- Route: the existing live-stock route in `.github/workflows/prices.yml` — Finnhub quote API, whose results are written into data-branch `prices.json` (`stocks` map, every ~5 min weekdays). The site reads that file; visitors never call the quote API. No new vendor is needed.
- Exact change (NOT made in Day 1 — `prices.yml` is untouched): add `'IBIT'` and `'FBTC'` to the live-quote symbol list in `prices.yml`, which currently reads `['MSTR','STRC','TSLA','PLTR','SPY','QQQ','BRK.B','GLD']`. That puts IBIT/FBTC `c`/`pc`/`t` into `prices.json` alongside the existing stocks.
- To verify at implementation time (not assumed in Day 1): that Finnhub returns a quote for IBIT and FBTC on the first pipeline run after the list change. Both are US-listed ETFs (IBIT Nasdaq, FBTC Cboe BZX), and Finnhub's quote endpoint covers US-listed ETFs by symbol, but the first run is the proof.
- Site side (Day 3, not Day 1): `s6.js` reads `prices.json` stocks for live values; the toggle will read the IBIT/FBTC entry when in ETF mode.
- Market-hours behaviour, already handled by existing rules: Finnhub `c` is the last close outside market hours; the site already treats a stock quote as live only while the market is open AND `prices.json` is under 30 minutes old. Weekend ETF mode therefore falls back to the Friday close through the same route — no special plumbing.
- BTC live route is unchanged (CoinGecko, then Coinbase, then keep last).

## 4. Spot-regression baseline snapshot — DONE

- File: `proposals/vehicle-toggle-day1/baseline-snapshot-2026-10-29.json` (full holdings units, live prices used, latest closes).
- Snapshot time: Thu 29 Oct 2026, ~7:53 a.m. ET. Market not yet open: stock prices are the 2026-10-28 closes from `prices.json` (updated 2026-10-29T11:45:17Z); BTC live is CoinGecko $80,108 at that time. History last session 2026-10-28 (updated 2026-10-29T00:20:18Z).
- Computed by replicating `book.js` exactly (initial units = $100,000 × weight ÷ 2025-12-31 close; STRC dividend cash buys the sleeve's dividend assets at the pay session's close; unpaid Oct 15 event, pay rolled past Oct 31, stays receivable cash). Cross-checked against the Wed 28 Oct 6 p.m. live check: Saylor matches to the cent ($104,013.87 vs $104,014 reported); the other sleeves' latest-close values sit within ~$25 of that evening's live figures, the difference being live BTC at that hour vs the Oct 28 close — as expected.
- Baseline values (spot mode, to the cent). NOW uses the live prices above; latest-close uses 2026-10-28 closes; YTD % is vs the $100,000 start:

| Sleeve | NOW (live) | NOW % | Latest close (28 Oct) | Close % | Receivable cash |
|---|---|---|---|---|---|
| Berkshire Killer | $97,088.96 | −2.91% | $97,640.65 | −2.36% | $101.22 |
| Hodler Jam Sandwich | $94,403.61 | −5.60% | $95,331.57 | −4.67% | $50.61 |
| Hedge Fund Killer | $95,018.03 | −4.98% | $95,742.85 | −4.26% | $50.61 |
| Saylor Moon | $104,013.87 | +4.01% | $104,013.87 | +4.01% | $253.05 |

- Holdings units at the last session (for Day 2 to reproduce): Berkshire BTC 0.4834, STRC 202.4394, TSLA 66.7082, PLTR 56.2588; Hodler BTC 0.8131, STRC 101.2197, MSTR 131.6222; Hedge Fund BTC 0.6351, MSTR 234.0767, STRC 101.2197; Saylor MSTR 366.4333, STRC 506.0985. (Full precision in the JSON file.)
- Day 2 gate: spot mode, recomputed with the vehicle mapping in place, must reproduce the latest-close values above to the cent, or Day 2 stops.

## 5. Decision record — Day 1

### LOCKED (Sunil, 29 Oct 2026 ~7:49 a.m. ET)
- **STRC dividends in ETF mode buy the ETF, not spot BTC.** (Day 2 implements this: on a dividend pay session in ETF mode, STRC cash buys the selected ETF at that session's ETF close, in the sleeve's existing dividend split — 100% BTC-slice equivalent for Berkshire/Hodler, 50/50 ETF/MSTR for Hedge Fund, 100% MSTR for Saylor Moon which has no BTC slice and is unchanged in every mode.)
- Weekend/holiday rule: ETF part flat at the Friday close, spot BTC live. (Confirmed in the Day 1 plan; the flat-at-Friday-close behaviour follows from the live-quote route above.)
- Data sources: Yahoo closes primary, cross-checked (sample check done, full Stooq check outstanding — see §2 gap).

### PROPOSED DEFAULTS — for Sunil to approve at the Day 1 completion review, NOT locked
- Labelling: a persistent "You are in IBIT mode" / "You are in FBTC mode" label wherever a BTC value is shown, so ETF mode can never be mistaken for spot.
- Mode persistence: session-only by default, unless the workshop says otherwise (no cross-visit persistence until approved).

### Still open for Day 2/3 (not Day 1 decisions)
- Exact label wording and placement (Day 3 frontend).
- Whether the live-quote list change and the Day 2 ledger mapping go in one push or two (batching decision at Day 2).
- The outstanding full-series Stooq/Tiingo cross-check (see §2 gap) — must be closed before deploy, not necessarily before Day 2 starts.

## 6. What Day 2 needs from here

1. The backfill file above (unchanged unless the outstanding cross-check finds an error).
2. The baseline snapshot above as the spot-regression gate.
3. The locked dividend rule above (ETF buys ETF).
4. The live-quote list change (§3) — can be done in Day 2 alongside the ledger mapping, or as its own step; it is a pipeline change, so it needs its own approval card at push time.
5. The outstanding full-series independent cross-check (§2 gap) closed before any deploy.

## 7. What was NOT done

- No change to `main`, no deploy, no ledger or frontend change, no `prices.yml` change.
- No spot BTC close overwritten, added, or moved.
- No message to the Grok Bot, Chief of Staff, or Site Launch.
- No fee deducted, no premium/discount modelled away.
