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

# 7. Implausible Tiingo value (> 40% from previous session) -> NOT frozen,
# and recorded as a disagreement (a wild confirmation is rejected, not skipped quietly).
# (Band is 0.6x..1/0.6x of the previous session close, 70000 here, so the
# value must clear 116666.67 to trip it; 120000 does.)
h = hist(prov=(D_STALLED,), fs={D_STALLED: {'BTC': 'coinbase'}})
r = tu.unstall(h, None, stub({D_STALLED: 120000.0}, []), NOW)
chk('Tiingo +71% vs previous session: NOT frozen (sanity band), disagreement recorded',
    r['frozen'] == [] and 'tiingo_final' not in h and len(r['disagreements']) == 1
    and 'sanity band' in r['disagreements'][0].get('reason', ''), r)

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

# 14. Stall boundary: STRICTLY more than 48 h after the UTC day ended.
# Exactly 48 h does NOT freeze; 48 h + 1 minute does.
cutoff = tu.stall_cutoff(D_STALLED, 48)
chk('stall cutoff is Nov 5 00:00 UTC for Nov 2',
    cutoff == dt.datetime(2026, 11, 5, 0, 0, tzinfo=UTC), cutoff)
h = hist(prov=(D_STALLED,), fs={D_STALLED: {'BTC': 'coinbase'}})
r = tu.unstall(h, None, stub({D_STALLED: 75000.0}, []), cutoff)
chk('at exactly 48h: NOT stalled, not frozen (boundary is strictly greater)',
    r['frozen'] == [] and r['stalled'] == [], r)
h = hist(prov=(D_STALLED,), fs={D_STALLED: {'BTC': 'coinbase'}})
r = tu.unstall(h, None, stub({D_STALLED: 75000.0}, []),
              cutoff + dt.timedelta(minutes=1))
chk('at 48h + 1 minute: stalled and frozen', r['frozen'] == [D_STALLED], r)
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

# 16. btc_daily --check-only: a stalled fallback date is exit 3; Tiingo-confirmed is exit 0.
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
chk('btc_daily --check-only: Tiingo-confirmed date -> exit 0 (no stall)',
    p.returncode == 0, 'rc=%s %s %s' % (p.returncode, p.stdout, p.stderr))
chk('btc_daily --check-only: Tiingo-confirmed named in the log (not silent)',
    'Tiingo-confirmed' in p.stdout, p.stdout)

# 17. Slice-1 validate-gate fit: a Tiingo-confirmed history passes all 7 checks.
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
    chk('validate gate: Tiingo-confirmed history passes (exit 0)',
        p.returncode == 0, 'rc=%s %s %s' % (p.returncode, p.stdout, p.stderr))
    chk('validate gate: check 6 (provisional) passes or flags, never fails, on a Tiingo-confirmed date',
        checks.get('provisional') in ('pass', 'flag'), checks)
    chk('validate gate: all checks ran and none failed',
        len(checks) >= 7 and all(s in ('pass', 'flag', 'skip') for s in checks.values()),
        checks)
    print('    validate.py used:', validate, '| checks:', checks)
    # 17b. The history EXACTLY as tools/tiingo_unstall.py writes it: the
    # freeze PLUS the tiingo_ref cache for the same provisional date. The
    # gate must publish it (exit 0, no fail) — a freeze the gate holds is a
    # stall the tool cannot fix.
    # RESOLVED (Nov 2026, Grok Bot correction 1): the slice-1 gate now
    # permits a BTC tiingo_ref entry on a provisional date ONLY with a
    # fully validated tiingo_final freeze for that date (validated BTC
    # equal to the published close, Tiingo value matching the cached
    # reference, agreement within 0.3%, valid timestamps, sanity band,
    # finite diff_pct — see validate.py _validated_freeze). A missing
    # record, or any failed sub-check, still FAILS. (Check 6's 'stale
    # provisional tag' flag on the same date is expected under the new
    # gate and does not hold the run.)
    vh2 = copy.deepcopy(vh)
    tfv = vh2['tiingo_final'][tf_date]
    vh2['tiingo_ref'] = {tf_date: {'BTC': {'v': tfv['tiingo'], 't': tfv['confirmed']}}}
    vhp2 = os.path.join(tmp, 'v_hist2.json')
    json.dump(vh2, open(vhp2, 'w'))
    vout2 = os.path.join(tmp, 'v_health2.json')
    p2 = subprocess.run([sys.executable, validate, '--history', vhp2, '--prices', vp,
                         '--ledger', os.path.join(a.repo, 'assets', 'js', 'ledger.js'),
                         '--out-health', vout2, '--now', '2026-11-06T23:30:00Z'],
                        capture_output=True, text=True)
    health2 = json.load(open(vout2)) if os.path.exists(vout2) else {}
    checks2 = {c['check']: c['status'] for c in health2.get('validation', [])}
    chk('validate gate: as-written frozen history (tiingo_ref cached) passes (exit 0, no fail)',
        p2.returncode == 0 and 'fail' not in checks2.values(),
        'rc=%s checks=%s %s %s' % (p2.returncode, checks2, p2.stdout, p2.stderr))
    print('    gate on as-written history:', validate, '| checks:', checks2)
    # 17c. Real un-stall output, not just the hand-built fixture above: run
    # the ACTUAL tu.unstall with a stub getter agreeing +0.1% on the
    # stalled 2026-11-04 (that date only stalls after Nov 7 00:00 UTC, so
    # now is 2026-11-07T00:30:00Z), take its real output through a JSON
    # round-trip, and feed it to the gate. Check 6's stale-tag flag on that
    # date is expected (the date is final by then) and does not hold.
    vh3 = copy.deepcopy(vh)
    vh3.pop('tiingo_final', None)
    vh3.pop('tiingo_ref', None)
    now3 = dt.datetime(2026, 11, 7, 0, 30, tzinfo=UTC)
    tv3 = round(vh3['closes'][tf_date]['BTC'] * 1.001, 6)
    _c3 = []
    r3 = tu.unstall(vh3, None, stub({tf_date: tv3}, _c3), now3)
    chk('validate gate: real un-stall output freezes 2026-11-04 (+0.1%, 1 call)',
        r3['frozen'] == [tf_date] and _c3 == [tf_date], r3)
    chk('validate gate: real un-stall output carries tiingo_final + tiingo_ref',
        vh3.get('tiingo_final', {}).get(tf_date, {}).get('BTC') == vh3['closes'][tf_date]['BTC']
        and vh3.get('tiingo_ref', {}).get(tf_date, {}).get('BTC', {}).get('v') == tv3,
        vh3.get('tiingo_final'))
    vh3 = json.loads(json.dumps(vh3))  # JSON round-trip, as the pipeline does
    vhp3 = os.path.join(tmp, 'v_hist3.json')
    json.dump(vh3, open(vhp3, 'w'))
    vout3 = os.path.join(tmp, 'v_health3.json')
    p3 = subprocess.run([sys.executable, validate, '--history', vhp3, '--prices', vp,
                         '--ledger', os.path.join(a.repo, 'assets', 'js', 'ledger.js'),
                         '--out-health', vout3, '--now', '2026-11-07T00:30:00Z'],
                        capture_output=True, text=True)
    health3 = json.load(open(vout3)) if os.path.exists(vout3) else {}
    checks3 = {c['check']: c['status'] for c in health3.get('validation', [])}
    chk('validate gate: real un-stall output passes the gate (exit 0, no fail)',
        p3.returncode == 0 and 'fail' not in checks3.values(),
        'rc=%s checks=%s %s %s' % (p3.returncode, checks3, p3.stdout, p3.stderr))
    chk('validate gate: real un-stall output flags (never fails) the stale provisional tag',
        checks3.get('provisional') == 'flag', checks3)
    print('    gate on real un-stall output:', validate, '| checks:', checks3)
else:
    print('SKIP validate-gate fit check (tools/validate.py not found)')

# 18. Malformed Tiingo confirmations are REJECTED: never frozen, and
# recorded as a disagreement — not silently accepted, not a quiet skip.
def stub_raw(payloads, calls):
    """payloads: {date: raw parsed JSON the getter returns}."""
    def get_t(u):
        import re
        d = re.search(r'startDate=([\d-]+)', u).group(1)
        calls.append(d)
        return payloads.get(d, [{'ticker': 'btcusd', 'priceData': []}])
    return get_t

def malformed_row(close=None, date=None):
    row = {'date': (date or D_STALLED) + 'T00:00:00+00:00'}
    if close is not None:
        row['close'] = close
    return [{'ticker': 'btcusd', 'priceData': [row]}]

# 18a. Row for the date but no 'close' field.
h = hist(prov=(D_STALLED,), fs={D_STALLED: {'BTC': 'coinbase'}})
r = tu.unstall(h, None, stub_raw({D_STALLED: malformed_row()}, []), NOW)
chk('malformed: missing close field -> NOT frozen, disagreement recorded',
    r['frozen'] == [] and 'tiingo_final' not in h and len(r['disagreements']) == 1
    and 'malformed' in r['disagreements'][0].get('reason', ''), r)
# 18b. Non-numeric close (a string, not a number).
h = hist(prov=(D_STALLED,), fs={D_STALLED: {'BTC': 'coinbase'}})
r = tu.unstall(h, None, stub_raw({D_STALLED: malformed_row(close='75010.0')}, []), NOW)
chk('malformed: non-numeric close -> NOT frozen, disagreement recorded',
    r['frozen'] == [] and 'tiingo_final' not in h and len(r['disagreements']) == 1
    and 'malformed' in r['disagreements'][0].get('reason', ''), r)
# 18c. Rows exist but every row is for the wrong date.
h = hist(prov=(D_STALLED,), fs={D_STALLED: {'BTC': 'coinbase'}})
r = tu.unstall(h, None, stub_raw({D_STALLED: malformed_row(close=75010.0, date=D_STALLED2)}, []), NOW)
chk('malformed: wrong-date row -> NOT frozen, disagreement recorded',
    r['frozen'] == [] and 'tiingo_final' not in h and len(r['disagreements']) == 1
    and 'malformed' in r['disagreements'][0].get('reason', ''), r)
chk('malformed: date stays provisional, published value untouched',
    D_STALLED in h['btc_provisional'] and h['closes'][D_STALLED]['BTC'] == 75000.0, h)
# 18d. A tolerance disagreement also carries a reason (not a bare record).
h = hist(prov=(D_STALLED,), fs={D_STALLED: {'BTC': 'coinbase'}})
r = tu.unstall(h, None, stub({D_STALLED: 76000.0}, []), NOW)
chk('disagreement: tolerance breach carries a reason',
    len(r['disagreements']) == 1 and 'tolerance' in r['disagreements'][0].get('reason', ''), r)
# 18e. main() survives a malformed confirmation end to end: the ::warning::
# print must not crash on a disagreement with no diff_pct (exit 0, no freeze).
import io, contextlib
_orig_getter = tu.real_getter
tu.real_getter = lambda key: stub_raw({D_STALLED: malformed_row()}, [])
os.environ['TIINGO_API_KEY'] = 'dummy-key-for-test'
mal_cand = os.path.join(tmp, 'mal-cand.json')
mal_out = os.path.join(tmp, 'mal-out.json')
json.dump(hist(prov=(D_STALLED,), fs={D_STALLED: {'BTC': 'coinbase'}}), open(mal_cand, 'w'))
_buf = io.StringIO()
with contextlib.redirect_stdout(_buf):
    _rc = tu.main(['--history', mal_cand, '--out', mal_out,
                   '--now', '2026-11-06T23:30:00Z'])
tu.real_getter = _orig_getter
del os.environ['TIINGO_API_KEY']
_mal = json.load(open(mal_out)) if os.path.exists(mal_out) else {}
chk('malformed: main() exit 0, warning printed, nothing frozen',
    _rc == 0 and 'malformed Tiingo confirmation' in _buf.getvalue()
    and 'tiingo_final' not in _mal, (_rc, _buf.getvalue(), _mal))

# 19. Month finalization on a Tiingo-confirmed close (Sunil's decision,
# Nov 2026): the month finalizes, with explicit pending-Yahoo disclosure
# on the page. BTC-only; the freeze itself costs at most the usual 5 calls
# (no extra calls for finalizing — the disclosure is text on the page).
def stage_month(mode):
    """Fresh staging repo for recap_gen.py, with a synthetic history whose
    closes run through Fri 2026-10-30 (the last NYSE session of Oct 2026).
    mode 'tf': Oct 30 provisional + Tiingo-confirmed. mode 'prov': Oct 30
    provisional, no confirmation (the stalled case)."""
    import math as _m, shutil
    from stock_weekly import HOLIDAYS
    sd = os.path.join(tmp, 'stage-' + mode)
    os.makedirs(os.path.join(sd, 'recap', '2026-09'), exist_ok=True)
    os.makedirs(os.path.join(sd, 'assets', 'js'), exist_ok=True)
    os.makedirs(os.path.join(sd, 'assets', 'data'), exist_ok=True)
    shutil.copy(os.path.join(a.repo, 'recap', '2026-09', 'index.html'),
                os.path.join(sd, 'recap', '2026-09', 'index.html'))
    # months.js without its 2026-10 entry, so October is a genuinely new
    # month here (otherwise recap_gen's entry-count validation trips).
    mj = open(os.path.join(a.repo, 'recap', 'months.js')).read()
    mj = '\n'.join(l for l in mj.split('\n') if "slug:'2026-10'" not in l)
    open(os.path.join(sd, 'recap', 'months.js'), 'w').write(mj)
    shutil.copy(os.path.join(a.repo, 'assets', 'js', 'ledger.js'),
                os.path.join(sd, 'assets', 'js', 'ledger.js'))
    shutil.copy(os.path.join(a.repo, 'assets', 'data', 'btc-daily.json'),
                os.path.join(sd, 'assets', 'data', 'btc-daily.json'))
    syms = {'BTC': 90000.0, 'MSTR': 300.0, 'STRC': 100.0, 'TSLA': 400.0,
            'PLTR': 150.0, 'SPY': 600.0, 'QQQ': 500.0, 'BRK.B': 480.0, 'GLD': 300.0}
    closes = {}
    d = dt.date(2025, 12, 31)
    end = dt.date(2026, 10, 30)
    i = 0
    while d <= end:
        if d.weekday() < 5 and d.isoformat() not in HOLIDAYS:
            closes[d.isoformat()] = {k: round(v * (1 + 0.002 * _m.sin(i * 1.7 + j)), 6)
                                     for j, (k, v) in enumerate(syms.items())}
            i += 1
        d += dt.timedelta(days=1)
    h = {'v': 1, 'closes': closes, 'divs': {}, 'btc_provisional': [],
         'fallback_sources': {}}
    if mode in ('tf', 'prov'):
        h['btc_provisional'] = ['2026-10-30']
        h['fallback_sources'] = {'2026-10-30': {'BTC': 'coinbase'}}
    if mode == 'tf':
        tv = closes['2026-10-30']['BTC']
        h['tiingo_final'] = {'2026-10-30': {'BTC': tv, 'tiingo': round(tv * 1.001, 6),
                                            'diff_pct': 0.1,
                                            'confirmed': '2026-11-06T23:30:00Z'}}
    hp = os.path.join(sd, 'hist.json')
    json.dump(h, open(hp, 'w'))
    return sd, hp

sd, hp = stage_month('tf')
p = subprocess.run([sys.executable, os.path.join(a.repo, 'tools', 'recap_gen.py'),
                    '--history', hp, '--repo', sd], capture_output=True, text=True)
oct_page = os.path.join(sd, 'recap', '2026-10', 'index.html')
page = open(oct_page).read() if os.path.exists(oct_page) else ''
chk('month finalization: recap_gen exit 0 on a Tiingo-confirmed month-end',
    p.returncode == 0 and os.path.exists(oct_page), 'rc=%s %s %s' % (p.returncode, p.stdout, p.stderr))
chk('month finalization: October page is FINAL (no "month to date" in the title)',
    '<title>October 2026 Recap' in page and 'month to date' not in page.split('</title>')[0], page.split('</title>')[0])
chk('month finalization: page names the Tiingo-confirmed date',
    "Tiingo-confirmed (Yahoo's final bar pending): Oct 30" in page, page)
chk('month finalization: page discloses the month is final on a Tiingo-confirmed close',
    'This month is final on a Tiingo-confirmed close; Yahoo\'s final bar is still pending.' in page, page)
sd2, hp2 = stage_month('prov')
p2 = subprocess.run([sys.executable, os.path.join(a.repo, 'tools', 'recap_gen.py'),
                     '--history', hp2, '--repo', sd2], capture_output=True, text=True)
page2 = open(os.path.join(sd2, 'recap', '2026-10', 'index.html')).read() if os.path.exists(os.path.join(sd2, 'recap', '2026-10', 'index.html')) else ''
chk('month finalization: without confirmation, recap_gen still exits 0',
    p2.returncode == 0, 'rc=%s %s %s' % (p2.returncode, p2.stdout, p2.stderr))
chk('month finalization: without confirmation the month stays month-to-date (no finalization disclosure)',
    '(month to date, through Oct 29, 2026)' in page2
    and 'This month is final on a Tiingo-confirmed close' not in page2, page2.split('</title>')[0])

print('TIINGO UN-STALL TESTS', len(R), 'FAIL', R.count(False))
sys.exit(1 if not all(R) else 0)
