#!/usr/bin/env bash
# One command for every reviewer (BP): bash tests/run_all.sh [--history PATH_OR_URL]
# Read-only: serves this checkout on localhost, never pushes, never writes outside $WORK. Exit 0 only if every suite is clean.
set -eu
# DISK SAFETY (bp2): stage ONLY the git-tracked repo (git archive), never cp from / or /proc; temp dir removed on EXIT;
# df checked before/after every big step, abort if disk use grows > 2 GB (DISK_MAX_GROWTH_KB to override).
cd "$(dirname "$0")/.."; REPO=$(git rev-parse --show-toplevel); cd "$REPO"; PORT=${PORT:-8799}
case "$REPO" in /|/proc|/proc/*|/sys|/sys/*|/dev|/dev/*|/tmp|"$HOME") echo "REFUSING: repo root is $REPO"; exit 2;; esac
[ -f "$REPO/tests/run_all.sh" ] && [ -d "$REPO/assets" ] || { echo "REFUSING: $REPO is not the paperstreet repo"; exit 2; }
# TG: temp root is configurable and defaults OUTSIDE /tmp (a cleaned /tmp lost runs mid-way): $PS_TMP or <repo>/../.pstmp; python temp files go there too
TROOT=${PS_TMP:-$(dirname "$REPO")/.pstmp}; case "$TROOT" in /|/proc*|/sys*|/dev*) echo "REFUSING temp root $TROOT"; exit 2;; esac; mkdir -p "$TROOT"
WORK=$(mktemp -d "$TROOT/psrun.XXXX"); export TMPDIR="$WORK"; SRV=""
cleanup(){ [ -n "$SRV" ] && kill "$SRV" 2>/dev/null; if [ -n "${KEEP_WORK:-}" ]; then echo "(KEEP_WORK set: $WORK kept)"; else rm -rf "$WORK"; fi; }
trap cleanup EXIT
DF0=$(df -Pk / | awk 'NR==2{print $3}'); MAXG=${DISK_MAX_GROWTH_KB:-2097152}
dfcheck(){ local u; u=$(df -Pk / | awk 'NR==2{print $3}'); echo "   [disk] $1: used $((u/1024)) MB (+$(((u-DF0)/1024)) MB since start), work dir $(du -sm "$WORK" | cut -f1) MB"; if [ $((u-DF0)) -gt "$MAXG" ]; then echo "ABORT: disk use grew more than $((MAXG/1024)) MB"; exit 3; fi; }
dfcheck start
OVR=""; HIST="https://raw.githubusercontent.com/Schadhaxx/paperstreetbtc/data/history.json"
while [ $# -gt 0 ]; do case "$1" in --history) HIST="$2"; shift 2;; *) echo "unknown arg $1"; exit 2;; esac; done
echo "build tree $(git rev-parse HEAD^{tree} 2>/dev/null) | head $(git rev-parse --short HEAD 2>/dev/null) | $(TZ=America/New_York date '+%a %b %-d %-I:%M %p ET')"
# recomputable unit ID: bp-<first 12 hex of sha256 over the BP patch series, in order>. Patches dir: $PATCHES or ../fix-proposals/bp
PD=${PATCHES:-$REPO/../fix-proposals/bp}; if ls "$PD"/00[0-9][0-9]-*.patch >/dev/null 2>&1; then echo "unit ID bp-$(cat "$PD"/00[0-9][0-9]-*.patch | sha256sum | cut -c1-12) (from $PD/00[0-9][0-9]-*.patch)"; fi
export PS_WATCH=${PS_WATCH:-$PD/watch_past_values.py}   # ops tool (not deployed), used by the Grok simbp1 repros
declare -A RES; FAILS=0
run(){ local name="$1"; shift; echo; echo "=== $name"; if "$@" > "$WORK/$name.log" 2>&1; then RES[$name]="PASS"; else RES[$name]="FAIL"; FAILS=$((FAILS+1)); fi; if [ "$name" = mutation ] || [ "$name" = reviewer_repros ]; then cat "$WORK/$name.log"; else tail -n 3 "$WORK/$name.log"; fi; dfcheck "$name"; }
# expected data = history (live or given); BP has no overrides.json handling (as live)
python3 - "$HIST" "$OVR" "$WORK/history.json" <<'PY' || { echo "cannot prepare expected history"; exit 2; }
import json, sys, urllib.request
src, ovr, out = sys.argv[1:4]
h = json.load(urllib.request.urlopen(src, timeout=30)) if src.startswith('http') else json.load(open(src))
if ovr:
    for d, r in json.load(open(ovr), parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c))).items():
        if d.startswith('_'): continue
        for k, v in r.items():   # approximation for the page tests only; the real validation is exercised in test_freeze
            if k in h['closes'].get(d, {}) and isinstance(v, (int, float)) and not isinstance(v, bool): h['closes'][d][k] = float(v)
json.dump(h, open(out, 'w'), separators=(',', ':'), allow_nan=False); print('expected history:', src, '+ overrides' if ovr else '(no overrides)', '-> Oct 22 BTC', h['closes'].get('2026-10-22', {}).get('BTC'))
PY
for z in America/New_York Asia/Tokyo America/Los_Angeles Europe/London UTC; do run "et_${z//\//_}" env TZ=$z node tests/test_et.js; done
run test_freeze python3 tests/test_freeze.py --history "$WORK/history.json"
run reviewer_repros python3 tests/repros.py --history "$WORK/history.json"   # BP: the SL/GB repros that apply to BP, listed in the log
run mutation python3 tests/mutate.py --history "$WORK/history.json"     # v9+: every constant/rule mutant must be caught
[ -f "$PD/test_watch.py" ] && run watch_tool python3 "$PD/test_watch.py"   # watch_past_values.py offline tests (W3)
run opens python3 tests/test_opens.py --history "$WORK/history.json"   # CR-005: opens validation, DST, coverage, golden values, page fallback
run tiingo python3 tests/test_tiingo.py                                   # TG: Tiingo cross-check (mocked, no key)
run tiingo_mutation python3 tests/mutate_tiingo.py                          # TG: mutants of the new Tiingo code only
run vehicle node tests/test_vehicle.js "$WORK/history.json"                 # ETF toggle: fresh / 1 stale / 2+ stale / missing / bad value
run vehicle_daily python3 tests/test_vehicle_daily.py                       # ETF toggle: nightly IBIT/FBTC updater (offline fixtures)
run stock_weekly_py python3 tests/test_stock_weekly.py                       # screener stock candles: generator fixtures + shipped invariants
run stock_weekly_js node tests/test_stock_weekly.js                          # screener stock candles: shipped JSON invariants (brief 4.6)
run desk_intraday python3 tests/test_desk_intraday.py                        # Desk intraday refresh: 15-min current-week candles (offline fixtures, no network)
run desk_live python3 tests/test_desk_live.py                              # 5-min Desk (option b): desk-live.json builder + validator (offline fixtures)
run ta_lines python3 tests/test_ta_lines.py                                # TA Stage 3: trendline job (tools/ta_lines.py) unit tests + replay gate (offline fixtures, no network)
run ta_lines_fix2 python3 tests/test_ta_lines_fix2.py                      # TA Stage 3 fix 2: sloped-line validity (rule A) live cases + B/C numbers (offline fixture, no network)
run candle_date_guardrail node tests/test_candle_date_guardrail.js             # Desk chart: live price only on the candle whose Mon-Sun range contains today (ET)
run desk_monday_candle node tests/test_desk_monday_candle.js               # Desk chart: append the fresh desk-live candle as a new in-progress week on the first trading day (16 Nov 2026)
run money_format node tests/test_money_format.js                             # -$153.50 money formatters, including the stock card line
run speed_lazy_panel node tests/test_speed_option2.js                        # lazy BTC panel split (et24): eager pill + lazy panel, live-feel/4H/FLIP/CAD/inline
run worker node --test worker/test/worker.test.mjs                              # Stage 2: Worker /err report + read routes (fake D1, placeholder secret)
run ps_err node tests/test_ps_err.js                                            # Stage 2: ps-err.js hook, beacon loader, /me/ page, pins
run s2_hero_cosmetic node tests/test_s2_hero_cosmetic.js                     # YTD hero: legend wrap + light grid + tooltip no-clip + fonts.ready redraw (15 Nov 2026 nice-to-haves)
run no_chartjs python3 tests/test_no_chartjs.py                              # Chart.js removed (20 Nov 2026): no refs, vendor files gone, BTC + YTD charts draw with chart.umd blocked
run desk_boll_title python3 tests/test_desk_boll_title.py                     # Desk: Bollinger title follows each symbol's own Weekly/Daily mode (21 Nov 2026)
run oi001_label node tests/test_oi001_label.js                              # OI-001: backup-source BTC label keyed on fallback_sources
run oi001_compare_scope python3 tests/test_oi001_compare_scope.py           # OI-001: Compare #pvChartNote backup label with crafted Coinbase day (scope fix)
run cmp_daily_py python3 tests/test_cmp_daily.py                             # comparison chart: daily-close generator fixtures + shipped file
run cmp_intraday_js node tests/test_cmp_intraday.js                          # Job 10: 1D intraday comparison — CmpIntraMath pure-block unit tests (trim / align / rebase / stale rule, incl. holiday + early-close freshness)
run cmp_intraday_py python3 tests/test_cmp_intraday.py                       # Job 10: tools/cmp_intraday.py — ET gate, expected session, Yahoo payload filter, document build + validator, CLI (offline fixtures, no network)
run cmp_js node tests/test_cmp.js                                            # comparison chart: rebase math, ranges, SPCX rule, shipped closes
run ps_ev node tests/test_ps_ev.js                                             # Stage 3: event analytics client (ps-ev.js) — hooks, ?src=, opt-out, dedupe
run worker_test node --test worker/test/worker.test.mjs                       # Worker (quotes + Stage 3 /ev) — node:test, upstream fetches stubbed
TD=${TG_PATCHES:-$REPO/../fix-proposals/tiingo}; ls "$TD"/00[0-9][0-9]-*.patch >/dev/null 2>&1 && echo "TG unit ID tg-$(cat "$TD"/00[0-9][0-9]-*.patch | sha256sum | cut -c1-12)"
run test_freeze_liveURL python3 tests/test_freeze.py                       # F8: against the live data-branch URL (read-only)
run et_expiry_guard_2028-11-15 bash -c 'if ET_TEST_NOW=2028-11-15 node tests/test_et.js; then echo "guard did NOT fire"; exit 1; else echo "guard fired as expected"; fi'   # F9 (moved with the 2028 list extension)
# recap: exactly what the nightly job does: regenerate in a staging copy, then test (strict 1e-6 embedded closes)
STAGE="$WORK/stage"; case "$STAGE" in "$TROOT"/psrun.*/stage) ;; *) echo "REFUSING to stage outside the temp dir: $STAGE"; exit 2;; esac
rm -rf "$STAGE"; mkdir "$STAGE"; git -C "$REPO" archive --format=tar HEAD | tar -x -C "$STAGE"   # tracked files of HEAD only
[ -z "$(git -C "$REPO" status --porcelain --untracked-files=no)" ] || echo "   WARNING: uncommitted changes are NOT in the stage (staged = HEAD)"
dfcheck stage
echo '["2026-10-22"]' > "$WORK/btc-heal-once.json"   # R-s: the one-time heal list shipped on the data branch (dates only)
run recap_gen bash -c "cd '$WORK/stage' && python3 tools/btc_daily.py assets/data/btc-daily.json '$WORK/history.json' --heal-list '$WORK/btc-heal-once.json' || true; python3 tools/recap_gen.py --history '$WORK/history.json' --repo ."
run test_recap bash -c "cd '$WORK/stage' && python3 tests/test_recap.py --history '$WORK/history.json' --repo ."
# v7 (GB v6-2): own server only. Free port picked automatically (PORT env only if free), PID alive, and /assets/js/et.js must match the staged file.
PORT=$(python3 - "$PORT" <<'PY'
import socket, sys
def free(p):
    s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
    try: s.bind(('127.0.0.1', p)); return True
    except OSError: return False
    finally: s.close()
p = int(sys.argv[1])
if not free(p): s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close()
print(p)
PY
)
( cd "$WORK/stage" && exec python3 -m http.server "$PORT" --bind 127.0.0.1 > "$WORK/server.log" 2>&1 ) & SRV=$!
ok=0; for i in $(seq 1 40); do
  sleep 0.25; kill -0 $SRV 2>/dev/null || break
  if curl -fsS "http://127.0.0.1:$PORT/assets/js/et.js" -o "$WORK/et.served" 2>/dev/null && cmp -s "$WORK/et.served" "$WORK/stage/assets/js/et.js"; then ok=1; break; fi
done
if [ $ok -ne 1 ] || ! kill -0 $SRV 2>/dev/null; then echo "FATAL: local server on port $PORT is not ours or not serving the staged build (pid $SRV); no page tests run"; cat "$WORK/server.log"; kill $SRV 2>/dev/null; exit 2; fi
echo "server: pid $SRV on 127.0.0.1:$PORT, et.js matches staged build"
run datatest_strict env DT_HISTORY="$WORK/history.json" python3 "$WORK/stage/tools/datatest.py" "http://127.0.0.1:$PORT"
run headless python3 tests/headless_matrix.py "http://127.0.0.1:$PORT" "$WORK/shots"
run ta_indicators node tests/test_ta_indicators.js  # TA Stage 2: SMA/EMA/Bollinger/RSI reference values
run ta_trendlines node tests/test_ta_trendlines.js  # TA Stage 4: trendline validate/stale/map/sloped/filter/label (pure functions)
run ta_pack_cases node tests/test_ta_pack_cases.js  # TA Stage 4: Grok Bot test pack's 16 cases against tlSelectLines (fixtures are repo copies of the pack's)
run ta_gating node tests/test_ta_gating.js  # TA drawing fixes Stage 1 + Jobs 1-3: per-view toggle gating (pure functions; trendlines ungated by Job 1, Bollinger + SMA/EMA 200 ungated by Job 2, RSI ungated by Job 3)
run ta_job1 python3 tests/test_ta_job1.py "http://127.0.0.1:$PORT" "$WORK/shots"  # TA drawing fixes Job 1: Line-view trendlines 1D/1W — y-range expands to include drawn lines, toggle ungreyed, candles unchanged
run ta_job2 python3 tests/test_ta_job2.py "http://127.0.0.1:$PORT" "$WORK/shots"  # TA drawing fixes Job 2: indicator windows — pre-warm + retry, Bollinger + SMA/EMA 200 valid from index 0, toggles ungreyed, retry heals a failed fetch
run ta_job3 python3 tests/test_ta_job3.py "http://127.0.0.1:$PORT" "$WORK/shots"  # TA drawing fixes Job 3: RSI strip rebuild — scale, shaded 30/70 bands, live header value, taller strip, toggle ungreyed everywhere
run ta_job4 python3 tests/test_ta_job4.py "http://127.0.0.1:$PORT" "$WORK/shots"  # TA drawing fixes Job 4: label drift — trendline labels anchored to the level's own USD price, identical across FX rates
run ta_job5 python3 tests/test_ta_job5.py "http://127.0.0.1:$PORT" "$WORK/shots"  # TA drawing fixes Job 5: panel state bugs — no SMA 50 auto-select, chips show on only with the group on, Clear all empties maSet, chart type survives range switches, fallbacks reset the type to Line
run ta_job6 python3 tests/test_ta_job6.py "http://127.0.0.1:$PORT" "$WORK/shots"  # TA drawing fixes Job 6: comparison note + badge — the note reads outside the panel when a comparison hides TA; the badge counts the overlays actually drawing (comparison on -> 0, gated MAs and lineless trendlines excluded)
run ta_job8 python3 tests/test_ta_job8.py "http://127.0.0.1:$PORT" "$WORK/shots"  # TA drawing fixes Job 8: unscanned items — 1W range scanned (Line + 4H + daily candles all draw), SMA 200 on 6M decided (reads right on Line + weekly, stays ungated), SMA/EMA 200 gated on monthly candles (only ~195 months of BTC history exist, so they can never compute there)
run ta_job9 python3 tests/test_ta_job9.py "http://127.0.0.1:$PORT" "$WORK/shots"  # TA drawing fixes Job 9: candle additions — 3M/6M/YTD gain Daily (default daily), 5Y gains Weekly/Monthly, 10Y gains Monthly/Yearly (both default daily); yearly aggregation is new; Bollinger + all MAs gated on yearly (only 17 yearly closes exist)
run ta_job10 python3 tests/test_ta_job10.py "http://127.0.0.1:$PORT" "$WORK/shots"  # TA drawing fixes Job 10: 1D comparison pipeline — BTC-only 1D Line unchanged, compare toggles draw the rebased session lines, candles force toggles off (state preserved), Saturday shows the last session, Monday after the open falls back to BTC-only
run ta_job11 python3 tests/test_ta_job11.py "http://127.0.0.1:$PORT" "$WORK/shots"  # TA drawing fixes Job 11: Candles reachable on Max (Daily/Weekly/Monthly/Yearly, default Daily, extended fetch back to 2010-08-18); 1W Candles -> 1D type carry verified (scan #2 case, fixed by Job 5)
run ta_job12 python3 tests/test_ta_job12.py "http://127.0.0.1:$PORT" "$WORK/shots"  # TA drawing fixes Job 12: scan #2 axis/comparison/labelling leftovers — auto-log on extreme compare spans (10Y/Max), half-tick headroom on Line views (YTD MSTR low, 1D peak), 5Y year-label dedupe, SMA 20/50 + EMA 50 ungated on 1W, axis widens for drawn overlays (1W BB poke, 1W daily 200s)
run ta_stage1 python3 tests/test_ta_stage1.py "http://127.0.0.1:$PORT" "$WORK/shots"  # TA Stage 1: chart-type pill + menu, TA pill/panel, RSI strip, overlap 0
run ta_stage2 python3 tests/test_ta_stage2.py "http://127.0.0.1:$PORT" "$WORK/shots"  # TA Stage 2: browser indicators, warm-up, RSI strip, tooltip, perf, pixel-diff
run ta_stage4 python3 tests/test_ta_stage4.py "http://127.0.0.1:$PORT" "$WORK/shots"  # TA Stage 4: trendlines drawn from ta-lines.json, 8 display rules, stale/missing/invalid, pixel checks
run ta_rotate python3 tests/test_rotate_hint.py "http://127.0.0.1:$PORT" "$WORK/shots"  # TA rotate hint: portrait pill bottom-left of the clock chart, tap enters fs chart + prompt, landscape hides, overlap 0
run ytd_chart_scroll python3 tests/test_ytd_chart_scroll.py "http://127.0.0.1:$PORT"  # YTD chart must not trap phone/iPad scroll (Speed Option 2 rollback)
kill $SRV 2>/dev/null; wait $SRV 2>/dev/null || true; SRV=""
dfcheck end
echo; echo "=== SUMMARY (logs + screenshots in $WORK; removed on exit unless KEEP_WORK=1)"; for k in $(printf '%s\n' "${!RES[@]}" | sort); do printf '  %-28s %s\n' "$k" "${RES[$k]}"; done
grep -h "^WARN\|WARNINGS" "$WORK"/datatest_strict.log 2>/dev/null | head -5 || true
echo "RUN-ALL: $FAILS suite(s) failed"; exit $((FAILS>0))
