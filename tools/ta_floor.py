#!/usr/bin/env python3
"""Long-term price floor trendline for the BTC 5Y/10Y line charts.

Skunkworks prototype (test branch only, Nov 2026): a SEPARATE long-term
pass, distinct from the Stage 3a short-term levels in tools/ta_lines.py
(which is per-timeframe pivots/levels; this is one rising floor from the
bear-market bottom over a 5-year window).

- weekly candles from the daily file (close = last close of the Mon-Sun
  UTC week; low = lowest daily close in the week -- the daily file holds
  closes only, so the weekly low is the lowest close, not an intraday low)
- swing lows: fractal k=5 on weekly lows
- anchor: the lowest swing low in the window (the bear-market bottom)
- floor: the steepest rising line from the anchor that no later swing
  low undercuts (lower envelope); its slope is set by whichever later
  low binds tightest
- touches: swing lows resting within 5% above the line
- the line is extended 52 weeks past the data as a projection

Break rule: a weekly CLOSE 2% or more under the floor breaks it. The
trigger for the current week is floorNow * 0.98. Two closes in
Dec 2022 / Jan 2023 finished slightly under the line (max -1.65%) and
recovered -- inside the 2% tolerance. The 23 Nov 2026 weekly close
($60,495.57) finished 3.12% under the line, past the tolerance, so
as of 26 Nov 2026 the floor is BROKEN.

Output: assets/data/ta-floor.json (a local fixture for now -- there is
NO workflow file yet; the front end reads the fixture directly).

Source: the site's own assets/data/btc-daily.json (Yahoo BTC-USD daily
closes). Same maths as the mockup script floor_lines_btc.py; the
verified numbers are asserted in tests/test_ta_floor.py.

usage: python3 tools/ta_floor.py [--src PATH] [--out PATH]
"""
import argparse
import json
import os
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SRC = os.path.join(ROOT, 'assets', 'data', 'btc-daily.json')
DEFAULT_OUT = os.path.join(ROOT, 'assets', 'data', 'ta-floor.json')

K = 5               # fractal window for swing lows (weeks each side)
WINDOW_DAYS = 5 * 365 + 1   # 5-year window
TOUCH_TOL = 1.05    # swing low within 5% above the line counts as a touch
BREAK_TOL = 0.98    # weekly close at or under floor * 0.98 breaks the floor
PROJ_WEEKS = 52     # projection length past the data


def load_daily(src):
    with open(src) as f:
        d = json.load(f)
    daily = [(date.fromisoformat(r[0]), float(r[1])) for r in d['d']]
    return daily, d.get('source')


def build_weeks(daily):
    """Mon-Sun UTC weeks: close = last close of the week, low = lowest
    daily close in the week. Returns (mondays, closes, lows) sorted."""
    last_date = daily[-1][0]
    start_date = last_date - timedelta(days=WINDOW_DAYS)
    weeks = {}
    for dt, px in daily:
        mon = dt - timedelta(days=dt.weekday())
        w = weeks.setdefault(mon, {'close': px, 'low': px})
        w['close'] = px
        w['low'] = min(w['low'], px)
    wk = sorted((m, v) for m, v in weeks.items()
                if m + timedelta(days=6) >= start_date)
    dates = [m for m, _ in wk]
    closes = [v['close'] for _, v in wk]
    lows = [v['low'] for _, v in wk]
    return dates, closes, lows, last_date


def compute_floor(dates, closes, lows):
    """The floor maths. Returns the output dict (without asOf/source)."""
    n = len(closes)
    swing_lows = [(i, lows[i]) for i in range(K, n - K)
                  if lows[i] == min(lows[i - K:i + K + 1])]
    ai, ap = min(swing_lows, key=lambda t: t[1])
    post = [(i, p) for i, p in swing_lows if i > ai]

    slope = min((p - ap) / (i - ai) for i, p in post)
    bind = min(post, key=lambda t: (t[1] - ap) / (t[0] - ai))

    def floor(i):
        return ap + slope * (i - ai)

    touches = [{'i': i, 'date': dates[i].isoformat(), 'low': round(p, 2),
                'line': round(floor(i), 2)}
               for i, p in post if floor(i) <= p <= floor(i) * TOUCH_TOL]

    last_close = closes[-1]
    floor_now = floor(n - 1)
    # Break check over every weekly close against the final line.
    under = [(i, (closes[i] / floor(i) - 1) * 100)
             for i in range(n) if closes[i] < floor(i)]
    max_under = min((u for _, u in under), default=0.0)
    broken = any(closes[i] <= floor(i) * BREAK_TOL for i in range(n))

    hi_i = max(range(n), key=lambda i: closes[i])
    return {
        'anchor': {'i': ai, 'date': dates[ai].isoformat(),
                   'low': round(ap, 2)},
        'binding': {'i': bind[0], 'date': dates[bind[0]].isoformat(),
                    'low': round(bind[1], 2)},
        'slopePerWeek': round(slope, 4),
        'floorNow': round(floor_now, 2),
        'floorPlus52': round(floor(n + 51), 2),
        'projIdx': n + 51,
        'pctAbove': round((last_close / floor_now - 1) * 100, 1),
        'touches': touches,
        'swingLows': [{'i': i, 'date': dates[i].isoformat(),
                       'low': round(p, 2)} for i, p in swing_lows],
        'lastClose': round(last_close, 2),
        'firstClose': round(closes[0], 2),
        'chg5y': round((last_close / closes[0] - 1) * 100, 1),
        'ath': {'date': dates[hi_i].isoformat(),
                'price': round(closes[hi_i], 2)},
        'ddAth': round((last_close / closes[hi_i] - 1) * 100, 1),
        'broken': broken,
        'breakTrigger': round(floor_now * BREAK_TOL, 2),
        'breakRule': 'weekly close 2% or more under the floor',
        'maxUnderPct': round(max_under, 2),
        'weeks': [[m.isoformat(), round(c, 2)]
                  for m, c in zip(dates, closes)],
    }


def run(src=DEFAULT_SRC, out=DEFAULT_OUT):
    daily, source = load_daily(src)
    dates, closes, lows, last_date = build_weeks(daily)
    n = len(closes)
    result = compute_floor(dates, closes, lows)
    result = {'symbol': 'BTC', 'asOf': str(last_date), 'source': source,
              **result}
    with open(out, 'w') as f:
        json.dump(result, f, indent=1)
    print(f"weeks={n} {dates[0]}..{dates[-1]} "
          f"anchor {dates[result['anchor']['i']]} "
          f"${result['anchor']['low']:,.0f}")
    print(f"slope ${result['slopePerWeek']:,.2f}/wk "
          f"binds {result['binding']['date']} "
          f"${result['binding']['low']:,.0f}")
    print(f"floorNow ${result['floorNow']:,.0f} "
          f"+52w ${result['floorPlus52']:,.0f} "
          f"pctAbove {result['pctAbove']}% "
          f"touches {[(t['date'], t['low']) for t in result['touches']]}")
    print(f"last ${result['lastClose']:,.0f} "
          f"ATH {result['ath']['date']} ${result['ath']['price']:,.0f} "
          f"5y {result['chg5y']:+}% ddATH {result['ddAth']}%")
    print(f"broken={result['broken']} trigger "
          f"${result['breakTrigger']:,.0f} maxUnder "
          f"{result['maxUnderPct']}%")
    print('wrote', out)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--src', default=DEFAULT_SRC)
    ap.add_argument('--out', default=DEFAULT_OUT)
    a = ap.parse_args()
    run(a.src, a.out)


if __name__ == '__main__':
    main()
