#!/usr/bin/env python3
"""BP freeze/fallback/heal simulations (NO override machinery). Runs the REAL build_history()/history_stale() extracted from
.github/workflows/prices.yml, the real push-race merge snippet, and tools/btc_daily.py, against mocked feeds. No network
(except reading --history when it is a URL). Exit 1 on any failure.
usage: python3 tests/test_freeze.py [--repo DIR] [--history PATH_OR_URL]
Independent of the data state: the fixture is the given history with Oct 22 BTC set to Yahoo's final bar (81311.890625),
the canonical value under Option B, and provenance reset. Works with the live file and with any corrected copy."""
import argparse, copy, datetime as dt, json, os, re, subprocess, sys, tempfile, textwrap, urllib.request, zoneinfo
ap = argparse.ArgumentParser(); ap.add_argument('--repo', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
ap.add_argument('--history', default='https://raw.githubusercontent.com/Schadhaxx/paperstreetbtc/data/history.json'); a = ap.parse_args()
YML = open(os.path.join(a.repo, '.github/workflows/prices.yml')).read(); L = YML.split('\n')
i0 = next(i for i, l in enumerate(L) if 'import datetime as _dt, zoneinfo as _zi' in l); i1 = next(i for i, l in enumerate(L) if '# --- history end ---' in l)
G = {'json': json}; exec(textwrap.dedent('\n'.join(L[i0:i1])), G)
HH = G['HistoryHold']; ET = zoneinfo.ZoneInfo('America/New_York'); UTC = dt.timezone.utc
H0 = json.load(urllib.request.urlopen(a.history, timeout=30)) if a.history.startswith('http') else json.load(open(a.history))
D21, D22, D23 = '2026-10-21', '2026-10-22', '2026-10-23'
H0['closes'][D22]['BTC'] = 81311.890625; H0['fallback_sources'] = {}; H0['revisions_ignored'] = []; H0.pop('pending_review', None); H0.pop('refs_at_publish', None)   # fixture = Option B state
R = []
def chk(name, ok, info=''): R.append((name, bool(ok))); print('PASS' if ok else 'FAIL', name, '' if ok else info, flush=True)
SY = {'BTC-USD': 'BTC', 'MSTR': 'MSTR', 'STRC': 'STRC', 'TSLA': 'TSLA', 'PLTR': 'PLTR', 'SPY': 'SPY', 'QQQ': 'QQQ', 'BRK-B': 'BRK.B', 'GLD': 'GLD'}
N = lambda s: dt.datetime.fromisoformat(s).replace(tzinfo=UTC)
def feed(Y, CB=None, CG=None, META=None):
    def fetch(u):
        if 'finance.yahoo.com' in u:
            k = SY[u.split('/chart/')[1].split('?')[0]]; ts, cl = [], []
            for d in sorted(Y):
                if k not in Y[d]: continue
                t = dt.datetime.fromisoformat(d).replace(tzinfo=UTC) if k == 'BTC' else dt.datetime.fromisoformat(d).replace(hour=9, minute=30, tzinfo=ET)
                ts.append(int(t.timestamp())); cl.append(Y[d][k])
            m = {}
            if META and k in META:
                d, px = META[k]; m = {'regularMarketPrice': px, 'regularMarketTime': int(dt.datetime.fromisoformat(d).replace(hour=16, tzinfo=ET).timestamp())}
            return {'chart': {'result': [{'timestamp': ts, 'indicators': {'quote': [{'close': cl}]}, 'meta': m}]}}
        if 'coinbase.com' in u and CB is not None:
            return [[int(dt.datetime.fromisoformat(d).replace(tzinfo=UTC).timestamp()), 0, 0, 0, v, 0] for d, v in CB.items()]
        if 'coingecko.com' in u and CG is not None:
            d = (dt.datetime.strptime(u.split('date=')[1][:10], '%d-%m-%Y').date() - dt.timedelta(days=1)).isoformat()
            if d in CG: return {'market_data': {'current_price': {'usd': CG[d]}}}
        raise OSError('offline')
    return fetch
def Ycopy(h): return {d: dict(r) for d, r in h['closes'].items()}
def mk_stooq(ST): return lambda y, d: (ST or {}).get((y, d))
def run(prev, Y, now, CB=None, CG=None, quotes=None, ov=None, raw=None, META=None, ST=None):
    d = tempfile.mkdtemp(); old = os.getcwd(); os.chdir(d)
    try:
        if raw is not None: open('overrides.json', 'w').write(raw)
        elif ov is not None: json.dump(ov, open('overrides.json', 'w'))
        return G['build_history'](feed(Y, CB, CG, META), now, copy.deepcopy(prev), quotes or {}, stooq=mk_stooq(ST))
    finally: os.chdir(old)
def stale(h, now, ov=None, raw=None, Y=None, CB=None, ST=None):
    d = tempfile.mkdtemp(); old = os.getcwd(); os.chdir(d)
    try:
        if raw is not None: open('overrides.json', 'w').write(raw)
        elif ov is not None: json.dump(ov, open('overrides.json', 'w'))
        return G['history_stale'](h, now)
    finally: os.chdir(old)
def hold(fn):
    try: fn(); return None
    except HH as e: return str(e)
P = copy.deepcopy(H0); P['updated'] = '2026-10-23T20:30:25Z'                 # published 4:30 PM ET Oct 23
for d_ in [x for x in P['closes'] if x > D23]: del P['closes'][d_]       # v10: pin the fixture to that moment, whatever the live data branch says now
P['btc_provisional'] = [D23]                                                    # (at 4:30 PM ET Oct 23 the Oct 23 BTC UTC day was still open)
Y = Ycopy(P); Y[D22]['BTC'] = 81320.0; Y[D22]['MSTR'] = 145.9                # a later upstream revision of the final Oct 22 bar
T23 = int(N('2026-10-23T20:00:00').timestamp())

print('# 1 published PRIMARY final closes are frozen; revisions logged, not applied')
o = run(P, Y, N('2026-10-23T21:00:00'))
chk('1a frozen: Oct 22 BTC stays Yahoo final 81311.890625', o['closes'][D22]['BTC'] == 81311.890625, o['closes'][D22])
chk('1b frozen: Oct 22 MSTR kept', o['closes'][D22]['MSTR'] == P['closes'][D22]['MSTR'])
chk('1c revision log has both', {r['sym'] for r in o['revisions_ignored'] if r['date'] == D22} >= {'BTC', 'MSTR'}, o['revisions_ignored'])
chk('1d no other published value changed', all(o['closes'][d][k] == P['closes'][d][k] for d in P['closes'] if d != D23 for k in P['closes'][d]))

print('# 2 provisional / intraday never becomes final by freezing')
Y2 = Ycopy(P); Y2[D23]['BTC'] = 81500.0; Y2[D23]['GLD'] = 366.5
o = run(P, Y2, N('2026-10-23T21:00:00'))
chk('2a provisional BTC Oct 23 still provisional, re-pulled', D23 in o['btc_provisional'] and o['closes'][D23]['BTC'] == 81500.0)
chk('2b stock published before 8 PM ET is NOT frozen (settlement-size GLD revision taken)', abs(o['closes'][D23]['GLD'] - 366.5) < 1e-9 or o['closes'][D23]['GLD'] == P['closes'][D23]['GLD'], o['closes'][D23]['GLD'])
P2 = copy.deepcopy(P); P2['closes'][D23]['GLD'] = 366.5; P2['updated'] = '2026-10-23T23:30:00Z'
Y3 = Ycopy(P2); Y3[D23]['GLD'] = 366.4
o = run(P2, Y3, N('2026-10-24T00:30:00'))
chk('2c freeze needs a run at/after 8 PM ET to have published it (GLD 366.4 taken)', o['closes'][D23]['GLD'] == 366.4)
P3 = copy.deepcopy(o); Y4 = Ycopy(P3); Y4[D23]['GLD'] = 366.0
o = run(P3, Y4, N('2026-10-24T01:30:00'))
chk('2d after a post-cutoff publish the stock close is frozen', o['closes'][D23]['GLD'] == 366.4)
Y5 = Ycopy(P); Y5[D23]['BTC'] = 81000.0
o5 = run(P, Y5, N('2026-10-24T00:25:00'), CB={D23: 81010.0})
chk('2e provisional BTC turns final only via cross-check (Yahoo vs Coinbase)', D23 not in o5['btc_provisional'] and o5['closes'][D23]['BTC'] == 81000.0)
e = hold(lambda: run(P, Y5, N('2026-10-24T00:25:00'), CB={D23: 85000.0}))
chk('2f provisional->final with sources disagreeing (>0.5%) holds', e and 'differ' in e, e)

print('# 3 a FALLBACK value never freezes; the primary final bar replaces it, then it freezes (Option B root cause)')
Pf = copy.deepcopy(P); Pf['closes'][D22]['BTC'] = 81307.16; Pf['fallback_sources'] = {D22: {'BTC': 'coinbase'}}
Yn = Ycopy(P); del Yn[D22]['BTC']                                       # Yahoo bar still null
o = run(Pf, Yn, N('2026-10-23T21:00:00'), CB={D22: 81307.16})
chk('3a while Yahoo is null the Coinbase fallback is kept and stays marked (not frozen)', o['closes'][D22]['BTC'] == 81307.16 and o['fallback_sources'][D22]['BTC'] == 'coinbase', o['fallback_sources'].get(D22))
Pms = copy.deepcopy(P); Pms['closes'][D22]['MSTR'] = 145.8; Pms['fallback_sources'] = {D22: {'MSTR': 'yahoo-meta'}}; Yms = Ycopy(P); del Yms[D22]['MSTR']
e_ = hold(lambda: run(Pms, Yms, N('2026-10-23T21:00:00')))
o_ms = run(Pms, Yms, N('2026-10-23T21:00:00')) if e_ is None else None
chk('3a2 stock fallback (yahoo-meta) is kept and stays marked while Yahoo\'s bar is null (no hold)', e_ is None and o_ms['closes'][D22]['MSTR'] == 145.8 and o_ms['fallback_sources'][D22]['MSTR'] == 'yahoo-meta', e_)
o = run(Pf, Ycopy(P), N('2026-10-23T21:00:00'), CB={D22: 81307.16})        # Yahoo final bar appears (81311.890625)
chk('3b Yahoo final bar replaces the Coinbase fallback (cross-checked)', o['closes'][D22]['BTC'] == 81311.890625 and 'BTC' not in o['fallback_sources'].get(D22, {}), (o['closes'][D22]['BTC'], o['fallback_sources'].get(D22)))
chk('3c replacement logged', any('replaced by primary' in r['src'] for r in o['revisions_ignored']), o['revisions_ignored'])
Yr = Ycopy(P); Yr[D22]['BTC'] = 81330.0
o2 = run(o, Yr, N('2026-10-23T21:10:00'))
chk('3d ... then it freezes (a later Yahoo revision is ignored)', o2['closes'][D22]['BTC'] == 81311.890625)
o3 = run(Pf, Yn, N('2026-10-30T21:00:00'), CB={D22: 81307.16})
chk('3e a fallback never freezes by age (still marked after a week)', o3['fallback_sources'][D22]['BTC'] == 'coinbase')
Pm = copy.deepcopy(P); Pm['closes'][D22]['MSTR'] = 145.8; Pm['fallback_sources'] = {D22: {'MSTR': 'yahoo-meta'}}
o = run(Pm, Ycopy(P), N('2026-10-23T21:00:00'), ST={('MSTR', D22): P['closes'][D22]['MSTR']})
chk('3f stock yahoo-meta fallback replaced by the Yahoo bar (confirmed by Stooq)', o['closes'][D22]['MSTR'] == P['closes'][D22]['MSTR'] and o['fallback_sources'].get(D22, {}).get('MSTR', 'yahoo') == 'yahoo', o['fallback_sources'].get(D22))
Pu = copy.deepcopy(P); Pu['fallback_sources'] = {D22: {'BTC': 'yahoo-unchecked'}}
o = run(Pu, Y, N('2026-10-23T21:00:00'), CB={D22: 81315.0})
chk('3g single-source (unchecked) Yahoo value is re-checked, not frozen', o['closes'][D22]['BTC'] == 81320.0 and o['fallback_sources'].get(D22, {}).get('BTC', 'yahoo') == 'yahoo', (o['closes'][D22]['BTC'], o['fallback_sources'].get(D22)))
o = run(Pu, Y, N('2026-10-26T21:00:00'))
chk('3h unchecked PRIMARY value freezes after ~3 days', o['closes'][D22]['BTC'] == 81311.890625)
Pc = copy.deepcopy(P); Pc['fallback_sources'] = {D22: {'BTC': 'coinbase-unchecked'}}
o = run(Pc, Yn, N('2026-10-27T21:00:00'))
chk('3i unchecked FALLBACK never freezes by age', o['fallback_sources'][D22]['BTC'].startswith('coinbase'))

print('# 4 bad first values never get published')
Pn = copy.deepcopy(P); del Pn['closes'][D23]; Pn['btc_provisional'] = []; Pn['updated'] = '2026-10-23T12:00:00Z'
for bad, lab in [(0.0, 'zero'), (float('nan'), 'NaN'), (14.6, '10x drop'), (-1.0, 'negative')]:
    Yb = Ycopy(P); Yb[D23]['MSTR'] = bad
    e = hold(lambda: run(Pn, Yb, N('2026-10-23T21:00:00'), quotes={'MSTR': {'c': bad, 't': T23}}))
    chk(f'4 bad first stock value ({lab}) holds', e is not None, e)
Pb = copy.deepcopy(P); del Pb['closes'][D23]; Pb['btc_provisional'] = []
Yb = Ycopy(P); Yb[D23]['BTC'] = 0.0
chk('4 bad first BTC value (0 from both feeds) holds', hold(lambda: run(Pb, Yb, N('2026-10-24T00:25:00'), CB={D23: 0.0})) is not None)
o = run(Pn, Ycopy(P), N('2026-10-23T21:00:00'), quotes={'MSTR': {'c': 140.0, 't': int(N('2026-10-22T20:00:00').timestamp())}})
chk('4 wrong-date Finnhub quote ignored; value marked unchecked', o['fallback_sources'][D23]['MSTR'] == 'yahoo-unchecked', o['fallback_sources'].get(D23))
good_q = {k: {'c': P['closes'][D23][k], 't': T23} for k in P['closes'][D23] if k != 'BTC'}
o = run(Pn, Ycopy(P), N('2026-10-23T21:00:00'), quotes=good_q)
chk('4 same-date Finnhub agreement -> checked', 'MSTR' not in o['fallback_sources'].get(D23, {}))
Yx = Ycopy(P); Yx[D23]['MSTR'] = 160.0
chk('4 Yahoo vs Finnhub disagree (>0.2%) -> hold', 'differ' in (hold(lambda: run(Pn, Yx, N('2026-10-23T21:00:00'), quotes={'MSTR': {'c': 146.0, 't': T23}})) or ''))

print('# 5 holiday / early close')
YH = Ycopy(P); YH['2026-11-26'] = dict(YH[D23]); YH['2026-11-27'] = dict(YH[D23])
o = run(P, YH, N('2026-11-27T19:00:00'))
chk('5a Thanksgiving never a session', '2026-11-26' not in o['closes']); chk('5b early-close day not taken before 4 PM ET', '2026-11-27' not in o['closes'])
o = run(P, YH, N('2026-11-27T21:30:00'))
chk('5c early-close day taken after 4 PM ET', '2026-11-27' in o['closes'])

print('# 5b ET/DST: freeze cut and the UTC-rollover window across the Nov 1 switch')
PE = copy.deepcopy(P); PE['updated'] = '2026-11-03T00:30:00Z'                     # Nov 2 (EST) 7:30 PM ET: before that session's 8 PM ET cut
YE = Ycopy(P); YE['2026-11-02'] = dict(YE[D23]); PE['closes']['2026-11-02'] = dict(P['closes'][D23]); YE['2026-11-02']['GLD'] = round(P['closes'][D23]['GLD'] * 1.001, 6)
oE = run(PE, YE, N('2026-11-03T01:30:00'), quotes={'GLD': {'c': YE['2026-11-02']['GLD'], 't': int(N('2026-11-02T21:00:00').timestamp())}})
chk('5b EST: a publish at 7:30 PM EST is before the 8 PM ET cut (01:00 UTC), so the value is NOT frozen yet', oE['closes']['2026-11-02']['GLD'] == YE['2026-11-02']['GLD'], oE['closes']['2026-11-02'].get('GLD'))
PE2 = copy.deepcopy(PE); PE2['updated'] = '2026-11-03T01:05:00Z'; YE2 = Ycopy(PE2); YE2['2026-11-02']['GLD'] = 1.0 * PE2['closes']['2026-11-02']['GLD'] * 1.05
oE2 = run(PE2, YE2, N('2026-11-03T02:00:00'))
chk('5b EST: a publish at 8:05 PM EST (01:05 UTC) freezes it (later revision ignored)', oE2['closes']['2026-11-02']['GLD'] == PE2['closes']['2026-11-02']['GLD'], oE2['closes']['2026-11-02'].get('GLD'))
chk('5b UTC rollover window is UTC-based (tracks 7 PM EST from Nov 1)', not stale(P, N('2026-11-03T00:05:00')) and "now_utc.hour == 23 and now_utc.minute >= 55" in YML)
print('# 6 morning repair')
Pr = copy.deepcopy(P); del Pr['closes'][D23]; Pr['btc_provisional'] = []; Pr['updated'] = '2026-10-23T23:59:00Z'
chk('6a history_stale asks for the morning repair', stale(Pr, N('2026-10-24T13:00:00')))
o = run(Pr, Y, N('2026-10-24T13:00:00'), CB={D23: P['closes'][D23]['BTC']}, quotes=good_q)
chk('6b repair adds the session', D23 in o['closes']); chk('6c frozen Oct 22 untouched', o['closes'][D22] == Pr['closes'][D22])

print('# 8 push race')
m = copy.deepcopy(P); m['updated'] = '2026-10-23T21:10:00Z'
mi = YML.index("import json\n          a, b = json.load(open('/tmp/h_up.json'))"); mj = YML.index('PY', mi)
merge = textwrap.dedent('          ' + YML[mi:mj]).replace('/tmp/h_up.json', 'UP').replace('/tmp/h_me.json', 'ME').replace("open('history.json', 'w')", "open('OUT', 'w')")
td = tempfile.mkdtemp(); up = copy.deepcopy(P); me = copy.deepcopy(P)
up['revisions_ignored'] = [{'date': D21, 'sym': 'BTC', 'kept': 1, 'upstream': 2, 'src': 'yahoo'}]; up['fallback_sources'] = {D21: {'MSTR': 'yahoo+finnhub'}}
me['revisions_ignored'] = [{'date': D22, 'sym': 'MSTR', 'kept': 3, 'upstream': 4, 'src': 'yahoo'}]; me['updated'] = '2026-10-23T21:00:00Z'
for n_, h_ in (('UP', up), ('ME', me)): json.dump(h_, open(os.path.join(td, n_), 'w'))
cw = os.getcwd(); os.chdir(td); exec(merge, {'json': json}); mm = json.load(open('OUT')); os.chdir(cw)
chk('8b merge unions revisions_ignored', len(mm['revisions_ignored']) == 2, mm['revisions_ignored'])
chk('8c R-t: an old tag is dropped when the new run has the same date+symbol from a primary source', 'MSTR' not in mm['fallback_sources'].get(D21, {}), mm['fallback_sources'])
me2 = copy.deepcopy(me); me2['fallback_sources'] = {D23: {'BTC': 'coinbase'}}; json.dump(me2, open(os.path.join(td, 'ME'), 'w'))
cw = os.getcwd(); os.chdir(td); exec(merge, {'json': json}); mm2 = json.load(open('OUT')); os.chdir(cw)
chk('8d merge keeps the NEW run\'s fallback marking (a fallback is never silently promoted to primary by a push race)', mm2['fallback_sources'].get(D23, {}).get('BTC') == 'coinbase', mm2['fallback_sources'])

print('# 9 btc-daily')
def btcd(h, last=D21):
    td = tempfile.mkdtemp(); bd = os.path.join(td, 'bd.json'); hp = os.path.join(td, 'h.json')
    json.dump({'d': [[last, round(P['closes'][last]['BTC'], 2)]], 'end': last}, open(bd, 'w')); json.dump(h, open(hp, 'w'))
    r = subprocess.run([sys.executable, '-c', f"import json,sys,urllib.request,time\ndef deny(*a,**k): raise OSError('offline')\nurllib.request.urlopen=deny; time.sleep=lambda s: None\nsys.argv=['btc_daily.py',{bd!r},{hp!r}]\nexec(open({os.path.join(a.repo, 'tools/btc_daily.py')!r}).read())"], capture_output=True, text=True)
    return dict(json.load(open(bd))['d']), r.stdout + r.stderr
got, out = btcd(P)
chk('9a btc-daily takes history\'s frozen Yahoo final (81311.89) with feeds down', got.get(D22) == 81311.89, (got, out[-200:]))
got, out = btcd(Pf)
chk('9b btc-daily pauses at a fallback-sourced BTC day', D22 not in got and 'paused' in out, out[-200:])
print('# 11 re-pull between the 4 PM publish and the 8 PM freeze (GB v3-2, cycle1-2)')
Pe = copy.deepcopy(P); Pe['updated'] = '2026-10-23T20:30:00Z'
Yg = Ycopy(P); Yg[D23]['MSTR'] = round(P['closes'][D23]['MSTR'] * 1.05, 6)
o = run(Pe, Yg, N('2026-10-24T00:35:00'))
chk('11a GB v3-2: unconfirmed +5% re-pull keeps the published value', o['closes'][D23]['MSTR'] == P['closes'][D23]['MSTR'])
chk('11b GB v3-2: ... logged', any(r['sym'] == 'MSTR' and 'unconfirmed' in r['src'] for r in o['revisions_ignored']))
o = run(Pe, Yg, N('2026-10-24T00:35:00'), META={'MSTR': (D23, Yg[D23]['MSTR'])})
chk('11c GB v3-2: Yahoo META can NOT confirm a Yahoo re-pull', o['closes'][D23]['MSTR'] == P['closes'][D23]['MSTR'])
o = run(Pe, Yg, N('2026-10-24T00:35:00'), quotes={'MSTR': {'c': Yg[D23]['MSTR'], 't': T23}})
chk('11d GB v3-2: Finnhub (same date) confirms -> accepted', o['closes'][D23]['MSTR'] == Yg[D23]['MSTR'] and o['fallback_sources'][D23]['MSTR'] == 'yahoo+finnhub')
o = run(Pe, Yg, N('2026-10-24T00:35:00'), ST={('MSTR', D23): Yg[D23]['MSTR']})
chk('11e GB v3-2: Stooq confirms -> accepted', o['closes'][D23]['MSTR'] == Yg[D23]['MSTR'] and o['fallback_sources'][D23]['MSTR'] == 'yahoo+stooq', o['fallback_sources'].get(D23))

print('# 12 unchecked value freezing by age')
Pu2 = copy.deepcopy(P); Pu2['fallback_sources'] = {D22: {'MSTR': 'yahoo-unchecked'}}
G['HIST_WARN'].clear(); o = run(Pu2, Ycopy(P), N('2026-10-26T21:00:00'))
chk('12a warning + log entry', any('WITHOUT A SECOND SOURCE' in w for w in G['HIST_WARN']) and any(r['src'] == 'frozen-unchecked' for r in o['revisions_ignored']))
chk('12b marked -frozen', o['fallback_sources'][D22]['MSTR'] == 'yahoo-unchecked-frozen')
G['HIST_WARN'].clear(); run(o, Ycopy(P), N('2026-10-26T21:10:00'))
chk('12c no repeat alert', not any(w.startswith('MSTR ' + D22) for w in G['HIST_WARN']))
Pu3 = copy.deepcopy(Pu2); Pu3['closes'][D22]['MSTR'] = P['closes'][D21]['MSTR'] * 1.2
chk('12d >15% from previous session is not frozen', '15%' in (hold(lambda: run(Pu3, Ycopy(P), N('2026-10-26T21:00:00'))) or ''))

print('# 13 durable revision log')
o = run(P, Y, N('2026-10-23T21:00:00')); n1 = len(o['revisions_ignored']); o2 = run(o, Ycopy(P), N('2026-10-23T21:10:00')); o3 = run(o2, Y, N('2026-10-23T21:20:00'))
chk('13a carried forward', len(o2['revisions_ignored']) >= n1 > 0); chk('13b no duplicates', len(o3['revisions_ignored']) == len({json.dumps(r, sort_keys=True) for r in o3['revisions_ignored']}))
chk('13c new revisions go to runlog.jsonl', "rec['revisions_ignored'] = NEW_REVS" in YML)
print('# 17b Stooq: bot challenge + dividend payers never cross-checked by Stooq')
import io as _io, urllib.request as _u
_orig = _u.urlopen
class _Resp(_io.BytesIO): pass
_u.urlopen = lambda *a_, **k_: _Resp(b'<!DOCTYPE html><html><body><noscript>This site requires JavaScript to verify your browser.</noscript></body></html>')
try: sv_ = G['_stooq']('MSTR', D22)
finally: _u.urlopen = _orig
chk('17 GB v7-1 Stooq JS bot-challenge page -> no reference (fail safe, None)', sv_ is None, sv_)
_u.urlopen = lambda *a_, **k_: _Resp(b'Date,Open,High,Low,Close,Volume\n2026-10-22,1,1,1,145.80,1\n')
try: sv_ = G['_stooq']('MSTR', D22)
finally: _u.urlopen = _orig
chk('17 GB v7-1 Stooq real CSV still parsed', sv_ == 145.80, sv_)
Pg5 = copy.deepcopy(P); del Pg5['closes'][D23]; Pg5['btc_provisional'] = []; Pg5['updated'] = '2026-10-23T12:00:00Z'
q5 = {k: {'c': P['closes'][D23][k], 't': T23} for k in P['closes'][D23] if k not in ('BTC', 'STRC')}
e_ = hold(lambda: run(Pg5, Ycopy(P), N('2026-10-23T21:00:00'), quotes=q5, ST={('STRC', D23): P['closes'][D23]['STRC'] * 1.05}))
chk('17 GB v7-1 G5: a (dividend-adjusted) Stooq STRC is never a cross-check in history (no hold; STRC unchecked)', e_ is None, e_)
def btcd_at(h, now_iso):
    td = tempfile.mkdtemp(); bd = os.path.join(td, 'bd.json'); hp = os.path.join(td, 'h.json')
    json.dump({'d': [[D21, round(P['closes'][D21]['BTC'], 2)]], 'end': D21}, open(bd, 'w')); json.dump(h, open(hp, 'w'))
    code = (f"import json,sys,urllib.request,time,datetime as _d\ndef deny(*a,**k): raise OSError('offline')\nurllib.request.urlopen=deny; time.sleep=lambda s: None\n"
            f"class _DT(_d.datetime):\n    @classmethod\n    def now(c, tz=None): return _d.datetime.fromisoformat({now_iso!r}).replace(tzinfo=_d.timezone.utc)\n_d.datetime=_DT\n"
            f"sys.argv=['btc_daily.py',{bd!r},{hp!r}]\nexec(open({os.path.join(a.repo, 'tools/btc_daily.py')!r}).read())")
    r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr
rc, out = btcd_at(Pf, '2026-10-24T12:00:00')
chk('14 SL c1-4 fallback paused < 48 h: warning only, exit 0', rc == 0 and '::warning::' in out and '::error' not in out, (rc, out[-300:]))
rc, out = btcd_at(Pf, '2026-10-25T00:30:00')
chk('14 SL c1-4 fallback paused > 48 h: ::error:: + exit 3 (recap job red)', rc == 3 and '::error title=btc-daily stalled' in out, (rc, out[-300:]))
def job(name):   # text of one top-level job block (no PyYAML needed)
    m = re.search(r'^  ' + re.escape(name) + r':\n(.*?)(?=^  [A-Za-z][\w-]*:\n|\Z)', YML, re.S | re.M); return m.group(1) if m else ''
def btcd_check(h, now_iso):
    td = tempfile.mkdtemp(); bd = os.path.join(td, 'bd.json'); hp = os.path.join(td, 'h.json')
    json.dump({'d': [[D21, round(P['closes'][D21]['BTC'], 2)]], 'end': D21}, open(bd, 'w')); json.dump(h, open(hp, 'w')); before = open(bd).read()
    code = (f"import json,sys,urllib.request,time,datetime as _d\ndef deny(*a,**k): raise AssertionError('network used in check-only')\nurllib.request.urlopen=deny\n"
            f"class _DT(_d.datetime):\n    @classmethod\n    def now(c, tz=None): return _d.datetime.fromisoformat({now_iso!r}).replace(tzinfo=_d.timezone.utc)\n_d.datetime=_DT\n"
            f"sys.argv=['btc_daily.py',{bd!r},{hp!r},'--check-only']\nexec(open({os.path.join(a.repo, 'tools/btc_daily.py')!r}).read())")
    r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr, open(bd).read() == before
rc, out, un = btcd_check(Pf, '2026-10-25T14:00:00')     # Sunday ET
chk('16 SL v6c1-4: --check-only fires the stall alarm on a Sunday (exit 3), no network, file untouched', rc == 3 and un and 'AssertionError' not in out, (rc, out[-200:]))
rc, out, un = btcd_check(P, '2026-10-25T14:00:00')
chk('16 SL v6c1-4: --check-only with nothing stalled: exit 0, untouched', rc == 0 and un, (rc, out[-200:]))
vj = job('btcd-stall-check'); vjc = '\n'.join(l.split(' #')[0] for l in vj.split('\n') if not l.strip().startswith('#'))
chk('16 SL v6c1-4: weekend job runs the stall check, read-only (contents: read, no push/commit)', '--check-only' in vj and re.search(r'permissions:\n\s+contents: read\n', vjc) and 'git push' not in vjc and 'git commit' not in vjc and ': write' not in vjc, vjc[:300])
chk('16 fetch (writes prices) never runs on the weekend check schedule', "if: github.event.schedule != '17 15 * * 0,6'" in job('fetch'))
chk('16 SL v6c1-4: every actions/checkout is pinned to a 40-hex SHA', re.findall(r'actions/checkout@(\S+)', YML) and all(re.fullmatch(r'[0-9a-f]{40}', x) for x in re.findall(r'actions/checkout@(\S+)', YML)))
print('# BP-x override machinery is NOT in BP: overrides.json is ignored exactly as on live main')
ovx = {D22: {'BTC': 80000.0, 'MSTR': 1.0, 'reason': 'x', 'force': True, 'expected_upstream': {'BTC': 81311.890625}}}
o_ = run(P, Y, N('2026-10-23T21:00:00'), ov=ovx); o0 = run(P, Y, N('2026-10-23T21:00:00'))
chk('BP-x a present overrides.json changes nothing (same output as without it)', json.dumps(o_, sort_keys=True).replace(o_['updated'], '') == json.dumps(o0, sort_keys=True).replace(o0['updated'], ''))
chk('BP-x no override/refs keys in history.json', not ({'pending_review', 'refs_at_publish'} & set(o0)), sorted(o0))
chk('BP-x no override machinery in prices.yml / btc_daily.py', not re.search(r'validate_overrides|ov_rule|reviewers\.json|refs_at_publish|pending_review|overrides-check|load_overrides', YML + open(os.path.join(a.repo, 'tools/btc_daily.py')).read()))
chk('BP-x no PyYAML dependency in this test', 'import yaml' not in open(__file__).read().replace("'import yaml'", ''))
P9 = copy.deepcopy(P); cM = P9['closes'][D22]['MSTR']
print('# 19e R-i residual feed disagreement: one value unchecked, rest publishes')
Pfi = copy.deepcopy(P9); Pfi['fallback_sources'] = {D22: {'MSTR': 'yahoo-meta'}}; Pfi['closes'][D22]['MSTR'] = round(cM * 0.999, 6)
G['FEED_ERR'].clear(); G['HIST_WARN'].clear(); o = None
try: o = run(Pfi, Ycopy(P9), N('2026-10-23T21:05:00'), ST={('MSTR', D22): cM * 1.01})
except HH as e_: o = e_
chk('19e fallback MSTR + Stooq/Yahoo 1% apart: no HistoryHold; value kept, marked unchecked; Oct 23 published',
    isinstance(o, dict) and o['closes'][D22]['MSTR'] == Pfi['closes'][D22]['MSTR'] and o['fallback_sources'][D22]['MSTR'] == 'yahoo-meta-unchecked' and D23 in o['closes'], o if not isinstance(o, dict) else (o['closes'][D22]['MSTR'], o['fallback_sources'].get(D22)))
chk('19e ... after 8 PM ET of the session it is an ::error:: (FEED_ERR)', bool(G['FEED_ERR']), G['FEED_ERR'])
Pfn = copy.deepcopy(P9); del Pfn['closes'][D23]; Pfn['btc_provisional'] = []; Pfn['updated'] = '2026-10-23T12:00:00Z'
Yx9 = Ycopy(P9); Yx9[D23]['MSTR'] = 160.0
chk('19e a NEW value that disagrees still holds (unchanged)', 'differ' in (hold(lambda: run(Pfn, Yx9, N('2026-10-23T21:00:00'), quotes={'MSTR': {'c': 146.0, 't': T23}})) or ''))
print('# 21 v10 generic btc-daily heal (pre-v5 code froze fallback values into btc-daily)')
def btcd_file(rows, h, now_iso, ybars=None, prov=None, use_h=True, cbars=None, heal=None):
    td = tempfile.mkdtemp(); bd = os.path.join(td, 'bd.json'); hp = os.path.join(td, 'h.json'); hl = os.path.join(td, 'heal.json')
    if heal is not None: open(hl, 'w').write(heal if isinstance(heal, str) else json.dumps(heal))
    j0 = {'d': [list(r) for r in rows], 'end': rows[-1][0]}
    if prov: j0['provisional'] = prov
    json.dump(j0, open(bd, 'w')); json.dump(h, open(hp, 'w'))
    yb = json.dumps({'chart': {'result': [{'timestamp': [int(dt.datetime.fromisoformat(d).replace(tzinfo=UTC).timestamp()) for d in sorted(ybars or {})], 'indicators': {'quote': [{'close': [ybars[d] for d in sorted(ybars or {})]}]}}]}})
    cbx = json.dumps([[int(dt.datetime.fromisoformat(d).replace(tzinfo=UTC).timestamp()), 0, 0, 0, v, 0] for d, v in sorted((cbars or {}).items())])
    code = (f"import json,sys,io,urllib.request,time,datetime as _d\n_YBX={yb!r}\n_CBX={cbx!r}\n"
            f"def fake(req,*a,**k):\n    u=req.full_url if hasattr(req,'full_url') else req\n    if 'finance.yahoo.com' in u and {bool(ybars)!r}: return io.BytesIO(_YBX.encode())\n    if 'coinbase.com' in u and {bool(cbars)!r}: return io.BytesIO(_CBX.encode())\n    raise OSError('offline')\n"
            f"urllib.request.urlopen=fake; time.sleep=lambda s: None\n"
            f"class _DT(_d.datetime):\n    @classmethod\n    def now(c, tz=None): return _d.datetime.fromisoformat({now_iso!r}).replace(tzinfo=_d.timezone.utc)\n_d.datetime=_DT\n"
            f"sys.argv=['btc_daily.py',{bd!r}" + (f",{hp!r}" if use_h else "") + (f",'--heal-list',{hl!r}" if heal is not None else "") + f"]\nexec(open({os.path.join(a.repo, 'tools/btc_daily.py')!r}).read())")
    r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
    j = json.load(open(bd)); return r.returncode, dict(j['d']), j.get('provisional') or [], r.stdout + r.stderr
b21 = round(P["closes"][D21]["BTC"], 2); CB23 = 81078.04                                            # what the OLD code froze tonight (Coinbase)
OLD = [(D21, b21), (D22, 81307.16), (D23, CB23)]
Hh = copy.deepcopy(P); Hh['btc_provisional'] = []; Hh['closes'][D23]['BTC'] = CB23; Hh['fallback_sources'] = {D23: {'BTC': 'coinbase'}}
rc, B, pv_, out = btcd_file(OLD, Hh, '2026-10-24T01:00:00', heal=['2026-10-22'])   # R-s: deploy configuration (one-time heal list in DATA)
chk('21 deploy: Oct 22 healed to history\'s Yahoo final (81311.89) generically (no hard-coded value in btc_daily.py)', B[D22] == round(P['closes'][D22]['BTC'], 2) == 81311.89 and '81311.89' not in open(os.path.join(a.repo, 'tools/btc_daily.py')).read(), (B, out[-300:]))
chk('21 deploy: Oct 23 (fallback-frozen by old code, Yahoo bar still empty) keeps its value but is PROVISIONAL, exit 0', rc == 0 and B[D23] == CB23 and pv_ == [D23], (rc, B, pv_, out[-300:]))
YX = 81123.45                                                                             # Yahoo's final bar, whatever it turns out to be
Hy = copy.deepcopy(Hh); Hy['closes'][D23]['BTC'] = YX; Hy['fallback_sources'] = {}
rc2, B2, pv2, out2 = btcd_file([(D21, b21), (D22, B[D22]), (D23, CB23)], Hy, '2026-10-24T02:00:00', prov=pv_)
chk('21 heal: once history.json has Yahoo\'s Oct 23 final bar, btc-daily Oct 23 = that bar and is no longer provisional', rc2 == 0 and B2[D23] == YX and not pv2 and B2[D22] == 81311.89, (rc2, B2, pv2, out2[-300:]))
rc3, B3, pv3, out3 = btcd_file([(D21, b21), (D22, 81311.89), (D23, YX)], Hy, '2026-10-24T03:00:00')
chk('21 heal is idempotent: already in sync -> up to date, nothing rewritten', rc3 == 0 and B3 == B2 and 'up to date' in out3, out3[-200:])
rc5, B5, pv5, out5 = btcd_file([(D21, b21), (D22, 81311.89), (D23, CB23)], {}, '2026-10-24T02:00:00', ybars={D23: YX}, prov=[D23], use_h=False)
chk('21 heal without history.json: a provisional date heals from Yahoo\'s own final bar', B5[D23] == YX and not pv5, (B5, pv5, out5[-300:]))
rc6, B6, pv6, out6 = btcd_file([(D21, b21), (D22, 81311.89), (D23, CB23)], Hh, '2026-10-26T02:00:00', prov=[D23])
chk('21 provisional > 48 h without Yahoo: ::error:: stall + exit 3', rc6 == 3 and 'stalled' in out6, (rc6, out6[-300:]))
rc7, B7, pv7, o7 = btcd_file([(D21, b21), (D22, 81311.89), (D23, 40000.0)], Hy, '2026-10-24T02:00:00')
chk('21 heal sanity (R-s): an implausible FINAL stored value is NOT rewritten (no record, > 0.5%): ::error::, exit 1, file unchanged', rc7 == 1 and B7[D23] == 40000.0 and 'heal refused' in o7, (rc7, B7, o7[-200:]))
rc7p, B7p, _, o7p = btcd_file([(D21, b21), (D22, 81311.89), (D23, 40000.0)], Hy, '2026-10-24T02:00:00', prov=[D23])
chk('21 heal sanity: an implausible PROVISIONAL value is healed to the final close (sane vs neighbours)', rc7p == 0 and B7p[D23] == YX, (rc7p, B7p, o7p[-200:]))
print('# 22 R-q heal pins')
# R-q heal pins
rows_ = [(D21, b21), (D22, 81311.89), (D23, CB23)]
for f_, w_ in ((2.0, False), (1.99, True), (0.5, False), (0.51, True)):
    Hq = copy.deepcopy(Hy); Hq['closes'][D23]['BTC'] = round(81311.89 * f_, 2)
    rcq, Bq, _, oq = btcd_file(rows_, Hq, '2026-10-24T02:00:00', prov=[D23])   # R-s: the band applies to provisional rows (final rows are capped at 0.5%)
    chk(f'22 SL R-q heal neighbour band: target {f_}x the neighbour -> {"healed" if w_ else "refused (exit 1, file untouched)"}', (Bq[D23] == round(81311.89 * f_, 2) and rcq == 0) if w_ else (rcq == 1 and Bq[D23] == CB23 and 'implausible heal' in oq), (rcq, Bq, oq[-200:]))
rcn, Bn, pvn, on = btcd_file([(D21, b21), (D22, 81307.16), (D23, CB23)], {}, '2026-10-24T02:00:00', ybars={D22: 81311.89, D23: YX}, prov=[D23], use_h=False)
chk('22 SL R-q no-history path heals ONLY provisional dates (Oct 23), never a non-provisional one (Oct 22 untouched)', Bn[D22] == 81307.16 and Bn[D23] == YX and not pvn, (Bn, pvn, on[-200:]))
rcc, Bc, pvc, oc = btcd_file([(D21, b21), (D22, 81311.89)], {}, '2026-10-24T02:00:00', cbars={D23: CB23}, use_h=False)
chk('22 a day filled from Coinbase (Yahoo down) is appended as PROVISIONAL', Bc.get(D23) == CB23 and pvc == [D23], (rcc, Bc, pvc, oc[-200:]))
print('# 23 SL attack cases A11/A12 (heal band edges, no-history path)')
# A11: heal band exact edges, +/- one cent (values are stored to the cent)
n11 = 81311.89
for t11, w11, l11 in ((n11 * 2, False, '2x exactly'), (n11 * 2 - 0.01, True, '2x - 0.01'), (n11 * 2 + 0.01, False, '2x + 0.01'),
                      (n11 * 0.5, False, '0.5x exactly (unrounded)'), (n11 * 0.5 + 0.01, True, '0.5x + 0.01'), (n11 * 0.5 - 0.01, False, '0.5x - 0.01')):
    Hq = copy.deepcopy(Hy); Hq['closes'][D23]['BTC'] = t11
    rcq, Bq, _, oq = btcd_file(rows_, Hq, '2026-10-24T02:00:00', prov=[D23])
    chk(f'SL-A11 heal band {l11} -> {"healed" if w11 else "refused"}', (Bq[D23] == round(t11, 2) and rcq == 0) if w11 else (rcq == 1 and Bq[D23] == CB23 and 'implausible heal' in oq), (rcq, Bq, oq[-160:]))
# A12: no-history path
chk('SL-A12 no-history path: provisional Oct 23 healed from Yahoo bar', Bn[D23] == YX and not pvn, (Bn, pvn))
chk('SL-A12 no-history path: non-provisional Oct 22 left alone despite a different Yahoo bar', Bn[D22] == 81307.16, Bn)
print('# 24 recap marks provisional BTC days (btc-daily "provisional")')
import shutil as _sh
def recap_with(prov):
    td = tempfile.mkdtemp(); rp = os.path.join(td, 'r'); _sh.copytree(a.repo, rp, ignore=_sh.ignore_patterns('.git', 'tests'))
    bdp = os.path.join(rp, 'assets/data/btc-daily.json'); j = json.load(open(bdp))
    if prov: j['provisional'] = [x for x in prov if x in dict(j['d'])]
    else: j.pop('provisional', None)
    json.dump(j, open(bdp, 'w'), separators=(',', ':')); hp = os.path.join(td, 'h.json'); json.dump(H0, open(hp, 'w'))
    r = subprocess.run([sys.executable, 'tools/recap_gen.py', '--history', hp, '--repo', '.'], cwd=rp, capture_output=True, text=True)
    pg = open(os.path.join(rp, 'recap', max(x for x in os.listdir(os.path.join(rp, 'recap')) if re.fullmatch(r'\d{4}-\d{2}', x)), 'index.html')).read()
    return r.returncode, pg, j, r.stdout + r.stderr
rc0, pg0, j0_, o0_ = recap_with(None)
rc1, pg1, j1_, o1_ = recap_with([D21])
chk('24 recap: a provisional btc-daily day is named in the BTC card note', rc1 == 0 and 'Provisional (fallback source until Yahoo' in pg1, (rc1, o1_[-300:]))
chk('24 recap: no provisional day -> no provisional note', rc0 == 0 and 'Provisional (fallback source' not in pg0, (rc0, o0_[-300:]))
print('# 25 SL BP attack cases B1-B15 (Oct 23 10:46 PM)')
import math as _m
def ext_sess(h, Yd, d, src_d=D23):   # add a session d to history fixture + Yahoo bars (copy of src_d's row)
    h['closes'][d] = dict(P['closes'][src_d]); Yd[d] = dict(P['closes'][src_d])
# B1 frozen final close revised by Yahoo
P1b = copy.deepcopy(P); P1b['closes'][D22]['MSTR'] = 145.80; Y1b = Ycopy(P1b); Y1b[D22]['BTC'] = 81400.0; Y1b[D22]['MSTR'] = 145.95
o1b = run(P1b, Y1b, N('2026-10-23T21:00:00'))
chk('SL-B1 Yahoo revises frozen Oct 22 BTC -> 81,400: stays 81311.890625', o1b['closes'][D22]['BTC'] == 81311.890625, o1b['closes'][D22]['BTC'])
chk('SL-B1 Yahoo revises frozen Oct 22 MSTR 145.80 -> 145.95: stays 145.80, revision logged', o1b['closes'][D22]['MSTR'] == 145.80 and any(r['sym'] == 'MSTR' and r['upstream'] == 145.95 for r in o1b['revisions_ignored']), o1b['closes'][D22]['MSTR'])
# B2 Coinbase fallback on D: Yahoo bar at D+1 then a revised bar at D+3
Yn2 = Ycopy(P); del Yn2[D22]['BTC']
o2a = run(Pf, Yn2, N('2026-10-23T21:00:00'), CB={D22: 81307.16})
chk('SL-B2 while still a fallback it is NOT frozen (marked coinbase)', o2a['closes'][D22]['BTC'] == 81307.16 and o2a['fallback_sources'][D22]['BTC'] == 'coinbase', o2a['fallback_sources'].get(D22))
o2b = run(o2a, Ycopy(P), N('2026-10-23T21:05:00'), CB={D22: 81307.16})
chk('SL-B2 D+1: Yahoo bar replaces the fallback once (primary, logged once)', o2b['closes'][D22]['BTC'] == 81311.890625 and 'BTC' not in o2b['fallback_sources'].get(D22, {}) and sum('replaced by primary' in r['src'] and r['date'] == D22 for r in o2b['revisions_ignored']) == 1, (o2b['closes'][D22]['BTC'], o2b['fallback_sources'].get(D22)))
Y2c = Ycopy(P); Y2c[D22]['BTC'] = 81500.0
o2c = run(o2b, Y2c, N('2026-10-25T21:00:00'), CB={D22: 81500.0})
chk('SL-B2 D+3: a later Yahoo bar is ignored (frozen), no second replacement', o2c['closes'][D22]['BTC'] == 81311.890625 and sum('replaced by primary' in r['src'] and r['date'] == D22 for r in o2c['revisions_ignored']) == 1, o2c['closes'][D22]['BTC'])
o2d = run(Pf, Yn2, N('2026-10-25T21:00:00'), CB={D22: 81307.16})
chk('SL-B2 D+3 with Yahoo still null: still a fallback, still not frozen', o2d['fallback_sources'][D22]['BTC'] == 'coinbase', o2d['fallback_sources'].get(D22))
# B3 provisional date: 8 PM EDT and 7 PM EST (Nov 2)
D2N = '2026-11-02'
for upd, now_, lab in (('2026-10-23T23:59:00Z', '2026-10-24T00:30:00', '7:59 PM EDT Oct 23'), ('2026-11-03T00:05:00Z', '2026-11-03T00:30:00', '7:05 PM EST Nov 2 (= 8:05 PM if EDT were wrongly assumed)')):
    d_ = D23 if '10-23' in lab else D2N
    h3 = copy.deepcopy(P); Y3_ = Ycopy(P)
    if d_ == D2N: ext_sess(h3, Y3_, D2N)
    h3['updated'] = upd; h3['btc_provisional'] = [d_]; Y3_[d_]['GLD'] = round(h3['closes'][d_]['GLD'] * 1.0015, 6)
    o3_ = run(h3, Y3_, N(now_))
    chk(f'SL-B3 stock published {lab}: before the 8 PM ET cut -> NOT frozen (settlement revision taken)', o3_['closes'][d_]['GLD'] == Y3_[d_]['GLD'], (o3_['closes'][d_]['GLD'], Y3_[d_]['GLD']))
h3b = copy.deepcopy(P); Y3b = Ycopy(P); ext_sess(h3b, Y3b, D2N); h3b['btc_provisional'] = [D2N]; h3b['updated'] = '2026-11-03T00:05:00Z'
o3b = run(h3b, Y3b, N('2026-11-03T00:15:00'))
chk('SL-B3 BTC Nov 2 at 7:15 PM EST (00:15 UTC, < 20 min after the UTC day): still provisional', D2N in o3b['btc_provisional'], o3b['btc_provisional'])
o3c = run(h3b, Y3b, N('2026-11-03T00:25:00'), CB={D2N: Y3b[D2N]['BTC']})
chk('SL-B3 BTC Nov 2 at 7:25 PM EST (00:25 UTC): final only via cross-check', D2N not in o3c['btc_provisional'], o3c['btc_provisional'])
# B4 DST edges
ok4 = []
for t_ in ('2026-11-01T05:30:00', '2026-11-01T06:30:00', '2027-03-14T06:30:00', '2027-03-14T07:30:00'):   # 1:30 AM EDT, 1:30 AM EST (repeated hour); 1:30 AM EST, 3:30 AM EDT
    try: ok4.append(stale(P, N(t_)))
    except Exception as e_: ok4.append(f'EXC {e_}')
chk('SL-B4 history_stale across the repeated hour (Nov 1 01:00-02:00 ET) and the skipped hour (Mar 14 2027): no crash, consistent', not any(isinstance(x, str) for x in ok4) and ok4[0] == ok4[1], ok4)
q4 = {'MSTR': {'c': 1.0, 't': int(N('2026-11-01T05:30:00').timestamp())}}; q4b = {'MSTR': {'c': 1.0, 't': int(N('2026-11-01T06:30:00').timestamp())}}
ET_ = zoneinfo.ZoneInfo('America/New_York')
chk('SL-B4 both 1:30 AM ET instants on Nov 1 map to ET date 2026-11-01 (fold-safe)', {dt.datetime.fromtimestamp(q['MSTR']['t'], ET_).date().isoformat() for q in (q4, q4b)} == {'2026-11-01'})
D3M = '2027-03-15'
for upd, want_frozen, lab in (('2027-03-15T23:30:00Z', False, '7:30 PM EDT'), ('2027-03-16T00:05:00Z', True, '8:05 PM EDT')):
    h4 = copy.deepcopy(P); Y4_ = Ycopy(P); ext_sess(h4, Y4_, D3M); h4['updated'] = upd; h4['btc_provisional'] = [D3M]
    Y4_[D3M]['GLD'] = round(h4['closes'][D3M]['GLD'] * 1.0015, 6)
    try:
        o4_ = run(h4, Y4_, N('2027-03-16T01:00:00')); got4 = o4_['closes'][D3M]['GLD']
    except Exception as e_: got4 = f'EXC {type(e_).__name__} {e_}'
    chk(f'SL-B4 Mon Mar 15 2027 (first EDT session) publish at {lab}: {"frozen" if want_frozen else "not frozen"}', got4 == (h4['closes'][D3M]['GLD'] if want_frozen else Y4_[D3M]['GLD']), got4)
# B5 heal once, second run byte-identical
def btcd_raw(path, h, now_iso, heal=None):
    hp = path + '.h.json'; json.dump(h, open(hp, 'w')); hl = path + '.heal.json'
    if heal is not None: json.dump(heal, open(hl, 'w'))
    code = (f"import json,sys,urllib.request,time,datetime as _d\ndef deny(*a,**k): raise OSError('offline')\nurllib.request.urlopen=deny; time.sleep=lambda s: None\n"
            f"class _DT(_d.datetime):\n    @classmethod\n    def now(c, tz=None): return _d.datetime.fromisoformat({now_iso!r}).replace(tzinfo=_d.timezone.utc)\n_d.datetime=_DT\n"
            f"sys.argv=['btc_daily.py',{path!r},{hp!r}" + (f",'--heal-list',{hl!r}" if heal is not None else "") + f"]\nexec(open({os.path.join(a.repo, 'tools/btc_daily.py')!r}).read())")
    r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True); return r.returncode, open(path, 'rb').read(), r.stdout + r.stderr
td5 = tempfile.mkdtemp(); bp5 = os.path.join(td5, 'bd.json'); json.dump({'d': [[D21, b21], [D22, 81307.16]], 'end': D22}, open(bp5, 'w'), separators=(',', ':'))
H5 = copy.deepcopy(P); H5['btc_provisional'] = [D23]
r5a, raw5a, out5a = btcd_raw(bp5, H5, '2026-10-23T21:00:00', heal=['2026-10-22']); m5a = os.path.getmtime(bp5)
r5b, raw5b, out5b = btcd_raw(bp5, H5, '2026-10-23T21:05:00', heal=['2026-10-22'])
chk('SL-B5 heal Oct 22 81,307.16 -> 81,311.89 on the first run', r5a == 0 and dict(json.loads(raw5a)['d'])[D22] == 81311.89 and 'HEALED' in out5a, out5a[-200:])
chk('SL-B5 second run: byte-identical file, not rewritten, "up to date"', r5b == 0 and raw5b == raw5a and os.path.getmtime(bp5) == m5a and 'up to date' in out5b and 'HEALED' not in out5b, out5b[-200:])
# B6 final non-fallback row never rewritten even if history differs
H6 = copy.deepcopy(P); H6['btc_provisional'] = [D23]; H6['closes'][D21]['BTC'] = round(b21 * 1.01, 2)   # history (Yahoo provenance) now differs for a final row
td6 = tempfile.mkdtemp(); bp6 = os.path.join(td6, 'bd.json'); json.dump({'d': [[D21, b21], [D22, 81311.89]], 'end': D22}, open(bp6, 'w'), separators=(',', ':')); raw6 = open(bp6, 'rb').read()
r6, raw6b, out6 = btcd_raw(bp6, H6, '2026-10-23T21:00:00')
chk('SL-B6 a final, non-fallback btc-daily row (Oct 21) is never rewritten even if history.json differs', raw6b == raw6, (dict(json.loads(raw6b)['d']).get(D21), b21, out6[-200:]))
# B7 stall timing (fallback in history, existing btc-daily row)
for now7, want7, lab7 in (('2026-10-25T23:59:00', 0, '47h59m'), ('2026-10-26T00:01:00', 3, '48h01m')):
    rc7_, B7_, pv7_, o7_ = btcd_file([(D21, b21), (D22, 81311.89), (D23, CB23)], Hh, now7)
    chk(f'SL-B7 Oct 23 fallback in history, {lab7} after its UTC day: provisional, exit {want7}' + (' with ::error::' if want7 else ', no error'), rc7_ == want7 and pv7_ == [D23] and (('::error title=btc-daily stalled' in o7_) == bool(want7)), (rc7_, pv7_, o7_[-200:]))
# B8 heal band edges (see SL-A11) + bad values in history
for bv, lab8 in ((float('nan'), 'NaN'), (0.0, '0'), (-1.0, '-1')):
    H8 = copy.deepcopy(Hy); H8['closes'][D23]['BTC'] = bv
    rc8, B8, pv8, o8 = btcd_file([(D21, b21), (D22, 81311.89), (D23, CB23)], H8, '2026-10-24T02:00:00')
    chk(f'SL-B8 history BTC {lab8}: never healed into btc-daily (value unchanged, no traceback)', B8[D23] == CB23 and 'Traceback' not in o8, (rc8, B8[D23], o8[-200:]))
chk('SL-B8 heal band 0.5x/2x edges covered by SL-A11 (6 cases)', sum(1 for n_, ok_ in R if n_.startswith('SL-A11') and ok_) == 6)
# B9 Stooq HTML challenge: no data and NO hold (real _stooq, patched network)
import urllib.request as _u9, io as _io9
P9n = copy.deepcopy(P); del P9n['closes'][D23]; P9n['btc_provisional'] = []; P9n['updated'] = '2026-10-23T12:00:00Z'
_o9 = _u9.urlopen; _u9.urlopen = lambda *a_, **k_: _io9.BytesIO(b'<!DOCTYPE html><html><body>verify you are human</body></html>')
try:
    try: o9 = G['build_history'](feed(Ycopy(P)), N('2026-10-23T21:00:00'), copy.deepcopy(P9n), {}, stooq=G['_stooq']); e9 = None
    except HH as e_: o9, e9 = None, str(e_)
finally: _u9.urlopen = _o9
chk('SL-B9 Stooq HTML challenge -> no data and no HistoryHold; values published single-source (unchecked)', e9 is None and o9 and D23 in o9['closes'] and o9['fallback_sources'][D23]['MSTR'] == 'yahoo-unchecked', e9)
# B10 Stooq never called for STRC/SPY/QQQ
called = []
def spy_st(y, d): called.append(y); return None
run_ = G['build_history'](feed(Ycopy(P)), N('2026-10-23T21:00:00'), copy.deepcopy(P9n), {}, stooq=spy_st)
chk('SL-B10 Stooq is never called for STRC/SPY/QQQ (called for the others)', not ({'STRC', 'SPY', 'QQQ'} & set(called)) and 'MSTR' in called, sorted(set(called)))
# B11 disagreeing fallback kept unchecked, no hold (BTC + stock)
Pb11 = copy.deepcopy(P); Pb11['closes'][D22]['BTC'] = 81307.16; Pb11['fallback_sources'] = {D22: {'BTC': 'coinbase'}}; Y11 = Ycopy(P); Y11[D22]['BTC'] = 84000.0
try: o11 = run(Pb11, Y11, N('2026-10-23T21:00:00'), CB={D22: 81307.16}); e11 = None
except HH as e_: o11, e11 = None, str(e_)
chk('SL-B11 BTC Coinbase fallback vs a disagreeing Yahoo bar (+3.3%): kept, marked unchecked, no HistoryHold', e11 is None and o11['closes'][D22]['BTC'] == 81307.16 and o11['fallback_sources'][D22]['BTC'] == 'coinbase-unchecked', e11 or o11['fallback_sources'].get(D22))
chk('SL-B11 stock (yahoo-meta) disagreeing fallback: covered by 19e (kept unchecked, no hold, ::error:: after 8 PM)', all(ok_ for n_, ok_ in R if n_.startswith('19e')))
# B12 Yahoo 0 / NaN / -1 treated as missing (Finnhub good)
for bv, lab12 in ((0.0, '0'), (float('nan'), 'NaN'), (-1.0, '-1')):
    Y12 = Ycopy(P); Y12[D23]['MSTR'] = bv
    try: o12 = run(P9n, Y12, N('2026-10-23T21:00:00'), quotes={'MSTR': {'c': P['closes'][D23]['MSTR'], 't': T23}}); e12 = None
    except HH as e_: o12, e12 = None, str(e_)
    chk(f'SL-B12 Yahoo MSTR {lab12} is missing: Finnhub value used, no hold, no bad value published', e12 is None and o12['closes'][D23]['MSTR'] == P['closes'][D23]['MSTR'], e12 or o12['closes'][D23]['MSTR'])
# B13 overrides.json ignored entirely
o13n = run(P, Y, N('2026-10-23T21:00:00'))
for raw13, lab13 in (('{not json', 'junk'), (json.dumps({D22: {'BTC': 81311.89, 'reason': 'x', 'force': True, 'reviewed_by': 'sunil', 'expected_upstream': {'BTC': 81311.890625}}}), 'valid force entry')):
    G['HIST_WARN'].clear(); o13 = run(P, Y, N('2026-10-23T21:00:00'), raw=raw13)
    chk(f'SL-B13 overrides.json ({lab13}): output identical to no file, no pending_review, no error/warning', json.dumps(o13, sort_keys=True).replace(o13['updated'], '') == json.dumps(o13n, sort_keys=True).replace(o13n['updated'], '') and 'pending_review' not in o13 and not G['HIST_WARN'] and not G.get('OV_ERR'))
chk('SL-B13 prices.yml never opens overrides.json (no read path at all)', 'overrides.json' not in YML.replace('overrides.json is ignored', ''), [l.strip()[:80] for l in YML.split('\n') if 'overrides.json' in l])
# B14 weekend stall job read-only
vj14 = job('btcd-stall-check'); vjc14 = '\n'.join(l.split(' #')[0] for l in vj14.split('\n') if not l.strip().startswith('#'))
chk('SL-B14 weekend stall job: permissions block is exactly contents: read', re.search(r'\n    permissions:\n      contents: read\n    steps:', vj14) is not None, vj14[:300])
chk('SL-B14 weekend stall job: no secrets, no write, no push/commit, checkout without persisted credentials', 'secrets.' not in vjc14 and ': write' not in vjc14 and 'git push' not in vjc14 and 'git commit' not in vjc14 and 'persist-credentials: false' in vjc14, vjc14[:300])
chk('SL-B14 workflow-level default permissions are empty (permissions: {})', re.search(r'^permissions: \{\}$', YML, re.M) is not None)
print('# 26 R-s: rewriting a FINAL btc-daily row needs a fallback record AND <= 7 days (ET) AND <= 0.5%')
def rs(o22, t22, now_iso, heal=None, revs=None, prov=None, rows_extra=()):
    h_ = copy.deepcopy(Hy); h_['closes'][D22]['BTC'] = t22; h_['revisions_ignored'] = revs or []   # Oct 23 already Yahoo (no unrelated stall)
    rows = [(D21, b21), (D22, o22), (D23, YX)] + list(rows_extra)
    rc_, B_, pv_, o_ = btcd_file(rows, h_, now_iso, heal=heal, prov=prov)
    return rc_, B_, o_
REVOK = [{'date': D22, 'sym': 'BTC', 'kept': 81311.89, 'upstream': 81307.16, 'src': 'fallback (coinbase) replaced by primary final bar'}]
def healed(r_, want): return r_[0] == 0 and r_[1][D22] == want and 'heal refused' not in r_[2]
def refused(r_, old): return r_[0] == 1 and r_[1][D22] == old and '::error title=btc-daily heal refused::' in r_[2]
T1 = '2026-10-24T01:00:00'
chk('26 SL-6 R-s (1) heal list in DATA ["2026-10-22"] -> Oct 22 healed', healed(rs(81307.16, 81311.89, T1, heal=['2026-10-22']), 81311.89))
chk('26 SL-6 R-s (1) revision log "fallback (coinbase) replaced by primary" -> healed', healed(rs(81307.16, 81311.89, T1, revs=REVOK), 81311.89))
chk('26 SL-6 R-s (1) no record at all -> refused, ::error::, file unchanged', refused(rs(81307.16, 81311.89, T1), 81307.16))
for lab_, rv_ in (('other symbol (MSTR)', [dict(REVOK[0], sym='MSTR')]), ('plain Yahoo revision (src yahoo)', [dict(REVOK[0], src='yahoo')]), ('other date', [dict(REVOK[0], date=D21)]), ('unconfirmed re-pull', [dict(REVOK[0], src='unconfirmed re-pull before freeze')])):
    chk(f'26 SL-6 R-s (1) revision log entry is not a fallback record ({lab_}) -> refused', refused(rs(81307.16, 81311.89, T1, revs=rv_), 81307.16))
for lab_, hl_ in (('other date only', ['2026-10-21']), ('values (object)', '{"2026-10-22": 81311.89}'), ('a value in the list', '["2026-10-22", 81311.89]'), ('junk', '{oops')):
    r_ = rs(81307.16, 81311.89, T1, heal=hl_)
    chk(f'26 SL-6 R-s (1) heal list {lab_} -> not a record' + (' (list ignored with ::error::)' if lab_ != 'other date only' else '') + ' -> refused', refused(r_, 81307.16) and (lab_ == 'other date only' or 'heal list ignored' in r_[2]), r_[2][-200:])
for now_, ok_, lab_ in (('2026-10-30T03:30:00', True, 'Oct 29 11:30 PM ET = 7 days (UTC date is already Oct 30)'), ('2026-10-30T04:05:00', False, 'Oct 30 12:05 AM ET = 8 days'),
                        ('2026-10-29T15:00:00', True, 'Oct 29 = 7 days'), ('2026-11-02T15:00:00', False, 'Nov 2 = 11 days')):
    r_ = rs(81307.16, 81311.89, now_, heal=['2026-10-22'])
    chk(f'26 SL-6 R-s (2) age in ET days: {lab_} -> {"healed" if ok_ else "refused"}', healed(r_, 81311.89) if ok_ else (refused(r_, 81307.16) and 'days old' in r_[2]), r_[2][-200:])
for t_, ok_, lab_ in ((80400.00, True, '+0.5% exactly'), (80400.01, False, '+0.5% + 1 cent'), (79600.00, True, '-0.5% exactly'), (79599.99, False, '-0.5% - 1 cent'), (80800.00, False, '+1%')):
    r_ = rs(80000.00, t_, T1, heal=['2026-10-22'])
    chk(f'26 SL-6 R-s (3) change {lab_} (80,000.00 -> {t_:,.2f}) -> {"healed" if ok_ else "refused"}', healed(r_, t_) if ok_ else (refused(r_, 80000.00) and 'change' in r_[2]), r_[2][-200:])
r_ = rs(81307.16, round(81307.16 * 1.01, 2), T1, prov=[D22, D23])
chk('26 SL-6 R-s provisional rows are not final: a 1% heal with no record still applies (R-q band only)', r_[0] == 0 and r_[1][D22] == round(81307.16 * 1.01, 2), r_[2][-200:])
r_ = rs(81307.16, 81311.89, T1, rows_extra=[])
Hn_ = copy.deepcopy(Hy); Hn_['closes'][D22]['BTC'] = 81311.89
rcn_, Bn_, _, on_ = btcd_file([(D21, b21), (D22, 81300.00)], Hn_, '2026-10-24T02:00:00')
chk('26 SL-6 R-s a refusal leaves the WHOLE file unchanged (pending Oct 23 append not written either)', rcn_ == 1 and Bn_ == {D21: b21, D22: 81300.00}, (rcn_, Bn_, on_[-200:]))
print('# 27 R-t: push-race merge keeps an old-only date\'s value, source tag and provisional mark')
def merge_of(old_h, new_h):
    td = tempfile.mkdtemp(); json.dump(old_h, open(os.path.join(td, 'UP'), 'w')); json.dump(new_h, open(os.path.join(td, 'ME'), 'w'))
    cw = os.getcwd(); os.chdir(td)
    try: exec(merge, {'json': json}); return json.load(open('OUT'))
    finally: os.chdir(cw)
D24, D26 = '2026-10-24', '2026-10-26'
oldm = copy.deepcopy(P); oldm['updated'] = '2026-10-24T21:00:00Z'; oldm['closes'][D24] = dict(P['closes'][D23], BTC=81078.04, MSTR=151.0, STRC=101.0)
oldm['fallback_sources'] = {D24: {'BTC': 'coinbase', 'MSTR': 'yahoo-meta', 'STRC': 'finnhub'}}; oldm['btc_provisional'] = [D24]
newm = copy.deepcopy(P); newm['updated'] = '2026-10-24T21:05:00Z'; newm['btc_provisional'] = []; newm['fallback_sources'] = {}
mm_ = merge_of(oldm, newm)
chk('27 Grok R-t pushed copy has Oct 24 BTC coinbase, new run lacks Oct 24: value AND tag kept', mm_['closes'].get(D24, {}).get('BTC') == 81078.04 and mm_['fallback_sources'].get(D24, {}).get('BTC') == 'coinbase', mm_['fallback_sources'].get(D24))
chk('27 Grok R-t stock equivalents (yahoo-meta MSTR, finnhub STRC) keep their tags', mm_['fallback_sources'].get(D24, {}).get('MSTR') == 'yahoo-meta' and mm_['fallback_sources'].get(D24, {}).get('STRC') == 'finnhub', mm_['fallback_sources'].get(D24))
chk('27 Grok R-t btc_provisional: a date only in the old copy is never dropped', D24 in mm_['btc_provisional'], mm_['btc_provisional'])
oldp = copy.deepcopy(P); oldp['updated'] = '2026-10-24T21:00:00Z'; oldp['btc_provisional'] = [D23]; newp = copy.deepcopy(P); newp['updated'] = '2026-10-24T21:05:00Z'; newp['btc_provisional'] = []
chk('27 Grok R-t btc_provisional: a date the NEW run has as final is not re-marked provisional from the old copy', D23 not in merge_of(oldp, newp)['btc_provisional'])
newx = copy.deepcopy(newm); newx['closes'][D24] = dict(oldm['closes'][D24], BTC=81100.0)
chk('27 Grok R-t control: new run has Oct 24 from a PRIMARY source -> old coinbase tag dropped', 'BTC' not in merge_of(oldm, newx)['fallback_sources'].get(D24, {}))
newy = copy.deepcopy(newx); newy['fallback_sources'] = {D24: {'BTC': 'coingecko'}}
chk('27 Grok R-t control: new run has Oct 24 with its OWN fallback tag -> the new tag', merge_of(oldm, newy)['fallback_sources'].get(D24, {}).get('BTC') == 'coingecko')
# full chain on a SESSION date (Oct 24 is a Saturday: history.json only has sessions) -> Mon Oct 26
oldc = copy.deepcopy(P); oldc['btc_provisional'] = []; oldc['closes'][D26] = dict(P['closes'][D23], BTC=81078.04, MSTR=151.0, STRC=101.0)
oldc['fallback_sources'] = {D26: {'BTC': 'coinbase', 'MSTR': 'yahoo-meta', 'STRC': 'finnhub'}}; oldc['updated'] = '2026-10-27T01:30:00Z'
newc = copy.deepcopy(P); newc['btc_provisional'] = []; newc['fallback_sources'] = {}; newc['updated'] = '2026-10-27T01:35:00Z'
mc = merge_of(oldc, newc)
chk('27 Grok R-t chain: after the race Oct 26 keeps coinbase / yahoo-meta / finnhub tags', mc['fallback_sources'].get(D26) == {'BTC': 'coinbase', 'MSTR': 'yahoo-meta', 'STRC': 'finnhub'}, mc['fallback_sources'].get(D26))
Yc0 = Ycopy(P); Yc0[D26] = {k: v for k, v in P['closes'][D23].items() if k not in ('BTC', 'MSTR', 'STRC')}
oc1 = run(mc, Yc0, N('2026-10-29T02:00:00'))
chk('27 Grok R-t chain: does NOT freeze (days later, Yahoo still null): values and tags unchanged', all(oc1['closes'][D26][k] == mc['closes'][D26][k] for k in ('BTC', 'MSTR', 'STRC')) and oc1['fallback_sources'].get(D26) == mc['fallback_sources'][D26], oc1['fallback_sources'].get(D26))
Yc1 = Ycopy(P); Yc1[D26] = dict(P['closes'][D23], BTC=81100.0, MSTR=151.1, STRC=101.05)
oc2 = run(oc1, Yc1, N('2026-10-29T02:05:00'), CB={D26: 81078.04}, quotes={'STRC': {'c': 101.05, 't': int(N('2026-10-26T20:00:00').timestamp())}, 'MSTR': {'c': 151.1, 't': int(N('2026-10-26T20:00:00').timestamp())}})
chk('27 Grok R-t chain: Yahoo\'s final bar later replaces all three (primary, logged)', oc2['closes'][D26]['BTC'] == 81100.0 and oc2['closes'][D26]['MSTR'] == 151.1 and oc2['closes'][D26]['STRC'] == 101.05 and all(str(oc2['fallback_sources'].get(D26, {}).get(k, 'yahoo')).startswith('yahoo') and oc2['fallback_sources'].get(D26, {}).get(k) != 'yahoo-meta' for k in ('BTC', 'MSTR', 'STRC')) and any(r['date'] == D26 and 'replaced by primary' in r['src'] for r in oc2['revisions_ignored']), oc2['fallback_sources'].get(D26))
rowsc = [(D21, b21), (D22, 81311.89), (D23, round(P['closes'][D23]['BTC'], 2)), (D24, 81000.0), ('2026-10-25', 81050.0), (D26, 81078.04)]
mc_h = copy.deepcopy(mc); mc_h['btc_provisional'] = []
rcc_, Bc_, pvc_, oc_ = btcd_file(rowsc, mc_h, '2026-10-27T02:00:00')
chk('27 Grok R-t chain: btc-daily marks Oct 26 provisional while history has the coinbase tag', rcc_ == 0 and D26 in pvc_ and Bc_[D26] == 81078.04, (rcc_, pvc_, oc_[-200:]))
oc2_h = copy.deepcopy(oc2)
rcd_, Bd_, pvd_, od_ = btcd_file(rowsc, oc2_h, '2026-10-29T02:10:00', prov=pvc_)
chk('27 Grok R-t chain: ... and heals it to Yahoo\'s final, no longer provisional', rcd_ == 0 and Bd_[D26] == 81100.0 and D26 not in pvd_, (rcd_, Bd_.get(D26), pvd_, od_[-200:]))
F = [n for n, ok in R if not ok]
print('FREEZE SIMULATIONS', len(R), 'FAIL', len(F)); sys.exit(1 if F else 0)
