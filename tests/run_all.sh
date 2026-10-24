#!/usr/bin/env bash
# One command for every reviewer (BP): bash tests/run_all.sh [--history PATH_OR_URL]
# Read-only: serves this checkout on localhost, never pushes, never writes outside $WORK. Exit 0 only if every suite is clean.
set -u
cd "$(dirname "$0")/.."; REPO=$(pwd); PORT=${PORT:-8799}; WORK=$(mktemp -d /tmp/psrun.XXXX)
OVR=""; HIST="https://raw.githubusercontent.com/Schadhaxx/paperstreetbtc/data/history.json"
while [ $# -gt 0 ]; do case "$1" in --history) HIST="$2"; shift 2;; *) echo "unknown arg $1"; exit 2;; esac; done
echo "build tree $(git rev-parse HEAD^{tree} 2>/dev/null) | head $(git rev-parse --short HEAD 2>/dev/null) | $(TZ=America/New_York date '+%a %b %-d %-I:%M %p ET')"
# recomputable unit ID: bp-<first 12 hex of sha256 over the BP patch series, in order>. Patches dir: $PATCHES or ../fix-proposals/bp
PD=${PATCHES:-$REPO/../fix-proposals/bp}; if ls "$PD"/00[0-9][0-9]-*.patch >/dev/null 2>&1; then echo "unit ID bp-$(cat "$PD"/00[0-9][0-9]-*.patch | sha256sum | cut -c1-12) (from $PD/00[0-9][0-9]-*.patch)"; fi
export PS_WATCH=${PS_WATCH:-$PD/watch_past_values.py}   # ops tool (not deployed), used by the Grok simbp1 repros
declare -A RES; FAILS=0
run(){ local name="$1"; shift; echo; echo "=== $name"; if "$@" > "$WORK/$name.log" 2>&1; then RES[$name]="PASS"; else RES[$name]="FAIL"; FAILS=$((FAILS+1)); fi; if [ "$name" = mutation ] || [ "$name" = reviewer_repros ]; then cat "$WORK/$name.log"; else tail -n 3 "$WORK/$name.log"; fi; }
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
run test_freeze_liveURL python3 tests/test_freeze.py                       # F8: against the live data-branch URL (read-only)
run et_expiry_guard_2027-11-15 bash -c 'if ET_TEST_NOW=2027-11-15 node tests/test_et.js; then echo "guard did NOT fire"; exit 1; else echo "guard fired as expected"; fi'   # F9
# recap: exactly what the nightly job does: regenerate in a staging copy, then test (strict 1e-6 embedded closes)
rm -rf "$WORK/stage" && cp -a "$REPO" "$WORK/stage"
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
kill $SRV 2>/dev/null; wait $SRV 2>/dev/null
echo; echo "=== SUMMARY (logs + screenshots in $WORK)"; for k in $(printf '%s\n' "${!RES[@]}" | sort); do printf '  %-28s %s\n' "$k" "${RES[$k]}"; done
grep -h "^WARN\|WARNINGS" "$WORK"/datatest_strict.log 2>/dev/null | head -5
echo "RUN-ALL: $FAILS suite(s) failed"; exit $((FAILS>0))
