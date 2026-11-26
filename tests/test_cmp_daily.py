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

# BTC guard: last date must equal the UTC cutoff, not the NYSE asOf.
# now Sat Jan 10 18:00 ET (23:00 UTC) -> UTC cutoff Jan 9, NYSE asOf Jan 9.
chk('BTC guard passes when last == UTC cutoff',
    cd.check_btc_cutoff({'BTC': {'dates': ['2026-01-09']}}, '2026-01-10T18:00:00-05:00') is None)
chk('BTC guard fails when last is a day short',
    cd.check_btc_cutoff({'BTC': {'dates': ['2026-01-08']}}, '2026-01-10T18:00:00-05:00') is not None)
chk('BTC guard skips when BTC not built',
    cd.check_btc_cutoff({}, '2026-01-10T18:00:00-05:00') is None)
# A run before 00:15 UTC ends BTC a day behind asOf — correct by design.
chk('BTC guard uses the pre-midnight UTC cutoff',
    cd.check_btc_cutoff({'BTC': {'dates': ['2026-01-08']}}, '2026-01-10T00:05:00Z') is None)

# BTC fixture end-to-end: baseline Dec 31 plus bars Jan 1-9 2026 (every
# day), now Sat Jan 10 18:00 ET. The file writes with BTC ending Jan 9
# (UTC cutoff) and the NYSE asOf Jan 9 (Friday).
td2 = tempfile.mkdtemp(prefix='cmpbtc-')
try:
    btc_bars = [{'date': '2025-12-31', 'close': 90000}] + [
        {'date': f'2026-01-0{d}', 'close': 90000 + d} for d in range(1, 10)]
    btc_fx = {'now': '2026-01-10T18:00:00-05:00', 'symbols': {'BTC': btc_bars}}
    btc_fx_path = os.path.join(td2, 'btc.json')
    btc_pack = os.path.join(td2, 'pack.json')
    btc_out = os.path.join(td2, 'cmp-daily.json')
    json.dump(btc_fx, open(btc_fx_path, 'w'))
    json.dump(pack, open(btc_pack, 'w'))
    code_b, _, err_b = run(['--fixture', btc_fx_path, '--pack', btc_pack, '--out', btc_out, '--weekly-dir', td2])
    chk('BTC fixture writes', code_b == 0, err_b)
    btc_doc = json.load(open(btc_out))
    chk('BTC fixture ends on UTC cutoff Jan 9', btc_doc['symbols']['BTC']['dates'][-1] == '2026-01-09')
    chk('BTC fixture asOf is the Friday NYSE close', btc_doc['asOf'] == '2026-01-09')
finally:
    shutil.rmtree(td2)

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

# History fallback: a null Yahoo close is filled from the site's own
# records (history first, shipped cmp-daily second); a value in
# neither source still fails loud; the fixture path stays strict.
def _payload_tsla_null_jan6():
    sess = ['2025-12-31', '2026-01-02', '2026-01-05', '2026-01-06', '2026-01-07', '2026-01-08', '2026-01-09']
    ts, cl = [], []
    for i, d in enumerate(sess):
        y, m, dd = map(int, d.split('-'))
        ts.append(int(dt.datetime(y, m, dd, 12, tzinfo=sw.NY).timestamp()))
        cl.append(449.72 if i == 0 else 100 + i)
    cl[3] = None  # Jan 6 null
    return {'meta': {'currency': 'USD'}, 'indicators': {'quote': [{'close': cl}]}, 'timestamp': ts}

fb = []
got = cd.closes_from_yahoo_payload('TSLA', _payload_tsla_null_jan6(), 'nyse',
                                   history={'2026-01-06': {'TSLA': 103.0}}, shipped={}, fallbacks=fb)
chk('null close filled from history', got[dt.date(2026, 1, 6)] == 103.0)
chk('fallback recorded with source', len(fb) == 1 and fb[0][0] == 'TSLA' and fb[0][3] == 'site history', str(fb))
fb2 = []
got2 = cd.closes_from_yahoo_payload('TSLA', _payload_tsla_null_jan6(), 'nyse',
                                    history={}, shipped={'TSLA': {dt.date(2026, 1, 6): 104.5}}, fallbacks=fb2)
chk('null close filled from shipped file', got2[dt.date(2026, 1, 6)] == 104.5)
chk('shipped fallback recorded with source', len(fb2) == 1 and fb2[0][3] == 'shipped cmp-daily file', str(fb2))
try:
    cd.closes_from_yahoo_payload('TSLA', _payload_tsla_null_jan6(), 'nyse', history={}, shipped={}, fallbacks=[])
    chk('null close with no source fails loud', False)
except RuntimeError as e:
    chk('null close with no source fails loud', 'null close' in str(e), str(e))
try:
    cd.closes_from_yahoo_payload('TSLA', _payload_tsla_null_jan6(), 'nyse')
    chk('null close with no sources configured fails loud', False)
except RuntimeError as e:
    chk('null close with no sources configured fails loud', 'null close' in str(e), str(e))
try:
    cd.closes_from_yahoo_payload('TSLA', _payload_tsla_null_jan6(), 'nyse',
                                 history={'2026-01-06': {'TSLA': 0}}, shipped={}, fallbacks=[])
    chk('bad history value is no value', False)
except RuntimeError as e:
    chk('bad history value is no value', 'null close' in str(e), str(e))
fb3 = []
got3 = cd.closes_from_yahoo_payload('TSLA', _payload_tsla_null_jan6(), 'nyse',
                                    history={'2026-01-06': {'TSLA': 103.456}}, shipped={}, fallbacks=fb3)
chk('history value rounded to cents', got3[dt.date(2026, 1, 6)] == 103.46, str(got3.get(dt.date(2026, 1, 6))))
try:
    cd.closes_from_pairs('TSLA', [(None, 100)], 'nyse', history={'2026-01-06': {'TSLA': 103.0}}, shipped={}, fallbacks=[])
    chk('null timestamp fails even with history', False)
except RuntimeError as e:
    chk('null timestamp fails even with history', 'timestamp' in str(e), str(e))

td3 = tempfile.mkdtemp(prefix='cmpfb-')
try:
    hist_path = os.path.join(td3, 'history.json')
    json.dump({'closes': {'2026-01-06': {'TSLA': 103.0, 'BTC': 59740.871}}}, open(hist_path, 'w'))
    chk('load_history reads closes', cd.load_history(hist_path) == {'2026-01-06': {'TSLA': 103.0, 'BTC': 59740.871}})
    chk('load_history missing file is None', cd.load_history(os.path.join(td3, 'nope.json')) is None)
    ship_path = os.path.join(td3, 'cmp-daily.json')
    json.dump({'symbols': {'TSLA': {'dates': ['2026-01-06'], 'closes': [104.5]}}}, open(ship_path, 'w'))
    chk('load_shipped_cmp reads nested closes', cd.load_shipped_cmp(ship_path) == {'TSLA': {dt.date(2026, 1, 6): 104.5}})
    chk('load_shipped_cmp missing file is empty', cd.load_shipped_cmp(os.path.join(td3, 'nope.json')) == {})
finally:
    shutil.rmtree(td3)

# The fixture path does not use the fallback: a fixture is the
# operator's exact bars, so a null close in one still fails loud.
td4 = tempfile.mkdtemp(prefix='cmpfxnull-')
try:
    null_bars = [{'date': d, 'close': 100 + i} for i, d in enumerate(sessions)]
    null_bars[0]['close'] = 449.72
    null_bars[3]['close'] = None  # Jan 6 null in the fixture
    null_fx = {'now': '2026-01-10T18:00:00-05:00', 'symbols': {'TSLA': null_bars}}
    null_fx_path = os.path.join(td4, 'null.json')
    null_pack = os.path.join(td4, 'pack.json')
    null_out = os.path.join(td4, 'cmp-daily.json')
    json.dump(null_fx, open(null_fx_path, 'w'))
    json.dump(pack, open(null_pack, 'w'))
    code_n, _, err_n = run(['--fixture', null_fx_path, '--pack', null_pack, '--out', null_out, '--weekly-dir', td4])
    chk('fixture null close still fails loud', code_n == 1 and 'null close' in err_n, err_n)
    chk('fixture null close writes nothing', not os.path.exists(null_out))
finally:
    shutil.rmtree(td4)

# End-to-end through main() with the Yahoo path stubbed (offline): a
# null TSLA bar on Jan 6 is filled from --history and the file writes;
# without history the same run fails loud and writes nothing. The
# shipped source is pointed at a missing file so only history can
# fill the null (the real shipped file already holds Jan 6).
import io, contextlib
td5 = tempfile.mkdtemp(prefix='cmpe2e-')
try:
    e2e_now = '2026-06-30T18:00:00-05:00'
    e2e_cutoff = dt.date(2026, 6, 30)
    e2e_nyse_days = [dt.date(2025, 12, 31)] + sw.expected_sessions(dt.date(2026, 1, 2), e2e_cutoff)
    e2e_hist = os.path.join(td5, 'history.json')
    json.dump({'closes': {'2026-01-06': {'TSLA': 103.0}}}, open(e2e_hist, 'w'))
    e2e_pack = os.path.join(td5, 'pack.json')
    e2e_rows = [{'symbol': s, 'baseClose': 100.0} for s in cd.ORDER if cd.SPECS[s]['kind'] == 'stock']
    json.dump({'asOf': '2026-06-30', 'rows': e2e_rows}, open(e2e_pack, 'w'))
    e2e_ship_missing = os.path.join(td5, 'nonesuch.json')
    e2e_out = os.path.join(td5, 'cmp-daily.json')

    def _stub_fetch(spec, history=None, shipped=None, fallbacks=None):
        pairs = []
        base_day = dt.date.fromisoformat(spec['base'])
        if spec['calendar'] == 'utc':
            d = dt.date(2025, 12, 31)
            j = 0
            while d <= e2e_cutoff:
                stamp = int(dt.datetime(d.year, d.month, d.day, 12, tzinfo=dt.timezone.utc).timestamp())
                pairs.append((stamp, 90000 + j))
                d += dt.timedelta(days=1); j += 1
        else:
            for i, d in enumerate(e2e_nyse_days):
                stamp = int(dt.datetime(d.year, d.month, d.day, 12, tzinfo=sw.NY).timestamp())
                close = 100.0 if d == base_day else 100 + i
                if spec['yahoo'] == 'TSLA' and d == dt.date(2026, 1, 6):
                    close = None
                pairs.append((stamp, close))
        return cd.closes_from_pairs(spec['yahoo'], pairs, spec['calendar'], history, shipped, fallbacks)

    _real_fetch = cd.fetch_yahoo
    cd.fetch_yahoo = _stub_fetch
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc_e2e = cd.main(['--history', e2e_hist, '--shipped', e2e_ship_missing,
                              '--pack', e2e_pack, '--out', e2e_out, '--weekly-dir', td5, '--now', e2e_now])
        e2e_log = buf.getvalue()
        chk('e2e null filled from history writes', rc_e2e == 0, e2e_log)
        e2e_doc = json.load(open(e2e_out))
        chk('e2e TSLA Jan 6 is the history value',
            e2e_doc['symbols']['TSLA']['closes'][e2e_doc['symbols']['TSLA']['dates'].index('2026-01-06')] == 103.0)
        chk('e2e FALLBACK line printed', 'FALLBACK TSLA: 2026-01-06 close 103.0 from site history' in e2e_log, e2e_log)
        chk('e2e all 19 symbols built', set(cd.ORDER) <= set(e2e_doc['symbols']))
        os.remove(e2e_out)
        buf2 = io.StringIO()
        with contextlib.redirect_stdout(buf2), contextlib.redirect_stderr(buf2):
            rc_e2e2 = cd.main(['--shipped', e2e_ship_missing,
                               '--pack', e2e_pack, '--out', e2e_out, '--weekly-dir', td5, '--now', e2e_now])
        chk('e2e without history fails loud', rc_e2e2 == 1, buf2.getvalue())
        chk('e2e without history writes nothing', not os.path.exists(e2e_out))
    finally:
        cd.fetch_yahoo = _real_fetch
finally:
    shutil.rmtree(td5)

print('cmp daily checks', n, 'fail', f)
sys.exit(1 if f else 0)
