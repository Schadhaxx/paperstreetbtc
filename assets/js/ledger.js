/* PaperStreet site book: the ONLY stored portfolio state. Everything shown (Pulse, YTD, chart, month-end cards) is computed from this ledger
   x the site's own daily closes (data branch history.json) and live prices (prices.json) on every page load.
   Funding: $100,000 per sleeve at target weights at the 2025-12-31 close (= the January 1st, 2026 start). No rebalancing: holdings float.
   Events that change holdings: STRC cash dividends only. Receivable (cash) = STRC shares held at ex-date x $/share, from the ex-date until the
   pay date; on the pay date (rolled to the next NYSE session if it falls on a weekend/holiday) the cash buys the sleeve's dividend assets at that
   session's close. Real declared events only, on their real dates; no daily accrual/backfill. Monthly through Jun 2026, twice a month from Jul 15. */
window.PSLEDGER = {
  base: '2025-12-31', start: 100000,
  sleeves: {
    berkshire: { w: { BTC: .40, STRC: .20, TSLA: .30, PLTR: .10 }, div: { BTC: 1 } },
    hodlr:     { w: { BTC: .70, STRC: .10, MSTR: .20 },            div: { BTC: 1 } },
    hf:        { w: { BTC: .55, MSTR: .35, STRC: .10 },            div: { BTC: .5, MSTR: .5 } },
    saylor:    { w: { MSTR: .50, STRC: .50 },                      div: { MSTR: 1 } }
  },
  rebalances: [], /* none: buy-and-hold */
  /* STRC declared dividends: [record, ex-date, scheduled pay date, $/share] (Strategy 8-Ks / strategy.com/strc) */
  strc: [
    ['2026-01-15', '2026-01-15', '2026-01-31', 0.916667],
    ['2026-02-15', '2026-02-13', '2026-02-28', 0.937500],
    ['2026-03-15', '2026-03-13', '2026-03-31', 0.958333],
    ['2026-04-15', '2026-04-15', '2026-04-30', 0.958333],
    ['2026-05-15', '2026-05-15', '2026-05-31', 0.958333],
    ['2026-06-15', '2026-06-15', '2026-06-30', 0.958333],
    ['2026-06-30', '2026-06-30', '2026-07-15', 0.479167], /* transitional half period */
    ['2026-07-15', '2026-07-15', '2026-07-31', 0.500000],
    ['2026-07-31', '2026-07-31', '2026-08-15', 0.500000],
    ['2026-08-15', '2026-08-14', '2026-08-31', 0.500000],
    ['2026-08-31', '2026-08-31', '2026-09-15', 0.500000],
    ['2026-09-15', '2026-09-15', '2026-09-30', 0.500000],
    ['2026-09-30', '2026-09-30', '2026-10-15', 0.500000],
    ['2026-10-15', '2026-10-15', '2026-10-31', 0.500000]
    /* NOT INCLUDED (conditional, pending the Oct 28 2026 vote): ['2026-10-31', '2026-10-30', '2026-11-15', 0.500000] */
  ]
};
