#!/usr/bin/env python3
"""CR-005: daily OPEN prices for lump-sum pricing on the Custom page (assets/data/opens.json).
Stocks/ETFs: the regular-session 9:30 AM ET open from the Yahoo daily bar (same vendor as the closes).
BTC: the 9:30 AM ET price = open of the Coinbase BTC-USD 5-minute candle starting 9:30 AM America/New_York
(13:30 UTC in EDT, 14:30 UTC in EST), so BTC follows the same market-open rule as the stocks.
Only dates that are history.json trading sessions are written (weekends/holidays never get an open).
Every value is validated: finite, not bool, > 0, and within +/-25% of the prior session's close; bad values are
dropped (the page then prices that asset/date at the close and says so). A failed source never fails the run.
Each run re-fetches the last REFETCH (5) history sessions (or from --since), so a failed asset-day is retried and a
revised Yahoo open replaces the stored one; a re-fetched value that fails validation never overwrites a stored good one.
usage: python3 tools/opens.py OUT.json --history history.json [--since YYYY-MM-DD]
       python3 tools/opens.py OUT.json --history history.json --check-only   (validate an existing file, no network)"""
import json, math, sys, time, datetime as dt, urllib.request
from zoneinfo import ZoneInfo
NY = ZoneInfo('America/New_York')
YSYM = {'MSTR': 'MSTR', 'STRC': 'STRC', 'TSLA': 'TSLA', 'PLTR': 'PLTR', 'SPY': 'SPY', 'QQQ': 'QQQ', 'BRK.B': 'BRK-B', 'GLD': 'GLD'}
ASSETS = ['BTC'] + list(YSYM)
BAND = 0.25
REFETCH = 5   # sessions re-fetched every night

def good(v, ref):
    """Accept only a real positive finite number near the reference close."""
    if isinstance(v, bool) or not isinstance(v, (int, float)): return False
    if not math.isfinite(v) or v <= 0: return False
    if ref is not None and not (abs(v / ref - 1) <= BAND): return False
    return True

def _get(u):
    r = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0 paperstreet-opens'})
    return json.load(urllib.request.urlopen(r, timeout=30))

def yahoo(sym, since):
    p1 = int(dt.datetime.fromisoformat(since).replace(tzinfo=dt.timezone.utc).timestamp()) - 3 * 86400
    j = _get(f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={p1}&period2={int(time.time()) + 86400}&interval=1d')
    r = j['chart']['result'][0]; o = r['indicators']['quote'][0]['open']
    return {dt.datetime.fromtimestamp(t, NY).date().isoformat(): v for t, v in zip(r['timestamp'], o)}

def btc_ts(d):
    """9:30 AM America/New_York on date d, in UTC (13:30Z in EDT, 14:30Z in EST)."""
    return dt.datetime.fromisoformat(d + 'T09:30:00').replace(tzinfo=NY).astimezone(dt.timezone.utc)

def btc_930(d):
    t = btc_ts(d)
    s = t.strftime('%Y-%m-%dT%H:%M:%SZ')
    c = _get(f'https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=300&start={s}&end={s}')
    ts = int(t.timestamp())
    for row in c:  # [time, low, high, open, close, volume]
        if int(row[0]) == ts: return row[3]
    return None

def refs(C, D):
    """prior-session close per (date, asset); first session uses its own close."""
    out = {}
    for i, d in enumerate(D):
        p = C[D[i - 1]] if i else C[d]
        out[d] = {a: p.get(a) for a in ASSETS}
    return out

def validate(O, C):
    D = sorted(C); R = refs(C, D); bad = []
    if not isinstance(O, dict) or not isinstance(O.get('o'), dict): return ['top level must be {"o": {date: {asset: open}}}']
    for d, row in O['o'].items():
        if d not in C: bad.append(f'{d}: not a history trading session'); continue
        if not isinstance(row, dict): bad.append(f'{d}: row not an object'); continue
        for a, v in row.items():
            if a not in ASSETS: bad.append(f'{d} {a}: unknown asset')
            elif not good(v, R[d][a]): bad.append(f'{d} {a}: bad open {v!r}')
    return bad

def main(a):
    out = a[0]; C = json.load(open(a[a.index('--history') + 1]))['closes']; D = sorted(C); R = refs(C, D)
    try: O = json.load(open(out))
    except Exception: O = {}
    if '--check-only' in a:
        b = validate(O, C); print('\n'.join(b) or f'opens OK: {len(O.get("o", {}))} sessions'); return 1 if b else 0
    o = O.get('o') if isinstance(O.get('o'), dict) else {}
    o = {d: r for d, r in o.items() if d in C and isinstance(r, dict)}
    since = a[a.index('--since') + 1] if '--since' in a else (min(D[-REFETCH], max(o)) if o else D[0])
    todo = [d for d in D if d >= since]
    for a_, sym in YSYM.items():
        try: Y = yahoo(sym, since)
        except Exception as e: print(f'WARN yahoo {sym}: {e}'); continue
        for d in todo:
            v = Y.get(d)
            if good(v, R[d][a_]): o.setdefault(d, {})[a_] = round(float(v), 6)   # good re-fetch replaces (revision); bad one is dropped, stored value kept
            elif v is not None: print(f'WARN {d} {a_}: rejected open {v!r}')
    for d in todo:
        try: v = btc_930(d)
        except Exception as e: print(f'WARN coinbase {d}: {e}'); v = None
        if good(v, R[d]['BTC']): o.setdefault(d, {})['BTC'] = round(float(v), 2)
        elif v is not None: print(f'WARN {d} BTC: rejected open {v!r}')
        time.sleep(0.2)
    old = O.get('o') if isinstance(O, dict) else None; oldu = O.get('updated') if isinstance(O, dict) else None
    O = {'v': 1, 'note': 'CR-005 lump-sum opens. Stocks/ETFs: Yahoo regular-session open. BTC: Coinbase BTC-USD 9:30 AM ET 5-min candle open. Trading sessions only.',
         'updated': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'o': dict(sorted(o.items()))}
    if old == O['o'] and oldu: O['updated'] = oldu   # unchanged opens -> byte-identical file, no commit
    b = validate(O, C)
    if b: print('refusing to write:', b[:5]); return 1
    tmp = out + '.tmp'; json.dump(O, open(tmp, 'w'), separators=(',', ':'), allow_nan=False); __import__('os').replace(tmp, out)
    miss = [(d, x) for d in D for x in ASSETS if x not in o.get(d, {})]
    print(f'opens: {len(o)} sessions written, {len(miss)} asset-days missing (priced at close):', miss[:10]); return 0

if __name__ == '__main__': sys.exit(main(sys.argv[1:]))
