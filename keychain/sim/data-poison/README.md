# data-poison/ — edge-case-test poison mode
A copy of `data/` with three malformed rows injected into
`candles-3600.json` (all inside the newest-169-row 1W window):
- row index 5 (newest-first): close set to 0 — would drag the 1W
  line low to 0 if not skipped.
- row index 50: short row `[t, 999999.0]` — size < 6, must be skipped.
- row index 100: zero-time row `[0, 1, 1, 1, 1, 100]` — would drag
  the 1W line low to 1 if not skipped.
Run: `edge-case-test data-poison poison`
The expected 1W tiles are derived from this file at run time by
the test itself (see expected1W in tools/edge-case-test.cpp).
