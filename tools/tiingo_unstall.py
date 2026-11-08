#!/usr/bin/env python3
"""Tiingo un-stall (Python supercharge, slice 2).

The problem. When Yahoo's final bar for a session never arrives, the recap
stalls: the pipeline fills the BTC close from a fallback (Coinbase/CoinGecko),
marks the date provisional, and the recap — which is built from FINAL closes
only — never advances past it. The weekend stall alarm (tools/btc_daily.py,
exit 3) fires after 48 h, but nothing moves. The manual way out was a
reviewed PR; this tool is the automated, Tiingo-confirmed version of it.

What this tool does. For each BTC date that is still provisional more than
48 h after its UTC day ended (the same clock btc_daily.py uses — strictly
more than 48 h: exactly 48 h does NOT freeze), it fetches the Tiingo close
for that date ONLY and checks it against the value already published (the
fallback value). If Tiingo agrees within the BTC tolerance (0.3%, the same
threshold the reference cross-check uses), the date is recorded as
Tiingo-confirmed in a new top-level field:

    "tiingo_final": {"2026-11-02": {"BTC": 75799.14, "tiingo": 75801.55,
                                     "diff_pct": 0.0032,
                                     "confirmed": "2026-11-04T23:30:00Z"}}

The field is named `tiingo_final` for the slice-1 validate-gate fit (the
gate and the pipeline read that name); every user-facing string calls the
date Tiingo-confirmed, never Yahoo-final.

The published value NEVER changes: Tiingo confirms it, it does not replace
it. Nothing is ever rewritten to Tiingo closes, and a Tiingo-confirmed value
is never presented as a Yahoo-final close:

  * the date STAYS in btc_provisional (so slice 1's validate gate, check 6,
    still passes unchanged, and the site keeps showing the OI-001
    backup-source label — "Spot BTC (close from backup source until Yahoo's
    final bar)");
  * the fallback_sources tag is left exactly as it was (it records which
    source supplied the value; Tiingo only confirmed it);
  * tools/recap_gen.py and tools/btc_daily.py treat a tiingo_final date as
    final for pipeline purposes (recap advances, no stall alarm), while
    still listing it as provisional in the recap note / btc-daily.json;
  * when Yahoo's final bar eventually arrives, the existing pipeline
    replaces the value (with a 'fallback (...) replaced by primary' revision
    entry), drops it from btc_provisional, and this tool drops it from
    tiingo_final on the next run. Yahoo always wins in the end.

When a date is NOT frozen. Tiingo disagrees beyond 0.3%, Tiingo returns
nothing, the fetch fails, the Tiingo value is implausible (> 40% from the
previous session, the same sanity band build_history uses), or the call
budget is spent: the date stays stalled and provisional, exactly as today.
A disagreement is printed as a ::warning:: (and recorded in the report) —
it is a data event for a human, not something to freeze over. The tool
never fails the run for a disagreement: exit 0, the recap simply stays
stalled, as it does today.

A malformed Tiingo confirmation is rejected the same way, and recorded as
a disagreement (never silently accepted, never frozen): a confirmation row
that is missing its close, carries a non-numeric close, is for the wrong
date, or a value outside the sanity band. "Tiingo returned nothing" (no
rows at all) is different — that is an absence, recorded as a skip, not a
disagreement. A carried-forward freeze from the previous published history
is trusted only if it is well-formed (date in provisional, value matches
the published close, numeric Tiingo value); a malformed carried record is
dropped, never trusted, and the date is re-verified (or skipped if there
is no key / the budget is spent).

Call budget (plan rec 4). Only NEWLY stalled dates cost a call — at most
--max-calls (default 5) per run, oldest first. A date already frozen is
carried forward from the previous published history.json with NO new call,
as long as the published value is unchanged (a changed value needs fresh
confirmation). The fetch is also written into the existing tiingo_ref cache
(same {v, t} shape the reference cross-check uses), so when the date later
becomes Yahoo-final the reference check reuses it instead of calling again.

Key. TIINGO_API_KEY from the environment only (GitHub Actions secret). The
key is sent as an Authorization header, never in a URL or a log. No key:
no NEW freezes (a warning is printed), but already-frozen dates are still
carried forward — the freeze is durable and does not need re-confirmation.

Scope. BTC only. The recap gate is BTC-driven (btc_provisional); a missing
stock bar does not stall the recap, it holds the run or keeps the published
value. Extending to stocks is a small change (the daily endpoint is already
in the plan's symbol list) if Grok + Chief ever want it.

Wiring (PROPOSED, not applied — for Grok + Chief review). In the prices
job, after build_history and the Tiingo reference check, before validate:

    python3 tools/tiingo_unstall.py --history work/history.json \
        --prev-history <data-branch history.json> --out work/history.json

and the Final-close check's lastf() treats a tiingo_final date as final:

    tf = set((h.get('tiingo_final') or {}).keys())
    return max(d for d in h['closes'] if d not in pv or d in tf)

No other pipeline change. The recap job needs no change: recap_gen.py and
btc_daily.py already read history.json (including tiingo_final) from the
data branch.

usage: python3 tools/tiingo_unstall.py --history CANDIDATE
           [--prev-history PUBLISHED] [--out OUT] [--now ISO]
           [--max-calls N] [--stall-hours N] [--dry-run]
Exit 0 = done (frozen, carried, or nothing to do). Exit 1 = the input
history.json could not be read or written (file untouched). Exit 2 = usage
error. Stdlib only; no network in --dry-run (no fetch is attempted).
"""
import argparse, datetime as dt, json, math, os, re, sys, urllib.request

STALL_HOURS = 48
MAX_CALLS = 5
TG_TOL_BTC = 0.003          # BTC Tiingo tolerance, same as prices.yml TG_TOL['BTC']
SANITY_BAND = 0.40          # same 40% band build_history's sane() uses
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
UTC = dt.timezone.utc


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v > 0


def stall_cutoff(date, hours=STALL_HOURS):
    """The moment a date counts as stalled: its UTC day ended + `hours`.

    Same clock as tools/btc_daily.py: now - (date + 1 day) > 48 h — strictly
    greater, so exactly 48 h is NOT stalled.
    """
    return dt.datetime.fromisoformat(date).replace(tzinfo=UTC) + dt.timedelta(days=1, hours=hours)


class MalformedConfirmation(Exception):
    """Tiingo returned rows but no usable confirmation for the date:
    the row is missing its close, the close is non-numeric, or every row
    is for a different date. Raised (not swallowed) so the caller records
    it as a disagreement instead of silently accepting or skipping it."""


def tiingo_btc_close(getter, date):
    """Tiingo's RAW close for BTC on UTC date `date`, or None.

    Same request as prices.yml tiingo_close() for BTC: crypto endpoint,
    resampleFreq=1day, startDate=date, endDate=date+1. Raw 'close' only
    (never adjClose/divCash — the crypto endpoint has none). `getter` is
    an injectable fetch function (url -> parsed JSON) so tests can stub it.

    Returns None only when Tiingo returned no rows at all (absence).
    Raises MalformedConfirmation when rows exist but none carries a usable
    close for `date` (missing field, non-numeric value, wrong date).
    """
    n = (dt.date.fromisoformat(date) + dt.timedelta(days=1)).isoformat()
    j = getter('https://api.tiingo.com/tiingo/crypto/prices'
               '?tickers=btcusd&startDate=%s&endDate=%s&resampleFreq=1day' % (date, n))
    rows = (j[0].get('priceData') or []) if isinstance(j, list) and j else []
    if not rows:
        return None
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get('date', ''))[:10] != date:
            continue
        c = row.get('close')
        if not _is_num(c):
            raise MalformedConfirmation('row for %s has no usable close (%r)' % (date, c))
        return round(float(c), 6)
    raise MalformedConfirmation('no row for %s in %d returned row(s)' % (date, len(rows)))


def real_getter(key):
    """Urllib getter with the key as an Authorization header (never in a URL)."""
    def get_t(u):
        req = urllib.request.Request(u, headers={'Authorization': 'Token ' + key,
                                                 'Content-Type': 'application/json',
                                                 'User-Agent': 'paperstreetbtc-unstall'})
        with urllib.request.urlopen(req, timeout=15) as f:
            return json.load(f)
    return get_t


def _prev_btc_close(closes, date):
    """Previous session's BTC close before `date` (for the sanity band)."""
    prev = [d for d in closes if d < date]
    if not prev:
        return None
    v = closes[max(prev)].get('BTC') if isinstance(closes[max(prev)], dict) else None
    return v if _is_num(v) else None


def unstall(hist, prev_hist, getter, now, max_calls=MAX_CALLS, stall_hours=STALL_HOURS,
          dry_run=False):
    """Pure core: freeze stalled BTC dates in `hist` (mutated in place).

    Returns a report dict: {stalled, frozen, carried, skipped, disagreements,
    calls}. `getter` may be None (no key): new freezes are skipped, but
    already-frozen dates are still carried forward.
    """
    closes = (hist or {}).get('closes') or {}
    prov = set((hist or {}).get('btc_provisional') or [])
    prev_tf = ((prev_hist or {}).get('tiingo_final') or {})
    new_tf = {}
    report = {'stalled': [], 'frozen': [], 'carried': [], 'skipped': [],
              'disagreements': [], 'calls': 0}
    ref = {d: dict(v) for d, v in ((hist.get('tiingo_ref') or {}).items())}
    now_s = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    stalled = sorted(d for d in prov
                     if DATE_RE.match(d) and d in closes
                     and _is_num(closes[d].get('BTC'))
                     and now > stall_cutoff(d, stall_hours))   # strictly more than 48 h: exactly 48 h is NOT stalled
    report['stalled'] = stalled
    for d in stalled:
        published = closes[d]['BTC']
        old = prev_tf.get(d) if isinstance(prev_tf.get(d), dict) else None
        # Already frozen and the published value is unchanged: carry forward,
        # no Tiingo call. A changed value needs fresh confirmation.
        if old and old.get('BTC') == published and _is_num(old.get('tiingo')):
            new_tf[d] = old
            report['carried'].append(d)
            # Keep the cached reference value alongside the freeze, so the
            # reference check reuses it once the date becomes Yahoo-final.
            if 'BTC' not in ref.get(d, {}):
                ref.setdefault(d, {})['BTC'] = {'v': old['tiingo'],
                                                't': old.get('confirmed', now_s)}
            continue
        if dry_run:
            report['skipped'].append((d, 'dry run (no fetch)'))
            continue
        if getter is None:
            report['skipped'].append((d, 'no Tiingo key; un-stall disabled'))
            continue
        if report['calls'] >= max_calls:
            report['skipped'].append((d, 'call budget spent (%d)' % max_calls))
            continue
        report['calls'] += 1
        try:
            tv = tiingo_btc_close(getter, d)
        except MalformedConfirmation as e:
            # A malformed confirmation is REJECTED, never frozen, and
            # recorded as a disagreement — not silently accepted, not a
            # quiet skip. The date stays stalled and provisional.
            report['disagreements'].append({'date': d, 'site': published,
                                            'tiingo': None, 'diff_pct': None,
                                            'reason': 'malformed Tiingo confirmation: %s' % e})
            report['skipped'].append((d, 'malformed Tiingo confirmation (%s)' % e))
            continue
        except Exception as e:
            report['skipped'].append((d, 'Tiingo fetch failed (%s)' % type(e).__name__))
            continue
        if tv is None:
            report['skipped'].append((d, 'Tiingo returned no close'))
            continue
        prev = _prev_btc_close(closes, d)
        if prev and not (0.6 * prev <= tv <= prev / 0.6):
            # Outside the sanity band: the confirmation cannot be trusted,
            # so it is a disagreement too — never frozen on a wild value.
            diff = (tv - published) / published
            report['disagreements'].append({'date': d, 'site': published,
                                            'tiingo': tv,
                                            'diff_pct': round(diff * 100, 4),
                                            'reason': 'Tiingo value %s outside the sanity band vs previous session %s' % (tv, prev)})
            report['skipped'].append((d, 'Tiingo value %s implausible vs previous %s'
                                     % (tv, prev)))
            continue
        diff = (tv - published) / published
        if abs(diff) > TG_TOL_BTC:
            report['disagreements'].append({'date': d, 'site': published,
                                            'tiingo': tv,
                                            'diff_pct': round(diff * 100, 4),
                                            'reason': 'Tiingo disagrees beyond the 0.3% tolerance'})
            report['skipped'].append((d, 'Tiingo disagrees %+.3f%% (> %.1f%%)'
                                     % (diff * 100, TG_TOL_BTC * 100)))
            continue
        new_tf[d] = {'BTC': published, 'tiingo': tv,
                     'diff_pct': round(diff * 100, 4), 'confirmed': now_s}
        report['frozen'].append(d)
        # Cache the fetch in tiingo_ref (same shape as the reference check),
        # so the reference check reuses it once the date becomes Yahoo-final.
        ref.setdefault(d, {})['BTC'] = {'v': tv, 't': now_s}
    if new_tf:
        hist['tiingo_final'] = new_tf
    else:
        hist.pop('tiingo_final', None)
    if ref != (hist.get('tiingo_ref') or {}):
        hist['tiingo_ref'] = ref
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--history', required=True, help='candidate history.json (built by build_history)')
    ap.add_argument('--prev-history', help='published history.json (carries forward existing freezes)')
    ap.add_argument('--out', help='output path (default: overwrite --history)')
    ap.add_argument('--now', help='run time as ISO UTC (default: now); for tests')
    ap.add_argument('--max-calls', type=int, default=MAX_CALLS)
    ap.add_argument('--stall-hours', type=int, default=STALL_HOURS)
    ap.add_argument('--dry-run', action='store_true', help='no fetch, no write; report only')
    a = ap.parse_args(argv)
    if a.max_calls < 0 or a.stall_hours < 0:
        ap.error('--max-calls and --stall-hours must be >= 0')
    try:
        hist = json.load(open(a.history))
        if not isinstance(hist, dict) or not isinstance(hist.get('closes'), dict):
            raise ValueError('not a history.json (no closes dict)')
    except Exception as e:
        print('tiingo-unstall: cannot read %s: %s: %s' % (a.history, type(e).__name__, e))
        return 1
    prev = None
    if a.prev_history:
        try:
            prev = json.load(open(a.prev_history))
        except Exception as e:
            print('tiingo-unstall: cannot read %s: %s: %s (continuing without it)'
                  % (a.prev_history, type(e).__name__, e))
    now = (dt.datetime.fromisoformat(a.now.replace('Z', '+00:00')) if a.now
           else dt.datetime.now(UTC))
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    key = os.environ.get('TIINGO_API_KEY', '')
    getter = real_getter(key) if key else None
    if getter is None:
        print('tiingo-unstall: TIINGO_API_KEY not set; no new freezes (carrying forward existing ones only)')
    report = unstall(hist, prev, None if a.dry_run else getter, now,
                     max_calls=a.max_calls, stall_hours=a.stall_hours,
                     dry_run=a.dry_run)
    for f in report['disagreements']:
        if f.get('diff_pct') is None:
            print('::warning title=Tiingo un-stall disagreement::BTC %s: %s; '
                  'not frozen, recap stays stalled for this date'
                  % (f['date'], f.get('reason', 'malformed Tiingo confirmation')))
        else:
            print('::warning title=Tiingo un-stall disagreement::BTC %s: site %s vs Tiingo %s differ %+.3f%%; '
                  'not frozen, recap stays stalled for this date'
                  % (f['date'], f['site'], f['tiingo'], f['diff_pct']))
    print('tiingo-unstall: stalled=%s frozen=%s carried=%s skipped=%s calls=%d'
          % (report['stalled'], report['frozen'], report['carried'],
             [d for d, _ in report['skipped']], report['calls']))
    for d, why in report['skipped']:
        print('tiingo-unstall: %s not frozen: %s' % (d, why))
    out = a.out or a.history
    if a.dry_run:
        print('tiingo-unstall: dry run, nothing written')
        return 0
    tmp = out + '.tmp'
    try:
        json.dump(hist, open(tmp, 'w'), separators=(',', ':'), allow_nan=False)
        json.load(open(tmp))
        os.replace(tmp, out)
    except Exception as e:
        print('tiingo-unstall: cannot write %s: %s: %s' % (out, type(e).__name__, e))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
