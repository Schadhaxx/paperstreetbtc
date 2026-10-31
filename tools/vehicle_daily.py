#!/usr/bin/env python3
"""Vehicle toggle data: IBIT/FBTC daily closes in assets/data/vehicle-daily.json.
Source: Yahoo Finance daily bar close (unadjusted 'close', same vendor/field as the original hand-built file, ET dates).
Only history.json trading sessions are written (weekends/holidays never get a row). Every value is validated:
finite, not bool, > 0, within +/-25% of the vehicle's prior stored close. A bad or missing value is skipped and
never overwrites a stored good one. Each run re-fetches the last REFETCH sessions so a revised close replaces the
stored one (only if it validates). A failed source never fails the run (exit 0, file unchanged); --check-only exits 1
on an invalid file.
usage: python3 tools/vehicle_daily.py FILE.json --history history.json [--check-only] [--fixture yahoo.json]"""
import json, math, sys, time, datetime as dt, urllib.request
from zoneinfo import ZoneInfo
NY = ZoneInfo('America/New_York')
VEH = ['IBIT', 'FBTC']
BAND = 0.25
REFETCH = 5

def good(v, ref):
    if isinstance(v, bool) or not isinstance(v, (int, float)): return False
    if not math.isfinite(v) or v <= 0: return False
    if ref is not None and not (abs(v / ref - 1) <= BAND): return False
    return True

def yahoo(sym, since):
    p1 = int(dt.datetime.fromisoformat(since).replace(tzinfo=dt.timezone.utc).timestamp()) - 3 * 86400
    u = f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={p1}&period2={int(time.time()) + 86400}&interval=1d'
    r = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0 paperstreet-vehicle'})
    j = json.load(urllib.request.urlopen(r, timeout=30))
    r = j['chart']['result'][0]; c = r['indicators']['quote'][0]['close']
    return {dt.datetime.fromtimestamp(t, NY).date().isoformat(): v for t, v in zip(r['timestamp'], c)}

def validate(V, sessions):
    bad = []; S = set(sessions)
    for v in VEH:
        rows = V['vehicles'].get(v) or []
        if not rows: bad.append(f'{v}: empty'); continue
        prev = None; pd = None
        for d, x in rows:
            if d not in S: bad.append(f'{v} {d}: not a trading session')
            if pd is not None and d <= pd: bad.append(f'{v} {d}: not ascending')
            if not good(x, prev): bad.append(f'{v} {d}: bad value {x!r}')
            prev, pd = x, d
    ends = {v: V['vehicles'][v][-1][0] for v in VEH if V['vehicles'].get(v)}
    if V.get('end') != min(ends.values(), default=None): bad.append(f'end {V.get("end")} != {ends}')
    return bad

def update(V, sessions, fetch):
    """fetch(sym, since) -> {date: close}. Returns list of change strings."""
    changes = []
    for v in VEH:
        rows = dict(V['vehicles'][v]); have = sorted(rows)
        last = have[-1]; idx = sessions.index(last) if last in sessions else len(sessions) - 1
        want = [d for d in sessions[max(0, idx - REFETCH + 1):] if d >= have[0]]
        if not want: continue
        try: got = fetch(v, want[0])
        except Exception as e: print(f'::warning::{v}: source failed ({type(e).__name__}); file unchanged for {v}'); continue
        for d in want:
            x = got.get(d)
            if x is None: continue
            x = round(x, 4) if isinstance(x, float) and math.isfinite(x) else x
            prior = [rows[p] for p in sorted(rows) if p < d]
            if not good(x, prior[-1] if prior else None):
                print(f'::warning::{v} {d}: rejected {x!r}'); continue
            if rows.get(d) != x: changes.append(f'{v} {d}: {rows.get(d)} -> {x}'); rows[d] = x
        V['vehicles'][v] = [[d, rows[d]] for d in sorted(rows)]
    V['end'] = min(V['vehicles'][v][-1][0] for v in VEH)
    V['sessions'] = max(len(V['vehicles'][v]) for v in VEH)
    return changes

def main(a):
    f = a[0]; hist = a[a.index('--history') + 1]
    H = json.load(open(hist)); sessions = sorted(H['closes'])
    V = json.load(open(f))
    if '--check-only' in a:
        bad = validate(V, sessions)
        for b in bad: print('BAD', b)
        print('vehicle-daily', 'OK' if not bad else 'INVALID', V.get('end')); return 1 if bad else 0
    if '--fixture' in a:
        fx = json.load(open(a[a.index('--fixture') + 1])); fetch = lambda s, since: fx[s]
    else: fetch = yahoo
    ch = update(V, sessions, fetch)
    bad = validate(V, sessions)
    if bad:
        for b in bad: print('BAD', b)
        print('::warning::vehicle-daily invalid after update; file NOT written'); return 0
    if ch:
        tmp = f + '.tmp'; open(tmp, 'w').write(json.dumps(V, indent=1)); import os; os.replace(tmp, f)
    for c in ch: print(c)
    print('vehicle-daily end', V['end'], 'changes', len(ch)); return 0

if __name__ == '__main__': sys.exit(main(sys.argv[1:]))
