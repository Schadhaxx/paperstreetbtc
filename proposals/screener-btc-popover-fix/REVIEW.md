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
- Browser-verified on this test branch 2 Nov 2026 ~4:45 p.m. (test copy at the exact commit
  SHA, live site untouched): screener BTC pill opened on 1D Line; switching to 1M Line redrew
  the chart (dates 10-02 to 11-01, ~$76k–$88k) and the note changed to daily-closes text with
  "provisional until 7 PM ET"; + S&P 500 drew the purple line and added -2.3% to the header;
  + Gold drew the yellow line and added -4.4%; + MSTR drew the orange line (~-18% to -19%)
  but, as noted below, added no header percentage; tapping all three off removed each line
  and restored the single BTC line. The original crash is fixed.
- Homepage pill re-check on Saturday review is still worthwhile (it was already working
  before this fix, and its pin moved et5 → et6 in this branch).

## Rollback
Revert this single commit (screener.html, index.html, btcchart.js). No data or pipeline rollback.

— Pepper, for Sunil, 2 Nov 2026
