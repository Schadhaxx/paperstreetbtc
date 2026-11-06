#!/usr/bin/env python3
"""Tiingo un-stall tests (slice 2). No network, no key needed: the Tiingo
fetch is stubbed, and the btc_daily stall behaviour is exercised through
--check-only (which never fetches). Exit 1 on any failure.
usage: python3 tests/test_tiingo_unstall.py [--repo DIR]
The slice-1 validate-gate fit check runs only if tools/validate.py is
findable (in-repo, $VALIDATE_PY, or the slice-1 work copy); otherwise it
is skipped, not failed.
"""
import argparse, copy, datetime as dt, json, os, subprocess, sys, tempfile

ap = argparse.ArgumentParser()
ap.add_argument('--repo', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
a = ap.parse_args()
sys.path.insert(0, os.path.join(a.repo, 'tools'))
import tiingo_unstall as tu

R = []


def chk(name, ok, info=''):
    R.append(bool(ok))
    print('PASS' if ok else 'FAIL', name, '' if ok else info, flush=True)


UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 6, 23, 30, tzinfo=UTC)   # Fri 6 Nov 2026, 23:30 UTC
D_STALLED = '2026-11-02'   # UTC day ended Nov 3 00:00 UTC; 48 h later Nov 5 00:00 UTC -> stalled at NOW
D_STALLED2 = '2026-11-03'
D_FRESH = '2026-11-05'     # UTC day ended Nov 6 00:00 UTC; 48 h later Nov 8 -> NOT stalled at NOW
D_OLD = '2026-10-30'


def hist(prov=(), fs=None, closes=None, tf=None, ref=None):
    base = {D_OLD: {'BTC': 70000.0, 'MSTR': 300.0}, D_STALLED: {'BTC': 75000.0},
            D_STALLED2: {'BTC': 76000.0}, D_FRESH: {'BTC': 77000.0}}
    if closes:
        base.update(closes)
    h = {'v': 1, 'closes': base, 'btc_provisional': list(prov),
         'fallback_sources': fs or {}}
    if tf is not None:
        h['tiingo_final'] = tf
    if ref is not None:
        h['tiingo_ref'] = ref
    return h


def stub(values, calls, boom=()):
    """values: {date: tiingo close}. Returns a getter recording its calls."""
    def get_t(u):
        import re
        d = re.search(r'startDate=([\d-]+)', u).group(1)
        calls.append(d)
        if d in boom:
            raise OSError('boom')
        if d in values:
            return [{'ticker': 'btcusd', 'priceData': [
                {'date': d + 'T00:00:00+00:00', 'close': values[d]}]}]
        return [{'ticker': 'btcusd', 'priceData': []}]
    return get_t


# 1. No stalled dates -> no-op, no field, no calls.
h = hist(prov=())
c = []
r = tu.unstall(h, None, stub({}, c), NOW)
chk('no stalled dates: no-op', r['calls'] == 0 and 'tiingo_final' not in h and r['stalled'] == [], r)

# 2. Stalled < 48 h -> not frozen, no call.
h = hist(prov=(D_FRESH,), fs={D_FRESH: {'BTC': 'coinbase'}})
c = []
r = tu.unstall(h, None, stub({D_FRESH: 77000.0}, c), NOW)
chk('fresh provisional (<48h): not frozen, no call',
    r['calls'] == 0 and 'tiingo_final' not in h and D_FRESH not in r['stalled'], r)

# 3. Stalled > 48 h, Tiingo agrees within 0.3% -> frozen.
h = hist(prov=(D_STALLED,), fs={D_STALLED: {'BTC': 'coinbase'}})
c = []
r = tu.unstall(h, None, stub({D_STALLED: 75010.0}, c), NOW)
chk('agree within 0.3%: frozen, 1 call',
    r['calls'] == 1 and r['frozen'] == [D_STALLED] and c == [D_STALLED], r)
chk('frozen: value unchanged (Tiingo confirms, never replaces)',
    h['closes'][D_STALLED]['BTC'] == 75000.0, h['closes'][D_STALLED])
chk('frozen: stays in btc_provisional',
    D_STALLED in h['btc_provisional'], h['btc_provisional'])
chk('frozen: fallback_sources tag untouched (still coinbase)',
    h['fallback_sources'][D_STALLED] == {'BTC': 'coinbase'}, h['fallback_sources'])
chk('frozen: tiingo_final record carries value + tiingo + diff + confirmed',
    h['tiingo_final'][D_STALLED]['BTC'] == 75000.0
    and h['tiingo_final'][D_STALLED]['tiingo'] == 75010.0
    and abs(h['tiingo_final'][D_STALLED]['diff_pct'] - 0.0133) < 0.001
    and h['tiingo_final'][D_STALLED]['confirmed'] == '2026-11-06T23:30:00Z',
    h.get('tiingo_final'))
chk('frozen: fetch cached in tiingo_ref for the reference check',
    h['tiingo_ref'][D_STALLED]['BTC'] == {'v': 75010.0, 't': '2026-11-06T23:30:00Z'},
    h.get('tiingo_ref'))

# 4. Exactly at the 0.3% threshold -> frozen (strictly greater disagrees).
h = hist(prov=(D_STALLED,), fs={D_STALLED: {'BTC': 'coinbase'}})
r = tu.unstall(h, None, stub({D_STALLED: 75000.0 * 1.003}, []), NOW)
chk('exactly +0.3%: frozen (threshold is strictly greater)',
    r['frozen'] == [D_STALLED], r)

# 5. Tiingo disagrees > 0.3% -> NOT frozen, disagreement recorded.
h = hist(prov=(D_STALLED,), fs={D_STALLED: {'BTC': 'coinbase'}})
r = tu.unstall(h, None, stub({D_STALLED: 76000.0}, []), NOW)
chk('disagree +1.33%: NOT frozen, disagreement recorded',
    r['frozen'] == [] and len(r['disagreements']) == 1
    and r['disagreements'][0]['date'] == D_STALLED
    and 'tiingo_final' not in h, r)
chk('disagreement: date stays provisional, value untouched',
    D_STALLED in h['btc_provisional'] and h['closes'][D_STALLED]['BTC'] == 75000.0, h)

# 6. Tiingo returns nothing / fetch fails -> NOT frozen, no crash.
h = hist(prov=(D_STALLED,), fs={D_STALLED: {'BTC': 'coinbase'}})
r = tu.unstall(h, None, stub({}, []), NOW)
chk('Tiingo returns no close: NOT frozen', r['frozen'] == [] and 'tiingo_final' not in h, r)
h = hist(prov=(D_STALLED,), fs={D_STALLED: {'BTC': 'coinbase'}})
r = tu.unstall(h, None, stub({D_STALLED: 75000.0}, [], boom=(D_STALLED,)), NOW)
chk('Tiingo fetch fails: NOT frozen, no crash', r['frozen'] == [] and 'tiingo_final' not in h, r)

# 7. Implausible Tiingo value (> 40% from previous session) -> NOT frozen.
h = hist(prov=(D_STALLED,), fs={D_STALLED: {'BTC': 'coinbase'}})
r = tu.unstall(h, None, stub({D_STALLED: 75000.0 * 1.5}, []), NOW)
chk('Tiingo +50% vs previous session: NOT frozen (sanity band)',
    r['frozen'] == [] and 'tiingo_final' not in h, r)

# 8. Already frozen, value unchanged, still stalled -> carried forward, 0 calls.
prev_tf = {D_STALLED: {'BTC': 75000.0, 'tiingo': 75010.0, 'diff_pct': 0.0133,
                       'confirmed': '2026-11-05T23:30:00Z'}}
h = hist(prov=(D_STALLED,), fs={D_STALLED: {'BTC': 'coinbase'}})
prev = hist(prov=(D_STALLED,), fs={D_STALLED: {'BTC': 'coinbase'}}, tf=prev_tf)
c = []
r = tu.unstall(h, prev, stub({D_STALLED: 75010.0}, c), NOW)
chk('already frozen, value unchanged: carried forward, 0 calls',
    r['carried'] == [D_STALLED] and c == [] and h['tiingo_final'] == prev_tf, r)

# 9. Already frozen but the published value changed -> re-verified (call made).
h = hist(prov=(D_STALLED,), fs={D_STALLED: {'BTC': 'coinbase'}},
         closes={D_STALLED: {'BTC': 75100.0}})
prev = hist(prov=(D_STALLED,), fs={D_STALLED: {'BTC': 'coinbase'}}, tf=prev_tf)
c = []
r = tu.unstall(h, prev, stub({D_STALLED: 75105.0}, c), NOW)
chk('frozen value changed: re-verified, re-frozen at the new value',
    r['calls'] == 1 and r['frozen'] == [D_STALLED]
    and h['tiingo_final'][D_STALLED]['BTC'] == 75100.0, r)

# 10. Already frozen but value changed and Tiingo disagrees -> dropped.
h = hist(prov=(D_STALLED,), fs={D_STALLED: {'BTC': 'coinbase'}},
         closes={D_STALLED: {'BTC': 75100.0}})
prev = hist(prov=(D_STALLED,), fs={D_STALLED: {'BTC': 'coinbase'}}, tf=prev_tf)
r = tu.unstall(h, prev, stub({D_STALLED: 80000.0}, []), NOW)
chk('frozen value changed + Tiingo disagrees: old freeze dropped, not re-frozen',
    r['frozen'] == [] and r['carried'] == [] and 'tiingo_final' not in h, r)

# 11. Yahoo replaced the date (no longer provisional) -> dropped from tiingo_final.
h = hist(prov=(), fs={})
prev = hist(prov=(D_STALLED,), fs={D_STALLED: {'BTC': 'coinbase'}}, tf=prev_tf)
r = tu.unstall(h, prev, stub({}, []), NOW)
chk('Yahoo replaced it (left provisional): tiingo_final dropped',
    'tiingo_final' not in h and r['stalled'] == [], r)

# 12. No API key -> no new freeze, but carry-forward still works.
h = hist(prov=(D_STALLED,), fs={D_STALLED: {'BTC': 'coinbase'}})
r = tu.unstall(h, None, None, NOW)
chk('no key: no new freeze', r['frozen'] == [] and 'tiingo_final' not in h, r)
h = hist(prov=(D_STALLED,), fs={D_STALLED: {'BTC': 'coinbase'}})
prev = hist(prov=(D_STALLED,), fs={D_STALLED: {'BTC': 'coinbase'}}, tf=prev_tf)
r = tu.unstall(h, prev, None, NOW)
chk('no key: existing freeze still carried forward',
    r['carried'] == [D_STALLED] and h['tiingo_final'] == prev_tf, r)

# 13. Call budget: 6 newly stalled dates, max 5 -> oldest 5 frozen, 6th skipped.
dates = ['2026-10-26', '2026-10-27', '2026-10-28', '2026-10-29', '2026-10-30', '2026-11-02']
closes = {d: {'BTC': 70000.0 + 100 * i} for i, d in enumerate(dates)}
fs = {d: {'BTC': 'coinbase'} for d in dates}
h = hist(prov=tuple(dates), fs=fs, closes=closes)
vals = {d: closes[d]['BTC'] for d in dates}
c = []
r = tu.unstall(h, None, stub(vals, c), NOW, max_calls=5)
chk('budget 5 for 6 newly stalled: oldest 5 frozen, 6th skipped',
    r['calls'] == 5 and len(r['frozen']) == 5 and r['frozen'] == sorted(dates)[:5]
    and [d for d, _ in r['skipped']] == ['2026-11-02'], r)

# 14. Stall boundary: exactly 48 h after the UTC day ended -> stalled.
cutoff = tu.stall_cutoff(D_STALLED, 48)
chk('stall cutoff is Nov 5 00:00 UTC for Nov 2',
    cutoff == dt.datetime(2026, 11, 5, 0, 0, tzinfo=UTC), cutoff)
h = hist(prov=(D_STALLED,), fs={D_STALLED: {'BTC': 'coinbase'}})
r = tu.unstall(h, None, stub({D_STALLED: 75000.0}, []), cutoff)
chk('at exactly 48h: stalled and frozen', r['frozen'] == [D_STALLED], r)
h = hist(prov=(D_STALLED,), fs={D_STALLED: {'BTC': 'coinbase'}})
r = tu.unstall(h, None, stub({D_STALLED: 75000.0}, []),
              cutoff - dt.timedelta(minutes=1))
chk('1 minute before 48h: not stalled', r['frozen'] == [] and r['stalled'] == [], r)

# 15. CLI end-to-end (subprocess, no network): dry run + carry-forward + bad input.
tmp = tempfile.mkdtemp(prefix='ps-unstall-')
cand = os.path.join(tmp, 'cand.json')
prevp = os.path.join(tmp, 'prev.json')
json.dump(hist(prov=(D_STALLED,), fs={D_STALLED: {'BTC': 'coinbase'}}), open(cand, 'w'))
json.dump(hist(prov=(D_STALLED,), fs={D_STALLED: {'BTC': 'coinbase'}}, tf=prev_tf), open(prevp, 'w'))
outp = os.path.join(tmp, 'out.json')
p = subprocess.run([sys.executable, os.path.join(a.repo, 'tools', 'tiingo_unstall.py'),
                    '--history', cand, '--prev-history', prevp, '--out', outp,
                    '--now', '2026-11-06T23:30:00Z'],
                   capture_output=True, text=True, env={**os.environ})
chk('CLI: exit 0 without a key (carry-forward only)',
    p.returncode == 0, p.stdout + p.stderr)
got = json.load(open(outp))
chk('CLI: carry-forward written to --out',
    got.get('tiingo_final') == prev_tf, got.get('tiingo_final'))
p = subprocess.run([sys.executable, os.path.join(a.repo, 'tools', 'tiingo_unstall.py'),
                    '--history', cand, '--prev-history', prevp,
                    '--now', '2026-11-06T23:30:00Z', '--dry-run'],
                   capture_output=True, text=True, env={**os.environ})
chk('CLI: --dry-run exit 0 and writes nothing',
    p.returncode == 0 and not os.path.exists(outp + '.dry'), p.stdout + p.stderr)
bad = os.path.join(tmp, 'bad.json')
open(bad, 'w').write('{not json')
p = subprocess.run([sys.executable, os.path.join(a.repo, 'tools', 'tiingo_unstall.py'),
                    '--history', bad], capture_output=True, text=True)
chk('CLI: malformed history.json -> exit 1, file untouched',
    p.returncode == 1 and open(bad).read() == '{not json', p.stdout + p.stderr)

# 16. btc_daily --check-only: a stalled fallback date is exit 3; Tiingo-final is exit 0.
# Fixture closes must match btc-daily.json's stored values, or the R-s heal
# path (unrelated to the stall) refuses the run.
bd = {'v': 1, 'end': '2026-10-30',
      'd': [['2026-10-28', 70000.0], ['2026-10-29', 70500.0], ['2026-10-30', 71000.0]],
      'provisional': []}
bdp = os.path.join(tmp, 'btc-daily.json')
json.dump(bd, open(bdp, 'w'))
bd_closes = {'2026-10-28': {'BTC': 70000.0}, '2026-10-29': {'BTC': 70500.0},
             '2026-10-30': {'BTC': 71000.0}, D_STALLED: {'BTC': 75000.0}}
stalled_hist = hist(prov=(D_STALLED,), fs={D_STALLED: {'BTC': 'coinbase'}},
                    closes=bd_closes)
shp = os.path.join(tmp, 'stalled.json')
json.dump(stalled_hist, open(shp, 'w'))
p = subprocess.run([sys.executable, os.path.join(a.repo, 'tools', 'btc_daily.py'),
                    bdp, shp, '--check-only'], capture_output=True, text=True)
chk('btc_daily --check-only: stalled fallback (no tiingo_final) -> exit 3',
    p.returncode == 3, 'rc=%s %s %s' % (p.returncode, p.stdout, p.stderr))
un_hist = hist(prov=(D_STALLED,), fs={D_STALLED: {'BTC': 'coinbase'}},
               closes=bd_closes, tf=prev_tf)
uhp = os.path.join(tmp, 'un.json')
json.dump(un_hist, open(uhp, 'w'))
p = subprocess.run([sys.executable, os.path.join(a.repo, 'tools', 'btc_daily.py'),
                    bdp, uhp, '--check-only'], capture_output=True, text=True)
chk('btc_daily --check-only: Tiingo-final date -> exit 0 (no stall)',
    p.returncode == 0, 'rc=%s %s %s' % (p.returncode, p.stdout, p.stderr))
chk('btc_daily --check-only: Tiingo-final named in the log (not silent)',
    'Tiingo-final' in p.stdout, p.stdout)

# 17. Slice-1 validate-gate fit: a Tiingo-final history passes all 7 checks.
# Build a synthetic FULL history (every NYSE session 2025-12-31..2026-11-06,
# same holiday set validate.py uses) so check 2 (sessions) is meaningful.
validate = None
for cand in (os.path.join(a.repo, 'tools', 'validate.py'),
             os.environ.get('VALIDATE_PY', ''),
             os.path.expanduser('~/workspace/ps-py-s1/tools/validate.py')):
    if cand and os.path.exists(cand):
        validate = cand
        break
if validate:
    sys.path.insert(0, os.path.join(a.repo, 'tools'))
    from stock_weekly import HOLIDAYS
    import math as _m
    syms = {'BTC': 90000.0, 'MSTR': 300.0, 'STRC': 100.0, 'TSLA': 400.0,
            'PLTR': 150.0, 'SPY': 600.0, 'QQQ': 500.0, 'BRK.B': 480.0, 'GLD': 300.0}
    closes = {}
    d = dt.date(2025, 12, 31)
    end = dt.date(2026, 11, 6)
    i = 0
    while d <= end:
        if d.weekday() < 5 and d.isoformat() not in HOLIDAYS:
            # gentle deterministic drift, never near a 35% jump
            closes[d.isoformat()] = {k: round(v * (1 + 0.002 * _m.sin(i * 1.7 + j)), 6)
                                     for j, (k, v) in enumerate(syms.items())}
            i += 1
        d += dt.timedelta(days=1)
    tf_date = '2026-11-04'
    tf_val = closes[tf_date]['BTC']
    vh = {'v': 1, 'updated': '2026-11-06T23:30:00Z', 'base': '2025-12-31',
          'source': 'test', 'closes': closes, 'divs': {},
          'btc_provisional': [tf_date],
          'fallback_sources': {tf_date: {'BTC': 'coinbase'}},
          'tiingo_final': {tf_date: {'BTC': tf_val, 'tiingo': round(tf_val * 1.001, 6),
                                     'diff_pct': 0.1,
                                     'confirmed': '2026-11-06T23:30:00Z'}},
          'revisions_ignored': []}
    vhp = os.path.join(tmp, 'v_hist.json')
    json.dump(vh, open(vhp, 'w'))
    vp = os.path.join(tmp, 'v_prices.json')
    json.dump({'v': 1, 'updated': '2026-11-06T23:30:00Z',
               'btc': {'usd': 75834, 'chg24h': 0.16, 'src': 'CoinGecko',
                       'time': '2026-11-06T23:25:14Z'},
               'stocks': {k: {'c': 100.0, 'pc': 99.0, 't': 1762450000}
                          for k in syms if k != 'BTC'}},
              open(vp, 'w'))
    vout = os.path.join(tmp, 'v_health.json')
    p = subprocess.run([sys.executable, validate, '--history', vhp, '--prices', vp,
                        '--ledger', os.path.join(a.repo, 'assets', 'js', 'ledger.js'),
                        '--out-health', vout, '--now', '2026-11-06T23:30:00Z'],
                       capture_output=True, text=True)
    health = json.load(open(vout)) if os.path.exists(vout) else {}
    checks = {c['check']: c['status'] for c in health.get('validation', [])}
    chk('validate gate: Tiingo-final history passes (exit 0)',
        p.returncode == 0, 'rc=%s %s %s' % (p.returncode, p.stdout, p.stderr))
    chk('validate gate: check 6 (provisional) passes on a Tiingo-final date',
        checks.get('provisional') == 'pass', checks)
    chk('validate gate: all 7 checks ran and none failed',
        len(checks) == 7 and all(s in ('pass', 'flag', 'skip') for s in checks.values()),
        checks)
    print('    validate.py used:', validate, '| checks:', checks)
else:
    print('SKIP validate-gate fit check (tools/validate.py not found)')

print('TIINGO UN-STALL TESTS', len(R), 'FAIL', R.count(False))
sys.exit(1 if not all(R) else 0)
