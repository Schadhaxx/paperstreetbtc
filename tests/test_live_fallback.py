#!/usr/bin/env python3
"""Tests for tools/live_fallback.py (Python supercharge slice 5, Part 1).

Pure Python, no network, no browser. A stub fetcher stands in for Yahoo
chart meta; each test proves the fallback applies a real, valid Yahoo
price and keeps the previous value (stale) whenever Yahoo cannot supply
one. Run: python3 tests/test_live_fallback.py   exit 0 = all pass

Review #2 (r2) additions: the prior close is derived from bar
timestamps, not closes[-2]; the quote timestamp / session / freshness
is validated before any price is trusted; writes are atomic and
finite-only. The new tests (13-22) cover exactly those.
"""
import copy
import datetime as dt
import json
import math
import os
import subprocess
import sys
import tempfile
import zoneinfo

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'tools'))
import live_fallback as LF

R = []


def chk(name, ok, detail=''):
    R.append((name, bool(ok), detail))
    print('%-58s %s %s' % (name, 'PASS' if ok else 'FAIL', detail))


ET = zoneinfo.ZoneInfo('America/New_York')


def ep(y, mo, d, h, mi=0):
    """Epoch seconds for an ET wall time."""
    return int(dt.datetime(y, mo, d, h, mi, tzinfo=ET).timestamp())


T0 = 1793998800  # 2026-11-06 16:00 ET, the market close
# `now` for the main fixture: Fri 2026-11-06 16:10 ET — the T0 quote is
# 10 min old, fresh, and from the same (expected) session.
NOW = dt.datetime(2026, 11, 6, 16, 10, tzinfo=ET)
BAR_TS = [ep(2026, 11, 4, 9, 30), ep(2026, 11, 5, 9, 30),
          ep(2026, 11, 6, 9, 30)]  # Wed / Thu / Fri 09:30 ET


def yahoo_ok(symbol='MSTR', price=130.0, pc=129.0, t=T0, ts=None,
             closes=None):
    """A valid Yahoo chart-meta response.

    Bars are dated by timestamp: Wed 2026-11-04, Thu 2026-11-05, Fri
    2026-11-06 (the quote's session), closes [127.0, pc, price]. The
    prior close is the Thu bar's close — derived from timestamps, so a
    caller can move the bars and the derivation follows.
    """
    return {'chart': {'result': [{'meta': {
        'regularMarketPrice': price, 'regularMarketTime': t},
        'timestamp': list(BAR_TS if ts is None else ts),
        'indicators': {'quote': [{'close': list(
            [127.0, pc, price] if closes is None else closes)}]}}]}}


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


def fb(symbols, stocks, fetch, now=NOW):
    return LF.fallback_for(symbols, stocks, fetch, now=now)


def main():
    # 1. Yahoo agrees and is valid -> fallback applied, src tagged.
    stocks = good_stocks()
    rep = fb(['MSTR'], stocks,
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
    rep = fb(['TSLA'], stocks,
             make_fetch({'TSLA': urllib_error()}))
    chk('yahoo fetch fails: kept previous', stocks['TSLA'] == before)
    chk('yahoo fetch fails: report kept',
        rep['TSLA']['source'] == 'kept', str(rep['TSLA']))

    # 4. Yahoo returns no result -> kept.
    stocks = good_stocks()
    rep = fb(['MSTR'], stocks,
             make_fetch({'MSTR': {'chart': {'result': []}}}))
    chk('yahoo empty result: kept', stocks['MSTR']['c'] == 128.93
        and rep['MSTR']['source'] == 'kept')

    # 5. Yahoo price non-positive / missing -> kept.
    for bad in (0, -5.0, None, 'abc'):
        stocks = good_stocks()
        rep = fb(['MSTR'], stocks, make_fetch(
            {'MSTR': yahoo_ok('MSTR', bad, 129.0)}))
        chk('yahoo bad price %r: kept' % (bad,),
            stocks['MSTR']['c'] == 128.93
            and rep['MSTR']['source'] == 'kept')

    # 6. Prior close missing / non-positive -> kept.
    stocks = good_stocks()
    resp = yahoo_ok('MSTR', 130.0, 129.0)
    resp['chart']['result'][0]['indicators']['quote'][0]['close'] = [130.0]
    resp['chart']['result'][0]['timestamp'] = [BAR_TS[2]]
    rep = fb(['MSTR'], stocks, make_fetch({'MSTR': resp}))
    chk('yahoo no prior close: kept', stocks['MSTR']['c'] == 128.93
        and rep['MSTR']['source'] == 'kept')
    stocks = good_stocks()
    rep = fb(['MSTR'], stocks,
             make_fetch({'MSTR': yahoo_ok('MSTR', 130.0, 0)}))
    chk('yahoo prior close 0: kept', stocks['MSTR']['c'] == 128.93
        and rep['MSTR']['source'] == 'kept')

    # 7. Sanity band: +26% from the prior close is rejected, +25% is used.
    stocks = good_stocks()
    rep = fb(['MSTR'], stocks,
             make_fetch({'MSTR': yahoo_ok('MSTR', 129.0 * 1.26, 129.0)}))
    chk('yahoo +26% vs prior close: kept',
        stocks['MSTR']['c'] == 128.93
        and rep['MSTR']['source'] == 'kept')
    stocks = good_stocks()
    rep = fb(['MSTR'], stocks,
             make_fetch({'MSTR': yahoo_ok('MSTR', 129.0 * 1.25, 129.0)}))
    chk('yahoo +25% vs prior close: applied (band edge)',
        stocks['MSTR']['c'] == 129.0 * 1.25
        and rep['MSTR']['source'] == 'yahoo')

    # 8. Yahoo time missing / invalid -> kept.
    stocks = good_stocks()
    resp = yahoo_ok('MSTR', 130.0, 129.0)
    del resp['chart']['result'][0]['meta']['regularMarketTime']
    rep = fb(['MSTR'], stocks, make_fetch({'MSTR': resp}))
    chk('yahoo no timestamp: kept', stocks['MSTR']['c'] == 128.93
        and rep['MSTR']['source'] == 'kept')

    # 9. BRK.B maps to BRK-B in the Yahoo URL.
    f = make_fetch({'BRK.B': yahoo_ok('BRK.B', 570.0, 568.0)})
    stocks = {'BRK.B': {'c': 569.0, 'pc': 568.0, 't': T0 - 86400}}
    fb(['BRK.B'], stocks, f)
    chk('BRK.B fetched as BRK-B',
        any('BRK-B' in u for u in f.seen) and stocks['BRK.B']['c'] == 570.0,
        str(f.seen))

    # 10. Both fail (Finnhub failed AND Yahoo fails) -> kept + stale.
    #     This is the keep-last-price case Part 2 must label stale.
    stocks = good_stocks()
    rep = fb(['MSTR', 'TSLA'], stocks,
             make_fetch({'MSTR': urllib_error(),
                         'TSLA': urllib_error()}))
    chk('both fail: both kept',
        stocks['MSTR']['c'] == 128.93 and stocks['TSLA']['c'] == 358.22
        and rep['MSTR']['source'] == 'kept'
        and rep['TSLA']['source'] == 'kept')

    # 11. Multiple symbols, mixed outcomes.
    stocks = good_stocks()
    rep = fb(['MSTR', 'TSLA', 'STRC'], stocks, make_fetch(
        {'MSTR': yahoo_ok('MSTR', 130.0, 129.0),
         'TSLA': urllib_error(),
         'STRC': yahoo_ok('STRC', 99.9, 99.56)}))
    chk('mixed: yahoo applied where valid, kept where not',
        stocks['MSTR']['c'] == 130.0 and stocks['TSLA']['c'] == 358.22
        and stocks['STRC']['c'] == 99.9
        and rep['MSTR']['source'] == 'yahoo'
        and rep['TSLA']['source'] == 'kept'
        and rep['STRC']['source'] == 'yahoo')

    # 12. CLI end-to-end (subprocess). --now is pinned to Sat
    #     2026-11-07 12:00 UTC on purpose: whatever Yahoo returns, its
    #     quote is from Friday's session and is stale / wrong-session by
    #     then, so the CLI keeps the previous values deterministically
    #     whether the sandbox can reach Yahoo or not.
    with tempfile.TemporaryDirectory() as tmp:
        pp = os.path.join(tmp, 'prices.json')
        data = {'updated': '2026-11-06T23:57:10Z',
                'stocks': good_stocks()}
        json.dump(data, open(pp, 'w'))
        tool = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            '..', 'tools', 'live_fallback.py')
        r = subprocess.run(
            [sys.executable, tool, '--prices', pp, '--failed', 'MSTR,TSLA',
             '--now', '2026-11-07T12:00:00Z'],
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
            [sys.executable, tool, '--prices', pp, '--failed', 'MSTR',
             '--dry-run', '--now', '2026-11-07T12:00:00Z'],
            capture_output=True, text=True)
        chk('CLI --dry-run: exit 0 and file untouched',
            r.returncode == 0 and open(pp).read() == before)
        # malformed prices.json -> exit 1.
        bad = os.path.join(tmp, 'bad.json')
        open(bad, 'w').write('{not json')
        r = subprocess.run(
            [sys.executable, tool, '--prices', bad, '--failed', 'MSTR'],
            capture_output=True, text=True)
        chk('CLI malformed prices.json: exit 1', r.returncode == 1)
        # missing --failed -> exit 2.
        r = subprocess.run(
            [sys.executable, tool, '--prices', pp],
            capture_output=True, text=True)
        chk('CLI missing --failed: exit 2', r.returncode == 2)

    # --- r2: prior close from bar timestamps, not closes[-2] ---
    # 13. Missing session: bars end Fri 2026-11-06, the quote is Mon
    #     2026-11-09 10:00 ET (Monday's bar not in the series yet).
    #     closes[-2] would give Thu's 128.0; the timestamp derivation
    #     gives Fri's 129.0 — the session right before the quote.
    stocks = good_stocks()
    resp = yahoo_ok('MSTR', 130.0, 129.0, t=ep(2026, 11, 9, 10),
                    closes=[127.0, 128.0, 129.0])
    rep = fb(['MSTR'], stocks, make_fetch({'MSTR': resp}),
             now=dt.datetime(2026, 11, 9, 10, 5, tzinfo=ET))
    chk('missing session: prior close is Fri bar, not closes[-2]',
        stocks['MSTR']['pc'] == 129.0
        and rep['MSTR']['source'] == 'yahoo', str(stocks['MSTR']))

    # 14. Holiday gap: Mon 2026-11-09 has no bar (holiday); bars are
    #     Fri 2026-11-06 (129.0) and Tue 2026-11-10 (130.0, today).
    #     The quote's session is Tue; the prior session is Fri.
    stocks = good_stocks()
    resp = yahoo_ok('MSTR', 131.0, 129.0, t=ep(2026, 11, 10, 10),
                    ts=[BAR_TS[2], ep(2026, 11, 10, 9, 30)],
                    closes=[129.0, 130.0])
    rep = fb(['MSTR'], stocks, make_fetch({'MSTR': resp}),
             now=dt.datetime(2026, 11, 10, 10, 5, tzinfo=ET))
    chk('holiday gap: prior close is Fri bar before Tue session',
        stocks['MSTR']['pc'] == 129.0
        and rep['MSTR']['source'] == 'yahoo', str(stocks['MSTR']))

    # --- r2: quote timestamp / session / freshness validation ---
    # 15. After-hours quote (17:30 ET) -> rejected, previous kept.
    stocks = good_stocks()
    rep = fb(['MSTR'], stocks, make_fetch(
        {'MSTR': yahoo_ok('MSTR', 130.0, 129.0, t=ep(2026, 11, 6, 17, 30))}),
        now=dt.datetime(2026, 11, 6, 17, 35, tzinfo=ET))
    chk('after-hours quote (17:30 ET): kept',
        stocks['MSTR']['c'] == 128.93
        and rep['MSTR']['source'] == 'kept'
        and 'regular hours' in rep['MSTR']['reason'],
        str(rep['MSTR']))

    # 16. Weekend quote (Sat 10:00 ET) -> rejected.
    stocks = good_stocks()
    rep = fb(['MSTR'], stocks, make_fetch(
        {'MSTR': yahoo_ok('MSTR', 130.0, 129.0, t=ep(2026, 11, 7, 10))}),
        now=dt.datetime(2026, 11, 7, 10, 5, tzinfo=ET))
    chk('weekend quote (Sat): kept',
        stocks['MSTR']['c'] == 128.93
        and rep['MSTR']['source'] == 'kept', str(rep['MSTR']))

    # 17. Stale quote (45 min old, inside regular hours) -> rejected.
    stocks = good_stocks()
    rep = fb(['MSTR'], stocks, make_fetch(
        {'MSTR': yahoo_ok('MSTR', 130.0, 129.0, t=ep(2026, 11, 6, 15, 0))}),
        now=dt.datetime(2026, 11, 6, 15, 45, tzinfo=ET))
    chk('stale quote (45 min old): kept',
        stocks['MSTR']['c'] == 128.93
        and rep['MSTR']['source'] == 'kept'
        and 'stale' in rep['MSTR']['reason'], str(rep['MSTR']))

    # 18. Quote timestamp in the future -> rejected.
    stocks = good_stocks()
    rep = fb(['MSTR'], stocks, make_fetch(
        {'MSTR': yahoo_ok('MSTR', 130.0, 129.0, t=ep(2026, 11, 6, 15, 0))}),
        now=dt.datetime(2026, 11, 6, 14, 50, tzinfo=ET))
    chk('future quote (+10 min): kept',
        stocks['MSTR']['c'] == 128.93
        and rep['MSTR']['source'] == 'kept'
        and 'future' in rep['MSTR']['reason'], str(rep['MSTR']))

    # 19. Wrong session: quote is yesterday's 16:00 close, now is today
    #     10:00 ET. A yesterday-close-as-live quote is rejected (stale
    #     here, and wrong-session by date too — the two checks are
    #     defence in depth: a fresh-but-wrong-session quote cannot occur
    #     in real time, since sessions are a day apart and freshness is
    #     30 min, but both are enforced).
    stocks = good_stocks()
    q, reason = LF.yahoo_quote_detailed(
        'MSTR', make_fetch({'MSTR': yahoo_ok('MSTR', 130.0, 129.0)}),
        now=dt.datetime(2026, 11, 9, 10, 0, tzinfo=ET))
    chk('wrong-session quote: rejected, not applied',
        q is None and stocks['MSTR']['c'] == 128.93, str(reason))
    rep = fb(['MSTR'], stocks, make_fetch(
        {'MSTR': yahoo_ok('MSTR', 130.0, 129.0)}),
        now=dt.datetime(2026, 11, 9, 10, 0, tzinfo=ET))
    chk('wrong-session quote: report kept',
        rep['MSTR']['source'] == 'kept', str(rep['MSTR']))

    # 20. Regular-hours edges: 09:30 (open) accepted, 09:29 rejected.
    stocks = good_stocks()
    rep = fb(['MSTR'], stocks, make_fetch(
        {'MSTR': yahoo_ok('MSTR', 130.0, 129.0, t=ep(2026, 11, 6, 9, 30))}),
        now=dt.datetime(2026, 11, 6, 9, 35, tzinfo=ET))
    chk('quote at 09:30 open: applied',
        stocks['MSTR']['c'] == 130.0
        and rep['MSTR']['source'] == 'yahoo', str(rep['MSTR']))
    stocks = good_stocks()
    rep = fb(['MSTR'], stocks, make_fetch(
        {'MSTR': yahoo_ok('MSTR', 130.0, 129.0, t=ep(2026, 11, 6, 9, 29))}),
        now=dt.datetime(2026, 11, 6, 9, 35, tzinfo=ET))
    chk('quote at 09:29 (pre-market): kept',
        stocks['MSTR']['c'] == 128.93
        and rep['MSTR']['source'] == 'kept', str(rep['MSTR']))

    # 23. Early-close day (correction 5, Grok Bot review 6 Nov 2026):
    #     Fri 2026-11-27 is an early-close day (market closes 13:00
    #     ET), but the fallback has no holiday / early-close calendar,
    #     so a FRESH afternoon quote (14:00 ET, 5 min old, same ET
    #     session) is ACCEPTED under the plain 09:30-16:00 ET rule —
    #     not rejected. The earlier docs wrongly claimed rejection.
    #     Bars: Wed 2026-11-25 and Thu 2026-11-26 09:30 ET; the prior
    #     close is the Thu bar's close (129.0), derived from timestamps.
    stocks = good_stocks()
    rep = fb(['MSTR'], stocks, make_fetch(
        {'MSTR': yahoo_ok('MSTR', 130.0, 129.0, t=ep(2026, 11, 27, 14, 0),
                          ts=[ep(2026, 11, 25, 9, 30),
                              ep(2026, 11, 26, 9, 30)])}),
        now=dt.datetime(2026, 11, 27, 14, 5, tzinfo=ET))
    chk('early-close day fresh 14:00 ET quote: applied',
        stocks['MSTR']['c'] == 130.0
        and stocks['MSTR']['pc'] == 129.0
        and rep['MSTR']['source'] == 'yahoo', str(rep['MSTR']))

    # --- r2: safe finite-only atomic writes ---
    # 21. _atomic_write_json writes valid JSON, leaves no temp files,
    #     and refuses non-finite numbers WITHOUT touching the target.
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, 'out.json')
        open(p, 'w').write('{"keep": true}\n')
        LF._atomic_write_json(p, {'a': 1, 'b': [1.5, 2]})
        chk('atomic write: valid data written',
            json.load(open(p)) == {'a': 1, 'b': [1.5, 2]})
        chk('atomic write: no temp files left',
            [f for f in os.listdir(tmp)
             if f.startswith('.live-fallback-')] == [], str(os.listdir(tmp)))
        try:
            LF._atomic_write_json(p, {'a': float('nan')})
            raised = False
        except ValueError:
            raised = True
        chk('atomic write: NaN raises, target untouched',
            raised and json.load(open(p)) == {'a': 1, 'b': [1.5, 2]})
        chk('atomic write: no temp file left after failure',
            [f for f in os.listdir(tmp)
             if f.startswith('.live-fallback-')] == [], str(os.listdir(tmp)))

    # 22. CLI: a prices.json carrying a non-finite value exits 1 and
    #     the file is byte-identical afterwards (never half-written);
    #     a bad --now exits 2. The NaN sits in TSLA, which is NOT in
    #     --failed, so it survives whatever Yahoo does for MSTR — the
    #     write must refuse the file either way. --now is pinned to
    #     Sat 2026-11-07 so MSTR is kept (stale Friday quote).
    with tempfile.TemporaryDirectory() as tmp:
        pp = os.path.join(tmp, 'prices.json')
        tool = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            '..', 'tools', 'live_fallback.py')
        open(pp, 'w').write('{"updated": "2026-11-06T23:57:10Z", '
                            '"stocks": {"MSTR": {"c": 128.93, "pc": 129.3, '
                            '"t": 1793912400}, "TSLA": {"c": NaN, '
                            '"pc": 343.69, "t": 1793912400}}}')
        before = open(pp).read()
        r = subprocess.run(
            [sys.executable, tool, '--prices', pp, '--failed', 'MSTR',
             '--now', '2026-11-07T12:00:00Z'],
            capture_output=True, text=True)
        chk('CLI non-finite prices.json: exit 1, file untouched',
            r.returncode == 1 and open(pp).read() == before,
            r.stderr.strip()[:200])
        r = subprocess.run(
            [sys.executable, tool, '--prices', pp, '--failed', 'MSTR',
             '--now', 'not-a-date'],
            capture_output=True, text=True)
        chk('CLI bad --now: exit 2', r.returncode == 2)

    bad = [x for x in R if not x[1]]
    print('\n%d checks, %d failed' % (len(R), len(bad)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
