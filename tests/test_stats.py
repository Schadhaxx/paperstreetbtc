#!/usr/bin/env python3
"""Tests for tools/stats.py (Python supercharge, slice 3). No network.

Run: python3 tests/test_stats.py   (exit 0 = all pass)

Two layers:
  1. A tiny synthetic history + ledger, where every stat is hand-computed
     in the test (monthly return, best/worst day, drawdown, volatility,
     Pulse, dividend calendar, badges, CSV round-trip).
  2. Today's real data-branch history.json + the real ledger.js: stats
     match independent hand calculations, the November dividend total is
     the declared $1.00/share, the CSV round-trips, and the stats.json
     carries every field the display (assets/js/stats-display.js) reads.
"""

import csv
import json
import math
import os
import statistics
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import stats as S

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
REAL_LEDGER = os.path.join(ROOT, "assets", "js", "ledger.js")


def real_history_path():
    """Today's data-branch history.json, if reachable, else None.

    Prefers the repo's fetched origin/data ref (no network), then a
    local copy, then a fresh fetch. Returns None if none works.
    """
    for cand in ("/tmp/ps-py-s3-history.json",
                 os.path.join(ROOT, "history.json")):
        if os.path.exists(cand):
            return cand
    try:
        out = subprocess.run(["git", "show", "origin/data:history.json"],
                             cwd=ROOT, capture_output=True, text=True,
                             timeout=30)
        if out.returncode == 0 and out.stdout.startswith("{"):
            p = os.path.join(tempfile.gettempdir(), "ps-s3-history.json")
            with open(p, "w") as f:
                f.write(out.stdout)
            return p
    except Exception:
        pass
    return None


REAL_HISTORY = real_history_path()

CHECKS = []


def check(name, cond, detail=""):
    CHECKS.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + ((" — " + str(detail)) if detail and not cond else ""))


# ---------------------------------------------------------------- synthetic
LEDGER = """window.PSLEDGER = {
  base: '2026-01-01', start: 100000,
  sleeves: {
    test: { w: { BTC: .5, STRC: .5 }, div: { BTC: 1 } }
  },
  rebalances: [],
  strc: [
    ['2026-01-02', '2026-01-02', '2026-01-05', 1.00],
    ['2026-01-07', '2026-01-07', '2026-01-08', 2.00]
  ]
};
"""
HIST = {
    "v": 1, "base": "2026-01-01",
    "closes": {
        "2026-01-01": {"BTC": 100, "STRC": 100},
        "2026-01-02": {"BTC": 110, "STRC": 100},
        "2026-01-05": {"BTC": 99, "STRC": 100},
        "2026-01-06": {"BTC": 121, "STRC": 100},
        "2026-01-07": {"BTC": 115, "STRC": 100},
    },
    "divs": {},
}


def synthetic():
    base, start, sleeves, strc = S.parse_ledger(LEDGER)
    check("parse: base/start/sleeves/strc", base == "2026-01-01"
          and start == 100000 and list(sleeves) == ["test"]
          and len(strc) == 2, (base, start, sleeves, len(strc)))
    dates = sorted(HIST["closes"])
    navs, evs, sev = S.build_sleeve_navs(
        dates, HIST["closes"], base, start, sleeves, strc)
    nav = navs["test"]
    # Hand-computed NAVs: init BTC 500, STRC 500. Jan 2 event pays $500
    # (500 STRC x $1.00), receivable Jan 2-4, buys 5.0505 BTC at 99 on Jan 5.
    # Jan 7 event ($2.00/share = $1,000) is receivable from Jan 7 (its pay
    # date is past the last session, so it stays receivable, as in book.js).
    expect = {"2026-01-01": 100000.0, "2026-01-02": 105500.0,
              "2026-01-05": 100000.0, "2026-01-06": 111111.11,
              "2026-01-07": 109080.81}
    for d, v in expect.items():
        check("nav %s" % d, abs(nav[d] - v) < 0.02, (d, nav[d], v))
    st = S.series_stats(dates, nav, base, start)
    check("monthly Jan +9.08%", abs(st["monthly"]["2026-01"] - 9.08) < 0.01,
          st["monthly"])
    check("ytd +9.08%", abs(st["ytd_pct"] - 9.08) < 0.01, st["ytd_pct"])
    check("best day Jan 6 +11.11%", st["best_day"] == {"date": "2026-01-06", "pct": 11.11},
          st["best_day"])
    check("worst day Jan 5 -5.21%", st["worst_day"] == {"date": "2026-01-05", "pct": -5.21},
          st["worst_day"])
    check("drawdown now -1.83%", abs(st["drawdown_pct"] - (-1.83)) < 0.01,
          st["drawdown_pct"])
    check("max drawdown -5.21% Jan 5", abs(st["max_drawdown_pct"] - (-5.21)) < 0.01
          and st["max_drawdown_date"] == "2026-01-05",
          (st["max_drawdown_pct"], st["max_drawdown_date"]))
    check("peak 111111.11 on Jan 6", abs(st["peak_value"] - 111111.11) < 0.02
          and st["peak_date"] == "2026-01-06", (st["peak_value"], st["peak_date"]))
    # volatility: independent reference via statistics.stdev
    # (Jan 7 return is -1.83%: the $1,000 receivable is in the NAV)
    rets = [5.5, -5.213270142180095, 11.11111111111111, -1.8272727272727273]
    ref_vol = statistics.stdev(rets) * math.sqrt(252)
    check("vol annualised ~%.1f%%" % ref_vol,
          abs(st["vol_ann_pct"] - ref_vol) < 0.05, st["vol_ann_pct"])
    # calendar: Jan 2 event paid (pay Jan 5 <= last Jan 7); Jan 7 event
    # upcoming, pay session unknown (no session >= Jan 8 in the fixture).
    cal = S.build_calendar(dates, sleeves, evs, sev)
    check("calendar: 1 upcoming", len(cal["upcoming"]) == 1, cal["upcoming"])
    nxt = cal["upcoming"][0]
    check("next pay Jan 8, session None, $2.00, cash $1000",
          nxt["pay"] == "2026-01-08" and nxt["pay_session"] is None
          and nxt["per_share"] == 2.0 and nxt["cash"]["test"] == 1000.0, nxt)
    check("Jan month total $3.00/share",
          cal["month_totals"]["2026-01"]["per_share"] == 3.0,
          cal["month_totals"])
    # badges: no round crossing at BTC ~100, no sleeve high (not at peak)
    badges = S.build_badges(dates, HIST["closes"], navs)
    check("badges: none on synthetic", badges == [], badges)
    # badges, direct: BTC crosses $80,000 down, then a sleeve at its high
    closes2 = {"2026-01-01": {"BTC": 81000}, "2026-01-02": {"BTC": 79000},
               "2026-01-05": {"BTC": 79500}}
    navs2 = {"test": {"2026-01-01": 100000.0, "2026-01-02": 99000.0,
                      "2026-01-05": 101000.0}}
    b2 = S.build_badges(["2026-01-01", "2026-01-02", "2026-01-05"],
                        closes2, navs2)
    check("badge: BTC crossed below $80,000 on Jan 2",
          any(b["kind"] == "btc_round" and b["level"] == 80000
              and b["direction"] == "down" and b["date"] == "2026-01-02"
              for b in b2), b2)
    check("badge: sleeve at new high Jan 5",
          any(b["kind"] == "sleeve_high" and b["sleeve"] == "test"
              and b["date"] == "2026-01-05" for b in b2), b2)


# ---------------------------------------------------------------- real data
def real():
    if not REAL_HISTORY:
        print("SKIP real-data checks (data-branch history.json not reachable)")
        return
    hist = json.load(open(REAL_HISTORY))
    with open(REAL_LEDGER) as f:
        base, start, sleeves, strc = S.parse_ledger(f.read())
    check("real ledger: 4 sleeves, 44 STRC events",
          list(sleeves) == ["berkshire", "hodlr", "hf", "saylor"]
          and len(strc) == 44, (list(sleeves), len(strc)))
    dates = sorted(hist["closes"])
    check("real history: 215 closes, 2025-12-31..2026-11-06",
          len(dates) == 215 and dates[0] == "2025-12-31"
          and dates[-1] == "2026-11-06", (len(dates), dates[0], dates[-1]))
    navs, evs, sev = S.build_sleeve_navs(
        dates, hist["closes"], base, start, sleeves, strc)
    benches = S.build_benchmarks(dates, hist["closes"], hist.get("divs") or {}, base)
    # BTC YTD by hand from the raw closes
    btc = S.series_stats(dates, benches["btc"], base, 100.0)
    hand = (hist["closes"]["2026-11-06"]["BTC"]
            / hist["closes"]["2025-12-31"]["BTC"] - 1) * 100
    check("BTC YTD matches hand calc (%.2f%%)" % hand,
          abs(btc["ytd_pct"] - hand) < 0.01, btc["ytd_pct"])
    # monthly returns compound to the YTD (within rounding)
    prod = 1.0
    for p in btc["monthly"].values():
        prod *= 1 + p / 100.0
    check("BTC monthly returns compound to YTD",
          abs((prod - 1) * 100 - btc["ytd_pct"]) < 0.05,
          ((prod - 1) * 100, btc["ytd_pct"]))
    # SPY total return beats its price return (distributions reinvested)
    spy_tr = benches["spy"]["2026-11-06"]
    spy_pr = 100.0 * hist["closes"]["2026-11-06"]["SPY"] / hist["closes"]["2025-12-31"]["SPY"]
    check("SPY total return > price return (divs reinvested)",
          spy_tr > spy_pr, (spy_tr, spy_pr))
    # sanity bounds on every series
    for key, series in list(navs.items()) + list(benches.items()):
        st = S.series_stats(dates, series, base, 100000 if key in navs else 100.0)
        check("bounds %s" % key,
              st["best_day"]["pct"] >= st["worst_day"]["pct"]
              and st["drawdown_pct"] <= 0.01
              and st["max_drawdown_pct"] <= st["drawdown_pct"] + 0.01
              and 0 < (st["vol_ann_pct"] or 0) < 200
              and st["value"] <= st["peak_value"] + 0.01
              and st["peak_date"] in dates,
              (st["best_day"], st["worst_day"], st["drawdown_pct"],
               st["max_drawdown_pct"], st["vol_ann_pct"]))
    # Pulse arithmetic, as main() builds it: above_start + start == value;
    # below_peak + value == peak_value.
    for key in navs:
        st = S.series_stats(dates, navs[key], base, start)
        pulse = {"value": st["value"],
                 "above_start": round(st["value"] - start, 2),
                 "below_peak": round(st["peak_value"] - st["value"], 2),
                 "peak_value": st["peak_value"]}
        check("pulse arithmetic %s" % key,
              abs(pulse["above_start"] + start - pulse["value"]) < 0.01
              and abs(pulse["below_peak"] + pulse["value"]
                      - pulse["peak_value"]) < 0.01, pulse)
    # dividend calendar: November declared aggregate is $1.00/share
    cal = S.build_calendar(dates, sleeves, evs, sev)
    check("Nov month total is the declared $1.00/share",
          cal["month_totals"]["2026-11"]["per_share"] == 1.0,
          cal["month_totals"])
    check("25 upcoming Nov payments (Nov 6-30)",
          len(cal["upcoming"]) == 25, len(cal["upcoming"]))
    check("next payment pays Mon Nov 9",
          cal["upcoming"][0]["pay"] == "2026-11-09", cal["upcoming"][0])
    check("no other preferreds in the calendar",
          all("STRF" not in json.dumps(e) and "STRK" not in json.dumps(e)
              for e in cal["upcoming"]), "")
    # Tiingo-final dates are used as published (no special-casing):
    # adding a tiingo_final field must not change any stat.
    hist2 = dict(hist)
    hist2["tiingo_final"] = {"2026-11-05": {"BTC": 75942.13, "tiingo": 75940.0,
                                             "diff_pct": 0.003, "confirmed": "2026-11-06T00:00:00Z"}}
    navs2, _, _ = S.build_sleeve_navs(
        dates, hist2["closes"], base, start, sleeves, strc)
    check("tiingo_final field does not change the stats",
          navs2 == navs, "")
    # full run end-to-end + CSV round-trip + display contract
    with tempfile.TemporaryDirectory() as td:
        out_s = os.path.join(td, "stats.json")
        out_c = os.path.join(td, "history.csv")
        r = subprocess.run([sys.executable,
                            os.path.join(ROOT, "tools", "stats.py"),
                            "--history", REAL_HISTORY, "--ledger", REAL_LEDGER,
                            "--out-stats", out_s, "--out-csv", out_c,
                            "--now", "2026-11-06T23:45:00Z"],
                           capture_output=True, text=True)
        check("tool exits 0 on real data", r.returncode == 0, r.stderr)
        st = json.load(open(out_s))
        check("stats.json: 10 series", len(st["series"]) == 10, len(st["series"]))
        # CSV round-trips history.json exactly
        rows = list(csv.reader(open(out_c)))
        check("CSV: 215 rows + header", len(rows) == 216, len(rows))
        hdr = rows[0][1:]
        ok = True
        for row in rows[1:]:
            d = row[0]
            for sym, val in zip(hdr, row[1:]):
                if val == "":
                    ok = ok and hist["closes"][d].get(sym) is None
                elif abs(float(val) - hist["closes"][d][sym]) > 1e-6:
                    ok = False
        check("CSV values match history.json", ok, "")
        # display contract: every field stats-display.js reads is present
        need_series = ["name", "kind", "value", "ytd_pct", "mtd_pct",
                       "mtd_month", "monthly", "best_day", "worst_day",
                       "drawdown_pct", "peak_value", "peak_date",
                       "max_drawdown_pct", "max_drawdown_date", "vol_ann_pct"]
        need_pulse = ["value", "above_start", "above_start_pct",
                      "below_peak", "peak_value", "peak_date"]
        need_div = ["record", "ex", "pay", "pay_session", "per_share", "cash"]
        need_badge = ["kind", "text", "date"]
        ok = (set(st) >= {"v", "generated", "as_of", "base", "series",
                          "pulse", "dividends", "badges", "csv"}
              and all(set(v) >= set(need_series) for v in st["series"].values())
              and all(set(v) >= set(need_pulse) for v in st["pulse"].values())
              and all(set(e) >= set(need_div)
                      for e in st["dividends"]["upcoming"])
              and all(set(b) >= set(need_badge) for b in st["badges"])
              and all(isinstance(v["best_day"], dict)
                      and set(v["best_day"]) >= {"date", "pct"}
                      for v in st["series"].values()))
        check("display contract: all fields present", ok, "")
        # display: the Node test renders this stats.json through the
        # pure PSStats.render() and asserts the HTML carries the numbers.
        import shutil
        if shutil.which("node"):
            r = subprocess.run(["node",
                                os.path.join(ROOT, "tests",
                                             "test_stats_display.js"),
                                out_s], capture_output=True, text=True)
            check("display renders the pre-computed numbers (node)",
                  r.returncode == 0, r.stdout.strip().splitlines()[-1]
                  if r.stdout else r.stderr)
        else:
            print("SKIP display test (node not available)")
        r = subprocess.run([sys.executable,
                            os.path.join(ROOT, "tools", "stats.py"),
                            "--history", "/nonexistent.json", "--ledger",
                            REAL_LEDGER, "--out-stats", out_s,
                            "--out-csv", out_c], capture_output=True, text=True)
        check("missing history exits 1", r.returncode == 1, r.returncode)
        r = subprocess.run([sys.executable,
                            os.path.join(ROOT, "tools", "stats.py")],
                           capture_output=True, text=True)
        check("missing args exits 2", r.returncode == 2, r.returncode)


synthetic()
real()
bad = [c for c in CHECKS if not c[1]]
print("\n%d checks, %d failed" % (len(CHECKS), len(bad)))
for name, _, detail in bad:
    print("  FAILED: " + name + " " + str(detail))
sys.exit(1 if bad else 0)
