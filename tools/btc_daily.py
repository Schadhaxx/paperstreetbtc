#!/usr/bin/env python3
"""Append FINAL daily BTC-USD closes (UTC day, weekends included) to assets/data/btc-daily.json.
Source: Yahoo Finance BTC-USD daily bars (same source as the file and as history.json). A UTC day counts as final
20 minutes after it ends. Only dates after the file's last date are added (backfills any gap); nothing is rewritten.
Exit 0 = ok (changed or not), 1 = fetch/validation failed (file untouched)."""
import json, sys, time, datetime as dt, urllib.request, os
F = sys.argv[1] if len(sys.argv) > 1 else 'assets/data/btc-daily.json'
def fetch(u, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0 paperstreet'}), timeout=20) as r: return json.load(r)
        except Exception as e:
            if i == tries - 1: raise
            time.sleep([5, 15, 30][min(i, 2)])
try:
    j = json.load(open(F)); last = j['d'][-1][0]
    now = dt.datetime.now(dt.timezone.utc)
    p0 = int((dt.datetime.fromisoformat(last).replace(tzinfo=dt.timezone.utc) - dt.timedelta(days=3)).timestamp())
    r = fetch(f'https://query1.finance.yahoo.com/v8/finance/chart/BTC-USD?period1={p0}&period2={int(now.timestamp())+86400}&interval=1d')['chart']['result'][0]
    bars = {}
    for t, c in zip(r.get('timestamp') or [], r['indicators']['quote'][0]['close']):
        if c is None: continue
        d = dt.datetime.fromtimestamp(t, dt.timezone.utc).date()
        if now >= dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc) + dt.timedelta(days=1, minutes=20): bars[d.isoformat()] = round(float(c), 2)
    new = sorted(d for d in bars if d > last)
    # no gaps allowed: every calendar day from last+1 to the newest added must be present
    want = []; d = dt.date.fromisoformat(last) + dt.timedelta(days=1)
    while new and d.isoformat() <= new[-1]: want.append(d.isoformat()); d += dt.timedelta(days=1)
    if new and want != new: print('gap in Yahoo bars, not appending:', sorted(set(want) - set(new))); sys.exit(1)
    if not new: print(f'btc-daily up to date (through {last})'); sys.exit(0)
    prev = j['d'][-1][1]
    for d in new:
        if not (0.5 * prev < bars[d] < 2 * prev): print('implausible close', d, bars[d]); sys.exit(1)
        prev = bars[d]
    j['d'] += [[d, bars[d]] for d in new]; j['end'] = new[-1]
    tmp = F + '.tmp'; json.dump(j, open(tmp, 'w'), separators=(',', ':')); json.load(open(tmp)); os.replace(tmp, F)
    print('btc-daily appended:', ', '.join(f'{d} {bars[d]}' for d in new))
except SystemExit: raise
except Exception as e:
    print('btc-daily update failed (file untouched):', type(e).__name__, e); sys.exit(1)
