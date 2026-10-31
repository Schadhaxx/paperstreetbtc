#!/usr/bin/env python3
"""Weekly OHLC candles for the Maple Leaf screener stock cards.

Writes one file per symbol: assets/data/stock-weekly-<SYM>.json
(TSLA, PLTR, MSTR, IBIT, MU, META, SPCX).

Source: Yahoo chart API, unadjusted daily OHLC (quote open/high/low/close,
never adjclose). Weeks are Monday-Sunday on the calendar date of each
session in America/New_York. YTD names start at the 2 Jan 2026 session
(week of Mon 29 Dec 2025, one trading day). The 31 Dec 2025 close is the
baseline, not a candle. SPCX starts at its first session (12 Jun 2026);
the baseline is that session's close, not an IPO print.

Fails loud. A missing session, a bad OHLC print, a Yahoo error, or a
baseline that disagrees with the pack by more than one cent aborts with
exit 1 and does not write a file. Candles are never invented, never
interpolated, and a failed run never exits 0 while leaving stale data
looking fresh.

usage:
  python3 tools/stock_weekly.py [--out-dir assets/data] [--pack assets/data/screener-pack.json]
  python3 tools/stock_weekly.py --fixture bars.json --pack pack.json --out-dir DIR [--now ISO]
  python3 tools/stock_weekly.py --check-only [--out-dir assets/data] [--pack assets/data/screener-pack.json]
"""
import json, math, os, sys, time, datetime as dt, urllib.request
from zoneinfo import ZoneInfo

NY = ZoneInfo('America/New_York')
# NYSE full closures. A weekday that is not in this set and has no Yahoo
# bar is a hard error (the script will not skip it or invent a candle).
HOLIDAYS = {
    '2026-01-01', '2026-01-19', '2026-02-16', '2026-04-03', '2026-05-25',
    '2026-06-19', '2026-07-03', '2026-09-07', '2026-11-26', '2026-12-25',
    '2027-01-01', '2027-01-18', '2027-02-15', '2027-03-26', '2027-05-31',
    '2027-06-18', '2027-07-05', '2027-09-06', '2027-11-25', '2027-12-24',
    '2028-01-17', '2028-02-21', '2028-04-14', '2028-05-29', '2028-06-19',
    '2028-07-04', '2028-09-04', '2028-11-23', '2028-12-25',
}
# Session is final only at/after 16:15 ET, so a 4:00 p.m. print that Yahoo
# has not settled yet is not shipped as a completed close.
FINAL_HM = (16, 15)
MN = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
SYMS = ['TSLA', 'PLTR', 'MSTR', 'IBIT', 'MU', 'META', 'SPCX']
SPECS = {
    'TSLA': {'basis': 'ytd', 'base_session': '2025-12-31', 'first_session': '2026-01-02', 'base_label': '31 Dec close'},
    'PLTR': {'basis': 'ytd', 'base_session': '2025-12-31', 'first_session': '2026-01-02', 'base_label': '31 Dec close'},
    'MSTR': {'basis': 'ytd', 'base_session': '2025-12-31', 'first_session': '2026-01-02', 'base_label': '31 Dec close'},
    'IBIT': {'basis': 'ytd', 'base_session': '2025-12-31', 'first_session': '2026-01-02', 'base_label': '31 Dec close'},
    'MU': {'basis': 'ytd', 'base_session': '2025-12-31', 'first_session': '2026-01-02', 'base_label': '31 Dec close'},
    'META': {'basis': 'ytd', 'base_session': '2025-12-31', 'first_session': '2026-01-02', 'base_label': '31 Dec close'},
    'SPCX': {'basis': 'listing', 'base_session': '2026-06-12', 'first_session': '2026-06-12', 'base_label': 'Listing close'},
}

def cents(x):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(float(x)):
        raise ValueError(f'bad price {x!r}')
    return float(format(float(x), '.2f'))

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

def remaining_in_week(last_session, now):
    sun = week_monday(last_session) + dt.timedelta(days=6)
    d, rem = last_session + dt.timedelta(days=1), []
    while d <= sun:
        if is_session_day(d) and not session_complete(d, now):
            rem.append(d)
        d += dt.timedelta(days=1)
    return rem

def _check_raw(sym, day, o, h, l, c):
    for name, v in (('open', o), ('high', h), ('low', l), ('close', c)):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
            raise RuntimeError(f'{sym}: bad {name} {v!r} on {day}')
    if h < max(o, c) - 1e-6 or l > min(o, c) + 1e-6 or l > h:
        raise RuntimeError(f'{sym}: OHLC inconsistent on {day}: o={o} h={h} l={l} c={c}')

def bar_from_raw(sym, day, o, h, l, c):
    _check_raw(sym, day, o, h, l, c)
    b = {'open': cents(o), 'high': cents(h), 'low': cents(l), 'close': cents(c)}
    # Rounding to the cent can nudge high/low by a cent. Pull them back
    # out only when the unrounded bar already satisfied the inequality.
    b['high'] = max(b['high'], b['open'], b['close'])
    b['low'] = min(b['low'], b['open'], b['close'])
    return b

def bars_from_yahoo_payload(sym, payload):
    """Pure parser. `payload` is the chart.result[0] object. Dates are ET."""
    res_meta = payload.get('meta') or {}
    cur = res_meta.get('currency')
    if cur not in (None, 'USD'):
        raise RuntimeError(f'{sym}: currency {cur!r} is not USD')
    try:
        q = payload['indicators']['quote'][0]
        ts = payload['timestamp']
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f'{sym}: Yahoo payload missing OHLC ({type(e).__name__})')
    if 'adjclose' in (payload.get('indicators') or {}):
        pass  # present, deliberately unused
    out = {}
    for t, o, h, l, c in zip(ts, q['open'], q['high'], q['low'], q['close']):
        if t is None or any(v is None for v in (o, h, l, c)):
            day = dt.datetime.fromtimestamp(t, NY).date().isoformat() if t else '?'
            raise RuntimeError(f'{sym}: null OHLC on {day} — refusing to skip or fill')
        day = dt.datetime.fromtimestamp(int(t), NY).date()
        if day in out:
            raise RuntimeError(f'{sym}: duplicate bar {day}')
        out[day] = bar_from_raw(sym, day, float(o), float(h), float(l), float(c))
    if not out:
        raise RuntimeError(f'{sym}: Yahoo returned no daily bars')
    return out

def fetch_yahoo(sym, since):
    p1 = int(dt.datetime(since.year, since.month, since.day, tzinfo=dt.timezone.utc).timestamp()) - 5 * 86400
    p2 = int(time.time()) + 2 * 86400
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={p1}&period2={p2}&interval=1d'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 paperstreet-stock-weekly'})
    try:
        with urllib.request.urlopen(req, timeout=30) as f:
            j = json.load(f)
    except Exception as e:
        raise RuntimeError(f'{sym}: Yahoo fetch failed ({type(e).__name__}: {e})')
    err = (j.get('chart') or {}).get('error')
    res = (j.get('chart') or {}).get('result') or []
    if not res:
        raise RuntimeError(f'{sym}: Yahoo returned no result ({err})')
    return bars_from_yahoo_payload(sym, res[0])

def bars_from_fixture_rows(sym, rows):
    out = {}
    for row in rows:
        day = dt.date.fromisoformat(row['date'])
        if day in out:
            raise RuntimeError(f'{sym}: duplicate fixture bar {day}')
        out[day] = bar_from_raw(sym, day, row['open'], row['high'], row['low'], row['close'])
    return out

def build_doc(sym, bars, now, pack_row):
    spec = SPECS[sym]
    now = parse_now(now)
    cutoff = cutoff_date(now)
    first = dt.date.fromisoformat(spec['first_session'])
    base_day = dt.date.fromisoformat(spec['base_session'])
    if base_day not in bars:
        raise RuntimeError(f'{sym}: missing baseline session {base_day} — not writing')
    if first > cutoff:
        raise RuntimeError(f'{sym}: no completed session yet (first {first}, cutoff {cutoff})')
    missing = [d.isoformat() for d in expected_sessions(first, cutoff) if d not in bars]
    if missing:
        sample = ', '.join(missing[:12])
        more = '' if len(missing) <= 12 else f' (+{len(missing) - 12} more)'
        raise RuntimeError(f'{sym}: missing {len(missing)} completed session(s): {sample}{more} — not writing')
    base_close = bars[base_day]['close']
    pack_base = pack_row.get('baseClose')
    if not isinstance(pack_base, (int, float)) or isinstance(pack_base, bool):
        raise RuntimeError(f'{sym}: pack baseClose missing')
    if abs(base_close - float(pack_base)) > 0.01:
        raise RuntimeError(f'{sym}: baseline {base_day} close {base_close} != pack baseClose {pack_base} — not writing')
    groups = {}
    for d in sorted(bars):
        if first <= d <= cutoff:
            groups.setdefault(week_monday(d), []).append(d)
    start_mon, end_mon = week_monday(first), week_monday(cutoff)
    weeks, cur = [], start_mon
    while cur <= end_mon:
        ds = groups.get(cur)
        if not ds:
            raise RuntimeError(f'{sym}: empty week of {cur} — not writing')
        rows = [bars[d] for d in ds]
        o, c = rows[0]['open'], rows[-1]['close']
        h, l = max(r['high'] for r in rows), min(r['low'] for r in rows)
        h, l = max(h, o, c), min(l, o, c)
        sun = cur + dt.timedelta(days=6)
        weeks.append({
            'monday': cur.isoformat(),
            'sunday': sun.isoformat(),
            'label': f'{dlabel(cur)} \u2013 {dlabel(sun)}',
            'days': len(ds),
            'open': o, 'high': h, 'low': l, 'close': c,
        })
        cur += dt.timedelta(days=7)
    rem = remaining_in_week(cutoff, now)
    in_progress = None
    if rem:
        in_progress = f'in progress, through last completed session {dlabel(cutoff)} — week not finished'
    if spec['basis'] == 'listing':
        head = ('Weekly candles since listing, UTC Monday-Sunday weeks. '
                'First week is partial: 1 trading day (12 Jun 2026), week starting Mon 8 Jun 2026. '
                'Nothing before listing is included. The baseline is the first trading close, not an IPO print. '
                'The first candle open is the first trade and is not that baseline.')
    else:
        head = ('Weekly candles, UTC Monday-Sunday weeks, YTD 2026. '
                'First week is partial: 1 trading day (2 Jan 2026), week starting Mon 29 Dec 2025. '
                'The 31 Dec 2025 close is the baseline, not a candle.')
    tail = (f' Latest week is in progress as of {dlabel(cutoff)}.' if in_progress
            else f' Latest week is a final close through {dlabel(cutoff)}.')
    return {
        'source': f'Yahoo {sym} unadjusted daily OHLC',
        'asOf': cutoff.isoformat(),
        'asOfLabel': dlabel(cutoff),
        'unit': 'usd',
        'basis': spec['basis'],
        'baseClose': base_close,
        'baseSession': base_day.isoformat(),
        'baseLabel': spec['base_label'],
        'lastSession': cutoff.isoformat(),
        'inProgress': in_progress,
        'note': head + tail + ' Dated snapshot shipped with the screener — not a live quote.',
        'weeks': weeks,
    }

def validate_doc(doc, pack_row):
    """Structural checks. Returns a list of error strings (empty == ok)."""
    bad = []
    sym = (doc.get('source') or '').split(' ')
    sym = sym[1] if len(sym) > 1 else '?'
    def err(m):
        bad.append(f'{sym}: {m}')
    if doc.get('unit') != 'usd':
        err(f'unit {doc.get("unit")!r}')
    basis = doc.get('basis')
    if basis not in ('ytd', 'listing'):
        err(f'basis {basis!r}')
    weeks = doc.get('weeks')
    if not isinstance(weeks, list) or not weeks:
        err('no weeks'); return bad
    prev = None
    for i, w in enumerate(weeks):
        try:
            mon = dt.date.fromisoformat(w['monday'])
            sun = dt.date.fromisoformat(w['sunday'])
        except Exception:
            err(f'week {i} bad dates'); continue
        if mon.weekday() != 0:
            err(f'{w["monday"]} is not a Monday')
        if sun != mon + dt.timedelta(days=6) or sun.weekday() != 6:
            err(f'{w["monday"]} sunday {w.get("sunday")} is not +6')
        if prev is not None and mon != prev + dt.timedelta(days=7):
            err(f'{w["monday"]} is not contiguous (previous {prev})')
        if prev is not None and mon <= prev:
            err(f'{w["monday"]} not ascending')
        prev = mon
        for k in ('open', 'high', 'low', 'close'):
            v = w.get(k)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                err(f'{w["monday"]} bad {k}')
                v = None
        if all(isinstance(w.get(k), (int, float)) and not isinstance(w.get(k), bool) for k in ('open', 'high', 'low', 'close')):
            if w['high'] < max(w['open'], w['close']) or w['low'] > min(w['open'], w['close']) or w['low'] > w['high']:
                err(f'{w["monday"]} OHLC invariant failed')
        if not isinstance(w.get('days'), int) or isinstance(w.get('days'), bool) or w['days'] < 1:
            err(f'{w["monday"]} bad days')
        expect = f'{dlabel(mon)} \u2013 {dlabel(sun)}'
        if w.get('label') != expect:
            err(f'{w["monday"]} label {w.get("label")!r} != {expect!r}')
    if basis == 'ytd':
        if weeks[0]['monday'] != '2025-12-29' or weeks[0].get('days') != 1:
            err(f'YTD first week {weeks[0].get("monday")} days {weeks[0].get("days")} (want 2025-12-29 x1)')
        if doc.get('baseSession') != '2025-12-31':
            err(f'baseSession {doc.get("baseSession")}')
    if basis == 'listing':
        if weeks[0]['monday'] != '2026-06-08' or weeks[0].get('days') != 1:
            err(f'listing first week {weeks[0].get("monday")} days {weeks[0].get("days")} (want 2026-06-08 x1)')
        if doc.get('baseSession') != '2026-06-12':
            err(f'baseSession {doc.get("baseSession")}')
        if any(w['monday'] < '2026-06-08' for w in weeks):
            err('candle before listing')
        if abs(weeks[0]['close'] - doc.get('baseClose', 0)) > 0.01:
            err('first candle close is not the listing-close baseline')
    pb = pack_row.get('baseClose') if pack_row else None
    if isinstance(pb, (int, float)) and not isinstance(pb, bool):
        if abs(doc.get('baseClose', 0) - float(pb)) > 0.01:
            err(f'baseClose {doc.get("baseClose")} != pack {pb}')
    else:
        err('pack baseClose missing')
    last = weeks[-1]['close']
    if doc.get('lastSession') != doc.get('asOf'):
        err('lastSession != asOf')
    if pack_row and doc.get('asOf') == (pack_row.get('_packAsOf')):
        price = pack_row.get('price')
        if isinstance(price, (int, float)) and not isinstance(price, bool) and abs(last - float(price)) > 0.01:
            err(f'last close {last} != pack price {price} on shared asOf {doc.get("asOf")}')
    if doc.get('inProgress') not in (None,) and not (isinstance(doc.get('inProgress'), str) and doc['inProgress'].strip()):
        err('inProgress must be null or a non-empty string')
    return bad

def load_pack(path):
    pack = json.load(open(path))
    rows = {}
    for r in pack.get('rows') or []:
        rows[r['symbol']] = dict(r)
        rows[r['symbol']]['_packAsOf'] = pack.get('asOf')
    return pack, rows

def write_doc(path, doc):
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(doc, f, indent=2)
        f.write('\n')
    os.replace(tmp, path)

def main(argv):
    out_dir, pack_path, fixture, now, check_only, only = 'assets/data', 'assets/data/screener-pack.json', None, None, False, None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--out-dir':
            out_dir = argv[i + 1]; i += 2
        elif a == '--pack':
            pack_path = argv[i + 1]; i += 2
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
    try:
        pack, rows = load_pack(pack_path)
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
    if only:
        syms = [only]
    elif fx is not None and fx.get('symbols'):
        syms = [s for s in SYMS if s in fx['symbols']]
        if not syms:
            print('fixture has none of the screener symbols', file=sys.stderr); return 1
    else:
        syms = list(SYMS)
    for s in syms:
        if s not in SPECS:
            print(f'unknown symbol {s}', file=sys.stderr); return 2
        if s not in rows:
            print(f'{s}: not in pack — refusing', file=sys.stderr); return 1
    if check_only:
        bad = []
        for s in syms:
            path = os.path.join(out_dir, f'stock-weekly-{s}.json')
            try:
                doc = json.load(open(path))
            except Exception as e:
                bad.append(f'{s}: cannot read {path} ({type(e).__name__})'); continue
            bad.extend(validate_doc(doc, rows[s]))
        for b in bad:
            print('BAD', b)
        print('stock-weekly', 'OK' if not bad else 'INVALID', len(syms), 'files')
        return 1 if bad else 0
    docs = {}
    for s in syms:
        try:
            if fx is not None:
                if s not in fx.get('symbols', {}):
                    raise RuntimeError(f'{s}: missing from fixture')
                bars = bars_from_fixture_rows(s, fx['symbols'][s])
            else:
                since = dt.date.fromisoformat(SPECS[s]['base_session'])
                bars = fetch_yahoo(s, since)
            docs[s] = build_doc(s, bars, now, rows[s])
            bad = validate_doc(docs[s], rows[s])
            if bad:
                raise RuntimeError('; '.join(bad))
        except Exception as e:
            print(f'FAILED {s}: {e}', file=sys.stderr)
            print('stock-weekly: no files written', file=sys.stderr)
            return 1
    os.makedirs(out_dir, exist_ok=True)
    for s, doc in docs.items():
        path = os.path.join(out_dir, f'stock-weekly-{s}.json')
        write_doc(path, doc)
        last = doc['weeks'][-1]['close']
        flag = ' IN PROGRESS' if doc['inProgress'] else ''
        print(f'{s} weeks={len(doc["weeks"])} sessions_end={doc["asOf"]} base={doc["baseClose"]} last={last}{flag}')
        prow = rows[s]
        if doc['asOf'] != prow.get('_packAsOf'):
            print(f'  NOTE {s}: chart close {last} as of {doc["asOf"]} vs pack price {prow.get("price")} as of {prow.get("_packAsOf")} (dates differ; not an error)')
    print('stock-weekly wrote', len(docs), 'file(s) ->', out_dir)
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
