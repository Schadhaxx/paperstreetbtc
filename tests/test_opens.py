#!/usr/bin/env python3
"""CR-005 opens: validation matrix, 9:30 ET time conversion (DST), opens.json shape/coverage, golden values, and the
page's open/close fallback (opx in compare.js, run in node). Offline except --history URL. usage: python3 tests/test_opens.py [--history PATH]"""
import json, math, os, re, subprocess, sys, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, 'tools'))
import opens as OP
src = sys.argv[sys.argv.index('--history') + 1] if '--history' in sys.argv else 'https://raw.githubusercontent.com/Schadhaxx/paperstreetbtc/data/history.json'
H = json.load(urllib.request.urlopen(src, timeout=30)) if src.startswith('http') else json.load(open(src)); C = H['closes']; D = sorted(C)
O = json.load(open(os.path.join(ROOT, 'assets/data/opens.json')))
n = f = 0
def chk(name, ok, info=''):
    global n, f; n += 1
    if not ok: f += 1; print('FAIL', name, info)
# 1. bad values are rejected, good ones accepted
for v in [math.inf, -math.inf, float('1e999'), 'Infinity', math.nan, 'NaN', True, False, None, '', '123.4', 'garbage', 0, -5, 1e12, 10.0, [], {}]:
    chk(f'rejects {v!r}', not OP.good(v, 100.0))
for v in [100.0, 80, 124.9, 75.1]: chk(f'accepts {v!r}', OP.good(v, 100.0))
chk('no reference: still rejects 0', not OP.good(0, None)); chk('no reference: accepts 5', OP.good(5, None))
# 2. validate(): corrupt structures
for bad in [[], 'x', None, {}, {'o': []}, {'o': 'x'}]: chk(f'validate rejects top level {bad!r}', OP.validate(bad, C))
chk('validate rejects weekend row', OP.validate({'o': {'2026-10-24': {'BTC': 1.0}}}, C))
chk('validate rejects unknown asset', OP.validate({'o': {D[-1]: {'XYZ': 1.0}}}, C))
chk('validate rejects row not object', OP.validate({'o': {D[-1]: 5}}, C))
chk('validate rejects open 30% off prior close', OP.validate({'o': {D[-1]: {'TSLA': C[D[-2]]['TSLA'] * 1.3}}}, C))
# 3. 9:30 AM ET in UTC across DST (EDT ends Sun Nov 1 2026)
for d, z in [('2026-10-30', '13:30'), ('2026-11-02', '14:30'), ('2026-03-06', '14:30'), ('2026-03-09', '13:30'), ('2026-11-27', '14:30')]:
    chk(f'BTC 9:30 ET on {d} = {z}Z', OP.btc_ts(d).strftime('%H:%M') == z, OP.btc_ts(d))
# 4. opens.json: valid, trading sessions only, full coverage up to the newest open
chk('opens.json validates against history', not OP.validate(O, C), OP.validate(O, C)[:3])
chk('no weekend dates', all(__import__('datetime').date.fromisoformat(d).weekday() < 5 for d in O['o']))
miss = [(d, a) for d in D if d <= max(O['o']) for a in OP.ASSETS if a not in O['o'].get(d, {})]
chk('every asset has an open for every session to the newest open', not miss, miss[:5])
chk('opens start at the 2025-12-31 base', min(O['o']) == D[0], min(O['o']))
# 5. BTC is the 9:30 ET price, not a shifted/stale close: it must rarely equal the prior session's close or that day's close
same = [d for i, d in enumerate(D[1:], 1) if d in O['o'] and (abs(O['o'][d]['BTC'] / C[D[i - 1]]['BTC'] - 1) < 1e-6 or abs(O['o'][d]['BTC'] / C[d]['BTC'] - 1) < 1e-6)]
chk('BTC open is not a copied close (< 2% of days equal)', len(same) < 0.02 * len(O['o']), len(same))
for a in OP.YSYM:
    eq = sum(1 for d in O['o'] if abs(O['o'][d][a] / C[d][a] - 1) < 1e-9); chk(f'{a} opens are not the closes (< 25% equal)', eq < 0.25 * len(O['o']), eq)
# 6. golden values, hand-checked from the source pages (Coinbase 5-min candle 13:30Z; Yahoo daily bar)
for d, a, v in [('2026-10-29', 'BTC', 80144.29), ('2026-10-21', 'TSLA', 381.429993), ('2026-10-26', 'TSLA', 383.829987)]:
    chk(f'golden {d} {a} = {v}', abs(O['o'][d][a] - v) < 1e-4, O['o'][d][a])
# 7. page fallback: opx() in compare.js, run in node with mocks
js = open(os.path.join(ROOT, 'assets/js/compare.js')).read(); m = re.search(r"let LFB=0;const opx=.*?;\n", js)
chk('compare.js has opx()', bool(m))
if m:
    t = m.group(0) + r"""
const out=[];const t=(o,c)=>{OP={'d':{'X':o}};CL={'d':{'X':c}};LFB=0;const v=opx('d','X');out.push([v,LFB])};
for(const o of [Infinity,-Infinity,NaN,'NaN','123',true,null,undefined,0,-1,200,50])t(o,100);t(101,100);OP=null;CL={'d':{'X':100}};LFB=0;out.push([opx('d','X'),LFB]);
console.log(JSON.stringify(out))"""
    r = json.loads(subprocess.run(['node', '-e', 'let OP,CL;' + t], capture_output=True, text=True, check=True).stdout)
    chk('bad/missing/absurd opens fall back to close and are counted', all(v == [100, 1] for v in r[:12]), r[:12])
    chk('good open is used, not counted', r[12] == [101, 0], r[12]); chk('missing opens file -> close, counted', r[13] == [100, 1], r[13])
# 8. nightly re-fetch window (last 5 sessions): retries a missing asset-day, applies a revision, never lets a bad value overwrite
import copy, tempfile
st = copy.deepcopy(O); L5 = D[-5:]; old7 = D[-7]
del st['o'][D[-3]]['TSLA']; del st['o'][old7]['GLD']
Y = {x: {d: O['o'][d][x] for d in O['o']} for x in OP.YSYM}
Y['TSLA'][D[-3]] = O['o'][D[-3]]['TSLA']; Y['MSTR'][D[-2]] = math.nan; Y['PLTR'][D[-1]] = round(O['o'][D[-1]]['PLTR'] * 1.01, 6)
Y['SPY'][D[-1]] = 0; Y['GLD'][old7] = O['o'][old7]['GLD']; Y['QQQ'][D[-4]] = C[D[-5]]['QQQ'] * 1.4
asked = []
def fb(d): asked.append(d); return 'garbage' if d == D[-4] else O['o'][d]['BTC']
oy, ob, osl = OP.yahoo, OP.btc_930, OP.time.sleep
OP.yahoo = lambda sym, since: {d: v for d, v in Y[{v: k for k, v in OP.YSYM.items()}[sym]].items() if d >= since}; OP.btc_930 = fb; OP.time.sleep = lambda s: None
with tempfile.TemporaryDirectory() as td:
    hp, op_ = os.path.join(td, 'h.json'), os.path.join(td, 'o.json'); json.dump(H, open(hp, 'w')); json.dump(st, open(op_, 'w'))
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()): rc = OP.main([op_, '--history', hp])
    N = json.load(open(op_))['o']
OP.yahoo, OP.btc_930, OP.time.sleep = oy, ob, osl
chk('refetch run succeeds', rc == 0, rc)
chk('refetch asks only the last 5 sessions (BTC)', asked == L5, asked)
chk('missing asset-day inside the window is filled', N[D[-3]].get('TSLA') == O['o'][D[-3]]['TSLA'], N[D[-3]].get('TSLA'))
chk('missing asset-day outside the window stays missing (window really is 5)', 'GLD' not in N[old7])
chk('good revised open replaces the stored one', N[D[-1]]['PLTR'] == Y['PLTR'][D[-1]], N[D[-1]]['PLTR'])
chk('NaN re-fetch rejected, stored value kept', N[D[-2]]['MSTR'] == O['o'][D[-2]]['MSTR'], N[D[-2]]['MSTR'])
chk('0 re-fetch rejected, stored value kept', N[D[-1]]['SPY'] == O['o'][D[-1]]['SPY'])
chk('+40% vs prior close rejected, stored value kept', N[D[-4]]['QQQ'] == O['o'][D[-4]]['QQQ'])
chk('garbage BTC re-fetch rejected, stored value kept', N[D[-4]]['BTC'] == O['o'][D[-4]]['BTC'])
chk('output still validates (trading days only)', not OP.validate({'o': N}, C))
print(f'test_opens: {n} checks, {f} failed'); sys.exit(1 if f else 0)
