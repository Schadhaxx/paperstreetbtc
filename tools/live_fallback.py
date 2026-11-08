#!/usr/bin/env python3
"""Live-stock fallback: Yahoo chart meta when Finnhub fails.

Live BTC already has a fallback chain (CoinGecko -> Coinbase -> keep last
price). Live stocks are Finnhub-only -> keep last price. This tool gives
stocks a second source so a Finnhub failure does not leave the live price
frozen: for each symbol Finnhub failed on, it fetches Yahoo chart meta
(regularMarketPrice, the same source the history rebuild and the market
indicators already use) and, if the price is valid, writes it into
prices.json with a 'src' tag so the site can show where it came from.

Why Yahoo, not Stooq: Stooq gives daily closes, not a live intraday
price — using it would present yesterday's close as a live price, which
is exactly the dishonesty this slice is meant to prevent. Yahoo chart
meta gives regularMarketPrice, a real live price during market hours,
keyless and free, from a source the pipeline already trusts.

A fallback price is NEVER invented and NEVER a stale price presented as
live. Before a Yahoo quote is accepted, all of these must hold:

* the quote timestamp is a real time, in regular market hours
  (09:30-16:00 ET, weekday), from the same ET session as `now`
  (the expected session), and no more than 30 min old — a quote from
  another session, from after hours, or a stale one is rejected;
* the price is positive and finite, the prior close is positive and
  finite, and the price is within 25% of that prior close (the same
  sanity band compare.js uses for lump-sum opens).

The prior close is derived from bar timestamps, NOT from closes[-2]:
it is the close of the daily bar whose session (ET date of its
timestamp) is the latest one strictly before the quote's session. That
stays right across a holiday or a missing session, where closes[-2]
can pick the wrong day (e.g. when the latest bar is not the quote's
session, closes[-2] is the session before that — or, after a holiday,
the bar list can end before the quote's session entirely).

If Yahoo fails or returns a bad / stale quote, the previous value is
kept (today's behaviour) and the symbol is reported as still stale —
the site then labels it stale (slice 5, Part 2) instead of showing a
frozen price as if it were live.

Writes are safe: prices.json is serialised with allow_nan=False
(non-finite numbers can never be written) and published by
write-to-temp + atomic rename, so a failed run can never leave a
partial file. The stall-alert step (tools/stall_alert.py) runs AFTER
this tool and the validate gate, last in the job, so nothing
overwrites its `alerts` field in health.json.

Known limit: regular hours here are the plain 09:30-16:00 ET window —
there is no holiday / early-close calendar in the repo, so the tool
cannot tell an early-close day from a regular session. A fresh
afternoon quote on an early-close day (e.g. 14:00 ET, after the 13:00
early close) is ACCEPTED, not rejected, as long as it passes the
regular-hours rule (09:30-16:00 ET, same ET session, at most 30 min
old, at most 5 min in the future) — so on an early-close day a quote
timestamped after the market has closed can still be shown as live
until 16:00 ET. That is the limitation to disclose, not a rejection.
No holiday / early-close calendar is built in this pass.

Stdlib only, no key (Yahoo chart is keyless). The fetcher is injectable
so tests run offline with fixtures; the default fetcher mirrors the
fetch job's `get()` (3 tries, 15 s timeout, User-Agent
'paperstreetbtc-cache').

CLI: python3 tools/live_fallback.py --prices <prices.json>
     --failed <MSTR,TSLA,...> [--out <prices.json>] [--dry-run]
     [--now <ISO>]
Exit 0 = done (fallback applied, or nothing to do), 1 = input
unreadable / unwritable (file untouched), 2 = usage error.
--dry-run prints the report and writes nothing. --now pins "now"
(default: current UTC time); it exists so a run is reproducible and
testable, and so the quote-session check has a definite expected
session.
"""
import datetime as dt
import json
import math
import os
import sys
import tempfile
import urllib.error
import urllib.request
import zoneinfo

# Symbols the fetch job asks Finnhub for (same list as prices.yml).
STOCKS = ['MSTR', 'STRC', 'TSLA', 'PLTR', 'SPY', 'QQQ', 'BRK.B', 'GLD',
          'IBIT', 'FBTC', 'MU', 'META', 'SPCX']
# A fallback price more than 25% from the prior close is not used.
BAND = 0.25
# Regular session, ET: 09:30-16:00, weekdays. No holiday / early-close
# calendar exists in the repo (see the known limit in the docstring).
REG_OPEN_MIN = 9 * 60 + 30
REG_CLOSE_MIN = 16 * 60
# A quote older than this (vs now) is stale and is rejected.
FRESH_MIN = 30
# Allow a quote this far ahead of now (clock skew); further ahead is
# a bad timestamp, not a live price.
SKEW_S = 300
ET = zoneinfo.ZoneInfo('America/New_York')


def yahoo_symbol(s):
    """Yahoo uses a dash where Finnhub uses a dot (BRK.B -> BRK-B)."""
    return s.replace('.', '-')


def _fetch(url, tries=3, timeout=15):
    """Default fetcher: parsed JSON, retries like the fetch job's get()."""
    import time as _t
    for i in range(tries):
        try:
            req = urllib.request.Request(
                url, headers={'User-Agent': 'paperstreetbtc-cache'})
            with urllib.request.urlopen(req, timeout=timeout) as f:
                return json.load(f)
        except urllib.error.HTTPError as e:
            if e.code < 500 or i == tries - 1:
                raise
        except (urllib.error.URLError, TimeoutError):
            if i == tries - 1:
                raise
        _t.sleep(3 * (i + 1))
    raise urllib.error.URLError('unreachable')


def _et_date(ts):
    """The ET calendar date of an epoch timestamp."""
    return dt.datetime.fromtimestamp(ts, tz=ET).date()


def _prior_close(timestamps, closes, quote_dt):
    """Prior session close, derived from bar timestamps.

    `timestamps` / `closes` are Yahoo's aligned 1d-bar arrays. The
    quote's session is the ET date of its regularMarketTime. The prior
    close is the close of the bar whose session (ET date of its
    timestamp) is the latest one strictly before the quote's session.
    Returns None when no bar precedes the quote's session, or when
    that immediately-preceding bar's close is missing / invalid —
    an older session's close is NOT substituted, because the sanity
    band must be measured against the session right before the quote.
    """
    session = quote_dt.astimezone(ET).date()
    dated = {}
    for ts, c in zip(timestamps or [], closes or []):
        if not (isinstance(ts, (int, float)) and not isinstance(ts, bool)
                and math.isfinite(ts) and ts > 0):
            continue
        d = _et_date(ts)
        if d >= session:
            continue
        dated[d] = c
    if not dated:
        return None
    c = dated[max(dated)]
    if not (isinstance(c, (int, float)) and not isinstance(c, bool)
            and math.isfinite(c) and c > 0):
        return None
    return c


def _check_quote_time(t, now):
    """Validate the quote timestamp / session / freshness.

    Returns (quote_dt, None) when the timestamp is acceptable, else
    (None, reason). Checked BEFORE any price is looked at: a quote
    whose timestamp is not in regular hours, whose session is not the
    expected session (today, ET), or which is stale is rejected
    outright — it can never become a live price.
    """
    if not (isinstance(t, (int, float)) and not isinstance(t, bool)
            and math.isfinite(t) and t > 0):
        return None, 'no valid regularMarketTime'
    quote_dt = dt.datetime.fromtimestamp(t, tz=dt.timezone.utc)
    if quote_dt > now + dt.timedelta(seconds=SKEW_S):
        return None, 'quote timestamp is in the future'
    age_s = (now - quote_dt).total_seconds()
    if age_s > FRESH_MIN * 60:
        return None, 'quote is stale (%.0f min old)' % (age_s / 60)
    q_et = quote_dt.astimezone(ET)
    if q_et.date() != now.astimezone(ET).date():
        return None, 'quote session (%s) is not the expected session (%s)' % (
            q_et.date().isoformat(), now.astimezone(ET).date().isoformat())
    if q_et.weekday() > 4:
        return None, 'quote is not from a weekday session'
    mins = q_et.hour * 60 + q_et.minute
    if mins < REG_OPEN_MIN or mins > REG_CLOSE_MIN:
        return None, 'quote timestamp is outside regular hours (09:30-16:00 ET)'
    return quote_dt, None


def yahoo_quote_detailed(symbol, fetch=_fetch, now=None):
    """Fetch one Yahoo chart-meta quote, with a rejection reason.

    Returns (quote, None) with quote = {'c', 'pc', 't'} when Yahoo
    supplies a valid, fresh, regular-hours quote whose prior close is
    derived from bar timestamps; else (None, reason). `now` defaults
    to the current UTC time and defines the expected session.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    y = yahoo_symbol(symbol)
    url = ('https://query1.finance.yahoo.com/v8/finance/chart/%s'
           '?range=10d&interval=1d' % y)
    try:
        r = fetch(url)
    except Exception:
        return None, 'yahoo fetch failed'
    try:
        res = (r.get('chart') or {}).get('result') or []
        if not res:
            return None, 'yahoo returned no result'
        meta = res[0].get('meta') or {}
        c = meta.get('regularMarketPrice')
        t = meta.get('regularMarketTime')
        # Timestamp / session / freshness first: an invalid, stale or
        # wrong-session quote is rejected before any price is trusted.
        quote_dt, reason = _check_quote_time(t, now)
        if quote_dt is None:
            return None, reason
        # Prior close from bar timestamps (never closes[-2]).
        timestamps = res[0].get('timestamp') or []
        closes = ((res[0].get('indicators') or {}).get('quote')
                  or [{}])[0].get('close') or []
        pc = _prior_close(timestamps, closes, quote_dt)
        if pc is None:
            return None, 'no daily bar before the quote session (no prior close)'
        if not (isinstance(c, (int, float)) and not isinstance(c, bool)
                and math.isfinite(c) and c > 0):
            return None, 'yahoo price is not a positive finite number'
        if abs(c / pc - 1) > BAND:
            return None, 'yahoo price is more than 25% from the prior close'
        return {'c': c, 'pc': pc, 't': int(t)}, None
    except Exception as e:
        return None, 'unparseable yahoo response (%s)' % type(e).__name__


def yahoo_quote(symbol, fetch=_fetch, now=None):
    """Fetch one Yahoo chart-meta quote, or None if it is unusable."""
    q, _reason = yahoo_quote_detailed(symbol, fetch, now)
    return q


def fallback_for(symbols, stocks, fetch=_fetch, now=None):
    """Apply the Yahoo fallback to each symbol in `symbols`.

    `stocks` is the prices.json stocks dict, updated in place: a symbol
    Yahoo supplies gets {'c','pc','t','src':'Yahoo'}. A symbol Yahoo
    cannot supply keeps its previous value untouched.

    Returns a report {symbol: {'source': 'yahoo'|'kept', ...}} — 'yahoo'
    when the fallback supplied the price, 'kept' when the previous value
    stands (Yahoo failed, or its quote was invalid / stale /
    wrong-session). A 'kept' symbol is still stale; the site labels it
    stale (Part 2) rather than showing the frozen price as live.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    report = {}
    for s in symbols:
        q, reason = yahoo_quote_detailed(s, fetch, now)
        if q is None:
            report[s] = {'source': 'kept',
                         'reason': ('keeping previous price (stale): '
                                    + (reason or 'yahoo unavailable'))}
            continue
        stocks[s] = {'c': q['c'], 'pc': q['pc'], 't': q['t'],
                     'src': 'Yahoo'}
        report[s] = {'source': 'yahoo', 'price': q['c'],
                     'reason': 'finnhub failed; yahoo chart meta'}
    return report


def _atomic_write_json(path, data):
    """Write JSON safely: finite numbers only, atomically.

    The data is serialised first with allow_nan=False, so a NaN or
    Infinity anywhere raises BEFORE the target is touched; then it is
    written to a temp file in the same directory, fsynced, and moved
    over the target with os.replace. A failed write can never leave a
    partial file, and no non-finite number can ever be published.
    """
    text = json.dumps(data, indent=2, sort_keys=True,
                      allow_nan=False) + '\n'
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, prefix='.live-fallback-',
                               suffix='.tmp')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _parse_now(s):
    if s is None:
        return dt.datetime.now(dt.timezone.utc)
    return dt.datetime.fromisoformat(s.replace('Z', '+00:00'))


def _parse_args(argv):
    prices = None
    failed = None
    out = None
    dry_run = False
    now_s = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--prices' and i + 1 < len(argv):
            prices = argv[i + 1]
            i += 2
        elif a == '--failed' and i + 1 < len(argv):
            failed = [s.strip() for s in argv[i + 1].split(',') if s.strip()]
            i += 2
        elif a == '--out' and i + 1 < len(argv):
            out = argv[i + 1]
            i += 2
        elif a == '--dry-run':
            dry_run = True
            i += 1
        elif a == '--now' and i + 1 < len(argv):
            now_s = argv[i + 1]
            i += 2
        else:
            return None
    if not prices or failed is None:
        return None
    return {'prices': prices, 'failed': failed, 'out': out or prices,
            'dry_run': dry_run, 'now': now_s}


def main(argv):
    args = _parse_args(argv)
    if args is None:
        print('usage: live_fallback.py --prices <prices.json> '
              '--failed <SYM,SYM,...> [--out <prices.json>] [--dry-run] '
              '[--now <ISO>]', file=sys.stderr)
        return 2
    try:
        now = _parse_now(args['now'])
    except ValueError as e:
        print(f'live-fallback: bad --now: {e}', file=sys.stderr)
        return 2
    try:
        data = json.load(open(args['prices']))
    except Exception as e:
        print(f'live-fallback: cannot read {args["prices"]}: '
              f'{type(e).__name__}: {e}', file=sys.stderr)
        return 1
    if not isinstance(data, dict):
        print('live-fallback: prices.json is not an object', file=sys.stderr)
        return 1
    stocks = data.get('stocks')
    if not isinstance(stocks, dict):
        print('live-fallback: prices.json has no stocks dict',
              file=sys.stderr)
        return 1
    report = fallback_for(args['failed'], stocks, now=now)
    for s in args['failed']:
        r = report[s]
        if r['source'] == 'yahoo':
            print(f'{s}: fallback Yahoo {r["price"]} (finnhub failed)')
        else:
            print(f'::warning::{s}: {r["reason"]}')
    if args['dry_run']:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    try:
        _atomic_write_json(args['out'], data)
    except Exception as e:
        print(f'live-fallback: cannot write {args["out"]}: '
              f'{type(e).__name__}: {e}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
