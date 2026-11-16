#!/usr/bin/env python3
"""Desk watchdog: cancel GitHub Actions runs stuck in 'queued'/'in_progress'.

Incident (Mon 2026-11-16): a desk-intraday dispatch (run 43888136076,
9:40 AM ET) sat in 'queued' with ZERO jobs for ~50 min while the
dispatches before (9:35) and after (9:45, 9:50, 10:00, 10:05, 10:10,
10:15) all completed. The workflow's concurrency group
(desk-intraday, cancel-in-progress: false) was FREE at 14:40 UTC (the
9:35 run finished 14:35:27), so this was a GitHub-side glitch, not a
workflow problem. The run eventually started late (15:30:08Z) and
succeeded — but a 50-min-late run is useless on a 5-min cadence, and
the run could not be cancelled from the GitHub web UI either ("Failed
to cancel workflow", three attempts). This script is the automation:
it lists recent runs, finds the stuck ones, and cancels them via the
GitHub REST API (the API route is the untested part — the first live
run of the watchdog workflow is the test of it).

Scope: the two 5-minute workflows ONLY — desk-intraday and prices.
Normal runs take ~15-45 s and the job timeout is 10 min, so a run
still queued/in_progress more than 15 min after creation is
definitely stuck. The watchdog workflow itself is never a target
(it is not one of the two watched workflows), so this script can
never cancel its own run.

Behaviour:
- Lists recent runs via GET /repos/{repo}/actions/runs (unauthenticated
  reads work on this public repo; a token is only needed to cancel).
- Cancels each stuck run via POST .../actions/runs/{id}/cancel, but
  only when a token (GH_TOKEN or GITHUB_TOKEN) is present and
  --dry-run is NOT set. A cancel that fails (e.g. 422 because the run
  already finished) is logged, not fatal.
- Exit 0 when the runs list works, even if a cancel fails. Exit
  non-zero only if the runs list itself cannot be fetched.
- Never touches repo contents, branches, or any other workflow.

Usage (run by .github/workflows/desk-watchdog.yml every 15 min in
market hours, and manually with workflow_dispatch):
    python3 tools/desk_watchdog.py [--dry-run] [--repo OWNER/REPO]
                                   [--max-age-minutes N]
"""

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"
UA = {"User-Agent": "paperstreet-desk-watchdog"}

# The two 5-minute workflows. Anything else (including the watchdog
# workflow itself) is never a cancel target.
WATCHED_WORKFLOWS = ("desk-intraday", "prices")


def _parse_time(s):
    # '2026-11-16T14:40:04Z' -> aware datetime (fromisoformat in
    # older Pythons does not accept the trailing Z).
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def _get(url, token):
    headers = dict(UA)
    headers["Accept"] = "application/vnd.github+json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def list_runs(repo, token, max_pages=3):
    """Recent runs, newest first, across a few pages.

    Stops early once the page's oldest run is far older than any
    run we could care about (the watchdog ticks every 15 min, so a
    stuck run is always recent); never fetches more than max_pages.
    """
    runs = []
    url = API + "/repos/%s/actions/runs?per_page=100" % repo
    for _ in range(max_pages):
        data = _get(url, token)
        page = data.get("workflow_runs", [])
        if not page:
            break
        runs.extend(page)
        oldest = _parse_time(page[-1]["created_at"])
        age_min = (dt.datetime.now(dt.timezone.utc) - oldest).total_seconds() / 60.0
        if age_min > 180:
            break
        links = data.get("_links", {})
        nxt = (links.get("next") or {}).get("href")
        if not nxt:
            break
        url = nxt
    return runs


def cancel_run(repo, run_id, token):
    """POST cancel. Returns (ok, detail): ok True on 202, else the
    HTTP status / error string. Never raises for an HTTP error."""
    url = API + "/repos/%s/actions/runs/%s/cancel" % (repo, run_id)
    headers = dict(UA)
    headers["Accept"] = "application/vnd.github+json"
    headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=b"", headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return True, "HTTP %d" % r.status
    except urllib.error.HTTPError as e:
        try:
            detail = json.load(e).get("message", "")
        except Exception:
            detail = ""
        return False, "HTTP %d%s" % (e.code, (" " + detail) if detail else "")
    except Exception as e:  # network error etc.
        return False, str(e)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Cancel stuck desk-intraday / prices runs.")
    ap.add_argument("--repo", default="Schadhaxx/paperstreetbtc",
                    help="owner/repo (default Schadhaxx/paperstreetbtc)")
    ap.add_argument("--max-age-minutes", type=int, default=15,
                    help="a queued/in_progress run older than this is stuck (default 15)")
    ap.add_argument("--dry-run", action="store_true",
                    help="list what WOULD be cancelled; never call cancel")
    args = ap.parse_args(argv)

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    now = dt.datetime.now(dt.timezone.utc)

    try:
        runs = list_runs(args.repo, token)
    except Exception as e:
        print("watchdog: ERROR listing runs: %s" % e, file=sys.stderr)
        return 2

    stuck = []
    for r in runs:
        if r.get("name") not in WATCHED_WORKFLOWS:
            continue
        if r.get("status") not in ("queued", "in_progress"):
            continue
        age_min = (now - _parse_time(r["created_at"])).total_seconds() / 60.0
        if age_min > args.max_age_minutes:
            stuck.append((r, age_min))

    if not stuck:
        print("watchdog: checked %d recent runs, no stuck %s runs (max age %d min)"
              % (len(runs), "/".join(WATCHED_WORKFLOWS), args.max_age_minutes))
        return 0

    cancelled, failed, skipped = 0, 0, 0
    for r, age_min in stuck:
        run_id = r["id"]
        line = ("watchdog: STUCK run=%s workflow=%s status=%s age_min=%.1f created=%s"
                % (run_id, r["name"], r["status"], age_min, r["created_at"]))
        print("::warning::" + line)
        print(line)
        if args.dry_run:
            print("watchdog: dry-run: would cancel run %s (not cancelling)" % run_id)
            skipped += 1
            continue
        if not token:
            print("watchdog: no token (GH_TOKEN/GITHUB_TOKEN unset): cannot cancel run %s" % run_id)
            skipped += 1
            continue
        ok, detail = cancel_run(args.repo, run_id, token)
        if ok:
            print("watchdog: cancelled run %s (%s)" % (run_id, detail))
            cancelled += 1
        else:
            # e.g. 422: the run finished between list and cancel.
            # Logged, not fatal — the next tick re-checks.
            print("watchdog: cancel FAILED for run %s (%s)" % (run_id, detail))
            failed += 1

    print("watchdog: stuck=%d cancelled=%d failed=%d skipped=%d"
          % (len(stuck), cancelled, failed, skipped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
