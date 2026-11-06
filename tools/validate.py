#!/usr/bin/env python3
"""Validate-before-publishing gate for the PaperStreet prices job (slice 1).

Before any freshly built price data goes live, this checks it and either
passes it or holds it. On ANY hard failure it holds: the previous published
file is kept, the bad bar is not published, and the reason is recorded in
health.json (written on the data branch, alongside history.json/prices.json).
The Actions run itself fails on a hold, so the existing failure-email channel
already surfaces it. No new alerting in slice 1.

Usage (run in the prices job, on the freshly built data, BEFORE commit):
    python3 tools/validate.py --history <candidate history.json> \\
        --prices <candidate prices.json> \\
        [--prev-history <published history.json>] [--prev-prices <published prices.json>] \\
        [--ledger <assets/js/ledger.js>] --out-health <health.json> \\
        [--publish-to <dir>] [--now <ISO timestamp>]
    exit 0 = all hard checks pass (publish); exit 1 = held (do not publish);
    exit 2 = usage/input error (a required input file is missing/unreadable).

Checks (each drawn from a real past failure mode; see the slice-1 spec):
  1. parse      — files parse as JSON, have the required shape, sane sizes.
  2. sessions   — every expected NYSE session is present (holidays excepted);
                  a missing session fails, it does not silently publish a gap.
  3. values     — no null or non-positive OHLC/close on a session claimed final.
  4. jumps      — a single-session move over 35% is a split suspect, held.
  5. tiingo     — Yahoo vs Tiingo beyond the existing thresholds (>0.05%
                  stocks, >0.3% BTC) FLAGS only, never blocks: Tiingo stays
                  reference-only, exactly as today. A Tiingo disagreement
                  does NOT hold a run.
  6. provisional— a fallback-sourced BTC close must carry its provisional tag
                  (OI-001: tag by actual fallback source, not just by time).
  7. dividends  — STRC record dates before pay dates, no duplicate ex-dates.
                  Amount adjudication ($0.0333 vs published $0.03/$0.04) is
                  NOT checked here — that is an open dividend decision, and
                  validation must not fail a run over it.

Design notes (for the Grok Bot + Chief of Staff review):
  - Stdlib only. Pure checks, runnable locally (same as tools/datatest.py).
  - The holiday set is reused from tools/stock_weekly.py (the weekly tools
    already carry it); it needs extending each year, same as those tools.
  - Check 6 enforces the direction the pipeline actually records
    (fallback source => tagged). It does NOT require the converse
    (provisional => a fallback_sources entry), because a close can be
    provisional simply because Yahoo's final bar has not arrived yet
    (e.g. 2026-11-06 is provisional with no fallback_sources BTC entry).
  - Check 7 needs the STRC ledger (assets/js/ledger.js) as an input; without
    it the STRC part is skipped, not failed. The history.json `divs` amounts
    are always checked.
  - Hold scope is the whole run (not per-symbol): partial publishes are how
    inconsistent pages happen. Grok decides (spec open question 4).
  - The prices.yml wiring is NOT in this slice (proposal for review only):
    build to a temp dir, run this gate, commit the new files only on exit 0;
    on exit 1 commit only health.json so the hold is visible, and fail the run.
"""
import argparse
import json
import math
import os
import re
import shutil
import sys
import datetime as dt
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from stock_weekly import HOLIDAYS as _HOLIDAYS
except Exception:  # pragma: no cover - fallback if the weekly tool is absent
    _HOLIDAYS = {
        '2026-01-01', '2026-01-19', '2026-02-16', '2026-04-03', '2026-05-25',
        '2026-06-19', '2026-07-03', '2026-09-07', '2026-11-26', '2026-12-25',
        '2027-01-01', '2027-01-18', '2027-02-15', '2027-03-26', '2027-05-31',
        '2027-06-18', '2027-07-05', '2027-09-06', '2027-11-25', '2027-12-24',
        '2028-01-17', '2028-02-21', '2028-04-14', '2028-05-29', '2028-06-19',
        '2028-07-04', '2028-09-04', '2028-11-23', '2028-12-25',
    }
HOLIDAYS = _HOLIDAYS

NY = ZoneInfo('America/New_York')
UTC = dt.timezone.utc

JUMP_MAX = 0.35            # single-session move over 35% = split suspect
TG_TOL_BTC = 0.003         # Tiingo disagreement threshold, BTC (0.3%)
TG_TOL_STOCK = 0.0005      # Tiingo disagreement threshold, stocks (0.05%)
SESSION_CLOSE_HM = (16, 0)  # NYSE session close, for price-age computation

CORE_SYMBOLS = ('BTC', 'MSTR', 'STRC', 'TSLA', 'PLTR', 'SPY', 'QQQ', 'BRK.B', 'GLD')

# STRC declared dividends in ledger.js: [record, ex-date, pay date, $/share]
STRC_DIV_RE = re.compile(
    r"\[\s*'(\d{4}-\d\d-\d\d)'\s*,\s*'(\d{4}-\d\d-\d\d)'\s*,"
    r"\s*'(\d{4}-\d\d-\d\d)'\s*,\s*([\d.]+)\s*\]")


def _is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _parse_date(s):
    try:
        return dt.date.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def _result(name, status, detail=''):
    return {'check': name, 'status': status, 'detail': detail}


def expected_sessions(d0, d1):
    """NYSE session dates in [d0, d1]: weekdays minus the holiday set."""
    out = []
    d = d0
    while d <= d1:
        if d.weekday() < 5 and d.isoformat() not in HOLIDAYS:
            out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


def _is_fallback_source(src):
    """True if a recorded source is a fallback (not Yahoo, not a forward-fill).

    Mirrors tools/btc_daily.py: a source counts as a fallback when its first
    hyphen-segment is neither 'yahoo' nor 'ffill' (e.g. 'coinbase').
    """
    if not isinstance(src, str) or not src:
        return False
    return src.split('-')[0] not in ('yahoo', 'ffill')


# ---------------------------------------------------------------- checks

def check_parse(new_hist, new_prices, prev_hist, prev_prices, sizes):
    """Check 1: files parse as JSON, have the required shape, sane sizes.

    `new_hist` / `new_prices` are (obj, error) pairs from loading the
    candidate files; `prev_*` the same for the previous published files
    (obj may be None when there is no previous file); `sizes` maps
    'history'/'prices' to (new_bytes, prev_bytes_or_None).
    """
    problems = []
    hist, hist_err = new_hist
    prices, prices_err = new_prices
    if hist_err:
        problems.append('history.json does not parse: %s' % hist_err)
    elif not isinstance(hist, dict):
        problems.append('history.json is not a JSON object')
    else:
        if not isinstance(hist.get('closes'), dict) or not hist['closes']:
            problems.append('history.json has no closes')
        if hist.get('v') != 1:
            problems.append('history.json v != 1 (got %r)' % (hist.get('v'),))
        if not hist.get('base'):
            problems.append('history.json has no base date')
    if prices_err:
        problems.append('prices.json does not parse: %s' % prices_err)
    elif not isinstance(prices, dict):
        problems.append('prices.json is not a JSON object')
    else:
        if not isinstance(prices.get('stocks'), dict) or not prices['stocks']:
            problems.append('prices.json has no stocks')
        btc = prices.get('btc') or {}
        if not _is_num(btc.get('usd')) or btc['usd'] <= 0:
            problems.append('prices.json btc.usd is not a positive number')
        if not prices.get('updated'):
            problems.append('prices.json has no updated timestamp')
    # Sane sizes: a candidate must never shrink the history (data loss), and
    # must not be absurdly smaller or larger than the previous file.
    if isinstance(hist, dict) and isinstance(prev_hist[0], dict):
        if len(hist.get('closes') or {}) < len(prev_hist[0].get('closes') or {}):
            problems.append('history.json shrank: %d closes vs %d published'
                            % (len(hist.get('closes') or {}),
                               len(prev_hist[0].get('closes') or {})))
    if isinstance(prices, dict) and isinstance(prev_prices[0], dict):
        if len(prices.get('stocks') or {}) < len(prev_prices[0].get('stocks') or {}):
            problems.append('prices.json shrank: %d stocks vs %d published'
                            % (len(prices.get('stocks') or {}),
                               len(prev_prices[0].get('stocks') or {})))
    for key in ('history', 'prices'):
        new_b, prev_b = sizes.get(key, (None, None))
        if new_b is not None and prev_b:
            if new_b < prev_b * 0.1:
                problems.append('%s is <10%% of the published file (%d vs %d bytes: truncated?)'
                                % (key, new_b, prev_b))
            if new_b > prev_b * 10:
                problems.append('%s is >10x the published file (%d vs %d bytes)'
                                % (key, new_b, prev_b))
    if problems:
        return _result('parse', 'fail', '; '.join(problems))
    n_close = len(hist['closes'])
    n_stock = len(prices['stocks'])
    return _result('parse', 'pass',
                   '%d closes, %d live stocks' % (n_close, n_stock))


def check_sessions(closes, today):
    """Check 2: every expected NYSE session is present (holidays excepted)."""
    dates = sorted(d for d in closes if _parse_date(d))
    if not dates:
        return _result('sessions', 'fail', 'no dated closes')
    d0, d1 = _parse_date(dates[0]), _parse_date(dates[-1])
    missing = [d for d in expected_sessions(d0, d1) if d not in closes]
    future = [d for d in dates if _parse_date(d) > today]
    if missing:
        return _result('sessions', 'fail',
                       'missing sessions: %s' % ', '.join(missing[:10]))
    if future:
        return _result('sessions', 'fail',
                       'close dated in the future: %s' % ', '.join(future[:5]))
    return _result('sessions', 'pass',
                   '%d sessions %s..%s, no gaps' % (len(dates), dates[0], dates[-1]))


def check_values(closes, prices):
    """Check 3: no null or non-positive close on a session claimed final."""
    problems = []
    if closes:
        base_syms = set(next(iter([closes[d] for d in sorted(closes)]), {}).keys())
        for d in sorted(closes):
            row = closes[d]
            if not isinstance(row, dict):
                problems.append('%s: not an object' % d)
                continue
            if not base_syms.issubset(set(row.keys())):
                problems.append('%s: missing symbols %s'
                                % (d, sorted(base_syms - set(row.keys()))))
            for s, v in row.items():
                if not _is_num(v) or v <= 0:
                    problems.append('%s %s: bad close %r' % (d, s, v))
    if prices:
        for s, q in (prices.get('stocks') or {}).items():
            if not isinstance(q, dict):
                problems.append('prices %s: not an object' % s)
                continue
            for k in ('c', 'pc'):
                if not _is_num(q.get(k)) or q[k] <= 0:
                    problems.append('prices %s.%s: bad value %r' % (s, k, q.get(k)))
            if not _is_num(q.get('t')) or q['t'] <= 0:
                problems.append('prices %s.t: bad timestamp %r' % (s, q.get('t')))
    if problems:
        return _result('values', 'fail', '; '.join(problems[:10]))
    return _result('values', 'pass', 'all closes and quotes finite and positive')


def check_jumps(closes):
    """Check 4: a single-session move over 35% is a split suspect, held."""
    dates = sorted(d for d in closes if _parse_date(d))
    syms = set()
    for d in dates:
        if isinstance(closes[d], dict):
            syms |= set(closes[d].keys())
    jumps = []
    for i in range(1, len(dates)):
        prev, cur = closes[dates[i - 1]], closes[dates[i]]
        if not isinstance(prev, dict) or not isinstance(cur, dict):
            continue
        for s in sorted(syms):
            a, b = prev.get(s), cur.get(s)
            if _is_num(a) and a > 0 and _is_num(b) and b > 0:
                if abs(b / a - 1) > JUMP_MAX:
                    jumps.append('%s %s %s->%s (%+.1f%%)'
                                 % (dates[i], s, a, b, (b / a - 1) * 100))
    if jumps:
        return _result('jumps', 'fail',
                       'split suspect (move >35%%): %s' % '; '.join(jumps[:10]))
    return _result('jumps', 'pass', 'no single-session move over 35%')


def check_tiingo(hist):
    """Check 5: Yahoo vs Tiingo beyond the thresholds FLAGS only, never blocks.

    Tiingo stays reference-only, exactly as today: a disagreement is recorded
    in the validation output (and in health.json) but does not hold the run.
    """
    ref = (hist or {}).get('tiingo_ref') or {}
    if not ref:
        return _result('tiingo', 'skip', 'no tiingo_ref in candidate')
    closes = (hist or {}).get('closes') or {}
    flags = []
    compared = 0
    for d in sorted(ref):
        for s, entry in sorted((ref[d] or {}).items()):
            v = entry.get('v') if isinstance(entry, dict) else entry
            site = closes.get(d, {}).get(s) if isinstance(closes.get(d), dict) else None
            if not _is_num(v) or not _is_num(site) or site <= 0:
                continue
            compared += 1
            tol = TG_TOL_BTC if s == 'BTC' else TG_TOL_STOCK
            if abs(v / site - 1) > tol:
                flags.append('%s %s site=%s tiingo=%s (%+.3f%%)'
                             % (d, s, site, v, (v / site - 1) * 100))
    if flags:
        return _result('tiingo', 'flag',
                       'reference disagreement (non-blocking): %s' % '; '.join(flags[:10]))
    return _result('tiingo', 'pass', '%d reference values within tolerance' % compared)


def check_provisional(hist):
    """Check 6: a fallback-sourced BTC close must carry its provisional tag.

    OI-001: tag by actual fallback source, not just by time. Enforces the
    direction the pipeline records (fallback source => tagged). Does NOT
    require the converse (provisional => a fallback_sources entry): a close
    can be provisional simply because Yahoo's final bar has not arrived yet.
    """
    closes = (hist or {}).get('closes') or {}
    prov = (hist or {}).get('btc_provisional') or []
    fb = (hist or {}).get('fallback_sources') or {}
    problems = []
    for d in prov:
        if d not in closes or not _is_num(closes.get(d, {}).get('BTC')):
            problems.append('provisional %s has no BTC close' % d)
    for d in sorted(fb):
        entry = fb[d] or {}
        if isinstance(entry, dict) and _is_fallback_source(entry.get('BTC')):
            if d not in prov:
                problems.append('%s: BTC fallback-sourced (%s) but not tagged provisional'
                                % (d, entry.get('BTC')))
    if problems:
        return _result('provisional', 'fail', '; '.join(problems[:10]))
    return _result('provisional', 'pass',
                   '%d provisional BTC date(s) tagged' % len(prov))


def check_dividends(hist, ledger_text):
    """Check 7: STRC record dates before pay dates, no duplicate ex-dates.

    Amount adjudication is deliberately NOT checked: the flat $0.0333 vs
    published $0.03/$0.04 split is an open dividend decision, and validation
    must not fail a run over it.
    """
    problems = []
    divs = (hist or {}).get('divs') or {}
    for s, entries in divs.items():
        if not isinstance(entries, dict):
            problems.append('divs %s: not an object' % s)
            continue
        for d, amt in entries.items():
            if _parse_date(d) is None:
                problems.append('divs %s: bad date %r' % (s, d))
            if not _is_num(amt) or amt <= 0:
                problems.append('divs %s %s: bad amount %r' % (s, d, amt))
    if ledger_text is None:
        if problems:
            return _result('dividends', 'fail', '; '.join(problems[:10]))
        return _result('dividends', 'skip',
                       'history divs ok; STRC ledger not supplied, skipped')
    try:
        rows = STRC_DIV_RE.findall(ledger_text)
    except Exception as e:  # pragma: no cover - regex on a string cannot fail
        return _result('dividends', 'fail', 'ledger parse error: %s' % e)
    if not rows:
        return _result('dividends', 'fail', 'no STRC dividend entries found in ledger')
    seen_ex = set()
    for rec, ex, pay, amt in rows:
        if not (rec < pay and ex < pay):
            problems.append('STRC %s: pay %s not after record/ex' % (ex, pay))
        if ex in seen_ex:
            problems.append('STRC %s: duplicate ex-date' % ex)
        seen_ex.add(ex)
        if not _is_num(float(amt)) or float(amt) <= 0:
            problems.append('STRC %s: bad amount %r' % (ex, amt))
    if problems:
        return _result('dividends', 'fail', '; '.join(problems[:10]))
    return _result('dividends', 'pass',
                   '%d STRC entries, record<pay, ex-dates unique' % len(rows))


# ---------------------------------------------------------------- health

def _price_age_minutes(last_close_date, now):
    """Minutes from the last close date's 16:00 ET session close to now."""
    if last_close_date is None:
        return None
    close_dt = dt.datetime.combine(last_close_date, dt.time(*SESSION_CLOSE_HM), tzinfo=NY)
    return max(0, int((now - close_dt).total_seconds() // 60))


def build_health(hist, prices, results, now, status, hold_reason=None):
    """Build the health.json dict (spec format) for this run."""
    closes = (hist or {}).get('closes') or {}
    fb = (hist or {}).get('fallback_sources') or {}
    prov = set((hist or {}).get('btc_provisional') or [])
    stocks = (prices or {}).get('stocks') or {}
    symbols = {}
    all_syms = set()
    for d, row in closes.items():
        if isinstance(row, dict):
            all_syms |= set(row.keys())
    all_syms |= set(stocks.keys())
    for s in sorted(all_syms):
        last = None
        for d in sorted(closes):
            if isinstance(closes[d], dict) and s in closes[d]:
                last = _parse_date(d)
        entry = {'last_close_date': last.isoformat() if last else None,
                 'price_age_minutes': None, 'source': 'yahoo', 'provisional': False}
        if last is not None:
            src = (fb.get(last.isoformat()) or {}).get(s)
            entry['source'] = src if isinstance(src, str) and src else 'yahoo'
            entry['provisional'] = bool(
                (s == 'BTC' and last.isoformat() in prov) or
                s in (fb.get(last.isoformat()) or {}))
            entry['price_age_minutes'] = _price_age_minutes(last, now)
        q = stocks.get(s) or {}
        if last is None and _is_num(q.get('t')) and q['t'] > 0:
            t = dt.datetime.fromtimestamp(q['t'], tz=UTC)
            entry['last_close_date'] = t.astimezone(NY).date().isoformat()
            entry['price_age_minutes'] = max(0, int((now - t).total_seconds() // 60))
            entry['source'] = 'live'
            entry['provisional'] = False
        symbols[s] = entry
    health = {
        'last_run': now.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'status': status,
        'symbols': symbols,
        'validation': results,
    }
    if hold_reason:
        health['hold_reason'] = hold_reason
    return health


# ---------------------------------------------------------------- orchestration

def validate_all(new_hist, hist_err, new_prices, prices_err,
                 prev_hist, prev_prices, sizes, ledger_text, now):
    """Run all checks. Returns (results, ok). 'flag'/'skip' never fail a run.

    A malformed candidate file is a check-1 failure; the checks that depend
    on it are skipped, but the checks on the other (usable) file still run.
    """
    results = []
    hist_ok = hist_err is None and isinstance(new_hist, dict) \
        and isinstance(new_hist.get('closes'), dict)
    prices_ok = prices_err is None and isinstance(new_prices, dict) \
        and isinstance(new_prices.get('stocks'), dict)
    results.append(check_parse((new_hist, hist_err), (new_prices, prices_err),
                               (prev_hist, None), (prev_prices, None), sizes))
    if hist_ok:
        results.append(check_sessions(new_hist['closes'], now.astimezone(NY).date()))
        results.append(check_values(new_hist['closes'],
                                    new_prices if prices_ok else None))
        results.append(check_jumps(new_hist['closes']))
    else:
        results.append(_result('sessions', 'skip', 'no usable history.json'))
        results.append(_result('values', 'skip', 'no usable history.json'))
        results.append(_result('jumps', 'skip', 'no usable history.json'))
    if hist_ok:
        results.append(check_tiingo(new_hist))
        results.append(check_provisional(new_hist))
    else:
        results.append(_result('tiingo', 'skip', 'no usable history.json'))
        results.append(_result('provisional', 'skip', 'no usable history.json'))
    results.append(check_dividends(new_hist if hist_ok else None, ledger_text))
    ok = all(r['status'] != 'fail' for r in results)
    return results, ok


def publish_or_hold(candidate_files, published_dir, ok):
    """Copy candidate files into published_dir only if validation passed.

    candidate_files: list of (src_path, dest_name). On hold the published
    directory is left untouched (previous file kept). Returns
    ('published', [names]) or ('held', []).
    """
    if not ok:
        return 'held', []
    os.makedirs(published_dir, exist_ok=True)
    names = []
    for src, name in candidate_files:
        shutil.copyfile(src, os.path.join(published_dir, name))
        names.append(name)
    return 'published', names


def _load_json(path):
    """Returns (obj, error). error is None on success."""
    try:
        with open(path, 'rb') as f:
            raw = f.read()
    except OSError as e:
        return None, 'cannot read: %s' % e
    try:
        return json.loads(raw.decode('utf-8')), None
    except (ValueError, UnicodeDecodeError) as e:
        return None, 'invalid JSON: %s' % e


def _parse_now(s):
    if not s:
        return dt.datetime.now(UTC)
    try:
        d = dt.datetime.fromisoformat(s.replace('Z', '+00:00'))
    except ValueError:
        raise SystemExit('bad --now value: %r (use ISO 8601)' % s)
    return d.astimezone(UTC) if d.tzinfo else d.replace(tzinfo=UTC)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description='Validate-before-publishing gate (Python supercharge slice 1).')
    ap.add_argument('--history', required=True, help='candidate history.json (freshly built)')
    ap.add_argument('--prices', required=True, help='candidate prices.json (freshly built)')
    ap.add_argument('--prev-history', help='previously published history.json')
    ap.add_argument('--prev-prices', help='previously published prices.json')
    ap.add_argument('--ledger', help='assets/js/ledger.js (STRC dividend list, optional)')
    ap.add_argument('--out-health', required=True, help='where to write health.json')
    ap.add_argument('--publish-to', help='if validation passes, copy candidates here')
    ap.add_argument('--now', help='run timestamp, ISO 8601 (default: now UTC)')
    a = ap.parse_args(argv)
    now = _parse_now(a.now)

    for p in (a.history, a.prices):
        if not os.path.exists(p):
            print('error: required input missing: %s' % p, file=sys.stderr)
            return 2
    new_hist, hist_err = _load_json(a.history)
    new_prices, prices_err = _load_json(a.prices)
    prev_hist, _ = _load_json(a.prev_history) if a.prev_history else (None, None)
    prev_prices, _ = _load_json(a.prev_prices) if a.prev_prices else (None, None)
    sizes = {}
    for key, cand, prev in (('history', a.history, a.prev_history),
                            ('prices', a.prices, a.prev_prices)):
        try:
            nb = os.path.getsize(cand)
        except OSError:
            nb = None
        pb = None
        if prev:
            try:
                pb = os.path.getsize(prev)
            except OSError:
                pb = None
        sizes[key] = (nb, pb)

    # A malformed candidate is a check-1 failure, not a usage error: the gate
    # must hold (and record why) rather than crash the workflow. The checks
    # on the other (usable) file still run.
    ledger_text = None
    if a.ledger:
        if not os.path.exists(a.ledger):
            print('error: ledger file missing: %s' % a.ledger, file=sys.stderr)
            return 2
        ledger_text = open(a.ledger, encoding='utf-8').read()
    results, ok = validate_all(new_hist, hist_err, new_prices, prices_err,
                               prev_hist, prev_prices, sizes, ledger_text, now)

    fails = [r for r in results if r['status'] == 'fail']
    status = 'ok' if ok else 'held'
    hold_reason = '; '.join('%s: %s' % (r['check'], r['detail']) for r in fails) if fails else None
    health = build_health(new_hist if isinstance(new_hist, dict) else None,
                          new_prices if isinstance(new_prices, dict) else None,
                          results, now, status, hold_reason)
    with open(a.out_health, 'w', encoding='utf-8') as f:
        json.dump(health, f, indent=1, sort_keys=True)
        f.write('\n')

    for r in results:
        print('%-12s %-4s %s' % (r['check'], r['status'], r['detail']))
    print('status: %s' % status)
    if hold_reason:
        print('hold_reason: %s' % hold_reason)
    print('health: %s' % a.out_health)
    if a.publish_to:
        decision, names = publish_or_hold(
            [(a.history, 'history.json'), (a.prices, 'prices.json')],
            a.publish_to, ok)
        print('%s: %s' % (decision, ', '.join(names) if names else 'previous file kept'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
