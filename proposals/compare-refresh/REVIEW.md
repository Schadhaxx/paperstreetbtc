# Compare Refresh — REVIEW NOTE (read this first)

## DO NOT REVIEW UNTIL SATURDAY
This is brainstorming work by Sunil and Pepper only.
Grok Bot, Chief of Staff, and the rest of the Grok team: please stay out of this conversation until Saturday.
We will ask for your input on Saturday, when we are done. Until then, no review, no comments, no alterations, no deploy.

## What this is
- Branch: `pepper-compare-refresh` (test branch only — NOT main, NOT live).
- Change: Compare page tap-to-refresh + as-of note, Phase 1 only. No polling, no pipeline change, no ledger change.
- Files changed: `compare/index.html` (Refresh button, compare.js pin et1 → et2) and `assets/js/compare.js` (reusable `loadHistory()`, preserved series/range selection across refresh, old chart destroyed before redraw, refresh states).
- Phase 2 (dashed live last point from prices.json) is NOT in this build. It stays optional and cuttable; ship Phase 1 alone if Phase 2 is ever wanted later.

## What it does, exactly
- On load: chart draws as before, note now starts "Data as of <last session> close."
- Tap Refresh: button disables while fetching, note says "Refreshing…".
  - New close found: chart redraws with the same selected series, range, and vehicle mode; note says "Updated <ET time> · Data as of <new close> close."
  - No new close: chart unchanged; note says "Already up to date · Data as of <last close> close."
  - Fetch fails: chart unchanged, previous closes kept; note says "Couldn't refresh — showing <last close> close." Never a blank chart, never an invented value.
- No timer polls history.json. History is fetched only on page load and on a Refresh tap.

## Test results (Pepper, 2 Nov 2026, before filing)
- `node --check assets/js/compare.js` passes. No `setInterval` added.
- Node harness with stubbed Chart/document/fetch, using the real data-branch history.json:
  - Initial load: note "Data as of 30 Oct 2026 close", default series Hodler / Spot BTC / Gold / MSTR drawn.
  - Refresh with unchanged history: "Already up to date · Data as of 30 Oct 2026 close", chart not recreated.
  - Refresh with a staged extra session (2 Nov 2026): chart recreated (old chart destroyed), note "Updated <ET time> · Data as of 2 Nov 2026 close", labels end …29 Oct, 30 Oct, 2 Nov. PASS.
- NOT yet verified in a real browser on this branch (that check is for Saturday's review, with the live page, at phone width).

## Saturday review (when input is wanted)
- Grok Bot + Chief of Staff review the diff, test at 390px phone width, and may alter it.
- Live only from the Grok side, after Sunil's yes, avoiding 8:00–9:30 p.m. ET pushes.
- Rollback: revert the single commit touching `compare/index.html` + `assets/js/compare.js`. No data, pipeline, or deploy rollback needed.
- Full build package (spec, test checklist, grouping with the other Grok-side build work): `compare-refresh-build-package-2026-11-02.md`, held by Sunil — ask Sunil for it on Saturday if you need it; it is not filed in this branch.

— Pepper, for Sunil, 2 Nov 2026
