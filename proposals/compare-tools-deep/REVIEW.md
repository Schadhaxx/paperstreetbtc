# Compare + Tools, deep version — review note (test branch, NOT live)

Branch: `pepper-compare-tools-deep` (see push SHA in the handover).
Base: main at build time (4 Nov 2026). NOT merged with any
Saturday branch — see Merge notes.

## What it is
One page, `/compare/`, where the calculator draws your
sleeve on the chart (the "deep" proposal Sunil picked
4 Nov from stacked / tabbed / deep). H1 "Compare & Tools";
chart first, Calculator section below it, Copy the weights
last. `/custom/` becomes a redirect stub. Homepage
"The Four Sleeves" section gains a buried footnote link
"Copy the weights →" to the weights section.

## Files
- `compare/index.html` — combined page (chart section from
  old Compare + calculator + weights sections from old
  Tools). compare.js pin et1 → et2. s4.js added (copy
  button). Description + canonical for /compare/ added.
- `assets/js/compare.js` — the only JS change. compare.js
  already served both pages, so the combine is small:
  1. `lumpSeries()` mirrors `lumpVal()` exactly (same
     open-priced buys, same dividend reinvestment at
     pay-day opens, same per-sleeve routes) but snapshots
     the value at every session close, so the line's
     final point equals the calculator's sleeve-today
     number.
  2. `customVals()` builds the custom series: starting
     amount scaled by the sleeve's daily closes from the
     start-date session close (the calculator's own
     convention for the starting amount), plus each valid
     extra contribution's lumpSeries from its buy session.
     Before the start date the line has no points (nulls
     in Chart.js = gap), never backfilled, never flat zero.
  3. `draw()` adds a "Your sleeve" dataset (white line)
     when the "Your sleeve" series button is on (default
     ON), as % change from the custom line's first point.
     The chart note states the conventions and the
     vehicle limitation below.
  4. `calc()` redraws the chart after updating its numbers
     (via `window.__psRedraw`, set by the chart block),
     so changing sleeve / date / amount / contributions
     redraws the line immediately.
- `custom/index.html` — redirect stub only: meta refresh
  to `../compare/index.html#calculator`, canonical to
  /compare/, `noindex`. No scripts, so the old calculator
  cannot run twice.
- `index.html` — nav "Tools" now points at
  `compare/index.html#calculator` (desktop + mobile);
  the existing `#copy-weights` hash redirect now points
  at `compare/index.html#weights`; buried weights link
  added at the end of the sleeves section (muted note
  style, not a button).
- `sitemap.xml` — homepage + /compare/ + /recap/ only.
  /custom/ removed (it is a stub now). If the SEO branch
  merges first, its /custom/ entry is superseded by this
  version — take this version.

## Decisions made in the build (v1)
- Custom line is SPOT-BASED and does not follow the
  vehicle toggle (stated in the chart note). Reason:
  vehicle-daily carries closes only, no vehicle opens,
  so an open-priced vehicle buy cannot be computed
  exactly. Following the toggle is a follow-up, not a
  silent approximation.
- Dividends on the custom run follow the same ledger
  rules as the sleeves (lumpSeries = lumpVal logic),
  so the line is comparable with the sleeves it sits
  next to.
- The two today's-values numbers stay under the chart;
  the line does not replace them.

## Merge notes (read before merging)
- This branch does NOT include Saturday's Compare
  refresh or sleeve candles — they touch the same
  `compare.js` draw() and the same `compare/index.html`.
  Grok merges all three; the custom-line code lives in
  draw() and in the new helpers, the refresh code in
  loadHistory, the candles in drawCandles — different
  functions, same file, merge by hand, do not take one
  branch's compare.js wholesale.
- compare.js pin et2 here collides with the refresh
  branch's et2 (different code, same pin). Merged file
  keeps one pin; bump again if the merged content
  differs from either branch.
- Recap page nav still links to /custom/ — the stub
  redirect covers it. Updating recap nav is a follow-up,
  not in this branch.

## Rollback
Revert the branch. Old /compare/ and /custom/ pages
are untouched on main; the stub only exists here.

## Checks owed (Saturday / browser)
- Chart draws with the white "Your sleeve" line by
  default; toggling it off/on works.
- Line's last point equals the calculator's sleeve-today
  number (same computation, two presentations).
- Changing sleeve / date / amount / adding a
  contribution redraws the line; a contribution steps
  the line up on its buy session.
- Copy weights button still copies and says Copied.
- Homepage buried link lands on the weights section;
  /custom/ redirects to the calculator section.
- Phone width (390px): calculator + chart + weights.
