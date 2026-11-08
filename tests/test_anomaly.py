#!/usr/bin/env python3
"""Tests for tools/anomaly.py (Python supercharge, slice 4).

No network. Run with: python3 tests/test_anomaly.py (exit 0 = all pass).

A clean synthetic history + ledger reports no anomalies. Each planted
anomaly — a split, an absurd jump, a missing session, a dividend double,
a stale symbol, a stale live quote — is found and labelled. The clean
real-data check (today's history.json + ledger.js: no anomalies) is
documented in the review note; it is run by hand because history.json
lives on the data branch, not in this repo.
"""

import copy
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import anomaly  # noqa: E402

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("PASS %s" % name)
    else:
        FAIL += 1
        print("FAIL %s %s" % (name, detail))


# --- clean synthetic history: 6 sessions, BTC + TSLA, no jumps --------
CLEAN = {
    "2026-01-02": {"BTC": 100000.0, "TSLA": 400.0},
    "2026-01-05": {"BTC": 101000.0, "TSLA": 404.0},
    "2026-01-06": {"BTC": 102000.0, "TSLA": 408.0},
    "2026-01-07": {"BTC": 103000.0, "TSLA": 412.0},
    "2026-01-08": {"BTC": 104000.0, "TSLA": 416.0},
    "2026-01-09": {"BTC": 105000.0, "TSLA": 420.0},
}
DATES = sorted(CLEAN)
# STRC ledger: monthly 0.5, a transitional half 0.25 followed by the new
# 0.25 regime, then daily 0.0333 — regime changes that must NOT trip the
# double detector (the half is 0.5x its previous neighbour but 1x its
# next, so it is not ~0.5x BOTH neighbours).
CLEAN_STRC = [
    ["2026-01-15", "2026-01-15", "2026-01-31", 0.5],
    ["2026-02-15", "2026-02-13", "2026-02-28", 0.5],
    ["2026-03-15", "2026-03-13", "2026-03-31", 0.5],
    ["2026-03-30", "2026-03-30", "2026-04-15", 0.25],
    ["2026-04-15", "2026-04-15", "2026-04-30", 0.25],
    ["2026-11-01", "2026-11-01", "2026-11-02", 0.0333333333],
    ["2026-11-02", "2026-11-02", "2026-11-03", 0.0333333333],
    ["2026-11-03", "2026-11-03", "2026-11-04", 0.0333333333],
]


def run_all(closes, strc=None, prices=None, now=None):
    dates = sorted(closes)
    out = []
    out += anomaly.check_jumps(dates, closes)
    out += anomaly.check_sessions(dates, closes, anomaly.load_holidays())
    if strc is not None:
        out += anomaly.check_dividends(strc)
    from datetime import datetime, timezone
    n = (datetime.strptime(now, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc) if now
        else datetime(2026, 1, 9, 21, 0, tzinfo=timezone.utc))
    out += anomaly.check_stale(dates, closes, prices, n,
                               anomaly.load_holidays())
    return out


def kinds(found):
    return sorted({a["kind"] for a in found})


def test_clean():
    found = run_all(copy.deepcopy(CLEAN), CLEAN_STRC)
    check("clean reports nothing", found == [], found)


def test_split():
    """TSLA doubles on 2026-01-07 and STAYS doubled (a real 2:1 split)
    — flagged as a split with factor 2, not just a jump."""
    c = copy.deepcopy(CLEAN)
    for d in ("2026-01-07", "2026-01-08", "2026-01-09"):
        c[d]["TSLA"] = c[d]["TSLA"] * 2
    found = run_all(c, CLEAN_STRC)
    splits = [a for a in found if a["kind"] == "split"]
    check("split found", len(splits) == 1, found)
    check("split factor 2", splits and splits[0]["split_factor"] == 2,
          splits)
    check("split date", splits and splits[0]["date"] == "2026-01-07", splits)
    check("no jump alongside", "jump" not in kinds(found), found)


def test_absurd_jump():
    """BTC +50% on one day only, reverting the next — an absurd jump,
    not a split (1.5x is no round split factor)."""
    c = copy.deepcopy(CLEAN)
    c["2026-01-07"]["BTC"] = 150000.0  # +47.06% vs 102000, then back
    c["2026-01-08"]["BTC"] = 104000.0
    found = run_all(c, CLEAN_STRC)
    jumps = [a for a in found if a["kind"] == "jump"]
    check("jump found", len(jumps) == 1, found)
    check("jump pct", jumps and abs(jumps[0]["pct"] - 47.06) < 0.1, jumps)
    check("no split label", "split" not in kinds(found), found)


def test_reverse_split():
    """TSLA halves on 2026-01-07 and stays halved (a 1:2 reverse split)."""
    c = copy.deepcopy(CLEAN)
    for d in ("2026-01-07", "2026-01-08", "2026-01-09"):
        c[d]["TSLA"] = c[d]["TSLA"] / 2
    found = run_all(c, CLEAN_STRC)
    splits = [a for a in found if a["kind"] == "split"]
    check("reverse split found", len(splits) == 1, found)
    check("reverse split factor 0.5",
          splits and splits[0]["split_factor"] == 0.5, splits)


def test_missing_session():
    """Remove Wednesday 2026-01-07 (a weekday, not a holiday) — the
    detective flags the missing session."""
    c = copy.deepcopy(CLEAN)
    del c["2026-01-07"]
    found = run_all(c, CLEAN_STRC)
    miss = [a for a in found if a["kind"] == "missing_session"]
    check("missing session found", len(miss) == 1, found)
    check("missing date", miss and miss[0]["date"] == "2026-01-07", miss)


def test_weekend_not_missing():
    """Saturday/Sunday are not sessions, so a history that skips them
    is not flagged (the clean set already skips 2026-01-03/04)."""
    found = run_all(copy.deepcopy(CLEAN), CLEAN_STRC)
    check("weekend not missing",
          "missing_session" not in kinds(found), found)


def test_dividend_double():
    """One STRC amount doubled (the Tiingo pattern: 1.0 vs 0.5 on both
    sides) — flagged as a dividend double."""
    s = copy.deepcopy(CLEAN_STRC)
    s[1] = ["2026-02-15", "2026-02-13", "2026-02-28", 1.0]
    found = run_all(copy.deepcopy(CLEAN), s)
    dbl = [a for a in found if a["kind"] == "dividend_double"]
    check("dividend double found", len(dbl) == 1, found)
    check("double date", dbl and dbl[0]["date"] == "2026-02-13", dbl)


def test_dividend_regimes_clean():
    """The transitional half-period (0.25) and the daily 0.0333 amounts
    are regime changes, not doubles — the clean ledger reports none."""
    found = anomaly.check_dividends(copy.deepcopy(CLEAN_STRC))
    check("regime changes not flagged", found == [], found)


def test_dividend_duplicate_ex():
    s = copy.deepcopy(CLEAN_STRC)
    s.append(["2026-11-04", "2026-11-03", "2026-11-05", 0.0333333333])
    found = run_all(copy.deepcopy(CLEAN), s)
    dup = [a for a in found if a["kind"] == "duplicate_ex_date"]
    check("duplicate ex-date found", len(dup) == 1, found)


def test_stale_symbol():
    """TSLA missing from the last two sessions — flagged stale."""
    c = copy.deepcopy(CLEAN)
    del c["2026-01-08"]["TSLA"]
    del c["2026-01-09"]["TSLA"]
    found = run_all(c, CLEAN_STRC)
    stale = [a for a in found if a["kind"] == "stale_symbol"]
    check("stale symbol found", len(stale) == 1, found)
    check("stale last close",
          stale and stale[0]["date"] == "2026-01-07", stale)


def test_stale_quote_market_hours():
    """A live quote 120 minutes old during market hours is stale; the
    same quote after the close is not (it is the close)."""
    prices = {"stocks": {"TSLA": {"c": 420.0, "pc": 416.0,
                                  "t": 1767960000}}}  # 2026-01-09 12:00 UTC
    # 14:00 UTC = 09:00 ET — before the open, not market hours
    f1 = run_all(copy.deepcopy(CLEAN), CLEAN_STRC, prices,
                 "2026-01-09T14:00:00Z")
    check("before open not stale",
          "stale_quote" not in kinds(f1), f1)
    # 15:00 UTC = 10:00 ET, market hours, quote 180 min old
    f2 = run_all(copy.deepcopy(CLEAN), CLEAN_STRC, prices,
                 "2026-01-09T15:00:00Z")
    sq = [a for a in f2 if a["kind"] == "stale_quote"]
    check("market-hours stale quote found", len(sq) == 1, f2)
    # 21:00 UTC = 16:00 ET, the close — the same quote is the close
    f3 = run_all(copy.deepcopy(CLEAN), CLEAN_STRC, prices,
                 "2026-01-09T21:00:00Z")
    check("after close not stale",
          "stale_quote" not in kinds(f3), f3)


def test_cli_end_to_end():
    """CLI on a planted history writes the JSON report and exits 0."""
    c = copy.deepcopy(CLEAN)
    c["2026-01-07"]["BTC"] = 150000.0
    c["2026-01-08"]["BTC"] = 104000.0
    with tempfile.TemporaryDirectory() as td:
        hp = os.path.join(td, "history.json")
        op = os.path.join(td, "report.json")
        with open(hp, "w") as f:
            json.dump({"v": 1, "closes": c}, f)
        r = subprocess.run(
            [sys.executable, "tools/anomaly.py", "--history", hp,
             "--out", op],
            capture_output=True, text=True, cwd="/tmp/ps-py-s4")
        check("cli exit 0", r.returncode == 0, r.stderr[-300:])
        rep = json.load(open(op))
        check("cli report counts 1", rep["anomalies"] == 1, rep)
        check("cli report kind", rep["by_kind"] == {"jump": 1}, rep)
        check("cli stdout names it", "BTC" in r.stdout and "jump" in r.stdout
              or "150000" in r.stdout, r.stdout)
        # malformed history -> exit 1
        bad = os.path.join(td, "bad.json")
        with open(bad, "w") as f:
            f.write("{not json")
        r2 = subprocess.run(
            [sys.executable, "tools/anomaly.py", "--history", bad],
            capture_output=True, text=True, cwd="/tmp/ps-py-s4")
        check("cli malformed exit 1", r2.returncode == 1)


if __name__ == "__main__":
    test_clean()
    test_split()
    test_absurd_jump()
    test_reverse_split()
    test_missing_session()
    test_weekend_not_missing()
    test_dividend_double()
    test_dividend_regimes_clean()
    test_dividend_duplicate_ex()
    test_stale_symbol()
    test_stale_quote_market_hours()
    test_cli_end_to_end()
    print("anomaly: %d passed, %d failed" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)
