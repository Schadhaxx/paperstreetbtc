# Vehicle toggle — cross-check report (Stooq gap closure)

Date: Thu 29 Oct 2026. Test branch only (`pepper-vehicle-toggle-day1`). No change to
`assets/data/vehicle-daily.json`, no main change, no deploy, no ledger/frontend change.

## 1. Stooq outcome — NOT usable from this environment

- Stooq daily CSV endpoint (`stooq.com/q/d/l`, `ibit.us` / `fbtc.us`, daily) was
  attempted via the text-fetch route on 29 Oct 2026.
  - IBIT: fetch failed with a network error (DNS, timeout, or connection refused),
    no HTTP status returned.
  - FBTC: fetch failed with no extractable content, no HTTP status returned.
- The request was NOT retried (a repeat of a failed fetch is not a diagnosis).
- This proves only that Stooq's CSV endpoint is not fetchable from this
  environment on this attempt. It does NOT prove Stooq is down globally, and it
  does NOT prove the symbols/parameters are wrong — the endpoint format used is
  Stooq's documented daily-CSV format.
- Consistent with Day 1 (connection dropped, retry hung) and Day 2 (network error).
  Conclusion: **a Stooq full-series cross-check itself remains uncompleted.**
  The gap below is closed by a different independent source instead, as the task
  allowed — it is not claimed as a Stooq check.

## 2. Independent source used instead — Finnhub daily candles

- Source: Finnhub (finnhub.io) structured daily-candle data returned with web
  search results for IBIT and FBTC, 29 Oct 2026. Finnhub is a separate market-data
  vendor from Yahoo, which supplied the backfill's daily closes. Caveat, stated
  plainly: Finnhub is also the pipeline's live-quote vendor (for live prices, not
  for daily closes), so this is independent of the Yahoo daily-close source, not
  of every vendor the project touches.
- Coverage: Finnhub daily candles, 259 sessions each, first 2025-10-15 (ET) to
  last 2026-10-27 (UTC date = trading date, verified against known closes, e.g.
  IBIT 2026-10-23 $45.96 and 2026-10-27 $45.70, FBTC 2026-10-23 $70.61 and
  2026-10-27 $70.19 — all matching the backfill).
- Overlap with the backfill (2025-12-31 to 2026-10-28, 208 sessions per vehicle):
  **207 sessions covered by Finnhub daily candles, 1 session (2026-10-28)
  covered separately — see §3. No extra dates in range, no missing dates other
  than 2026-10-28.**

## 3. Result — clean pass, no flags over 0.05%

| Vehicle | Compared | Exact to the cent | Max difference | Flags > 0.05% |
|---|---|---|---|---|
| IBIT | 207 sessions (2025-12-31 to 2026-10-27) | 207 / 207 | 0.0128% (2026-03-02, sub-cent rounding) | none |
| FBTC | 207 sessions (2025-12-31 to 2026-10-27) | 207 / 207 | 0.0090% (2026-07-10, sub-cent rounding) | none |

- 2026-10-28 (the one session outside the Finnhub daily list, because the
  daily list ends 2026-10-27): Finnhub's current-price snippet for the
  2026-10-28 regular-session close gives IBIT $46.14 and FBTC $70.85, exactly
  matching the backfill. Corroborated independently by YCharts historical tables
  (IBIT Oct 28, 2026 close $46.14; FBTC Oct 28, 2026 close $70.85) and, for FBTC,
  by the Stocknear history table (Oct 27 $70.19, Oct 26 $69.44, Oct 23 $70.61 —
  all matching the backfill).
- No date in either vehicle differs from the independent source by more than
  the 0.05% stock threshold. **No correction to `vehicle-daily.json` was needed
  or made.**

## 4. Gap status — CLOSED (by Finnhub, not by Stooq)

- The Day 1 / Day 2 open item "full-series independent cross-check" is now
  closed on this evidence: 208/208 sessions per vehicle verified against an
  independent source (207 via Finnhub daily candles + 2026-10-28 via Finnhub
  close, corroborated by YCharts), with zero flags over 0.05%.
- Honest limit to keep in the record: this is a Finnhub cross-check, not a
  Stooq cross-check. If a reviewer specifically requires Stooq, that sub-item
  remains open and would need a Stooq fetch from an environment where Stooq's
  CSV endpoint is reachable.
- Nothing in this report authorises a deploy on its own: the cross-check gate
  is closed, but the rebasing model decision (with Sunil, separate) and the
  Day 3 / Day 4 work still stand in their own right.
