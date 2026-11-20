#!/usr/bin/env python3
"""Backfill Desk weekly files with history so the 50/200-week moving averages draw.

Skunkworks TA 2.0 (test branch only). PREPENDS weeks to the Desk weekly
files (16 stocks + 8 indicators) back to Nov 2021, keeping the shipped
47 weeks (29 Dec 2025 - 16 Nov 2026) unchanged in value. SPCX is
untouched (listed 12 Jun 2026, no earlier history). IBIT starts
11 Jan 2024 (launched that day) so it tops out near 150 weeks.

Source: Yahoo chart API daily OHLC (unadjusted), the same source and
the same conventions as the site's own generators: tools/stock_weekly.py
for stocks (ET dates, Monday-Sunday weeks, volume = summed daily
volume) and tools/indicator_weekly.py for indicators (UTC dates).
Backfilled weeks are closed history; the file's asOf / inProgress /
last week are untouched, and a sentence is appended to the note.

Fails loud. A Yahoo error, a null OHLC on a real session, an OHLC
inconsistency, a stock week whose day count disagrees with the NYSE
calendar, a non-contiguous week, or any change to the shipped tail
aborts with exit 1 and writes nothing.

usage:
  python3 tools/ta_backfill_weekly.py [--out-dir assets/data] [--dry-run]
"""
import datetime as dt
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stock_weekly as SW
import indicator_weekly as IW

NY = ZoneInfo('America/New_York')
UTC = dt.timezone.utc
FIRST_OLD_MONDAY = dt.date(2025, 12, 29)  # first shipped week (all files but SPCX)
FETCH_SINCE = dt.date(2021, 11, 1)        # 5y of daily bars covers 200+ weeks
CUTOFF = dt.date(2025, 12, 28)            # last day of the last prepended week;
# bars after this belong to the shipped tail and are never parsed (Yahoo's
# latest bar can be a null-OHLC stub for the still-open session).
BACKFILL_DATE = '19 Nov 2026'

# NYSE full closures 2021-2025 (the site's stock_weekly.HOLIDAYS covers
# 2026-2028 only). Includes 9 Jan 2025, the Carter mourning closure.
# Used to validate stock week day counts and to skip Yahoo's null-OHLC
# holiday rows for indicators. Futures/FX weeks are NOT validated
# against this calendar (their markets keep different holidays).
HOLIDAYS_2021_2025 = {
    '2021-01-01', '2021-01-18', '2021-02-15', '2021-04-02', '2021-05-31',
    '2021-07-05', '2021-09-06', '2021-11-25', '2021-12-24',
    '2022-01-17', '2022-02-21', '2022-04-15', '2022-05-30', '2022-06-20',
    '2022-07-04', '2022-09-05', '2022-11-24', '2022-12-26',
    '2023-01-02', '2023-01-16', '2023-02-20', '2023-04-07', '2023-05-29',
    '2023-06-19', '2023-07-04', '2023-09-04', '2023-11-23', '2023-12-25',
    '2024-01-01', '2024-01-15', '2024-02-19', '2024-03-29', '2024-05-27',
    '2024-06-19', '2024-07-04', '2024-09-02', '2024-11-28', '2024-12-25',
    '2025-01-01', '2025-01-09', '2025-01-20', '2025-02-17', '2025-04-18',
    '2025-05-26', '2025-06-19', '2025-07-04', '2025-09-01', '2025-11-27',
    '2025-12-25',
}
# indicator_weekly reads SW.HOLIDAYS at call time when skipping null rows,
# so patching it here extends its holiday handling to the backfill range.
SW.HOLIDAYS = SW.HOLIDAYS | HOLIDAYS_2021_2025
HOLIDAYS = SW.HOLIDAYS

STOCK_SYMS = list(SW.SYMS) + ['BRK.B']  # SW.SYMS omits BRK.B (hyphen ticker)
INDICATOR_KEYS = list(IW.SPECS.keys())


def fetch_payload(ysym):
    p1 = int(dt.datetime(FETCH_SINCE.year, FETCH_SINCE.month, FETCH_SINCE.day,
                         tzinfo=UTC).timestamp())
    p2 = int(time.time()) + 2 * 86400
    url = (f'https://query1.finance.yahoo.com/v8/finance/chart/{ysym}'
           f'?period1={p1}&period2={p2}&interval=1d')
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 paperstreet-ta-backfill'})
    try:
        with urllib.request.urlopen(req, timeout=30) as f:
            j = json.load(f)
    except Exception as e:
        raise RuntimeError(f'{ysym}: Yahoo fetch failed ({type(e).__name__}: {e})')
    err = (j.get('chart') or {}).get('error')
    res = (j.get('chart') or {}).get('result') or []
    if not res:
        raise RuntimeError(f'{ysym}: Yahoo returned no result ({err})')
    return res[0]


def parse_stock_payload(sym, payload):
    """Daily bars with volume, ET dates. Mirrors stock_weekly's parser
    (unadjusted OHLC, never adjclose) plus the volume column."""
    try:
        q = payload['indicators']['quote'][0]
        ts = payload['timestamp']
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f'{sym}: Yahoo payload missing OHLC ({type(e).__name__})')
    vols = q.get('volume') or []
    out = {}
    for i, t in enumerate(ts):
        if t is not None and dt.datetime.fromtimestamp(int(t), NY).date() > CUTOFF:
            continue  # shipped tail territory; also skips today's null stub
        o, h, l, c = q['open'][i], q['high'][i], q['low'][i], q['close'][i]
        v = vols[i] if i < len(vols) else None
        if t is None or any(x is None for x in (o, h, l, c)):
            day = dt.datetime.fromtimestamp(t, NY).date() if t else None
            if day is not None and (day.weekday() >= 5 or day.isoformat() in HOLIDAYS):
                continue
            raise RuntimeError(f'{sym}: null OHLC on {day} — refusing to skip or fill')
        day = dt.datetime.fromtimestamp(int(t), NY).date()
        if day in out:
            raise RuntimeError(f'{sym}: duplicate bar {day}')
        bar = SW.bar_from_raw(sym, day, float(o), float(h), float(l), float(c))
        bar['volume'] = int(v) if v is not None else None
        out[day] = bar
    if not out:
        raise RuntimeError(f'{sym}: Yahoo returned no daily bars')
    return out


def clean_indicator_bars(key, payload):
    """Yahoo's FX feed carries float noise: 34 of ~1300 CADUSD bars have
    an open or close a hair outside [low, high] in the raw floats (up
    to 0.0002, two ticks at 4dp). The site's own parsers fail loud on
    any such bar, which would block the whole CADUSD backfill over
    noise the shipped week candles barely use (a mid-week bar's open
    and close are not in the week candle at all). So, bar by bar, in
    the backfill script only (the site's tools are untouched), widen
    the raw high/low to cover the raw open/close — the exact
    rounding-widen convention stock_weekly.bar_from_raw already uses
    (preserve open/close, pull high/low out to cover them). When the
    bar is consistent after rounding to the file's decimals, the
    rounded values are identical either way; otherwise a rounded bound
    moves by at most two ticks. Each repair is logged below. A bar off
    by more than 0.0005 is not noise and is left alone so
    bars_from_payload fails loud on it."""
    nd = IW.SPECS[key][1]
    q = (payload.get('indicators') or {}).get('quote', [{}])[0]
    ts = payload.get('timestamp') or []
    for i, t in enumerate(ts):
        try:
            o, h, l, c = q['open'][i], q['high'][i], q['low'][i], q['close'][i]
        except (IndexError, TypeError):
            continue
        if t is None or any(v is None for v in (o, h, l, c)):
            continue
        if h < max(o, c) - 1e-9 or l > min(o, c) + 1e-9:
            day = dt.datetime.fromtimestamp(int(t), UTC).date().isoformat()
            ro, rh, rl, rc = round(o, nd), round(h, nd), round(l, nd), round(c, nd)
            unchanged = rh >= max(ro, rc) and rl <= min(ro, rc)
            # Widen the raw high/low to cover the raw open/close (the
            # rounding-widen convention stock_weekly.bar_from_raw uses).
            # A bar whose open/close sits outside [low, high] by more
            # than 0.0005 is not noise: leave it so bars_from_payload
            # fails loud on it. (The violation is the overshoot past
            # the bound, not the day's range.)
            violation = max(0.0, max(o, c) - h, l - min(o, c))
            if violation > 0.0005:
                continue
            q['high'][i] = max(h, o, c)
            q['low'][i] = min(l, o, c)
            why = 'rounded value unchanged' if unchanged else 'bound moved <=2 ticks'
            print(f'  NOTE {key}: widened high/low on {day} to cover open/close ({why})')
    return payload


# London (CCY exchange) bank holidays 2021-2026. Yahoo's CADUSD=X
# bars are stamped 23:00 UTC, so a null row for a summer (BST) holiday
# is dated the day BEFORE the holiday (23:00 UTC = 00:00 BST next day);
# a winter (GMT) holiday's null row carries the holiday's own date.
# The five null rows in 5y of CADUSD data are exactly: New Year
# 2025-01-01 and 2026-01-01, Christmas 2025-12-25 (own dates), and
# the days before Good Friday 2025-04-18 and Easter Monday 2025-04-21.
LONDON_HOLIDAYS = {
    '2021-01-01', '2021-04-02', '2021-04-05', '2021-05-03', '2021-05-31',
    '2021-08-30', '2021-12-27', '2021-12-28',
    '2022-01-03', '2022-04-15', '2022-04-18', '2022-05-02', '2022-06-02',
    '2022-06-03', '2022-08-29', '2022-09-19', '2022-12-26', '2022-12-27',
    '2023-01-02', '2023-04-07', '2023-04-10', '2023-05-01', '2023-05-08',
    '2023-05-29', '2023-08-28', '2023-12-25', '2023-12-26',
    '2024-01-01', '2024-03-29', '2024-04-01', '2024-05-06', '2024-05-27',
    '2024-08-26', '2024-12-25', '2024-12-26',
    '2025-01-01', '2025-04-18', '2025-04-21', '2025-05-05', '2025-05-26',
    '2025-08-25', '2025-12-25', '2025-12-26',
    '2026-01-01', '2026-04-03', '2026-04-06', '2026-05-04', '2026-05-25',
    '2026-08-31', '2026-12-25', '2026-12-28',
}
# UTC dates on which a null CADUSD row is a holiday, not a missing
# session: each London holiday plus the day before it (BST stamp shift).
CADUSD_NULL_SKIP = set()
for _h in LONDON_HOLIDAYS:
    _d = dt.date.fromisoformat(_h)
    CADUSD_NULL_SKIP.add(_h)
    CADUSD_NULL_SKIP.add((_d - dt.timedelta(days=1)).isoformat())


def drop_cadusd_holiday_nulls(payload):
    """Drop null-OHLC CADUSD rows dated on a London bank holiday (or
    the day before it, BST stamp shift). Yahoo inserts these for
    CCY-exchange closures; they are non-sessions, not missing data.
    Any null row outside that set is left in place so
    bars_from_payload fails loud on it."""
    q = (payload.get('indicators') or {}).get('quote', [{}])[0]
    ts = payload.get('timestamp') or []
    keep = []
    for i, t in enumerate(ts):
        if t is not None and any(v is None for v in (q['open'][i], q['high'][i], q['low'][i], q['close'][i])):
            day = dt.datetime.fromtimestamp(int(t), UTC).date().isoformat()
            if day in CADUSD_NULL_SKIP:
                print(f'  NOTE CADUSD: dropped null row {day} (CCY-exchange holiday)')
                continue
        keep.append(i)
    out = dict(payload)
    out['timestamp'] = [ts[i] for i in keep]
    ind = dict(payload.get('indicators') or {})
    q2 = dict(q)
    for k, v in q.items():
        if isinstance(v, list):
            q2[k] = [v[i] for i in keep if i < len(v)]
    ind['quote'] = [q2]
    out['indicators'] = ind
    return out


def trim_payload_to_cutoff(payload):
    """Drop bars after CUTOFF (shipped-tail territory; also drops today's
    null-OHLC stub) from a Yahoo payload, trimming every parallel array."""
    q = (payload.get('indicators') or {}).get('quote', [{}])[0]
    ts = payload.get('timestamp') or []
    keep = [i for i, t in enumerate(ts)
            if t is not None and dt.datetime.fromtimestamp(int(t), UTC).date() <= CUTOFF]
    out = dict(payload)
    out['timestamp'] = [ts[i] for i in keep]
    ind = dict(payload.get('indicators') or {})
    q2 = dict(q)
    for k, v in q.items():
        if isinstance(v, list):
            q2[k] = [v[i] for i in keep if i < len(v)]
    ind['quote'] = [q2]
    out['indicators'] = ind
    return out


def parse_indicator_volume(payload):
    """UTC date -> daily volume (None when Yahoo carries none: indexes, FX)."""
    try:
        q = payload['indicators']['quote'][0]
        ts = payload['timestamp']
    except (KeyError, IndexError, TypeError):
        return {}
    vols = q.get('volume') or []
    out = {}
    for i, t in enumerate(ts):
        if t is None:
            continue
        day = dt.datetime.fromtimestamp(int(t), UTC).date()
        v = vols[i] if i < len(vols) else None
        out[day] = int(v) if v is not None else None
    return out


def expected_sessions(mon, first_bar):
    """Weekday non-holiday dates in [max(mon, first_bar), mon+6]."""
    out = []
    d = max(mon, first_bar)
    end = mon + dt.timedelta(days=6)
    while d <= end:
        if d.weekday() < 5 and d.isoformat() not in HOLIDAYS:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


def build_stock_weeks(sym, bars, first_old):
    """Weeks strictly before first_old, from daily bars. Same shape as
    stock_weekly.build_doc's weeks (incl. summed volume)."""
    first_bar = min(bars)
    mon = SW.week_monday(first_bar)
    last_mon = first_old - dt.timedelta(days=7)
    weeks = []
    while mon <= last_mon:
        ds = sorted(d for d in bars if SW.week_monday(d) == mon)
        if not ds:
            raise RuntimeError(f'{sym}: no bars in week of {mon} — refusing to invent a week')
        exp = expected_sessions(mon, first_bar)
        if ds != exp:
            raise RuntimeError(f'{sym}: week of {mon} has sessions {[d.isoformat() for d in ds]} '
                               f'but calendar expects {[d.isoformat() for d in exp]}')
        rows = [bars[d] for d in ds]
        o, c = rows[0]['open'], rows[-1]['close']
        h, l = max(r['high'] for r in rows), min(r['low'] for r in rows)
        h, l = max(h, o, c), min(l, o, c)
        sun = mon + dt.timedelta(days=6)
        vols = [r['volume'] for r in rows if r.get('volume') is not None]
        weeks.append({
            'monday': mon.isoformat(), 'sunday': sun.isoformat(),
            'label': f'{SW.dlabel(mon)} \u2013 {SW.dlabel(sun)}',
            'days': len(ds), 'open': o, 'high': h, 'low': l, 'close': c,
            'volume': sum(vols) if vols else None,
        })
        mon += dt.timedelta(days=7)
    return weeks


def build_indicator_weeks(key, bars, vols, first_old):
    """Weeks strictly before first_old, from daily bars. Same shape as
    indicator_weekly.candle_for_week plus summed volume. DIA/QQQ are
    NYSE ETFs, so their day counts are validated against the NYSE
    calendar like stocks; futures/FX/index weeks are validated only
    for contiguity, OHLC and 1-5 days (their markets keep different
    holidays, and indicator_weekly itself enforces no day counts)."""
    first_bar = min(bars)
    mon = IW.week_monday(first_bar)
    last_mon = first_old - dt.timedelta(days=7)
    weeks = []
    while mon <= last_mon:
        c = IW.candle_for_week(bars, mon)
        if c is None:
            raise RuntimeError(f'{key}: no bars in week of {mon} — refusing to invent a week')
        ds = sorted(d for d in bars if IW.week_monday(d) == mon)
        if not 1 <= len(ds) <= 6:
            raise RuntimeError(f'{key}: week of {mon} has {len(ds)} days')
        if key in ('DIA', 'QQQ'):
            exp = expected_sessions(mon, first_bar)
            if ds != exp:
                raise RuntimeError(f'{key}: week of {mon} has sessions {[d.isoformat() for d in ds]} '
                                   f'but calendar expects {[d.isoformat() for d in exp]}')
        vs = [vols[d] for d in ds if vols.get(d)]
        c['volume'] = sum(vs) if vs else None
        # The week candle itself must satisfy the OHLC invariant (a
        # widened bound above guarantees it, but verify rather than trust).
        if (c['high'] < max(c['open'], c['close']) or c['low'] > min(c['open'], c['close'])
                or c['low'] > c['high']):
            raise RuntimeError(f"{key}: week of {mon} candle inconsistent: {c}")
        weeks.append(c)
        mon += dt.timedelta(days=7)
    return weeks


def backfill_file(path, prepend, old_weeks, first_monday_label):
    doc = json.load(open(path))
    old = doc['weeks']
    if old != old_weeks:
        raise RuntimeError(f'{path}: shipped weeks changed under us — aborting')
    new_weeks = prepend + old
    for a, b in zip(new_weeks, new_weeks[1:]):
        if dt.date.fromisoformat(b['monday']) != dt.date.fromisoformat(a['monday']) + dt.timedelta(days=7):
            raise RuntimeError(f"{path}: weeks not contiguous at {a['monday']} -> {b['monday']}")
    if new_weeks[-len(old):] != old:
        raise RuntimeError(f'{path}: shipped tail changed — aborting')
    new = dict(doc)
    new['weeks'] = new_weeks
    note = doc.get('note', '')
    new['note'] = (note + f' Backfilled {BACKFILL_DATE} on the TA 2.0 test branch: weekly history '
                   f'extended back to {first_monday_label}; the {len(old)} weeks from '
                   f'{old[0]["monday"]} are unchanged from the shipped file.')
    return new


def main(argv):
    out_dir, dry_run = 'assets/data', False
    i = 0
    while i < len(argv):
        if argv[i] == '--out-dir':
            out_dir = argv[i + 1]; i += 2
        elif argv[i] == '--dry-run':
            dry_run = True; i += 1
        else:
            print(f'unknown arg {argv[i]}', file=sys.stderr); return 2
    results = {}
    docs = {}
    # --- stocks ---
    for sym in STOCK_SYMS:
        if sym == 'SPCX':
            print('SPCX: skipped — listed 12 Jun 2026, no earlier history exists')
            continue
        ysym = SW.YAHOO_MAP.get(sym, sym)
        path = os.path.join(out_dir, f'stock-weekly-{sym}.json')
        old = json.load(open(path))
        old_weeks = old['weeks']
        first_old = dt.date.fromisoformat(old_weeks[0]['monday'])
        payload = fetch_payload(ysym)
        bars = parse_stock_payload(sym, payload)
        prepend = build_stock_weeks(sym, bars, first_old)
        doc = backfill_file(path, prepend, old_weeks,
                            SW.dlabel(dt.date.fromisoformat(prepend[0]['monday'])))
        docs[path] = doc
        results[sym] = (len(old_weeks), len(prepend), len(doc['weeks']), prepend[0]['monday'])
        print(f'{sym}: old={len(old_weeks)} prepend={len(prepend)} total={len(doc["weeks"])} first={prepend[0]["monday"]}')
        time.sleep(0.3)
    # --- indicators ---
    for key in INDICATOR_KEYS:
        ysym = urllib.parse.unquote(IW.SPECS[key][0])
        path = os.path.join(out_dir, IW.FILES[key])
        old = json.load(open(path))
        old_weeks = old['weeks']
        first_old = dt.date.fromisoformat(old_weeks[0]['monday'])
        payload = fetch_payload(ysym)
        payload = trim_payload_to_cutoff(payload)
        payload = clean_indicator_bars(key, payload)
        if key == 'CADUSD':
            payload = drop_cadusd_holiday_nulls(payload)
        bars = IW.bars_from_payload(key, payload)
        vols = parse_indicator_volume(payload)
        prepend = build_indicator_weeks(key, bars, vols, first_old)
        doc = backfill_file(path, prepend, old_weeks,
                            IW.dlabel(dt.date.fromisoformat(prepend[0]['monday'])))
        docs[path] = doc
        results[key] = (len(old_weeks), len(prepend), len(doc['weeks']), prepend[0]['monday'])
        print(f'{key}: old={len(old_weeks)} prepend={len(prepend)} total={len(doc["weeks"])} first={prepend[0]["monday"]}')
        time.sleep(0.3)
    if dry_run:
        print('dry-run: nothing written')
        return 0
    os.makedirs(out_dir, exist_ok=True)
    for path, doc in docs.items():
        SW.write_doc(path, doc)
    print(f'ta-backfill wrote {len(docs)} file(s) -> {out_dir}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
