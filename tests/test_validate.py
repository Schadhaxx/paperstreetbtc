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
_pub_n = [0]


def chk(name, ok, detail=''):
    R.append((name, bool(ok), detail))
    print('%-58s %s %s' % (name, 'PASS' if ok else 'FAIL', detail))


def git_out(pubdir, *args):
    return subprocess.run(['git', '-C', pubdir] + list(args),
                          capture_output=True, text=True)


def git_tree(pubdir, ref='HEAD'):
    """{name: bytes} of the tree at ref (HEAD by default)."""
    out = {}
    r = git_out(pubdir, 'ls-tree', '-r', '--name-only', ref)
    for name in r.stdout.split():
        out[name] = subprocess.run(['git', '-C', pubdir, 'show', '%s:%s' % (ref, name)],
                                   capture_output=True).stdout
    return out


def git_head_count(pubdir):
    return int(git_out(pubdir, 'rev-list', '--count', 'HEAD').stdout.strip())


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
        # The publish target is a temp git repo (the data-branch checkout):
        # the previous files are committed as the initial published
        # snapshot, so publish_snapshot() can make its one commit on top.
        # A fresh repo per call, so no call's commits leak into the next.
        _pub_n[0] += 1
        pubdir = os.path.join(tmp, 'published-%d' % _pub_n[0])
        os.makedirs(pubdir)
        subprocess.run(['git', 'init', '-q', pubdir], check=True, capture_output=True)
        # Local identity: in production the workflow sets this (identity is
        # the caller's job); the test repo needs it for publish_snapshot's
        # plain `git commit` to succeed.
        subprocess.run(['git', '-C', pubdir, 'config', 'user.name', 'validate-test'],
                       check=True, capture_output=True)
        subprocess.run(['git', '-C', pubdir, 'config', 'user.email',
                        'validate-test@example.com'], check=True, capture_output=True)
        if prev_hist is not None:
            open(os.path.join(pubdir, 'history.json'), 'w').write(
                prev_hist if isinstance(prev_hist, str) else json.dumps(prev_hist))
        if prev_prices is not None:
            open(os.path.join(pubdir, 'prices.json'), 'w').write(
                prev_prices if isinstance(prev_prices, str) else json.dumps(prev_prices))
        if os.listdir(pubdir):
            subprocess.run(['git', '-C', pubdir, 'add', '-A'], check=True,
                           capture_output=True)
            subprocess.run(['git', '-C', pubdir, '-c', 'user.name=validate-test',
                            '-c', 'user.email=validate-test@example.com',
                            'commit', '-q', '-m', 'initial published snapshot'],
                           check=True, capture_output=True)
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

    # 8a. Single-commit publish (Grok Bot correction 3): a kill AT the
    # commit leaves HEAD untouched, and a clean re-run lands exactly ONE
    # new commit carrying the whole new generation. The old sequential-
    # rename tests (failure injected between two writes) are superseded:
    # there is no between-writes window any more — the ref moves once,
    # at the commit.
    def make_pub_repo(dirname, hist_bytes, prices_bytes, health_bytes):
        d = os.path.join(tmp, dirname)
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, 'history.json'), 'wb').write(hist_bytes)
        open(os.path.join(d, 'prices.json'), 'wb').write(prices_bytes)
        open(os.path.join(d, 'health.json'), 'wb').write(health_bytes)
        subprocess.run(['git', 'init', '-q', d], check=True, capture_output=True)
        subprocess.run(['git', '-C', d, 'config', 'user.name', 'validate-test'],
                       check=True, capture_output=True)
        subprocess.run(['git', '-C', d, 'config', 'user.email',
                        'validate-test@example.com'], check=True, capture_output=True)
        subprocess.run(['git', '-C', d, 'add', '-A'], check=True, capture_output=True)
        subprocess.run(['git', '-C', d, '-c', 'user.name=validate-test',
                        '-c', 'user.email=validate-test@example.com',
                        'commit', '-q', '-m', 'initial published snapshot'],
                       check=True, capture_output=True)
        return d

    prev_h_bytes = json.dumps(gh).encode()
    prev_p_bytes = json.dumps(gp).encode()
    prev_health_bytes = b'{"status": "ok"}\n'
    pubdir2 = make_pub_repo('pub-commit', prev_h_bytes, prev_p_bytes, prev_health_bytes)
    old_head = git_out(pubdir2, 'rev-parse', 'HEAD').stdout.strip()
    old_tree = git_tree(pubdir2)
    h2 = copy.deepcopy(gh)
    h2['closes']['2026-11-06']['BTC'] = 76000.0
    hp2 = os.path.join(tmp, 'history2.json')
    json.dump(h2, open(hp2, 'w'))
    pp2 = os.path.join(tmp, 'prices2.json')
    gp2 = copy.deepcopy(gp)
    gp2['btc']['usd'] = 76000  # the new generation changes all three files
    json.dump(gp2, open(pp2, 'w'))
    hh2 = os.path.join(tmp, 'health2x.json')
    open(hh2, 'w').write('{"status": "ok", "gen": 2}\n')
    calls = {'n': 0}
    real_replace = V._replace

    def flaky_replace(src, dst):
        calls['n'] += 1
        if calls['n'] == 2:
            raise RuntimeError('injected failure between writes')
        return real_replace(src, dst)

    real_run_git = V._run_git

    def flaky_git(args, cwd):
        if args and args[0] == 'commit':
            raise KeyboardInterrupt('injected kill at commit')
        return real_run_git(args, cwd)

    V._run_git = flaky_git
    try:
        try:
            V.publish_snapshot([(hp2, 'history.json'), (pp2, 'prices.json'),
                                (hh2, 'health.json')], pubdir2,
                               message='test snapshot')
            raised = False
        except KeyboardInterrupt:
            raised = True
    finally:
        V._run_git = real_run_git
    chk('single-commit publish: kill at commit re-raises KeyboardInterrupt', raised)
    chk('single-commit publish: HEAD unchanged after the kill',
        git_out(pubdir2, 'rev-parse', 'HEAD').stdout.strip() == old_head)
    chk('single-commit publish: HEAD tree byte-identical after the kill',
        git_tree(pubdir2) == old_tree)
    chk('single-commit publish: working tree restored to the old files',
        open(os.path.join(pubdir2, 'history.json'), 'rb').read() == prev_h_bytes
        and open(os.path.join(pubdir2, 'prices.json'), 'rb').read() == prev_p_bytes
        and open(os.path.join(pubdir2, 'health.json'), 'rb').read() == prev_health_bytes)
    chk('single-commit publish: index clean after the kill (git status empty)',
        git_out(pubdir2, 'status', '--porcelain').stdout.strip() == '')
    chk('single-commit publish: no temp files left behind',
        not [f for f in os.listdir(pubdir2) if '.tmp-' in f],
        str(os.listdir(pubdir2)))
    # Clean re-run: exactly ONE new commit on the old HEAD, tree = new generation.
    names, committed = V.publish_snapshot([(hp2, 'history.json'), (pp2, 'prices.json'),
                                           (hh2, 'health.json')], pubdir2,
                                          message='test snapshot')
    new_head = git_out(pubdir2, 'rev-parse', 'HEAD').stdout.strip()
    chk('single-commit publish: clean publish reports committed',
        committed is True and names == ['history.json', 'prices.json', 'health.json'])
    chk('single-commit publish: exactly one new commit on the old HEAD',
        git_head_count(pubdir2) == 2
        and git_out(pubdir2, 'rev-parse', 'HEAD~1').stdout.strip() == old_head)
    chk('single-commit publish: HEAD tree is the new generation',
        json.loads(git_tree(pubdir2)['history.json'])['closes']['2026-11-06']['BTC'] == 76000.0
        and json.loads(git_tree(pubdir2)['health.json'])['status'] == 'ok')
    chk('single-commit publish: the commit lists all three files',
        set(git_out(pubdir2, 'show', '--name-only', '--format=', 'HEAD').stdout.split())
        == {'history.json', 'prices.json', 'health.json'})
    # Re-run after success with the identical generation: no empty commit.
    names, committed = V.publish_snapshot([(hp2, 'history.json'), (pp2, 'prices.json'),
                                           (hh2, 'health.json')], pubdir2,
                                          message='test snapshot')
    chk('single-commit publish: re-run after success makes no empty commit',
        committed is False and git_head_count(pubdir2) == 2
        and git_out(pubdir2, 'rev-parse', 'HEAD').stdout.strip() == new_head)
    # An add-step failure also rolls back, raises PublishError, HEAD untouched.
    def failing_add_git(args, cwd):
        if args and args[0] == 'add':
            raise RuntimeError('injected failure at git add')
        return real_run_git(args, cwd)

    V._run_git = failing_add_git
    try:
        try:
            V.publish_snapshot([(hp2, 'history.json'), (pp2, 'prices.json'),
                                (hh2, 'health.json')], pubdir2,
                               message='test snapshot')
            raised = False
        except V.PublishError:
            raised = True
    finally:
        V._run_git = real_run_git
    chk('single-commit publish: add failure raises PublishError', raised)
    chk('single-commit publish: HEAD unchanged after the add failure',
        git_out(pubdir2, 'rev-parse', 'HEAD').stdout.strip() == new_head)
    chk('single-commit publish: working tree restored after the add failure',
        json.load(open(os.path.join(pubdir2, 'history.json')))['closes']['2026-11-06']['BTC'] == 76000.0)
    # A commit failing for missing identity fails loudly, HEAD untouched.
    def no_identity_git(args, cwd):
        if args and args[0] == 'commit':
            return subprocess.CompletedProcess(
                args, 128, '', 'Author identity unknown\n\n*** Please tell me who you are.\n')
        return real_run_git(args, cwd)

    h2b = copy.deepcopy(gh)
    h2b['closes']['2026-11-06']['BTC'] = 77000.0
    hp2b = os.path.join(tmp, 'history2b.json')
    json.dump(h2b, open(hp2b, 'w'))
    V._run_git = no_identity_git
    try:
        try:
            V.publish_snapshot([(hp2b, 'history.json'), (pp2, 'prices.json'),
                                (hh2, 'health.json')], pubdir2,
                               message='test snapshot')
            raised = False
        except V.PublishError:
            raised = True
    finally:
        V._run_git = real_run_git
    chk('single-commit publish: commit failure (no identity) raises PublishError', raised)
    chk('single-commit publish: HEAD unchanged after the commit failure',
        git_out(pubdir2, 'rev-parse', 'HEAD').stdout.strip() == new_head)
    chk('single-commit publish: working tree restored after the commit failure',
        json.load(open(os.path.join(pubdir2, 'history.json')))['closes']['2026-11-06']['BTC'] == 76000.0)
    # A plain directory (not a git working tree) fails closed.
    plain = os.path.join(tmp, 'pub-plain')
    os.makedirs(plain, exist_ok=True)
    try:
        V.publish_snapshot([(hp2, 'history.json')], plain, message='test')
        raised = False
    except V.PublishError:
        raised = True
    chk('single-commit publish: non-git publish dir fails closed', raised)

    # 8c. Grok Bot fix 2 (success control): a clean index publishes, and
    # the new commit contains exactly the snapshot files.
    pubdir4 = make_pub_repo('pub-clean-index', prev_h_bytes, prev_p_bytes,
                            prev_health_bytes)
    names, committed = V.publish_snapshot([(hp2, 'history.json'), (pp2, 'prices.json'),
                                           (hh2, 'health.json')], pubdir4,
                                          message='test snapshot')
    chk('single-commit publish: clean index publishes the snapshot (8c)',
        committed is True and names == ['history.json', 'prices.json', 'health.json'])
    chk('single-commit publish: clean index publish adds exactly one commit (8c)',
        git_head_count(pubdir4) == 2)
    chk('single-commit publish: clean index commit lists only the snapshot files (8c)',
        set(git_out(pubdir4, 'show', '--name-only', '--format=', 'HEAD').stdout.split())
        == {'history.json', 'prices.json', 'health.json'})

    # 8d. Grok Bot fix 2 (failure): an index that already has an unrelated
    # staged file is REJECTED before anything changes — no new commit, the
    # unrelated file stays staged, and the working-tree bytes are untouched.
    pubdir5 = make_pub_repo('pub-prestaged', prev_h_bytes, prev_p_bytes,
                            prev_health_bytes)
    open(os.path.join(pubdir5, 'unrelated.txt'), 'w').write('not part of the snapshot\n')
    subprocess.run(['git', '-C', pubdir5, 'add', 'unrelated.txt'],
                   check=True, capture_output=True)
    before_count = git_head_count(pubdir5)
    before_bytes = {n: open(os.path.join(pubdir5, n), 'rb').read()
                    for n in ('history.json', 'prices.json', 'health.json')}
    try:
        V.publish_snapshot([(hp2, 'history.json'), (pp2, 'prices.json'),
                            (hh2, 'health.json')], pubdir5,
                           message='test snapshot')
        raised = False
    except V.PublishError:
        raised = True
    chk('single-commit publish: pre-staged index raises PublishError (8d)', raised)
    chk('single-commit publish: no new commit when the index is pre-staged (8d)',
        git_head_count(pubdir5) == before_count)
    chk('single-commit publish: unrelated staged file remains staged (8d)',
        git_out(pubdir5, 'diff', '--cached', '--name-only').stdout.split()
        == ['unrelated.txt'])
    chk('single-commit publish: working-tree bytes unchanged when rejected (8d)',
        all(open(os.path.join(pubdir5, n), 'rb').read() == before_bytes[n]
            for n in before_bytes)
        and open(os.path.join(pubdir5, 'unrelated.txt')).read()
        == 'not part of the snapshot\n')

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

    # 8b2. End to end: a kill at the commit inside main() propagates (the
    # process died there), HEAD stays the old snapshot, the working tree is
    # restored, health is still written, and the staging dir is cleaned up.
    pubdir3 = make_pub_repo('pub-e2e', prev_h_bytes, prev_p_bytes, prev_health_bytes)
    old_head3 = git_out(pubdir3, 'rev-parse', 'HEAD').stdout.strip()
    old_tree3 = git_tree(pubdir3)
    h3 = copy.deepcopy(gh)
    h3['closes']['2026-11-06']['BTC'] = 76000.0  # changed, so it reaches the commit step
    hp3 = os.path.join(tmp, 'history3.json')
    json.dump(h3, open(hp3, 'w'))
    pp3 = os.path.join(tmp, 'prices3.json')
    json.dump(gp, open(pp3, 'w'))
    open(os.path.join(tmp, 'ledger.js'), 'w').write(GOOD_LEDGER)
    staging_before = {d for d in os.listdir(tempfile.gettempdir())
                      if d.startswith('.staging-')}
    V._run_git = flaky_git
    try:
        try:
            V.main(['--history', hp3, '--prices', pp3, '--ledger',
                    os.path.join(tmp, 'ledger.js'),
                    '--now', NOW.strftime('%Y-%m-%dT%H:%M:%SZ'),
                    '--out-health', os.path.join(tmp, 'health-e2e.json'),
                    '--publish-to', pubdir3])
            raised = False
        except KeyboardInterrupt:
            raised = True
    finally:
        V._run_git = real_run_git
    staging_after = {d for d in os.listdir(tempfile.gettempdir())
                     if d.startswith('.staging-')}
    chk('single-commit publish (main): kill at commit re-raises KeyboardInterrupt', raised)
    chk('single-commit publish (main): HEAD unchanged after the kill',
        git_out(pubdir3, 'rev-parse', 'HEAD').stdout.strip() == old_head3)
    chk('single-commit publish (main): HEAD tree byte-identical after the kill',
        git_tree(pubdir3) == old_tree3)
    chk('single-commit publish (main): working tree restored after the kill',
        open(os.path.join(pubdir3, 'history.json'), 'rb').read() == prev_h_bytes
        and open(os.path.join(pubdir3, 'prices.json'), 'rb').read() == prev_p_bytes)
    chk('single-commit publish (main): health file still written with status ok',
        json.load(open(os.path.join(tmp, 'health-e2e.json')))['status'] == 'ok')
    chk('single-commit publish (main): no staging dir left behind',
        staging_after <= staging_before, str(staging_after - staging_before))

    # 8b3. On a hold, only health.json is published (hold visible, data untouched).
    h_bad = copy.deepcopy(gh)
    h_bad['closes']['2026-11-05']['TSLA'] = 0
    code, health, pubdir = run_cli(tmp, h_bad, gp, ledger=GOOD_LEDGER,
                                   prev_hist=gh, prev_prices=gp, publish=True)
    chk('hold publish: health.json published with status held',
        code == 1 and json.load(open(os.path.join(pubdir, 'health.json')))['status'] == 'held')
    chk('hold publish: previous history still the published file',
        json.load(open(os.path.join(pubdir, 'history.json')))['closes'] == gh['closes'])
    chk('hold publish: HEAD tree history/prices unchanged (health-only commit)',
        json.loads(git_tree(pubdir)['history.json'])['closes'] == gh['closes']
        and json.loads(git_tree(pubdir)['prices.json'])['stocks'] == gp['stocks'])
    chk('hold publish: HEAD health committed with status held',
        json.loads(git_tree(pubdir)['health.json'])['status'] == 'held')
    chk('hold publish: exactly one new commit, listing health.json only',
        git_head_count(pubdir) == 2
        and set(git_out(pubdir, 'show', '--name-only', '--format=', 'HEAD').stdout.split())
        == {'health.json'})

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

    # 8h. Narrow rule (Grok Bot correction 1): a BTC tiingo_ref entry on a
    # provisional date is permitted ONLY with a fully validated tiingo_final
    # freeze. Direct check_tiingo cases first (isolated from the other
    # checks), then one end-to-end run through main().
    def tg_freeze_hist(mutate=None):
        h = {'closes': {'2026-11-05': {'BTC': 75600.0, 'TSLA': 352.0},
                        '2026-11-06': {'BTC': 75732.0, 'TSLA': 353.0}},
             'btc_provisional': ['2026-11-06'],
             'tiingo_ref': {'2026-11-06': {'BTC': {'v': 75807.732,
                                                   't': '2026-11-07T00:20:19Z'}}},
             'tiingo_final': {'2026-11-06': {'BTC': 75732.0, 'tiingo': 75807.732,
                                             'diff_pct': 0.1,
                                             'confirmed': '2026-11-07T00:20:19Z'}}}
        if mutate:
            mutate(h)
        return h

    r = V.check_tiingo(tg_freeze_hist())
    chk('narrow rule: fully validated freeze passes, counted as compared',
        r['status'] == 'pass' and '1 reference values within tolerance' in r['detail'],
        '%s %s' % (r['status'], r['detail']))
    narrow_cases = []
    narrow_cases.append(('narrow rule: missing tiingo_final fails',
                         lambda h: h.pop('tiingo_final')))
    narrow_cases.append(('narrow rule: tiingo_final not an object fails',
                         lambda h: h.update({'tiingo_final': 'confirmed'})))
    narrow_cases.append(('narrow rule: tiingo_final date not an object fails',
                         lambda h: h['tiingo_final'].update({'2026-11-06': 'confirmed'})))
    narrow_cases.append(('narrow rule: tiingo_final BTC != published close fails',
                         lambda h: h['tiingo_final']['2026-11-06'].update({'BTC': 75733.0})))
    narrow_cases.append(('narrow rule: tiingo_final tiingo != cached value fails',
                         lambda h: h['tiingo_final']['2026-11-06'].update({'tiingo': 75808.0})))
    narrow_cases.append(('narrow rule: agreement over 0.3% fails',
                         lambda h: (h['tiingo_ref']['2026-11-06']['BTC'].update({'v': 76110.66}),
                                    h['tiingo_final']['2026-11-06'].update(
                                        {'tiingo': 76110.66, 'diff_pct': 0.5}))))
    narrow_cases.append(('narrow rule: missing confirmed timestamp fails',
                         lambda h: h['tiingo_final']['2026-11-06'].pop('confirmed')))
    narrow_cases.append(('narrow rule: unparseable confirmed timestamp fails',
                         lambda h: h['tiingo_final']['2026-11-06'].update(
                             {'confirmed': 'not-a-time'})))
    narrow_cases.append(('narrow rule: Tiingo value outside the sanity band fails',
                         lambda h: (h['closes']['2026-11-05'].update({'BTC': 50000.0}),
                                    h['closes']['2026-11-06'].update({'BTC': 100000.0}),
                                    h['tiingo_ref']['2026-11-06']['BTC'].update({'v': 100100.0}),
                                    h['tiingo_final']['2026-11-06'].update(
                                        {'BTC': 100000.0, 'tiingo': 100100.0}))))
    narrow_cases.append(('narrow rule: boolean tiingo in tiingo_final fails',
                         lambda h: h['tiingo_final']['2026-11-06'].update({'tiingo': True})))
    narrow_cases.append(('narrow rule: NaN tiingo in tiingo_final fails',
                         lambda h: h['tiingo_final']['2026-11-06'].update(
                             {'tiingo': float('nan')})))
    narrow_cases.append(('narrow rule: string diff_pct fails',
                         lambda h: h['tiingo_final']['2026-11-06'].update({'diff_pct': '0.1'})))
    narrow_cases.append(('narrow rule: NaN diff_pct fails',
                         lambda h: h['tiingo_final']['2026-11-06'].update(
                             {'diff_pct': float('nan')})))
    narrow_cases.append(('narrow rule: recorded miss (v null) on a provisional date fails',
                         lambda h: h['tiingo_ref']['2026-11-06']['BTC'].update({'v': None})))
    for name, mutate in narrow_cases:
        r = V.check_tiingo(tg_freeze_hist(mutate))
        chk('%s' % name, r['status'] == 'fail', '%s %s' % (r['status'], r['detail']))
    r = V.check_tiingo(tg_freeze_hist(
        lambda h: h['tiingo_final']['2026-11-06'].pop('diff_pct')))
    chk('narrow rule: diff_pct absent still passes',
        r['status'] == 'pass', '%s %s' % (r['status'], r['detail']))
    # End to end: a validated freeze on the provisional 2026-11-06 passes
    # the whole gate and publishes.
    h = copy.deepcopy(gh)
    pub = h['closes']['2026-11-06']['BTC']
    tv = round(pub * 1.001, 2)
    h['tiingo_final'] = {'2026-11-06': {'BTC': pub, 'tiingo': tv, 'diff_pct': 0.1,
                                        'confirmed': '2026-11-06T23:30:00Z'}}
    h['tiingo_ref']['2026-11-06'] = {'BTC': {'v': tv, 't': '2026-11-06T23:30:00Z'}}
    code, health, pubdir = run_cli(tmp, h, gp, ledger=GOOD_LEDGER,
                                   prev_hist=gh, prev_prices=gp, publish=True)
    tg = [r for r in health['validation'] if r['check'] == 'tiingo'][0]
    chk('narrow rule (main): validated freeze passes the whole gate, exit 0',
        code == 0 and health['status'] == 'ok' and tg['status'] == 'pass',
        'exit=%s status=%s tiingo=%s' % (code, health['status'], tg['status']))
    chk('narrow rule (main): frozen history published',
        json.load(open(os.path.join(pubdir, 'history.json')))['tiingo_final']['2026-11-06']['BTC'] == pub)

    # 8i. Grok Bot fix 3: EVERY tiingo_final entry is validated, including
    # entries the tiingo_ref loop never looked at. A tiingo_final entry
    # with NO companion tiingo_ref BTC entry for that date is inconsistent
    # (the un-stall tool always writes both together) and FAILS.
    r = V.check_tiingo(tg_freeze_hist(lambda h: h.pop('tiingo_ref')))
    chk('tiingo_final orphan: no tiingo_ref at all fails',
        r['status'] == 'fail', '%s %s' % (r['status'], r['detail']))
    r = V.check_tiingo(tg_freeze_hist(
        lambda h: h['tiingo_final'].update(
            {'2026-11-05': {'BTC': 75600.0, 'tiingo': 75675.6, 'diff_pct': 0.1,
                            'confirmed': '2026-11-06T00:20:24Z'}})))
    chk('tiingo_final orphan: valid-looking entry for a date with no ref fails',
        r['status'] == 'fail', '%s %s' % (r['status'], r['detail']))
    # Positive control: a fully valid tiingo_final WITH its companion ref,
    # on a FINAL date (not provisional), still passes — the new loop must
    # not fail records the ref loop never fully validated.
    r = V.check_tiingo(tg_freeze_hist(
        lambda h: (h['tiingo_ref'].update(
                       {'2026-11-05': {'BTC': {'v': 75675.6,
                                               't': '2026-11-06T00:20:24Z'}}}),
                   h['tiingo_final'].update(
                       {'2026-11-05': {'BTC': 75600.0, 'tiingo': 75675.6,
                                       'diff_pct': 0.1,
                                       'confirmed': '2026-11-06T00:20:24Z'}}))))
    chk('tiingo_final with ref: valid final-date pair still passes',
        r['status'] == 'pass', '%s %s' % (r['status'], r['detail']))
    # End to end: an orphan tiingo_final fails the whole gate, exit 1.
    h = copy.deepcopy(gh)
    pub = h['closes']['2026-11-06']['BTC']
    h['tiingo_final'] = {'2026-11-06': {'BTC': pub, 'tiingo': round(pub * 1.001, 2),
                                        'diff_pct': 0.1,
                                        'confirmed': '2026-11-06T23:30:00Z'}}
    code, health, _ = run_cli(tmp, h, gp, ledger=GOOD_LEDGER,
                              prev_hist=gh, prev_prices=gp)
    tg = [r for r in health['validation'] if r['check'] == 'tiingo'][0]
    chk('tiingo_final orphan (main): fails the whole gate, exit 1',
        code == 1 and health['status'] == 'held' and tg['status'] == 'fail',
        'exit=%s status=%s tiingo=%s' % (code, health['status'], tg['status']))

    bad = [x for x in R if not x[1]]
    print('\n%d checks, %d failed' % (len(R), len(bad)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
