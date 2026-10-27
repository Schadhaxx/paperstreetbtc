# Task 3 — Mon 26 Oct 2026, 10 a.m. ET — CR-005: lump sums, open vs close

Answer first, in plain business terms: switch Tools Page lump sums from the daily close to the daily open, for all 9 assets, backfilled to 2025-12-31. No new vendor needed — Yahoo already returns `open` in the same daily bar as `close`.

## Decided rules — user, Mon 26 Oct 2026 evening (these supersede the morning leaning)

Page name: the lump-sum page is now called the Tools Page, NOT Custom. Use "Tools Page" going forward.

1. Lump sums must be during market hours.
2. Price is the OPEN, not the close.
3. History MUST be redone — existing lump sums repriced to the open, including dividend counts/history.
4. BTC follows the same market-open rule even though BTC trades 24/7, because the user cannot buy BTC until their broker lets them at market open — i.e. BTC lump-sum price is the market-open price, not the Yahoo midnight-UTC boundary open.
5. Lump sums ONLY work on weekdays — no weekend lump sums.
6. Weekend rule: a weekend lump sum is HELD until Monday open, NOT rejected.
7. Dividend / tracker: the open/market-hours rule also dictates the dividend reinvestment buy as shown in the tracker — dividend cash buys at the market open on the issue day (weekdays only, held to Monday open if it falls on a weekend), and repricing that history changes the tracker holdings/units and YTD. Lump sums themselves are entered on the Tools Page; dividend buys are automatic and show up in tracker holdings.
8. Price method CONFIRMED: stick to the OPEN. First-30-minute average / VWAP was discussed as a dynamic alternative (smoother, but needs intraday bars for all 9 assets back to Dec 31 2025, harder to audit) and NOT chosen.

## Evidence / impact

- Assets: BTC, MSTR, STRC, TSLA, PLTR, SPY, QQQ, BRK.B, GLD — all 9.
- Example from the morning report: PLTR 21 Oct open 191.72 vs close 201.72 — about a 5% units difference on volatile days, which is why the open matters.
- Full morning report (recommendation only, before the evening decisions): workspace log task3-2026-10-26-cr005-open-vs-close.md, held in Muse's workspace and summarised in the Friday handover report.

## What is NOT authorised in this task

- Implementation is NOT authorised here. Chief of Staff will delegate CR-005 implementation on Friday (via Grok Bot coordination). Pepper does NOT build/implement CR-005 now.
- No live site change, no main-branch change, no deploy from this file.

## Open questions remaining for Friday (Grok Bot + Chief of Staff)

1. Holiday handling: weekday vs trading day — is a holiday treated like a weekend (held to next open) or like a weekday?
2. What happens to a lump sum entered outside market hours on a weekday — held to next open, or rejected? (Weekend rule is decided: held to Monday open.)
3. Audit / display: how should repriced history be labelled in the tracker so a user can see what changed?

## Ready-to-forward summary

CR-005 decided: Tools Page lump sums buy at the market open, weekdays only, weekend attempts held to Monday open, history repriced to the open including dividend buys, BTC at market-open price. Implementation to be delegated by Chief of Staff on Friday. No code changed by this report.
