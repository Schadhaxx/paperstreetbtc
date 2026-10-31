# Stale-note audit — REVIEW

## File / folder list
- Test branch: `pepper-stale-note-audit` (from current main `65dc45a`, verified first, not assumed)
- Changed files: `assets/js/compare.js`, `assets/data/screener-pack.json`
- This review note: `proposals/stale-note-audit/REVIEW.md`
- NOT changed: any number, price, data series, behaviour, banner text, dividend wording, status lines, clock split, vehicle toggle, charts.

## Audit table

### 1. Compare ETF-mode note — CONFIRMED STALE, FIXED
- Location: `assets/js/compare.js`, `pvChartNote` (ETF mode only).
- Old text (verbatim): "You are in ${VEH} mode — BTC sleeve priced in ${VEH} at its latest close (live ETF quotes pending the prices.yml change). Spot BTC remains the hurdle."
- Why stale: the prices.yml change landed 29 Oct 2026 as `75cfaf44` ("Vehicle toggle: add IBIT/FBTC to live-quote list") and quotes were verified flowing that day. The "pending" claim has been false since then.
- New text: "You are in ${VEH} mode — BTC sleeve priced in ${VEH} at its latest close. Spot BTC remains the hurdle."
- Note on the fix choice: the parenthetical was deleted, not replaced with a live-quote claim, because the Compare sleeve itself is still priced from `vehicle-daily.json` latest closes — claiming live-quote pricing there would have introduced a new inaccuracy.

### 2. GOLD "+" note — CONFIRMED STALE, FIXED
- Location: `assets/data/screener-pack.json`, indicators GOLD `note` (shown behind the gold "+" pill).
- Old text (verbatim): "COMEX gold futures (GC=F), $/troy oz. Pack close only until the pipeline writes GOLD."
- Why stale: the pipeline has written GOLD since 29 Oct 2026 (`78160e8`, Yahoo chart block for `GC=F` in `prices.yml`, 17 keys, verified working that evening). "Until the pipeline writes GOLD" has been false since then.
- New text: "COMEX gold futures (GC=F), $/troy oz. Pipeline writes GOLD live in futures hours."
- Note: "futures hours" (CME Globex, Sun 6 p.m. ET → Fri 5 p.m. ET, excluding the daily 5–6 p.m. break) is the correct clock for GOLD, per the 30 Oct clock split — not generic stock-market hours.

### 3. Other sweep results — checked, NOT stale (left alone)
- `assets/js/screener.js` fallback "rows show their 28 Oct 2026 closes" — still true: the pack `asOf` is 2026-10-28, so the fallback describes the pack correctly.
- `assets/js/screener-chart.js` "snapshot rows vs 27 Oct 2026" — still true: snapshot rows' day change is vs the prior session close (27 Oct), the pack close being 28 Oct.
- `assets/js/vehicle.js` comment "Until the prices.yml live-quote change lands, ETF prices are the latest vehicle closes" — code comment, not visitor text, and still accurate for the vehicle pricing mechanism (vehicle-daily.json latest closes). Left alone.
- Dividend / rebalancing wording — see "Intentionally left alone" below.

## Overlap with `pepper-screener-clean-blurbs` (de787ff, NOT live)
- That branch already proposes deleting "Manual refresh only, when Sunil asks" from all visitor-facing chart text and shortening chart sub-blurbs, and deleting most row "+" pills.
- This audit does NOT re-propose any of those lines: the "Manual refresh" strings still on current main (indicator-chart footnotes, weekly JSON notes) are covered by clean-blurbs, not duplicated here.
- No conflict: clean-blurbs does not touch the Compare note or the GOLD "+" note, and this audit does not touch chart blurbs or footer "+" text. Grok Bot can take both branches without a text conflict on the same line (the only shared file, `screener-pack.json`, is touched by clean-blurbs for notes/version and by this audit for the single GOLD note line — a merge will need to keep both, i.e. the GOLD new text plus the clean-blurbs version/buster changes).
- The GOLD "+" pill itself is deleted by clean-blurbs (all indicator "+" pills except SPCX go). If clean-blurbs lands first, this audit's GOLD fix becomes moot for that pill; if this audit lands first, clean-blurbs then deletes the corrected pill. Either order is safe — the corrected text never contradicts the deletion.

## Intentionally left alone
- Dividend / rebalancing wording (e.g. ledger header "Monthly through Jun 2026, twice a month from Jul 15", sleeve issue-day lines): STALE BY SUNIL'S DECISION, recommendations only. Not fixed here, per the brief. The confirmed daily basis (29 Oct 8-K, STRC effective 1 Nov 2026) is already covered by the dividend recommendation report.
- Banner text: untouched.
- All numbers, prices, data series, and behaviour: untouched.
- No STRF/STRK/STRD wording introduced anywhere in this diff (grep-verified).

## Checks
- `node --check` passes on `compare.js`, `screener.js`, `screener-indicator-chart.js`.
- `screener-pack.json` parses as valid JSON.
- Grep on the branch: "live ETF quotes pending" gone; "Pack close only until the pipeline writes GOLD" gone.
- Painted-browser / real phone tap: NOT checked here — remains Grok Bot's check.

## Rollout (for Grok Bot / Chief of Staff)
1. Grok Bot diff-only review of this branch. 2. Sunil's own yes. 3. Push to main (no prices.yml step needed for this branch). 4. One live check (Compare in ETF mode; screener gold "+" pill). 5. Rollback: revert the single release commit.
- NOT pushed to main, NOT live.
