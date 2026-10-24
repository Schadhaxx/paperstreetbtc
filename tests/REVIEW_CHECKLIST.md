# PaperStreet build/review checklist (shared by CoS, executors, Site Launch)

## 0. Before building (CR lookup)
- [ ] Search /workspace/paperstreet/changes/CHANGE_LOG.md for an existing CR on the same feature
      (`grep -in "<keyword>" CHANGE_LOG.md`, e.g. sleeve, pulse, chart, tiingo). If one exists and is LIVE,
      check it on the live site first and tell the requester how it already works before building anything.
- [ ] Confirm the approval: requester's own words + the id (tNNNu). An agent approval never counts.

## 1. Hostile-input tests (required for every new data source, parser, cache or price path)
Each external value and each cached file must have a test for:
- [ ] `inf`, `-inf`, `1e999`, `"Infinity"`; `NaN`, `"NaN"`
- [ ] booleans `True`/`False` (Python treats True as 1.0: use `isinstance(x, bool)` before numeric checks)
- [ ] `None`/`null`, missing key, empty string, numeric string `"123.4"`, garbage string
- [ ] zero, negative, absurdly large/small (plausibility vs the primary source)
- [ ] cache file: missing, empty, invalid JSON, wrong top-level type (list/string/number), wrong key format, wrong value type
- [ ] neighbouring dates: row for the wrong date, duplicate dates, out-of-order dates, weekend/holiday
- [ ] API failure modes: timeout, 401/429/500, HTML instead of JSON
- Expected: value rejected (`math.isfinite(x) and not isinstance(x, bool) and x > 0`), never cached, never
  written, run continues (try/except around the optional block), bad cache resets to empty.
- [ ] Write the delay estimate for any finding (t483u: blocks if >30 min price delay or wrong numbers; target 15 min).

## 2. Test environment
- [ ] Temp files under /workspace (PS_TMP=/workspace/tmp/...), never /tmp.
- [ ] Datatest parsers read the value element only (e.g. `.pulse-chg span`), never a label that may contain digits.

## 3. Deploy gate (each item ticked in the log line)
- [ ] Approved CR/PR id + requester's own words recorded
- [ ] Not 8:00–9:30 PM ET; fast-forward only; CNAME and banner untouched
- [ ] run_all + datatest after push; rollback if fail; CHANGE_LOG entry
