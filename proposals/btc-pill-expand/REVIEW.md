# BTC pill expands into its chart — REVIEW (Saturday)

**Sunil + Pepper work, for Grok Bot + Chief of Staff peer review on Saturday.**
**Test branch only. Nothing here is live. Live only from the Grok side, after
Sunil's yes, one item at a time.**

## What it is
The live BTC pill no longer just opens a chart that appears at full size.
Two changes, from the 2 Nov mockup + spec (`btc-pill-expand-mockup.html`,
`btc-pill-expand-spec-for-saturday.md`, Sunil's copy):

1. **Discoverability.** The bare `▾` at the end of the pill is replaced by a
   labelled chip: `↗ Chart ▾`, in cyan with a cyan outline. It is visible at
   phone width (the "Live BTC" label is still hidden on phones; the chip is
   not). The pill's aria-label is unchanged ("Live BTC price. Open BTC chart").
2. **FLIP morph.** Opening the chart grows the dialog out of the pill that
   was tapped: the dialog is placed at its final position, scaled and
   translated to the pill's rectangle, then animated (~450ms, ease) to full
   size, with border-radius animating from pill-round to the card's radius.
   Closing reverses it: the dialog shrinks back into the pill before hiding.
   The chart itself is drawn at final size throughout (the transform only
   scales it visually), and it is resized once the grow finishes.
   `prefers-reduced-motion` skips the animation entirely — the dialog
   appears at final size, exactly as before. A window resize mid-animation
   snaps the dialog to its final size, never leaving it stranded scaled.

## Files changed
- `assets/js/btcchart.js` — chip text in `decorate()`; morph helpers
  (`reducedMotion`, `morphToPill`) and rewritten `open()` / `close()`; the
  resize handler clears any in-flight morph before re-placing.
- `assets/css/nav.css` — `.lp-cv` becomes the chip style; `.bc-w.bc-morph`
  carries the 450ms transform + border-radius transition, disabled under
  reduced motion.
- `index.html`, `screener.html` — btcchart pin et5 → et6 (script changed).
- `compare/index.html`, `custom/index.html`, `recap/index.html`,
  `recap/2026-*/index.html` — btcchart pin et1 → et2 (same reason).

## Deliberately NOT changed
- No data, chart content, ranges, toggles, or vehicle behaviour. The popover
  stays Spot BTC only; the tracker BITCOIN VEHICLE toggle is untouched.
- No pipeline, ledger, or history changes.
- This branch does **not** include the screener BTC popover fix
  (`pepper-screener-btc-fix`): screener.html still does not load et.js here,
  so the provisional-close note bug on the screener is still present on this
  branch alone. The two branches touch different parts of btcchart.js
  (that fix: the drawDaily note; this one: open/close), so they should merge
  cleanly, and both already use pin et6 on index/screener. If the screener
  fix lands first, rebase this branch onto it and re-check the screener pill.

## Checks done by Pepper (pre-review)
- `node --check assets/js/btcchart.js` passes.
- Browser check on this branch (githack, exact commit SHA): homepage pill
  shows the `↗ Chart ▾` chip; tapping it grows the dialog from the pill;
  closing shrinks it back; the 1D Line chart draws; Escape / ✕ / dim-click
  still close. (Filled in after the check runs — see verification note below.)

## Checks still for Grok Bot (before deploy)
1. Read the diff, not just this note.
2. Browser-check the branch at phone width (390px): chip fits the header
   pill, the sheet morph travels to the bottom sheet, and the chart resizes
   cleanly after the grow.
3. Confirm the Saturday open questions from the spec are settled as built:
   chip wording "Chart" (not "Tap for chart"); straight morph to the sheet
   on phones (no expand-in-place-then-dock step); no pulse-until-first-open.
4. Merge order with `pepper-screener-btc-fix` (see above), then one live
   check after deploy, with a rollback line (revert this branch's two
   script/CSS changes and the pin bumps).
