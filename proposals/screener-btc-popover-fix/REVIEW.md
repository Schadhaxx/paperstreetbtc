# Screener BTC popover fix — REVIEW NOTE (read this first)

## For Saturday review — do not deploy before then
Prepared by Pepper for Grok Bot + Chief of Staff review on Saturday 7 Nov 2026.
Nothing here is live. Live only from the Grok side, after Sunil's yes, avoiding 8:00–9:30 p.m. ET pushes.
Test branch only: `pepper-screener-btc-fix`.

## The bug (reproduced live on the screener, 2 Nov 2026 ~4:37 p.m.)
On screener.html, the BTC pill popover opened on 1D Line, and switching to 1M Line then tapping
+ S&P 500 / + Gold / + MSTR updated the button labels and the header percentages, but the chart
never redrew (stayed on the 1D intraday line) and the note never left the 1D intraday text.
The same test on the homepage worked fully: 1M redrew, the purple S&P 500 line appeared, and
tapping it off removed it.

## Root cause
- screener.html was the only page loading btcchart.js without also loading assets/js/et.js
  (homepage loads et.js; compare/custom/recap pages load it too).
- btcchart.js drawDaily() builds its note with an unguarded ET.btcCloseLabel(), but only when
  today's BTC close is provisional (PROV true — as on 2 Nov, when the homepage note itself said
  "Today's close is provisional until 7 PM ET").
- On the screener that call threw after the header line was written but before the new chart was
  created. That is exactly the observed symptom: labels/header update, note/chart do not.
- Consequence: the bug comes and goes with the provisional state — it looks fine on days when
  the BTC close is already final.

## The fix (this branch, 3 files + this note)
1. `screener.html`: load `assets/js/et.js?v=et2` before btcchart.js, and bump the screener's
   btcchart pin et5 → et6.
2. `index.html`: bump btcchart pin et5 → et6 (the script itself changed; same push, same pin).
3. `assets/js/btcchart.js`: new `provCloseLabel()` helper — uses ET.btcCloseLabel() when ET is
   present, otherwise computes the same 00:00 UTC close in America/New_York directly, with a
   '7 PM ET' fallback. drawDaily() now calls provCloseLabel() instead of ET.btcCloseLabel().
   So even a future page that forgets et.js cannot freeze the chart this way again.
- NOT changed: no data, pipeline, ledger, vehicle, or screener-table code. No MSTR header change
  (see below).

## Separate quirk, deliberately NOT changed here
drawDaily's header string lists BTC, S&P 500, and Gold only — it never lists an MSTR percentage,
even when the MSTR line draws. That is existing code design, not part of this crash. If Grok Bot
and Chief want an MSTR header value, that is a separate decision.

## Verification done before filing
- `node --check assets/js/btcchart.js` passes.
- Diff reviewed: only the 3 changes above (plus this note).
- NOT yet verified in a browser on this branch — that check belongs in Saturday review:
  open the test-branch screener, open the BTC pill, switch to 1M Line, tap + S&P 500, + Gold,
  + MSTR, and confirm each line appears and the note changes; tap them off and confirm the
  lines disappear. Also confirm the homepage pill still works the same way.

## Rollback
Revert this single commit (screener.html, index.html, btcchart.js). No data or pipeline rollback.

— Pepper, for Sunil, 2 Nov 2026
