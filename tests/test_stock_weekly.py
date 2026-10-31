#!/usr/bin/env python3
"""tools/stock_weekly.py — offline fixtures plus shipped-file invariants. No network."""
import datetime as dt, json, os, shutil, subprocess, sys, tempfile
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, 'tools'))
import stock_weekly as S

FIX = os.path.join(R, 'tests/fixtures/stock_weekly')
n = f = 0
def chk(name, ok, info=''):
    global n, f
    n += 1
    f += (not ok)
    print(('PASS' if ok else 'FAIL'), name, '' if ok else info)

def run_cli(args):
    p = subprocess.run([sys.executable, os.path.join(R, 'tools/stock_weekly.py')] + args, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr

# --- CLI fixture: TSLA through Sat 10 Jan 2026 ---
td = tempfile.mkdtemp(prefix='sw-')
try:
    code, out, err = run_cli(['--fixture', os.path.join(FIX, 'bars.json'), '--pack', os.path.join(FIX, 'pack.json'), '--out-dir', td])
    chk('fixture CLI exit 0', code == 0, err)
    doc = json.load(open(os.path.join(td, 'stock-weekly-TSLA.json')))
    chk('TSLA two weeks', len(doc['weeks']) == 2, doc['weeks'])
    w0, w1 = doc['weeks']
    chk('first week is Mon 29 Dec, 1 day, Jan 2 only', w0['monday'] == '2025-12-29' and w0['sunday'] == '2026-01-04' and w0['days'] == 1 and w0['close'] == 452.25)
    chk('first candle open is 2 Jan open, not the 31 Dec baseline', w0['open'] == 448.10 and doc['baseClose'] == 449.72)
    chk('second week Mon 5 Jan, 5 days', w1['monday'] == '2026-01-05' and w1['days'] == 5 and w1['open'] == 453.00 and w1['close'] == 460.50)
    chk('week high is max, low is min', w1['high'] == 462.50 and w1['low'] == 449.80)
    chk('Saturday run is a finished week', doc['inProgress'] is None and doc['asOf'] == '2026-01-09')
    chk('unit and basis', doc['unit'] == 'usd' and doc['basis'] == 'ytd')
    chk('31 Dec is not inside a candle session count', w0['days'] == 1)
    first_bytes = open(os.path.join(td, 'stock-weekly-TSLA.json'), 'rb').read()
    code2, out2, err2 = run_cli(['--fixture', os.path.join(FIX, 'bars.json'), '--pack', os.path.join(FIX, 'pack.json'), '--out-dir', td])
    second_bytes = open(os.path.join(td, 'stock-weekly-TSLA.json'), 'rb').read()
    chk('idempotent second run', code2 == 0 and first_bytes == second_bytes, err2)
finally:
    shutil.rmtree(td, ignore_errors=True)

# Friday afternoon: drop the unfinished session, flag the week.
bars = json.load(open(os.path.join(FIX, 'bars.json')))
pack = json.load(open(os.path.join(FIX, 'pack.json')))
rows = {r['symbol']: dict(r, _packAsOf=pack['asOf']) for r in pack['rows']}
raw = S.bars_from_fixture_rows('TSLA', bars['symbols']['TSLA'])
fri = S.build_doc('TSLA', raw, '2026-01-09T15:00:00-05:00', rows['TSLA'])
chk('Friday 15:00 drops the partial day', fri['asOf'] == '2026-01-08' and fri['weeks'][-1]['days'] == 4 and fri['weeks'][-1]['close'] == 455.00)
chk('Friday 15:00 week in progress', isinstance(fri['inProgress'], str) and 'not finished' in fri['inProgress'])
done = S.build_doc('TSLA', raw, '2026-01-09T16:15:00-05:00', rows['TSLA'])
chk('Friday 16:15 keeps the close and finishes the week', done['asOf'] == '2026-01-09' and done['inProgress'] is None and done['weeks'][-1]['days'] == 5)

# Missing session must fail and must not be filled in.
gap = [r for r in bars['symbols']['TSLA'] if r['date'] != '2026-01-07']
try:
    S.build_doc('TSLA', S.bars_from_fixture_rows('TSLA', gap), '2026-01-10T11:00:00-05:00', rows['TSLA'])
    chk('missing 7 Jan raises', False)
except RuntimeError as e:
    chk('missing 7 Jan raises', '2026-01-07' in str(e), str(e))

# Bad OHLC never becomes a candle.
bad = [dict(r) for r in bars['symbols']['TSLA']]
bad[2] = dict(bad[2], high=100.0, close=458.0)
try:
    S.bars_from_fixture_rows('TSLA', bad)
    chk('high < close rejected', False)
except RuntimeError as e:
    chk('high < close rejected', 'inconsistent' in str(e), str(e))

# Baseline disagreement with the pack aborts.
wrong = dict(rows['TSLA'], baseClose=1.0)
try:
    S.build_doc('TSLA', raw, '2026-01-10T11:00:00-05:00', wrong)
    chk('pack baseline mismatch raises', False)
except RuntimeError as e:
    chk('pack baseline mismatch raises', 'baseline' in str(e), str(e))

# Shared asOf: last close must equal the pack price, else the validator complains.
match = dict(rows['TSLA'], _packAsOf='2026-01-09', price=460.50)
chk('validator accepts last close when asOf matches pack', S.validate_doc(done, match) == [], S.validate_doc(done, match))
mismatch = dict(rows['TSLA'], _packAsOf='2026-01-09', price=999.0)
got = S.validate_doc(done, mismatch)
chk('validator flags last close when asOf matches and price differs', any('last close' in x for x in got), got)
other = S.validate_doc(done, rows['TSLA'])
chk('different asOf does not force pack price equality', not any('last close' in x for x in other), other)

# SPCX: listing week, open is not the baseline, Juneteenth week is 4 days and finished on the 20th.
td2 = tempfile.mkdtemp(prefix='sw2-')
try:
    code, out, err = run_cli(['--fixture', os.path.join(FIX, 'bars_spcx.json'), '--pack', os.path.join(FIX, 'pack.json'), '--out-dir', td2])
    chk('SPCX fixture CLI exit 0', code == 0, err)
    sp = json.load(open(os.path.join(td2, 'stock-weekly-SPCX.json')))
    chk('SPCX title data starts week of 8 Jun, one day', sp['weeks'][0]['monday'] == '2026-06-08' and sp['weeks'][0]['days'] == 1 and sp['weeks'][0]['sunday'] == '2026-06-14')
    chk('SPCX first open is the first trade, not the listing close', sp['weeks'][0]['open'] == 155.00 and sp['weeks'][0]['close'] == 160.95 == sp['baseClose'])
    chk('SPCX no week before listing', all(w['monday'] >= '2026-06-08' for w in sp['weeks']))
    chk('Juneteenth week is 4 days and not in progress on Sat 20 Jun', sp['weeks'][1]['monday'] == '2026-06-15' and sp['weeks'][1]['days'] == 4 and sp['inProgress'] is None and sp['asOf'] == '2026-06-18')
    chk('SPCX basis listing', sp['basis'] == 'listing' and sp['baseLabel'] == 'Listing close')
finally:
    shutil.rmtree(td2, ignore_errors=True)

# DST: 09:30 ET stays on that calendar date on both sides of the 2026 transitions.
# 8 Mar 2026 is the spring-forward Sunday. Monday 9 Mar 09:30 EDT = 13:30 UTC.
# 1 Nov 2026 is the fall-back Sunday. Monday 2 Nov 09:30 EST = 14:30 UTC.
def payload(pairs):
    return {'meta': {'currency': 'USD'}, 'timestamp': [t for t, _ in pairs],
            'indicators': {'quote': [{'open': [10], 'high': [11], 'low': [9], 'close': [10.5]}] if False else
                           [{'open': [b[0] for _, b in pairs], 'high': [b[1] for _, b in pairs],
                             'low': [b[2] for _, b in pairs], 'close': [b[3] for _, b in pairs]}]}}
# rebuild properly
def one(ts, o=10, h=11, l=9, c=10.5):
    return {'meta': {'currency': 'USD', 'symbol': 'TSLA'}, 'timestamp': [ts],
            'indicators': {'quote': [{'open': [o], 'high': [h], 'low': [l], 'close': [c]}], 'adjclose': [{'adjclose': [1.0]}]}}
edt = int(dt.datetime(2026, 3, 9, 13, 30, tzinfo=dt.timezone.utc).timestamp())
est = int(dt.datetime(2026, 11, 2, 14, 30, tzinfo=dt.timezone.utc).timestamp())
bars_dst = S.bars_from_yahoo_payload('TSLA', {'meta': {'currency': 'USD'}, 'timestamp': [edt, est],
    'indicators': {'quote': [{'open': [10, 12], 'high': [11, 13], 'low': [9, 11], 'close': [10.5, 12.5]}],
                   'adjclose': [{'adjclose': [999, 999]}]}})
chk('EDT bar lands on 9 Mar not the UTC previous day', dt.date(2026, 3, 9) in bars_dst and bars_dst[dt.date(2026, 3, 9)]['close'] == 10.5)
chk('EST bar lands on 2 Nov', dt.date(2026, 11, 2) in bars_dst and bars_dst[dt.date(2026, 11, 2)]['close'] == 12.5)
chk('adjclose 999 was not used', all(b['close'] != 999 for b in bars_dst.values()))
# A timestamp an hour before the spring session, if naively read as UTC date, is still 9 Mar
# (04:00Z). Read as ET it is 00:00 EDT 9 Mar... 04:00 UTC = 00:00 EDT. Use 03:30 UTC = 23:30 EDT previous day.
late = int(dt.datetime(2026, 3, 9, 3, 30, tzinfo=dt.timezone.utc).timestamp())
late_bars = S.bars_from_yahoo_payload('TSLA', one(late))
chk('03:30Z on 9 Mar is still 8 Mar in ET', dt.date(2026, 3, 8) in late_bars and dt.date(2026, 3, 9) not in late_bars)

# CLI failure leaves no file.
td3 = tempfile.mkdtemp(prefix='sw3-')
try:
    broken = json.loads(json.dumps(bars))
    broken['symbols']['TSLA'] = [r for r in broken['symbols']['TSLA'] if r['date'] != '2026-01-06']
    bf = os.path.join(td3, 'bad.json')
    json.dump(broken, open(bf, 'w'))
    marker = os.path.join(td3, 'out')
    os.makedirs(marker)
    pre = os.listdir(marker)
    code, out, err = run_cli(['--fixture', bf, '--pack', os.path.join(FIX, 'pack.json'), '--out-dir', marker])
    chk('bad fixture exits 1', code == 1, err)
    chk('bad fixture writes nothing', os.listdir(marker) == pre, os.listdir(marker))
    chk('stderr says not writing', 'not writing' in err.lower() or 'no files written' in err.lower(), err)
finally:
    shutil.rmtree(td3, ignore_errors=True)

# Shipped files: structural validator, plus day counts derived from the
# same holiday calendar the generator uses (so a Friday regen still passes).
pack_live, pack_rows = S.load_pack(os.path.join(R, 'assets/data/screener-pack.json'))
shipped_n = 0
for sym in S.SYMS:
    path = os.path.join(R, 'assets/data', f'stock-weekly-{sym}.json')
    if not os.path.exists(path):
        continue
    shipped_n += 1
    doc = json.load(open(path))
    bad = S.validate_doc(doc, pack_rows[sym])
    chk(f'shipped {sym} validates', bad == [], bad)
    asof = dt.date.fromisoformat(doc['asOf'])
    now = dt.datetime(asof.year, asof.month, asof.day, 21, 0, tzinfo=S.NY)
    rem = S.remaining_in_week(asof, now)
    chk(f'{sym} inProgress matches a 21:00 ET reading of asOf', (doc['inProgress'] is None) == (not rem), (doc['inProgress'], rem))
    by = {w['monday']: w for w in doc['weeks']}
    # Every week after the partial first week, through the last, has exactly
    # the sessions the calendar predicts. No invented and no skipped days.
    for w in doc['weeks'][1:]:
        mon = dt.date.fromisoformat(w['monday'])
        if sym == 'SPCX':
            exp = len(S.expected_sessions(mon, min(mon + dt.timedelta(days=6), asof)))
        else:
            exp = len(S.expected_sessions(max(mon, dt.date(2026, 1, 2)), min(mon + dt.timedelta(days=6), asof)))
        chk(f'{sym} {w["monday"]} days {exp}', w['days'] == exp, w['days'])
    if sym == 'SPCX':
        w0 = doc['weeks'][0]
        chk('SPCX week of 8 Jun is the one listing day', w0['monday'] == '2026-06-08' and w0['days'] == 1 and w0['close'] == doc['baseClose'])
        chk('SPCX keeps the first-trade open distinct in the file', 'open' in w0 and isinstance(w0['open'], float))
        # The open is allowed to equal the close; it must not be overwritten by the baseline
        # unless that really was the first print. Recorded for the audit.
        print(f'  NOTE SPCX first-trade open {w0["open"]} vs listing close {doc["baseClose"]}')
    else:
        w0 = doc['weeks'][0]
        chk(f'{sym} partial first week', w0['monday'] == '2025-12-29' and w0['days'] == 1 and w0['close'] != doc['baseClose'])
if shipped_n == len(S.SYMS):
    code, out, err = run_cli(['--check-only', '--out-dir', os.path.join(R, 'assets/data'), '--pack', os.path.join(R, 'assets/data/screener-pack.json')])
    chk('--check-only on shipped files', code == 0, err)
elif shipped_n == 0:
    print('NOTE shipped JSON not in tree yet; structural fixture tests still ran')
else:
    chk('all seven shipped files present', False, shipped_n)

print('STOCK_WEEKLY TESTS', n, 'FAIL', f)
sys.exit(1 if f else 0)
