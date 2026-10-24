#!/usr/bin/env python3
"""TG (Tiingo) tests. Runs the REAL tiingo_* code extracted from .github/workflows/prices.yml against MOCKED Tiingo responses (no network,
no key needed). Exit 1 on any failure. usage: python3 tests/test_tiingo.py [--repo DIR]"""
import argparse, copy, datetime as dt, json, os, re, sys, textwrap, zoneinfo
ap = argparse.ArgumentParser(); ap.add_argument('--repo', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')); a = ap.parse_args()
YML = open(os.path.join(a.repo, '.github/workflows/prices.yml')).read(); L = YML.split('\n')
i0 = next(i for i, l in enumerate(L) if 'import datetime as _dt, zoneinfo as _zi' in l); i1 = next(i for i, l in enumerate(L) if '# --- history end ---' in l)
G = {'json': json}; exec(textwrap.dedent('\n'.join(L[i0:i1])), G)
R = []
def chk(n, ok, info=''): R.append(ok); print('PASS' if ok else 'FAIL', n, '' if ok else info, flush=True)
UTC = dt.timezone.utc; N = lambda s: dt.datetime.fromisoformat(s).replace(tzinfo=UTC)
def mock(T, calls, boom=()):
    """T: {(sym, date): close}. Stocks return close AND a wildly different adjClose/divCash (must never be read)."""
    def get_t(u):
        calls.append(u)
        if 'crypto' in u:
            d = re.search(r'startDate=([\d-]+)', u).group(1)
            if ('BTC', d) in boom: raise OSError('boom')
            return [{'ticker': 'btcusd', 'priceData': ([{'date': d + 'T00:00:00+00:00', 'close': T[('BTC', d)]}] if ('BTC', d) in T else [])}]
        t = re.search(r'/daily/([^/]+)/prices', u).group(1); d = re.search(r'startDate=([\d-]+)', u).group(1)
        k = {v: k for k, v in G['TG_SY'].items()}[t]
        if (k, d) in boom: raise OSError('boom')
        return [{'date': d + 'T00:00:00.000Z', 'close': T[(k, d)], 'adjClose': T[(k, d)] * 0.9, 'divCash': 1.9}] if (k, d) in T else []
    return get_t
D = '2026-10-22'; SYMS = ['BTC', 'MSTR', 'STRC', 'TSLA', 'PLTR', 'SPY', 'QQQ', 'BRK.B', 'GLD']
BASE = {'BTC': 81311.89, 'MSTR': 300.0, 'STRC': 100.0, 'TSLA': 400.0, 'PLTR': 150.0, 'SPY': 600.0, 'QQQ': 500.0, 'BRK.B': 480.0, 'GLD': 300.0}
def H(row=None, prov=(), fs=None): return {'closes': {D: dict(row or BASE)}, 'btc_provisional': list(prov), 'fallback_sources': fs or {}}
LATE = N('2026-10-23T01:00:00')   # Oct 22 9 PM EDT: stocks final (8 PM ET) and BTC final (00:20 UTC)
T0 = {(k, D): v for k, v in BASE.items()}
# 1 identical -> no flags, closes untouched, one call per symbol, cached
h = H(); c = []; f = G['tiingo_check'](h, LATE, mock(T0, c))
chk('identical: no flags', f == [] and h['tiingo_flags'] == [])
chk('identical: closes unchanged', h['closes'] == {D: BASE})
chk('identical: 9 calls', len(c) == 9, len(c))
chk('cache: stored raw close', h['tiingo_ref'][D]['MSTR']['v'] == 300.0)
c2 = []; G['tiingo_check'](h, LATE + dt.timedelta(minutes=5), mock(T0, c2)); chk('cache: no second call', c2 == [], c2)
# 2 thresholds: stocks 0.05%, BTC 0.3% (strictly greater flags)
for k, base, tol in [('MSTR', 300.0, 0.0005), ('BTC', 81311.89, 0.003)]:
    for mult, want in [(1 + tol * 0.98, 0), (1 + tol * 1.05, 1), (1 - tol * 1.05, 1)]:
        T = dict(T0); T[(k, D)] = round(base * mult, 6); h = H(); f = G['tiingo_check'](h, LATE, mock(T, []))
        chk(f'threshold {k} x{mult:.5f} -> {want} flag', len([x for x in f if x['sym'] == k]) == want and h['closes'][D][k] == base, f)
T = dict(T0); T[('SPY', D)] = 601.0; h = H(); f = G['tiingo_check'](h, LATE, mock(T, []))
chk('stock 0.17% flagged (BTC tol not applied to stocks)', [x['sym'] for x in f] == ['SPY'] and f[0]['diff_pct'] == round(1 / 601 * 100, 4), f)
chk('flag never changes the site value', h['closes'][D]['SPY'] == 600.0)
f2 = G['tiingo_check'](h, LATE + dt.timedelta(hours=1), mock(T, [])); chk('flag not duplicated on rerun', f2 == [] and len(h['tiingo_flags']) == 1)
# 2b exactly at the threshold is NOT flagged (strictly greater); a neighbouring-date row is never used
T = dict(T0); T[('GLD', D)] = 10000.0; h = H(dict(BASE, GLD=10005.0)); f = G['tiingo_check'](h, LATE, mock(T, [])); chk('exactly 0.05% not flagged', f == [], f)
def mock_extra(T):
    g = mock(T, [])
    def get_t(u):
        j = g(u)
        if 'crypto' in u: j[0]['priceData'].insert(0, {'date': '2026-10-21T00:00:00+00:00', 'close': 1.0})
        else: j.insert(0, {'date': '2026-10-21T00:00:00.000Z', 'close': 1.0})
        return j
    return get_t
h = H(); f = G['tiingo_check'](h, LATE, mock_extra(T0)); chk('other-date row ignored', f == [] and h['tiingo_ref'][D]['BTC']['v'] == BASE['BTC'], f)
# 3 raw close only: adjClose is 10% off in the mock; reading it would flag everything
h = H(); f = G['tiingo_check'](h, LATE, mock(T0, [])); chk('raw close only (adjClose/divCash ignored)', f == [])
# 4 not final -> no call
c = []; h = H(); G['tiingo_check'](h, N('2026-10-22T23:30:00'), mock(T0, c)); chk('stocks before 8 PM ET: no call', not any('/daily/' in u for u in c), c)
c = []; h = H(prov=[D]); G['tiingo_check'](h, LATE, mock(T0, c)); chk('provisional BTC: no call', not any('crypto' in u for u in c), c)
c = []; h = H(); G['tiingo_check'](h, N('2026-10-23T00:10:00'), mock(T0, c)); chk('BTC before +20 min: no call', not any('crypto' in u for u in c), c)
# 5 ffill-not-listed skipped; fallback-sourced value IS checked and labelled
c = []; h = H(fs={D: {'GLD': 'ffill-not-listed', 'TSLA': 'finnhub-unchecked'}}); T = dict(T0); T[('TSLA', D)] = 404.0
f = G['tiingo_check'](h, LATE, mock(T, c)); chk('ffill skipped', not any('/daily/gld/' in u for u in c)); chk('fallback value flagged with its source', f and f[0]['src'] == 'finnhub-unchecked', f)
# 6 call cap + miss retry hourly
c = []; h = {'closes': {f'2026-10-{d:02d}': dict(BASE) for d in (19, 20, 21, 22)}, 'btc_provisional': [], 'fallback_sources': {}}
G['tiingo_check'](h, LATE, mock({}, c)); chk('call cap per run', len(c) == G['TG_MAX_CALLS'], len(c)); c1 = list(c)
c = []; G['tiingo_check'](h, LATE + dt.timedelta(minutes=30), mock({}, c)); chk('miss: not re-called within the hour (only new pairs)', len(c) == G['TG_MAX_CALLS'] and not set(c) & set(c1), len(c))
c = []; G['tiingo_check'](h, LATE + dt.timedelta(minutes=65), mock({}, c)); chk('miss retried after 60 min (capped)', 0 < len(c) <= G['TG_MAX_CALLS'], len(c))
# 7 errors never raise; 8-day window
c = []; h = H(); f = G['tiingo_check'](h, LATE, mock(T0, c, boom={('BTC', D), ('MSTR', D)})); chk('Tiingo error -> no reference, no raise', f == [] and h['tiingo_ref'][D]['BTC']['v'] is None)
c = []; h = H(); G['tiingo_check'](h, LATE + dt.timedelta(days=9), mock(T0, c)); chk('older than 7 days: no call, cache pruned', c == [] and h['tiingo_ref'] == {}, c)
# 8 garbage values from Tiingo ignored
for bad in (0, -5, None, 'x', float('inf'), float('-inf'), 1e999, float('nan'), True, False):
    T = dict(T0); T[('PLTR', D)] = bad; T[('BTC', D)] = bad; h = H(); f = G['tiingo_check'](h, LATE, mock(T, [])); chk(f'bad Tiingo close {bad!r} ignored', f == [] and h['tiingo_ref'][D]['PLTR']['v'] is None and h['tiingo_ref'][D]['BTC']['v'] is None)
# 9 key handling: header only, never in URL; scoped to the fetch step
cap = {}
class FakeResp:
    def __enter__(s): return s
    def __exit__(s, *x): pass
    def read(s): return b'[]'
import urllib.request as ur
orig = ur.urlopen
def fake(r, timeout=0): cap['url'] = r.full_url; cap['auth'] = r.get_header('Authorization'); return FakeResp()
G['_ur'].urlopen = fake
try: G['tiingo_getter']('SECRETKEY123')('https://api.tiingo.com/tiingo/daily/spy/prices?startDate=x&endDate=x')
finally: G['_ur'].urlopen = orig
chk('key in Authorization header only', cap.get('auth') == 'Token SECRETKEY123' and 'SECRETKEY123' not in cap.get('url', ''))
jobs = YML.split('\n  btcd-stall-check:'); fetch_job, rest = jobs[0], jobs[1]
chk('TIINGO secret referenced exactly once, in the fetch job', YML.count('secrets.TIINGO_API_KEY') == 1 and 'secrets.TIINGO_API_KEY' in fetch_job)
chk('weekend stall job and recap job never see the key', 'TIINGO' not in rest)
chk('no key printed', not re.search(r"print\([^)]*tk_|print\([^)]*key", '\n'.join(L[i0:i1])))
chk('Tiingo never writes closes (no closes assignment in block)', not re.search(r"h\['closes'\]\[[^]]+\]\[[^]]+\]\s*=", YML.split('# --- tiingo begin ---')[1].split('# --- tiingo end ---')[0]))
chk('wire-up only when key set and guarded', "if tk_:" in YML and "Tiingo cross-check skipped" in YML)
print(f'TIINGO: {sum(R)}/{len(R)} passed'); sys.exit(0 if all(R) else 1)
