"""Tests for TA Stage 3 fix 2 (rule A, plus B/C numbers).

Rule A is checked via sloped_line_valid from the job
(tools/ta_lines.py, same signature as the review reference
ref_sloped_valid.py). Fixture fixtures/sloped_cases.json sits next to
this file: live [t_ms, close] bars plus the cases from the Nov 20
21:00 ET recheck (1h window ending 2026-11-21T02:00:00Z).

Run:
  python3 tests/test_ta_lines_fix2.py
  python3 -m pytest tests/test_ta_lines_fix2.py -q
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
from ta_lines import (  # noqa: E402
    CONSEC_LIMIT,
    RECENT_BARS,
    TOTAL_CAP,
    WRONG_TOL_ATR,
    sloped_line_valid,
)

FIX = json.loads((HERE / "fixtures" / "sloped_cases.json").read_text())

# Rule B / C numbers (spec). test_replay enforces FLICKER_STEPS_LIMIT
# as the hard gate; the comparative filter enforces
# COMPARATIVE_HYST_SEP_ATR as the incumbent separation. Asserted here
# so the values are not implicit.
FLICKER_STEPS_LIMIT = 0
COMPARATIVE_MIN_SEP_ATR = 1.0
COMPARATIVE_HYST_SEP_ATR = 1.15


def _eval(case):
    line = FIX["lines"][case["line_id"]]
    bars = FIX["bars"][case["tf"]]
    native = sloped_line_valid(
        line, bars, case["atr"], case["lastClose"], kind=line["kind"])
    opposite = "resistance" if line["kind"] == "support" else "support"
    flipped = sloped_line_valid(
        line, bars, case["atr"], case["lastClose"], kind=opposite)
    return native, flipped


def test_live_cases():
    for case in FIX["cases"]:
        native, flipped = _eval(case)
        assert native is case["expect_valid"], (
            case["id"], native, case["reason"])
        assert flipped is case["expect_valid_as_opposite"], (
            case["id"], "opposite", flipped, case["reason"])


def test_1h_support_58676_dropped_not_flipped():
    case = next(c for c in FIX["cases"] if c["id"] == "1h_support_58676.58")
    native, flipped = _eval(case)
    assert native is False
    assert flipped is False
    # last close is only 0.181 ATR below the line — inside the 0.5 ATR
    # wrong-side tolerance and the current 0.25 ATR flip buffer, but
    # still a support labeled above the last close.
    assert case["lastClose"] < FIX["lines"][case["line_id"]]["priceNow"]
    assert (FIX["lines"][case["line_id"]]["priceNow"] - case["lastClose"]
            ) / case["atr"] < WRONG_TOL_ATR


def test_1h_support_58676_also_above_earlier_close():
    case = next(c for c in FIX["cases"]
                if c["id"] == "1h_support_58676.58_lastClose_58633.62")
    native, flipped = _eval(case)
    assert native is False and flipped is False
    assert case["lastClose"] == 58633.62


def test_1d_supports_rejected():
    for cid in ("1d_support_57784.98", "1d_support_54908.49"):
        case = next(c for c in FIX["cases"] if c["id"] == cid)
        native, flipped = _eval(case)
        assert native is False and flipped is False, cid


def test_good_1h_and_4h_supports_kept():
    for cid in ("1h_support_57287.97", "1h_support_57707.25",
                "4h_support_56545.96"):
        case = next(c for c in FIX["cases"] if c["id"] == cid)
        native, flipped = _eval(case)
        assert native is True and flipped is False, cid


def test_4h_flipped_resistance_dropped():
    case = next(c for c in FIX["cases"] if c["id"] == "4h_resistance_60177.21")
    native, flipped = _eval(case)
    assert native is False and flipped is False
    assert case["counts"]["recent6"] >= 1
    assert case["counts"]["max_consec"] >= CONSEC_LIMIT


def _synth(closes, slope=0.0, p0=100.0, atr=10.0, kind="support"):
    bars = [[i * 3_600_000, c] for i, c in enumerate(closes)]
    line = {"kind": kind, "slope": slope,
            "anchor": {"t": bars[0][0], "price": p0}}
    return sloped_line_valid(line, bars, atr, last_close=closes[-1], kind=kind)


def test_rule_a_last_close_no_tolerance():
    ok = [100.0] * 20
    assert _synth(ok) is True
    below = list(ok)
    below[-1] = 99.99  # 0.001 ATR under a support — still reject
    assert _synth(below) is False
    res = [100.0] * 20
    assert _synth(res, kind="resistance") is True
    res[-1] = 100.01
    assert _synth(res, kind="resistance") is False


def test_rule_a_three_consecutive_rejects_two_do_not():
    closes = [100.0] * 30
    two = list(closes)
    two[8:10] = [94.0, 94.0]  # 0.6 ATR below, not in last 6
    assert _synth(two) is True
    three = list(closes)
    three[8:11] = [94.0, 94.0, 94.0]
    assert _synth(three) is False


def test_rule_a_any_recent_wrong_side_rejects():
    closes = [100.0] * 20
    closes[-2] = 94.0  # within last RECENT_BARS, last close still on-side
    assert RECENT_BARS == 6
    assert _synth(closes) is False


def test_rule_a_fixed_cap_not_percentage():
    closes = [100.0] * 40
    # five isolated historic violations, not in the last 6, no 3 consecutive
    five = list(closes)
    for i in (2, 5, 8, 11, 14):
        five[i] = 94.0
    assert TOTAL_CAP == 5
    assert _synth(five) is True
    six = list(closes)
    for i in (2, 5, 8, 11, 14, 17):
        six[i] = 94.0
    assert _synth(six) is False


def test_flicker_gate_limit_is_zero():
    assert FLICKER_STEPS_LIMIT == 0


def test_comparative_edge_is_between_1_and_115():
    # selloff 1h @ 2026-11-13T08:00Z, ATR 680.92: 74076.19 vs 73380.20
    sep = abs(74076.19 - 73380.20) / 680.92
    assert COMPARATIVE_MIN_SEP_ATR < sep < COMPARATIVE_HYST_SEP_ATR
    sep2 = abs(74076.19 - 74791.41) / 680.92
    assert COMPARATIVE_MIN_SEP_ATR < sep2 < COMPARATIVE_HYST_SEP_ATR


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    failed = []
    for fn in tests:
        try:
            fn()
        except Exception as e:
            failed.append((fn.__name__, e))
            print("FAIL", fn.__name__, e)
        else:
            print("ok  ", fn.__name__)
    print(f"{len(tests) - len(failed)}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
