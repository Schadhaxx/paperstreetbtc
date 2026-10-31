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
run money_format node tests/test_money_format.js                             # -$153.50 money formatters, including the stock card line
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
kill $SRV 2>/dev/null; wait $SRV 2>/dev/null || true; SRV=""
dfcheck end
echo; echo "=== SUMMARY (logs + screenshots in $WORK; removed on exit unless KEEP_WORK=1)"; for k in $(printf '%s\n' "${!RES[@]}" | sort); do printf '  %-28s %s\n' "$k" "${RES[$k]}"; done
grep -h "^WARN\|WARNINGS" "$WORK"/datatest_strict.log 2>/dev/null | head -5 || true
echo "RUN-ALL: $FAILS suite(s) failed"; exit $((FAILS>0))
