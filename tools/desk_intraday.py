#!/usr/bin/env python3
"""Desk intraday refresh: keep the current week's Desk candle up to date.

Re-pulls ONLY the in-progress weekly candle for the 16 Desk stock pills
and the 8 indicator tiles on screener.html, every 15 minutes while NYSE
is open (plus one final run after the close). The candle is in progress,
not a live quote: the Pages CDN can lag ~10 min behind a push, so the
Desk shows the latest published candle, not a tick. Run by the
`desk-intraday` job in .github/workflows/desk-intraday.yml — never by
hand on main, never as a full rebuild (that is tools/stock_weekly.py /
tools/indicator_weekly.py).

For each symbol: load the shipped weekly file, fetch the current week's
daily bars from Yahoo, recompute ONLY the current week candle (open =
first bar's open in the week, high = max high to date, low = min low to
date, close = last bar's close to date, days = bars so far). If the
file's last week IS the current week, replace it in place; if it is a
past week, append the new current week. Past weeks that are final are
NEVER modified — the shipped weeks (including gold's flagged 30 Oct
close and WTI's 26 Oct week close, preserved pending review) stay
byte-identical. The one exception: a past week still marked in progress
is re-fetched and replaced with its final values before the new week is
appended, so a stale in-progress candle never freezes as a final week;
if it cannot be re-fetched and validated, the symbol is not appended
at all (the next 15-min tick retries).

Weeks follow each tool's existing convention: stocks by America/New_York
date, indicators by UTC date. Stocks fetch through the Yahoo map in
stock_weekly.YAHOO_MAP (BRK.B -> BRK-B); indicators through
indicator_weekly.SPECS (CADUSD is CADUSD=X, USD per 1 CAD, NOT
USDCAD=X).

Fails closed per symbol. A Yahoo error, empty bars, a null/inconsistent
bar, or a candle that fails validation keeps the last good file, warns,
and moves on to the next symbol. Every failure is named: the run prints a
::warning:: listing the stale symbols (and a plain log line with the same
names), so a run never passes quietly with part of the Desk stale. The
run FAILS (exit 1) if more than 3 symbols fail, if every symbol fails,
if a shipped file cannot be loaded, or if Yahoo rate-limits twice in a
row: a single HTTP 429 fails closed for that symbol only, but two
consecutive 429s abort the run (stop fetching, keep all last good files)
instead of hammering Yahoo. The file is written ONLY if something
changed (no empty writes, no timestamp-only writes).

Exit 0: every symbol processed (refreshed, appended, already up-to-date,
or skipped with no bars yet), with at most 3 failures (all named). A
--check-only run prints what would change and writes nothing.

The market-hours gate lives here too (--gate): the workflow's first
step asks this tool whether now (America/New_York) is inside a NYSE
session, so the cron alone is never trusted. Window: Mon-Fri
9:30 AM-4:30 PM ET (Friday runs to 4:45 PM ET, so a late Friday run
still finalises the week for the weekend); on an early-close day
9:30 AM-1:30 PM ET.
Holidays come from stock_weekly.HOLIDAYS (2026-2028); early closes are
the official NYSE list in EARLY_CLOSES below (2026-2028). If the
America/New_York zone data is missing or stale (wrong DST offsets) the
gate skips the run — it never fetches with untrusted ET times.

usage:
  python3 tools/desk_intraday.py [--out-dir assets/data] [--now ISO]
  python3 tools/desk_intraday.py --check-only [--out-dir assets/data]
  python3 tools/desk_intraday.py --symbol TSLA [--out-dir assets/data]
  python3 tools/desk_intraday.py --fixture bars.json [--out-dir DIR] [--now ISO]
  python3 tools/desk_intraday.py --gate   # prints run=1 / run=0 for the workflow
"""
import datetime as dt, json, math, os, re, sys, time, urllib.error, urllib.request
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stock_weekly as SW
import indicator_weekly as IW

try:
    NY = ZoneInfo('America/New_York')
except Exception:
    # tzdata missing (a minimal container): do not crash on import — the
    # gate must still be able to run and skip. tz_healthy() reports False
    # and in_window() / main() fail safe (skip, never fetch).
    NY = None
UTC = dt.timezone.utc

STOCK_SYMS = ['TSLA', 'PLTR', 'MSTR', 'IBIT', 'MU', 'META', 'SPCX',
              'AAPL', 'AMZN', 'MSFT', 'NFLX', 'SPOT', 'XYZ', 'GOOGL', 'NVDA', 'BRK.B']
INDICATOR_KEYS = ['WTI', 'GOLD', 'US10Y', 'VIX', 'DIA', 'QQQ', 'CADUSD', 'DXY']
STOCK_FILES = {s: f'stock-weekly-{s}.json' for s in STOCK_SYMS}

# NYSE early closes (1:00 PM ET), from the official NYSE holiday calendar
# (nyse.com/trade/hours-calendars, NYSE Group release 23 Dec 2025).
# 2026 has two: Fri 27 Nov (day after Thanksgiving) and Thu 24 Dec
# (Christmas Eve). 2027 has one: Fri 26 Nov (day after Thanksgiving).
# 2028 has two: Mon 3 Jul (day before Independence Day) and Fri 24 Nov
# (day after Thanksgiving). There is NO stock early close on Thu 2 Jul
# 2026, Fri 2 Jul 2027, or on 31 Dec in either year — those are full
# sessions — and 24 Dec 2027 is a full holiday (Christmas observed),
# covered by HOLIDAYS, not an early close. An earlier draft of this list
# had 25 Nov 2026 / 24 Nov 2027 (the day BEFORE Thanksgiving) and the
# July-2 / Dec-31 dates; all were wrong and are corrected here.
EARLY_CLOSES = {
    '2026-11-27', '2026-12-24',
    '2027-11-26',
    '2028-07-03', '2028-11-24',
}

# Fail the run if more than a few symbols fail. A few isolated failures
# are expected (a symbol's Yahoo bar can be delayed); 4+ of 24 (more than
# 1 in 6) signals a systemic problem (Yahoo outage, bad deploy, broken
# file), so the run fails to surface it instead of passing quietly with
# most of the Desk stale. The failing symbols are named in a ::warning::
# (see main) either way.
MAX_SYMBOL_FAILURES = 3

# --- market-hours gate (pure function; the workflow's first step) ---

_DEFAULT_ZONE = object()  # sentinel: tz_healthy() with no arg tests the module zone

def tz_healthy(zone=_DEFAULT_ZONE):
    """True only if the America/New_York zone loads AND its DST offsets are right.

    Guards against missing tzdata (ZoneInfo fails to load, NY is None) and
    stale tzdata (a zone whose rules are wrong). ET is UTC-5 in January and
    UTC-4 in July; anything else means the zone data cannot be trusted, so
    the gate skips the run instead of fetching with wrong times.
    """
    z = NY if zone is _DEFAULT_ZONE else zone
    if z is None:
        return False
    try:
        y = dt.datetime.now(dt.timezone.utc).year
        jan = dt.datetime(y, 1, 15, 12, 0, tzinfo=z).utcoffset()
        jul = dt.datetime(y, 7, 15, 12, 0, tzinfo=z).utcoffset()
        return jan == dt.timedelta(hours=-5) and jul == dt.timedelta(hours=-4)
    except Exception:
        return False

def in_window(now_et):
    """(inside, reason). `now_et` is an aware datetime in America/New_York."""
    if not tz_healthy():
        return False, 'America/New_York time zone data unavailable or stale — skipping run'
    now_et = now_et.astimezone(NY)
    d = now_et.date()
    if d.weekday() >= 5:
        return False, f'{d.isoformat()} is a weekend'
    if d.isoformat() in SW.HOLIDAYS:
        return False, f'{d.isoformat()} is an NYSE holiday'
    mins = now_et.hour * 60 + now_et.minute
    if d.isoformat() in EARLY_CLOSES:
        if 570 <= mins <= 810:  # 9:30 AM-1:30 PM ET
            return True, f'{d.isoformat()} is an early-close day, inside 9:30 AM-1:30 PM ET'
        return False, f'{d.isoformat()} is an early-close day, outside 9:30 AM-1:30 PM ET'
    # Friday's window runs to 4:45 PM ET (1005 min): the Friday final run
    # marks the week as final for the weekend, so a GitHub run delayed
    # past 4:30 PM still gets in instead of leaving the week "in progress"
    # over the weekend. Other weekdays end at 4:30 PM ET (990 min).
    # Early-close days are unaffected (their window is separate, above).
    end = 1005 if d.weekday() == 4 else 990
    if 570 <= mins <= end:  # 9:30 AM-4:30 PM ET (4:45 PM on Friday)
        return True, f'inside 9:30 AM-{"4:45" if d.weekday() == 4 else "4:30"} PM ET'
    return False, 'outside 9:30 AM-4:30 PM ET'

def session_open(now_et):
    """True if the NYSE session is open right now.

    9:30 AM to the close (4:00 PM, or 1:00 PM on an early-close day),
    on a weekday that is not an NYSE holiday. Used only for the
    in-progress label: while the session is open, the candle's close is
    today's in-progress print, not a completed session — so the label
    must not say "through last completed session".
    """
    d = now_et.date()
    if d.weekday() >= 5 or d.isoformat() in SW.HOLIDAYS:
        return False
    mins = now_et.hour * 60 + now_et.minute
    close_mins = 780 if d.isoformat() in EARLY_CLOSES else 960  # 1 PM / 4 PM
    return 570 <= mins < close_mins

# --- Yahoo fetch (windowed; parsing/validation reused from the existing tools) ---

class YahooRateLimited(RuntimeError):
    """Yahoo returned HTTP 429 (rate limit) for this symbol."""

def yahoo_symbol(sym):
    """Display ticker -> Yahoo symbol (BRK.B -> BRK-B; everything else unchanged)."""
    return SW.YAHOO_MAP.get(sym, sym)

def yahoo_url(ysym, since):
    p1 = int(dt.datetime(since.year, since.month, since.day, tzinfo=UTC).timestamp()) - 2 * 86400
    p2 = int(time.time()) + 2 * 86400
    return (f'https://query1.finance.yahoo.com/v8/finance/chart/{ysym}'
            f'?period1={p1}&period2={p2}&interval=1d')

def fetch_yahoo_payload(ysym, since):
    url = yahoo_url(ysym, since)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 paperstreet-desk-intraday'})
    try:
        with urllib.request.urlopen(req, timeout=30) as f:
            j = json.load(f)
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise YahooRateLimited(f'Yahoo rate-limited {ysym} (HTTP 429)')
        raise RuntimeError(f'Yahoo fetch failed (HTTPError {e.code}: {e})')
    except Exception as e:
        raise RuntimeError(f'Yahoo fetch failed ({type(e).__name__}: {e})')
    err = (j.get('chart') or {}).get('error')
    res = (j.get('chart') or {}).get('result') or []
    if not res:
        raise RuntimeError(f'Yahoo returned no result ({err})')
    return res[0]

def volumes_from_payload(payload, tz):
    """date -> summed-daily volume, from the same payload the OHLC came from.

    Returns {} when Yahoo carries no volume (indexes, FX): callers then
    keep the old candle's volume, or omit the field if it never had one.
    A volume entry that is missing or invalid for a bar in the current
    week also falls back to the old volume — volume is display-only and
    must never fail a candle.
    """
    try:
        q = payload['indicators']['quote'][0]
        vols = q.get('volume') or []
        ts = payload['timestamp']
    except (KeyError, IndexError, TypeError):
        return {}
    out = {}
    for t, v in zip(ts, vols):
        if t is None or v is None:
            continue
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
            continue
        out[dt.datetime.fromtimestamp(int(t), tz).date()] = int(v)
    return out

# --- fixture bars (offline tests; same shape as stock_weekly fixtures) ---

def bars_from_fixture_rows(sym, rows, nd):
    """Validate fixture rows exactly like the Yahoo parsers do.

    `nd` is the rounding (2 for stocks, the SPECS decimals for indicators).
    A null / non-finite / non-positive / inconsistent row raises — the
    caller treats that as a per-symbol failure and keeps the last good file.
    """
    out = {}
    vols = {}
    for row in rows:
        day = dt.date.fromisoformat(row['date'])
        if day in out:
            raise RuntimeError(f'{sym}: duplicate fixture bar {day}')
        vals = [row.get(k) for k in ('open', 'high', 'low', 'close')]
        if any(v is None for v in vals):
            raise RuntimeError(f'{sym}: null OHLC on {day} — refusing to skip or fill')
        for name, v in zip(('open', 'high', 'low', 'close'), vals):
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
                raise RuntimeError(f'{sym}: bad {name} {v!r} on {day}')
        o, h, l, c = (float(format(float(v), f'.{nd}f')) for v in vals)
        if h < max(o, c) - 1e-9 or l > min(o, c) + 1e-9 or l > h:
            raise RuntimeError(f'{sym}: OHLC inconsistent on {day}: o={o} h={h} l={l} c={c}')
        out[day] = {'open': o, 'high': max(h, o, c), 'low': min(l, o, c), 'close': c}
        if row.get('volume') is not None:
            v = row['volume']
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
                raise RuntimeError(f'{sym}: bad volume {v!r} on {day}')
            vols[day] = int(v)
    if not out:
        raise RuntimeError(f'{sym}: fixture has no daily bars')
    return out, vols

# --- candle build + validation ---

def candle_for_week(bars, monday, vols=None, old_volume=None):
    """Current-week candle from daily bars, or None when the week has no bars yet."""
    ds = sorted(d for d in bars if SW.week_monday(d) == monday)
    if not ds:
        return None
    rows = [bars[d] for d in ds]
    sun = monday + dt.timedelta(days=6)
    candle = {
        'monday': monday.isoformat(), 'sunday': sun.isoformat(),
        'label': f"{SW.dlabel(monday)} \u2013 {SW.dlabel(sun)}",
        'days': len(ds), 'open': rows[0]['open'],
        'high': max(r['high'] for r in rows), 'low': min(r['low'] for r in rows),
        'close': rows[-1]['close'],
    }
    # Volume is display-only and only where the shipped file already has
    # it (stocks, WTI, gold). Sum the week's daily volumes when Yahoo /
    # the fixture has all of them; otherwise keep the old week's volume.
    # Yahoo returns zero volumes for indexes/FX (US10Y, VIX, CADUSD,
    # DXY) — a zero sum is NOT a volume, so those files keep no volume
    # field at all rather than gaining a bogus "volume": 0.
    if vols is not None and all(d in vols for d in ds):
        total = sum(vols[d] for d in ds)
        if total > 0:
            candle['volume'] = total
        elif old_volume is not None:
            candle['volume'] = old_volume
    elif old_volume is not None:
        candle['volume'] = old_volume
    return candle

def validate_candle(candle):
    """Error strings for a recomputed candle (empty == ok). Fail closed."""
    bad = []
    if candle is None:
        return ['no bars for the current week']
    for k in ('open', 'high', 'low', 'close'):
        v = candle.get(k)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
            bad.append(f'bad {k} {v!r}')
    if not bad:
        o, h, l, c = candle['open'], candle['high'], candle['low'], candle['close']
        if h < max(o, c) or l > min(o, c) or l > h:
            bad.append(f'OHLC inconsistent: o={o} h={h} l={l} c={c}')
    if not isinstance(candle.get('days'), int) or isinstance(candle.get('days'), bool) or candle.get('days', 0) < 1:
        bad.append(f"bad days {candle.get('days')!r}")
    return bad

# --- note handling: replace the one "Latest week ..." sentence, never bloat ---

_STOCK_TAIL = re.compile(r" Latest week (?:is in progress as of|is a final close through)[^.]*\.")
_IND_TAIL = re.compile(r" Latest week \([^)]*\) (?:refreshed in progress|is in progress) as of [^;]*; its close is not a final close\.")

def refresh_note(note, tail, pattern):
    """Swap the existing latest-week sentence for `tail`, in place if one
    exists, appended if the file never had one. Everything else — the
    head, the preserved-weeks sentences, the dated-snapshot line — is
    left untouched."""
    note = note or ''
    if pattern.search(note):
        return pattern.sub(' ' + tail.strip(), note, count=1)
    return (note + ' ' + tail) if note else tail

# --- per-symbol refresh ---

def et_label(now_et):
    return now_et.strftime('%-d %b %Y, %-I:%M %p ET')

def refresh_stock(sym, out_dir, now, fixture_bars, check_only):
    """Returns (status, changed). status: refreshed|appended|unchanged|skipped|failed."""
    now_et = SW.parse_now(now)
    path = os.path.join(out_dir, STOCK_FILES[sym])
    try:
        old = json.load(open(path))
    except Exception as e:
        raise RuntimeError(f'{sym}: cannot load {path} ({type(e).__name__}: {e})')
    weeks = old.get('weeks') or []
    if not weeks:
        raise RuntimeError(f'{sym}: shipped file has no weeks — refusing to build from scratch')
    today_et = now_et.date()
    cur_mon = SW.week_monday(today_et)
    last = weeks[-1]
    last_mon = dt.date.fromisoformat(last['monday'])
    if last_mon > cur_mon:
        print(f'{sym}: shipped file is ahead of the current week ({last_mon} > {cur_mon}) — skipping')
        return 'skipped', False
    # If the last shipped week is a past week that was still in progress,
    # it must be finalised before a new week is appended — otherwise its
    # stale in-progress values would freeze as a final week (the 2 Nov
    # week was stuck at Thursday's close). Fetch from its Monday so its
    # bars are in the payload too.
    finalize_last = last_mon < cur_mon and bool(old.get('inProgress'))
    fetch_since = last_mon if finalize_last else cur_mon
    if fixture_bars is not None:
        bars, vols = fixture_bars
    else:
        payload = fetch_yahoo_payload(yahoo_symbol(sym), fetch_since)
        try:
            bars = SW.bars_from_yahoo_payload(yahoo_symbol(sym), payload)
        except RuntimeError as e:
            # A null row for TODAY before the first trade is "no bar yet",
            # not a failure: the market has not printed today. Any other
            # null row is a data problem and still fails closed.
            if f'null OHLC on {today_et.isoformat()}' in str(e):
                print(f'{sym}: no bar for today yet — file unchanged')
                return 'skipped', False
            raise
        vols = volumes_from_payload(payload, NY)
    old_volume = last.get('volume') if last_mon == cur_mon else None
    candle = candle_for_week(bars, cur_mon, vols, old_volume)
    if candle is None:
        print(f'{sym}: no bars for the current week yet — file unchanged')
        return 'skipped', False
    bad = validate_candle(candle)
    if bad:
        print(f'{sym}: recomputed candle invalid ({ "; ".join(bad) }) — keeping last good file', file=sys.stderr)
        return 'failed', False
    # Finalise the previous in-progress week before appending: re-fetch
    # (already in the payload) and validate it, replace it, then append.
    # If it cannot be finalised, do NOT append — the file stays as-is and
    # the next 15-min tick retries, rather than freezing stale values.
    if finalize_last:
        prev = candle_for_week(bars, last_mon, vols, last.get('volume'))
        prev_bad = validate_candle(prev)
        if prev is None or prev_bad:
            why = 'no bars' if prev is None else '; '.join(prev_bad)
            print(f'{sym}: cannot finalise previous week {last_mon} ({why}) — keeping last good file, not appending', file=sys.stderr)
            return 'failed', False
        if prev['days'] < last['days']:
            print(f'{sym}: re-fetched previous week {last_mon} has fewer days ({prev["days"]}) than shipped ({last["days"]}) — keeping last good file, not appending', file=sys.stderr)
            return 'failed', False
        weeks = weeks[:-1] + [prev]
        print(f'{sym}: finalised previous week {last_mon} (close {prev["close"]}, {prev["days"]} days) before appending')
    last_bar = max(d for d in bars if SW.week_monday(d) == cur_mon)
    # Week finished only on the weekend, or Friday after the close has
    # settled (4:15 PM, or 1:15 PM on an early-close Friday).
    if today_et.weekday() >= 5:
        finished = True
    elif today_et.weekday() == 4:
        close_hm = (13, 15) if today_et.isoformat() in EARLY_CLOSES else (16, 15)
        finished = (now_et.hour, now_et.minute) >= close_hm
    else:
        finished = False
    doc = dict(old)
    if last_mon == cur_mon:
        if candle == last and old.get('lastSession') == last_bar.isoformat():
            print(f'{sym}: current week unchanged — file unchanged')
            return 'unchanged', False
        doc['weeks'] = weeks[:-1] + [candle]
        action = 'refreshed'
    else:
        if last_mon + dt.timedelta(days=7) != cur_mon:
            print(f'{sym}: WARNING gap — last shipped week {last_mon}, current week {cur_mon}; appending current week only, past weeks untouched')
        doc['weeks'] = weeks + [candle]
        action = 'appended'
    doc['asOf'] = last_bar.isoformat()
    doc['asOfLabel'] = SW.dlabel(last_bar)
    doc['lastSession'] = last_bar.isoformat()
    if finished:
        doc['inProgress'] = None
        tail = f'Latest week is a final close through {SW.dlabel(last_bar)}.'
    elif session_open(now_et):
        # The session is open: today's close is an in-progress print, not
        # a completed session — say so, and never say "completed" here.
        doc['inProgress'] = f'in progress, as of {et_label(now_et)} (session open), week not finished'
        tail = f'Latest week is in progress as of {SW.dlabel(last_bar)}, {now_et.strftime("%-I:%M %p ET")}; its close is not a final close.'
    else:
        doc['inProgress'] = f'in progress, through last completed session {SW.dlabel(last_bar)} — week not finished'
        tail = f'Latest week is in progress as of {SW.dlabel(last_bar)}, {now_et.strftime("%-I:%M %p ET")}; its close is not a final close.'
    doc['note'] = refresh_note(old.get('note', ''), tail, _STOCK_TAIL)
    if check_only:
        print(f'{sym}: would {action} current week to {candle}')
        return action, True
    SW.write_doc(path, doc)
    print(f'{sym}: {action} current week -> {path}')
    return action, True

def refresh_indicator(key, out_dir, now, fixture_bars, check_only):
    """Returns (status, changed). Same contract as refresh_stock."""
    now_et = SW.parse_now(now)
    path = os.path.join(out_dir, IW.FILES[key])
    try:
        old = json.load(open(path))
    except Exception as e:
        raise RuntimeError(f'{key}: cannot load {path} ({type(e).__name__}: {e})')
    weeks = old.get('weeks') or []
    if not weeks:
        raise RuntimeError(f'{key}: shipped file has no weeks — refusing to build from scratch')
    today_utc = now_et.astimezone(UTC).date()
    cur_mon = SW.week_monday(today_utc)
    last = weeks[-1]
    last_mon = dt.date.fromisoformat(last['monday'])
    if last_mon > cur_mon:
        print(f'{key}: shipped file is ahead of the current week ({last_mon} > {cur_mon}) — skipping')
        return 'skipped', False
    # If the last shipped week is a past week that was still in progress,
    # finalise it before appending — otherwise its stale in-progress
    # values would freeze as a final week. Fetch from its Monday so its
    # bars are in the payload too.
    finalize_last = last_mon < cur_mon and bool(old.get('inProgress'))
    fetch_since = last_mon if finalize_last else cur_mon
    if fixture_bars is not None:
        bars, vols = fixture_bars
    else:
        ysym = IW.SPECS[key][0]
        payload = fetch_yahoo_payload(ysym, fetch_since)
        try:
            bars = IW.bars_from_payload(key, payload)
        except RuntimeError as e:
            # A null row for TODAY before the first trade is "no bar yet",
            # not a failure. Any other null row still fails closed.
            if f'null OHLC on {today_utc.isoformat()}' in str(e):
                print(f'{key}: no bar for today yet — file unchanged')
                return 'skipped', False
            raise
        vols = volumes_from_payload(payload, UTC)
    old_volume = last.get('volume') if last_mon == cur_mon else None
    candle = candle_for_week(bars, cur_mon, vols, old_volume)
    if candle is None:
        print(f'{key}: no bars for the current week yet — file unchanged')
        return 'skipped', False
    bad = validate_candle(candle)
    if bad:
        print(f'{key}: recomputed candle invalid ({ "; ".join(bad) }) — keeping last good file', file=sys.stderr)
        return 'failed', False
    # Finalise the previous in-progress week before appending; if it
    # cannot be finalised, do NOT append — the file stays as-is and the
    # next 15-min tick retries.
    if finalize_last:
        prev = candle_for_week(bars, last_mon, vols, last.get('volume'))
        prev_bad = validate_candle(prev)
        if prev is None or prev_bad:
            why = 'no bars' if prev is None else '; '.join(prev_bad)
            print(f'{key}: cannot finalise previous week {last_mon} ({why}) — keeping last good file, not appending', file=sys.stderr)
            return 'failed', False
        if prev['days'] < last['days']:
            print(f'{key}: re-fetched previous week {last_mon} has fewer days ({prev["days"]}) than shipped ({last["days"]}) — keeping last good file, not appending', file=sys.stderr)
            return 'failed', False
        weeks = weeks[:-1] + [prev]
        print(f'{key}: finalised previous week {last_mon} (close {prev["close"]}, {prev["days"]} days) before appending')
    asof_label = et_label(now_et)
    finished = today_utc >= cur_mon + dt.timedelta(days=6)
    doc = dict(old)
    if last_mon == cur_mon:
        # No write when the candle is unchanged: asOf is the time the
        # candle was last (re)computed, not a heartbeat — otherwise
        # every 15-minute run would commit a file whose candle never moved.
        if candle == last:
            print(f'{key}: current week unchanged — file unchanged')
            return 'unchanged', False
        doc['weeks'] = weeks[:-1] + [candle]
        action = 'refreshed'
    else:
        if last_mon + dt.timedelta(days=7) != cur_mon:
            print(f'{key}: WARNING gap — last shipped week {last_mon}, current week {cur_mon}; appending current week only, past weeks untouched')
        doc['weeks'] = weeks + [candle]
        action = 'appended'
    doc['asOf'] = asof_label
    if finished:
        doc['inProgress'] = None
        tail = f'Latest week ({candle["label"]}) is a final close as of {asof_label}.'
    else:
        doc['inProgress'] = f'in progress, as of {asof_label}'
        tail = f'Latest week ({candle["label"]}) refreshed in progress as of {asof_label}; its close is not a final close.'
    doc['note'] = refresh_note(old.get('note', ''), tail, _IND_TAIL)
    if check_only:
        print(f'{key}: would {action} current week to {candle}')
        return action, True
    with open(path + '.tmp', 'w') as f:
        json.dump(doc, f, indent=2)
        f.write('\n')
    os.replace(path + '.tmp', path)
    print(f'{key}: {action} current week -> {path}')
    return action, True

# --- CLI ---

def load_fixture(path):
    """Fixture -> {(kind, sym): ('ok', bars, vols) | ('error', message)}.

    A bad fixture entry for one symbol is a per-symbol failure (fail
    closed, keep its last good file), never a load-time abort: an empty
    bars list or a null/inconsistent row must behave exactly like the
    same bad data arriving from Yahoo.
    """
    try:
        fx = json.load(open(path))
    except Exception as e:
        raise RuntimeError(f'fixture unreadable: {type(e).__name__}: {e}')
    out = {}
    def _add(kind, sym, rows, nd):
        try:
            out[(kind, sym)] = ('ok',) + bars_from_fixture_rows(sym, rows, nd)
        except Exception as e:
            out[(kind, sym)] = ('error', str(e))
    for sym, rows in (fx.get('stocks') or {}).items():
        _add('stock', sym, rows, 2)
    for sym, rows in (fx.get('symbols') or {}).items():  # stock_weekly fixture shape
        if ('stock', sym) not in out:
            _add('stock', sym, rows, 2)
    for key, rows in (fx.get('indicators') or {}).items():
        if key not in IW.SPECS:
            raise RuntimeError(f'fixture has unknown indicator {key}')
        _add('indicator', key, rows, IW.SPECS[key][1])
    return fx, out

def main(argv):
    out_dir, now, check_only, only, fixture, gate = 'assets/data', None, False, None, None, False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--out-dir':
            out_dir = argv[i + 1]; i += 2
        elif a == '--now':
            now = argv[i + 1]; i += 2
        elif a == '--symbol':
            only = argv[i + 1]; i += 2
        elif a == '--check-only':
            check_only = True; i += 1
        elif a == '--fixture':
            fixture = argv[i + 1]; i += 2
        elif a == '--gate':
            gate = True; i += 1
        else:
            print(f'unknown arg {a}', file=sys.stderr); return 2
    if gate:
        try:
            inside, reason = in_window(SW.parse_now(now))
        except Exception as e:
            # Cannot determine ET time (tzdata missing, bad --now): fail safe
            # — skip the run, do not fetch. The workflow treats run=0 as a
            # clean skip, so this never pages anyone at 3 a.m.
            print('run=0')
            print(f'desk-intraday gate: cannot determine ET time ({type(e).__name__}: {e}) — skipping run')
            return 0
        print(f'run={"1" if inside else "0"}')
        print(f'desk-intraday gate: {reason} ({"inside" if inside else "outside"} window)')
        return 0
    if only and only not in STOCK_SYMS and only not in INDICATOR_KEYS:
        print(f'unknown symbol {only}', file=sys.stderr); return 2
    if not tz_healthy():
        # Belt and braces: the workflow's gate step already skips when the
        # zone is bad, but a direct invocation must fail safe too — never
        # fetch (and so never mis-assign a week) with untrusted ET times.
        print('desk-intraday: America/New_York time zone data unavailable or stale — skipping run (fail safe, no fetch)', file=sys.stderr)
        return 0
    fx = fx_bars = None
    if fixture:
        try:
            fx, fx_bars = load_fixture(fixture)
        except Exception as e:
            print(str(e), file=sys.stderr); return 1
        if now is None:
            now = fx.get('now')
    targets = []
    if only:
        targets = [('stock', only)] if only in STOCK_SYMS else [('indicator', only)]
    else:
        targets = [('stock', s) for s in STOCK_SYMS] + [('indicator', k) for k in INDICATOR_KEYS]
    failed = skipped = changed = 0
    failed_names = []
    critical = []
    consecutive_429 = 0
    aborted_429 = False
    never_tried = []
    for idx, (kind, sym) in enumerate(targets):
        try:
            fb = fx_bars.get((kind, sym)) if fx_bars is not None else None
            if fx_bars is not None and fb is None:
                # A fixture only covers the symbols it lists; the rest are
                # not attempted (a test artifact, not a Yahoo failure), so
                # they count as skipped and never touch the failure
                # threshold. A fixture skip is not a fetch, so it neither
                # breaks nor continues a 429 streak.
                print(f'{sym}: not in fixture — skipping (not attempted)')
                skipped += 1
                continue
            if fb is not None and fb[0] == 'error':
                print(f'{sym}: bad fixture data ({fb[1]}) — keeping last good file', file=sys.stderr)
                failed += 1
                failed_names.append(sym)
                consecutive_429 = 0
                continue
            fixture_bars = fb[1:] if fb is not None else None
            if kind == 'stock':
                status, did = refresh_stock(sym, out_dir, now, fixture_bars, check_only)
            else:
                status, did = refresh_indicator(sym, out_dir, now, fixture_bars, check_only)
            # A completed refresh (any outcome) breaks a 429 streak: only
            # consecutive failed *fetches* count toward the abort.
            consecutive_429 = 0
            if status == 'failed':
                failed += 1
                failed_names.append(sym)
            elif status == 'skipped':
                skipped += 1
            elif did:
                changed += 1
        except YahooRateLimited as e:
            # A single 429 fails closed for that symbol only (keep its last
            # good file, warn, carry on). Two in a row means Yahoo is
            # throttling us, so stop the run instead of hammering it: the
            # symbols already refreshed stay refreshed, the rest keep their
            # last good files, and the run fails so it surfaces.
            consecutive_429 += 1
            failed += 1
            failed_names.append(sym)
            print(f'{sym}: Yahoo rate-limited (HTTP 429) — keeping last good file', file=sys.stderr)
            if consecutive_429 >= 2:
                never_tried = [s for _, s in targets[idx + 1:]]
                never = f' Never tried: {", ".join(never_tried)}.' if never_tried else ''
                print(f'desk-intraday: ABORTING — two Yahoo 429s in a row ({", ".join(failed_names[-2:])}); '
                      f'stopping the run instead of hammering Yahoo. Last good files kept.{never}', file=sys.stderr)
                aborted_429 = True
                break
        except Exception as e:
            consecutive_429 = 0
            print(f'{sym}: FAILED: {e}', file=sys.stderr)
            if 'cannot load' in str(e) or 'no weeks' in str(e):
                critical.append(str(e))
            failed += 1
            failed_names.append(sym)
    attempted = len(targets)
    print(f'desk-intraday: {changed} changed, {skipped} skipped, {failed} failed of {attempted}'
          + (' (check-only, nothing written)' if check_only else f' -> {out_dir}'))
    if failed_names:
        # Name the stale symbols, both as a GitHub Actions annotation and
        # as a plain log line — a run must never pass quietly with part of
        # the Desk stale and nobody able to see which part. The ::warning::
        # goes on stdout so it is picked up as an annotation.
        stale = ', '.join(failed_names)
        print(f'::warning::desk-intraday: {len(failed_names)} symbol(s) failed and kept their last good file (stale): {stale}')
        print(f'desk-intraday: stale symbols (kept last good file): {stale}', file=sys.stderr)
    if aborted_429:
        print('desk-intraday: run aborted on consecutive Yahoo 429s — no further symbols fetched', file=sys.stderr)
        if never_tried:
            print(f'desk-intraday: never tried after the abort: {", ".join(never_tried)}', file=sys.stderr)
        return 1
    if critical:
        print('desk-intraday: critical failure — ' + '; '.join(critical), file=sys.stderr)
        return 1
    if attempted and failed == attempted:
        print('desk-intraday: every symbol failed — keeping all last good files', file=sys.stderr)
        return 1
    if failed > MAX_SYMBOL_FAILURES:
        print(f'desk-intraday: {failed} symbols failed (more than {MAX_SYMBOL_FAILURES} allowed) — failing the run', file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
