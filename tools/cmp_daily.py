#!/usr/bin/env python3
"""Daily closes for the Maple Leaf comparison chart.

Writes one combined file, assets/data/cmp-daily.json: the seven screener
stocks plus three optional benchmarks (SPY, QQQ, BTC-USD).

Source: Yahoo chart API, unadjusted close (quote.close, never adjclose).
Equity and ETF dates are the America/New_York session date. BTC-USD dates
are the UTC day, because that is how the crypto daily bar is stamped.
YTD names keep the 31 Dec 2025 close as baseClose and start the series on
the next session. SPCX starts on its first session (12 Jun 2026); that
close is the baseline, not an IPO print.

Fails loud. A missing session, a null close, a Yahoo error, or a stock
baseline that disagrees with the pack by more than one cent aborts with
exit 1 and does not write. Closes are never invented or interpolated.

usage:
  python3 tools/cmp_daily.py [--out assets/data/cmp-daily.json] [--pack assets/data/screener-pack.json]
  python3 tools/cmp_daily.py --fixture bars.json --pack pack.json --out FILE [--now ISO]
  python3 tools/cmp_daily.py --check-only [--out assets/data/cmp-daily.json] [--pack ...] [--weekly-dir assets/data]
"""
import json, math, os, sys, time, datetime as dt, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stock_weekly as sw

# kind stock|benchmark, calendar nyse|utc, basis ytd|listing.
SPECS = {
    'TSLA': {'kind': 'stock', 'yahoo': 'TSLA', 'calendar': 'nyse', 'basis': 'ytd', 'base': '2025-12-31', 'first': '2026-01-02'},
    'PLTR': {'kind': 'stock', 'yahoo': 'PLTR', 'calendar': 'nyse', 'basis': 'ytd', 'base': '2025-12-31', 'first': '2026-01-02'},
    'MSTR': {'kind': 'stock', 'yahoo': 'MSTR', 'calendar': 'nyse', 'basis': 'ytd', 'base': '2025-12-31', 'first': '2026-01-02'},
    'IBIT': {'kind': 'stock', 'yahoo': 'IBIT', 'calendar': 'nyse', 'basis': 'ytd', 'base': '2025-12-31', 'first': '2026-01-02'},
    'MU':   {'kind': 'stock', 'yahoo': 'MU',   'calendar': 'nyse', 'basis': 'ytd', 'base': '2025-12-31', 'first': '2026-01-02'},
    'META': {'kind': 'stock', 'yahoo': 'META', 'calendar': 'nyse', 'basis': 'ytd', 'base': '2025-12-31', 'first': '2026-01-02'},
    'SPCX': {'kind': 'stock', 'yahoo': 'SPCX', 'calendar': 'nyse', 'basis': 'listing', 'base': '2026-06-12', 'first': '2026-06-12'},
    'SPY':  {'kind': 'benchmark', 'yahoo': 'SPY', 'calendar': 'nyse', 'basis': 'ytd', 'base': '2025-12-31', 'first': '2026-01-02'},
    'QQQ':  {'kind': 'benchmark', 'yahoo': 'QQQ', 'calendar': 'nyse', 'basis': 'ytd', 'base': '2025-12-31', 'first': '2026-01-02'},
    'BTC':  {'kind': 'benchmark', 'yahoo': 'BTC-USD', 'calendar': 'utc', 'basis': 'ytd', 'base': '2025-12-31', 'first': '2026-01-01'},
}
ORDER = ['TSLA', 'PLTR', 'MSTR', 'IBIT', 'MU', 'META', 'SPCX', 'SPY', 'QQQ', 'BTC']


def closes_from_pairs(sym, pairs, calendar):
    """pairs: iterable of (unix_seconds, close). Dates follow `calendar`."""
    out = {}
    for t, c in pairs:
        if t is None or c is None:
            raise RuntimeError(f'{sym}: null close — refusing to skip or fill')
        if isinstance(c, bool) or not isinstance(c, (int, float)) or not math.isfinite(float(c)) or float(c) <= 0:
            raise RuntimeError(f'{sym}: bad close {c!r}')
        if calendar == 'utc':
            day = dt.datetime.fromtimestamp(int(t), dt.timezone.utc).date()
        else:
            day = dt.datetime.fromtimestamp(int(t), sw.NY).date()
        if day in out:
            raise RuntimeError(f'{sym}: duplicate close {day}')
        out[day] = sw.cents(c)
    if not out:
        raise RuntimeError(f'{sym}: no closes')
    return out


def closes_from_yahoo_payload(sym, payload, calendar):
    meta = payload.get('meta') or {}
    cur = meta.get('currency')
    if cur not in (None, 'USD'):
        raise RuntimeError(f'{sym}: currency {cur!r} is not USD')
    try:
        q = payload['indicators']['quote'][0]
        ts = payload['timestamp']
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f'{sym}: Yahoo payload missing closes ({type(e).__name__})')
    return closes_from_pairs(sym, zip(ts, q.get('close') or []), calendar)


def fetch_yahoo(spec):
    sym = spec['yahoo']
    since = dt.date.fromisoformat(spec['base'])
    p1 = int(dt.datetime(since.year, since.month, since.day, tzinfo=dt.timezone.utc).timestamp()) - 5 * 86400
    p2 = int(time.time()) + 2 * 86400
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={p1}&period2={p2}&interval=1d'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 paperstreet-cmp-daily'})
    try:
        with urllib.request.urlopen(req, timeout=30) as f:
            body = json.load(f)
    except Exception as e:
        raise RuntimeError(f'{sym}: Yahoo fetch failed ({type(e).__name__}: {e})')
    err = (body.get('chart') or {}).get('error')
    res = (body.get('chart') or {}).get('result') or []
    if not res:
        raise RuntimeError(f'{sym}: Yahoo returned no result ({err})')
    return closes_from_yahoo_payload(spec['yahoo'], res[0], spec['calendar'])


def closes_from_fixture(sym, rows, calendar):
    pairs = []
    for row in rows:
        day = dt.date.fromisoformat(row['date'])
        # Stamp noon UTC / noon ET so the calendar split is unambiguous.
        if calendar == 'utc':
            stamp = int(dt.datetime(day.year, day.month, day.day, 12, tzinfo=dt.timezone.utc).timestamp())
        else:
            stamp = int(dt.datetime(day.year, day.month, day.day, 12, tzinfo=sw.NY).timestamp())
        pairs.append((stamp, row['close']))
    return closes_from_pairs(sym, pairs, calendar)


def expected_days(spec, first, last):
    if spec['calendar'] == 'utc':
        d, out = first, []
        while d <= last:
            out.append(d)
            d += dt.timedelta(days=1)
        return out
    return sw.expected_sessions(first, last)


def build_symbol(sym, closes, now, pack_row):
    spec = SPECS[sym]
    now = sw.parse_now(now)
    cutoff = sw.cutoff_date(now) if spec['calendar'] == 'nyse' else _utc_cutoff(now)
    first = dt.date.fromisoformat(spec['first'])
    base_day = dt.date.fromisoformat(spec['base'])
    if base_day not in closes:
        raise RuntimeError(f'{sym}: missing baseline session {base_day} — not writing')
    if first > cutoff:
        raise RuntimeError(f'{sym}: no completed session yet (first {first}, cutoff {cutoff})')
    missing = [d.isoformat() for d in expected_days(spec, first, cutoff) if d not in closes]
    if missing:
        sample = ', '.join(missing[:12])
        more = '' if len(missing) <= 12 else f' (+{len(missing) - 12} more)'
        raise RuntimeError(f'{sym}: missing {len(missing)} session(s): {sample}{more} — not writing')
    base_close = closes[base_day]
    if pack_row is not None:
        pack_base = pack_row.get('baseClose')
        if not isinstance(pack_base, (int, float)) or isinstance(pack_base, bool):
            raise RuntimeError(f'{sym}: pack baseClose missing')
        if abs(base_close - float(pack_base)) > 0.01:
            raise RuntimeError(f'{sym}: baseline {base_day} close {base_close} != pack baseClose {pack_base} — not writing')
    dates, vals = [], []
    for d in sorted(closes):
        if first <= d <= cutoff:
            dates.append(d.isoformat())
            vals.append(closes[d])
    if not dates:
        raise RuntimeError(f'{sym}: empty series')
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise RuntimeError(f'{sym}: dates not strictly ascending')
    return {
        'kind': spec['kind'],
        'yahoo': spec['yahoo'],
        'calendar': spec['calendar'],
        'basis': spec['basis'],
        'baseDate': spec['base'],
        'baseClose': base_close,
        'firstSession': spec['first'],
        'dates': dates,
        'closes': vals,
    }


def _utc_cutoff(now):
    """Last completed UTC day. A calendar day is final at 00:15 UTC the next day."""
    now = sw.parse_now(now).astimezone(dt.timezone.utc)
    day = now.date()
    if (now.hour, now.minute) < (0, 15):
        day -= dt.timedelta(days=1)
    day -= dt.timedelta(days=1)
    return day


def build_doc(symbols, now):
    now = sw.parse_now(now)
    # asOf is the equity cutoff (what the page labels). BTC may end the same UTC day.
    as_of = sw.cutoff_date(now)
    return {
        'source': 'Yahoo chart API unadjusted daily close',
        'asOf': as_of.isoformat(),
        'asOfLabel': sw.dlabel(as_of),
        'unit': 'usd',
        'note': 'Dated snapshot of daily closes. Not a live quote.',
        'symbols': symbols,
    }


def validate_doc(doc, pack_rows, weekly_dir=None, require_all=False):
    bad = []
    if doc.get('unit') != 'usd':
        bad.append(f'unit {doc.get("unit")!r}')
    if not doc.get('asOf') or not doc.get('asOfLabel'):
        bad.append('missing asOf')
    symbols = doc.get('symbols')
    if not isinstance(symbols, dict) or not symbols:
        return bad + ['no symbols']
    for sym in ORDER:
        if sym not in symbols:
            if require_all and SPECS[sym]['kind'] == 'stock':
                bad.append(f'{sym}: missing')
            continue
        s = symbols[sym]
        spec = SPECS[sym]
        dates, closes = s.get('dates') or [], s.get('closes') or []
        if len(dates) != len(closes) or len(dates) < 2:
            bad.append(f'{sym}: dates/closes length'); continue
        if dates != sorted(set(dates)):
            bad.append(f'{sym}: dates not strictly ascending unique')
        if s.get('basis') != spec['basis'] or s.get('baseDate') != spec['base'] or s.get('firstSession') != spec['first']:
            bad.append(f'{sym}: basis/base/first mismatch {s.get("basis")} {s.get("baseDate")} {s.get("firstSession")}')
        if s.get('kind') != spec['kind']:
            bad.append(f'{sym}: kind {s.get("kind")}')
        try:
            first = dt.date.fromisoformat(dates[0])
            last = dt.date.fromisoformat(dates[-1])
            want_first = dt.date.fromisoformat(spec['first'])
        except Exception:
            bad.append(f'{sym}: bad date'); continue
        if first != want_first:
            bad.append(f'{sym}: first date {dates[0]} != {spec["first"]}')
        if last.isoformat() != doc.get('asOf') and spec['calendar'] == 'nyse':
            bad.append(f'{sym}: last {dates[-1]} != asOf {doc.get("asOf")}')
        for c in closes:
            if isinstance(c, bool) or not isinstance(c, (int, float)) or not math.isfinite(c) or c <= 0:
                bad.append(f'{sym}: bad close {c!r}'); break
        # Gap check against the calendar between first and last.
        have = set(dates)
        end = last
        missing = [d.isoformat() for d in expected_days(spec, want_first, end) if d.isoformat() not in have]
        if missing:
            bad.append(f'{sym}: gap {missing[:6]}')
        base = s.get('baseClose')
        if not isinstance(base, (int, float)) or isinstance(base, bool):
            bad.append(f'{sym}: bad baseClose')
        elif spec['basis'] == 'listing' and abs(closes[0] - float(base)) > 0.01:
            bad.append(f'{sym}: first close {closes[0]} != listing base {base}')
        if sym in (pack_rows or {}):
            pb = pack_rows[sym].get('baseClose')
            if isinstance(pb, (int, float)) and not isinstance(pb, bool) and isinstance(base, (int, float)) and abs(float(base) - float(pb)) > 0.01:
                bad.append(f'{sym}: baseClose {base} != pack {pb}')
        if weekly_dir and spec['kind'] == 'stock':
            path = os.path.join(weekly_dir, f'stock-weekly-{sym}.json')
            if os.path.exists(path):
                try:
                    w = json.load(open(path))
                    wlast = w['weeks'][-1]['close']
                    if abs(closes[-1] - float(wlast)) > 0.01:
                        bad.append(f'{sym}: daily last {closes[-1]} != weekly last {wlast}')
                except Exception as e:
                    bad.append(f'{sym}: weekly unreadable ({type(e).__name__})')
    return bad


def write_doc(path, doc):
    tmp = path + '.tmp'
    os.makedirs(os.path.dirname(os.path.abspath(path)) or '.', exist_ok=True)
    with open(tmp, 'w') as f:
        json.dump(doc, f, indent=2)
        f.write('\n')
    os.replace(tmp, path)


def main(argv):
    out, pack_path, fixture, now, check_only, weekly_dir = (
        'assets/data/cmp-daily.json', 'assets/data/screener-pack.json', None, None, False, 'assets/data')
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--out':
            out = argv[i + 1]; i += 2
        elif a == '--pack':
            pack_path = argv[i + 1]; i += 2
        elif a == '--fixture':
            fixture = argv[i + 1]; i += 2
        elif a == '--now':
            now = argv[i + 1]; i += 2
        elif a == '--weekly-dir':
            weekly_dir = argv[i + 1]; i += 2
        elif a == '--check-only':
            check_only = True; i += 1
        else:
            print(f'unknown arg {a}', file=sys.stderr); return 2
    try:
        pack, rows = sw.load_pack(pack_path)
    except Exception as e:
        print(f'pack unreadable: {type(e).__name__}: {e}', file=sys.stderr); return 1
    fx = None
    if fixture:
        try:
            fx = json.load(open(fixture))
        except Exception as e:
            print(f'fixture unreadable: {type(e).__name__}: {e}', file=sys.stderr); return 1
        if now is None:
            now = fx.get('now')
    if check_only:
        try:
            doc = json.load(open(out))
        except Exception as e:
            print(f'cannot read {out}: {type(e).__name__}: {e}', file=sys.stderr); return 1
        bad = validate_doc(doc, rows, weekly_dir, require_all=True)
        for b in bad:
            print('BAD', b)
        print('cmp-daily', 'OK' if not bad else 'INVALID', out)
        return 1 if bad else 0
    want = [s for s in ORDER if (fx is None or s in (fx.get('symbols') or {}))]
    if not want:
        print('fixture has no symbols', file=sys.stderr); return 1
    built = {}
    for sym in want:
        spec = SPECS[sym]
        pack_row = rows.get(sym) if spec['kind'] == 'stock' else None
        if spec['kind'] == 'stock' and pack_row is None:
            print(f'{sym}: not in pack — refusing', file=sys.stderr)
            print('cmp-daily: no file written', file=sys.stderr)
            return 1
        try:
            if fx is not None:
                closes = closes_from_fixture(sym, fx['symbols'][sym], spec['calendar'])
            else:
                closes = fetch_yahoo(spec)
            built[sym] = build_symbol(sym, closes, now, pack_row)
        except Exception as e:
            print(f'FAILED {sym}: {e}', file=sys.stderr)
            print('cmp-daily: no file written', file=sys.stderr)
            return 1
    doc = build_doc(built, now)
    # NYSE names must share the equity cutoff. A benchmark may end on asOf
    # or, for BTC, on the UTC cutoff, which can be the next calendar day.
    for sym, s in built.items():
        if SPECS[sym]['calendar'] == 'nyse' and s['dates'][-1] != doc['asOf']:
            print(f'FAILED {sym}: last {s["dates"][-1]} != asOf {doc["asOf"]}', file=sys.stderr)
            print('cmp-daily: no file written', file=sys.stderr)
            return 1
    bad = validate_doc(doc, rows, None if fx is not None else weekly_dir)
    if bad:
        print('FAILED validation: ' + '; '.join(bad), file=sys.stderr)
        print('cmp-daily: no file written', file=sys.stderr)
        return 1
    write_doc(out, doc)
    for sym in want:
        s = built[sym]
        print(f'{sym} days={len(s["dates"])} {s["dates"][0]}..{s["dates"][-1]} base={s["baseClose"]} last={s["closes"][-1]}')
    print('cmp-daily wrote', out)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
