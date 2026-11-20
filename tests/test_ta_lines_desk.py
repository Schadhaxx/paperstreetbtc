#!/usr/bin/env python3
"""Tests for tools/ta_lines_desk.py (skunkworks TA 2.0, Desk trendlines).

Pure Python, no network, no browser. Gold is the regression check: the
job MUST reproduce the site-file run exactly (ATR $232.76, last close
$3,644.60, levels $5,510.15 / $4,836.35 / $4,027.70, sloped resistance
-$27.71/wk, 3 touches off the Jan 2026 high). The committed fixture
must match a fresh compute, and every one of the 24 Desk symbols must
be present with well-formed levels/sloped lists.

The fixture was computed on the recent 47 weeks (29 Dec 2025 - 16 Nov
2026). The weekly files were backfilled to 200+ weeks in Nov 2026
(TA 2.0 test branch, tools/ta_backfill_weekly.py) and the fixture was
deliberately NOT recomputed, so the regression below runs on the last
47 weeks of the file — the same 47 the fixture came from. A fresh
compute on the full 264 weeks gives different levels (ATR $227.45,
support $3,152.03 / $3,506.77); that is the known recompute question,
not a regression.

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
chk('gold: last 47 weeks start 29 Dec 2025', gold_weeks[-47]['monday'] == '2025-12-29', gold_weeks[-47])
rec = TLD.compute(gold_weeks[-47:])

chk('gold: 47 weeks', rec['weeks'] == 47, rec['weeks'])
chk('gold: ATR 232.76', rec['atr'] == 232.76, rec['atr'])
chk('gold: last close 3644.6', rec['lastClose'] == 3644.6, rec['lastClose'])
chk('gold: 3 levels',
    [lv['price'] for lv in rec['levels']] == [5510.15, 4836.35, 4027.7],
    rec['levels'])
chk('gold: levels all resistance',
    all(lv['type'] == 'resistance' for lv in rec['levels']), rec['levels'])
chk('gold: levels 2 touches each',
    all(lv['touches'] == 2 for lv in rec['levels']), rec['levels'])
chk('gold: 1 sloped line', len(rec['sloped']) == 1, rec['sloped'])
sl = rec['sloped'][0]
chk('gold: sloped resistance -27.71/wk, 3 touches, anchor [4, 5586.2], end 4422.52',
    sl['type'] == 'resistance' and sl['slope'] == -27.71 and sl['touches'] == 3
    and sl['anchor'] == [4, 5586.2] and sl['endPrice'] == 4422.52, sl)

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
