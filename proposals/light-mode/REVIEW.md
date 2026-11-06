# Light mode — integration review (Pepper)

## Base and reference
- **Base:** current main `1f3b958` (verified 6 Nov ~3 p.m.: rollback `6d7c830`
  reverted Speed Option 2, then test-only `1f3b958`). Main unchanged since.
- **Reference:** Grok Bot's `light-mode-local`, head `77ff1a6`, built on `dd71e0d`,
  patches 0001–0008. Published by Chief of Staff as the branch
  `pepper-light-mode-reference` (same head `77ff1a6`).
- **Method:** integrated, NOT merged wholesale. The reference's combined diff
  (`light-mode.diff`) was applied onto current main `1f3b958` in this branch.
  Verified after applying: the staged tree is byte-identical to the reference
  branch except for two files that come from main's newer head — the YTD chart
  scroll regression test (`tests/test_ytd_chart_scroll.py`, from `1f3b958`) and
  its one-line hook in `tests/run_all.sh`. Both are kept: they guard the Speed
  Option 2 rollback. Nothing else differs.
- The remote `grokbuild-light-mode` branch is an older experiment ("Do not
  merge") and was NOT used — it deletes the OI-001 tests.

## What changed (26 files, +1299/−73 vs main)
- New: `light.css` (471 lines, `?v=lm4`), `chart-theme.js` (`?v=lm1`),
  `assets/js/theme-pill.js` (`?v=lm2`), and four tests
  (`tests/dark_regression.py`, `tests/theme_toggle.py`,
  `tests/theme_pill_layout.py`, `tests/stale_html_psC.py`).
- Changed: `index.html` (floating pill script + theme links), `compare/` and
  `custom/index.html`, `screener.html`, `recap/index.html` and the 11 monthly
  recaps (footer theme links + inline head theme script), `assets/js/btcchart.js`
  (psC fallback + psC() colour calls, pin et5/et1 → et6),
  `assets/js/screener-chart.js` and `assets/js/screener-indicator-chart.js`
  (psC calls).
- Design, as specified: dark is the default, no automatic switching on device
  settings. Home: floating **Light / Dark** pill beside the existing **↑ Top**
  button (matches Top's height, font, radius, colour and alignment, even
  spacing; Top keeps its scroll behaviour). No theme link in the home footer.
  Other pages: footer **Light version / Back to dark** links, no floating pill.
  Choice remembered in `ps-theme` local storage; `?theme=light` and
  `?theme=dark` keep working.

## The one fix Pepper made on top of the reference (Chief's instruction)
- **Footer spacing narrowed to recap pages only.** Patch 0008 put
  `margin-bottom: 4.75rem` on `.ps-theme-link` globally. That rule now reads
  `body.ps-recap .ps-theme-link`, and the 11 monthly recap pages carry
  `<body class="ps-recap">`. No other page gets the class or the spacing.
  (In practice only the monthly recaps have `.ps-theme-link` elements, so this
  changes no rendered layout today — it scopes the rule explicitly, as asked.)
  The other `.ps-theme-link` rules (show/hide of the Light/Dark link text,
  link colour) stay global; they are visibility, not spacing.

## Preserved (verified in this branch)
- Original Chart.js charts and chart interactions — no chart code changed
  except the psC() colour calls.
- OI-001: `compare.js` untouched — the `BFB`/`BPROV` hoist before `run()`,
  the backup-source label, and the failed-fetch reset (`BFB={}`) are all intact.
- `psC` colour-helper fallback in the chart scripts, including the trailing
  semicolon (`window.psC=window.psC||function(d,l){...};` at the top of
  `btcchart.js`, and the same `||` form in `theme-pill.js` and `chart-theme.js`),
  so cached HTML cannot break charts. The inline head script in each page also
  defines `psC` with a trailing semicolon.
- No speed changes: `a746518`, `96c3d74`, `c9f4cf6` are in main's history but
  reverted by `6d7c830`; `s2.js` has no `drawNative`, no `touchAction='none'`,
  no `setPointerCapture`. The native YTD renderer and the lazy panel split are
  NOT reintroduced.
- Fresh cache-busters on every affected page: `light.css?v=lm4`,
  `chart-theme.js?v=lm1`, `theme-pill.js?v=lm2`, `btcchart.js?v=et6`.
- Scope: no logo/image replacements, no unrelated layout changes, no portfolio
  math, prices, data or workflow changes. No STRF/STRK/STRD coverage.
- Syntax: `node --check` passes on all five JS files; `light.css` braces
  balanced (82/82).

## Pin note for the merge
- This branch sets `btcchart.js?v=et6` everywhere. The block-clock V2 branch
  (`pepper-block-clock-v2`) sets et9 on index/screener/clock and et5 on
  compare/custom/recap. Whoever merges last must reconcile to a single fresh
  pin matching the final merged `btcchart.js` content.

## Checks (before any main commit)
- Re-run `tests/dark_regression.py`, `tests/theme_toggle.py`,
  `tests/theme_pill_layout.py`, `tests/stale_html_psC.py` against this branch.
  The export's logs are historical evidence from Grok's environment, not fresh
  tests on this integration.
- Browser checks: all pages and monthly recaps in both themes; chart
  readability; theme persistence; keyboard operation; mobile touch scrolling
  starting on charts; floating controls don't overlap or block taps. Full-page
  dark screenshots vs current main — only the theme controls and the
  narrowly scoped recap footer spacing should differ.
- Do not rely on pass counts alone.

## Delivery
- This branch is the review package. NO commit to main until Chief of Staff's
  read-only review is done and Sunil relays written changes; Pepper handles
  rebuilds and the final commit, then Grok's live-site check.
