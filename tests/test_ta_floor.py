#!/usr/bin/env python3
"""Tests for tools/ta_floor.py (skunkworks long-term price floor).

Pure Python, no network, no browser. Asserts the job reproduces the
mockup's verified numbers exactly, and that the break rule behaves per
the Grok Bot test pack (tests/floor-testpack/SPEC.md): ONLY a completed
weekly close 2% or more under the floor breaks it. The in-progress week
never breaks it, even when it is already >2% under.

usage: python3 tests/test_ta_floor.py   exit 0 = all pass
"""
import copy
import json
import os
import sys
from datetime import date

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
out = TF.compute_floor(dates, closes, lows, last_date)

chk('262 weeks 2021-11-22..2026-11-23',
    len(closes) == 262 and str(dates[0]) == '2021-11-22'
    and str(dates[-1]) == '2026-11-23', (len(closes), dates[0], dates[-1]))
chk('last daily close 2026-11-26', str(last_date) == '2026-11-26', last_date)
chk('anchor 21 Nov 2022 $15,787.28',
    out['anchor'] == {'i': 52, 'date': '2022-11-21', 'low': 15787.28},
    out['anchor'])
chk('binding low 11 Sep 2023 $25,162.65',
    out['binding'] == {'i': 94, 'date': '2023-09-11', 'low': 25162.65},
    out['binding'])
chk('slope +$223.22/week', abs(out['slopePerWeek'] - 223.2231) < 0.001,
    out['slopePerWeek'])
chk('floor now $62,440.91', out['floorNow'] == 62440.91, out['floorNow'])
chk('floor +52w $74,048.51', out['floorPlus52'] == 74048.51,
    out['floorPlus52'])
chk('price 3.1% below the floor (in-progress week)', out['pctAbove'] == -3.1,
    out['pctAbove'])
chk('touches Sep 2023 + Jun 2026',
    [t['date'] for t in out['touches']] == ['2023-09-11', '2026-06-29'],
    out['touches'])
chk('last close $60,495.57', out['lastClose'] == 60495.57, out['lastClose'])
# The headline rule: the 23 Nov week is IN PROGRESS (Thu close -3.12%),
# so it must NOT break the floor. Last completed week 16 Nov closed
# $61,161.91 vs floor $62,217.68 (-1.7%), inside the band.
chk('NOT broken on the 26 Nov snapshot (in-progress week must not break)',
    out['broken'] is False, out['broken'])
chk('last completed week 2026-11-16',
    out['lastCompletedWeek'] == '2026-11-16', out['lastCompletedWeek'])
chk('last completed Sunday 2026-11-22',
    out['lastCompletedSunday'] == '2026-11-22', out['lastCompletedSunday'])
chk('last completed close $61,161.91',
    out['lastCompletedClose'] == 61161.91, out['lastCompletedClose'])
chk('floor at last completed week $62,217.68',
    out['floorAtLastCompleted'] == 62217.68, out['floorAtLastCompleted'])
chk('pct at last completed week -1.7%',
    out['pctAtLastCompleted'] == -1.7, out['pctAtLastCompleted'])
chk('in-progress week 2026-11-23',
    out['inProgressWeek'] == '2026-11-23', out['inProgressWeek'])
chk('in-progress close $60,495.57',
    out['inProgressClose'] == 60495.57, out['inProgressClose'])
chk('in-progress pct -3.1%', out['inProgressPct'] == -3.1, out['inProgressPct'])
chk('break trigger $60,973.33 (floor at last completed week x 0.98)',
    out['breakTrigger'] == 60973.33, out['breakTrigger'])
chk('max undershoot -1.7% (completed weeks only; Dec 2022 brushed -1.65%)',
    out['maxUnderPct'] == -1.7, out['maxUnderPct'])
chk('break rule text',
    out['breakRule'] == TF.BREAK_RULE, out['breakRule'])

# The shipped fixture matches a fresh compute exactly (same maths, same file).
fix = json.load(open(FIXTURE))
chk('fixture matches fresh compute on every mockup key',
    all(fix.get(k) == v for k, v in out.items()), '')
chk('fixture v 1 (ta-lines-refresh validation)', fix.get('v') == 1,
    fix.get('v'))
chk('fixture asOf 2026-11-22 (Sunday of the last completed week)',
    fix.get('asOf') == '2026-11-22', fix.get('asOf'))
chk('fixture dataThrough 2026-11-26 (last daily close)',
    fix.get('dataThrough') == '2026-11-26', fix.get('dataThrough'))
chk('fixture broken false', fix.get('broken') is False, fix.get('broken'))

# evaluate_break / floor_broken / display_copy on the shipped fixture.
ev = TF.evaluate_break(fix)
chk('evaluate_break(fixture): broken false', ev['broken'] is False, ev)
chk('evaluate_break(fixture): lastCompletedWeek 2026-11-16',
    ev['lastCompletedWeek'] == '2026-11-16', ev)
chk('evaluate_break(fixture): inProgressWouldBreakIfCompleted true',
    ev['inProgressWouldBreakIfCompleted'] is True, ev)
chk('evaluate_break(fixture): dashInProgress true',
    ev['dashInProgress'] is True, ev)
chk('evaluate_break(fixture): lineIsRed false', ev['lineIsRed'] is False, ev)
chk('floor_broken(fixture) false', TF.floor_broken(fix) is False)
chk('stale broken=true flag is ignored',
    TF.floor_broken({**fix, 'broken': True}) is False)
chk('display_copy(fixture): label', TF.display_copy(fix)['label'] == TF.LABEL)
chk('display_copy(fixture): asOf 2026-11-22',
    TF.display_copy(fix)['asOf'] == '2026-11-22', TF.display_copy(fix))
chk('display_copy(fixture): source passes through',
    TF.display_copy(fix)['source'] == fix['source'])
chk('display_copy(fixture): breakRule',
    TF.display_copy(fix)['breakRule'] == TF.BREAK_RULE)
chk('display_copy(fixture): brokenNote null',
    TF.display_copy(fix)['brokenNote'] is None)

# Week helpers: Monday-start UTC, date-only vs datetime asOf.
chk('week_monday of Thu 26 Nov is Mon 23 Nov',
    TF.week_monday('2026-11-26') == date(2026, 11, 23), TF.week_monday('2026-11-26'))
chk('week_monday of Sun 22 Nov 23:59 UTC is Mon 16 Nov',
    TF.week_monday('2026-11-22T23:59:59Z') == date(2026, 11, 16),
    TF.week_monday('2026-11-22T23:59:59Z'))
chk('week_monday of Mon 23 Nov 00:00 UTC is Mon 23 Nov',
    TF.week_monday('2026-11-23T00:00:00Z') == date(2026, 11, 23),
    TF.week_monday('2026-11-23T00:00:00Z'))
chk('date-only Sunday: week complete',
    TF.is_week_complete('2026-11-16', '2026-11-22') is True)
chk('date-only Saturday: week in progress',
    TF.is_week_complete('2026-11-16', '2026-11-21') is False)
chk('datetime Sunday 23:59 UTC: week still in progress',
    TF.is_week_complete('2026-11-16', '2026-11-22T23:59:59Z') is False)
chk('datetime Monday 00:00 UTC: week complete',
    TF.is_week_complete('2026-11-16', '2026-11-23T00:00:00Z') is True)
chk('floor_at anchor $15,787.28',
    TF.floor_at('2022-11-21', 15787.28, 223.2231, '2022-11-21') == 15787.28)
chk('floor_at before the anchor is None',
    TF.floor_at('2022-11-21', 15787.28, 223.2231, '2021-11-15') is None)

# Synthetic break cases (flat $10,000 floor).
def synth(weeks, as_of):
    return {'anchor': {'date': '2026-01-05', 'low': 10000},
            'slopePerWeek': 0.0, 'asOf': as_of, 'source': 'synthetic',
            'weeks': weeks}

wks = [['2026-01-05', 11000], ['2026-01-12', 10500], ['2026-01-19', 9700]]
chk('completed week 3% under: broken',
    TF.floor_broken(synth(wks, '2026-01-25'), '2026-01-25') is True)
chk('completed week 3% under: brokenNote set',
    TF.display_copy(synth(wks, '2026-01-25'), '2026-01-25')['brokenNote'] == TF.BROKEN_NOTE)
chk('same 3% dip, week in progress (Thu): NOT broken',
    TF.floor_broken(synth(wks, '2026-01-22'), '2026-01-22') is False)
chk('in-progress dip: inProgressWouldBreakIfCompleted true',
    TF.evaluate_break(synth(wks, '2026-01-22'), '2026-01-22')['inProgressWouldBreakIfCompleted'] is True)
chk('exactly -2.0% completed: breaks',
    TF.floor_broken(synth([['2026-01-05', 11000], ['2026-01-19', 9800]], '2026-01-25'), '2026-01-25') is True)
chk('9800.01 completed (just inside): does not break',
    TF.floor_broken(synth([['2026-01-05', 11000], ['2026-01-19', 9800.01]], '2026-01-25'), '2026-01-25') is False)
chk('exactly -2.0% in progress: does not break',
    TF.floor_broken(synth([['2026-01-05', 11000], ['2026-01-19', 9800]], '2026-01-22'), '2026-01-22') is False)
chk('null / bad input fails closed',
    TF.floor_broken(None) is False and TF.floor_broken({}) is False
    and TF.floor_at_payload(None, '2026-11-23') is None)

# Break rule, exercised by mutating weekly closes on the real data.
# Mutating the LAST (in-progress) week 3% under must NOT break it.
c2 = list(closes)
c2[-1] = out['floorNow'] * 0.97   # 3% under the floor, week in progress
chk('last (in-progress) close 3% under: NOT broken',
    TF.compute_floor(dates, c2, lows, last_date)['broken'] is False)
c3 = list(closes)
c3[-1] = out['floorNow'] * 0.99   # 1% under: inside tolerance
chk('last close 1% under: not broken',
    TF.compute_floor(dates, c3, lows, last_date)['broken'] is False)
# Mutating the last COMPLETED week 3% under DOES break it.
c5 = list(closes)
c5[-2] = out['floorAtLastCompleted'] * 0.97
chk('last completed close 3% under: broken',
    TF.compute_floor(dates, c5, lows, last_date)['broken'] is True)
# A mid-series completed close 3% under also breaks it.
c4 = list(closes)
i_dec22 = dates.index(date(2022, 12, 26))
fl_dec22 = out['anchor']['low'] + out['slopePerWeek'] * (i_dec22 - 52)
c4[i_dec22] = fl_dec22 * 0.97
chk('Dec 2022 close 3% under: broken',
    TF.compute_floor(dates, c4, lows, last_date)['broken'] is True)

print('TA FLOOR TESTS', n, 'FAIL', f)
sys.exit(1 if f else 0)
