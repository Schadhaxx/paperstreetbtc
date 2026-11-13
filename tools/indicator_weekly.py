#!/usr/bin/env python3
"""Weekly OHLC candles for the Maple Leaf screener MARKET INDICATOR tiles.

Writes one file per indicator: assets/data/{wti,gold,us10y,vix,dia,qqq,usdcad,dxy}-weekly.json
(WTI = CL=F NYMEX front-month futures, GOLD = GC=F COMEX futures,
US10Y = ^TNX, VIX = ^VIX, DIA = DIA (SPDR Dow Jones Industrial
Average ETF, replaced the ^DJI index 13 Nov 2026), QQQ = QQQ,
CADUSD = CADUSD=X, USD per 1 CAD, DXY = DX-Y.NYB).

Source: Yahoo chart API, unadjusted daily OHLC (quote open/high/low/close,
never adjclose), fetched server-side by this tool — never in the browser.
Weeks are UTC Monday-Sunday, YTD 2026, first week Mon 29 Dec 2025
(one trading day, 2 Jan 2026), matching the shipped 30 Oct 2026 files.

Append-only by design. The shipped weeks are NEVER rewritten: the tool
loads the existing file, keeps every shipped week verbatim, and only
appends weeks whose Monday is after the last shipped Sunday, plus the
current (in-progress) week. That protects the two flagged shipped values
pending Grok Bot + Chief of Staff review: gold's 30 Oct close $3,901.20
(file note calls it a daily close, but it came from a Friday intraday
pull) and WTI's 26 Oct week close $104.24 (an intraday snapshot at
30 Oct 3:42 p.m. ET, not a final close). If Yahoo's recomputed final
for a shipped week differs from the shipped value, the tool reports it
in the file note as "preserved, pending review" and does NOT overwrite it.

The current week candle: open = first bar's open in that week,
high = max high to date, low = min low to date, close = last bar's
close to date, days = number of bars in the week so far. It is marked
in the file as inProgress ("in progress, as of <ET date/time>") and the
chart module renders it with an "(in progress)" label; its close is
never called a final close. Weeks are finalised only by appending a
later week — a shipped week is never edited in place.

Fails loud. A Yahoo error, a null OHLC in a returned bar, or an
inconsistent bar aborts with exit 1 and writes nothing. A failed run
never exits 0 while leaving stale data looking fresh.

usage:
  python3 tools/indicator_weekly.py [--out-dir assets/data]
  python3 tools/indicator_weekly.py --check-only [--out-dir assets/data]
"""
import json, math, os, sys, time, datetime as dt, urllib.request
from zoneinfo import ZoneInfo

# Holidays are the NYSE list in stock_weekly (2026-2028); importing it
# keeps the two tools on the same calendar. stock_weekly has no
# import-time side effects (guarded by __main__).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stock_weekly as SW

UTC = dt.timezone.utc
try:
    ET = ZoneInfo('America/New_York')
except Exception:
    # tzdata missing (a minimal container): do not crash on import — the
    # intraday gate must still be able to run and skip. build() raises a
    # clear error if it is ever called without one.
    ET = None
MN = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

# symbol key -> (Yahoo symbol, decimals, source blurb, unit)
SPECS = {
    'WTI':   ('CL%3DF', 2, 'Yahoo CL=F (NYMEX front-month WTI futures, continuous series), $/barrel', 'usd'),
    'GOLD':  ('GC%3DF', 2, 'Yahoo GC=F (COMEX futures), $/troy oz', 'usd'),
    'US10Y': ('%5ETNX', 3, 'Yahoo ^TNX (10-year Treasury yield), %', 'pct'),
    'VIX':   ('%5EVIX', 2, 'Yahoo ^VIX (CBOE Volatility Index), index points', 'pts'),
    # Added with the Desk stocks/indicators (Nov 2026). Yahoo symbols are
    # URL-encoded as in the shipped files; CADUSD is CADUSD=X (USD per 1
    # CAD, ~0.709), NOT USDCAD=X.
    # DIA replaced DJIA (^DJI index points) on 13 Nov 2026 (Sunil): the
    # Desk shows the SPDR Dow Jones Industrial Average ETF in USD.
    'DIA':   ('DIA', 2, 'Yahoo DIA (SPDR Dow Jones Industrial Average ETF Trust), USD', 'usd'),
    'QQQ':   ('QQQ', 2, 'Yahoo QQQ (Invesco QQQ Trust), USD', 'usd'),
    'CADUSD': ('CADUSD%3DX', 4, 'Yahoo CADUSD=X (CAD/USD), USD per 1 CAD', 'usd'),
    'DXY':   ('DX-Y.NYB', 2, 'Yahoo DX-Y.NYB (ICE US Dollar Index), index points', 'pts'),
}
FILES = {'WTI': 'wti-weekly.json', 'GOLD': 'gold-weekly.json',
         'US10Y': 'us10y-weekly.json', 'VIX': 'vix-weekly.json',
         'DIA': 'dia-weekly.json', 'QQQ': 'qqq-weekly.json',
         'CADUSD': 'usdcad-weekly.json', 'DXY': 'dxy-weekly.json'}


def rnd(x, nd):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(float(x)):
        raise ValueError(f'bad price {x!r}')
    return float(format(float(x), f'.{nd}f'))


def dlabel(d):
    return f'{d.day} {MN[d.month - 1]} {d.year}'


def week_monday(d):
    return d - dt.timedelta(days=d.weekday())


def fetch_yahoo(ysym):
    p1 = int(dt.datetime(2025, 12, 20, tzinfo=UTC).timestamp())
    p2 = int(time.time()) + 2 * 86400
    url = (f'https://query1.finance.yahoo.com/v8/finance/chart/{ysym}'
           f'?period1={p1}&period2={p2}&interval=1d')
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 paperstreet-indicator-weekly'})
    try:
        with urllib.request.urlopen(req, timeout=30) as f:
            j = json.load(f)
    except Exception as e:
        raise RuntimeError(f'Yahoo fetch failed ({type(e).__name__}: {e})')
    err = (j.get('chart') or {}).get('error')
    res = (j.get('chart') or {}).get('result') or []
    if not res:
        raise RuntimeError(f'Yahoo returned no result ({err})')
    return res[0]


def bars_from_payload(key, payload):
    nd = SPECS[key][1]
    try:
        q = payload['indicators']['quote'][0]
        ts = payload['timestamp']
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f'{key}: Yahoo payload missing OHLC ({type(e).__name__})')
    # Yahoo inserts null-OHLC rows for market holidays (e.g. 25 Dec 2025 for
    # ^VIX). Those are not trading days and are skipped; a null bar on any
    # other day is a hard failure, never skipped or filled.
    # NYSE holidays from stock_weekly (2026-2028) plus 25 Dec 2025, the
    # only pre-2026 holiday in the indicator data (Yahoo inserts a
    # null-OHLC row for it, e.g. ^VIX). A hardcoded 2026-only list would
    # fail on 2027+ holidays.
    HOLIDAYS = SW.HOLIDAYS | {'2025-12-25'}
    out = {}
    for t, o, h, l, c in zip(ts, q['open'], q['high'], q['low'], q['close']):
        if t is None or any(v is None for v in (o, h, l, c)):
            day = dt.datetime.fromtimestamp(t, UTC).date() if t else None
            if day is not None and (day.weekday() >= 5 or day.isoformat() in HOLIDAYS):
                continue
            raise RuntimeError(f'{key}: null OHLC on {day.isoformat() if day else "?"} — refusing to skip or fill')
        day = dt.datetime.fromtimestamp(int(t), UTC).date()
        if day in out:
            raise RuntimeError(f'{key}: duplicate bar {day}')
        if h < max(o, c) - 1e-9 or l > min(o, c) + 1e-9 or l > h:
            raise RuntimeError(f'{key}: OHLC inconsistent on {day}: o={o} h={h} l={l} c={c}')
        b = {'open': rnd(o, nd), 'high': rnd(h, nd), 'low': rnd(l, nd), 'close': rnd(c, nd)}
        b['high'] = max(b['high'], b['open'], b['close'])
        b['low'] = min(b['low'], b['open'], b['close'])
        out[day] = b
    if not out:
        raise RuntimeError(f'{key}: Yahoo returned no daily bars')
    return out


def candle_for_week(bars, monday):
    ds = sorted(d for d in bars if week_monday(d) == monday)
    if not ds:
        return None
    rows = [bars[d] for d in ds]
    sun = monday + dt.timedelta(days=6)
    return {
        'monday': monday.isoformat(), 'sunday': sun.isoformat(),
        'label': f"{dlabel(monday)} \u2013 {dlabel(sun)}",
        'days': len(ds), 'open': rows[0]['open'],
        'high': max(r['high'] for r in rows), 'low': min(r['low'] for r in rows),
        'close': rows[-1]['close'],
    }


def build(key, out_dir, check_only):
    if ET is None:
        raise RuntimeError(f'{key}: America/New_York time zone data unavailable — cannot build')
    ysym, nd, source, unit = SPECS[key]
    path = os.path.join(out_dir, FILES[key])
    with open(path) as f:
        old = json.load(f)
    weeks = list(old.get('weeks') or [])
    if not weeks:
        raise RuntimeError(f'{key}: shipped file has no weeks — refusing to build from scratch')
    last_sunday = dt.date.fromisoformat(weeks[-1]['sunday'])
    payload = fetch_yahoo(ysym)
    bars = bars_from_payload(key, payload)
    now_et = dt.datetime.now(ET)
    asof_label = now_et.strftime('%-d %b %Y, %-I:%M %p ET') if hasattr(now_et, 'strftime') else str(now_et)
    # Recompute ONLY the last shipped week from Yahoo for comparison — never
    # write it. Earlier weeks are preserved silently: Yahoo restates old
    # bars by cents, and listing every restatement would bloat the note.
    # The last week is the review-relevant one (gold's flagged 30 Oct close,
    # WTI's intraday snapshot), so only its close difference is noted.
    preserved = []
    last_w = weeks[-1]
    recomputed = candle_for_week(bars, dt.date.fromisoformat(last_w['monday']))
    if recomputed and abs(recomputed['close'] - last_w['close']) > 10 ** (-nd) * 1.5:
        preserved.append(f"week of {last_w['monday']} shipped close {last_w['close']} differs from Yahoo recomputed {recomputed['close']} — preserved as shipped, pending review")
    today_utc = dt.datetime.now(UTC).date()
    cur_mon = week_monday(today_utc)
    # Daily-update rule (keeps pipeline commits to at most one a day):
    # if the last shipped week IS the current week and it was already
    # rebuilt today (asOf date == today in ET), there is nothing to do.
    # If it was rebuilt on an earlier day, refresh that one candle in
    # place (close/high/low to date) instead of appending a duplicate.
    if weeks[-1]['monday'] == cur_mon.isoformat():
        asof_date = None
        try:
            asof_date = dt.datetime.strptime(old.get('asOf', ''), '%d %b %Y, %I:%M %p ET').date()
        except Exception:
            asof_date = None
        if asof_date == now_et.date():
            print(f'{key}: current week already rebuilt today — file unchanged')
            return None
        refreshed = candle_for_week(bars, cur_mon)
        if refreshed and refreshed != weeks[-1]:
            doc = dict(old)
            doc['weeks'] = weeks[:-1] + [refreshed]
            doc['asOf'] = asof_label
            doc['inProgress'] = f'in progress, as of {asof_label}'
            doc['note'] = old.get('note', '') + f' Latest week ({refreshed["label"]}) refreshed in progress as of {asof_label}; its close is not a final close.'
            if check_only:
                print(f'{key}: would refresh current week to {refreshed}')
                return doc
            with open(path, 'w') as f:
                json.dump(doc, f, indent=2); f.write('\n')
            print(f'{key}: refreshed current week -> {path}')
            return doc
        print(f'{key}: current week unchanged — file unchanged')
        return None
    # Append weeks after the last shipped Sunday, and the current week.
    new_weeks = []
    mon = last_sunday + dt.timedelta(days=1)  # next Monday
    while mon <= today_utc:
        c = candle_for_week(bars, mon)
        if c:
            new_weeks.append(c)
        mon += dt.timedelta(days=7)
    if not new_weeks:
        print(f'{key}: no new weeks (last shipped Sunday {last_sunday}) — file unchanged')
        return None
    cur_mon = week_monday(today_utc)
    in_progress = None
    if new_weeks and new_weeks[-1]['monday'] == cur_mon.isoformat() and cur_mon + dt.timedelta(days=6) > today_utc:
        in_progress = f'in progress, as of {asof_label}'
    doc = dict(old)
    doc['weeks'] = weeks + new_weeks
    doc['asOf'] = asof_label
    doc['inProgress'] = in_progress
    note = old.get('note', '').replace('Manual refresh only, when Sunil asks.', 'Refreshed by the weekly rebuild (proposals/current-week-candle).').replace('Dated snapshot shipped with the screener — not a live quote.', 'Weekly snapshot — the latest week is in progress until it closes.')
    if preserved:
        note = note + ' Preserved shipped weeks (not overwritten): ' + '; '.join(preserved) + '.'
    if in_progress:
        note = note + f' Latest week ({new_weeks[-1]["label"]}) is in progress as of {asof_label}; its close is not a final close.'
    doc['note'] = note
    if check_only:
        print(f'{key}: would append {len(new_weeks)} week(s), last={new_weeks[-1]}, inProgress={in_progress}')
        return doc
    with open(path, 'w') as f:
        json.dump(doc, f, indent=2)
        f.write('\n')
    print(f'{key}: appended {len(new_weeks)} week(s) -> {path}, inProgress={in_progress}')
    return doc


def main(argv):
    out_dir, check_only = 'assets/data', False
    i = 0
    while i < len(argv):
        if argv[i] == '--out-dir':
            out_dir = argv[i + 1]; i += 2
        elif argv[i] == '--check-only':
            check_only = True; i += 1
        else:
            print(f'unknown arg {argv[i]}', file=sys.stderr); return 2
    bad = 0
    for key in SPECS:
        try:
            build(key, out_dir, check_only)
        except Exception as e:
            print(f'{key}: FAILED: {e}', file=sys.stderr); bad += 1
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
