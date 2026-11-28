#!/usr/bin/env python3
"""Compare intraday (TA Drawing Fixes Job 10): publish today's 15-minute
bars for the three 1D compare assets (^GSPC, GC=F, MSTR) as
cmp-intraday.json on the `data` branch, every 15 minutes while NYSE is
open. Run by the `cmp-intraday` job in
.github/workflows/cmp-intraday.yml — never by hand on main.

Why this file exists: a 1D compare needs a *series* — Gold, MSTR and
S&P 500 values at many points through the trading day — and the site's
compare series were daily closes only (spx-daily.json, gold-daily.json,
mstr-daily.json), so one value per day could not draw a day (Job 10
diagnosis). The client (btcchart-panel.js, 1D Line only) loads this file,
aligns the three series to BTC's 15-minute points, trims BTC to
9:30 AM-4 PM ET, and rebases everything to 100 at the window open —
TradingView's session-toggle model.

Yahoo fetch (verified 22 Nov 2026, from the sandbox): `range=2d` +
`interval=15m` for all three symbols. `range=1d` returns NO bars for
GC=F at all (a futures symbol — its session is not the NYSE session),
while `range=2d` returns the latest session cleanly: ^GSPC and MSTR
27 bars, 0 nulls, 9:30 AM-4 PM ET; GC=F 69 bars over its full futures
day (midnight-5 PM ET), 0 nulls in the NYSE window — its null bars are
all at 10-10:45 PM ET, the futures maintenance break, outside the
window, and its last bar (9:59:57 PM UTC) falls after the 4 PM close
so the window filter drops it. The tool therefore fetches 2d and
filters to the latest session date in the 9:30 AM-4 PM ET window.
GLD (the gold ETF) returns the exact NYSE-session shape too, but the
site's gold source is GC=F (gold-daily.json), so GC=F stays primary;
GLD is the documented fallback if GC=F intraday ever fails.

Fails closed per symbol. A Yahoo error, empty bars, a null bar inside
the window, or an inconsistent bar keeps that symbol out of the file
(status "failed", named) and the other symbols still publish. The run
FAILS (exit 1) if every symbol fails, if two Yahoo 429s arrive in a
row, or if the document fails validation. A single HTTP 429 fails
closed for that symbol only; two consecutive 429s abort the run
instead of hammering Yahoo. A transient failure (HTTP 429, HTTP 5xx,
network error or timeout) is retried once, after ~10 s.

The market-hours gate lives here too (--gate): the workflow's first
step asks this tool whether now (America/New_York) is inside a NYSE
session, so the cron alone is never trusted. Window: Mon-Fri
9:30 AM-4:15 PM ET (the 4:15 tick picks up the 4:00 PM bar, which
closes at 4:15); on an early-close day 9:30 AM-1:15 PM ET. Holidays
and early closes are the shared lists in stock_weekly / desk_intraday
(2026-2028). If the America/New_York zone data is missing or stale
the gate skips the run — it never fetches with untrusted ET times.

The stale rule (settled in the build; the client enforces it too):
the file is valid for its `session` date. While that session is open
(9:30 AM-4 PM ET) it is fresh only while `asOf` is under 30 minutes
old (the job ticks every 15 min, so 30 min is one missed tick plus
margin). After the close the file is final for the day and stays valid
until midnight ET. Before the open, and on weekends, the file is the
LAST session (labelled as such) while `asOf` is under 4 days old — a
Friday file on Monday morning is 3 days old; older than 4 days means
the job is broken, so the client treats it as stale and the toggles
stay off.

usage:
  python3 tools/cmp_intraday.py --out cmp-intraday.json [--now ISO]
  python3 tools/cmp_intraday.py --out cmp-intraday.json --check-only [--now ISO]
  python3 tools/cmp_intraday.py --out cmp-intraday.json --fixture bars.json [--now ISO]
  python3 tools/cmp_intraday.py --gate   # prints run=1|0 for the workflow
  python3 tools/cmp_intraday.py --validate cmp-intraday.json

--fixture PATH (offline tests): a JSON document in Yahoo-payload shape,
{"now": ISO, "symbols": {"SPX": {"timestamp": [...], "quote": {"open":
[...], "high": [...], "low": [...], "close": [...]}}, ...}}. A bad
fixture entry for one symbol is a per-symbol failure (fail closed),
never a load-time abort.

CMP_SCHEMA (v1). One object; keys:
  v            1
  kind         "cmp-intraday"
  asOf         ISO UTC time the file was built, e.g. "2026-11-20T21:15:00Z"
  asOfLabel    same instant in ET, e.g. "20 Nov 2026, 4:15 PM ET"
  session      ISO date (ET) of the session the bars belong to, e.g. "2026-11-20"
  sessionOpen  true while the NYSE session is open
  symbols      {"SPX": {"bars": [[t_ms, o, h, l, c], ...]},
                "GOLD": {"bars": [...]},
                "MSTR": {"bars": [...]}} — a failed symbol is
                {"status": "failed"} and carries no bars.
  failed       sorted list of symbols whose entry is failed.
Bars are 15-minute opens in the 9:30 AM-4:00 PM ET window of the
session date (27 bars on a full session), t in epoch milliseconds,
OHLC rounded to 2 decimals. A consumer must ignore the file when the
stale rule above says so, and any symbol without bars.
"""
import datetime as dt, json, math, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import desk_intraday as DI
import stock_weekly as SW

try:
    NY = ZoneInfo('America/New_York')
except Exception:
    NY = None
UTC = dt.timezone.utc

# Display key -> Yahoo symbol. GOLD is the GC=F futures contract (the
# site's gold source for daily closes too); see the module docstring for
# why range=2d is used and why GLD is only a fallback.
SYMBOLS = {'SPX': '^GSPC', 'GOLD': 'GC=F', 'MSTR': 'MSTR'}

# 15-minute bar open times inside the NYSE session, minutes after midnight ET.
OPEN_MIN = 570    # 9:30 AM ET
CLOSE_MIN = 960   # 4:00 PM ET (the bar that opens at 4:00 PM is the last)
GATE_END_MIN = 975        # 4:15 PM ET — the tick that picks up the 4:00 PM bar
GATE_END_EARLY_MIN = 795  # 1:15 PM ET on an early-close day

FETCH_RETRY_BACKOFF_S = 10
CMP_VERSION = 1
CMP_KIND = 'cmp-intraday'
CMP_MAX_BYTES = 64 * 1024

YahooRateLimited = DI.YahooRateLimited


def et_label(now_et):
    return now_et.strftime('%-d %b %Y, %-I:%M %p ET')


def _et_parts(ms):
    """(ET date ISO, minutes after midnight ET) for an epoch-ms timestamp."""
    d = dt.datetime.fromtimestamp(ms / 1000.0, NY)
    return d.date().isoformat(), d.hour * 60 + d.minute


def prev_trading_day(today):
    """Most recent trading day on or before `today` (an ET date).

    A trading day is a weekday that is not an NYSE holiday.
    """
    d = today
    for _ in range(10):
        if d.weekday() < 5 and d.isoformat() not in SW.HOLIDAYS:
            return d
        d -= dt.timedelta(days=1)
    return d


def expected_session(now_et):
    """The session the latest bars should belong to, for `now_et`.

    Today's session once it is underway (at/after 9:30 AM ET on a
    trading day); otherwise the most recent trading day strictly
    before today — the normal pre-open state (no bars yet today, the
    last session is yesterday) and weekends/holidays. A fetch whose
    latest session is older than this is stale data, not a session.
    """
    now_et = now_et.astimezone(NY)
    d = now_et.date()
    mins = now_et.hour * 60 + now_et.minute
    if d.weekday() < 5 and d.isoformat() not in SW.HOLIDAYS and mins >= OPEN_MIN:
        return d
    return prev_trading_day(d - dt.timedelta(days=1))


# --- market-hours gate (pure function; the workflow's first step) ---

def in_window(now_et):
    """(inside, reason). `now_et` is an aware datetime in America/New_York."""
    if not DI.tz_healthy():
        return False, 'America/New_York time zone data unavailable or stale — skipping run'
    now_et = now_et.astimezone(NY)
    d = now_et.date()
    if d.weekday() >= 5:
        return False, f'{d.isoformat()} is a weekend'
    if d.isoformat() in SW.HOLIDAYS:
        return False, f'{d.isoformat()} is an NYSE holiday'
    mins = now_et.hour * 60 + now_et.minute
    if d.isoformat() in DI.EARLY_CLOSES:
        if OPEN_MIN <= mins <= GATE_END_EARLY_MIN:
            return True, f'{d.isoformat()} is an early-close day, inside 9:30 AM-1:15 PM ET'
        return False, f'{d.isoformat()} is an early-close day, outside 9:30 AM-1:15 PM ET'
    if OPEN_MIN <= mins <= GATE_END_MIN:
        return True, 'inside 9:30 AM-4:15 PM ET'
    return False, 'outside 9:30 AM-4:15 PM ET'


# --- Yahoo fetch (15-minute bars, range=2d) ---

def yahoo_url(ysym):
    return ('https://query1.finance.yahoo.com/v8/finance/chart/'
            + urllib.parse.quote(ysym, safe='')
            + '?range=2d&interval=15m')


def fetch_yahoo_payload(ysym):
    """Fetch one symbol's Yahoo 15-minute bars, with ONE retry on a
    transient failure (same contract as desk_intraday.fetch_yahoo_payload:
    a symbol that fails twice still raises a single exception)."""
    url = yahoo_url(ysym)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 paperstreet-cmp-intraday'})
    last_err = None
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=30) as f:
                j = json.load(f)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                last_err = YahooRateLimited(f'Yahoo rate-limited {ysym} (HTTP 429)')
            elif e.code >= 500:
                last_err = RuntimeError(f'Yahoo fetch failed (HTTPError {e.code}: {e})')
            else:
                raise RuntimeError(f'Yahoo fetch failed (HTTPError {e.code}: {e})')
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = RuntimeError(f'Yahoo fetch failed ({type(e).__name__}: {e})')
        except Exception as e:
            raise RuntimeError(f'Yahoo fetch failed ({type(e).__name__}: {e})')
        else:
            err = (j.get('chart') or {}).get('error')
            res = (j.get('chart') or {}).get('result') or []
            if not res:
                raise RuntimeError(f'Yahoo returned no result ({err})')
            return res[0]
        if attempt == 1:
            print(f'{ysym}: transient Yahoo failure ({last_err}) — retrying once after {FETCH_RETRY_BACKOFF_S}s', file=sys.stderr)
            time.sleep(FETCH_RETRY_BACKOFF_S)
    raise last_err


def _round2(v):
    return float(format(float(v), '.2f'))


def bars_from_payload(ysym, payload, now_et):
    """15-minute bars for the latest session in the NYSE window.

    Returns (session_iso, bars) where bars is a list of [t_ms, o, h, l, c]
    with t the bar open in epoch ms. Raises on a missing/empty payload,
    on a null bar inside the window, or on an inconsistent bar. A null
    bar OUTSIDE the window (GC=F's 10 PM ET maintenance break) is
    dropped with the bar, not an error. The session must be the session
    `expected_session(now_et)` returns — older bars are stale data, not
    a session (before the open that is yesterday's session, which is
    expected, not stale).
    """
    try:
        ts = payload['timestamp']
        q = payload['indicators']['quote'][0]
        opens, highs, lows, closes = q['open'], q['high'], q['low'], q['close']
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f'{ysym}: Yahoo payload has no 15-minute bars ({type(e).__name__})')
    if not ts or not (len(ts) == len(opens) == len(highs) == len(lows) == len(closes)):
        raise RuntimeError(f'{ysym}: Yahoo payload bars are missing or ragged')
    # Group window bars by ET session date; the latest date with at least
    # one bar in the window is the session.
    by_date = {}
    for t, o, h, l, c in zip(ts, opens, highs, lows, closes):
        if t is None:
            continue
        t_ms = int(t) * 1000
        d_iso, mins = _et_parts(t_ms)
        if OPEN_MIN <= mins <= CLOSE_MIN:
            by_date.setdefault(d_iso, []).append((t_ms, o, h, l, c))
    if not by_date:
        raise RuntimeError(f'{ysym}: no 15-minute bars in the 9:30 AM-4 PM ET window')
    session = max(by_date)
    expected = expected_session(now_et).isoformat()
    if session < expected:
        raise RuntimeError(f'{ysym}: latest session {session} is older than the expected session {expected} — stale data')
    bars = []
    for t_ms, o, h, l, c in sorted(by_date[session]):
        if o is None or h is None or l is None or c is None:
            raise RuntimeError(f'{ysym}: null OHLC inside the window on {session} — refusing to publish a gappy session')
        vals = [o, h, l, c]
        for name, v in zip(('open', 'high', 'low', 'close'), vals):
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
                raise RuntimeError(f'{ysym}: bad {name} {v!r} on {session}')
        o2, h2, l2, c2 = (_round2(v) for v in vals)
        if h2 < max(o2, c2) or l2 > min(o2, c2) or l2 > h2:
            raise RuntimeError(f'{ysym}: OHLC inconsistent on {session}: o={o2} h={h2} l={l2} c={c2}')
        bars.append([t_ms, o2, h2, l2, c2])
    if not bars:
        raise RuntimeError(f'{ysym}: no bars for session {session}')
    return session, bars


# --- document build + validation ---

def _finite_pos(v):
    return (not isinstance(v, bool)) and isinstance(v, (int, float)) and math.isfinite(v) and v > 0


def validate_cmp_doc(doc):
    """Error strings for a cmp-intraday document (empty == ok). Fail closed."""
    bad = []
    if not isinstance(doc, dict):
        return ['not an object']
    if doc.get('v') != CMP_VERSION:
        bad.append(f"bad v {doc.get('v')!r}")
    if doc.get('kind') != CMP_KIND:
        bad.append(f"bad kind {doc.get('kind')!r}")
    a = doc.get('asOf')
    try:
        if not (isinstance(a, str) and re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ', a)):
            raise ValueError
        dt.datetime.strptime(a, '%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        bad.append(f'bad asOf {a!r}')
    session = doc.get('session')
    try:
        dt.date.fromisoformat(session)
    except Exception:
        bad.append(f'bad session {session!r}')
        session = None
    if not isinstance(doc.get('sessionOpen'), bool):
        bad.append('bad sessionOpen')
    syms = doc.get('symbols')
    if not isinstance(syms, dict) or not syms:
        return bad + ['no symbols']
    missing = sorted(set(SYMBOLS) - set(syms))
    extra = sorted(set(syms) - set(SYMBOLS))
    if missing:
        bad.append(f'missing symbols {missing}')
    if extra:
        bad.append(f'unknown symbols {extra}')
    failed = []
    for key, e in syms.items():
        if not isinstance(e, dict):
            bad.append(f'{key}: not an object')
            continue
        st = e.get('status', 'ok' if 'bars' in e else None)
        if st == 'failed':
            failed.append(key)
            if 'bars' in e:
                bad.append(f'{key}: failed entry must not carry bars')
            continue
        if st is not None and st != 'ok':
            bad.append(f"{key}: bad status {st!r}")
            continue
        bars = e.get('bars')
        if not isinstance(bars, list) or not bars:
            bad.append(f'{key}: no bars')
            continue
        prev_t = None
        for bar in bars:
            if not isinstance(bar, list) or len(bar) != 5:
                bad.append(f'{key}: bad bar {bar!r}')
                continue
            t, o, h, l, c = bar
            if isinstance(t, bool) or not isinstance(t, int) or t <= 0:
                bad.append(f'{key}: bad bar time {t!r}')
                continue
            if prev_t is not None and t <= prev_t:
                bad.append(f'{key}: bars out of order at {t}')
            prev_t = t
            if session is not None:
                d_iso, mins = _et_parts(t)
                if d_iso != session:
                    bad.append(f'{key}: bar {t} is on {d_iso}, not session {session}')
                elif not (OPEN_MIN <= mins <= CLOSE_MIN):
                    bad.append(f'{key}: bar {t} outside 9:30 AM-4 PM ET')
            for name, v in zip(('open', 'high', 'low', 'close'), (o, h, l, c)):
                if not _finite_pos(v):
                    bad.append(f'{key}: bad {name} {v!r}')
            if all(_finite_pos(v) for v in (o, h, l, c)):
                if h < max(o, c) or l > min(o, c) or l > h:
                    bad.append(f'{key}: OHLC inconsistent o={o} h={h} l={l} c={c}')
    if sorted(doc.get('failed') or []) != sorted(failed) or not isinstance(doc.get('failed'), list):
        bad.append('failed list does not match the failed entries')
    return bad


def build_cmp_doc(now_et, results):
    """cmp-intraday document from per-symbol results.

    `results` maps key -> (session, bars) for ok symbols or None for
    failed ones. The file session is the latest session among the ok
    symbols; a symbol whose session is older is failed, never published
    as the current session.
    """
    ok = {k: v for k, v in results.items() if v is not None}
    if not ok:
        raise RuntimeError('no symbol produced bars — refusing to build an empty file')
    session = max(v[0] for v in ok.values())
    symbols = {}
    failed = []
    for key in sorted(SYMBOLS):
        v = results.get(key)
        if v is None or v[0] != session:
            symbols[key] = {'status': 'failed'}
            failed.append(key)
        else:
            symbols[key] = {'bars': v[1]}
    now_utc = now_et.astimezone(UTC)
    return {
        'v': CMP_VERSION, 'kind': CMP_KIND,
        'asOf': now_utc.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'asOfLabel': et_label(now_et.astimezone(NY)),
        'session': session,
        'sessionOpen': DI.session_open(now_et.astimezone(NY)),
        'symbols': symbols,
        'failed': sorted(failed),
    }


def write_cmp_doc(path, doc):
    """Validate, then write atomically. Raises (and writes nothing) if invalid."""
    bad = validate_cmp_doc(doc)
    if bad:
        raise RuntimeError('cmp-intraday document invalid: ' + '; '.join(bad))
    text = json.dumps(doc, separators=(',', ':'), sort_keys=False, allow_nan=False) + '\n'
    if len(text.encode()) > CMP_MAX_BYTES:
        raise RuntimeError(f'cmp-intraday document too big ({len(text)} bytes > {CMP_MAX_BYTES})')
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    with open(path + '.tmp', 'w') as f:
        f.write(text)
    os.replace(path + '.tmp', path)
    return len(text.encode())


# --- fixture (offline tests; Yahoo-payload shape) ---

def load_fixture(path):
    """Fixture -> (now_iso, {key: payload | ('error', msg)}).

    A bad fixture entry for one symbol is a per-symbol failure (fail
    closed), never a load-time abort.
    """
    try:
        fx = json.load(open(path))
    except Exception as e:
        raise RuntimeError(f'fixture unreadable: {type(e).__name__}: {e}')
    out = {}
    for key, payload in (fx.get('symbols') or {}).items():
        if key not in SYMBOLS:
            raise RuntimeError(f'fixture has unknown symbol {key}')
        if not isinstance(payload, dict) or 'timestamp' not in payload:
            out[key] = ('error', 'fixture entry has no timestamp array')
        else:
            out[key] = ('ok', payload)
    return fx, out


# --- CLI ---

def main(argv):
    out, now, check_only, fixture, gate, validate = 'cmp-intraday.json', None, False, None, False, None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--out':
            out = argv[i + 1]; i += 2
        elif a == '--now':
            now = argv[i + 1]; i += 2
        elif a == '--check-only':
            check_only = True; i += 1
        elif a == '--fixture':
            fixture = argv[i + 1]; i += 2
        elif a == '--gate':
            gate = True; i += 1
        elif a == '--validate':
            validate = argv[i + 1]; i += 2
        else:
            print(f'unknown arg {a}', file=sys.stderr); return 2
    if gate:
        try:
            inside, reason = in_window(SW.parse_now(now))
        except Exception as e:
            print('run=0')
            print('final=0')
            print(f'cmp-intraday gate: cannot determine ET time ({type(e).__name__}: {e}) — skipping run')
            return 0
        print(f'run={"1" if inside else "0"}')
        print(f'final=0')
        print(f'cmp-intraday gate: {reason} ({"inside" if inside else "outside"} window; {"intraday run: cmp-intraday.json only" if inside else "skip"})')
        return 0
    if validate:
        try:
            with open(validate) as f:
                vdoc = json.load(f, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(f'non-finite {c}')))
        except Exception as e:
            print(f'cmp-intraday: cannot read {validate} ({type(e).__name__}: {e})', file=sys.stderr); return 1
        vbad = validate_cmp_doc(vdoc)
        if vbad:
            print('cmp-intraday INVALID: ' + '; '.join(vbad), file=sys.stderr); return 1
        ok_n = sum(1 for e in vdoc['symbols'].values() if 'bars' in e)
        print(f"cmp-intraday OK: {ok_n}/{len(vdoc['symbols'])} symbols with bars, session {vdoc['session']}, asOf {vdoc['asOf']}, failed {vdoc['failed'] or 'none'}")
        return 0
    if not DI.tz_healthy():
        print('cmp-intraday: America/New_York time zone data unavailable or stale — skipping run (fail safe, no fetch)', file=sys.stderr)
        return 0
    fx = fx_payloads = None
    if fixture:
        try:
            fx, fx_payloads = load_fixture(fixture)
        except Exception as e:
            print(str(e), file=sys.stderr); return 1
        if now is None:
            now = fx.get('now')
    now_et = SW.parse_now(now)
    results = {}
    failed_names = []
    consecutive_429 = 0
    aborted_429 = False
    never_tried = []
    for idx, key in enumerate(sorted(SYMBOLS)):
        ysym = SYMBOLS[key]
        try:
            fb = fx_payloads.get(key) if fx_payloads is not None else None
            if fx_payloads is not None and fb is None:
                print(f'{key}: not in fixture — skipping (not attempted)')
                results[key] = None
                failed_names.append(key)
                consecutive_429 = 0
                continue
            if fb is not None and fb[0] == 'error':
                print(f'{key}: bad fixture data ({fb[1]}) — keeping it out of the file', file=sys.stderr)
                results[key] = None
                failed_names.append(key)
                consecutive_429 = 0
                continue
            payload = fb[1] if fb is not None else fetch_yahoo_payload(ysym)
            results[key] = bars_from_payload(ysym, payload, now_et)
            consecutive_429 = 0
            print(f'{key}: {len(results[key][1])} bars for session {results[key][0]}')
        except YahooRateLimited as e:
            consecutive_429 += 1
            results[key] = None
            failed_names.append(key)
            print(f'{key}: Yahoo rate-limited (HTTP 429) — keeping it out of the file', file=sys.stderr)
            if consecutive_429 >= 2:
                never_tried = [s for s in sorted(SYMBOLS)[idx + 1:]]
                never = f' Never tried: {", ".join(never_tried)}.' if never_tried else ''
                print(f'cmp-intraday: ABORTING — two Yahoo 429s in a row ({", ".join(failed_names[-2:])}); '
                      f'stopping the run instead of hammering Yahoo.{never}', file=sys.stderr)
                aborted_429 = True
                break
        except Exception as e:
            consecutive_429 = 0
            results[key] = None
            failed_names.append(key)
            print(f'{key}: FAILED: {e}', file=sys.stderr)
    if aborted_429:
        return 1
    if not any(v is not None for v in results.values()):
        print('cmp-intraday: every symbol failed — no file written', file=sys.stderr)
        return 1
    try:
        doc = build_cmp_doc(now_et, results)
    except Exception as e:
        print(f'cmp-intraday: cannot build document: {e}', file=sys.stderr)
        return 1
    if check_only:
        ok_n = sum(1 for e in doc['symbols'].values() if 'bars' in e)
        print(f"cmp-intraday: would write {out} (session {doc['session']}, {ok_n}/3 symbols with bars, failed {doc['failed'] or 'none'}) (check-only, nothing written)")
        return 0
    try:
        nbytes = write_cmp_doc(out, doc)
    except Exception as e:
        print(f'cmp-intraday: NOT written: {e}', file=sys.stderr)
        return 1
    ok_n = sum(1 for e in doc['symbols'].values() if 'bars' in e)
    print(f'cmp-intraday: wrote {out} ({nbytes} bytes, session {doc["session"]}, {ok_n}/3 symbols with bars, failed {doc["failed"] or "none"})')
    if failed_names:
        stale = ', '.join(failed_names)
        print(f'::warning::cmp-intraday: {len(failed_names)} symbol(s) failed and were left out of the file: {stale}')
        print(f'cmp-intraday: failed symbols (left out of the file): {stale}', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
