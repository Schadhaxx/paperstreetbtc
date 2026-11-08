#!/usr/bin/env python3
"""Validate-before-publishing gate for the PaperStreet prices job (slice 1,
rework 2 — Grok Bot review #2; batch corrections 1 + 3, Grok Bot review #3).

Before any freshly built price data goes live, this checks it and either
passes it or holds it. On ANY hard failure it holds: the previous published
file is kept, the bad bar is not published, and the reason is recorded in
health.json (written on the data branch, alongside history.json/prices.json).
The Actions run itself fails on a hold, so the existing failure-email channel
already surfaces it. No new alerting in slice 1.

Publish model (review #2, corrected): a complete generation is STAGED
first, then validated, then published as ONE data-branch commit. The gate
never replaces the published files one after another: the candidates are
copied into a staging directory (in the system temp dir — no consumer
reads the intermediate workspace), the checks run on the staged copies,
and only then does publish_snapshot() install history.json + prices.json
+ health.json into the data-branch checkout and publish them with a
single `git commit`. Readers of the data branch therefore see either the
old generation or the new one, never a mix, and a process dying
mid-publish leaves HEAD untouched (the ref only moves when the commit
completes). health.json itself is always written with atomic_write()
(temp + fsync + rename), never by a bare open().

Usage (run in the prices job, on the freshly built data, BEFORE commit):
    python3 tools/validate.py --history <candidate history.json> \\
        --prices <candidate prices.json> \\
        [--prev-history <published history.json>] [--prev-prices <published prices.json>] \\
        [--ledger <assets/js/ledger.js>] --out-health <health.json> \\
        [--publish-to <dir>] [--now <ISO timestamp>]
    exit 0 = all hard checks pass (publish); exit 1 = held (do not publish);
    exit 2 = usage/input error (a required input file is missing/unreadable).
    If --publish-to is given and validation passes, the three files are
    committed there as one data-branch commit; if validation holds, only
    health.json is committed (so the hold is visible) and the published
    data is untouched. --publish-to must be a git working tree (the
    data-branch checkout); anything else fails closed. A publish that
    fails part-way rolls back the working tree, leaves HEAD untouched,
    and exits 1. The tool never pushes.

Checks (each drawn from a real past failure mode; see the slice-1 spec):
  1. parse      — files parse as JSON, have the required shape, sane sizes.
  2. sessions   — every expected NYSE session is present (holidays excepted);
                  a missing session fails, it does not silently publish a gap.
  3. values     — no null or non-positive OHLC/close on a session claimed final.
  4. jumps      — a single-session move over 35% is a split suspect, held.
  5. tiingo     — Yahoo vs Tiingo beyond the existing thresholds (>0.05%
                  stocks, >0.3% BTC) FLAGS only, never blocks: Tiingo stays
                  reference-only, exactly as today. But a confirmation that
                  is MALFORMED (bad value, missing timestamp, date/symbol
                  with no published close) or MISMATCHED FAILS: it must not
                  pass silently. A BTC confirmation for a provisional date
                  is permitted ONLY with a fully validated tiingo_final
                  freeze (see _validated_freeze): the un-stall tool's
                  freeze cache is a real confirmation of the frozen
                  published value, not a reference cross-check of a final
                  close. Validate BEFORE downstream tools trust a
                  confirmation key: the gate fully validates the
                  tiingo_final record before permitting the reference, and
                  the pipeline order is un-stall → validate gate → publish
                  → recap/btc_daily read the published file, so downstream
                  tools only ever see validated generations.
  6. provisional— a fallback-sourced BTC close must carry its provisional tag
                  WHILE its UTC day is still open (OI-001). btc_provisional
                  is time-based, not source-based: once the UTC day has
                  ended (date + 1 day + 20 min) the pipeline drops the tag
                  even when the close still came from a fallback — the
                  fallback_sources entry remains as provenance and the site
                  label keys on it, so an untagged fallback on a final date
                  is legitimate and passes. A stale tag on a final date is
                  flagged, not held (run-time straddle).
  7. dividends  — STRC record dates before pay dates, no duplicate ex-dates.
                  Amount adjudication ($0.0333 vs published $0.03/$0.04) is
                  NOT checked here — that is an open dividend decision, and
                  validation must not fail a run over it.
  8. inclusion  — the candidate must contain every date and symbol the
                  published file had (a dropped date/symbol fails even when
                  the counts look right), and every session must carry all
                  CORE_SYMBOLS. A value that changed vs the published file
                  is reported; a Yahoo final bar replacing a fallback value
                  is legitimate and passes.

Design notes (for the Grok Bot + Chief of Staff review):
  - Stdlib only. Pure checks, runnable locally (same as tools/datatest.py).
  - The holiday set is reused from tools/stock_weekly.py (the weekly tools
    already carry it); it needs extending each year, same as those tools.
  - Check 6 enforces the pipeline's actual semantics (see above): tag while
    the UTC day is open, provenance forever in fallback_sources. The first
    build required fallback => tagged unconditionally; real data proved that
    wrong (2026-11-06 BTC is coinbase-sourced, final, and untagged — and the
    site still labels it correctly from fallback_sources).
  - Check 7 needs the STRC ledger (assets/js/ledger.js) as an input; without
    it the STRC part is skipped, not failed. The history.json `divs` amounts
    are always checked.
  - Hold scope is the whole run (not per-symbol): partial publishes are how
    inconsistent pages happen. Grok decides (spec open question 4).
  - Wiring contract (Grok Bot correction 3; prices.yml itself is NOT
    changed in this slice): build to a staging dir, run this gate with
    --publish-to pointing at the data-branch checkout (a git working
    tree). The gate stages + validates, then publish_snapshot() makes
    exactly ONE commit of history+prices+health (or one health-only commit
    on a hold); the workflow pushes that commit and fails the run on a
    hold. Never commit or push the three files individually, and no
    consumer reads the intermediate staging workspace.
"""
import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
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


def _parse_ts(s):
    """Parse an ISO 8601 timestamp; None when unparseable."""
    if not isinstance(s, str) or not s:
        return None
    try:
        d = dt.datetime.fromisoformat(s.replace('Z', '+00:00'))
    except ValueError:
        return None
    return d


def _validated_freeze(hist, d, v, t):
    """Narrow rule (Grok Bot correction 1): a BTC tiingo_ref entry on a
    provisional date is permitted ONLY with a FULLY VALIDATED tiingo_final
    confirmation for the same date. Returns None when the freeze is fully
    validated, else a reason string. Every sub-check must pass — a missing
    record, or any failed sub-check, rejects the entry (never permit on key
    presence alone):
      - the date has a published BTC close in closes;
      - tiingo_final[d] is a dict;
      - tiingo_final[d]['BTC'] is finite positive and EXACTLY equal to the
        published close;
      - tiingo_final[d]['tiingo'] is finite positive and EXACTLY equal to
        the cached reference value v;
      - agreement within 0.3% (abs(tiingo/published - 1) <= TG_TOL_BTC);
      - valid timestamps for BOTH the cached t and tiingo_final[d]['confirmed'];
      - diff_pct, if present, is a finite number (not bool/NaN/string);
      - the Tiingo value is inside the sanity band vs the previous
        session's BTC close (same 0.6x..1/0.6x band tiingo_unstall.py uses).
    Booleans, NaN/Infinity and non-numeric values are rejected by _is_num.
    A v of None (recorded miss) is rejected by the caller, not here: there
    is no validated confirmation to permit it.
    """
    closes = (hist or {}).get('closes') or {}
    tf = (hist or {}).get('tiingo_final')
    if d not in closes or not isinstance(closes.get(d), dict):
        return 'no published close for that date'
    site = closes[d].get('BTC')
    if not _is_num(site) or site <= 0:
        return 'no usable published BTC close for that date'
    if not isinstance(tf, dict):
        return 'no tiingo_final record for that date'
    rec = tf.get(d)
    if not isinstance(rec, dict):
        return 'no tiingo_final record for that date'
    if not _is_num(rec.get('BTC')) or rec['BTC'] <= 0 or rec['BTC'] != site:
        return 'tiingo_final BTC does not equal the published close'
    if not _is_num(rec.get('tiingo')) or rec['tiingo'] <= 0 or rec['tiingo'] != v:
        return 'tiingo_final tiingo does not match the cached reference value'
    if abs(rec['tiingo'] / site - 1) > TG_TOL_BTC:
        return 'Tiingo disagrees with the published close by more than 0.3%'
    if _parse_ts(t) is None:
        return 'cached reference timestamp missing/unparseable'
    if _parse_ts(rec.get('confirmed')) is None:
        return 'tiingo_final confirmed timestamp missing/unparseable'
    if 'diff_pct' in rec and not _is_num(rec.get('diff_pct')):
        return 'tiingo_final diff_pct is not a finite number'
    prev_dates = sorted(x for x in closes
                        if x < d and isinstance(closes.get(x), dict)
                        and _is_num(closes[x].get('BTC')) and closes[x]['BTC'] > 0)
    if prev_dates:
        prev = closes[prev_dates[-1]]['BTC']
        if not (0.6 * prev <= rec['tiingo'] <= prev / 0.6):
            return 'Tiingo value outside the sanity band vs the previous session close'
    return None


def check_tiingo(hist, prev_hist=None):
    """Check 5: Tiingo confirmations, validated not just compared.

    A disagreement beyond the reference tolerance (>0.05% stocks, >0.3%
    BTC) FLAGS only, never blocks — Tiingo stays reference-only, exactly as
    today. But a confirmation that is MALFORMED or MISMATCHED FAILS, so it
    can never pass silently:
      - entry not an object, or `v` neither null (a recorded miss — allowed)
        nor a finite positive number, or `t` missing/unparseable;
      - date invalid, or with no close in the candidate (dangling);
      - symbol with no close on that date;
      - a BTC confirmation for a date in btc_provisional: permitted ONLY
        with a FULLY VALIDATED tiingo_final freeze for that date (see
        _validated_freeze) — the slice-2 un-stall tool freezes a stalled
        date by caching its Tiingo fetch in tiingo_ref AND recording the
        confirmation in tiingo_final, while the date stays provisional by
        design. A missing tiingo_final record, a recorded miss (v null),
        or any failed validation sub-check FAILS; a fully validated freeze
        falls through to the normal comparison below.
      - EVERY tiingo_final entry is validated too (Grok Bot fix 3):
        downstream code trusts any tiingo_final entry as a validated
        confirmation, so an entry with no companion tiingo_ref BTC entry
        for that date — the un-stall tool always writes both together —
        FAILS as inconsistent, and every entry must pass the same full
        validation as _validated_freeze (dict; date with a published BTC
        close; BTC exactly the published close; tiingo finite positive
        and matching the cached reference; agreement within 0.3%; valid
        confirmed timestamp; finite diff_pct if present; Tiingo value
        inside the sanity band vs the previous session's close).
    Each confirmation is validated against the published BTC value (the
    candidate close) at the reference tolerance; when the candidate value
    for a date changed vs the previously published file (a Yahoo final bar
    replacing a fallback value — legitimate, see check 8) and the
    confirmation matches the OLD published value instead, the flag says so,
    so a stale confirmation is never mistaken for a live disagreement.
    A missing confirmation is not a failure: Tiingo may be down, out of
    calls, or unconfigured, and the pipeline explicitly never blocks on it.
    """
    ref = (hist or {}).get('tiingo_ref') or {}
    tf = (hist or {}).get('tiingo_final') or {}
    # Skip only when there is nothing to check at all: a tiingo_final
    # entry with no tiingo_ref must still reach the tiingo_final loop
    # below (a lone tiingo_final is a failure, not a skip).
    if not ref and not tf:
        return _result('tiingo', 'skip', 'no tiingo_ref in candidate')
    closes = (hist or {}).get('closes') or {}
    prov = set((hist or {}).get('btc_provisional') or [])
    prev_closes = (prev_hist or {}).get('closes') or {}
    problems, flags = [], []
    compared = 0
    for d in sorted(ref):
        entries = ref[d]
        if not isinstance(entries, dict):
            problems.append('tiingo_ref %s: not an object' % d)
            continue
        if _parse_date(d) is None:
            problems.append('tiingo_ref %s: bad date' % d)
            continue
        if d not in closes or not isinstance(closes.get(d), dict):
            problems.append('tiingo_ref %s: no published close for that date' % d)
            continue
        for s, entry in sorted(entries.items()):
            if not isinstance(entry, dict):
                problems.append('tiingo_ref %s %s: not an object' % (d, s))
                continue
            v, t = entry.get('v'), entry.get('t')
            if v is not None and (not _is_num(v) or v <= 0):
                problems.append('tiingo_ref %s %s: bad value %r' % (d, s, v))
                continue
            if _parse_ts(t) is None:
                problems.append('tiingo_ref %s %s: missing/unparseable timestamp' % (d, s))
                continue
            if s not in closes[d]:
                problems.append('tiingo_ref %s %s: no published close for that symbol' % (d, s))
                continue
            if s == 'BTC' and d in prov:
                if v is None:
                    # A recorded miss has no validated confirmation to
                    # permit it; the "recorded miss passes" principle
                    # applies only to final dates.
                    problems.append('tiingo_ref %s BTC: recorded miss (v null) on a '
                                    'provisional date — no validated confirmation' % d)
                    continue
                reason = _validated_freeze(hist, d, v, t)
                if reason is not None:
                    problems.append('tiingo_ref %s BTC: provisional-date confirmation '
                                    'not fully validated (%s)' % (d, reason))
                    continue
                # Fully validated freeze: fall through to the normal
                # comparison below (counted as compared; it passes, since
                # agreement is within 0.3%).
            if v is None:
                continue  # recorded miss: no reference yet, not a failure
            site = closes[d][s]
            if not _is_num(site) or site <= 0:
                continue  # bad site value is check 3's job, not this check's
            compared += 1
            tol = TG_TOL_BTC if s == 'BTC' else TG_TOL_STOCK
            if abs(v / site - 1) > tol:
                note = ''
                prev_v = prev_closes.get(d, {}).get(s) if isinstance(prev_closes.get(d), dict) else None
                if _is_num(prev_v) and prev_v != site and abs(v / prev_v - 1) <= tol:
                    note = ' (confirmation matches the previously published value' \
                           ' — stale after a Yahoo replacement)'
                flags.append('%s %s site=%s tiingo=%s (%+.3f%%)%s'
                             % (d, s, site, v, (v / site - 1) * 100, note))
    # Grok Bot fix 3: validate EVERY tiingo_final entry, not only the
    # ones a tiingo_ref entry points at. The ref loop above never
    # iterates tiingo_final, so a tiingo_final entry with no companion
    # tiingo_ref used to escape validation entirely while downstream
    # code (recap_gen etc.) trusts any tiingo_final entry as a validated
    # confirmation. The un-stall tool always writes tiingo_final and
    # tiingo_ref together, so a lone tiingo_final entry is inconsistent
    # and FAILS. Entries WITH a companion ref are fully validated here
    # with _validated_freeze — the same checks the ref loop applies on
    # provisional dates — so this loop is also the safety net for any
    # record the ref loop did not cover (e.g. a final-date entry whose
    # cached value drifted from the frozen one).
    if not isinstance(tf, dict):
        problems.append('tiingo_final: not an object')
    else:
        for d in sorted(tf):
            rec = tf[d]
            if not isinstance(rec, dict):
                problems.append('tiingo_final %s: not an object' % d)
                continue
            if _parse_date(d) is None:
                problems.append('tiingo_final %s: bad date' % d)
                continue
            ref_entries = ref.get(d) if isinstance(ref, dict) else None
            btc_ref = ref_entries.get('BTC') if isinstance(ref_entries, dict) else None
            if not isinstance(btc_ref, dict):
                problems.append('tiingo_final %s: no companion tiingo_ref BTC entry '
                                'for that date — a lone tiingo_final is not trusted' % d)
                continue
            reason = _validated_freeze(hist, d, btc_ref.get('v'), btc_ref.get('t'))
            if reason is not None:
                problems.append('tiingo_final %s: not fully validated (%s)' % (d, reason))
    if problems:
        return _result('tiingo', 'fail', '; '.join(problems[:10]))
    if flags:
        return _result('tiingo', 'flag',
                       'reference disagreement (non-blocking): %s' % '; '.join(flags[:10]))
    return _result('tiingo', 'pass', '%d reference values within tolerance' % compared)


def _btc_final(d, now):
    """True once a BTC UTC day's close is final: date + 1 day + 20 min (UTC).

    Mirrors prices.yml final_btc(): the pipeline re-fetches a BTC close
    until this moment, then the date leaves btc_provisional for good.
    """
    dd = _parse_date(d)
    if dd is None or now is None:
        return False
    due = dt.datetime.combine(dd, dt.time(0, 0), tzinfo=UTC) + dt.timedelta(days=1, minutes=20)
    return now >= due


def check_provisional(hist, now):
    """Check 6: a fallback-sourced BTC close must carry its provisional tag
    WHILE its UTC day is still open (OI-001).

    btc_provisional is time-based, not source-based: the pipeline lists a
    date there exactly while its UTC day has not ended. Once the day is
    final the tag is dropped even when the close still came from a fallback
    (e.g. 2026-11-06: BTC coinbase-sourced, final, untagged) — the
    fallback_sources entry remains as provenance and the site label keys on
    it, so that is legitimate and passes. What must never happen is an
    untagged fallback while the day is still open: the reader would see a
    final-looking close that is really a backup-source value. A tag left on
    a final date is stale, but only flagged (a run straddling the 00:20 UTC
    boundary could produce one transiently). A tag for a date with no BTC
    close fails, as before. The converse is still not required (provisional
    does not need a fallback_sources entry): a close can be provisional
    simply because Yahoo's final bar has not arrived yet.
    """
    closes = (hist or {}).get('closes') or {}
    prov = (hist or {}).get('btc_provisional') or []
    fb = (hist or {}).get('fallback_sources') or {}
    problems, stale = [], []
    for d in prov:
        if d not in closes or not _is_num(closes.get(d, {}).get('BTC')):
            problems.append('provisional %s has no BTC close' % d)
        elif _btc_final(d, now):
            stale.append(d)
    for d in sorted(fb):
        entry = fb[d] or {}
        if isinstance(entry, dict) and _is_fallback_source(entry.get('BTC')):
            if d not in closes or not _is_num(closes.get(d, {}).get('BTC')):
                continue  # a tag with no close is check 1/2 territory
            if not _btc_final(d, now) and d not in prov:
                problems.append('%s: BTC fallback-sourced (%s) on an open UTC day'
                                ' but not tagged provisional' % (d, entry.get('BTC')))
    if problems:
        return _result('provisional', 'fail', '; '.join(problems[:10]))
    if stale:
        return _result('provisional', 'flag',
                       'stale provisional tag on final date(s): %s' % ', '.join(stale[:5]))
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


def check_inclusion(new_hist, new_prices, prev_hist, prev_prices):
    """Check 8: the candidate must include what the published file had.

    Counts alone do not prove inclusion: a candidate that drops one date
    and adds another, or drops one symbol and adds another, can have
    identical counts. So compare sets, not sizes:
      - every date in the published closes must be in the candidate closes;
      - every symbol the published file had on a date must be there still;
      - every candidate session must carry all CORE_SYMBOLS (a symbol
        dropped from every session is invisible to the count checks);
      - every live symbol in the published prices.json must be there still.
    A value that CHANGED vs the published file is reported, not failed: a
    Yahoo final bar replacing a fallback/provisional value is legitimate
    (the pipeline logs it in revisions_ignored and drops the fallback tag).
    A changed value whose previous source was a fallback and whose new
    source is Yahoo/primary is named as a legitimate replacement; any other
    change is named too, so a silent rewrite is always visible in health.
    """
    problems, notes = [], []
    new_closes = (new_hist or {}).get('closes') or {}
    new_fb = (new_hist or {}).get('fallback_sources') or {}
    prev_closes = (prev_hist or {}).get('closes') or {}
    prev_fb = (prev_hist or {}).get('fallback_sources') or {}
    dropped_dates = sorted(set(prev_closes) - set(new_closes))
    if dropped_dates:
        problems.append('dropped published date(s): %s' % ', '.join(dropped_dates[:10]))
    dropped_syms = []
    for d in sorted(set(prev_closes) & set(new_closes)):
        prev_row = prev_closes[d] if isinstance(prev_closes[d], dict) else {}
        new_row = new_closes[d] if isinstance(new_closes[d], dict) else {}
        for s in sorted(set(prev_row) - set(new_row)):
            dropped_syms.append('%s %s' % (d, s))
    if dropped_syms:
        problems.append('dropped published symbol(s): %s' % ', '.join(dropped_syms[:10]))
    missing_core = []
    for d in sorted(new_closes):
        row = new_closes[d]
        if isinstance(row, dict):
            missing = sorted(set(CORE_SYMBOLS) - set(row.keys()))
            if missing:
                missing_core.append('%s: %s' % (d, ', '.join(missing)))
    if missing_core:
        problems.append('session(s) missing core symbol(s): %s' % '; '.join(missing_core[:5]))
    new_stocks = (new_prices or {}).get('stocks') or {}
    prev_stocks = (prev_prices or {}).get('stocks') or {}
    dropped_live = sorted(set(prev_stocks) - set(new_stocks))
    if dropped_live:
        problems.append('dropped published live symbol(s): %s' % ', '.join(dropped_live[:10]))
    replaced = []
    for d in sorted(set(prev_closes) & set(new_closes)):
        prev_row = prev_closes[d] if isinstance(prev_closes[d], dict) else {}
        new_row = new_closes[d] if isinstance(new_closes[d], dict) else {}
        for s in sorted(set(prev_row) & set(new_row)):
            a, b = prev_row[s], new_row[s]
            if _is_num(a) and _is_num(b) and a != b:
                old_src = (prev_fb.get(d) or {}).get(s, 'yahoo')
                new_src = (new_fb.get(d) or {}).get(s, 'yahoo')
                legit = _is_fallback_source(old_src) and not _is_fallback_source(new_src)
                replaced.append('%s %s %s->%s (%s->%s%s)'
                                % (d, s, a, b, old_src, new_src,
                                   ', legitimate Yahoo replacement' if legit else ''))
    if replaced:
        notes.append('changed vs published: %s' % '; '.join(replaced[:5]))
    if problems:
        return _result('inclusion', 'fail', '; '.join(problems))
    detail = '%d dates, %d symbols incl. core, %d live stocks; %s' % (
        len(new_closes),
        len({s for row in new_closes.values() if isinstance(row, dict) for s in row}),
        len(new_stocks),
        '; '.join(notes) if notes else ('no previous file to compare'
                                        if not prev_closes else 'nothing dropped, nothing changed'))
    return _result('inclusion', 'pass', detail)


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
        results.append(check_tiingo(new_hist, prev_hist))
        results.append(check_provisional(new_hist, now))
    else:
        results.append(_result('tiingo', 'skip', 'no usable history.json'))
        results.append(_result('provisional', 'skip', 'no usable history.json'))
    results.append(check_dividends(new_hist if hist_ok else None, ledger_text))
    if hist_ok and prices_ok:
        results.append(check_inclusion(new_hist, new_prices, prev_hist, prev_prices))
    else:
        results.append(_result('inclusion', 'skip', 'no usable history.json/prices.json'))
    ok = all(r['status'] != 'fail' for r in results)
    return results, ok


# ---------------------------------------------------------------- atomic publish

# Module-level indirection for os.replace: the fault-injection point the
# tests use to prove a failure mid-write cannot corrupt a single file.
_replace = os.replace


def _run_git(args, cwd):
    """Run git in `cwd`; the fault-injection point the tests use to prove a
    failure at the commit boundary cannot publish a partial snapshot."""
    return subprocess.run(['git'] + args, cwd=cwd, capture_output=True, text=True)


class PublishError(Exception):
    """A publish step failed; the published snapshot was rolled back."""


def _fsync_dir(path):
    """Best-effort fsync of a directory (so a rename is durable)."""
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def atomic_write(path, data):
    """Write bytes to path atomically: temp file in the same directory,
    flush + fsync, rename over the destination, fsync the directory.

    A reader never sees a partial file, and a failure before the rename
    leaves the previous file untouched. Used for health.json and for every
    file of a published snapshot.
    """
    path = os.path.abspath(path)
    d = os.path.dirname(path)
    tmp = os.path.join(d, '.%s.tmp-%d' % (os.path.basename(path), os.getpid()))
    try:
        with open(tmp, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        _replace(tmp, path)
        _fsync_dir(d)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _restore_publish(publish_dir, staged):
    """Best-effort restore of the publish working tree after a failed
    publish: each file back to its previous bytes (or removed, if it did
    not exist before), then `git reset` to clear the index. Never raises:
    the original failure is the one reported, and HEAD is untouched either
    way — the ref only moves when a commit completes."""
    for name, _new, old_bytes in staged:
        dest = os.path.join(publish_dir, name)
        try:
            if old_bytes is None:
                os.unlink(dest)
            else:
                atomic_write(dest, old_bytes)
        except Exception:
            pass
    try:
        _run_git(['reset', '-q'], publish_dir)
    except Exception:
        pass


def publish_snapshot(files, publish_dir, message=None):
    """Publish a complete generation as ONE data-branch commit.

    `files` is a list of (src_path, dest_name) — the staged, already
    validated generation (history + prices + health). `publish_dir` MUST
    be a git working tree (the data-branch checkout); anything else fails
    closed with PublishError — there is no sequential-rename fallback, so
    a reader can never see a mixed generation. The tool does NOT push.

    Every source is read fully into memory first; each file is then
    written into the working tree with atomic_write, `git add` stages the
    named files, and ONE `git commit` publishes the whole generation at
    once. If the tree already matches (nothing staged), it reports
    already-published with NO empty commit. Returns (names, committed):
    the published names, and whether a new commit was made.

    The index must be CLEAN when publish runs: the plain `git commit`
    below commits EVERYTHING staged, so a file staged before this publish
    ran would be swept into the snapshot commit. Before reading or
    writing any file, the index is checked (`git diff --cached --quiet`);
    if anything is already staged, the publish is REJECTED with
    PublishError and nothing is changed — no file read or written, no
    commit made. Consistency covers COMMITTED snapshots, not intermediate
    working files: a publish either lands one complete generation as one
    commit on a clean index, or it does not run at all.

    On any failure before the commit, the working tree is restored to its
    previous bytes and the index reset, and PublishError is raised — the
    published snapshot stays the old generation. KeyboardInterrupt /
    SystemExit are re-raised as-is (process-death semantics preserved);
    the HEAD invariant holds regardless, since the ref only moves when
    the commit completes. A commit failing for missing git identity fails
    loudly (PublishError), never silently.
    """
    try:
        r = _run_git(['rev-parse', '--git-dir'], publish_dir)
    except OSError as e:
        raise PublishError('publish_dir is not a git working tree: %s (%s)'
                           % (publish_dir, e))
    if r.returncode != 0:
        raise PublishError('publish_dir is not a git working tree: %s' % publish_dir)
    r = _run_git(['rev-parse', '--is-bare-repository'], publish_dir)
    if r.returncode != 0 or (r.stdout or '').strip() != 'false':
        raise PublishError('publish_dir is not a git working tree: %s' % publish_dir)
    # Grok Bot fix 2: reject an already-staged index BEFORE changing
    # anything (before reading/writing any file). A plain `git commit`
    # commits everything staged, so unrelated files staged before this
    # publish ran would be swept into the snapshot commit. `git diff
    # --cached --quiet` exits 0 when the index is clean, 1 when staged
    # changes are present; any other exit code is a git failure.
    try:
        r = _run_git(['diff', '--cached', '--quiet'], publish_dir)
    except OSError as e:
        raise PublishError('git diff --cached failed: %s' % e)
    if r.returncode == 1:
        raise PublishError('git index already has staged changes; refusing to publish '
                           'into a dirty index: %s' % publish_dir)
    if r.returncode != 0:
        raise PublishError('git diff --cached failed: %s' % (r.stderr or r.stdout).strip())
    staged = []  # (dest_name, new_bytes, old_bytes_or_None)
    for src, name in files:
        with open(src, 'rb') as f:
            new_bytes = f.read()
        dest = os.path.join(publish_dir, name)
        try:
            with open(dest, 'rb') as f:
                old_bytes = f.read()
        except OSError:
            old_bytes = None
        staged.append((name, new_bytes, old_bytes))
    names = [name for name, _n, _o in staged]
    try:
        for name, new_bytes, _old in staged:
            atomic_write(os.path.join(publish_dir, name), new_bytes)
        r = _run_git(['add', '--'] + names, publish_dir)
        if r.returncode != 0:
            raise PublishError('git add failed: %s' % (r.stderr or r.stdout).strip())
        # Nothing staged means the tree already matches this generation:
        # already published, no empty commit.
        r = _run_git(['status', '--porcelain', '--'] + names, publish_dir)
        if r.returncode != 0:
            raise PublishError('git status failed: %s' % (r.stderr or r.stdout).strip())
        if not (r.stdout or '').strip():
            return names, False
        msg = message or 'PaperStreet prices snapshot'
        r = _run_git(['commit', '-m', msg], publish_dir)
        if r.returncode != 0:
            if 'nothing to commit' in ((r.stdout or '') + (r.stderr or '')):
                return names, False
            raise PublishError('git commit failed: %s' % (r.stderr or r.stdout).strip())
    except (KeyboardInterrupt, SystemExit):
        _restore_publish(publish_dir, staged)
        raise
    except PublishError:
        _restore_publish(publish_dir, staged)
        raise
    except BaseException as e:
        _restore_publish(publish_dir, staged)
        raise PublishError('publish failed part-way (rolled back): %s' % e)
    return names, True


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
    ap.add_argument('--publish-to', help='if validation passes, publish the staged '
                    'history+prices+health there as one snapshot; if held, publish '
                    'only health.json (the hold stays visible) and leave the data alone')
    ap.add_argument('--now', help='run timestamp, ISO 8601 (default: now UTC)')
    a = ap.parse_args(argv)
    now = _parse_now(a.now)

    for p in (a.history, a.prices):
        if not os.path.exists(p):
            print('error: required input missing: %s' % p, file=sys.stderr)
            return 2

    # Stage the complete generation first, then validate the STAGED copies:
    # what is checked is byte-for-byte what would be published. The staging
    # dir lives in the system temp dir (NOT inside --publish-to): no
    # consumer reads the intermediate workspace, and it leaves no untracked
    # clutter in the data checkout. Without --publish-to there is nothing
    # to stage into, so validate in place.
    staged_hist, staged_prices, staging_dir = a.history, a.prices, None
    if a.publish_to:
        staging_dir = tempfile.mkdtemp(prefix='.staging-')
        try:
            for src, name in ((a.history, 'history.json'), (a.prices, 'prices.json')):
                shutil.copyfile(src, os.path.join(staging_dir, name))
        except OSError as e:
            print('error: cannot stage candidates: %s' % e, file=sys.stderr)
            shutil.rmtree(staging_dir, ignore_errors=True)
            return 2
        staged_hist = os.path.join(staging_dir, 'history.json')
        staged_prices = os.path.join(staging_dir, 'prices.json')

    new_hist, hist_err = _load_json(staged_hist)
    new_prices, prices_err = _load_json(staged_prices)
    prev_hist, _ = _load_json(a.prev_history) if a.prev_history else (None, None)
    prev_prices, _ = _load_json(a.prev_prices) if a.prev_prices else (None, None)
    sizes = {}
    for key, cand, prev in (('history', staged_hist, a.prev_history),
                            ('prices', staged_prices, a.prev_prices)):
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
            if staging_dir:
                shutil.rmtree(staging_dir, ignore_errors=True)
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
    health_bytes = (json.dumps(health, indent=1, sort_keys=True) + '\n').encode('utf-8')
    # Health is always written atomically (temp + fsync + rename): a reader
    # never sees a partial health file.
    try:
        atomic_write(a.out_health, health_bytes)
    except OSError as e:
        print('error: cannot write health file %s: %s' % (a.out_health, e), file=sys.stderr)
        if staging_dir:
            shutil.rmtree(staging_dir, ignore_errors=True)
        return 2

    for r in results:
        print('%-12s %-4s %s' % (r['check'], r['status'], r['detail']))
    print('status: %s' % status)
    if hold_reason:
        print('hold_reason: %s' % hold_reason)
    print('health: %s' % a.out_health)
    try:
        if a.publish_to:
            # Publish ONE data-branch commit from the staging directory. On
            # a pass: history + prices + health together. On a hold: health
            # only, so the hold is visible while the published data stays
            # untouched. The staging dir is always removed afterwards, even
            # when publishing raises (e.g. a process kill at the commit).
            staged_health = os.path.join(staging_dir, 'health.json')
            with open(staged_health, 'wb') as f:
                f.write(health_bytes)
            publish_files = ([(staged_hist, 'history.json'),
                              (staged_prices, 'prices.json'),
                              (staged_health, 'health.json')] if ok else
                             [(staged_health, 'health.json')])
            msg = 'PaperStreet prices snapshot %s%s' % (
                now.strftime('%Y-%m-%dT%H:%M:%SZ'),
                '' if ok else ' (held: health only)')
            try:
                names, committed = publish_snapshot(publish_files, a.publish_to,
                                                    message=msg)
            except PublishError as e:
                print('publish failed: %s' % e, file=sys.stderr)
                print('published: (rolled back, previous snapshot kept)')
                return 1
            if committed:
                print('published: %s (one commit)' % ', '.join(names))
            else:
                print('published: %s (already published, no new commit)'
                      % ', '.join(names))
    finally:
        if staging_dir:
            shutil.rmtree(staging_dir, ignore_errors=True)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())

