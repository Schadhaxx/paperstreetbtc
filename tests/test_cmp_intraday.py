#!/usr/bin/env python3
"""tools/cmp_intraday.py — offline fixtures. No network.

Covers: the ET gate (in-session / before open / after 4:15 / weekend /
holiday / early close, EST + EDT), the expected-session rule (today
once the session is underway, otherwise the last trading day strictly
before today), the 2d Yahoo payload filter (latest session in the
9:30 AM-4 PM ET window; GC=F's out-of-window bars and null
maintenance-break bars dropped, its 21:59:57 final bar dropped; a null
bar INSIDE the window fails the symbol; inconsistent OHLC fails; a
session older than the expected session is stale, not a session), the
document build (mixed sessions: an older symbol is failed, never
published as the current session; all failed builds nothing), the
document validator (bad v/kind/asOf, bars outside the window or on the
wrong date, bars out of order, failed-list mismatch, missing symbol),
and the CLI end to end on fixtures (writes a valid file; --validate
passes; --check-only writes nothing; one bad symbol still publishes
the other two; all bad writes nothing, exit 1).

The fixture sessions are synthetic: Friday 20 Nov 2026, 9:30 AM-4 PM
ET (14:30-21:00 UTC, EST), 27 bars, built programmatically — the
shape is the Yahoo `range=2d&interval=15m` payload verified live on
22 Nov 2026 (^GSPC/MSTR 27 clean bars; GC=F 69 bars over its futures
day with the nulls outside the window).
"""
import datetime as dt, json, os, shutil, subprocess, sys, tempfile, time
from zoneinfo import ZoneInfo
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, 'tools'))
import cmp_intraday as C
import stock_weekly as SW

NY = ZoneInfo('America/New_York')
UTC = dt.timezone.utc
n = f = 0

def test_tmpdir():
    """A temp dir under the workspace (.pstmp, the run_all convention),
    not the system /tmp — /tmp is intermittently unusable in this
    sandbox (EPERM waves / cleanups) and tempfile then fails outright.
    Retries the mkdir while a wave passes."""
    base = os.path.join(os.path.dirname(R), '.pstmp')
    last = None
    for _ in range(30):
        try:
            os.makedirs(base, exist_ok=True)
            return tempfile.TemporaryDirectory(dir=base)
        except (PermissionError, FileNotFoundError, OSError) as e:
            last = e
            time.sleep(2)
    return tempfile.TemporaryDirectory()

def dump_json(path, obj):
    """Write a JSON file with retries: exec'd python writes hit the
    intermittent EPERM wave in this sandbox, which can leave a 0-byte
    file (open truncates, the write fails). Retry until the file reads
    back non-empty."""
    text = json.dumps(obj)
    last = None
    for _ in range(60):
        try:
            with open(path, 'w') as fh:
                fh.write(text)
                fh.flush()
                os.fsync(fh.fileno())
            if os.path.getsize(path) > 0:
                return
        except (PermissionError, FileNotFoundError, OSError) as e:
            last = e
            time.sleep(2)
    raise RuntimeError(f'could not write {path}: {last}')

def chk(name, ok, info=''):
    global n, f
    n += 1
    f += (not ok)
    print(('PASS' if ok else 'FAIL'), name, '' if ok else info)

def run_cli(args):
    p = subprocess.run([sys.executable, os.path.join(R, 'tools/cmp_intraday.py')] + args,
                       capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr

# --- synthetic Yahoo 15m payloads ---

def session_payload(base_price, day='2026-11-20', extra_before=True, extra_after=True, null_break=True):
    """Yahoo-payload dict for one full NYSE session plus GC=F-style extras.

    The session is 27 bars, 9:30 AM-4 PM ET (14:30-21:00 UTC in EST).
    Extras (dropped by the window filter): bars from midnight ET
    (05:00 UTC) to 9:15 AM, bars after the close (4:15/4:30/4:45 PM ET
    plus a 4:59:57 PM odd bar), and null bars at 10-10:45 PM ET (the
    futures maintenance break).
    """
    ts, o, h, l, c = [], [], [], [], []
    def bar(t_utc, price, null=False):
        ts.append(int(t_utc.timestamp()))
        if null:
            o.append(None); h.append(None); l.append(None); c.append(None)
        else:
            o.append(round(price, 2)); h.append(round(price * 1.001, 2))
            l.append(round(price * 0.999, 2)); c.append(round(price * 1.0005, 2))
    start = dt.datetime.fromisoformat(day + 'T05:00:00+00:00')
    if extra_before:
        t = start
        while t < dt.datetime.fromisoformat(day + 'T14:30:00+00:00'):
            bar(t, base_price); t += dt.timedelta(minutes=15)
    t = dt.datetime.fromisoformat(day + 'T14:30:00+00:00')
    for i in range(27):
        bar(t, base_price + i * 0.5); t += dt.timedelta(minutes=15)
    if extra_after:
        for mins in (15, 30, 45):
            bar(dt.datetime.fromisoformat(day + 'T21:00:00+00:00') + dt.timedelta(minutes=mins), base_price + 20)
        bar(dt.datetime.fromisoformat(day + 'T21:59:57+00:00'), base_price + 21)
    if null_break:
        t = dt.datetime.fromisoformat(day + 'T22:00:00-05:00')
        for _ in range(4):
            bar(t, base_price, null=True); t += dt.timedelta(minutes=15)
    return {'timestamp': ts, 'indicators': {'quote': [{'open': o, 'high': h, 'low': l, 'close': c}]}}

def friday_payloads():
    return {'SPX': session_payload(6800.0, extra_before=False, extra_after=False, null_break=False),
            'GOLD': session_payload(4200.0),
            'MSTR': session_payload(150.0, extra_before=False, extra_after=False, null_break=False)}

# --- gate ---

def gate(now_iso):
    code, out, err = run_cli(['--gate', '--now', now_iso])
    d = {}
    for line in out.splitlines():
        if '=' in line and line.split('=')[0] in ('run', 'final'):
            d[line.split('=')[0]] = line.split('=')[1]
    return code, d.get('run'), d.get('final'), out

code, run, final, _ = gate('2026-11-20T14:00:00-05:00')
chk('gate: Fri 2 PM ET in session', code == 0 and run == '1' and final == '0', (code, run, final))
code, run, final, _ = gate('2026-11-20T08:00:00-05:00')
chk('gate: Fri 8 AM ET before open skips', code == 0 and run == '0', (code, run))
code, run, final, _ = gate('2026-11-20T16:10:00-05:00')
chk('gate: Fri 4:10 PM ET in the final-tick window', code == 0 and run == '1', (code, run))
code, run, final, _ = gate('2026-11-20T17:00:00-05:00')
chk('gate: Fri 5 PM ET after the window skips', code == 0 and run == '0', (code, run))
code, run, final, _ = gate('2026-11-21T14:00:00-05:00')
chk('gate: Saturday skips', code == 0 and run == '0', (code, run))
code, run, final, _ = gate('2026-11-26T14:00:00-05:00')
chk('gate: Thanksgiving (holiday) skips', code == 0 and run == '0', (code, run))
code, run, final, _ = gate('2026-11-27T13:00:00-05:00')
chk('gate: early-close Fri 1 PM ET in session', code == 0 and run == '1', (code, run))
code, run, final, _ = gate('2026-11-27T14:00:00-05:00')
chk('gate: early-close Fri 2 PM ET skips', code == 0 and run == '0', (code, run))
code, run, final, _ = gate('2026-07-15T14:00:00-04:00')
chk('gate: Jul 2 PM EDT in session', code == 0 and run == '1', (code, run))
code, run, final, _ = gate('2026-07-15T22:00:00-04:00')
chk('gate: Jul 10 PM EDT outside skips', code == 0 and run == '0', (code, run))

# --- prev_trading_day / expected_session ---

chk('prev trading day Mon -> Mon (on-or-before)', C.prev_trading_day(dt.date(2026, 11, 23)).isoformat() == '2026-11-23')
chk('prev trading day Sat -> Fri', C.prev_trading_day(dt.date(2026, 11, 21)).isoformat() == '2026-11-20')
chk('prev trading day Thanksgiving -> Wed', C.prev_trading_day(dt.date(2026, 11, 26)).isoformat() == '2026-11-25')
chk('prev trading day Fri after Thanksgiving -> Fri', C.prev_trading_day(dt.date(2026, 11, 27)).isoformat() == '2026-11-27')

def exp_session(iso):
    return C.expected_session(SW.parse_now(iso)).isoformat()

chk('expected session Mon 8 AM -> Fri', exp_session('2026-11-23T08:00:00-05:00') == '2026-11-20')
chk('expected session Mon 2 PM -> Mon', exp_session('2026-11-23T14:00:00-05:00') == '2026-11-23')
chk('expected session Tue 8 AM -> Mon', exp_session('2026-11-24T08:00:00-05:00') == '2026-11-23')
chk('expected session Sat 9:15 AM -> Fri', exp_session('2026-11-21T09:15:00-05:00') == '2026-11-20')
chk('expected session Thanksgiving 2 PM -> Wed', exp_session('2026-11-26T14:00:00-05:00') == '2026-11-25')
chk('expected session Fri 9:15 AM -> Thu', exp_session('2026-11-20T09:15:00-05:00') == '2026-11-19')

# --- bars_from_payload ---

fri_after_close = SW.parse_now('2026-11-20T21:15:00Z')
mon_pre_open = SW.parse_now('2026-11-23T08:00:00-05:00')
tue_afternoon = SW.parse_now('2026-11-24T14:00:00-05:00')
fx = friday_payloads()
s, bars = C.bars_from_payload('^GSPC', fx['SPX'], fri_after_close)
chk('SPX: latest session Fri, 27 bars', s == '2026-11-20' and len(bars) == 27, (s, len(bars)))
chk('SPX: first bar 9:30 AM ET (14:30 UTC)', bars[0][0] == int(dt.datetime(2026, 11, 20, 14, 30, tzinfo=UTC).timestamp()) * 1000, bars[0])
chk('SPX: last bar 4:00 PM ET (21:00 UTC)', bars[-1][0] == int(dt.datetime(2026, 11, 20, 21, 0, tzinfo=UTC).timestamp()) * 1000, bars[-1])
s, bars = C.bars_from_payload('GC=F', fx['GOLD'], fri_after_close)
chk('GOLD: extras + null break dropped, still 27 bars', s == '2026-11-20' and len(bars) == 27, (s, len(bars)))
chk('GOLD: no nulls in the window', all(all(v is not None for v in b[1:]) for b in bars))
chk('GOLD: bars rounded to 2 decimals', all(b[1] == round(b[1], 2) for b in bars))
s, bars = C.bars_from_payload('MSTR', fx['MSTR'], fri_after_close)
chk('MSTR: 27 bars', s == '2026-11-20' and len(bars) == 27, (s, len(bars)))

# Null bar INSIDE the window fails the symbol.
bad = session_payload(6800.0, extra_before=False, extra_after=False, null_break=False)
bad['indicators']['quote'][0]['close'][10] = None
try:
    C.bars_from_payload('^GSPC', bad, fri_after_close)
    chk('null close inside the window fails', False, 'no raise')
except RuntimeError as e:
    chk('null close inside the window fails', 'null OHLC' in str(e), str(e))

# Inconsistent OHLC inside the window fails the symbol.
bad2 = session_payload(6800.0, extra_before=False, extra_after=False, null_break=False)
bad2['indicators']['quote'][0]['high'][5] = 100.0  # below open/close
try:
    C.bars_from_payload('^GSPC', bad2, fri_after_close)
    chk('inconsistent OHLC inside the window fails', False, 'no raise')
except RuntimeError as e:
    chk('inconsistent OHLC inside the window fails', 'inconsistent' in str(e), str(e))

# No bars in the window at all fails the symbol.
empty = {'timestamp': [int(dt.datetime(2026, 11, 20, 5, 0, tzinfo=UTC).timestamp())],
         'indicators': {'quote': [{'open': [1.0], 'high': [1.0], 'low': [1.0], 'close': [1.0]}]}}
try:
    C.bars_from_payload('^GSPC', empty, fri_after_close)
    chk('no window bars fails', False, 'no raise')
except RuntimeError as e:
    chk('no window bars fails', 'no 15-minute bars' in str(e), str(e))

# Session older than the expected session is stale, not a session.
# Today is Tue 24 Nov, 2 PM; the payload only has Fri 20 Nov (Mon 23 missing).
try:
    C.bars_from_payload('^GSPC', fx['SPX'], tue_afternoon)
    chk('session older than expected is stale', False, 'no raise')
except RuntimeError as e:
    chk('session older than expected is stale', 'stale data' in str(e), str(e))
# ... but Friday bars on Monday morning are the last session, not stale.
s, bars = C.bars_from_payload('^GSPC', fx['SPX'], mon_pre_open)
chk('Friday bars on Monday morning are the last session', s == '2026-11-20' and len(bars) == 27, (s, len(bars)))

# --- build + validate ---

now_et = SW.parse_now('2026-11-20T21:15:00Z')
results = {k: C.bars_from_payload(C.SYMBOLS[k], fx[k], fri_after_close) for k in ('SPX', 'GOLD', 'MSTR')}
doc = C.build_cmp_doc(now_et, results)
chk('doc: session Fri, 3 symbols, none failed', doc['session'] == '2026-11-20' and doc['failed'] == [] and len(doc['symbols']) == 3, doc)
chk('doc: asOf + sessionOpen set', doc['asOf'] == '2026-11-20T21:15:00Z' and doc['sessionOpen'] is False, doc)
chk('doc: validates clean', C.validate_cmp_doc(doc) == [], C.validate_cmp_doc(doc))

# Mixed sessions: GOLD's session is Thursday, the others Friday — GOLD is
# failed in the file, never published as Friday's session. (Thursday's
# bars are parsed with Thursday's clock, so the staleness check passes;
# the mix is then assembled under Friday's clock, as a lagging fetch
# would produce it.)
thu = session_payload(4200.0, day='2026-11-19')
results2 = dict(results)
results2['GOLD'] = C.bars_from_payload('GC=F', thu, SW.parse_now('2026-11-19T21:15:00Z'))
doc2 = C.build_cmp_doc(now_et, results2)
chk('mixed sessions: older symbol failed, not published as current',
    doc2['symbols']['GOLD'] == {'status': 'failed'} and doc2['failed'] == ['GOLD'] and 'bars' in doc2['symbols']['SPX'], doc2)
chk('mixed sessions doc still validates', C.validate_cmp_doc(doc2) == [], C.validate_cmp_doc(doc2))

# All failed builds nothing.
try:
    C.build_cmp_doc(now_et, {'SPX': None, 'GOLD': None, 'MSTR': None})
    chk('all failed builds nothing', False, 'no raise')
except RuntimeError as e:
    chk('all failed builds nothing', 'no symbol produced bars' in str(e), str(e))

def mutated(**kw):
    import copy
    d = copy.deepcopy(doc)
    for k, v in kw.items():
        d[k] = v
    return d

chk('validate: bad v', C.validate_cmp_doc(mutated(v=2)) != [])
chk('validate: bad kind', C.validate_cmp_doc(mutated(kind='desk-live')) != [])
chk('validate: bad asOf', C.validate_cmp_doc(mutated(asOf='yesterday')) != [])
chk('validate: bad session', C.validate_cmp_doc(mutated(session='2026-13-40')) != [])
chk('validate: missing symbol', (lambda d: C.validate_cmp_doc(d) != [])(dict(doc, symbols={'SPX': doc['symbols']['SPX']})))
chk('validate: failed list must match', C.validate_cmp_doc(mutated(failed=['SPX'])) != [])
bad_bar = json.loads(json.dumps(doc))
bad_bar['symbols']['SPX']['bars'][3][0] = bad_bar['symbols']['SPX']['bars'][2][0]  # duplicate time
chk('validate: bars out of order', C.validate_cmp_doc(bad_bar) != [])
bad_bar2 = json.loads(json.dumps(doc))
bad_bar2['symbols']['SPX']['bars'][0][0] -= 86400000  # previous day
chk('validate: bar on the wrong date', C.validate_cmp_doc(bad_bar2) != [])
bad_bar3 = json.loads(json.dumps(doc))
bad_bar3['symbols']['SPX']['bars'][0][0] = int(dt.datetime(2026, 11, 20, 5, 0, tzinfo=UTC).timestamp()) * 1000  # midnight ET
chk('validate: bar outside the window', C.validate_cmp_doc(bad_bar3) != [])
bad_bar4 = json.loads(json.dumps(doc))
bad_bar4['symbols']['GOLD'] = {'status': 'failed', 'bars': [[1, 2, 3, 4, 5]]}
chk('validate: failed entry must not carry bars', C.validate_cmp_doc(bad_bar4) != [])

# --- CLI end to end on fixtures ---

with test_tmpdir() as td:
    fxp = os.path.join(td, 'fx.json')
    dump_json(fxp, {'now': '2026-11-20T21:15:00Z', 'symbols': fx})
    outp = os.path.join(td, 'cmp-intraday.json')
    code, out, err = run_cli(['--fixture', fxp, '--out', outp])
    chk('CLI: fixture run writes the file, exit 0', code == 0 and os.path.exists(outp), (code, out, err))
    code, out, err = run_cli(['--validate', outp])
    chk('CLI: --validate passes on the written file', code == 0, (code, out, err))
    written = json.load(open(outp))
    chk('CLI: written file matches the built doc', written['session'] == '2026-11-20' and len(written['symbols']['SPX']['bars']) == 27, written)
    mtime = os.path.getmtime(outp)
    code, out, err = run_cli(['--fixture', fxp, '--out', outp, '--check-only'])
    chk('CLI: --check-only writes nothing', code == 0 and os.path.getmtime(outp) == mtime, (code, out, err))
    # One bad symbol: the file still publishes the other two, exit 0.
    fx_bad = {'now': '2026-11-20T21:15:00Z',
              'symbols': dict(fx, GOLD={'timestamp': [], 'indicators': {'quote': [{'open': [], 'high': [], 'low': [], 'close': []}]}})}
    fxp2 = os.path.join(td, 'fx2.json')
    dump_json(fxp2, fx_bad)
    outp2 = os.path.join(td, 'cmp2.json')
    code, out, err = run_cli(['--fixture', fxp2, '--out', outp2])
    w2 = json.load(open(outp2)) if os.path.exists(outp2) else {}
    chk('CLI: one bad symbol still publishes the other two',
        code == 0 and w2.get('failed') == ['GOLD'] and 'bars' in w2.get('symbols', {}).get('SPX', {}), (code, out, err, w2))
    code, out, err = run_cli(['--validate', outp2])
    chk('CLI: --validate passes on the partial file', code == 0, (code, out, err))
    # All bad: nothing written, exit 1.
    fx_all_bad = {'now': '2026-11-20T21:15:00Z', 'symbols': {k: {'timestamp': []} for k in ('SPX', 'GOLD', 'MSTR')}}
    fxp3 = os.path.join(td, 'fx3.json')
    dump_json(fxp3, fx_all_bad)
    outp3 = os.path.join(td, 'cmp3.json')
    code, out, err = run_cli(['--fixture', fxp3, '--out', outp3])
    chk('CLI: all bad writes nothing, exit 1', code == 1 and not os.path.exists(outp3), (code, out, err))
    # --validate on a corrupt file fails.
    badp = os.path.join(td, 'bad.json')
    dump_json(badp, {'v': 9, 'kind': 'cmp-intraday'})
    code, out, err = run_cli(['--validate', badp])
    chk('CLI: --validate fails on a corrupt file', code == 1, (code, out, err))

print(f'\n{n} checks, {f} failures')
sys.exit(1 if f else 0)
