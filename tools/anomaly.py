#!/usr/bin/env python3
"""Anomaly detective for the PaperStreet site (Python supercharge, slice 4).

A daily check that looks for splits, absurd one-day jumps, missing
sessions, dividend doubles like the Tiingo STRC case, and stale prices —
and writes a short health report. Instead of discovering a bad bar when
the site stalls, you get a one-line flag the morning it appears.

This is a REPORTER, not a gate. Slice 1's validate.py is the gate that
BLOCKS bad data from publishing; this tool FINDS anomalies and reports
them. It shares the anomaly definitions where sensible — the 35% jump
threshold and the NYSE holiday set are the same as validate.py uses —
but a finding here never holds a run on its own. Exit 0 on a successful
scan, whether or not anomalies were found; the report is the output.

Checks (all on the real published data — nothing is invented):
  1. jumps — a single-session move over 35% is a split suspect (the same
     threshold validate.py holds on). If the move is close to a round
     split factor (2:1, 3:1, 4:1, 5:1, 10:1, or the inverse), it is
     labelled a likely split; otherwise an absurd jump.
  2. sessions — an expected NYSE session (weekday, not a holiday) with
     no close in history.json. Holiday set reused from
     tools/stock_weekly.py, same as validate.py.
  3. dividends — STRC ledger amounts that are about twice (or half) BOTH
     neighbours (an isolated spike, not a regime change — the daily
     $0.0333 amounts and the transitional half-period do not trip it,
     because their neighbours are not both half/double), and duplicate
     ex-dates. This is the Tiingo STRC double (1.916667 vs the declared
     0.958333) as a pattern, applied to the ledger itself.
  4. stale — a symbol whose last close is not the latest session, and
     (when prices.json is given) a live quote older than 30 minutes.

Report: JSON (--out) plus a short text summary on stdout. A clean scan
prints "No anomalies found".

Stdlib only. No network, no API key, no new data source.

Usage:
  python3 tools/anomaly.py --history <history.json>
      [--ledger <ledger.js>] [--prices <prices.json>]
      [--out <report.json>] [--now <ISO>]
Exit 0 = scan complete, 1 = input unreadable, 2 = usage error.
"""

import argparse
import ast
import json
import re
import sys
from datetime import datetime, timezone

JUMP_PCT = 35.0       # shared with validate.py check 4
SPLIT_FACTORS = (2, 3, 4, 5, 10)
SPLIT_TOL = 0.05      # a move within 5% of a round split factor
DOUBLE_LO = 1.8       # ~2x a neighbour (Tiingo STRC double: 1.916667/0.958333)
DOUBLE_HI = 2.2
STALE_MINUTES = 30    # a live quote older than this is stale, in market hours
MARKET_OPEN = (9, 30)   # a live quote is only expected fresh in market hours
MARKET_CLOSE = (16, 0)  # outside them the quote is the close, and being
                        # hours old is normal — not an anomaly.


def fail(msg):
    print("anomaly: " + msg, file=sys.stderr)
    return 1


def load_holidays():
    """NYSE holiday set, reused from tools/stock_weekly.py (same as
    validate.py); embedded copy as fallback so the tool still runs
    without the weekly tool present."""
    try:
        sys.path.insert(0, "tools")
        from stock_weekly import HOLIDAYS
        return set(HOLIDAYS)
    except Exception:
        pass
    return {
        "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03",
        "2026-05-25", "2026-06-19", "2026-07-03", "2026-09-07",
        "2026-11-26", "2026-12-25",
    }


def expected_sessions(first, last, holidays):
    """Weekdays minus holidays, first..last inclusive (ISO dates)."""
    out = []
    d = datetime.strptime(first, "%Y-%m-%d").date()
    end = datetime.strptime(last, "%Y-%m-%d").date()
    while d <= end:
        if d.weekday() < 5 and d.isoformat() not in holidays:
            out.append(d.isoformat())
        d = d.fromordinal(d.toordinal() + 1)
    return out


def parse_strc(text):
    """STRC dividend list out of assets/js/ledger.js: [record, ex, pay, $]."""
    i = text.find("strc:")
    if i < 0:
        raise ValueError("ledger: strc list not found")
    j = text.find("[", i)
    depth = 0
    k = j
    while k < len(text):
        c = text[k]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                break
        k += 1
    if depth != 0:
        raise ValueError("ledger: strc list brackets do not balance")
    raw = text[j:k + 1]
    raw = re.sub(r"/\*.*?\*/", "", raw, flags=re.S)
    return ast.literal_eval(raw)


def is_split_like(ratio):
    """Is a single-session price ratio close to a round split factor?"""
    for f in SPLIT_FACTORS:
        for cand in (f, 1.0 / f):
            if abs(ratio / cand - 1) <= SPLIT_TOL:
                return cand
    return None


def check_jumps(dates, closes):
    """>35% single-session moves, labelled likely-split or absurd-jump."""
    out = []
    symbols = sorted({a for d in dates for a in closes[d]})
    for sym in symbols:
        prev = None
        for d in dates:
            v = closes[d].get(sym)
            if v is None or prev is None:
                prev = v
                continue
            if prev > 0:
                pct = (v / prev - 1) * 100
                if abs(pct) > JUMP_PCT:
                    ratio = v / prev
                    split = is_split_like(ratio)
                    out.append({
                        "kind": "split" if split else "jump",
                        "symbol": sym,
                        "date": d,
                        "pct": round(pct, 2),
                        "from": prev,
                        "to": v,
                        "split_factor": split,
                        "detail": ("%s %s: %+0.2f%% in one session "
                                   "(%s -> %s)%s" % (
                                       sym, d, pct, prev, v,
                                       (" — close to a %s:1 split"
                                        % (split if split >= 1
                                           else "1:%s" % (1 / split)))
                                       if split else "")),
                    })
            prev = v
    return out


def check_sessions(dates, closes, holidays):
    """Expected NYSE sessions with no close at all."""
    expected = expected_sessions(dates[0], dates[-1], holidays)
    have = set(dates)
    missing = [d for d in expected if d not in have]
    return [{"kind": "missing_session", "date": d,
             "detail": "expected NYSE session %s has no close" % d}
            for d in missing]


def check_dividends(strc):
    """Dividend doubles (and halves) + duplicate ex-dates, STRC ledger."""
    out = []
    seen_ex = {}
    for i, (rec, ex, pay, dps) in enumerate(strc):
        if ex in seen_ex:
            out.append({
                "kind": "duplicate_ex_date", "date": ex,
                "detail": "STRC ex-date %s appears twice (records %s, %s)"
                          % (ex, seen_ex[ex], rec)})
        else:
            seen_ex[ex] = rec
        if dps is None or dps <= 0:
            out.append({
                "kind": "dividend_bad_amount", "date": ex,
                "detail": "STRC %s: $/share %s is not positive" % (ex, dps)})
            continue
        # isolated spike: ~2x (or ~0.5x) BOTH neighbours, so a regime
        # change (monthly -> daily, or a transitional half-period) does
        # not trip it — only a single amount out of line with the amounts
        # on either side of it.
        if 0 < i < len(strc) - 1:
            prev_dps = strc[i - 1][3]
            next_dps = strc[i + 1][3]
            if prev_dps and next_dps:
                r_prev = dps / prev_dps
                r_next = dps / next_dps
                if DOUBLE_LO <= r_prev <= DOUBLE_HI and \
                        DOUBLE_LO <= r_next <= DOUBLE_HI:
                    out.append({
                        "kind": "dividend_double", "date": ex,
                        "detail": ("STRC %s: $%.6g/share is ~2x both "
                                   "neighbours ($%.6g, $%.6g) — possible "
                                   "double (cf. Tiingo 1.916667 vs "
                                   "declared 0.958333)"
                                   % (ex, dps, prev_dps, next_dps))})
                elif 1 / DOUBLE_HI <= r_prev <= 1 / DOUBLE_LO and \
                        1 / DOUBLE_HI <= r_next <= 1 / DOUBLE_LO:
                    out.append({
                        "kind": "dividend_half", "date": ex,
                        "detail": ("STRC %s: $%.6g/share is ~0.5x both "
                                   "neighbours ($%.6g, $%.6g) — possible "
                                   "halved dividend"
                                   % (ex, dps, prev_dps, next_dps))})
    return out


def in_market_hours(now, holidays):
    """Is `now` (UTC) inside NYSE market hours (9:30-16:00 ET, weekday,
    not a holiday)? A live quote is only expected fresh then; outside
    market hours the quote is the close and being hours old is normal."""
    try:
        from zoneinfo import ZoneInfo
        et = now.astimezone(ZoneInfo("America/New_York"))
    except Exception:
        # no tz database: approximate ET as UTC-5 (Nov-Mar) / UTC-4
        # (Mar-Nov) by month — good enough for a reporter, and the
        # check degrades to skipping the live-quote test, never to a
        # false positive, when the offset is uncertain.
        return False
    if et.weekday() >= 5 or et.date().isoformat() in holidays:
        return False
    mins = et.hour * 60 + et.minute
    return (MARKET_OPEN[0] * 60 + MARKET_OPEN[1]
            <= mins < MARKET_CLOSE[0] * 60 + MARKET_CLOSE[1])


def check_stale(dates, closes, prices, now, holidays):
    """A symbol whose last close is not the latest session; a live quote
    older than STALE_MINUTES — but only when `now` is in market hours
    (outside them the quote is the close, and being hours old is normal)."""
    out = []
    last = dates[-1]
    symbols = sorted({a for d in dates for a in closes[d]})
    for sym in symbols:
        sym_dates = [d for d in dates if closes[d].get(sym) is not None]
        if not sym_dates:
            continue
        if sym_dates[-1] != last:
            out.append({
                "kind": "stale_symbol", "symbol": sym,
                "date": sym_dates[-1],
                "detail": ("%s last close %s, %d session(s) behind the "
                           "latest session %s"
                           % (sym, sym_dates[-1],
                              len([d for d in dates
                                   if d > sym_dates[-1]]), last))})
    if prices and in_market_hours(now, holidays):
        stocks = prices.get("stocks") or {}
        for sym, q in stocks.items():
            t = q.get("t")
            if t is None:
                continue
            ts = None
            if isinstance(t, (int, float)):
                # epoch seconds (the format prices.json uses)
                ts = datetime.fromtimestamp(t, tz=timezone.utc)
            elif isinstance(t, str):
                try:
                    ts = datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ").replace(
                        tzinfo=timezone.utc)
                except ValueError:
                    continue
            if ts is None:
                continue
            age = (now - ts).total_seconds() / 60
            if age > STALE_MINUTES:
                out.append({
                    "kind": "stale_quote", "symbol": sym,
                    "detail": ("%s live quote is %.0f minutes old "
                               "(older than %d min)" % (sym, age,
                                                        STALE_MINUTES))})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--history", required=True)
    ap.add_argument("--ledger", default=None)
    ap.add_argument("--prices", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--now", default=None)
    args = ap.parse_args(argv)

    try:
        with open(args.history) as f:
            hist = json.load(f)
    except (OSError, ValueError) as e:
        return fail("cannot read history.json: %s" % e)
    strc = None
    if args.ledger:
        try:
            with open(args.ledger) as f:
                strc = parse_strc(f.read())
        except (OSError, ValueError) as e:
            return fail("cannot read ledger.js: %s" % e)
    prices = None
    if args.prices:
        try:
            with open(args.prices) as f:
                prices = json.load(f)
        except (OSError, ValueError) as e:
            return fail("cannot read prices.json: %s" % e)

    closes = hist.get("closes") or {}
    if not closes:
        return fail("history.json has no closes")
    dates = sorted(closes.keys())
    now = (datetime.strptime(args.now, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc) if args.now
        else datetime.now(timezone.utc))
    holidays = load_holidays()

    anomalies = []
    anomalies += check_jumps(dates, closes)
    anomalies += check_sessions(dates, closes, holidays)
    if strc is not None:
        anomalies += check_dividends(strc)
    anomalies += check_stale(dates, closes, prices, now, holidays)

    by_kind = {}
    for a in anomalies:
        by_kind[a["kind"]] = by_kind.get(a["kind"], 0) + 1
    report = {
        "v": 1,
        "generated": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "as_of": dates[-1],
        "sessions": len(dates),
        "anomalies": len(anomalies),
        "by_kind": by_kind,
        "findings": anomalies,
    }
    if args.out:
        try:
            with open(args.out, "w") as f:
                json.dump(report, f, indent=1, sort_keys=True)
                f.write("\n")
        except OSError as e:
            return fail("cannot write report: %s" % e)

    if not anomalies:
        print("anomaly: no anomalies found (%d sessions through %s)"
              % (len(dates), dates[-1]))
    else:
        print("anomaly: %d anomal%s found (%d sessions through %s):"
              % (len(anomalies), "y" if len(anomalies) == 1 else "ies",
                 len(dates), dates[-1]))
        for a in anomalies:
            print("  - " + a["detail"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
