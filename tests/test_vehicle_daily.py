#!/usr/bin/env python3
"""tools/vehicle_daily.py: offline fixture tests (no network). Bad values never overwrite stored ones; non-sessions never written."""
import json, os, sys, copy, subprocess, tempfile
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(R, 'tools'))
import vehicle_daily as V
H = json.load(open(os.path.join(R, 'tests/fixtures/vehicle/history.json'))); S = sorted(H['closes'])
base = json.load(open(os.path.join(R, 'assets/data/vehicle-daily.json')))
n = f = 0
def chk(name, ok):
    global n, f; n += 1; f += (not ok); print('PASS' if ok else 'FAIL', name)
def trimmed():
    v = copy.deepcopy(base)
    for k in V.VEH: v['vehicles'][k] = v['vehicles'][k][:-1]
    v['end'] = v['vehicles']['IBIT'][-1][0]; return v
last = S[-1]; prev = {k: base['vehicles'][k][-2][1] for k in V.VEH}
for label, val, ok in [('good', None, True), ('inf', float('inf'), False), ('nan', float('nan'), False), ('bool', True, False),
                       ('zero', 0, False), ('neg', -5.0, False), ('+30%', 'x1.3', False), ('str', '43', False)]:
    v = trimmed()
    def fetch(sym, since, val=val):
        x = base['vehicles'][sym][-1][1] if val is None else (prev[sym] * 1.3 if val == 'x1.3' else val)
        return {last: x, '2026-10-31': 99.0}
    V.update(v, S, fetch)
    got = dict(v['vehicles']['IBIT']).get(last)
    chk(f'{label}: {"written" if ok else "rejected"}', (got is not None) == ok and not V.validate(v, S))
    chk(f'{label}: weekend 2026-10-31 never written', '2026-10-31' not in dict(v['vehicles']['IBIT']))
v = copy.deepcopy(base); stored = v['vehicles']['FBTC'][-2][1]
V.update(v, S, lambda s, since: {v['vehicles'][s][-2][0]: float('inf')})
chk('bad revision never overwrites stored value', v['vehicles']['FBTC'][-2][1] == stored)
v = copy.deepcopy(base)
def boom(s, since): raise OSError('down')
chk('source failure: no change, no exception', V.update(v, S, boom) == [] and v == base)
chk('--check-only OK on repo file', V.validate(base, S) == [])
print('VEHICLE_DAILY TESTS', n, 'FAIL', f); sys.exit(1 if f else 0)
