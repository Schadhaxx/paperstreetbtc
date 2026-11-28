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

Break rule (fixed 28 Nov 2026, Grok Bot test pack): ONLY a COMPLETED
weekly close 2% or more under the floor breaks it. Weeks are Monday-start
UTC, closing Sunday UTC. A week is complete iff its Sunday daily close is
in hand -- for a date-only asOf, asOf >= that Sunday; for a datetime asOf,
asOf >= the next Monday 00:00 UTC (so Sunday 23:59 UTC is still
in-progress). The in-progress week may be drawn dashed but must never set
broken or turn the line red, even when it is already >2% under. Two closes
in Dec 2022 / Jan 2023 finished slightly under the line (max -1.65%) and
recovered -- inside the 2% tolerance. The 23 Nov 2026 week (Thu close
$60,495.57, -3.12%) is still IN PROGRESS as of 26 Nov 2026, so it does NOT
break the floor: the last completed week (16 Nov, $61,161.91 vs floor
$62,217.68, -1.7%) is inside the band, so broken=false on this snapshot.

Output: assets/data/ta-floor.json, a GENERATED artifact kept current by
.github/workflows/ta-lines-refresh.yml (daily 01:30 UTC + push on
btc-daily.json + manual dispatch; regenerates ta-floor.json and
ta-ma200.json). The fixture's asOf is the Sunday of the last completed
week (2026-11-22 on this snapshot); dataThrough is the last daily close
(2026-11-26).

Source: the site's own assets/data/btc-daily.json (Yahoo BTC-USD daily
closes). Same maths as the mockup script floor_lines_btc.py; the
verified numbers are asserted in tests/test_ta_floor.py.

usage: python3 tools/ta_floor.py [--src PATH] [--out PATH]
"""
import argparse
import json
import os
from datetime import date, datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SRC = os.path.join(ROOT, 'assets', 'data', 'btc-daily.json')
DEFAULT_OUT = os.path.join(ROOT, 'assets', 'data', 'ta-floor.json')

K = 5               # fractal window for swing lows (weeks each side)
WINDOW_DAYS = 5 * 365 + 1   # 5-year window
TOUCH_TOL = 1.05    # swing low within 5% above the line counts as a touch
BREAK_TOL = 0.98    # weekly close at or under floor * 0.98 breaks the floor
PROJ_WEEKS = 52     # projection length past the data

LABEL = 'Trend support (weekly closes)'
BREAK_RULE = ('Completed weekly close (Monday-Sunday UTC) 2% or more below '
              'the floor. An in-progress week does not count.')
BROKEN_NOTE = ('Broken: a completed weekly close finished 2% or more below '
               'this line.')


def parse_as_of(value):
    """Return ('date', date) or ('datetime', aware UTC datetime).

    A YYYY-MM-DD string or date is date-only (a daily close for that UTC
    day is available). An ISO datetime is an instant; timezone-naive
    values are treated as UTC.
    """
    if isinstance(value, datetime):
        dt = value
        return ('datetime', dt if dt.tzinfo is not None
                else dt.replace(tzinfo=timezone.utc))
    if isinstance(value, date):
        return ('date', value)
    if not isinstance(value, str):
        raise TypeError('as_of must be date, datetime, or ISO string')
    s = value.strip()
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    if 'T' in s:
        dt = datetime.fromisoformat(s)
        return ('datetime', dt if dt.tzinfo is not None
                else dt.replace(tzinfo=timezone.utc))
    return ('date', date.fromisoformat(s[:10]))


def week_monday(ts):
    """Monday (UTC) of the week containing ts. Sunday 23:59 UTC stays
    in the week that started that Monday; Monday 00:00 UTC starts the next.
    """
    kind, val = parse_as_of(ts)
    d = val.date() if kind == 'datetime' else val
    return d - timedelta(days=d.weekday())


def week_sunday(week_start):
    return week_monday(week_start) + timedelta(days=6)


def is_week_complete(week_start, as_of):
    """A Monday-start week is complete when its Sunday daily close exists.

    Date-only as_of: complete iff as_of >= that Sunday (the Sunday daily
    close is in hand).
    Datetime as_of: the week occupies [Mon 00:00 UTC, next Mon 00:00 UTC).
    It is complete iff as_of >= next Monday 00:00 UTC. So Sunday 23:59 UTC
    is still in-progress; Monday 00:00 UTC completes it.
    """
    mon = week_monday(week_start)
    sunday = mon + timedelta(days=6)
    next_mon = mon + timedelta(days=7)
    kind, val = parse_as_of(as_of)
    if kind == 'date':
        return val >= sunday
    threshold = datetime(next_mon.year, next_mon.month, next_mon.day,
                         tzinfo=timezone.utc)
    return val >= threshold


def floor_at(anchor_date, anchor_low, slope_per_week, ds):
    """Floor value on the Monday of the week containing ds. None before the anchor."""
    if anchor_date is None or anchor_low is None or slope_per_week is None or ds is None:
        return None
    a = week_monday(anchor_date)
    d = week_monday(ds)
    w = (d - a).days // 7
    if w < 0:
        return None
    return anchor_low + slope_per_week * w


def floor_at_payload(j, ds):
    """Same as the panel floorAt(j, ds): uses j.anchor and j.slopePerWeek."""
    if not j or not j.get('anchor') or not isinstance(j.get('slopePerWeek'), (int, float)):
        return None
    try:
        return floor_at(j['anchor']['date'], j['anchor']['low'], j['slopePerWeek'], ds)
    except (KeyError, TypeError, ValueError):
        return None


def _week_breaks(close, floor):
    if close is None or floor is None or floor == 0:
        return False
    return close <= floor * BREAK_TOL


def evaluate_break(j, as_of=None):
    """Classify completed vs in-progress weeks and apply the break rule.

    j must have anchor, slopePerWeek, and weeks: [[monday_iso, close], ...].
    as_of defaults to j['asOf'].
    """
    if not j:
        return {
            'broken': False, 'lastCompletedWeek': None, 'lastCompletedSunday': None,
            'lastCompletedClose': None, 'floorAtLastCompleted': None,
            'pctAtLastCompleted': None, 'inProgressWeek': None,
            'inProgressClose': None, 'inProgressPct': None,
            'inProgressTriggersBreak': False, 'maxUnderPct': 0.0,
            'floorNow': None, 'breakTrigger': None, 'asOfInput': None,
        }
    as_of = as_of if as_of is not None else j.get('asOf')
    if as_of is None:
        raise ValueError('as_of or j.asOf is required')
    weeks = j.get('weeks') or []
    completed = []
    in_prog = None
    floor_now = None
    for item in weeks:
        mon_s, close = item[0], float(item[1])
        mon = week_monday(mon_s)
        fl = floor_at_payload(j, mon)
        if fl is not None:
            floor_now = fl
        pct = ((close / fl - 1) * 100) if fl else None
        rec = {
            'monday': mon.isoformat(),
            'sunday': (mon + timedelta(days=6)).isoformat(),
            'close': close,
            'floor': None if fl is None else fl,
            'pct': pct,
            'complete': is_week_complete(mon, as_of),
        }
        rec['weekBreaks'] = bool(rec['complete'] and _week_breaks(close, fl))
        if rec['complete']:
            completed.append(rec)
        else:
            in_prog = rec  # last incomplete week wins (should be the latest)
    last = completed[-1] if completed else None
    unders = [r['pct'] for r in completed if r['pct'] is not None and r['pct'] < 0]
    in_pct = in_prog['pct'] if in_prog else None
    # In-progress may sit >2% under; that must not flip broken or the red line.
    in_would = bool(in_prog and _week_breaks(in_prog['close'], in_prog['floor']))
    out = {
        'broken': any(r['weekBreaks'] for r in completed),
        'lastCompletedWeek': last['monday'] if last else None,
        'lastCompletedSunday': last['sunday'] if last else None,
        'lastCompletedClose': last['close'] if last else None,
        'floorAtLastCompleted': None if not last or last['floor'] is None else round(last['floor'], 2),
        'pctAtLastCompleted': None if not last or last['pct'] is None else round(last['pct'], 1),
        'inProgressWeek': in_prog['monday'] if in_prog else None,
        'inProgressClose': in_prog['close'] if in_prog else None,
        'inProgressPct': None if in_pct is None else round(in_pct, 1),
        'inProgressTriggersBreak': False,
        'inProgressWouldBreakIfCompleted': in_would,
        'maxUnderPct': round(min(unders), 2) if unders else 0.0,
        'floorNow': None if floor_now is None else round(floor_now, 2),
        'breakTrigger': None if not last or last['floor'] is None else round(last['floor'] * BREAK_TOL, 2),
        'asOfInput': as_of if isinstance(as_of, str) else (
            as_of.isoformat() if hasattr(as_of, 'isoformat') else str(as_of)
        ),
        'dashInProgress': in_prog is not None,
        'lineIsRed': False,  # set below
    }
    out['lineIsRed'] = out['broken']
    out['inProgressTriggersBreak'] = False
    return out


def floor_broken(j, as_of=None):
    """Broken flag: completed weeks only. Ignores a stale j['broken'] flag
    when weeks are present. Bad/missing input fails closed (False).
    """
    if not j or not j.get('weeks') or not j.get('anchor'):
        return False
    try:
        return evaluate_break(j, as_of)['broken']
    except (TypeError, ValueError, KeyError):
        return False


def display_copy(j, as_of=None):
    """Caption fields the chart must show. brokenNote is None when not broken."""
    ev = evaluate_break(j, as_of) if j and j.get('weeks') else {
        'broken': False, 'lastCompletedSunday': None,
    }
    source = (j or {}).get('source')
    return {
        'label': LABEL,
        'asOf': ev.get('lastCompletedSunday'),
        'source': source,
        'breakRule': BREAK_RULE,
        'brokenNote': BROKEN_NOTE if ev.get('broken') else None,
    }


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


def compute_floor(dates, closes, lows, last_date=None):
    """The floor maths. Returns the output dict (without asOf/source).

    last_date is the last daily close in hand (a date, or an ISO string /
    datetime for the datetime rule). Only weeks complete as of last_date
    can set broken; the in-progress week never can. When last_date is
    None the last week is treated as complete (legacy callers with no
    as-of in hand).
    """
    n = len(closes)
    if last_date is None:
        last_date = dates[-1] + timedelta(days=6)
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

    # Break check over COMPLETED weekly closes only, against the line at
    # that week. The in-progress week (last_date inside it) never breaks.
    completed = [i for i in range(n) if is_week_complete(dates[i], last_date)]
    in_prog = [i for i in range(n) if not is_week_complete(dates[i], last_date)]
    last_completed = completed[-1] if completed else None
    in_prog_i = in_prog[-1] if in_prog else None
    broken = any(closes[i] <= floor(i) * BREAK_TOL for i in completed)
    under = [(closes[i] / floor(i) - 1) * 100
             for i in completed if closes[i] < floor(i)]
    max_under = min(under, default=0.0)

    last_close = closes[-1]
    floor_now = floor(n - 1)
    hi_i = max(range(n), key=lambda i: closes[i])
    return {
        'v': 1,
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
        # Trigger at the last COMPLETED week (the evaluate_break
        # definition): the close that would break the floor once a week
        # completes. The in-progress week's own trigger is floorNow*0.98.
        'breakTrigger': (round(floor(last_completed) * BREAK_TOL, 2)
                         if last_completed is not None else None),
        'breakRule': BREAK_RULE,
        'maxUnderPct': round(max_under, 2),
        'lastCompletedWeek': (dates[last_completed].isoformat()
                              if last_completed is not None else None),
        'lastCompletedSunday': ((dates[last_completed] + timedelta(days=6)).isoformat()
                                if last_completed is not None else None),
        'lastCompletedClose': (round(closes[last_completed], 2)
                               if last_completed is not None else None),
        'floorAtLastCompleted': (round(floor(last_completed), 2)
                                 if last_completed is not None else None),
        'pctAtLastCompleted': (round((closes[last_completed] / floor(last_completed) - 1) * 100, 1)
                               if last_completed is not None else None),
        'inProgressWeek': (dates[in_prog_i].isoformat()
                           if in_prog_i is not None else None),
        'inProgressClose': (round(closes[in_prog_i], 2)
                            if in_prog_i is not None else None),
        'inProgressPct': (round((closes[in_prog_i] / floor(in_prog_i) - 1) * 100, 1)
                          if in_prog_i is not None else None),
        'weeks': [[m.isoformat(), round(c, 2)]
                  for m, c in zip(dates, closes)],
    }


def run(src=DEFAULT_SRC, out=DEFAULT_OUT):
    daily, source = load_daily(src)
    dates, closes, lows, last_date = build_weeks(daily)
    n = len(closes)
    result = compute_floor(dates, closes, lows, last_date)
    # asOf is the Sunday of the last completed week (the display rule);
    # dataThrough is the last daily close the fixture was built from.
    result = {'symbol': 'BTC', 'asOf': result['lastCompletedSunday'],
              'dataThrough': str(last_date), 'source': source,
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
    print(f"last completed week {result['lastCompletedWeek']} "
          f"close ${result['lastCompletedClose']:,.2f} "
          f"({result['pctAtLastCompleted']}% vs floor) "
          f"in-progress week {result['inProgressWeek']} "
          f"close ${result['inProgressClose']:,.2f} "
          f"({result['inProgressPct']}% vs floor)")
    print(f"broken={result['broken']} trigger "
          f"${result['breakTrigger']:,.0f} maxUnder "
          f"{result['maxUnderPct']}% asOf {result['asOf']}")
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
