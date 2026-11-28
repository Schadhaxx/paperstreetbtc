#!/usr/bin/env python3
"""Reference functions for the BTC trend-support (floor) overlay redo.

Pure helpers: no I/O, no network. Pepper should export the same names
from tools/ta_floor.py (and keep the existing swing/anchor maths).

Weeks are Monday-start UTC, closing Sunday UTC. Only a completed week
can set broken. An in-progress week may be drawn dashed and never turns
the line red.
"""
from datetime import date, datetime, timedelta, timezone

LABEL = 'Trend support (weekly closes)'
BREAK_RULE = (
    'Completed weekly close (Monday-Sunday UTC) 2% or more below the floor. '
    'An in-progress week does not count.'
)
BROKEN_NOTE = (
    'Broken: a completed weekly close finished 2% or more below this line.'
)
BREAK_TOL = 0.98  # close <= floor * 0.98  ==  2% or more below


def parse_as_of(value):
    """Return ('date', date) or ('datetime', aware UTC datetime).

    A YYYY-MM-DD string or date is date-only (a daily close for that UTC
    day is available). An ISO datetime is an instant; timezone-naive
    values are treated as UTC.
    """
    if isinstance(value, datetime):
        return ('datetime', _as_utc_datetime(value))
    if isinstance(value, date):
        return ('date', value)
    if not isinstance(value, str):
        raise TypeError('as_of must be date, datetime, or ISO string')
    s = value.strip()
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    if 'T' in s:
        dt = datetime.fromisoformat(s)
        return ('datetime', _as_utc_datetime(dt))
    return ('date', date.fromisoformat(s[:10]))


def _as_utc_datetime(dt):
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


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
