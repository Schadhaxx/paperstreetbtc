#!/usr/bin/env python3
"""Tests for tools/backtest.py (Python supercharge, slice 4).

No network. Run with: python3 tests/test_backtest.py (exit 0 = all pass).

The engine is verified against book.js by hand computation on a tiny
synthetic history where every number is worked out in the test: initial
units at the base close, STRC cash receivable from the ex-date until the
pay session, the dividend buy at the pay session's price, and the value
at each session. The real-data cross-check (Berkshire $89,923.35,
-10.08% YTD — identical to slice 3's verified stats) is documented in
the review note; it is run by hand because history.json lives on the
data branch, not in this repo.
"""

import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import backtest  # noqa: E402

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


def approx(a, b, tol=0.01):
    return abs(a - b) <= tol


# --- synthetic history: 5 sessions, BTC + STRC, one STRC dividend ------
# base 2025-12-31: BTC 100000, STRC 100. Sleeve {BTC: .5, STRC: .5},
# div {BTC: 1}, start $100,000. Init: BTC 0.5 units, STRC 500 units.
# Dividend: ex 2026-01-05, pay 2026-01-06, $1/share -> cash $500,
# receivable 2026-01-05..2026-01-06, buys BTC at the 2026-01-06 close.
SYNTH_CLOSES = {
    "2025-12-31": {"BTC": 100000.0, "STRC": 100.0},
    "2026-01-02": {"BTC": 110000.0, "STRC": 100.0},
    "2026-01-05": {"BTC": 120000.0, "STRC": 100.0},
    "2026-01-06": {"BTC": 100000.0, "STRC": 100.0},
    "2026-01-07": {"BTC": 100000.0, "STRC": 100.0},
}
SYNTH_OPENS = {
    "2025-12-31": {"BTC": 100000.0, "STRC": 100.0},
    "2026-01-02": {"BTC": 105000.0, "STRC": 100.0},
    "2026-01-05": {"BTC": 115000.0, "STRC": 100.0},
    "2026-01-06": {"BTC": 100000.0, "STRC": 100.0},
    "2026-01-07": {"BTC": 100000.0, "STRC": 100.0},
}
SYNTH_LEDGER = """
window.PSLEDGER = {
  base: '2025-12-31', start: 100000,
  sleeves: {
    test: { w: { BTC: .5, STRC: .5 }, div: { BTC: 1 } },
  },
  rebalances: [],
  strc: [
    ['2026-01-04', '2026-01-05', '2026-01-06', 1.0],
  ],
};
"""
BASE = "2025-12-31"
DATES = sorted(SYNTH_CLOSES)


def synth_engine(vehicle=None, price_mode="close"):
    base, start, sleeves, strc = backtest.parse_ledger(SYNTH_LEDGER)
    veh_map = None
    if vehicle:
        # IBIT closes: base 50, then 55, 60, 55, 55 (diverges from spot)
        veh_map = {"2025-12-31": 50.0, "2026-01-02": 55.0,
                   "2026-01-05": 60.0, "2026-01-06": 55.0,
                   "2026-01-07": 55.0}

    def price_at(a, d):
        if vehicle and a == "BTC":
            return veh_map[d]
        return SYNTH_CLOSES[d][a]

    def buy_price(a, d):
        if price_mode == "close":
            return price_at(a, d)
        if vehicle and a == "BTC":
            return veh_map[d]
        return SYNTH_OPENS[d][a]

    return backtest.Engine(DATES, SYNTH_CLOSES, base, start, sleeves,
                           strc, price_at, buy_price)


def test_baseline_reproduces_book():
    """No contributions, Spot: the NAV series is hand-computed from
    book.js's rules."""
    eng = synth_engine()
    series, summary = eng.run("test", [])
    # 2026-01-02: BTC 0.5 x 110000 + STRC 500 x 100 = 55000 + 50000
    check("baseline 2026-01-02", approx(series["2026-01-02"], 105000),
          series["2026-01-02"])
    # 2026-01-05: BTC 0.5 x 120000 + STRC 500 x 100 + receivable $500
    check("baseline 2026-01-05 (receivable)", approx(series["2026-01-05"], 110500),
          series["2026-01-05"])
    # 2026-01-06: dividend buys $500 / 100000 = 0.005 BTC; BTC 0.505 x
    # 100000 + STRC 500 x 100 = 50500 + 50000; no receivable (paid)
    check("baseline 2026-01-06 (paid)", approx(series["2026-01-06"], 100500),
          series["2026-01-06"])
    # 2026-01-07: same holdings, same prices
    check("baseline 2026-01-07", approx(series["2026-01-07"], 100500),
          series["2026-01-07"])
    check("baseline contributed 0", summary["contributed"] == 0)
    check("baseline nothing skipped", summary["skipped"] == [])


def test_vehicle_rebases():
    """IBIT: initial BTC units are re-based (50000/50 = 1000), the
    dividend buys at the vehicle close, and the value tracks the vehicle."""
    eng = synth_engine(vehicle="IBIT")
    series, _ = eng.run("test", [])
    # 2026-01-07: BTC units 1000 + 500/55 = 1009.0909, x 55 = 55500;
    # STRC 500 x 100 = 50000. Total 105500.
    check("vehicle 2026-01-07", approx(series["2026-01-07"], 105500),
          series["2026-01-07"])
    # At the base the value is still exactly $100,000 (re-basing
    # preserves the start — the book.js rule).
    check("vehicle base is $100k", approx(series["2025-12-31"], 100000),
          series["2025-12-31"])


def test_contribution_open_vs_close():
    """A $10,000 contribution on 2026-01-02: open buys BTC at 105000,
    close buys at 110000 — the open rule buys more BTC, so the final
    value is higher when the price later falls back to 100000."""
    contrib = [{"date": "2026-01-02", "amount": 10000}]
    eng_o = synth_engine(price_mode="open")
    series_o, s_o = eng_o.run("test", contrib)
    eng_c = synth_engine(price_mode="close")
    series_c, s_c = eng_c.run("test", contrib)
    # open: BTC 5000/105000 = 0.047619, STRC 50. The contribution's
    # STRC earns the dividend too, so cash is (500+50) x $1 = $550,
    # buying 0.0055 BTC. Final: BTC (0.5+0.047619+0.0055) x 100000 +
    # STRC 550 x 100 = 55311.90 + 55000
    check("open final", approx(series_o["2026-01-07"], 110311.90, 0.05),
          series_o["2026-01-07"])
    # close: BTC 5000/110000 = 0.045455. Final: (0.5+0.045455+0.0055)
    # x 100000 + 55000 = 55095.45 + 55000
    check("close final", approx(series_c["2026-01-07"], 110095.45, 0.05),
          series_c["2026-01-07"])
    check("open beats close here", series_o["2026-01-07"] > series_c["2026-01-07"])
    check("open bought one", len(s_o["bought"]) == 1)
    check("open buy session", s_o["bought"][0]["buy_session"] == "2026-01-02")


def test_contribution_weekend_held():
    """A contribution dated Saturday 2026-01-03 (CR-005) is held to the
    next session, Monday 2026-01-05, and buys at that session's open."""
    contrib = [{"date": "2026-01-03", "amount": 10000}]
    eng = synth_engine(price_mode="open")
    _s, summary = eng.run("test", contrib)
    check("weekend held to Monday",
          summary["bought"][0]["buy_session"] == "2026-01-05",
          summary["bought"])
    check("weekend target kept",
          summary["bought"][0]["target_date"] == "2026-01-03")


def test_contribution_skips():
    """Before the base and after the last close are skipped, and listed."""
    contrib = [{"date": "2025-12-30", "amount": 1000},
               {"date": "2026-01-08", "amount": 1000}]
    eng = synth_engine()
    _s, summary = eng.run("test", contrib)
    check("two skipped", len(summary["skipped"]) == 2)
    check("skipped reasons",
          {x["reason"] for x in summary["skipped"]}
          == {"on or before base", "after last close"},
          summary["skipped"])
    check("skipped contributes 0", summary["contributed"] == 0)


def test_contribution_raises_future_dividends():
    """A contribution that buys STRC before an ex-date earns that
    dividend: $10,000 on 2026-01-02 buys 50 STRC, so the 2026-01-05
    dividend cash is (500 + 50) x $1 = $550, not $500."""
    contrib = [{"date": "2026-01-02", "amount": 10000}]
    eng = synth_engine(price_mode="close")
    series, _ = eng.run("test", contrib)
    # 2026-01-05: BTC (0.5+0.045455) x 120000 + STRC 550 x 100 +
    # receivable $550 = 65454.55 + 55000 + 550
    check("contribution earns dividend",
          approx(series["2026-01-05"], 121004.55, 0.05),
          series["2026-01-05"])


def test_vehicle_open_uses_close():
    """In ETF mode an open-priced contribution buys the BTC leg at the
    vehicle CLOSE (no vehicle opens exist) — the item-3 treatment."""
    contrib = [{"date": "2026-01-02", "amount": 10000}]
    eng = synth_engine(vehicle="IBIT", price_mode="open")
    series, _ = eng.run("test", contrib)
    # BTC leg: 5000 / 55 (vehicle close) = 90.9091 units; STRC leg:
    # 5000 / 100 (open) = 50. The dividend cash is (500+50) x $1 =
    # $550, buying 550/55 = 10 vehicle units. Final 2026-01-07: BTC
    # (1000 + 90.9091 + 10) x 55 + STRC 550 x 100 = 60550 + 55000
    check("vehicle open uses close", approx(series["2026-01-07"], 115550.0, 0.05),
          series["2026-01-07"])


def test_dca_schedules():
    """Monthly and weekly schedule generation."""
    m = backtest.dca_dates("monthly:500:1:2026-01-01:2026-03-31")
    check("monthly dates", m == ["2026-01-01", "2026-02-01", "2026-03-01"], m)
    w = backtest.dca_dates("weekly:100:0:2026-01-01:2026-01-31")
    check("weekly Mondays",
          w == ["2026-01-05", "2026-01-12", "2026-01-19", "2026-01-26"], w)
    try:
        backtest.parse_dca("daily:500:1:2026-01-01:2026-03-31")
        check("bad freq rejected", False)
    except ValueError:
        check("bad freq rejected", True)
    try:
        backtest.parse_dca("monthly:500:31:2026-01-01:2026-03-31")
        check("day 31 rejected", False)
    except ValueError:
        check("day 31 rejected", True)


def test_vehicle_map_rules():
    """The vehicle map fills a 1-session lag with the prior close and
    rejects a 2-session lag (the book.js staleness rule)."""
    rows = [["2025-12-31", 50.0], ["2026-01-02", 55.0],
            ["2026-01-05", 60.0], ["2026-01-06", 55.0]]
    # last session 2026-01-07 is 1 behind the vehicle end 2026-01-06
    m = backtest.build_vehicle_map(DATES, rows, BASE)
    check("1-session lag fills", m["2026-01-07"] == 55.0, m)
    rows2 = [["2025-12-31", 50.0], ["2026-01-02", 55.0],
             ["2026-01-05", 60.0]]
    try:
        backtest.build_vehicle_map(DATES, rows2, BASE)
        check("2-session lag rejected", False)
    except ValueError:
        check("2-session lag rejected", True)


def test_cli_compare():
    """End-to-end CLI: --compare on a synthetic history file produces a
    baseline and three scenarios with non-zero differences."""
    with tempfile.TemporaryDirectory() as td:
        hist = {"v": 1, "closes": SYNTH_CLOSES}
        hp = os.path.join(td, "history.json")
        lp = os.path.join(td, "ledger.js")
        op = os.path.join(td, "opens.json")
        vp = os.path.join(td, "vehicle.json")
        with open(hp, "w") as f:
            json.dump(hist, f)
        with open(lp, "w") as f:
            f.write(SYNTH_LEDGER)
        with open(op, "w") as f:
            json.dump({"o": SYNTH_OPENS}, f)
        with open(vp, "w") as f:
            json.dump({"vehicles": {"IBIT": [
                ["2025-12-31", 50.0], ["2026-01-02", 55.0],
                ["2026-01-05", 60.0], ["2026-01-06", 55.0],
                ["2026-01-07", 55.0]],
                "FBTC": [
                ["2025-12-31", 50.0], ["2026-01-02", 55.0],
                ["2026-01-05", 60.0], ["2026-01-06", 55.0],
                ["2026-01-07", 55.0]]}}, f)
        outp = os.path.join(td, "out.json")
        r = subprocess.run(
            [sys.executable, "tools/backtest.py",
             "--history", hp, "--ledger", lp, "--opens", op,
             "--vehicle-daily", vp, "--sleeve", "test",
             "--dca", "monthly:1000:1:2026-01-01:2026-01-07",
             "--compare", "--out", outp],
            capture_output=True, text=True, cwd="/tmp/ps-py-s4")
        check("cli compare exit 0", r.returncode == 0, r.stderr[-300:])
        res = json.load(open(outp))
        check("cli has three scenarios",
              set(res["scenarios"]) == {"close_not_open", "ibit_not_spot",
                                        "weekly_not_monthly"},
              res.get("scenarios", {}).keys())
        for name, sc in res["scenarios"].items():
            d = sc["test"]["diff_vs_baseline"]
            check("scenario %s non-zero" % name, d != 0, d)
        check("baseline final matches hand calc",
              abs(res["results"]["test"]["final"] - 101481.19) < 0.05,
              res["results"]["test"]["final"])
        # CLI errors: unknown sleeve, missing vehicle file
        r2 = subprocess.run(
            [sys.executable, "tools/backtest.py", "--history", hp,
             "--ledger", lp, "--sleeve", "nope"],
            capture_output=True, text=True, cwd="/tmp/ps-py-s4")
        check("cli unknown sleeve exit 1", r2.returncode == 1)
        r3 = subprocess.run(
            [sys.executable, "tools/backtest.py", "--history", hp,
             "--ledger", lp, "--vehicle", "IBIT"],
            capture_output=True, text=True, cwd="/tmp/ps-py-s4")
        check("cli IBIT without file exit 1", r3.returncode == 1)


if __name__ == "__main__":
    test_baseline_reproduces_book()
    test_vehicle_rebases()
    test_contribution_open_vs_close()
    test_contribution_weekend_held()
    test_contribution_skips()
    test_contribution_raises_future_dividends()
    test_vehicle_open_uses_close()
    test_dca_schedules()
    test_vehicle_map_rules()
    test_cli_compare()
    print("backtest: %d passed, %d failed" % (PASS, FAIL))
    sys.exit(1 if FAIL else 0)
