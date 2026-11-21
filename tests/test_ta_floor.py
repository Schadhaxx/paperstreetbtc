#!/usr/bin/env python3
"""Tests for tools/ta_floor.py (skunkworks long-term price floor).

Pure Python, no network, no browser. Asserts the job reproduces the
mockup's verified numbers exactly, and that the break rule behaves:
a weekly close 2%+ under the floor breaks it, anything inside the
tolerance does not.

usage: python3 tests/test_ta_floor.py   exit 0 = all pass
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'tools'))
import ta_floor as TF

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAILY = os.path.join(R, 'assets', 'data', 'btc-daily.json')
FIXTURE = os.path.join(R, 'assets', 'data', 'ta-floor.json')

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


daily, _src = TF.load_daily(DAILY)
dates, closes, lows, last_date = TF.build_weeks(daily)
out = TF.compute_floor(dates, closes, lows)

chk('262 weeks 2021-11-15..2026-11-16',
    len(closes) == 262 and str(dates[0]) == '2021-11-15'
    and str(dates[-1]) == '2026-11-16', (len(closes), dates[0], dates[-1]))
chk('anchor 21 Nov 2022 $15,787.28',
    out['anchor'] == {'i': 53, 'date': '2022-11-21', 'low': 15787.28},
    out['anchor'])
chk('binding low 11 Sep 2023 $25,162.65',
    out['binding'] == {'i': 95, 'date': '2023-09-11', 'low': 25162.65},
    out['binding'])
chk('slope +$223.22/week', abs(out['slopePerWeek'] - 223.2231) < 0.001,
    out['slopePerWeek'])
chk('floor now $62,217.68', out['floorNow'] == 62217.68, out['floorNow'])
chk('floor +52w $73,825.28', out['floorPlus52'] == 73825.28,
    out['floorPlus52'])
chk('price 0.5% below the floor', out['pctAbove'] == -0.5, out['pctAbove'])
chk('touches Sep 2023 + Jun 2026',
    [t['date'] for t in out['touches']] == ['2023-09-11', '2026-06-29'],
    out['touches'])
chk('last close $61,901.82', out['lastClose'] == 61901.82, out['lastClose'])
chk('not broken', out['broken'] is False, out['broken'])
chk('break trigger $60,973.33', out['breakTrigger'] == 60973.33,
    out['breakTrigger'])
chk('max undershoot -1.65% (Dec 2022 / Jan 2023 brushed under, recovered)',
    out['maxUnderPct'] == -1.65, out['maxUnderPct'])

# The shipped fixture matches a fresh compute exactly (same maths, same file).
fix = json.load(open(FIXTURE))
chk('fixture matches fresh compute on every mockup key',
    all(fix.get(k) == v for k, v in out.items()), '')
chk('fixture asOf 2026-11-19', fix.get('asOf') == '2026-11-19',
    fix.get('asOf'))

# Break rule, exercised by mutating the last weekly close on the real data.
import copy
c2 = list(closes)
c2[-1] = out['floorNow'] * 0.97   # 3% under the floor
chk('last close 3% under: broken',
    TF.compute_floor(dates, c2, lows)['broken'] is True)
c3 = list(closes)
c3[-1] = out['floorNow'] * 0.99   # 1% under: inside tolerance
chk('last close 1% under: not broken',
    TF.compute_floor(dates, c3, lows)['broken'] is False)
# A mid-series close 3% under also breaks it (the rule is any weekly close).
c4 = list(closes)
i_dec22 = dates.index(__import__('datetime').date(2022, 12, 26))
fl_dec22 = out['anchor']['low'] + out['slopePerWeek'] * (i_dec22 - 53)
c4[i_dec22] = fl_dec22 * 0.97
chk('Dec 2022 close 3% under: broken',
    TF.compute_floor(dates, c4, lows)['broken'] is True)

print('TA FLOOR TESTS', n, 'FAIL', f)
sys.exit(1 if f else 0)
