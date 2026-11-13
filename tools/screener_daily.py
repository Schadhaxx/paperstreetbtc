#!/usr/bin/env python3
"""Daily closes for the Maple Leaf screener weekly candle modal's
Bollinger Weekly/Daily switch.

Writes one file per symbol: assets/data/stock-daily-<SYM>.json
(TSLA, PLTR, MSTR, IBIT, MU, META, SPCX, plus the nine Desk stocks
added 9 Nov 2026: BRK.B, AAPL, AMZN, MSFT, NFLX, SPOT, XYZ, GOOGL,
NVDA) and assets/data/ind-daily-{wti,gold,us10y,vix,dia}.json
(WTI = CL=F, GOLD = GC=F, US10Y = ^TNX, VIX = ^VIX, DIA = DIA, the
SPDR Dow Jones Industrial Average ETF that replaced the DJIA index
tile on 13 Nov 2026).
BRK.B is fetched as Yahoo BRK-B (hyphen), same map as
tools/stock_weekly.py; a raw BRK.B request would 404. New indicators
(QQQ, USDCAD, DXY) are not included — their Desk charts have
dailyUrl: null.
(The ind-daily- prefix avoids colliding with the Compare daily files
gold-daily.json and mstr-daily.json, which are different data.)

Source: Yahoo chart API, unadjusted daily closes (quote close, never
adjclose) — the same bars the weekly tools aggregate, so a daily close
on a week's last session equals that week's close in the shipped weekly
file. The JS uses these for the DAILY Bollinger: for each week, SMA
+/- 2 sigma from the 20 daily closes ending on that week's last
session. Only the close is shipped (Bollinger needs closes only).

Stocks use NYSE sessions (Mon-Fri ex holidays, America/New_York dates,
final only at/after 16:15 ET) — the same calendar as
tools/stock_weekly.py. Indicators use UTC calendar dates and skip
null-OHLC bars on weekends/holidays, as tools/indicator_weekly.py does.
An indicator bar counts as final only once its session is over: a bar
dated before today (ET) is final; today's bar (ET) is final at/after
18:00 ET (after the 17:00 ET CME close of CL=F/GC=F, the 16:15 ET VIX
close and the US10Y close); a bar dated after today (ET) never is.
Yahoo publishes the in-progress bar from the early session on, so
without this rule every recap run rewrote today's moving price.

Consistency: every daily close on a week's last session is checked
against the shipped weekly file's close for that week, except the
current in-progress week. Desk-intraday snapshots in the weekly file
legitimately differ from the official daily close until the weekly
file catches up (typically by the next week). The last session of a
completed week is capped at the weekly file's asOf, because the
weekly file may not yet include a newer session the daily file has.
- Stocks: a mismatch over one cent on a completed week is a hard
  error for that stock only (the weekly file is rebuilt from the same
  Yahoo bars, so they must agree). Other symbols are still written.
  The run exits 1 if any symbol failed.
- Indicators: a mismatch is REPORTED, not fatal — the shipped weekly
  files preserve two flagged values pending Grok Bot + Chief of Staff
  review (gold's 30 Oct close $3,901.20, an intraday pull; WTI's 26 Oct
  week close $104.24, an intraday snapshot), and the indicator weekly
  files' latest-week close is an intraday snapshot (refreshed ~3:40 PM
  ET), so the daily final close for that session is expected to differ.
  The note lists each mismatch. Three VIX weeks (2 Feb, 15 Jun, 29 Jun
  2026) also differ — pre-existing shipped-value discrepancies, reported.

Fails loud per symbol. A missing completed session, a bad close, a
Yahoo error, or a stock weekly-consistency failure on a completed
week skips that symbol and still writes the rest; the run exits 1 if
any symbol failed. Closes are never invented, never interpolated, and
a failed run never exits 0 while leaving stale data looking fresh. A
daily file with fewer than 20 closes is still written (it grows
daily); the JS draws no bands until 20 daily closes are available.

Refresh route: the recap job in .github/workflows/prices.yml runs this
tool on final closes (continue-on-error, never blocks recap or prices)
and commits any changed stock-daily-*.json / ind-daily-*.json files.
The weekly tools are still refreshed separately (Chief's job and
desk-intraday). See proposals/daily-bollinger-prices-note.md for the
original wiring note; the file list here now includes the nine new
Desk stocks.

usage:
  python3 tools/screener_daily.py [--out-dir assets/data] [--weekly-dir assets/data]
  python3 tools/screener_daily.py --symbol TSLA [--out-dir DIR]
  python3 tools/screener_daily.py --fixture bars.json [--out-dir DIR] [--now ISO]
  python3 tools/screener_daily.py --check-only [--out-dir assets/data] [--weekly-dir assets/data]
"""
import json, math, os, sys, time, datetime as dt, urllib.request
from zoneinfo import ZoneInfo

NY = ZoneInfo('America/New_York')
UTC = dt.timezone.utc
ET = ZoneInfo('America/New_York')
MN = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
# NYSE full closures — the SAME set as tools/stock_weekly.py. Keep in sync.
HOLIDAYS = {
    '2026-01-01', '2026-01-19', '2026-02-16', '2026-04-03', '2026-05-25',
    '2026-06-19', '2026-07-03', '2026-09-07', '2026-11-26', '2026-12-25',
    '2027-01-01', '2027-01-18', '2027-02-15', '2027-03-26', '2027-05-31',
    '2027-06-18', '2027-07-05', '2027-09-06', '2027-11-25', '2027-12-24',
    '2028-01-17', '2028-02-21', '2028-04-14', '2028-05-29', '2028-06-19',
    '2028-07-04', '2028-09-04', '2028-11-23', '2028-12-25',
}
# Null-OHLC days Yahoo inserts for indicator holidays/weekends (UTC dates).
IND_HOLIDAYS = {
    '2025-12-25', '2026-01-01', '2026-01-19', '2026-02-16', '2026-04-03',
    '2026-05-25', '2026-06-19', '2026-07-03', '2026-09-07', '2026-11-26', '2026-12-25',
}
FINAL_HM = (16, 15)
IND_FINAL_HM = (18, 0)   # indicators: today's bar (ET) is final at/after 18:00 ET

# key -> (yahoo symbol, decimals, unit, basis, first session, output file)
STOCKS = {
    'TSLA': ('TSLA', 2, 'usd', 'ytd', '2026-01-02', 'stock-daily-TSLA.json'),
    'PLTR': ('PLTR', 2, 'usd', 'ytd', '2026-01-02', 'stock-daily-PLTR.json'),
    'MSTR': ('MSTR', 2, 'usd', 'ytd', '2026-01-02', 'stock-daily-MSTR.json'),
    'IBIT': ('IBIT', 2, 'usd', 'ytd', '2026-01-02', 'stock-daily-IBIT.json'),
    'MU':   ('MU', 2, 'usd', 'ytd', '2026-01-02', 'stock-daily-MU.json'),
    'META': ('META', 2, 'usd', 'ytd', '2026-01-02', 'stock-daily-META.json'),
    'SPCX': ('SPCX', 2, 'usd', 'listing', '2026-06-12', 'stock-daily-SPCX.json'),
    # New Desk stocks (9 Nov 2026). BRK.B's Yahoo symbol is BRK-B
    # (hyphen), same as tools/stock_weekly.py YAHOO_MAP; a raw 'BRK.B'
    # fetch would 404. The other eight are 1:1 with their tickers.
    'BRK.B': ('BRK-B', 2, 'usd', 'ytd', '2026-01-02', 'stock-daily-BRK.B.json'),
    'AAPL': ('AAPL', 2, 'usd', 'ytd', '2026-01-02', 'stock-daily-AAPL.json'),
    'AMZN': ('AMZN', 2, 'usd', 'ytd', '2026-01-02', 'stock-daily-AMZN.json'),
    'MSFT': ('MSFT', 2, 'usd', 'ytd', '2026-01-02', 'stock-daily-MSFT.json'),
    'NFLX': ('NFLX', 2, 'usd', 'ytd', '2026-01-02', 'stock-daily-NFLX.json'),
    'SPOT': ('SPOT', 2, 'usd', 'ytd', '2026-01-02', 'stock-daily-SPOT.json'),
    'XYZ':  ('XYZ', 2, 'usd', 'ytd', '2026-01-02', 'stock-daily-XYZ.json'),
    'GOOGL': ('GOOGL', 2, 'usd', 'ytd', '2026-01-02', 'stock-daily-GOOGL.json'),
    'NVDA': ('NVDA', 2, 'usd', 'ytd', '2026-01-02', 'stock-daily-NVDA.json'),
}
INDICATORS = {
    'WTI':   ('CL%3DF', 2, 'usd', 'ytd', '2026-01-02', 'ind-daily-wti.json'),
    'GOLD':  ('GC%3DF', 2, 'usd', 'ytd', '2026-01-02', 'ind-daily-gold.json'),
    'US10Y': ('%5ETNX', 3, 'pct', 'ytd', '2026-01-02', 'ind-daily-us10y.json'),
    'VIX':   ('%5EVIX', 2, 'pts', 'ytd', '2026-01-02', 'ind-daily-vix.json'),
    'DIA':   ('DIA', 2, 'usd', 'ytd', '2026-01-02', 'ind-daily-dia.json'),
}
WEEKLY_FILES = {
    'TSLA': 'stock-weekly-TSLA.json', 'PLTR': 'stock-weekly-PLTR.json',
    'MSTR': 'stock-weekly-MSTR.json', 'IBIT': 'stock-weekly-IBIT.json',
    'MU': 'stock-weekly-MU.json', 'META': 'stock-weekly-META.json',
    'SPCX': 'stock-weekly-SPCX.json',
    'BRK.B': 'stock-weekly-BRK.B.json', 'AAPL': 'stock-weekly-AAPL.json',
    'AMZN': 'stock-weekly-AMZN.json', 'MSFT': 'stock-weekly-MSFT.json',
    'NFLX': 'stock-weekly-NFLX.json', 'SPOT': 'stock-weekly-SPOT.json',
    'XYZ': 'stock-weekly-XYZ.json', 'GOOGL': 'stock-weekly-GOOGL.json',
    'NVDA': 'stock-weekly-NVDA.json',
    'WTI': 'wti-weekly.json', 'GOLD': 'gold-weekly.json',
    'US10Y': 'us10y-weekly.json', 'VIX': 'vix-weekly.json',
    'DIA': 'dia-weekly.json',
}
ALL = {**STOCKS, **INDICATORS}


def rnd(x, nd):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(float(x)):
        raise ValueError(f'bad close {x!r}')
    return float(format(float(x), f'.{nd}f'))


def dlabel(d):
    return f'{d.day} {MN[d.month - 1]} {d.year}'


def parse_now(now):
    if now is None:
        return dt.datetime.now(NY)
    if isinstance(now, dt.datetime):
        return now.astimezone(NY) if now.tzinfo else now.replace(tzinfo=NY)
    parsed = dt.datetime.fromisoformat(now)
    return parsed.astimezone(NY) if parsed.tzinfo else parsed.replace(tzinfo=NY)


def week_monday(d):
    return d - dt.timedelta(days=d.weekday())


def is_session_day(d):
    return d.weekday() < 5 and d.isoformat() not in HOLIDAYS


def session_complete(day, now):
    if day < now.date():
        return True
    if day > now.date():
        return False
    return (now.hour, now.minute) >= FINAL_HM


def cutoff_date(now):
    d = now.date()
    if is_session_day(d) and not session_complete(d, now):
        d -= dt.timedelta(days=1)
    while not is_session_day(d):
        d -= dt.timedelta(days=1)
    return d


def expected_sessions(first, last):
    d, out = first, []
    while d <= last:
        if is_session_day(d):
            out.append(d)
        d += dt.timedelta(days=1)
    return out


def fetch_yahoo(ysym):
    p1 = int(dt.datetime(2025, 12, 20, tzinfo=UTC).timestamp())
    p2 = int(time.time()) + 2 * 86400
    url = (f'https://query1.finance.yahoo.com/v8/finance/chart/{ysym}'
           f'?period1={p1}&period2={p2}&interval=1d')
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 paperstreet-screener-daily'})
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


def closes_from_payload(key, payload, is_stock):
    """Pure parser. Returns {date: close}. Dates are ET (stocks) or UTC (indicators)."""
    ysym, nd, unit, basis, first, _ = ALL[key]
    try:
        q = payload['indicators']['quote'][0]
        ts = payload['timestamp']
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f'{key}: Yahoo payload missing closes ({type(e).__name__})')
    tz = NY if is_stock else UTC
    out = {}
    for t, c in zip(ts, q['close']):
        if t is None:
            raise RuntimeError(f'{key}: null timestamp — refusing to skip')
        day = dt.datetime.fromtimestamp(int(t), tz).date()
        if c is None:
            # Indicators: Yahoo inserts null-OHLC rows for market holidays
            # and weekends. Those are not trading days and are skipped; a
            # null close on any other day is a hard failure.
            if is_stock:
                raise RuntimeError(f'{key}: null close on {day} — refusing to skip or fill')
            if day.weekday() >= 5 or day.isoformat() in IND_HOLIDAYS:
                continue
            raise RuntimeError(f'{key}: null close on {day} — refusing to skip or fill')
        if day in out:
            raise RuntimeError(f'{key}: duplicate bar {day}')
        if isinstance(c, bool) or not isinstance(c, (int, float)) or not math.isfinite(c) or c <= 0:
            raise RuntimeError(f'{key}: bad close {c!r} on {day}')
        out[day] = rnd(c, nd)
    if not out:
        raise RuntimeError(f'{key}: Yahoo returned no daily closes')
    return out


def closes_from_fixture_rows(key, rows):
    ysym, nd, unit, basis, first, _ = ALL[key]
    out = {}
    for row in rows:
        day = dt.date.fromisoformat(row['date'])
        if day in out:
            raise RuntimeError(f'{key}: duplicate fixture bar {day}')
        out[day] = rnd(row['close'], nd)
    return out


def build_doc(key, closes, now, weekly_weeks, weekly_asof=None):
    """Build the daily file doc. `weekly_weeks` is the shipped weekly file's
    weeks list (for the consistency check). `weekly_asof` is the weekly
    file's asOf (last completed session it covers); the consistency check
    caps each week's last session at that date, because the weekly file's
    in-progress close is a snapshot as of its asOf while the daily file
    may already include a newer session. Returns (doc, mismatches)."""
    ysym, nd, unit, basis, first_s, fname = ALL[key]
    is_stock = key in STOCKS
    now = parse_now(now)
    first = dt.date.fromisoformat(first_s)
    if is_stock:
        cutoff = cutoff_date(now)
        if first > cutoff:
            raise RuntimeError(f'{key}: no completed session yet (first {first}, cutoff {cutoff})')
        missing = [d.isoformat() for d in expected_sessions(first, cutoff) if d not in closes]
        if missing:
            sample = ', '.join(missing[:12])
            more = '' if len(missing) <= 12 else f' (+{len(missing) - 12} more)'
            raise RuntimeError(f'{key}: missing {len(missing)} completed session(s): {sample}{more} — not writing')
        asof = cutoff
    else:
        # Indicators: last FINAL bar. A bar dated before today (ET) is
        # final; today's bar only at/after IND_FINAL_HM ET; a later-dated
        # bar never. (Yahoo serves today's in-progress bar all session.)
        # No session calendar is enforced (they trade nearly every day);
        # a bar older than 10 days is stale and refuses.
        today = now.date()
        done_today = (now.hour, now.minute) >= IND_FINAL_HM
        dated = sorted(d for d in closes if d < today or (d == today and done_today))
        if not dated:
            raise RuntimeError(f'{key}: no final daily bar on or before {today}')
        asof = dated[-1]
        if (today - asof).days > 10:
            raise RuntimeError(f'{key}: last daily bar {asof} is {(today - asof).days} days old — stale, not writing')
    days = [{'date': d.isoformat(), 'close': closes[d]} for d in sorted(closes) if first <= d <= asof]
    if not days:
        raise RuntimeError(f'{key}: no daily closes in range — not writing')
    # Consistency: the daily close on each completed week's last session
    # must equal the shipped weekly close for that week (same Yahoo
    # bars). The current in-progress week is skipped: desk-intraday
    # snapshots legitimately differ from the official daily close until
    # the weekly file catches up. The last session of a completed week
    # is capped at the weekly file's asOf, in case the daily file already
    # includes a newer session. Stocks: hard error for that symbol only.
    # Indicators: reported (two flagged shipped values are expected to
    # differ — see module docstring).
    mismatches = []
    cap = None
    if weekly_asof:
        try:
            cap = dt.date.fromisoformat(weekly_asof)
        except Exception:
            try:
                # Indicator weekly files store asOf as "5 Nov 2026, 4:15 PM ET".
                cap = dt.datetime.strptime(weekly_asof, '%d %b %Y, %I:%M %p ET').date()
            except Exception:
                cap = None
    today = now.date()
    for w in weekly_weeks or []:
        try:
            sun = dt.date.fromisoformat(w['sunday'])
            mon = dt.date.fromisoformat(w['monday'])
        except Exception:
            continue
        # Still inside this Mon-Sun week in ET: skip. A mid-session
        # desk-intraday close on the same calendar day as the official
        # daily bar would otherwise fail the check (and, before
        # per-symbol writes, abort the whole run).
        if today <= sun:
            continue
        hi = sun if cap is None else min(sun, cap)
        in_week = [d for d in closes if mon <= d <= hi]
        if not in_week:
            continue
        last_day = max(in_week)
        dc = closes[last_day]
        wc = w.get('close')
        if not isinstance(wc, (int, float)) or isinstance(wc, bool):
            continue
        if abs(dc - float(wc)) > 0.01:
            mismatches.append(
                f"week of {w['monday']}: daily close {dc} on {last_day} != weekly close {wc}")
    if mismatches and is_stock:
        raise RuntimeError(f'{key}: weekly-consistency failure: ' + '; '.join(mismatches))
    if basis == 'listing':
        head = ('Daily closes since listing. YTD names start at the first '
                'session (12 Jun 2026); nothing before listing is included.')
    else:
        head = ('Daily closes, YTD 2026. First session 2 Jan 2026. '
                'Unadjusted Yahoo closes, ET dates for stocks, UTC dates for indicators.')
    tail = f' Latest completed session {dlabel(asof)}.'
    if mismatches:
        tail += (' Weekly-consistency notes (daily close differs from the '
                 'shipped weekly close — preserved shipped value, pending review): '
                 + '; '.join(mismatches) + '.')
    return {
        'source': f'Yahoo {ysym} unadjusted daily closes',
        'asOf': asof.isoformat(),
        'asOfLabel': dlabel(asof),
        'unit': unit,
        'basis': basis,
        'firstSession': first_s,
        'note': head + tail + ' Dated snapshot shipped with the screener — not a live quote.',
        'days': days,
    }, mismatches


def load_weekly(weekly_dir, key):
    path = os.path.join(weekly_dir, WEEKLY_FILES[key])
    try:
        with open(path) as f:
            doc = json.load(f)
    except Exception as e:
        raise RuntimeError(f'{key}: cannot read weekly file {path} ({type(e).__name__}: {e})')
    weeks = doc.get('weeks')
    if not isinstance(weeks, list) or not weeks:
        raise RuntimeError(f'{key}: weekly file {path} has no weeks')
    return weeks, doc.get('asOf')


def write_doc(path, doc):
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(doc, f, indent=2)
        f.write('\n')
    os.replace(tmp, path)


def main(argv):
    out_dir, weekly_dir, fixture, now, check_only, only = 'assets/data', 'assets/data', None, None, False, None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--out-dir':
            out_dir = argv[i + 1]; i += 2
        elif a == '--weekly-dir':
            weekly_dir = argv[i + 1]; i += 2
        elif a == '--fixture':
            fixture = argv[i + 1]; i += 2
        elif a == '--now':
            now = argv[i + 1]; i += 2
        elif a == '--symbol':
            only = argv[i + 1]; i += 2
        elif a == '--check-only':
            check_only = True; i += 1
        else:
            print(f'unknown arg {a}', file=sys.stderr); return 2
    if only and only not in ALL:
        print(f'unknown symbol {only}', file=sys.stderr); return 2
    fx = None
    if fixture:
        try:
            fx = json.load(open(fixture))
        except Exception as e:
            print(f'fixture unreadable: {type(e).__name__}: {e}', file=sys.stderr); return 1
        if now is None:
            now = fx.get('now')
    if only:
        keys = [only]
    elif fx is not None and fx.get('symbols'):
        keys = [k for k in ALL if k in fx['symbols']]
        if not keys:
            print('fixture has none of the screener symbols', file=sys.stderr); return 1
    else:
        keys = list(ALL)
    if check_only:
        bad = []
        for k in keys:
            path = os.path.join(out_dir, ALL[k][5])
            try:
                with open(path) as f:
                    doc = json.load(f)
            except Exception as e:
                bad.append(f'{k}: cannot read {path} ({type(e).__name__})'); continue
            days = doc.get('days')
            if not isinstance(days, list) or not days:
                bad.append(f'{k}: no daily closes'); continue
            prev = None
            for row in days:
                try:
                    d = dt.date.fromisoformat(row['date'])
                except Exception:
                    bad.append(f'{k}: bad date {row.get("date")!r}'); break
                if prev is not None and d <= prev:
                    bad.append(f'{k}: dates not ascending at {row["date"]}'); break
                prev = d
                c = row.get('close')
                if isinstance(c, bool) or not isinstance(c, (int, float)) or not math.isfinite(c) or c <= 0:
                    bad.append(f'{k}: bad close {c!r} on {row["date"]}'); break
            try:
                weeks, wasof = load_weekly(weekly_dir, k)
                _, mism = build_doc(k, {dt.date.fromisoformat(r['date']): r['close'] for r in days}, now, weeks, wasof)
                if mism and k in STOCKS:
                    bad.append(f'{k}: weekly-consistency failure: ' + '; '.join(mism))
                elif mism:
                    print(f'NOTE {k}: weekly-consistency notes (reported, not fatal): ' + '; '.join(mism))
            except Exception as e:
                bad.append(f'{k}: consistency check failed: {e}')
        for b in bad:
            print('BAD', b)
        print('screener-daily', 'OK' if not bad else 'INVALID', len(keys), 'files')
        return 1 if bad else 0
    docs = {}
    failed = []
    for k in keys:
        try:
            weeks, wasof = load_weekly(weekly_dir, k)
            if fx is not None:
                if k not in fx.get('symbols', {}):
                    raise RuntimeError(f'{k}: missing from fixture')
                closes = closes_from_fixture_rows(k, fx['symbols'][k])
            else:
                payload = fetch_yahoo(ALL[k][0])
                closes = closes_from_payload(k, payload, k in STOCKS)
            docs[k], mism = build_doc(k, closes, now, weeks, wasof)
            if mism:
                print(f'NOTE {k}: weekly-consistency notes (reported, not fatal): ' + '; '.join(mism))
        except Exception as e:
            print(f'FAILED {k}: {e}', file=sys.stderr)
            failed.append(k)
    os.makedirs(out_dir, exist_ok=True)
    for k, doc in docs.items():
        path = os.path.join(out_dir, ALL[k][5])
        write_doc(path, doc)
        print(f'{k} days={len(doc["days"])} asOf={doc["asOf"]} first={doc["days"][0]["date"]} last={doc["days"][-1]["close"]}')
    print('screener-daily wrote', len(docs), 'file(s) ->', out_dir)
    if failed:
        print('screener-daily: skipped ' + ', '.join(failed) + f' ({len(failed)} failed, {len(docs)} written)', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
