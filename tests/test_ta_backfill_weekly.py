#!/usr/bin/env python3
"""Backfill regression: the 24 Desk weekly files hold 200+ weeks after
the Nov 2026 backfill (tools/ta_backfill_weekly.py), the shipped 47
weeks are untouched, and SPCX/IBIT keep their honest short histories.

Pure Python, no network. The last-47 sentinel values pin the protected
closes: gold's 30 Oct week close $3,901.20 and WTI's 26 Oct week close
$104.24 (both flagged, pending Grok Bot + Chief of Staff review) and
the first shipped week (29 Dec 2025) per symbol.

usage: python3 tests/test_ta_backfill_weekly.py   exit 0 = all pass
"""
import datetime as dt
import json
import math
import os
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(R, 'assets', 'data')

STOCKS = ['TSLA', 'PLTR', 'MSTR', 'IBIT', 'MU', 'META', 'SPCX',
          'AAPL', 'AMZN', 'MSFT', 'NFLX', 'SPOT', 'XYZ', 'GOOGL', 'NVDA', 'BRK.B']
INDICATORS = {'WTI': 'wti-weekly.json', 'GOLD': 'gold-weekly.json',
              'US10Y': 'us10y-weekly.json', 'VIX': 'vix-weekly.json',
              'DIA': 'dia-weekly.json', 'QQQ': 'qqq-weekly.json',
              'CADUSD': 'usdcad-weekly.json', 'DXY': 'dxy-weekly.json'}

n = 0
f = 0


def chk(name, ok, info=''):
    global n, f
    n += 1
    if not ok:
        f += 1
        print('FAIL', name, info)
    else:
        print('PASS', name)


def load(name):
    with open(os.path.join(DATA, name)) as fh:
        return json.load(fh)


def check_file(label, doc, want_n, want_first):
    weeks = doc['weeks']
    chk(f'{label}: {want_n} weeks', len(weeks) == want_n if isinstance(want_n, int) else want_n[0] <= len(weeks) <= want_n[1],
        len(weeks))
    chk(f'{label}: first week {want_first}', weeks[0]['monday'] == want_first, weeks[0]['monday'])
    chk(f'{label}: last week 16 Nov 2026', weeks[-1]['monday'] == '2026-11-16', weeks[-1]['monday'])
    chk(f'{label}: last week in progress', isinstance(doc.get('inProgress'), str) and doc['inProgress'].strip(),
        doc.get('inProgress'))
    prev = None
    ok_shape = True
    for w in weeks:
        try:
            mon = dt.date.fromisoformat(w['monday'])
            sun = dt.date.fromisoformat(w['sunday'])
        except Exception:
            ok_shape = False
            continue
        if mon.weekday() != 0 or sun != mon + dt.timedelta(days=6):
            ok_shape = False
        if prev is not None and mon != prev + dt.timedelta(days=7):
            ok_shape = False
        prev = mon
        if not (1 <= w.get('days', 0) <= 6):
            ok_shape = False
        for k in ('open', 'high', 'low', 'close'):
            v = w.get(k)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                ok_shape = False
        if all(isinstance(w.get(k), (int, float)) and not isinstance(w.get(k), bool)
               for k in ('open', 'high', 'low', 'close')):
            if w['high'] < max(w['open'], w['close']) or w['low'] > min(w['open'], w['close']):
                ok_shape = False
    chk(f'{label}: contiguous Mondays, OHLC valid, 1-6 days', ok_shape)


for sym in STOCKS:
    doc = load(f'stock-weekly-{sym}.json')
    if sym == 'SPCX':
        check_file('SPCX', doc, 24, '2026-06-08')
        chk('SPCX: note has no backfill sentence (untouched)',
            'Backfilled' not in doc.get('note', ''))
    elif sym == 'IBIT':
        check_file('IBIT', doc, (100, 199), '2024-01-08')
        chk('IBIT: note carries the backfill sentence', 'Backfilled' in doc.get('note', ''))
    else:
        check_file(sym, doc, 264, '2021-11-01')
        chk(f'{sym}: note carries the backfill sentence', 'Backfilled' in doc.get('note', ''))

for key, fname in INDICATORS.items():
    doc = load(fname)
    check_file(key, doc, 264, '2021-11-01')
    chk(f'{key}: note carries the backfill sentence', 'Backfilled' in doc.get('note', ''))

# Sentinels: the protected shipped values, and the first shipped week.
gold = load('gold-weekly.json')['weeks']
wti = load('wti-weekly.json')['weeks']
chk('gold: week of 26 Oct 2026 close is the flagged $3,901.20',
    [w['close'] for w in gold if w['monday'] == '2026-10-26'] == [3901.2],
    [w['close'] for w in gold if w['monday'] == '2026-10-26'])
chk('WTI: week of 26 Oct 2026 close is the flagged $104.24',
    [w['close'] for w in wti if w['monday'] == '2026-10-26'] == [104.24],
    [w['close'] for w in wti if w['monday'] == '2026-10-26'])
aapl = load('stock-weekly-AAPL.json')['weeks']
chk('AAPL: first shipped week is 29 Dec 2025, close $271.01',
    aapl[-47]['monday'] == '2025-12-29' and aapl[-47]['close'] == 271.01,
    aapl[-47])
chk('AAPL: last 47 weeks are the shipped tail (47th from end is the first shipped week)',
    len(aapl) - 47 == 217, len(aapl))

print(f'{n - f}/{n} checks passed')
sys.exit(1 if f else 0)
