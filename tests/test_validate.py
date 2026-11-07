#!/usr/bin/env python3
"""Tests for tools/validate.py (Python supercharge slice 1).

Pure Python, no network, no browser. Builds synthetic good data, then
mutates one thing at a time and proves the gate passes on good data and
holds (keeping the previous file) on each class of bad data.
usage: python3 tests/test_validate.py   exit 0 = all pass
"""
import copy
import json
import os
import subprocess
import sys
import tempfile
import datetime as dt

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
import validate as V

R = []


def chk(name, ok, detail=''):
    R.append((name, bool(ok), detail))
    print('%-58s %s %s' % (name, 'PASS' if ok else 'FAIL', detail))


def good_history():
    closes = {}
    base = {'BTC': 75000.0, 'MSTR': 130.0, 'STRC': 99.5, 'TSLA': 350.0,
            'PLTR': 160.0, 'SPY': 730.0, 'QQQ': 650.0, 'BRK.B': 570.0, 'GLD': 370.0}
    for i, d in enumerate(['2026-11-02', '2026-11-03', '2026-11-04',
                           '2026-11-05', '2026-11-06']):
        row = {s: round(v * (1 + 0.002 * i), 2) for s, v in base.items()}
        closes[d] = row
    return {
        'v': 1, 'base': '2025-12-31', 'source': 'Yahoo Finance chart API (unadjusted close)',
        'updated': '2026-11-06T23:00:30Z',
        'closes': closes,
        'btc_provisional': ['2026-11-06'],
        'fallback_sources': {'2026-11-06': {'BTC': 'coinbase'}},
        'tiingo_ref': {'2026-11-05': {'BTC': {'v': 75400.0, 't': '2026-11-06T00:20:24Z'},
                                      'TSLA': {'v': 352.0, 't': '2026-11-06T00:20:24Z'}}},
        'tiingo_flags': [],
        'divs': {'SPY': {'2026-09-18': 1.889}},
        'revisions_ignored': [],
    }


def good_prices():
    stocks = {}
    for s, c, pc in [('MSTR', 128.93, 129.3), ('STRC', 99.84, 99.56),
                     ('TSLA', 358.22, 343.69), ('PLTR', 160.38, 154.99),
                     ('SPY', 735.29, 733.0), ('QQQ', 656.1, 647.05),
                     ('BRK.B', 570.89, 572.33), ('GLD', 372.52, 375.49),
                     ('IBIT', 42.88, 43.03), ('FBTC', 65.9, 66.17),
                     ('MU', 690.0, 656.39), ('META', 610.15, 605.08),
                     ('SPCX', 134.27, 123.62), ('WTI', 90.34, 90.52),
                     ('US10Y', 4.859, 4.837), ('VIX', 25.64, 28.18),
                     ('GOLD', 4079.5, 4113.5)]:
        stocks[s] = {'c': c, 'pc': pc, 't': 1793998800}
    return {'updated': '2026-11-06T23:15:19Z',
            'btc': {'usd': 75835, 'chg24h': 0.64, 'src': 'CoinGecko',
                    'time': '2026-11-06T23:15:19Z'},
            'stocks': stocks,
            'monthEnd': {'date': '2026-10-30', 'month': '2026-10',
                         'calendar_end': '2026-10-31', 'bar_dates': {}}}


GOOD_LEDGER = """/* STRC declared dividends: [record, ex-date, scheduled pay date, $/share] */
var STRC_DIVS = [
  ['2026-11-01', '2026-11-01', '2026-11-02', 0.0333333333],
  ['2026-11-02', '2026-11-02', '2026-11-03', 0.0333333333],
  ['2026-11-03', '2026-11-03', '2026-11-04', 0.0333333333],
];
"""

NOW = dt.datetime(2026, 11, 6, 23, 30, tzinfo=dt.timezone.utc)


def run_cli(tmp, hist, prices, ledger=None, prev_hist=None, prev_prices=None,
            publish=False, now=NOW):
    """Write the fixtures, run validate.main(), return (exit_code, health)."""
    hp = os.path.join(tmp, 'history.json')
    pp = os.path.join(tmp, 'prices.json')
    with open(hp, 'w') as f:
        f.write(hist if isinstance(hist, str) else json.dumps(hist))
    with open(pp, 'w') as f:
        f.write(prices if isinstance(prices, str) else json.dumps(prices))
    args = ['--history', hp, '--prices', pp, '--now', now.strftime('%Y-%m-%dT%H:%M:%SZ'),
            '--out-health', os.path.join(tmp, 'health.json')]
    if ledger is not None:
        lp = os.path.join(tmp, 'ledger.js')
        open(lp, 'w').write(ledger)
        args += ['--ledger', lp]
    if prev_hist is not None:
        ph = os.path.join(tmp, 'prev_history.json')
        open(ph, 'w').write(prev_hist if isinstance(prev_hist, str) else json.dumps(prev_hist))
        args += ['--prev-history', ph]
    if prev_prices is not None:
        ppr = os.path.join(tmp, 'prev_prices.json')
        open(ppr, 'w').write(prev_prices if isinstance(prev_prices, str) else json.dumps(prev_prices))
        args += ['--prev-prices', ppr]
    pubdir = None
    if publish:
        pubdir = os.path.join(tmp, 'published')
        os.makedirs(pubdir, exist_ok=True)
        if prev_hist is not None:
            open(os.path.join(pubdir, 'history.json'), 'w').write(
                prev_hist if isinstance(prev_hist, str) else json.dumps(prev_hist))
        if prev_prices is not None:
            open(os.path.join(pubdir, 'prices.json'), 'w').write(
                prev_prices if isinstance(prev_prices, str) else json.dumps(prev_prices))
        args += ['--publish-to', pubdir]
    code = V.main(args)
    health = json.load(open(os.path.join(tmp, 'health.json')))
    return code, health, pubdir


def main():
    tmp = tempfile.mkdtemp(prefix='validate-test-')
    gh, gp = good_history(), good_prices()

    # 1. Good data passes, health says ok, all 7 checks present.
    code, health, _ = run_cli(tmp, gh, gp, ledger=GOOD_LEDGER,
                              prev_hist=gh, prev_prices=gp)
    chk('good data: exit 0', code == 0, 'exit=%s' % code)
    chk('good data: health status ok', health['status'] == 'ok')
    names = [r['check'] for r in health['validation']]
    chk('good data: all 8 checks ran',
        names == ['parse', 'sessions', 'values', 'jumps', 'tiingo', 'provisional', 'dividends',
                  'inclusion'],
        ','.join(names))
    chk('good data: no fails or holds',
        all(r['status'] in ('pass', 'flag', 'skip') for r in health['validation']))
    chk('good data: BTC provisional in health',
        health['symbols']['BTC']['provisional'] is True
        and health['symbols']['BTC']['source'] == 'coinbase'
        and health['symbols']['BTC']['last_close_date'] == '2026-11-06',
        str(health['symbols']['BTC']))
    chk('good data: stock source yahoo',
        health['symbols']['TSLA']['source'] == 'yahoo'
        and health['symbols']['TSLA']['last_close_date'] == '2026-11-06')
    chk('good data: live-only symbol present',
        health['symbols']['IBIT']['source'] == 'live'
        and health['symbols']['IBIT']['last_close_date'] == '2026-11-06')

    # 2. Publish-or-hold on good data: candidate replaces the published file.
    code, health, pubdir = run_cli(tmp, gh, gp, ledger=GOOD_LEDGER,
                                   prev_hist=gh, prev_prices=gp, publish=True)
    pub_hist = json.load(open(os.path.join(pubdir, 'history.json')))
    chk('publish on pass: candidate published',
        code == 0 and pub_hist['closes']['2026-11-06']['BTC'] == gh['closes']['2026-11-06']['BTC'])

    # 3. Each bad-data class holds, names the right check, keeps the old file.
    cases = []

    h = copy.deepcopy(gh)
    cases.append(('parse: truncated history.json', '{invalid json', gp, None, ['parse']))

    h = copy.deepcopy(gh)
    del h['closes']['2026-11-04']
    # A missing session also shrinks the history vs published and drops a
    # published date, so parse (shrink), sessions and inclusion all fail —
    # intentional defence in depth.
    cases.append(('sessions: missing 2026-11-04', h, gp, GOOD_LEDGER,
                  ['parse', 'sessions', 'inclusion']))
    h = copy.deepcopy(gh)
    h['closes']['2026-11-05']['TSLA'] = 0
    cases.append(('values: zero TSLA close', h, gp, GOOD_LEDGER, ['values']))

    h = copy.deepcopy(gh)
    h['closes']['2026-11-05']['TSLA'] = None
    cases.append(('values: null TSLA close', h, gp, GOOD_LEDGER, ['values']))

    h = copy.deepcopy(gh)
    h['closes']['2026-11-05']['TSLA'] = round(h['closes']['2026-11-04']['TSLA'] * 1.5, 2)
    cases.append(('jumps: TSLA +50% in one session', h, gp, GOOD_LEDGER, ['jumps']))

    h = copy.deepcopy(gh)
    # 2026-11-06's UTC day is still open at NOW (23:30Z; final at 00:20Z),
    # so an untagged fallback there must hold. (A fallback on a FINAL date
    # untagged is legitimate — see the rework-2 tests below.)
    h['fallback_sources'] = {'2026-11-06': {'BTC': 'coinbase'}}
    h['btc_provisional'] = []
    cases.append(('provisional: BTC fallback untagged on open day', h, gp, GOOD_LEDGER,
                  ['provisional']))

    h = copy.deepcopy(gh)
    h['btc_provisional'] = ['2026-11-09']
    cases.append(('provisional: tag for a date with no BTC close',
                  h, gp, GOOD_LEDGER, ['provisional']))

    bad_ledger = GOOD_LEDGER.replace(
        "['2026-11-02', '2026-11-02', '2026-11-03', 0.0333333333]",
        "['2026-11-03', '2026-11-02', '2026-11-02', 0.0333333333]")
    cases.append(('dividends: pay before record', gh, gp, bad_ledger, ['dividends']))

    dup_ledger = GOOD_LEDGER.replace(
        "['2026-11-03', '2026-11-03', '2026-11-04', 0.0333333333]",
        "['2026-11-02', '2026-11-02', '2026-11-04', 0.0333333333]")
    cases.append(('dividends: duplicate ex-date', gh, gp, dup_ledger, ['dividends']))

    h = copy.deepcopy(gh)
    del h['closes']['2026-11-06']
    del h['closes']['2026-11-05']
    h['btc_provisional'] = []
    h['fallback_sources'] = {}
    # Dropping 2026-11-05 also orphans its tiingo_ref entry (a confirmation
    # for a date with no close), so tiingo fails too — a dangling
    # confirmation must not pass silently.
    cases.append(('parse: history shrank vs published', h, gp, GOOD_LEDGER,
                  ['parse', 'tiingo', 'inclusion']))

    for name, hist, prices, ledger, want in cases:
        code, health, pubdir = run_cli(tmp, hist, prices, ledger=ledger,
                                       prev_hist=gh, prev_prices=gp, publish=True)
        got = [r['check'] for r in health['validation'] if r['status'] == 'fail']
        kept = json.load(open(os.path.join(pubdir, 'history.json')))
        chk('%s: exit 1 + held' % name, code == 1 and health['status'] == 'held',
            'exit=%s status=%s' % (code, health['status']))
        chk('%s: fails %s' % (name, want), got == want, 'got=%s' % got)
        chk('%s: hold_reason names %s' % (name, want),
            all(w in (health.get('hold_reason') or '') for w in want))
        chk('%s: previous file kept' % name,
            kept['closes'] == gh['closes'], 'published closes unchanged')

    # 4. Tiingo disagreement flags but does NOT hold (reference-only).
    h = copy.deepcopy(gh)
    h['tiingo_ref']['2026-11-05']['TSLA']['v'] = 360.0  # ~2.4% away, over 0.05%
    code, health, pubdir = run_cli(tmp, h, gp, ledger=GOOD_LEDGER,
                                   prev_hist=gh, prev_prices=gp, publish=True)
    tg = [r for r in health['validation'] if r['check'] == 'tiingo'][0]
    chk('tiingo: disagreement flags, does not hold',
        code == 0 and health['status'] == 'ok' and tg['status'] == 'flag',
        'exit=%s status=%s tiingo=%s' % (code, health['status'], tg['status']))
    chk('tiingo: flag names the symbol/date', 'TSLA' in tg['detail'] and '2026-11-05' in tg['detail'])
    pub_hist = json.load(open(os.path.join(pubdir, 'history.json')))
    chk('tiingo: candidate still published',
        pub_hist['closes']['2026-11-06']['BTC'] == gh['closes']['2026-11-06']['BTC'])

    # 5. No ledger supplied: dividends check skips the STRC part, does not fail.
    code, health, _ = run_cli(tmp, gh, gp, ledger=None, prev_hist=gh, prev_prices=gp)
    dv = [r for r in health['validation'] if r['check'] == 'dividends'][0]
    chk('dividends: no ledger -> skip, run still passes',
        code == 0 and dv['status'] == 'skip', 'exit=%s dividends=%s' % (code, dv['status']))

    # 6. Amounts are NOT adjudicated: a $0.03 November amount must not fail.
    amt_ledger = GOOD_LEDGER.replace('0.0333333333', '0.03')
    code, health, _ = run_cli(tmp, gh, gp, ledger=amt_ledger, prev_hist=gh, prev_prices=gp)
    dv = [r for r in health['validation'] if r['check'] == 'dividends'][0]
    chk('dividends: $0.03 amounts do not fail (open decision)',
        code == 0 and dv['status'] == 'pass', 'exit=%s dividends=%s' % (code, dv['status']))

    # 7. CLI smoke test as a real subprocess.
    hp = os.path.join(tmp, 'history.json')
    pp = os.path.join(tmp, 'prices.json')
    json.dump(gh, open(hp, 'w'))
    json.dump(gp, open(pp, 'w'))
    lp = os.path.join(tmp, 'ledger.js')
    open(lp, 'w').write(GOOD_LEDGER)
    r = subprocess.run([sys.executable,
                        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     '..', 'tools', 'validate.py'),
                        '--history', hp, '--prices', pp, '--ledger', lp,
                        '--out-health', os.path.join(tmp, 'health2.json')],
                       capture_output=True, text=True)
    chk('CLI subprocess: exit 0 on good data', r.returncode == 0, r.stderr.strip()[:200])

    # 8. Rework 2 (Grok Bot review #2).
    NOW2 = dt.datetime(2026, 11, 7, 0, 30, tzinfo=dt.timezone.utc)  # past 2026-11-06 finality

    # 8a. Atomic publish: a failure BETWEEN the two writes leaves the old pair.
    pubdir2 = os.path.join(tmp, 'pub-atomic')
    os.makedirs(pubdir2, exist_ok=True)
    prev_h_bytes = json.dumps(gh).encode()
    prev_p_bytes = json.dumps(gp).encode()
    prev_health_bytes = b'{"status": "ok"}\n'
    open(os.path.join(pubdir2, 'history.json'), 'wb').write(prev_h_bytes)
    open(os.path.join(pubdir2, 'prices.json'), 'wb').write(prev_p_bytes)
    open(os.path.join(pubdir2, 'health.json'), 'wb').write(prev_health_bytes)
    h2 = copy.deepcopy(gh)
    h2['closes']['2026-11-06']['BTC'] = 76000.0
    hp2 = os.path.join(tmp, 'history2.json')
    json.dump(h2, open(hp2, 'w'))
    pp2 = os.path.join(tmp, 'prices2.json')
    json.dump(gp, open(pp2, 'w'))
    hh2 = os.path.join(tmp, 'health2x.json')
    open(hh2, 'w').write('{"status": "ok"}\n')
    calls = {'n': 0}
    real_replace = V._replace

    def flaky_replace(src, dst):
        calls['n'] += 1
        if calls['n'] == 2:
            raise RuntimeError('injected failure between writes')
        return real_replace(src, dst)

    V._replace = flaky_replace
    try:
        try:
            V.publish_snapshot([(hp2, 'history.json'), (pp2, 'prices.json'),
                                (hh2, 'health.json')], pubdir2)
            raised = False
        except V.PublishError:
            raised = True
    finally:
        V._replace = real_replace
    chk('atomic publish: failure between writes raises PublishError', raised)
    chk('atomic publish: old history kept byte-identical',
        open(os.path.join(pubdir2, 'history.json'), 'rb').read() == prev_h_bytes)
    chk('atomic publish: old prices kept byte-identical',
        open(os.path.join(pubdir2, 'prices.json'), 'rb').read() == prev_p_bytes)
    chk('atomic publish: old health kept byte-identical',
        open(os.path.join(pubdir2, 'health.json'), 'rb').read() == prev_health_bytes)
    chk('atomic publish: no temp files left behind',
        not [f for f in os.listdir(pubdir2) if '.tmp-' in f],
        str(os.listdir(pubdir2)))
    names = V.publish_snapshot([(hp2, 'history.json'), (pp2, 'prices.json'),
                                (hh2, 'health.json')], pubdir2)
    chk('atomic publish: clean publish lands the whole new snapshot',
        names == ['history.json', 'prices.json', 'health.json']
        and json.load(open(os.path.join(pubdir2, 'history.json')))['closes']['2026-11-06']['BTC'] == 76000.0
        and json.load(open(os.path.join(pubdir2, 'health.json')))['status'] == 'ok')

    # 8b. Safe health writes: a failure mid-write leaves the previous health intact.
    hh = os.path.join(tmp, 'health-safe.json')
    V.atomic_write(hh, b'{"status": "ok"}\n')
    calls['n'] = 1  # the next _replace (this write's rename) is call #2: fails
    V._replace = flaky_replace
    try:
        try:
            V.atomic_write(hh, b'{"status": "held"}\n')
            raised = False
        except RuntimeError:
            raised = True
    finally:
        V._replace = real_replace
    chk('safe health write: failure mid-write raises', raised)
    chk('safe health write: previous health kept byte-identical',
        open(hh, 'rb').read() == b'{"status": "ok"}\n')
    chk('safe health write: no temp files left behind',
        not [f for f in os.listdir(tmp) if f.startswith('.health-safe.json.tmp-')],
        str([f for f in os.listdir(tmp) if 'health-safe' in f]))

    # 8b2. End to end: a publish failure inside main() exits 1, old pair kept.
    pubdir3 = os.path.join(tmp, 'pub-e2e')
    os.makedirs(pubdir3, exist_ok=True)
    open(os.path.join(pubdir3, 'history.json'), 'wb').write(prev_h_bytes)
    open(os.path.join(pubdir3, 'prices.json'), 'wb').write(prev_p_bytes)
    open(os.path.join(pubdir3, 'health.json'), 'wb').write(prev_health_bytes)
    hp3 = os.path.join(tmp, 'history3.json')
    json.dump(gh, open(hp3, 'w'))
    pp3 = os.path.join(tmp, 'prices3.json')
    json.dump(gp, open(pp3, 'w'))
    calls['n'] = 0  # call #1: health write; call #2: first install -> fails
    V._replace = flaky_replace
    try:
        code = V.main(['--history', hp3, '--prices', pp3, '--ledger',
                       os.path.join(tmp, 'ledger.js'),
                       '--now', NOW.strftime('%Y-%m-%dT%H:%M:%SZ'),
                       '--out-health', os.path.join(tmp, 'health-e2e.json'),
                       '--publish-to', pubdir3])
    finally:
        V._replace = real_replace
    chk('atomic publish (main): publish failure exits 1', code == 1, 'exit=%s' % code)
    chk('atomic publish (main): old history kept byte-identical',
        open(os.path.join(pubdir3, 'history.json'), 'rb').read() == prev_h_bytes)
    chk('atomic publish (main): old prices kept byte-identical',
        open(os.path.join(pubdir3, 'prices.json'), 'rb').read() == prev_p_bytes)
    chk('atomic publish (main): old health kept byte-identical',
        open(os.path.join(pubdir3, 'health.json'), 'rb').read() == prev_health_bytes)

    # 8b3. On a hold, only health.json is published (hold visible, data untouched).
    h_bad = copy.deepcopy(gh)
    h_bad['closes']['2026-11-05']['TSLA'] = 0
    code, health, pubdir = run_cli(tmp, h_bad, gp, ledger=GOOD_LEDGER,
                                   prev_hist=gh, prev_prices=gp, publish=True)
    chk('hold publish: health.json published with status held',
        code == 1 and json.load(open(os.path.join(pubdir, 'health.json')))['status'] == 'held')
    chk('hold publish: previous history still the published file',
        json.load(open(os.path.join(pubdir, 'history.json')))['closes'] == gh['closes'])

    # 8c. Inclusion: counts looking right must not hide a dropped date/symbol.
    h = copy.deepcopy(gh)
    for d in h['closes']:
        del h['closes'][d]['TSLA']
    del h['tiingo_ref']['2026-11-05']['TSLA']  # isolate: no dangling confirmation
    code, health, _ = run_cli(tmp, h, gp, ledger=GOOD_LEDGER,
                              prev_hist=gh, prev_prices=gp)
    got = [r['check'] for r in health['validation'] if r['status'] == 'fail']
    chk('inclusion: TSLA dropped from every session fails (counts unchanged)',
        code == 1 and got == ['inclusion'], 'got=%s' % got)
    chk('inclusion: hold_reason names the core symbol',
        'TSLA' in (health.get('hold_reason') or ''))

    h = copy.deepcopy(gh)
    del h['closes']['2026-11-04']
    prev4 = copy.deepcopy(gh)
    del prev4['closes']['2026-11-06']  # same count as the candidate (4), different set
    code, health, _ = run_cli(tmp, h, gp, ledger=GOOD_LEDGER,
                              prev_hist=prev4, prev_prices=gp)
    got = [r['check'] for r in health['validation'] if r['status'] == 'fail']
    chk('inclusion: dropped date fails even when the count matches',
        code == 1 and got == ['sessions', 'inclusion'], 'got=%s' % got)
    chk('inclusion: hold_reason names the dropped date',
        '2026-11-04' in (health.get('hold_reason') or ''))

    p = copy.deepcopy(gp)
    del p['stocks']['MU']
    code, health, _ = run_cli(tmp, gh, p, ledger=GOOD_LEDGER,
                              prev_hist=gh, prev_prices=gp)
    got = [r['check'] for r in health['validation'] if r['status'] == 'fail']
    chk('inclusion: dropped live symbol fails',
        code == 1 and got == ['parse', 'inclusion'], 'got=%s' % got)
    chk('inclusion: hold_reason names the dropped live symbol',
        'MU' in (health.get('hold_reason') or ''))

    # 8d. Legitimate Yahoo replacement: a Yahoo final bar replacing a
    # fallback/provisional BTC value passes (value may change, tag drops).
    prev_r = copy.deepcopy(gh)
    prev_r['closes']['2026-11-06']['BTC'] = 75731.04
    prev_r['btc_provisional'] = []
    prev_r['tiingo_ref']['2026-11-06'] = {'BTC': {'v': 75732.244103,
                                                  't': '2026-11-07T00:20:19Z'}}
    h = copy.deepcopy(gh)
    h['closes']['2026-11-06']['BTC'] = 76200.0
    h['btc_provisional'] = []
    h['fallback_sources'] = {}
    h['tiingo_ref']['2026-11-06'] = {'BTC': {'v': 75732.244103,
                                             't': '2026-11-07T00:20:19Z'}}
    code, health, _ = run_cli(tmp, h, gp, ledger=GOOD_LEDGER,
                              prev_hist=prev_r, prev_prices=gp, now=NOW2)
    tg = [r for r in health['validation'] if r['check'] == 'tiingo'][0]
    inc = [r for r in health['validation'] if r['check'] == 'inclusion'][0]
    chk('yahoo replacement: exit 0, run passes',
        code == 0 and health['status'] == 'ok', 'exit=%s' % code)
    chk('yahoo replacement: tiingo flags (not holds) the stale confirmation',
        tg['status'] == 'flag' and 'previously published value' in tg['detail'],
        tg['detail'])
    chk('yahoo replacement: inclusion names it legitimate',
        inc['status'] == 'pass' and 'legitimate Yahoo replacement' in inc['detail'],
        inc['detail'])

    # 8e. Today's real-data shape: fallback BTC on a FINAL date, untagged, passes.
    h = copy.deepcopy(gh)
    h['btc_provisional'] = []
    code, health, _ = run_cli(tmp, h, gp, ledger=GOOD_LEDGER,
                              prev_hist=gh, prev_prices=gp, now=NOW2)
    pv = [r for r in health['validation'] if r['check'] == 'provisional'][0]
    chk('provisional: fallback on a final date, untagged, passes',
        code == 0 and pv['status'] == 'pass', 'exit=%s prov=%s' % (code, pv['status']))

    # 8f. A stale provisional tag (final date still tagged) flags, never holds.
    h = copy.deepcopy(gh)
    code, health, _ = run_cli(tmp, h, gp, ledger=GOOD_LEDGER,
                              prev_hist=gh, prev_prices=gp, now=NOW2)
    pv = [r for r in health['validation'] if r['check'] == 'provisional'][0]
    chk('provisional: stale tag on a final date flags, does not hold',
        code == 0 and pv['status'] == 'flag', 'exit=%s prov=%s' % (code, pv['status']))

    # 8g. Tiingo confirmations: malformed or mismatched must FAIL, not pass silently.
    tg_cases = []
    h = copy.deepcopy(gh)
    h['tiingo_ref']['2026-11-05']['TSLA']['v'] = '352.0'
    tg_cases.append(('tiingo: non-numeric value', h))
    h = copy.deepcopy(gh)
    h['tiingo_ref']['2026-11-01'] = {'BTC': {'v': 75000.0, 't': '2026-11-06T00:20:24Z'}}
    tg_cases.append(('tiingo: entry for a date with no close', h))
    h = copy.deepcopy(gh)
    h['tiingo_ref']['2026-11-05']['NOPE'] = {'v': 1.0, 't': '2026-11-06T00:20:24Z'}
    tg_cases.append(('tiingo: entry for a symbol with no close', h))
    h = copy.deepcopy(gh)
    del h['tiingo_ref']['2026-11-05']['BTC']['t']
    tg_cases.append(('tiingo: missing timestamp', h))
    h = copy.deepcopy(gh)
    h['tiingo_ref']['2026-11-06'] = {'BTC': {'v': 75732.0, 't': '2026-11-07T00:20:19Z'}}
    tg_cases.append(('tiingo: BTC confirmation for a provisional date', h))
    for name, hist in tg_cases:
        code, health, _ = run_cli(tmp, hist, gp, ledger=GOOD_LEDGER,
                                  prev_hist=gh, prev_prices=gp)
        got = [r['check'] for r in health['validation'] if r['status'] == 'fail']
        chk('%s: exit 1, fails tiingo' % name,
            code == 1 and got == ['tiingo'], 'got=%s' % got)
    # A recorded miss (v null, valid timestamp) is not a failure.
    h = copy.deepcopy(gh)
    h['tiingo_ref']['2026-11-05']['BTC'] = {'v': None, 't': '2026-11-06T00:20:24Z'}
    code, health, _ = run_cli(tmp, h, gp, ledger=GOOD_LEDGER,
                              prev_hist=gh, prev_prices=gp)
    tg = [r for r in health['validation'] if r['check'] == 'tiingo'][0]
    chk('tiingo: recorded miss (v null) passes',
        code == 0 and tg['status'] == 'pass', 'exit=%s tiingo=%s' % (code, tg['status']))

    bad = [x for x in R if not x[1]]
    print('\n%d checks, %d failed' % (len(R), len(bad)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
