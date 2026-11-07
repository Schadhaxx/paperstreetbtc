#!/usr/bin/env python3
"""Tests for tools/live_fallback.py (Python supercharge slice 5, Part 1).

Pure Python, no network, no browser. A stub fetcher stands in for Yahoo
chart meta; each test proves the fallback applies a real, valid Yahoo
price and keeps the previous value (stale) whenever Yahoo cannot supply
one. Run: python3 tests/test_live_fallback.py   exit 0 = all pass
"""
import copy
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'tools'))
import live_fallback as LF

R = []


def chk(name, ok, detail=''):
    R.append((name, bool(ok), detail))
    print('%-58s %s %s' % (name, 'PASS' if ok else 'FAIL', detail))


T0 = 1793998800  # 2026-11-06 16:00 ET, the market close


def yahoo_ok(symbol='MSTR', price=130.0, pc=129.0, t=T0):
    """A valid Yahoo chart-meta response. closes[-2] is the prior close."""
    return {'chart': {'result': [{'meta': {
        'regularMarketPrice': price, 'regularMarketTime': t},
        'indicators': {'quote': [{'close': [127.0, pc, price]}]}}]}}


def make_fetch(responses):
    """responses: {symbol: dict | Exception | None}. Records the URLs."""
    seen = []

    def fetch(url):
        seen.append(url)
        # symbol is the path segment after /chart/
        sym = url.split('/chart/')[1].split('?')[0]
        # Yahoo uses BRK-B; map back to the Finnhub symbol for the lookup.
        sym = sym.replace('-', '.') if sym == 'BRK-B' else sym
        r = responses.get(sym, None)
        if isinstance(r, Exception):
            raise r
        if r is None:
            raise urllib_error()
        return copy.deepcopy(r)

    fetch.seen = seen
    return fetch


def urllib_error():
    import urllib.error
    return urllib.error.URLError('stubbed failure')


def good_stocks():
    return {
        'MSTR': {'c': 128.93, 'pc': 129.3, 't': T0 - 86400},
        'TSLA': {'c': 358.22, 'pc': 343.69, 't': T0 - 86400},
        'STRC': {'c': 99.84, 'pc': 99.56, 't': T0 - 86400},
    }


def main():
    # 1. Yahoo agrees and is valid -> fallback applied, src tagged.
    stocks = good_stocks()
    rep = LF.fallback_for(['MSTR'], stocks,
                          make_fetch({'MSTR': yahoo_ok('MSTR', 130.0, 129.0)}))
    chk('valid yahoo: applied', stocks['MSTR']['c'] == 130.0
        and stocks['MSTR']['pc'] == 129.0 and stocks['MSTR']['t'] == T0
        and stocks['MSTR'].get('src') == 'Yahoo', str(stocks['MSTR']))
    chk('valid yahoo: report says yahoo',
        rep['MSTR']['source'] == 'yahoo', str(rep['MSTR']))

    # 2. A symbol not in the failed list is untouched.
    chk('unfailed symbol untouched', stocks['TSLA']['c'] == 358.22
        and 'src' not in stocks['TSLA'])

    # 3. Yahoo fetch fails -> kept, report says kept.
    stocks = good_stocks()
    before = copy.deepcopy(stocks['TSLA'])
    rep = LF.fallback_for(['TSLA'], stocks,
                          make_fetch({'TSLA': urllib_error()}))
    chk('yahoo fetch fails: kept previous', stocks['TSLA'] == before)
    chk('yahoo fetch fails: report kept',
        rep['TSLA']['source'] == 'kept', str(rep['TSLA']))

    # 4. Yahoo returns no result -> kept.
    stocks = good_stocks()
    rep = LF.fallback_for(['MSTR'], stocks,
                          make_fetch({'MSTR': {'chart': {'result': []}}}))
    chk('yahoo empty result: kept', stocks['MSTR']['c'] == 128.93
        and rep['MSTR']['source'] == 'kept')

    # 5. Yahoo price non-positive / missing -> kept.
    for bad in (0, -5.0, None, 'abc'):
        stocks = good_stocks()
        rep = LF.fallback_for(['MSTR'], stocks, make_fetch(
            {'MSTR': yahoo_ok('MSTR', bad, 129.0)}))
        chk('yahoo bad price %r: kept' % (bad,),
            stocks['MSTR']['c'] == 128.93
            and rep['MSTR']['source'] == 'kept')

    # 6. Prior close missing / non-positive -> kept.
    stocks = good_stocks()
    resp = yahoo_ok('MSTR', 130.0, 129.0)
    resp['chart']['result'][0]['indicators']['quote'][0]['close'] = [130.0]
    rep = LF.fallback_for(['MSTR'], stocks, make_fetch({'MSTR': resp}))
    chk('yahoo no prior close: kept', stocks['MSTR']['c'] == 128.93
        and rep['MSTR']['source'] == 'kept')
    stocks = good_stocks()
    rep = LF.fallback_for(['MSTR'], stocks,
                          make_fetch({'MSTR': yahoo_ok('MSTR', 130.0, 0)}))
    chk('yahoo prior close 0: kept', stocks['MSTR']['c'] == 128.93
        and rep['MSTR']['source'] == 'kept')

    # 7. Sanity band: +26% from the prior close is rejected, +25% is used.
    stocks = good_stocks()
    rep = LF.fallback_for(['MSTR'], stocks,
                          make_fetch({'MSTR': yahoo_ok('MSTR', 129.0 * 1.26, 129.0)}))
    chk('yahoo +26% vs prior close: kept',
        stocks['MSTR']['c'] == 128.93
        and rep['MSTR']['source'] == 'kept')
    stocks = good_stocks()
    rep = LF.fallback_for(['MSTR'], stocks,
                          make_fetch({'MSTR': yahoo_ok('MSTR', 129.0 * 1.25, 129.0)}))
    chk('yahoo +25% vs prior close: applied (band edge)',
        stocks['MSTR']['c'] == 129.0 * 1.25
        and rep['MSTR']['source'] == 'yahoo')

    # 8. Yahoo time missing / invalid -> kept.
    stocks = good_stocks()
    resp = yahoo_ok('MSTR', 130.0, 129.0)
    del resp['chart']['result'][0]['meta']['regularMarketTime']
    rep = LF.fallback_for(['MSTR'], stocks, make_fetch({'MSTR': resp}))
    chk('yahoo no timestamp: kept', stocks['MSTR']['c'] == 128.93
        and rep['MSTR']['source'] == 'kept')

    # 9. BRK.B maps to BRK-B in the Yahoo URL.
    f = make_fetch({'BRK.B': yahoo_ok('BRK.B', 570.0, 568.0)})
    stocks = {'BRK.B': {'c': 569.0, 'pc': 568.0, 't': T0 - 86400}}
    LF.fallback_for(['BRK.B'], stocks, f)
    chk('BRK.B fetched as BRK-B',
        any('BRK-B' in u for u in f.seen) and stocks['BRK.B']['c'] == 570.0,
        str(f.seen))

    # 10. Both fail (Finnhub failed AND Yahoo fails) -> kept + stale.
    #     This is the keep-last-price case Part 2 must label stale.
    stocks = good_stocks()
    rep = LF.fallback_for(['MSTR', 'TSLA'], stocks,
                          make_fetch({'MSTR': urllib_error(),
                                      'TSLA': urllib_error()}))
    chk('both fail: both kept',
        stocks['MSTR']['c'] == 128.93 and stocks['TSLA']['c'] == 358.22
        and rep['MSTR']['source'] == 'kept'
        and rep['TSLA']['source'] == 'kept')

    # 11. Multiple symbols, mixed outcomes.
    stocks = good_stocks()
    rep = LF.fallback_for(['MSTR', 'TSLA', 'STRC'], stocks, make_fetch(
        {'MSTR': yahoo_ok('MSTR', 130.0, 129.0),
         'TSLA': urllib_error(),
         'STRC': yahoo_ok('STRC', 99.9, 99.56)}))
    chk('mixed: yahoo applied where valid, kept where not',
        stocks['MSTR']['c'] == 130.0 and stocks['TSLA']['c'] == 358.22
        and stocks['STRC']['c'] == 99.9
        and rep['MSTR']['source'] == 'yahoo'
        and rep['TSLA']['source'] == 'kept'
        and rep['STRC']['source'] == 'yahoo')

    # 12. CLI end-to-end (subprocess, stubbed network is NOT available to
    #     the CLI, so this run uses --failed on a symbol whose Yahoo fetch
    #     will fail in the sandbox -> kept, exit 0, file unchanged).
    with tempfile.TemporaryDirectory() as tmp:
        pp = os.path.join(tmp, 'prices.json')
        data = {'updated': '2026-11-06T23:57:10Z',
                'stocks': good_stocks()}
        json.dump(data, open(pp, 'w'))
        r = subprocess.run(
            [sys.executable,
             os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          '..', 'tools', 'live_fallback.py'),
             '--prices', pp, '--failed', 'MSTR,TSLA'],
            capture_output=True, text=True)
        out = json.load(open(pp))
        chk('CLI: exit 0 when yahoo fails (kept, not a crash)',
            r.returncode == 0, r.stderr.strip()[:200])
        chk('CLI: file unchanged when yahoo fails',
            out['stocks']['MSTR']['c'] == 128.93
            and out['stocks']['TSLA']['c'] == 358.22)
        # dry-run writes nothing.
        before = open(pp).read()
        r = subprocess.run(
            [sys.executable,
             os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          '..', 'tools', 'live_fallback.py'),
             '--prices', pp, '--failed', 'MSTR', '--dry-run'],
            capture_output=True, text=True)
        chk('CLI --dry-run: exit 0 and file untouched',
            r.returncode == 0 and open(pp).read() == before)
        # malformed prices.json -> exit 1.
        bad = os.path.join(tmp, 'bad.json')
        open(bad, 'w').write('{not json')
        r = subprocess.run(
            [sys.executable,
             os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          '..', 'tools', 'live_fallback.py'),
             '--prices', bad, '--failed', 'MSTR'],
            capture_output=True, text=True)
        chk('CLI malformed prices.json: exit 1', r.returncode == 1)
        # missing --failed -> exit 2.
        r = subprocess.run(
            [sys.executable,
             os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          '..', 'tools', 'live_fallback.py'),
             '--prices', pp],
            capture_output=True, text=True)
        chk('CLI missing --failed: exit 2', r.returncode == 2)

    bad = [x for x in R if not x[1]]
    print('\n%d checks, %d failed' % (len(R), len(bad)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
