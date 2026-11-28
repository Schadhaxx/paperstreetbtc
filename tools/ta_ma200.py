#!/usr/bin/env python3
"""200-week moving average for the BTC 5Y/10Y line charts.

Skunkworks prototype (test branch only, Nov 2026): a SEPARATE long-term
pass, distinct from the Stage 3a short-term levels in tools/ta_lines.py
(which is per-timeframe pivots/levels; this is one slow trend line over
the full history) and from the floor in tools/ta_floor.py (which is a
rising support line from the bear-market bottom; this is anchor-free --
it just follows price).

- weekly closes from the daily file (Monday-start weeks; close = last
  daily close of the week; low = lowest daily close in the week -- the
  daily file holds closes only, so the weekly low is the lowest close,
  not an intraday low)
- 200-week MA = mean of the last 200 weekly closes, including the
  current week. First MA value: week of 9 Jun 2014, $125.51.
- updated once a week, at the weekly close. Judged on weekly closes,
  like the floor's break rule.

Output: assets/data/ta-ma200.json (a local fixture for now -- there is
NO workflow file yet; the front end reads the fixture directly).

Source: the site's own assets/data/btc-daily.json (Yahoo BTC-USD daily
closes from Sep 2014; blockchain.info market-price daily average
before that). Same maths as the mockup script ma200.py; the verified
numbers are asserted in tests/test_ta_ma200.py.

usage: python3 tools/ta_ma200.py [--src PATH] [--out PATH]
"""
import argparse
import json
import os
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SRC = os.path.join(ROOT, 'assets', 'data', 'btc-daily.json')
DEFAULT_OUT = os.path.join(ROOT, 'assets', 'data', 'ta-ma200.json')

N = 200  # weeks in the moving average


def load_daily(src):
    with open(src) as f:
        d = json.load(f)
    daily = [(date.fromisoformat(r[0]), float(r[1])) for r in d['d']]
    return daily, d.get('source')


def build_weeks(daily):
    """Monday-start weeks: close = last close of the week, low = lowest
    daily close in the week. Returns a list of dicts sorted by Monday."""
    weeks = {}
    for dt, px in daily:
        mon = dt - timedelta(days=dt.weekday())
        w = weeks.setdefault(mon, {'dates': [], 'closes': []})
        w['dates'].append(dt)
        w['closes'].append(px)
    out = []
    for mon in sorted(weeks):
        w = weeks[mon]
        out.append({'monday': mon.isoformat(),
                    'close': w['closes'][-1],
                    'low': min(w['closes']),
                    'days': len(w['closes'])})
    return out


def compute_ma(weeks):
    """200-week MA on weekly closes. Returns a list of dicts
    {monday, close, low, ma, days} for every week with a full 200-week
    window (first MA week: 9 Jun 2014)."""
    out = []
    for i, w in enumerate(weeks):
        if i >= N - 1:
            vals = [x['close'] for x in weeks[i - N + 1:i + 1]]
            out.append({'monday': w['monday'],
                        'close': w['close'],
                        'low': w['low'],
                        'days': w['days'],
                        'ma': sum(vals) / N})
    return out


def longest_below_run(ma_weeks):
    """Longest run of consecutive weekly closes below the MA.
    Returns (count, start_monday, end_monday)."""
    best = (0, None, None)
    run = 0
    start = None
    for w in ma_weeks:
        if w['close'] < w['ma']:
            if run == 0:
                start = w['monday']
            run += 1
            if run > best[0]:
                best = (run, start, w['monday'])
        else:
            run = 0
            start = None
    return best


def episode(ma_weeks, monday):
    """The MA row for a given Monday, or None."""
    for w in ma_weeks:
        if w['monday'] == monday:
            return w
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=DEFAULT_SRC)
    ap.add_argument('--out', default=DEFAULT_OUT)
    a = ap.parse_args()

    daily, source = load_daily(a.src)
    weeks = build_weeks(daily)
    ma_weeks = compute_ma(weeks)

    last = ma_weeks[-1]          # in-progress week of 16 Nov 2026
    prev = ma_weeks[-2]          # last completed week of 9 Nov 2026
    year_ago = ma_weeks[-53] if len(ma_weeks) > 53 else None
    below = [w for w in ma_weeks if w['close'] < w['ma']]
    longest = longest_below_run(ma_weeks)

    # The five verified touches-and-breaks episodes (see the mockup
    # report): each is recomputed here from the same series, so a data
    # change would move the numbers rather than silently keeping them.
    ep_defs = [
        ('2018-12-10', 'held', 'Dec 2018 bottomed essentially ON the MA'),
        ('2022-11-21', 'broke', 'Nov 2022 broke the MA and stayed under'),
        ('2020-03-09', 'dip', 'Mar 2020 COVID one-week dip'),
        ('2015-08-17', 'shallow', 'Aug-Sep 2015 shallow, 5 weeks below'),
        ('2026-06-15', 'brush', 'Summer 2026 brush 1 of 3, then the break'),
        ('2026-07-20', 'brush', 'Summer 2026 brush 2 of 3'),
        ('2026-08-17', 'brush', 'Summer 2026 brush 3 of 3'),
    ]
    episodes = []
    for monday, kind, note in ep_defs:
        w = episode(ma_weeks, monday)
        if w is None:
            continue
        episodes.append({'monday': monday, 'kind': kind, 'note': note,
                         'close': round(w['close'], 2),
                         'low': round(w['low'], 2),
                         'ma': round(w['ma'], 2),
                         'lowVsMaPct': round((w['low'] / w['ma'] - 1) * 100, 2),
                         'closeVsMaPct': round((w['close'] / w['ma'] - 1) * 100, 2)})

    out = {
        'v': 1,
        'source': source,
        'asOf': daily[-1][0].isoformat(),
        'dataThrough': daily[-1][0].isoformat(),
        'maNow': round(last['ma'], 2),
        'maPrev': round(prev['ma'], 2),
        'lastClose': round(last['close'], 2),
        'prevClose': round(prev['close'], 2),
        'lastWeek': {'monday': last['monday'], 'close': round(last['close'], 2),
                     'ma': round(last['ma'], 2), 'days': last['days'],
                     'inProgress': True},
        'prevWeek': {'monday': prev['monday'], 'close': round(prev['close'], 2),
                     'ma': round(prev['ma'], 2), 'days': prev['days'],
                     'inProgress': False},
        'priceVsMaNowPct': round((last['close'] / last['ma'] - 1) * 100, 2),
        'priceVsMaPrevPct': round((prev['close'] / prev['ma'] - 1) * 100, 2),
        'maYearAgo': round(year_ago['ma'], 2) if year_ago else None,
        # Slope: last COMPLETED week vs the MA 52 weeks earlier (the
        # mockup's convention — the in-progress week's MA would give
        # $242/wk; the completed-week slope is $238.55/wk ≈ +$239/wk).
        'maSlopePerWeek': round((prev['ma'] - ma_weeks[-53]['ma']) / 52, 2),
        'weeksBelow': len(below),
        'weeksTotal': len(ma_weeks),
        'longestBelowWeeks': longest[0],
        'longestBelow': {'start': longest[1], 'end': longest[2]},
        'episodes': episodes,
        # [monday, close, low, ma] for every week with a full window.
        'weeks': [[w['monday'], round(w['close'], 2), round(w['low'], 2),
                   round(w['ma'], 2)] for w in ma_weeks],
    }

    with open(a.out, 'w') as f:
        json.dump(out, f, indent=1)
        f.write('\n')
    print('wrote %s (%d MA weeks, %s..%s)' %
          (a.out, len(ma_weeks), ma_weeks[0]['monday'], ma_weeks[-1]['monday']))
    print('MA now $%.2f  price vs MA %+.2f%%  (prev week $%.2f, %+.2f%%)' %
          (last['ma'], (last['close'] / last['ma'] - 1) * 100,
           prev['ma'], (prev['close'] / prev['ma'] - 1) * 100))
    print('weeks below MA: %d of %d; longest run %d (%s..%s)' %
          (len(below), len(ma_weeks), longest[0], longest[1], longest[2]))


if __name__ == '__main__':
    main()
