#!/usr/bin/env python3
"""Tests for tools/ta_lines_desk.py (skunkworks TA 2.0, Desk trendlines).

Pure Python, no network, no browser. Gold is the regression check: the
job MUST reproduce the site-file run exactly (ATR $227.45, last close
$3,644.60, levels $3,152.03 / $3,506.77 / $5,510.15, sloped supports
+$15.14/+$15.39 per week, 11 touches each). The committed fixture
must match a fresh compute, and every one of the 24 Desk symbols must
be present with well-formed levels/sloped lists.

The fixture is computed on the full backfilled series (264 weeks for
21 symbols, IBIT 150, SPCX 24). The original 47-week run gave
ATR $232.76, levels $5,510.15 / $4,836.35 / $4,027.70 and one sloped
resistance -$27.71/wk; those numbers are history, not a regression.

usage: python3 tests/test_ta_lines_desk.py   exit 0 = all pass
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'tools'))
import ta_lines_desk as TLD

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLD_FILE = os.path.join(R, 'assets', 'data', 'gold-weekly.json')
FIXTURE = os.path.join(R, 'assets', 'data', 'ta-lines-desk.json')

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


with open(GOLD_FILE) as fh:
    gold_weeks = json.load(fh)['weeks']
chk('gold: file holds 264 weeks (backfilled)', len(gold_weeks) == 264, len(gold_weeks))
rec = TLD.compute(gold_weeks)

chk('gold: 264 weeks', rec['weeks'] == 264, rec['weeks'])
chk('gold: ATR 227.45', rec['atr'] == 227.45, rec['atr'])
chk('gold: last close 3644.6', rec['lastClose'] == 3644.6, rec['lastClose'])
chk('gold: 3 levels',
    [lv['price'] for lv in rec['levels']] == [3152.03, 3506.77, 5510.15],
    rec['levels'])
chk('gold: levels support/support/resistance',
    [lv['type'] for lv in rec['levels']] == ['support', 'support', 'resistance'],
    rec['levels'])
chk('gold: levels 4/3/2 touches',
    [lv['touches'] for lv in rec['levels']] == [4, 3, 2], rec['levels'])
chk('gold: 2 sloped lines', len(rec['sloped']) == 2, rec['sloped'])
sl = rec['sloped'][0]
chk('gold: sloped[0] support +15.14/wk, 11 touches, anchor [135, 2304.2], end 4242.24',
    sl['type'] == 'support' and sl['slope'] == 15.14 and sl['touches'] == 11
    and sl['anchor'] == [135, 2304.2] and sl['endPrice'] == 4242.24, sl)
sl2 = rec['sloped'][1]
chk('gold: sloped[1] support +15.39/wk, 11 touches, anchor [179, 2970.4], end 4263.21',
    sl2['type'] == 'support' and sl2['slope'] == 15.39 and sl2['touches'] == 11
    and sl2['anchor'] == [179, 2970.4] and sl2['endPrice'] == 4263.21, sl2)

with open(FIXTURE) as fh:
    fix = json.load(fh)

chk('fixture: 24 symbols', len(fix) == 24, len(fix))
chk('fixture: all expected symbols present',
    set(fix) == {s for s, _, _ in TLD.SYMBOLS}, sorted(set(fix)))
chk('fixture: GOLD matches a fresh compute',
    fix['GOLD']['atr'] == rec['atr']
    and fix['GOLD']['lastClose'] == rec['lastClose']
    and fix['GOLD']['weeks'] == rec['weeks']
    and fix['GOLD']['levels'] == rec['levels']
    and fix['GOLD']['sloped'] == rec['sloped'],
    fix['GOLD'])
ok_shape = True
for sym, entry in fix.items():
    if not (isinstance(entry.get('levels'), list) and len(entry['levels']) <= 3):
        ok_shape = False
    if not (isinstance(entry.get('sloped'), list) and len(entry['sloped']) <= 2):
        ok_shape = False
    for lv in entry.get('levels', []):
        if not (isinstance(lv.get('price'), (int, float))
                and math.isfinite(lv['price'])
                and lv.get('type') in ('support', 'resistance')):
            ok_shape = False
    for ln in entry.get('sloped', []):
        if not (isinstance(ln.get('slope'), (int, float))
                and isinstance(ln.get('anchor'), list) and len(ln['anchor']) == 2
                and ln.get('touches', 0) >= 3):
            ok_shape = False
chk('fixture: every symbol has <=3 levels, <=2 sloped, well-formed entries', ok_shape)
with_levels = sum(1 for e in fix.values() if e.get('levels'))
chk('fixture: 23+ of 24 symbols got levels', with_levels >= 23, with_levels)

print(f'{n - f}/{n} checks passed')
sys.exit(1 if f else 0)
