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
live: the Yahoo price must be positive and finite, its prior close must
be positive and finite, and it must be within 25% of that prior close
(the same sanity band compare.js uses for lump-sum opens). If Yahoo
fails or returns a bad price, the previous value is kept (today's
behaviour) and the symbol is reported as still stale — the site then
labels it stale (slice 5, Part 2) instead of showing a frozen price
as if it were live.

Stdlib only, no key (Yahoo chart is keyless). The fetcher is injectable
so tests run offline with fixtures; the default fetcher mirrors the
fetch job's `get()` (3 tries, 15 s timeout, User-Agent
'paperstreetbtc-cache').

CLI: python3 tools/live_fallback.py --prices <prices.json>
     --failed <MSTR,TSLA,...> [--out <prices.json>] [--dry-run]
Exit 0 = done (fallback applied, or nothing to do), 1 = input
unreadable / unwritable (file untouched), 2 = usage error.
--dry-run prints the report and writes nothing.
"""
import json
import math
import sys
import urllib.error
import urllib.request

# Symbols the fetch job asks Finnhub for (same list as prices.yml).
STOCKS = ['MSTR', 'STRC', 'TSLA', 'PLTR', 'SPY', 'QQQ', 'BRK.B', 'GLD',
          'IBIT', 'FBTC', 'MU', 'META', 'SPCX']
# A fallback price more than 25% from the prior close is not used.
BAND = 0.25


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


def yahoo_quote(symbol, fetch=_fetch):
    """Fetch one Yahoo chart-meta quote.

    Returns {'c': price, 'pc': prior close, 't': regularMarketTime} or
    None if Yahoo fails or returns a bad / implausible price. The prior
    close is the 2nd-to-last daily bar's close — the same definition the
    fetch job uses for the market indicators.
    """
    y = yahoo_symbol(symbol)
    url = ('https://query1.finance.yahoo.com/v8/finance/chart/%s'
           '?range=5d&interval=1d' % y)
    try:
        r = fetch(url)
    except Exception:
        return None
    try:
        res = (r.get('chart') or {}).get('result') or []
        if not res:
            return None
        meta = res[0].get('meta') or {}
        c = meta.get('regularMarketPrice')
        t = meta.get('regularMarketTime')
        closes = ((res[0].get('indicators') or {}).get('quote')
                  or [{}])[0].get('close') or []
        pc = closes[-2] if len(closes) >= 2 else None
        if not (isinstance(c, (int, float)) and not isinstance(c, bool)
                and math.isfinite(c) and c > 0):
            return None
        if not (isinstance(pc, (int, float)) and not isinstance(pc, bool)
                and math.isfinite(pc) and pc > 0):
            return None
        if abs(c / pc - 1) > BAND:
            return None
        if not (isinstance(t, (int, float)) and not isinstance(t, bool)
                and math.isfinite(t) and t > 0):
            return None
        return {'c': c, 'pc': pc, 't': int(t)}
    except Exception:
        return None


def fallback_for(symbols, stocks, fetch=_fetch):
    """Apply the Yahoo fallback to each symbol in `symbols`.

    `stocks` is the prices.json stocks dict, updated in place: a symbol
    Yahoo supplies gets {'c','pc','t','src':'Yahoo'}. A symbol Yahoo
    cannot supply keeps its previous value untouched.

    Returns a report {symbol: {'source': 'yahoo'|'kept', ...}} — 'yahoo'
    when the fallback supplied the price, 'kept' when the previous value
    stands (Yahoo failed, or its price was invalid). A 'kept' symbol is
    still stale; the site labels it stale (Part 2) rather than showing
    the frozen price as live.
    """
    report = {}
    for s in symbols:
        q = yahoo_quote(s, fetch)
        if q is None:
            report[s] = {'source': 'kept',
                         'reason': ('yahoo unavailable or invalid; '
                                    'keeping previous price (stale)')}
            continue
        stocks[s] = {'c': q['c'], 'pc': q['pc'], 't': q['t'],
                     'src': 'Yahoo'}
        report[s] = {'source': 'yahoo', 'price': q['c'],
                     'reason': 'finnhub failed; yahoo chart meta'}
    return report


def _parse_args(argv):
    prices = None
    failed = None
    out = None
    dry_run = False
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
        else:
            return None
    if not prices or failed is None:
        return None
    return {'prices': prices, 'failed': failed, 'out': out or prices,
            'dry_run': dry_run}


def main(argv):
    args = _parse_args(argv)
    if args is None:
        print('usage: live_fallback.py --prices <prices.json> '
              '--failed <SYM,SYM,...> [--out <prices.json>] [--dry-run]',
              file=sys.stderr)
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
    report = fallback_for(args['failed'], stocks)
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
        with open(args['out'], 'w') as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write('\n')
    except Exception as e:
        print(f'live-fallback: cannot write {args["out"]}: '
              f'{type(e).__name__}: {e}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
