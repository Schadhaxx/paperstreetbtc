#!/usr/bin/env python3
"""history_stale() (extracted from .github/workflows/prices.yml): a FINAL BTC
day whose history.json value is still from a fallback source (Coinbase /
CoinGecko) asks for a rebuild about every 30 min, so Yahoo's final bar
replaces it and btc-daily.json can advance the same day instead of waiting
for the next stock session close. No network.
Run: python3 tests/test_history_stale_fallback.py"""
import datetime as dt, json, os, sys, textwrap
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
L = open(os.path.join(ROOT, '.github/workflows/prices.yml')).read().split('\n')
i0 = next(i for i, l in enumerate(L) if 'import datetime as _dt, zoneinfo as _zi' in l)
i1 = next(i for i, l in enumerate(L) if '# --- history end ---' in l)
G = {'json': json}; exec(textwrap.dedent('\n'.join(L[i0:i1])), G)
stale = G['history_stale']
N = lambda s: dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc)
base = {'v': 1, 'closes': {'2026-11-09': {'BTC': 75223.15}, '2026-11-10': {'BTC': 73697.87}}, 'btc_provisional': []}
R = []
def chk(name, ok): R.append(ok); print('PASS' if ok else 'FAIL', name)
cb = dict(base, fallback_sources={'2026-11-10': {'BTC': 'coinbase-unchecked'}})
chk('coinbase BTC day (final) -> stale at :00-:04 / :30-:34', stale(cb, N('2026-11-11T10:30:00')) and stale(cb, N('2026-11-11T11:02:00')))
chk('coinbase BTC day -> not stale off the 30-min slot', not stale(cb, N('2026-11-11T10:25:00')))
chk('coingecko source also counts', stale(dict(base, fallback_sources={'2026-11-10': {'BTC': 'coingecko'}}), N('2026-11-11T10:30:00')))
chk('yahoo source -> not stale', not stale(dict(base, fallback_sources={'2026-11-10': {'BTC': 'yahoo-unchecked'}}), N('2026-11-11T10:30:00')))
chk('stock-only fallback -> not stale', not stale(dict(base, fallback_sources={'2026-11-10': {'TSLA': 'finnhub'}}), N('2026-11-11T10:30:00')))
chk('Tiingo-confirmed date -> not stale', not stale(dict(cb, tiingo_final={'2026-11-10': {}}), N('2026-11-11T10:30:00')))
chk('UTC day not final yet (00:10 UTC rollover) -> not stale', not stale(cb, N('2026-11-11T00:01:00')))
chk('no fallback -> not stale (unchanged behaviour)', not stale(base, N('2026-11-11T10:30:00')))
print(f'{sum(R)}/{len(R)} PASS'); sys.exit(0 if all(R) else 1)
