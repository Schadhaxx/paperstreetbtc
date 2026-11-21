#!/usr/bin/env python3
"""Tests for tools/ta_ma200.py (skunkworks 200-week moving average).

Pure Python, no network, no browser. Asserts the job reproduces the
mockup's verified numbers exactly, and that the shipped fixture
matches a fresh compute on every key.

usage: python3 tests/test_ta_ma200.py   exit 0 = all pass
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'tools'))
import ta_ma200 as TM

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAILY = os.path.join(R, 'assets', 'data', 'btc-daily.json')
FIXTURE = os.path.join(R, 'assets', 'data', 'ta-ma200.json')

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


daily, _src = TM.load_daily(DAILY)
weeks = TM.build_weeks(daily)
ma_weeks = TM.compute_ma(weeks)
last = ma_weeks[-1]          # in-progress week of 16 Nov 2026
prev = ma_weeks[-2]          # last completed week of 9 Nov 2026
below = [w for w in ma_weeks if w['close'] < w['ma']]
longest = TM.longest_below_run(ma_weeks)

chk('650 MA weeks 2014-06-09..2026-11-16',
    len(ma_weeks) == 650 and ma_weeks[0]['monday'] == '2014-06-09'
    and ma_weeks[-1]['monday'] == '2026-11-16',
    (len(ma_weeks), ma_weeks[0]['monday'], ma_weeks[-1]['monday']))
chk('first MA week 9 Jun 2014 $125.51',
    round(ma_weeks[0]['ma'], 2) == 125.51, ma_weeks[0]['ma'])
chk('MA now $68,169.58 (in-progress week)',
    round(last['ma'], 2) == 68169.58, last['ma'])
chk('MA last completed week $67,973.67',
    round(prev['ma'], 2) == 67973.67, prev['ma'])
chk('last close $61,901.82 / prev close $65,305.06',
    round(last['close'], 2) == 61901.82
    and round(prev['close'], 2) == 65305.06,
    (last['close'], prev['close']))
chk('price vs MA -9.19% now / -3.93% last completed week',
    round((last['close'] / last['ma'] - 1) * 100, 2) == -9.19
    and round((prev['close'] / prev['ma'] - 1) * 100, 2) == -3.93)
chk('MA a year ago $55,569.11 (week of 17 Nov 2025)',
    round(ma_weeks[-53]['ma'], 2) == 55569.11, ma_weeks[-53]['ma'])
chk('MA slope +$238.55/week (mockup: about +$239/wk)',
    round((prev['ma'] - ma_weeks[-53]['ma']) / 52, 2) == 238.55,
    (prev['ma'] - ma_weeks[-53]['ma']) / 52)
chk('57 of 650 weeks closed below the MA',
    len(below) == 57, len(below))
chk('longest below run 30 weeks, 15 Aug 2022 – 6 Mar 2023',
    longest == (30, '2022-08-15', '2023-03-06'), longest)

ep = {w['monday']: w for w in ma_weeks}
chk('Dec 2018 held: low +1.22% above the MA',
    round((ep['2018-12-10']['low'] / ep['2018-12-10']['ma'] - 1) * 100, 2)
    == 1.22 and round(ep['2018-12-10']['low'], 2) == 3236.76,
    ep['2018-12-10'])
chk('Nov 2022 broke: low -34.47% below the MA',
    round((ep['2022-11-21']['low'] / ep['2022-11-21']['ma'] - 1) * 100, 2)
    == -34.47 and round(ep['2022-11-21']['low'], 2) == 15787.28,
    ep['2022-11-21'])
chk('Mar 2020 dip: close -2.54%, low -10.16%',
    round((ep['2020-03-09']['close'] / ep['2020-03-09']['ma'] - 1) * 100, 2)
    == -2.54
    and round((ep['2020-03-09']['low'] / ep['2020-03-09']['ma'] - 1) * 100, 2)
    == -10.16, ep['2020-03-09'])
chk('Aug 2015 shallow: close -0.92%',
    round((ep['2015-08-17']['close'] / ep['2015-08-17']['ma'] - 1) * 100, 2)
    == -0.92, ep['2015-08-17'])
chk('Summer 2026 brushes +1.05% / +1.22% / +0.34% above the MA',
    round((ep['2026-06-15']['low'] / ep['2026-06-15']['ma'] - 1) * 100, 2)
    == 1.05
    and round((ep['2026-07-20']['low'] / ep['2026-07-20']['ma'] - 1) * 100, 2)
    == 1.22
    and round((ep['2026-08-17']['low'] / ep['2026-08-17']['ma'] - 1) * 100, 2)
    == 0.34)

# The shipped fixture matches a fresh compute on every mockup key.
fix = json.load(open(FIXTURE))
chk('fixture matches fresh compute on every mockup key',
    fix.get('maNow') == 68169.58
    and fix.get('maPrev') == 67973.67
    and fix.get('lastClose') == 61901.82
    and fix.get('prevClose') == 65305.06
    and fix.get('priceVsMaNowPct') == -9.19
    and fix.get('priceVsMaPrevPct') == -3.93
    and fix.get('maYearAgo') == 55569.11
    and fix.get('maSlopePerWeek') == 238.55
    and fix.get('weeksBelow') == 57
    and fix.get('weeksTotal') == 650
    and fix.get('longestBelowWeeks') == 30
    and fix.get('longestBelow') == {'start': '2022-08-15',
                                    'end': '2023-03-06'}
    and fix.get('lastWeek', {}).get('monday') == '2026-11-16'
    and fix.get('lastWeek', {}).get('inProgress') is True
    and fix.get('prevWeek', {}).get('monday') == '2026-11-09'
    and len(fix.get('weeks', [])) == 650
    and fix['weeks'][0] == ['2014-06-09', 572.28, 572.28, 125.51]
    and fix['weeks'][-1] == ['2026-11-16', 61901.82, 61901.82, 68169.58]
    and all(fix['weeks'][i][3] == round(ma_weeks[i]['ma'], 2)
            for i in range(len(ma_weeks))), '')
chk('fixture asOf 2026-11-19', fix.get('asOf') == '2026-11-19',
    fix.get('asOf'))
chk('fixture episodes carry the verified numbers',
    {e['monday']: e for e in fix.get('episodes', [])}['2018-12-10']
    ['lowVsMaPct'] == 1.22
    and {e['monday']: e for e in fix.get('episodes', [])}['2022-11-21']
    ['lowVsMaPct'] == -34.47)

print('TA MA200 TESTS', n, 'FAIL', f)
sys.exit(1 if f else 0)
