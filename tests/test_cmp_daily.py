#!/usr/bin/env python3
"""Offline checks for tools/cmp_daily.py, plus the shipped cmp-daily.json."""
import datetime as dt
import json, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import cmp_daily as cd
import stock_weekly as sw

n = 0
f = 0

def chk(name, ok, info=''):
    global n, f
    n += 1
    if not ok:
        f += 1
        print('FAIL', name, info)

def run(args):
    p = subprocess.run([sys.executable, os.path.join(ROOT, 'tools/cmp_daily.py')] + args, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr

# DST: noon rules are tested via closes_from_pairs.
pairs_et = [
    (int(dt.datetime(2026, 3, 9, 13, 30, tzinfo=dt.timezone.utc).timestamp()), 10),
    (int(dt.datetime(2026, 3, 9, 3, 30, tzinfo=dt.timezone.utc).timestamp()), 9),
]
got = cd.closes_from_pairs('TSLA', pairs_et, 'nyse')
chk('13:30Z 9 Mar is 9 Mar ET', dt.date(2026, 3, 9) in got and got[dt.date(2026, 3, 9)] == 10)
chk('03:30Z 9 Mar is still 8 Mar ET', dt.date(2026, 3, 8) in got and got[dt.date(2026, 3, 8)] == 9)
btc = cd.closes_from_pairs('BTC', [(int(dt.datetime(2026, 3, 9, 0, 0, tzinfo=dt.timezone.utc).timestamp()), 100)], 'utc')
chk('BTC stamp stays on the UTC day', dt.date(2026, 3, 9) in btc)

# Jan 2026 TSLA: base 31 Dec, sessions 2, 5, 6, 7, 8, 9. Now Saturday 10 Jan 18:00 ET.
sessions = ['2025-12-31', '2026-01-02', '2026-01-05', '2026-01-06', '2026-01-07', '2026-01-08', '2026-01-09']
bars = [{'date': d, 'close': 100 + i} for i, d in enumerate(sessions)]
bars[0]['close'] = 449.72
fx = {'now': '2026-01-10T18:00:00-05:00', 'symbols': {'TSLA': bars}}
pack = {'asOf': '2026-01-09', 'rows': [{'symbol': 'TSLA', 'baseClose': 449.72, 'price': 106}]}

td = tempfile.mkdtemp(prefix='cmpfix-')
try:
    fx_path = os.path.join(td, 'bars.json')
    pack_path = os.path.join(td, 'pack.json')
    out = os.path.join(td, 'cmp-daily.json')
    json.dump(fx, open(fx_path, 'w'))
    json.dump(pack, open(pack_path, 'w'))
    code, stdout, err = run(['--fixture', fx_path, '--pack', pack_path, '--out', out, '--weekly-dir', td])
    chk('fixture writes', code == 0, err)
    doc = json.load(open(out))
    s = doc['symbols']['TSLA']
    chk('fixture asOf Friday', doc['asOf'] == '2026-01-09', doc['asOf'])
    chk('fixture starts 2 Jan and keeps the base off the series', s['dates'][0] == '2026-01-02' and s['baseClose'] == 449.72)
    chk('fixture last is the Friday close', s['dates'][-1] == '2026-01-09' and s['closes'][-1] == 106)
    chk('Jan 1 holiday is not required', '2026-01-01' not in s['dates'])
    b1 = open(out, 'rb').read()
    code2, _, err2 = run(['--fixture', fx_path, '--pack', pack_path, '--out', out, '--weekly-dir', td])
    chk('idempotent', code2 == 0 and open(out, 'rb').read() == b1, err2)

    broken = json.loads(json.dumps(fx))
    broken['symbols']['TSLA'] = [b for b in broken['symbols']['TSLA'] if b['date'] != '2026-01-06']
    bad_fx = os.path.join(td, 'bad.json')
    bad_out = os.path.join(td, 'nope.json')
    json.dump(broken, open(bad_fx, 'w'))
    code3, _, err3 = run(['--fixture', bad_fx, '--pack', pack_path, '--out', bad_out])
    chk('missing session exits 1', code3 == 1 and 'missing' in err3.lower(), err3)
    chk('missing session writes nothing', not os.path.exists(bad_out))

    bad_base = json.loads(json.dumps(pack))
    bad_base['rows'][0]['baseClose'] = 1
    bad_pack = os.path.join(td, 'badpack.json')
    json.dump(bad_base, open(bad_pack, 'w'))
    code4, _, err4 = run(['--fixture', fx_path, '--pack', bad_pack, '--out', bad_out])
    chk('pack baseline mismatch exits 1', code4 == 1 and not os.path.exists(bad_out), err4)
finally:
    shutil.rmtree(td)

shipped = os.path.join(ROOT, 'assets/data/cmp-daily.json')
code5, out5, err5 = run(['--check-only', '--out', shipped, '--pack', os.path.join(ROOT, 'assets/data/screener-pack.json'), '--weekly-dir', os.path.join(ROOT, 'assets/data')])
chk('shipped file passes check-only', code5 == 0, err5 or out5)

doc = json.load(open(shipped))
chk('seven stocks plus three benchmarks', set(cd.ORDER) <= set(doc['symbols']))
spcx = doc['symbols']['SPCX']
chk('SPCX open week is the listing close', spcx['closes'][0] == 160.95 and spcx['dates'][0] == '2026-06-12')
# A Friday 15:00 ET clock drops that day; 16:15 keeps it.
early_closes = {dt.date.fromisoformat(d): (449.72 if d == '2025-12-31' else 10) for d in sessions}
early = cd.build_symbol('TSLA', early_closes, '2026-01-09T15:00:00-05:00', {'baseClose': 449.72, 'symbol': 'TSLA'})
chk('friday 15:00 drops the unfinished session', early['dates'][-1] == '2026-01-08', early['dates'][-1])
late_closes = {dt.date.fromisoformat(d): (449.72 if d == '2025-12-31' else 10) for d in sessions}
late = cd.build_symbol('TSLA', late_closes, '2026-01-09T16:15:00-05:00', {'baseClose': 449.72, 'symbol': 'TSLA'})
chk('friday 16:15 keeps the close', late['dates'][-1] == '2026-01-09')

print('cmp daily checks', n, 'fail', f)
sys.exit(1 if f else 0)
