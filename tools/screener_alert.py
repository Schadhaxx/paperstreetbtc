#!/usr/bin/env python3
"""Decide whether the recap job's screener-daily fail-loud step should go red.

The step fires when the screener-daily step reports failed symbols or stale
ind-daily files. Left as-is it goes red on EVERY 5-minute run for as long as
the underlying gap lasts, emailing Sunil each time (the Nov 23-27 pattern:
Yahoo blanks a close, the run turns red after publish, and the same alert
repeats until Yahoo heals). Two guards, both from Grok Bot's plan
(Fri 27 Nov 2026, follow-up #1):

(a) Alert once. If this failure is identical to the previous completed run's
    alert -- same failed symbols, same stale keys, same session date -- it
    is a repeat of an already-alerted incident. Stay quiet until the
    signature changes (i.e. until the files move). A new session failing
    the same way is a NEW alert, not a repeat.
(b) Stay quiet when the published files already hold that session's close.
    For each failed symbol, check its published daily file's asOf against
    the session date (the null-close date from the screener log). A symbol
    whose file already holds the session's close is not a miss. When the
    log has NO null-close date the session cannot be derived from the
    published files (their newest asOf is their own date, so the check
    would always say "already published" and a real outage would go
    silent) -- check (b) is skipped and the run is a real miss; the
    session date for the alert/dedupe is then derived independently
    (screener_daily.cutoff_date, now ET).

A real miss still goes red (exit 1). Quiet exits 0. When the repeat check
cannot run (no GitHub API credentials, or the lookup fails) the tool fails
OPEN and alerts -- a missed alert is noise, a suppressed real miss is not.

Run: python3 tools/screener_alert.py --failed "TSLA, DIA" --stale "" \
         --log /tmp/screener-daily.log --data-dir assets/data
The GitHub lookup reads GITHUB_REPOSITORY, GITHUB_RUN_ID and GH_TOKEN from
the environment (all three are set in the prices.yml recap job). Without
them the repeat check is skipped and the tool alerts on any real miss.
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.request
import urllib.error

# Daily file for each screener key (mirrors tools/screener_daily.py ALL).
# A test pins this mapping against screener_daily.ALL so a rename in one
# place fails loudly in the other.
FILEMAP = {
    'TSLA': 'stock-daily-TSLA.json', 'PLTR': 'stock-daily-PLTR.json',
    'MSTR': 'stock-daily-MSTR.json', 'IBIT': 'stock-daily-IBIT.json',
    'MU': 'stock-daily-MU.json', 'META': 'stock-daily-META.json',
    'SPCX': 'stock-daily-SPCX.json', 'BRK.B': 'stock-daily-BRK.B.json',
    'AAPL': 'stock-daily-AAPL.json', 'AMZN': 'stock-daily-AMZN.json',
    'MSFT': 'stock-daily-MSFT.json', 'NFLX': 'stock-daily-NFLX.json',
    'SPOT': 'stock-daily-SPOT.json', 'XYZ': 'stock-daily-XYZ.json',
    'GOOGL': 'stock-daily-GOOGL.json', 'NVDA': 'stock-daily-NVDA.json',
    'WTI': 'ind-daily-wti.json', 'GOLD': 'ind-daily-gold.json',
    'US10Y': 'ind-daily-us10y.json', 'VIX': 'ind-daily-vix.json',
    'DIA': 'ind-daily-dia.json',
}

NULL_RE = re.compile(r'null close on (\d{4}-\d{2}-\d{2})')
# The alert line this tool prints (and the previous run's annotation
# carries). The session date is part of the signature so a new session
# failing the same way is a new alert, not a repeat.
ALERT_RE = re.compile(
    r'screener-daily failed for:\s*([^;]*);\s*ind-daily stale:\s*([^;.]*)'
    r'(?:;\s*session:\s*(\d{4}-\d{2}-\d{2}))?\.')


def parse_list(s):
    """Split a comma-separated step output into a sorted unique list."""
    if not s:
        return []
    return sorted({p.strip() for p in s.split(',') if p.strip()})


def session_date_from_log(log_path):
    """Newest null-close date in the screener log, or None.

    The gen step logs "FAILED TSLA: TSLA: null close on 2026-11-27 ..."
    for each symbol whose Yahoo bar had a null close. The date is the
    session the run was trying to fill.
    """
    try:
        with open(log_path) as f:
            text = f.read()
    except Exception:
        return None
    dates = NULL_RE.findall(text)
    if not dates:
        return None
    return dt.date.fromisoformat(max(dates))


def cutoff_session(now=None):
    """Last completed session date, derived independently of the
    published files (screener_daily.cutoff_date, now ET).

    Used only as the dedupe label and the alert's session date when the
    screener log has no null-close date -- never as the coverage
    criterion for check (b). Returns None when the derivation is
    unavailable; the caller then alerts with no session date (fail
    open, no dedupe).
    """
    try:
        import screener_daily as sd
    except Exception:
        return None
    if now is None:
        now = dt.datetime.now(sd.ET)
    try:
        return sd.cutoff_date(now)
    except Exception:
        return None


def file_asof(data_dir, key):
    """asOf date of a symbol's published daily file, or None."""
    fname = FILEMAP.get(key)
    if not fname:
        return None
    try:
        with open(os.path.join(data_dir, fname)) as f:
            doc = json.load(f)
        return dt.date.fromisoformat(doc['asOf'])
    except Exception:
        return None


def newest_asof(data_dir):
    """Newest asOf across all published daily files, or None."""
    best = None
    for key in FILEMAP:
        a = file_asof(data_dir, key)
        if a is not None and (best is None or a > best):
            best = a
    return best


def uncovered(failed, stale, session_date, data_dir):
    """Symbols/keys whose published file does NOT hold the session date.

    A failed symbol is covered when its daily file's asOf equals the
    session date (the close is already published, so the gen failure is
    not a data miss). A stale key is covered the same way. Returns the
    sorted list of uncovered keys; empty means nothing is actually
    missing and the step should stay quiet.
    """
    out = []
    for key in sorted(set(failed) | set(stale)):
        if file_asof(data_dir, key) != session_date:
            out.append(key)
    return out


def signature(failed, stale, session_date):
    """Canonical signature for repeat detection."""
    return 'failed=%s; stale=%s; session=%s' % (
        ','.join(parse_list(','.join(failed))),
        ','.join(parse_list(','.join(stale))),
        session_date or '')


def parse_alert_message(msg):
    """Parse a previous run's alert line into (failed, stale, session).

    Handles both the new format (with "; session: YYYY-MM-DD") and the
    old format (no session date) -- the old one predates this tool, so
    its session is None and the caller treats it as unmatchable.
    Returns None when the message is not an alert line at all.
    """
    if not msg:
        return None
    m = ALERT_RE.search(msg)
    if not m:
        return None
    return (parse_list(m.group(1)), parse_list(m.group(2)), m.group(3))


def gh_api(path, token):
    """GET a GitHub API path, returning the parsed JSON (or raising)."""
    req = urllib.request.Request(
        'https://api.github.com' + path,
        headers={'Authorization': 'token ' + token,
                 'Accept': 'application/vnd.github+json',
                 'User-Agent': 'paperstreet-screener-alert'})
    with urllib.request.urlopen(req, timeout=30) as f:
        return json.load(f)


def prev_alert_signature(repo, run_id, token, _gh_api=None, max_runs=20):
    """Signature of the most recent screener alert in recent runs.

    Walks back through the most recent completed prices runs (newest
    first) and returns the signature of the first alert line found. A
    quiet run carries no alert, so the walk must skip quiet runs --
    otherwise the first repeat would be the last alert ever seen (the
    run right after an alert is quiet, so its recap job has no alert
    line, and the chain would break on the second repeat).
    Returns None when no alert is found in the window (or the lookup
    fails); the caller treats None as "cannot confirm a repeat" and
    alerts (fails open). A window of 20 runs is ~100 min at the 5-min
    cadence, so a very long incident re-alerts about hourly -- a
    reminder, not the every-5-minutes flood.
    """
    gh = _gh_api or gh_api
    try:
        runs = gh('/repos/%s/actions/workflows/prices.yml/runs'
                  '?per_page=%d&status=completed' % (repo, max_runs), token)
        for r in runs.get('workflow_runs', []):
            if r.get('id', 0) >= run_id:
                continue
            jobs = gh('/repos/%s/actions/runs/%s/jobs?per_page=20'
                      % (repo, r['id']), token)
            recap = None
            for j in jobs.get('jobs', []):
                if j.get('name') == 'recap':
                    recap = j
                    break
            if recap is None:
                continue
            anns = gh('/repos/%s/check-runs/%s/annotations'
                      % (repo, recap['id']), token)
            for a in anns:
                parsed = parse_alert_message(a.get('message') or '')
                if parsed is None:
                    continue
                failed, stale, session = parsed
                if session is None:
                    # Old-format alert line (predates the session date):
                    # cannot confirm it is the same incident.
                    return None
                return signature(failed, stale, session)
        return None
    except Exception as e:
        print('::warning::repeat check failed (%s: %s); alerting'
              % (type(e).__name__, e))
        return None


def decide(failed, stale, log_path, data_dir, repo=None, run_id=None,
           token=None, _gh_api=None, now=None):
    """Return (exit_code, message). 0 = stay quiet, 1 = go red."""
    failed = parse_list(failed) if isinstance(failed, str) else sorted(failed)
    stale = parse_list(stale) if isinstance(stale, str) else sorted(stale)
    session = session_date_from_log(log_path)
    if session is None:
        # No null-close date in the log: the run failed for another
        # reason (Yahoo fetch error/outage, "missing N completed
        # session(s)", bad close). The session cannot be derived from
        # the published files -- newest_asof(data_dir) is the files'
        # own date, so check (b) would compare the files against
        # themselves and call every failed symbol "already published",
        # and a real outage would go silent (Grok Bot must-fix, Fri
        # 27 Nov). Skip check (b) entirely: every failed/stale key is
        # a real miss. The session date is derived independently
        # (cutoff_date, now ET) and is used ONLY as the dedupe label
        # and the alert's session date, never as the coverage
        # criterion.
        missing = list(failed) + list(stale)
        session = cutoff_session(now)
    else:
        # (b) Stay quiet when the published files already hold the session.
        missing = uncovered(failed, stale, session, data_dir)
    if not missing:
        return (0, 'quiet: published files already hold session %s '
                   '(failed: %s; stale: %s)'
                   % (session, ','.join(failed), ','.join(stale)))
    # Real miss. (a) Alert once: quiet if the previous completed run
    # alerted on the identical signature.
    if repo and run_id and token:
        prev = prev_alert_signature(repo, run_id, token, _gh_api=_gh_api)
        if prev is not None and prev == signature(failed, stale, session):
            return (0, 'quiet: repeat of previous alert (%s)' % prev)
    return (1, '::error::screener-daily failed for: %s; ind-daily stale: %s; '
               'session: %s. The recap still published; see the '
               'screener-daily step log.'
               % (', '.join(failed), ', '.join(stale), session or ''))


def main(argv):
    failed = stale = log_path = data_dir = ''
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--failed':
            failed = argv[i + 1]; i += 2
        elif a == '--stale':
            stale = argv[i + 1]; i += 2
        elif a == '--log':
            log_path = argv[i + 1]; i += 2
        elif a == '--data-dir':
            data_dir = argv[i + 1]; i += 2
        else:
            print('unknown arg %s' % a, file=sys.stderr)
            return 2
    if not log_path or not data_dir:
        print('--log and --data-dir are required', file=sys.stderr)
        return 2
    repo = os.environ.get('GITHUB_REPOSITORY')
    run_id = os.environ.get('GITHUB_RUN_ID')
    token = os.environ.get('GH_TOKEN')
    try:
        run_id = int(run_id) if run_id else None
    except ValueError:
        run_id = None
    code, msg = decide(failed, stale, log_path, data_dir,
                       repo=repo, run_id=run_id, token=token)
    print(msg)
    return code


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
