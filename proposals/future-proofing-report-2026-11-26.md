# Website future-proofing: YTD + Max — implementation report

**Date:** 26 Nov 2026
**Status:** Report only. No site change, no branch, no deploy.
**Revision 3:** 26 Nov 2026 — after Grok Bot's second review (one fix left, then a pass). The pack-writing step is now part of the one-time build; §4 and §6 rollover lines aligned with the table; withdrawn Jan-1 framing fixed; EARLY added to the late-2028 checklist, with the client-side expiry note.
**Revision 4:** 26 Nov 2026 — after the full four-reviewer pass on revision 3 (Site Launch, PaperStreet Portfolio Bot, Chief of Staff, Grok Bot): 1 MUST, 10 SHOULD, 3 NICE, all folded in below; everyone agrees with the §12 recommendations. MUST: the base-close conflict (§4/§5/§11) — the daily and weekly files keep the launch base, the pack's baseClose is tile-YTD only, and the pack check compares the pack to the current year's base-date close. SHOULD: SPCX listing basis is 2026-only (Dec 31, 2026 base from the first 2027 session); STRC never pre-fills undeclared months (one lump per record day once declared, pay date rolled to the next NY Fed business day, never spread or backfill); the pack writer checks every number is finite and sensible and writes atomically; §10 gains a simulated Jan 2, 2027 run of cmp_daily.py and stock_weekly.py against a rolled pack, and test_recap.py line 58 is confirmed already listed (revision 3); the pack rolls baseClose only after the Dec 31 close is final, on the first 2027 run (same for the SPCX switch); one launch phrasing everywhere — "Launched January 2026 with $100,000 (priced at the 31 Dec 2025 close)", "runs continuously" in place of "never reset, never rebased", shown once on the homepage (under the YTD heading) and once on Compare, with the index line-260 footnote trimmed (the line-148 sleeves-section placement is dropped); labels "2027 YTD" for the current year, bare "2026" for completed years in the short label and "2026 (full year)" as the full label; early-January near-empty charts use daily points until the first month-end or a "2027 has just started" note; the BTC chart shows past-year pills only (current year = YTD) or a year dropdown. NICE: the Max label reads "from 18 Aug 2010" (not an ISO date); recap cards say "{year} YTD"; "2026 in review" is scheduled for early January. No open question is resolved by these findings — all 8 stand (§12).
**Decisions this report implements** (Sunil, Thu 26 Nov 2026, side chat "Website future-proofing: YTD and Max"):
- No rebase in January. Sleeves run continuously from the $100k base (31 Dec 2025).
- The site acknowledges Jan 2026 as the launch date ("Launched January 2026" anchors the track record).
- Year views — 2026 YTD, 2027 YTD, etc. — plus Max (since launch). A year view is a window onto the continuous series, not a reset.
- The year view reads as the year's return ("hf is up 12% in 2027"), with the dollar value underneath still continuous from launch. Past-year views are frozen; the current year is live.

## Verdict

**Yes — the January rollover can be fully automatic, after a one-time build.** The data layer already accumulates; nothing in the pipeline restarts each January, and nothing needs to. The work is almost entirely in the presentation layer: today the label "YTD" is pasted onto numbers that are really "since launch" (31 Dec 2025), in about ten places. From the first 2027 session, every one of those numbers silently becomes wrong — not broken, wrong — unless the year is made a parameter.

Two exceptions to "fully automatic", both pre-existing and unchanged by this work:

1. **NYSE holiday sets run through 2028** — in five places (`tools/screener_daily.py`, `tools/stock_weekly.py`, `tools/recap_gen.py`, `.github/workflows/prices.yml`, `assets/js/et.js`), plus the separate CME Globex closure list in `assets/js/screener.js` (`CME_CLOSED`). A manual extension of all of them is due in late 2028, or a one-time change to derive the calendars instead of hardcoding them. See §5.
2. **The STRC dividend list is hand-maintained** (`assets/js/ledger.js`, duplicated in `assets/js/compare.js`). New dividends must be added as they are declared — monthly, as today. This is the one recurring manual step, and the list is the single most likely thing to go silently stale.

The pack is not a third exception: the pack-writing step is part of the one-time build (§4), so January stays fully automatic. The pack's `baseClose` is tile-YTD only — the daily and weekly files keep the launch base (2025-12-31), and the pack check compares the pack to the current year's base-date close (§4, MUST, revision 4).

One design rule underpins the whole build, and it is the only year rule in this report: **derive the current year from the latest session date in the data, never from the wall clock — everywhere, with no exceptions.** The current year is the year of the latest session in the data. Between 1 Jan 2027 and the first 2027 session, the current year is still 2026: the site keeps showing the completed 2026 view under a 2026 label, and no 2027 view exists yet. The 2027 view appears when the first 2027 session lands in the data, with `yearBase(2027)` = the last 2026 session. There is no "2027 YTD at 0.00%" placeholder, and no view ever flips on the wall-clock date alone. (Revision 2: the first draft said the 1 Jan 2027 view should show the 31 Dec 2026 close as its base and read 0.00% under a 2027 label — that contradicted this rule and is withdrawn. Grok Bot review, item 1.)

## The core pattern (read this first)

Every "YTD" on the site today is computed against the same fixed base, **31 Dec 2025**, and every series starts at that base. That was correct in 2026, when "since launch" and "year to date" were the same thing. The moment 2027 starts they diverge, and the code has no notion of "which year" anywhere. The fix in every part is the same shape:

- Introduce `yearBase(year)` = the last session on or before 31 Dec of (year − 1). For 2026 that is 2025-12-31; for 2027 it is the last 2026 session (31 Dec 2026).
- A year view's **return** is `value(last session in year) / value(yearBase) − 1`. Its **dollars** are the continuous NAV, never rebased.
- "Max" is the same computation with `yearBase` = the launch base (2025-12-31 for sleeves) — i.e. Max is just the year view with the year removed.
- Year pills are generated from the data (the years present in `history.json`), not hardcoded, so 2028 needs no code change.

The one place that already does this correctly is the BTC chart's line view: `assets/js/btcchart-panel.js` line 977 computes the YTD start as `(last.getUTCFullYear()-1)+'-12-31'` — derived from the data's last date, automatic every January. (The candle path is the exception — lines 625 and 631 still use the wall clock; see §3.) Everything else hardcodes 2025-12-31 or "2026".

---

## 1. Sleeves and the Portfolio Lab (Compare)

### Current state

- **Ledger (single source of sleeve truth):** `assets/js/ledger.js` (64 lines) — `window.PSLEDGER = { base: '2025-12-31', start: 100000, sleeves: {...}, rebalances: [], strc: [...] }`. The STRC dividend list is hardcoded and ends 2026-11-30.
- **History (the series):** `history.json` on the data branch — 228 closes, first 2025-12-31, last 2026-11-25, 9 symbols (BTC, BRK.B, GLD, MSTR, PLTR, QQQ, SPY, STRC, TSLA). It accumulates; nothing truncates it. The ledger engine (`assets/js/book.js`) computes every sleeve value from it on the fly — no stored NAVs, no snapshots (`book.js` line 1 comment).
- **Compare:** `assets/js/compare.js` (623 lines).
  - Line 3 (header comment): ranges are `['1W','1M','3M','6M','YTD','1Y']`, default YTD. "1Y = 12 months back; in Oct 2026 it initially matches YTD because data starts 2025-12-31, **diverging after YTD resets Jan 2027**." The comment anticipates a reset that **no code performs** — the reset is assumed, not implemented.
  - Line 358: `let pvRng='YTD'`.
  - Line 492 (`dates()`): `1W` → last 6 sessions, `1M` → last 22, `3M`/`6M`/`1Y` → months back from the last session, **YTD → `return D` — the whole series from 2025-12-31**. YTD is "everything" and only means YTD while the data starts at the year boundary.
  - Line 494: the range buttons are built from the same hardcoded 6-range list.
  - Line 547 (sleeve-candle note): "Sleeve value in USD, same basis as the line chart ($100,000 at 31 Dec 2025)".
  - Lines 351–352: `L` **duplicates** `ledger.js` (base, start, sleeves, and the STRC list as 3-element `[ex, pay, amt]` tuples, ending 2026-11-30). Any dividend added to `ledger.js` must also be added here, by hand.
  - Lines 466, 599 (calculator): start-date input defaults to 2026-01-01 with a floor `if(d<'2026-01-01')d='2026-01-01'`, `min="2026-01-01"`; `s0` maps 2026-01-01 → `L.base`.
- **Pre-computed stats:** `tools/stats.py` line 294: `ytd = (value / series[base] - 1.0) * 100.0` — the `ytd_pct` written into `stats.json` is value vs the launch base. `assets/js/stats-display.js` line 65 renders the table header "Series | YTD | {month}" and line 72 renders `s.ytd_pct`. The display does not re-derive the number; it trusts `stats.json`.

### The change

1. **Range selector** (`compare.js` lines 492, 494): replace the single `YTD` pill with explicit year pills generated from the data — `['1W','1M','3M','6M','2026','2027','1Y','Max']` once 2027 data exists (before that, `2026` only). Implementation: derive the year list from `D` (the session dates in `history.json`); `dates()` for a year pill returns sessions from `yearBase(year)` through the last session of that year (or the latest session, for the current year). `Max` returns all of `D` — i.e. today's YTD behaviour, renamed. Default pill: the current year.
2. **The return shown** for a year pill is `value / value(yearBase) − 1`; the dollar value shown is the continuous NAV. The chart note (line 547) must say which year it is: "2027 · sleeve value in USD, continuous from $100,000 at 31 Dec 2025."
3. **Calculator** (lines 466, 599): the `min="2026-01-01"` floor stays — it is a launch floor, not a year floor — but the `2026-01-01 → L.base` special case generalises to "1 Jan of any year → that year's base". No user-visible change needed beyond that.
4. **Stats** (`tools/stats.py` line 294): `ytd_pct` becomes `year_pct` — computed vs `yearBase(current year)`, plus a separate `since_launch_pct` vs the launch base. `stats-display.js` gains a "Since launch" column (or the header becomes "2027" with the year derived from `stats.json`'s `as_of`). `stats.json` already records `history_first`, `history_last`, `as_of` and `generated`, so the year can be derived from `as_of` with no new input.
5. **De-duplicate the ledger:** `compare.js` should read `ledger.js` (or a shared JSON) instead of carrying its own copy of the sleeve definitions and the STRC list. This is a correctness fix, not cosmetics — see §8.

### Rollover behaviour

- **After the one-time build: fully automatic.** Year pills appear when the first session of a new year lands in `history.json`; the current-year pill flips on its own; past-year pills are frozen because they are computed from final closes only (the live point is appended only on the current-year view).
- **What breaks if left as-is:** from the first 2027 session, the Compare chart's "YTD" keeps showing the whole series from Dec 2025 — the 2027 return is never shown, and the label is wrong from the first session of the year. The `stats.json` `ytd_pct` does the same. The line-3 comment's "diverging after YTD resets Jan 2027" never happens.

---

## 2. Homepage (tracker section)

### Current state

- `index.html` line 199: the section heading is literally **"Year to Date"**.
- `index.html` line 245–246: stat label `<span class="stat-label" id="ytdLbl">YTD</span>` and value `#stat-ytd`.
- `assets/js/s2.js` line 37: `sleeves[k].ytd = (sleeves[k].now / 100000 - 1) * 100` — the homepage "YTD" stat is now / $100k − 1. In 2027 this silently becomes the since-launch return.
- `assets/js/s2.js` line 93 (`ytdLbl()`): sets the label to "YTD", "YTD (live)" or "YTD (BTC live)".
- **Pulse / Portfolios now** (`assets/js/s6.js`): line 48 `ytdLabel()` returns "YTD", "YTD (live)" or "YTD (BTC live)"; line 159 the portfolio card sub-line shows `ytdLabel() + pct(v/START-1)`, where `START` is the $100,000 ledger start (line 4, `START=PSLEDGER.start`) — so the "YTD" number on every portfolio card is the since-launch return. Line 160: "Started with $100k on January 1st, 2026: …". Line 163 (the section note): "YTD vs $100,000 start on January 1st, 2026. Tap a portfolio for holdings."
- `assets/js/s2.js` lines 8–17 (`pathStartYear(iso)`): derives the "path year" from the ledger base — Dec base → year+1, so 2025-12-31 → 2026. This is already derived, not hardcoded, and it is correct for the *launch* year — but it is the wrong value for the *current* year once 2027 arrives.
- `assets/js/book.js` lines 117–118 (`B.points()`): chart points = base + last session of each completed month + latest close. The hero chart accumulates month-end points across years automatically — it never breaks, but it is a since-launch chart wearing a YTD label.
- `assets/js/book.js` line 114 (`B.bench()`): benchmarks indexed to 100 at the base close — same since-launch basis.
- `index.html` line 260 (note-small): already states "$100k start January 1st, 2026; values are computed from the site's own ledger and daily closes… buy-and-hold with STRC dividends reinvested on issue day."

### The change

1. **Stat** (`s2.js` line 37): the YTD stat becomes `now / value(yearBase(current year)) − 1`. The "Start" stat stays `$100,000` and "Now" stays the continuous NAV — dollars continuous, return yearly, exactly as decided.
2. **Label** (`s2.js` line 93, `index.html` line 245): the label becomes "2027 YTD" for the current year — derived from the latest session in `history.json`. A completed year is a bare "2026" in the short label, and "2026 (full year)" as the full label. The year is not labelled "2027 (live)": the "(live)" suffix is dropped from the year label. The section heading (`index.html` line 199, "Year to Date") becomes "Year to Date — 2027" or stays "Year to Date" with the year carried in the stat label; recommend the year in the heading, since the heading is the first thing read.
3. **Pulse / Portfolios now** (`s6.js` lines 48, 159, 160, 163): `ytdLabel()` becomes "2027 YTD" for the current year — derived from the latest session — with the "(live)" suffix dropped from the year label (see item 2). The card sub-line return becomes `v / value(yearBase(current year)) − 1`. The line-160 start sentence becomes the single launch phrasing (§9): "Launched January 2026 with $100,000 (priced at the 31 Dec 2025 close)". The line-163 note becomes "YTD vs the 31 Dec {prior year} close", so the $100,000 stays as the dollars basis, not the return basis.
4. **Hero chart** (`book.js` `B.points()`): take a year parameter. For the current year: year-base + month-end points within the year + latest close. For a past year: year-base + that year's month-ends. The "Performance path" lead (`index.html` line ~217: "Each sleeve from January 1st, `<span id="pathYear">`…") then shows the *selected* year, not the launch year — `pathStartYear()` must take the selected year instead of deriving it from the base. **Early January:** before the first month-end, the current-year hero line has only two points (year-base + latest close) and the vs-benchmark is near 0 — use daily points until the first month-end, or show a "2027 has just started" note, so the chart is not near-empty. The same note covers the vs-benchmark (item 5) and the tool memory (§7).
5. **Benchmarks** (`book.js` line 114): the "Vs benchmark" stat is computed over the same window as the sleeve return — i.e. re-index the benchmark to 100 at `yearBase(year)` for the year view, not at the launch base.

### Rollover behaviour

- **After the one-time build: fully automatic.** The year in the heading, the stat and the chart all follow the latest session date.
- **What breaks if left as-is:** from the first 2027 session, the homepage's headline number is the since-launch return labelled "YTD". It will read e.g. "−18%" in January 2027 — the 2026 return, shown under a YTD label, while the 2027 return has barely begun — the most visible number on the site, wrong from the first session of the new year. The portfolio cards do the same: each card's "YTD" is the since-launch return (`s6.js` line 159), under a note that says "YTD vs $100,000 start".

---

## 3. The BTC chart (live chart + popover)

### Current state

- `assets/js/btcchart-panel.js` line 770: `RANGES=['1D','1W','1M','3M','6M','YTD','1Y','5Y','10Y','Max']`.
- Line 977 (`series()`): `if(rng==='Max')st='0000'; else if(rng==='YTD')st=(last.getUTCFullYear()-1)+'-12-31'; else st=...` — **the YTD start is already computed from the current year. This is the only YTD on the site that rolls over automatically today.**
- Line 994: the range label — `rng==='Max' ? 'Max · from '+d[0][0] : rng+': BTC … · from '+d[0][0]`.
- Lines 611–631: YTD/1Y need extended daily candles (CBEXT); the `need` for YTD is computed from the wall-clock year (lines 625, 631) — see the change below.
- Line 93: `CANDLE_RANGES=['1W','1M','3M','6M','YTD','1Y']` — no 5Y/10Y/Max candles, by design (drawing-fixes Job 7: no trendlines for 5Y/10Y/Max; TA2's floor + 200W MA cover those views).
- Line 88 (`defaultGran`): 1W→4h, 3M/6M/YTD/1Y→weekly, else daily.
- Data: `assets/data/btc-daily.json` — **5,944 rows, first 2010-08-18 ($0.07), last 2026-11-25 ($60,378.20)**. Source note: "2010-08-18..2014-09-16 blockchain.info market-price (daily avg); 2014-09-17 onward Yahoo Finance BTC-USD daily close (UTC day)". Extended at runtime with data-branch `history.json` + Coinbase daily candles (`assets/js/btcchart.js`, 146 lines; panel pin wr3).

### The change — and a correction to the design doc

1. **The design doc says "BTC chart Max starts ~2015". The data says 2010.** The line view's Max starts **18 Aug 2010** (`btc-daily.json`). The "~2015" figure is the start of the *Coinbase daily-candle* history — which matters only if a Max candle view is ever added, and no Max candle view exists (CANDLE_RANGES excludes Max by design). The report recommends correcting the design doc: **BTC line Max = Aug 2010; sleeves Max = Dec 2025.** The pages must state that distinction wherever both Maxes appear (see §9). The Max label itself reads "Max · from 18 Aug 2010" — a human-readable date, not the ISO "2010-08-18" (line 994's `d[0][0]` is an ISO date and must be formatted).
2. **Year pills:** add year ranges to `RANGES` (line 770), generated from the data — but year pills crowd mobile, so show **past-year pills only**: the current year is the existing YTD pill (no separate "2027" pill), and past years get their own pills (e.g. "2026" once 2027 data exists); or use a year dropdown instead of pills. A year pill is YTD-with-a-year: `st=(year-1)+'-12-31'`, same as line 977's YTD branch but with the selected year instead of the current one. `defaultGran` treats a year pill like YTD (weekly). The CBEXT extension (lines 611–631) must use the selected year, not the current year, for past-year views.
3. **YTD line view needs no change; the candle view does.** The line view (line 977) already means "current calendar year" and flips automatically. The candle path does not: lines 625 and 631 compute the YTD window from the wall clock — `need` from `Date.now()` and `new Date().getUTCFullYear()`, `cut` from `Date.UTC(new Date().getUTCFullYear(),0,1)`. The two views disagree from the first 2027 session: the candle path computes its YTD window from the wall-clock year, so before that first session lands it shows a near-empty window starting 1 Jan 2027 while the line view still shows 2026. Fix: derive both from the series' last date (the same `last` line 977 uses) — `need` = days from 1 Jan of the last-data year to the last date, `cut` = 1 Jan of the last-data year. Until that change, **do not call the BTC chart the reference implementation**: the line view is the pattern to copy, the candle path is the outstanding fix. (Grok Bot review, item 2.)

### Rollover behaviour

- **Line-view YTD and Max: already fully automatic. Candle-view YTD: not yet** — automatic once lines 625/631 are fixed. **Year pills: one-time build, then automatic** (pills generated from the years present in `btc-daily.json`).
- **What breaks if left as-is:** the line view is fine, but the candle view's YTD is wall-clock-based and wrong at the turn of the year (see above). The other gap is the missing past-year view (no way to see 2026 YTD once 2027 starts) and the "~2015" misstatement in the design doc.

---

## 4. The Desk

The Desk has four separate YTD surfaces, all hardcoded to 31 Dec 2025. They need the same treatment, but the Desk is a live-trading surface — the recommendation is **current-year only, with the year in the label**, not a year switcher on every tile.

### Current state

- **Tiles** — `assets/js/screener.js` line 221: `r.ytdPct = (q.c / r.baseClose - 1) * 100` — the tile YTD is the live quote vs `baseClose` from `assets/data/screener-pack.json`. The pack carries per-symbol `baseClose` (e.g. TSLA 449.72 — the 31 Dec 2025 close) and a pre-computed `ytdPct`. `screener.js` lines 367–374 render the label: `r.ytdBasis === 'listing'` → "Since listing" + row-note "Since listing 12 Jun 2026", otherwise "YTD".
  - **The pack is hand-maintained, and no tool writes it.** `tools/stock_weekly.py` does not write `screener-pack.json` — it only reads it (`load_pack`) and checks each weekly file's `baseClose` against the pack, aborting if they disagree by more than $0.01. `tools/cmp_daily.py` likewise only reads the pack (same check). No tool, workflow or script in the repo writes the pack; its rows are edited by hand. (Grok Bot review, item 5 — the first draft said `stock_weekly.py` writes the pack. It does not.)
  - **`ytdBasis` is never set.** Verified in this pass: no row in the pack carries a `ytdBasis` key (rows carry `baseClose`, `price`, `prevClose`, `dayChange`, `ytdPct`, `name`, `symbol`), and no code anywhere assigns it. The three readers already handle it — `screener.js` (tile label + row-note), `screener-chart.js` (comparison), `screener-indicator-chart.js` (modal label) — so the "Since listing" branch exists but never fires. The live SPCX tiles therefore cannot show "Since listing" today. (Grok Bot review, item 6.)
- **Desk comparison chart** — `assets/js/screener-chart.js` (v=cmp14): line 20 `var YTD_BASE = '2025-12-31';`, line 21 `var LISTING = '2026-06-12';`, lines 54–58 (`commonTarget`): `range === 'ytd'` → `YTD_BASE`; `1M`/`3M`/`6M` → months back; anything else defaults to `YTD_BASE`. Line 130: default `range = 'ytd'`. Chips in `screener.html` lines 296 (`data-cmp-range="ytd"`, default on) and 323 (`data-cmp-metric="ytd"`).
  - **Comparison notes** (`assets/js/screener-chart.js` lines 985, 992): the note "YTD vs 31 Dec 2025. SPCX is since 12 Jun 2026, not YTD…" and the SPCX-off-view note "SPCX is off this YTD view (since 12 Jun 2026, not 31 Dec 2025)…" both hardcode the 2025 base and must become year-derived. (Grok Bot review, item 7.)
- **Indicator modal** — `assets/js/screener-indicator-chart.js` lines 28–29 (header comment): the "+" button opens "SYMBOL — YTD weekly candles"; weekly candles, UTC Monday–Sunday weeks, **YTD only**. Lines 76–150 hardcode the modal titles ("Gold — YTD weekly candles", "WTI — YTD weekly candles", etc.). The modal draws from the shipped weekly files (`assets/data/stock-weekly-<SYM>.json`, `wti-weekly.json`, etc.).
- **Copy** — `screener.html` line 262 ("About YTD" details): "YTD is vs the 31 Dec 2025 close, except SPCX (since listing 12 Jun 2026). Tap a card for weekly candles." Line 273: sort button "YTD ↕". Line 340: modal aria-label "Indicator YTD weekly candle chart". Line 255: "Tap a tile for its YTD weekly candle chart."
- **Weekly files** — built by `tools/stock_weekly.py`. SPECS (lines 57–75): every YTD name has `base_session: '2025-12-31'`, `first_session: '2026-01-02'`, `base_label: '31 Dec close'`; SPCX is `basis: 'listing'`, base 2026-06-12. Lines 250–258: the file's header note is hardcoded — YTD names get `'Weekly candles, UTC Monday-Sunday weeks, YTD 2026. First week is partial: 1 trading day (2 Jan 2026), week starting Mon 29 Dec 2025. The 31 Dec 2025 close is the baseline, not a candle.'` The weekly files are refreshed by `.github/workflows/desk-intraday.yml` (after-close final run commits them to main).
  - **"YTD 2026" notes** (`tools/indicator_weekly.py` docstring: "Weeks are UTC Monday-Sunday, YTD 2026…", and the shipped weekly files' `note` field: "Weekly candles, UTC Monday-Sunday weeks, YTD 2026. First week is partial: 1 trading day (2 Jan 2026)…") — the year is hardcoded in the generator and in every shipped file, and must become year-derived with `stock_weekly.py`. (Grok Bot review, item 7.)

### The change

1. **Tiles + pack-writing step (part of the one-time build):** the pack's `baseClose` becomes the prior-year-end close for the *current* year, and `ytdPct` is recomputed against it — by a new pack-writing step in the build (e.g. in `cmp_daily.py`, which already loads the pack and knows every base close from the daily closes), not by hand. **The pack's `baseClose` is used only for the tile YTD. The daily files (`cmp-daily.json`) and the weekly files keep the launch base (2025-12-31) — their `baseClose` / `base_session` do not move with the pack.** The pack is hand-maintained today, and the writing step is what makes January fully automatic: without it, the January update would be a hand-edit of one row per symbol (`baseClose` → the last close of the prior year, `ytdPct` → recomputed). The tile label becomes "2027 YTD". SPCX keeps "Since listing" in 2026 — but only once `ytdBasis` is set (see below); from the first 2027 session it uses the Dec 31, 2026 base and the normal YTD label. **Roll timing:** the pack writer rolls `baseClose` to the new year only after the Dec 31 close is a completed, final session — that is, on the first 2027 run — never from a provisional Dec 31 value. **Pack-writer checks:** the writer checks that every number is finite and sensible before writing, and writes the file atomically (temp file + rename), so a crash cannot leave a half-written pack. **The pack check (MUST):** the check in `cmp_daily.py` (lines 148–152 and 262–266) and `stock_weekly.py` (lines 217–221) that stops with "not writing" when the pack disagrees by more than $0.01 must compare the pack's `baseClose` against the **current year's base-date close** (the last close of the prior year, from the daily closes) — not against the launch close. As written in revision 3, §4 moved the pack's `baseClose` while §5 kept the launch base, so the first 2027 pack write would stop both the daily and weekly jobs; this is the MUST the full review caught, and the split above (launch base in the files, year base in the pack, check against the year base) is the fix.
2. **`ytdBasis` — set it in the pack.** The build must set `"ytdBasis": "listing"` on the SPCX pack row (and `"ytdBasis": "ytd"` on the others, or leave them unset) when the pack is written or edited for the new year. The listing date in the row-note ("Since listing 12 Jun 2026", `screener.js`) stays fixed — it is a listing fact, not a year fact. Once the key is set, the tile, comparison and modal labels all show "Since listing" correctly with no further code change, because all three already read the key. **The listing basis applies to 2026 only.** From the first 2027 session, SPCX uses the Dec 31, 2026 base and the normal YTD label — the pack writer switches its `ytdBasis` from `"listing"` to `"ytd"` (and its `baseClose` to the Dec 31, 2026 close) on the first 2027 run, once the Dec 31 close is final (same roll timing as item 1).
3. **Desk comparison chart:** `YTD_BASE` (line 20) becomes `yearBase(current year)`; the chip label shows the year. No new ranges needed on the Desk. The comparison notes (lines 985, 992) become year-derived too ("YTD vs 31 Dec {prior year}…").
4. **Modal:** the weekly files accumulate weeks from the Jan 2026 start, so the modal must **slice to the selected year** (default current) instead of drawing the whole file — otherwise in 2027 the "YTD weekly candles" modal shows 2026 + 2027 weeks. The modal title becomes "Gold — 2027 weekly candles" (year derived from the data). The weekly file's header note (`stock_weekly.py` line 255) must become year-derived: "YTD {year}" with the first-week sentence computed from that year's first session, not hardcoded to 2 Jan 2026 / 29 Dec 2025.
5. **Copy:** `screener.html` line 262 becomes "YTD is vs the 31 Dec {prior year} close, except SPCX (since listing 12 Jun 2026)" — year derived at build/publish time, or reworded to avoid the year entirely: "YTD is vs the last close of the previous year".

### Rollover behaviour

- **After the one-time build: fully automatic** (base close via the new pack-writing step, modal slice and note all follow the current year).
- **What breaks if left as-is:** the Desk tiles show since-launch returns labelled YTD from the first 2027 session; the modal's "YTD weekly candles" grows to two years of candles under a YTD title; the weekly file's note still says "YTD 2026" while containing 2027 weeks. None of these fail loudly — all four are silent mislabels on the page Sunil watches most.

---

## 5. The data pipeline (daily files, weekly files, workflows)

### Current state — the good news first

**The daily files already accumulate. Nothing restarts in January.** Verified:

- `tools/screener_daily.py`: `fetch_yahoo` uses a **fixed** period1 of 2025-12-20; the STOCKS/INDICATORS maps (lines 118–143) fix `basis: 'ytd'`, `first: '2026-01-02'` (SPCX: `'listing'`, `'2026-06-12'`). The file is regenerated wholesale from that fixed start each run, so it grows session by session. The `expected_sessions(first, last)` check grows with it.
- `tools/cmp_daily.py`: lines 10–11 (docstring) — "YTD names keep the 31 Dec 2025 close as baseClose and start the series on the next session." SPECS (lines 30–51): `basis: 'ytd'`, `base: '2025-12-31'`, `first: '2026-01-02'` for every name except SPCX. `fetch_yahoo` uses period1 = base − 5 days — again a fixed start, so `cmp-daily.json` (asOf 2026-11-25) accumulates.
- `tools/stock_weekly.py`: SPECS fix `base_session: '2025-12-31'`, `first_session: '2026-01-02'`; the weekly files grow week by week.
- `history.json` (data branch): 228 closes, 2025-12-31 → 2026-11-25 — accumulates by construction; the ledger engine reads it whole.
- `.github/workflows/prices.yml` recap job: runs only when the fetch job reports a final close (`if: … needs.fetch.outputs.final_close == '1'`, line 781). It runs `recap_gen.py` (line 804), `screener_daily.py` (lines 828–839, `--weekly-dir assets/data`), `cmp_daily.py` (lines 878–896, `--weekly-dir assets/data`), then commits `stock-daily-*.json`, `ind-daily-*.json`, `cmp-daily.json` (line 912). The publish step's glob `recap/20*/index.html` (line 808) picks up any new `recap/YYYY-MM/` page automatically — and would pick up a `recap/YYYY/` year page too, since `2026` matches `20*`.

### What has to change

1. **Nothing in the pipeline needs to restart or truncate.** The design doc's "Desk/comparison daily files must accumulate instead of restarting each January (history.json already does)" is already satisfied by the tools as written — the files never restart. The change is to stop calling the series "YTD" in the *labels and bases* (§1, §4), not to change the fetch windows.
2. **Rename the concept in the tools:** `basis: 'ytd'` in the three SPECS maps is now a misnomer — the basis is "since launch". Recommend renaming to `basis: 'launch'` (or keeping the key and adding a `year` parameter to the tools) so a future reader doesn't assume the series is year-scoped. The `baseClose` / `base_session` values stay 2025-12-31 — they are the launch base, and Max needs them. This is the other half of the MUST (§4): the daily and weekly files keep the launch base, so their `baseClose` / `base_session` never move — only the pack's `baseClose` rolls, and only for the tile YTD. The `cmp_daily.py` / `stock_weekly.py` pack check must therefore compare the pack against the current year's base-date close, not the launch close (see §4 item 1).
3. **Holidays — the one pipeline item with a real expiry date.** The NYSE holiday sets are hardcoded and run through 2028 in **five** places, not three: `tools/screener_daily.py` lines 95–106 (`HOLIDAYS`, plus a separate `IND_HOLIDAYS` for indicators), `tools/stock_weekly.py` (same set, shared via `sw.HOLIDAYS`), `tools/recap_gen.py` lines 22–24 (`HOL`), `.github/workflows/prices.yml` (`NYSE_HOLIDAYS`), and `assets/js/et.js` (`HOL`, plus the early-close list `EARLY`). There is also a **separate** CME Globex full-closure list, `assets/js/screener.js` (`CME_CLOSED`, 2026–2028) — futures closures, not NYSE holidays, used only for the Desk live/freshness rule. The comment in `screener_daily.py` lines 104–106 already warns: "(2026-2028): a local copy here would go stale in 2027, and a null close on a 2027 indicator holiday would fail the daily build instead of being skipped." (That comment is about the *shared* set; the local set itself runs to 2028.) **Action: extend all six lists to 2029+ in late 2028 — including `et.js` EARLY (early closes), which is part of the et.js list — or — better, one-time — derive the NYSE calendar from a source instead of hand-maintaining it.** `tests/test_et.js` already keeps the three NYSE lists in `prices.yml`, `recap_gen.py` and `et.js` in sync (see §10) — but it does not cover the `screener_daily.py`/`stock_weekly.py` shared set or `CME_CLOSED`, so the late-2028 extension checklist must include those, and EARLY, by hand. Note: `test_et.js` line 31 still says the lists end in 2027 — stale, they run through 2028; fix the comment. If the pipeline sets expire unnoticed, the failure mode is a hard build failure on a 2029 holiday (null close refused), not a silent mislabel — it fails loud, which is the safer direction. The client-side lists are different: `et.js` HOL/EARLY and `screener.js` CME_CLOSED are not read by any build, so their expiry fails nothing — they just mislabel live/open (a holiday reads as a session, an early close reads as a full close) until they are extended. (Grok Bot review, item 4; revision 3.)

### Rollover behaviour

- **January 2027: fully automatic, no workflow change.** The recap job, the daily-file jobs and the weekly refresh all run exactly as they do today; the files keep growing.
- **Late 2028: one manual step** (extend the holiday sets) unless the calendar is derived instead.

---

## 6. Recaps (monthly pages + the yearly summary)

### Current state

- `tools/recap_gen.py` (198 lines) refreshes only the current month's page (`recap/YYYY-MM/index.html`) from `history.json` final closes; completed months are never rewritten (docstring lines 8–9 — the one exception is the previous page's nav link when a new month starts).
- Line 25: `BASE = '2025-12-31'` — hardcoded. (`recap_lib.py`'s `BASE_DATE = '2025-12-31'` is a different thing — the funding base that prices the $100,000 launch allocation — and stays as-is; do not year-derive it.)
- Line 140 (the page note): `YTD = Dec 31, 2025 → {nice(ME)} close.` — hardcoded year in the note.
- Months.js card: `yy = pc(VAL[k][BASE], VAL[k][ME])` — the `y` field in each month's `sl` entry is the return vs the launch base. In `recap/months.js` today, e.g. November 2026: `y:-16.17` for Berkshire Killer = since 31 Dec 2025.
- Line 149/176: the prev-month nav link uses `{full} {y}` — the year is already dynamic there.
- `sitemap.xml`: recap entries 2026-01 → 2026-11; `sitemap_update()` (lines 60–75) inserts a new month URL automatically.
- **No yearly summary exists.** There is no `recap/YYYY/` page, no year aggregation in `recap_gen.py`, and no "2026 in review" anywhere.

### The change

1. **Year-derived base:** replace `BASE` with `yearBase(m)` where `m` is the month being recapped — the last session on or before 31 Dec of (year − 1). The note (line 140) becomes `YTD = Dec 31, {year-1} → {nice(ME)} close.` The months.js `y` becomes the year's return. Past-year months are frozen (never rewritten), so a January 2027 recap page correctly shows "YTD = Dec 31, 2026 → Jan 2027 close" while the December 2026 page keeps "Dec 31, 2025 → Dec 2026 close" — each month's YTD is its own year's. The recap cards say "{year} YTD" (e.g. "2026 YTD" for 2026 months, "2027 YTD" for 2027 months) — the `y` field's label carries its year. Early January: the January card's return is near 0 with only a few sessions — the "2027 has just started" note (§2) applies here too.
2. **Yearly summary ("2026 in review") — new page, follow-on (not part of the one-time build).** When December finalizes, generate `recap/2026/index.html` (proposed URL; see open questions): the year's return per sleeve and for BTC, best/worst months, the year's high/low closes, STRC dividends paid in the year, and the year-end dollar values. It is a thin wrapper over data `recap_gen.py` already computes — the month loop already has `VAL[k][ME]` for every month-end; the year page is the December page's numbers plus the twelve month cards. Add a year entry to `recap/months.js` (or a separate `RECAP_YEARS` list) and to `sitemap.xml` — `sitemap_update()` already inserts new URLs, and the prices.yml publish glob `recap/20*/index.html` picks the year page up automatically. "2026 in review" is scheduled for early January (after December finalizes).
3. **Archive page** (`recap/index.html`) — follow-on, with the yearly summary: group the month list by year once a second year exists, with the year page linked at the top of its year's group.

### Rollover behaviour

- **After the one-time build: fully automatic for the monthly pages.** Each month's YTD follows its own year. The year page is **not** part of the one-time build — it is a follow-on (§6 item 2, §11 table) — so it appears when December finalizes only once the follow-on is built; the sitemap and archive update themselves when it does.
- **What breaks if left as-is:** from the January 2027 page onward, every new recap page's note still says "YTD = Dec 31, 2025 → …" and its months.js `y` is the since-launch return, mislabelled as the year's. The December 2026 page would be the last correct one.

---

## 7. The mockup tools (fear gauge, washout metre, risk meter, rebalance rule)

None of these is live; all four are mockups. The year parameter belongs in them **when they are built live**, not before — but the design must be settled now, because one of them has a trap.

### Current windows (from the handbacks)

- **Fear gauge** (`~/workspace/ps-fear-gauge/HANDBACK.md`): RSI and MAs "computed from the site's 2026 YTD daily closes (226 sessions). The 200-day MA as of Nov 25 uses closes back to ~Feb 2026, inside the window." Memory chart: 125 days (Jun 1 – Nov 25, 2026). Washout definition: close recovered ≥4% from the day's low **and the low was a new 30-day intraday low**; 38 such days in BTC history 2021–2026.
- **Sleeve washout metre** (`~/workspace/ps-sleeve-washout-metre/HANDBACK.md`): flags a washout "in the last 5 days"; trendline analysis uses ≥3 pivot points over ≥2 calendar months.
- **Risk markets meter** (`~/workspace/ps-risk-markets-meter/HANDBACK.md`): leadership is "two days running"; breadth is names above their 50-day MA; washouts use the same 30-day-low definition.
- **Sleeve rebalance rule** (parked, not building — Sunil, Wed 25 Nov): monthly ranking on 1-month returns; the multi-year backtest ran 2021–2026.

### The change — and the trap

- **Display window = year parameter.** Each tool takes `year` (default current) and its history charts, memory charts and track-record tables scope to that year.
- **Indicator windows are trailing, not year-scoped — and must stay that way.** RSI-14 needs 14 sessions, the 50-day MA needs 50, the 200-day MA needs ~200. A "2027 YTD" gauge computed from 2027 sessions alone has no 200-day MA until October 2027. **The tool must compute indicators from the trailing Max series and display the year window.** This is the trap: naïvely scoping the gauge's data fetch to the year breaks the 200-day MA for most of the year. The fear gauge handback already shows the edge — the 200-day MA "uses closes back to ~Feb 2026, inside the window" — inside the 2026 window only because 2026 had 226 sessions by November. In January 2027 the same construction has ~0 sessions.
- **Trailing definitions stay trailing.** The 30-day intraday low (washouts), the last-5-days flag, "two days running" leadership and the 50-day breadth are trailing windows that cross year boundaries by nature; they do not become year-scoped. Only the *displayed history* (memory chart, year table) takes the year parameter.
- **Rebalance rule (if ever revived):** the monthly ranking is unchanged; the *track record display* takes the year parameter. The multi-year backtest already runs across years — no change needed there.

### Rollover behaviour

- **One-time build (when each tool goes live), then automatic.** No yearly manual step.

---

## 8. The STRC dividend list (the recurring manual step)

- `assets/js/ledger.js`: the STRC list is 4-element `[record, ex, pay, dps]` tuples, ending 2026-11-30 (daily $0.0333… rows through November).
- `assets/js/compare.js` lines 351–352: the **same list duplicated** as 3-element `[ex, pay, amt]` tuples, also ending 2026-11-30.
- `tools/recap_gen.py` reads `ledger.js` by regex (with a fallback to the recap page's own embedded ledger constants) — a third copy of the same data, in the page source.
- `assets/js/book.js` line 39: `B.ev = L.strc.filter(e => e[1] > L.base)` — events after the base; new dividends flow into sleeve NAVs only if they are in the list.

**Change:** single-source the list. `compare.js` should import `ledger.js` (or both should read one shared JSON) instead of carrying a duplicate that drifts. Longer term, generate the list from the declared monthly total (e.g. $1.00/share for November → daily rows) rather than hand-writing ~30 rows a month — the November daily pattern is already ~30 rows for one month, and at that rate the list is ~360 rows a year.

**Never pre-fill undeclared months.** The generator and the checklist never add a month before its dividend is declared. Once a dividend is declared, add one lump per record day at the declared rate, with the pay date rolled to the next NY Fed business day. Never spread a declared total across days, and never backfill a month that was skipped.

**Rollover behaviour: monthly manual step, as today.** If a month's dividends are not added, sleeve NAVs understate by the missing dividend amount — silently, because the ledger just has no event. This is the one place where "the site goes stale" is a real, recurring risk, and it is not a January problem: it is every month. Flag it in the year-end checklist (§11).

---

## 9. Launch-date acknowledgement (copy + placement)

The site already states the start in one place: `index.html` line 260 (note-small) — "$100k start January 1st, 2026…". The decision is to make the launch an explicit anchor, not a footnote. The single phrasing, used everywhere it appears:

> **Launched January 2026 with $100,000 (priced at the 31 Dec 2025 close). Sleeves run continuously.**

"Runs continuously" replaces "never reset, never rebased" in the launch copy. Placement (two places — one line each, where the numbers are read):

1. **`index.html`, under the "Year to Date" heading (line 199)** — a `<p class="section-lead">` directly under the `<h2>`, so the first thing under the headline number is the anchor. This is the primary placement.
2. **`compare/index.html`, above the range pills (`#pvRange`)** — one line, so the year pills have their context: the years are windows onto a continuous series that started in January 2026.

(The revision-3 draft also placed it in the sleeves-section lead, `index.html` line 148 — dropped in revision 4: the review says show it once on the homepage and once on Compare.) The footnote at `index.html` line 260 is trimmed to the computation note only — the launch fact moves to the anchor under the heading, so the footnote no longer repeats the $100k start.

Also state the Max distinction wherever both Maxes appear (Compare chart note, BTC chart label): **"Sleeves Max starts 31 Dec 2025; the Bitcoin chart's Max starts 18 Aug 2010."** The BTC chart's Max label (`btcchart-panel.js` line 994) reads "Max · from 18 Aug 2010" (human date, not ISO — §3) — the sleeves side needs the equivalent line.

---

## 10. Tests that pin YTD behaviour (must move with the build)

- `tests/test_stats.py` lines 115, 196, 202–203, 322: pin `ytd_pct` values (e.g. "ytd +9.08%") and the series keys (`"ytd_pct"` in the required key list) — they must move with the `stats.py` change (§1 item 4) to the year return + since-launch column.
- `tests/test_stats_display.js` line 40: renders each series' `ytd_pct` into the table and checks it appears — must follow the display change.
- `tests/test_et.js`: keeps the three NYSE holiday lists in sync — it reads `NYSE_HOLIDAYS` from `prices.yml`, `HOL` from `recap_gen.py` and `HOL` from `et.js` and asserts all three agree, and has an expiry guard that fails 60 days before the last listed year ends. Cited in §5. Its line-31 comment still says the lists end in 2027 — stale (they run through 2028); fix the comment. It does not cover the `screener_daily.py`/`stock_weekly.py` shared set or `CME_CLOSED`.
- `tests/test_recap.py` line 58: checks the months.js card `y` against `pc(VAL[k]['2025-12-31'], VAL[k][ME])` — the test hardcodes the 2025-12-31 base for the months.js "y" check. It must become year-derived with `recap_gen.py`. (Full review SHOULD 7 — already listed in revision 3; confirmed.)
- **Simulated Jan 2, 2027 run (regression test for the MUST, §4):** a test that runs `cmp_daily.py` and `stock_weekly.py` against a rolled pack (pack `baseClose` at the Dec 31, 2026 close, daily/weekly files on the launch base) as of Jan 2, 2027 — both must complete without stopping with "not writing", and the tile YTD must come out against the year base. Without this test, the §4 conflict would stop both jobs on the first 2027 pack write and nothing would catch it until then.
- `tests/test_desk_intraday.py` lines 47, 247, 614, 675: assert the weekly-file note text "Weekly candles, UTC Monday-Sunday weeks, YTD 2026. First week is partial: 1 trading day…" — these pin the hardcoded note and must become year-derived with `stock_weekly.py`.
- `tests/headless_matrix.py` lines 23–29, 57–59: assert on `#ytdLbl` text ("YTD (LIVE)") — must follow the label change in `s2.js`/`index.html`.
- `tests/run_all.sh` matched-pair baselines: the current failing sets were measured with YTD = since launch; re-measure the baseline after the build (the build changes labels and numbers, so a fresh matched pair is required — do not reuse the old failing-set counts as a pass/fail gate).

---

## 11. Summary table — automatic vs manual

| Part | File(s) | One-time build | After that | If left as-is |
|---|---|---|---|---|
| Compare range selector | `assets/js/compare.js` lines 492, 494 | Year pills from data; `dates()` year-scoped; return vs `yearBase(year)`, labelled "2027 YTD" (completed year "2026 (full year)") | Fully automatic | "YTD" shows the whole series forever; 2027 return never shown |
| Compare stats | `tools/stats.py` line 294; `assets/js/stats-display.js` | `ytd_pct` → year return + since-launch column | Fully automatic | `ytd_pct` becomes since-launch, mislabelled |
| Homepage stat + chart | `assets/js/s2.js` lines 37, 93; `assets/js/s6.js` lines 48, 159, 160, 163; `assets/js/book.js` lines 114, 117–118; `index.html` lines 199, 245 | Year-derived stat, label ("2027 YTD"; completed year bare "2026" short / "2026 (full year)" full), chart points, benchmark re-index; `s6.js` label + card return year-derived, note reworded; early January uses daily points or a "2027 has just started" note | Fully automatic | Headline number is since-launch labelled YTD from the first 2027 session |
| BTC chart YTD/Max (line view) | `assets/js/btcchart-panel.js` line 977 | None needed; Max label "Max · from 18 Aug 2010" (human date, not ISO) | Already automatic | Nothing breaks; no past-year view |
| BTC chart YTD (candle view) | `assets/js/btcchart-panel.js` lines 625, 631 | Derive `need`/`cut` from the series' last date, not the wall clock | Automatic once fixed | Candle YTD wrong at the turn of the year; not the reference implementation until fixed |
| BTC chart year pills | `assets/js/btcchart-panel.js` lines 770, 88, 93, 611–631 | Past-year pills only (current year = YTD), or a year dropdown; CBEXT uses selected year | Fully automatic | No 2026 view once 2027 starts |
| Desk tiles | `assets/js/screener.js` line 221; pack hand-maintained today (no tool writes it) | Pack-writing step in `cmp_daily.py` (part of the one-time build): pack `baseClose` + `ytdPct` derived each run, tile-YTD only; daily/weekly files keep the launch base; pack check compares the pack to the current year's base-date close; roll only after the Dec 31 close is final (first 2027 run); writer checks numbers finite/sensible and writes atomically; label "2027 YTD" | Fully automatic | Tiles show since-launch labelled YTD; the first 2027 pack write stops both jobs (MUST) |
| Desk tiles: `ytdBasis` | `assets/data/screener-pack.json` | Set `"ytdBasis": "listing"` on the SPCX row for 2026; from the first 2027 session switch SPCX to the Dec 31, 2026 base and the normal YTD label (roll only after the Dec 31 close is final) | Automatic once set | SPCX tiles never show "Since listing"; SPCX stays on its listing base into 2027 |
| Desk comparison chart | `assets/js/screener-chart.js` lines 20, 54–58, 130; notes lines 985, 992 | `YTD_BASE` → `yearBase(current year)`; notes year-derived | Fully automatic | Comparison anchored to Dec 2025 forever |
| Desk modal | `assets/js/screener-indicator-chart.js` lines 28–29, 76–150 | Slice weekly file to selected year; title shows year | Fully automatic | Modal grows to multi-year candles under a YTD title |
| Weekly file note | `tools/stock_weekly.py` lines 250–258; `tools/indicator_weekly.py` | Note year-derived | Fully automatic | Note says "YTD 2026" while holding 2027 weeks |
| Daily files (stock/ind/cmp) | `tools/screener_daily.py`, `tools/cmp_daily.py` | Rename `basis: 'ytd'` → `'launch'` (label hygiene); files keep the launch base — the pack check compares the pack to the current year's base-date close (§4, MUST) | Already automatic — files accumulate | Files are fine; only the label is wrong |
| Pipeline / workflows | `.github/workflows/prices.yml`, `desk-intraday.yml` | No change | Fully automatic | Nothing breaks |
| Recaps (monthly) | `tools/recap_gen.py` lines 25, 140; months.js `y` | `BASE` → `yearBase(month)`; note + `y` year-derived; cards say "{year} YTD" | Fully automatic | Every 2027 page's YTD is since-launch, mislabelled |
| Recaps (yearly summary) | `tools/recap_gen.py` (new) | New `recap/YYYY/` page on December finalization; "2026 in review" scheduled for early January | **Follow-on, not part of the one-time build** | No "2026 in review" exists |
| Mockup tools (4) | Handbacks (§7) | Year parameter on display; indicators stay trailing | Fully automatic once built live | N/A (not live) |
| Launch-date copy | `index.html` lines 199, 260; `compare/index.html` | One phrasing everywhere — "Launched January 2026 with $100,000 (priced at the 31 Dec 2025 close). Sleeves run continuously." — once on the homepage (under the YTD heading), once on Compare; footnote at index line 260 trimmed (§9) | Static — no rollover | Launch date stays a footnote |
| **NYSE holidays (+ CME)** | `tools/screener_daily.py` lines 95–106; `tools/stock_weekly.py`; `tools/recap_gen.py` lines 22–24; `.github/workflows/prices.yml`; `assets/js/et.js` (incl. EARLY); `assets/js/screener.js` (`CME_CLOSED`) | Extend all six lists to 2029+ (incl. `et.js` EARLY) **or** derive the calendars (one-time); `test_et.js` keeps three in sync | **Manual in late 2028** if not derived | Pipeline lists: hard build failure on a 2029 holiday (fails loud). Client-side lists (`et.js`, `CME_CLOSED`): no build failure, just mislabelled live/open |
| **STRC dividend list** | `assets/js/ledger.js`; `assets/js/compare.js` lines 351–352 | Single-source the list (de-duplicate); never pre-fill undeclared months — one lump per record day once declared, pay date rolled to the next NY Fed business day, never spread or backfill | **Manual monthly** — add dividends as declared | Sleeve NAVs silently understate by missing dividends |
| Tests | `tests/test_recap.py`, `tests/test_desk_intraday.py`, `tests/headless_matrix.py`, `tests/test_stats.py`, `tests/test_stats_display.js`, `tests/test_et.js` | Update to year-derived expectations; fix the stale `test_et.js` line-31 comment; add simulated Jan 2, 2027 run (cmp_daily.py + stock_weekly.py vs rolled pack); test_recap.py line 58 year-derived | Automatic thereafter | Tests pin the old (wrong) behaviour |

---

## 12. Open questions (real choices the code leaves)

1. **Does the homepage keep a "since launch" number anywhere?** The design says the year view reads as the year's return with dollars continuous. The homepage today shows Start $100,000 / Now / YTD / Vs benchmark. Under the new design the YTD stat becomes the year's return — should a "Since launch" return also be shown (e.g. as a second stat, or on the Compare page only)? Recommend: keep it on Compare (Max view) and keep the homepage year-only, so the headline number is never ambiguous — but this is Sunil's call.
2. **Does 1Y stay trailing-12-months on Compare?** Today 1Y = 12 months back, distinct from YTD. With explicit year pills, 1Y's meaning is unchanged — but confirm it stays, rather than becoming "last calendar year".
3. **Where do past-year views live — a pill on the same page, or a deep-linkable URL?** Recommend pills that update the URL (`/compare/?year=2026` or `#2026`) so a past-year view can be shared and linked. The BTC chart's range pills are in-page state today; decide whether year views need linkability.
4. **Desk: current-year only, or a year switcher?** Recommend current-year only with the year in the label — the Desk is a live surface, and a year switcher on every tile is clutter. The modal could still offer a year choice.
5. **Yearly recap URL:** `recap/2026/` or `recap/2026-in-review/`? Recommend `recap/2026/` — it matches the `recap/YYYY-MM/` pattern, the prices.yml publish glob picks it up automatically, and it sorts naturally in the archive. Confirm it appears as a card in `recap/months.js` (or a separate year list) and in the sitemap.
6. **STRC dividends: hand-maintain or generate?** The list grows ~30 rows/month at the current daily pattern. Recommend generating it from the declared monthly total in a one-time change; until then, it is a monthly manual step that must be on a checklist.
7. **BTC Max start — confirmed 2010, not 2015.** The data (`btc-daily.json`) starts 18 Aug 2010; the design doc says ~2015 (the Coinbase candle start). Confirmed by Grok Bot's review: state "Max · from 18 Aug 2010" on the chart, and correct the design doc.
8. **Year pills generated from data, or hardcoded?** Recommend generated from the years present in `history.json` / `btc-daily.json` — then 2028 needs no code change. The alternative (hardcoding 2026/2027) creates a yearly manual step for no benefit.

---

## 13. What happens next (per Sunil, Thu 26 Nov)

Revision 3 went to **Grok Bot for review** (passed ~15:23, Thu 26 Nov); **Chief took it and organized the full-scale review** — the handover and focused look ran in this order: **Site Launch, then PaperStreet Portfolio Bot, then back to Chief, then back to Grok Bot**, and the full review landed Thu 26 Nov ~17:19 (1 MUST, 10 SHOULD, 3 NICE), folded into revision 4 here. Sunil's name for the follow-up: **"future proof review mania of the century"** — the full-scale audit of the whole site for the year rollover and future-proofing (every hardcoded year, YTD window, fixed lookback, date assumption, and place that goes stale as history grows). Next step: a recheck of the revision-4 fix diff by Grok Bot, after his Friday token reset, on Sunil's say-so.

No build is authorised by this report. When the build is authorised, it follows the usual rules: one branch, Grok Bot single review, Sunil's go before any go-live, outside market hours, never Sunday.

## 14. What was not verified in this pass

- The exact mechanism by which `tools/stock_weekly.py` rebuilds vs appends the weekly files (fetch window not read); the SPECS map and the hardcoded note were verified, the fetch start was not. (Verified in revision 2: `stock_weekly.py` reads the pack and checks `baseClose`; it does not write the pack.)
- (Revision 2: `ytdBasis` verified — never set anywhere; see §4.)
- The Desk comparison metric chip handler (`data-cmp-metric="ytd"`, `screener.html` line 323) beyond `commonTarget` in `screener-chart.js`.
- The full text of the `stats-display.js` note (line 82, truncated in the read) and the `recap/index.html` archive structure (for year-grouping placement).
- The 5-year floor / 200-week MA computation code (ta-lines job) was not re-read in this pass; the design doc's "rolls forward on their own" is taken as given, and the floor/MA do not depend on the calendar year.
- `assets/js/ledger.js` and `assets/js/s2.js` line numbers are as read earlier in this task (pre-compaction); the values cited (base 2025-12-31, start 100000, STRC list ending 2026-11-30, `sleeves[k].ytd` formula) were verified against the files and against `compare.js`'s duplicate copy.
