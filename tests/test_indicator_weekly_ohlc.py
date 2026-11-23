#!/usr/bin/env python3
"""tools/indicator_weekly.py bars_from_payload — round then check OHLC.

Regression for the Nov 18 2026 CADUSD=X Yahoo bar: close sat ~0.00004
above high in the raw floats, which is consistent once rounded to the
4 decimals CADUSD is shown at. The fixture path already rounded first;
the live Yahoo path did not, so desk-intraday kept CADUSD stale.

No network.
"""
import datetime as dt
import os
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, 'tools'))
import indicator_weekly as IW

n = f = 0
def chk(name, ok, info=''):
    global n, f
    n += 1
    f += (not ok)
    print(('PASS' if ok else 'FAIL'), name, '' if ok else info)

def payload(rows):
    """rows: (date_iso, o, h, l, c). Timestamps are noon UTC."""
    ts, o, h, l, c = [], [], [], [], []
    for d, oo, hh, ll, cc in rows:
        dd = dt.date.fromisoformat(d)
        ts.append(int(dt.datetime(dd.year, dd.month, dd.day, 12, 0, tzinfo=dt.timezone.utc).timestamp()))
        o.append(oo); h.append(hh); l.append(ll); c.append(cc)
    return {'timestamp': ts, 'indicators': {'quote': [{'open': o, 'high': h, 'low': l, 'close': c}]}}

# Exact raw Yahoo CADUSD=X daily bar for Wed 18 Nov 2026 (from the
# desk-intraday failure log). Close is above high by ~4e-5 raw, but
# rounds at nd=4 to o=0.6992 h=0.6993 l=0.6974 c=0.6993, which is consistent.
NOV18 = (
    0.6992322206497192,
    0.6993007063865662,
    0.6974133253097534,
    0.6993447542190552,
)
p = payload([('2026-11-18', *NOV18)])
bars = IW.bars_from_payload('CADUSD', p)
day = dt.date(2026, 11, 18)
chk('Nov 18 CADUSD raw Yahoo bar parses at nd=4', day in bars, bars)
if day in bars:
    b = bars[day]
    chk('Nov 18 rounded values are o=0.6992 h=0.6993 l=0.6974 c=0.6993',
        (b['open'], b['high'], b['low'], b['close']) == (0.6992, 0.6993, 0.6974, 0.6993), b)
    chk('CADUSD SPECS still 4dp', IW.SPECS['CADUSD'][1] == 4, IW.SPECS['CADUSD'])

# A clearly broken bar (low well above high) must still fail closed,
# including after rounding.
try:
    IW.bars_from_payload('CADUSD', payload([('2026-11-18', 0.70, 0.71, 0.80, 0.705)]))
    chk('low above high by a lot still raises', False, 'no error raised')
except RuntimeError as e:
    chk('low above high by a lot still raises', 'OHLC inconsistent' in str(e), str(e))

print('INDICATOR_WEEKLY_OHLC TESTS', n, 'FAIL', f)
sys.exit(1 if f else 0)
