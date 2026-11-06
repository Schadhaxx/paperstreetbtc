#!/usr/bin/env python3
"""What-if backtester for the PaperStreet site (Python supercharge, slice 4).

Replays the ledger offline with different rules and writes the difference
in dollars and percent. The safe way to test CR-005 and the vehicle toggle
before anyone builds them live. Uses the REAL history (history.json closes,
opens.json opens, vehicle-daily.json ETF closes) and the REAL ledger
(assets/js/ledger.js) — nothing is invented.

The engine replicates assets/js/book.js exactly: initial units at the base
close, STRC cash dividends receivable from the ex-date until the pay
session, cash buying the sleeve's dividend assets at the pay session's
price. Contributions (lump sums / DCA) buy the sleeve at target weights
under the rule being tested.

Rules that can vary (one run = one rule set):
  --price open|close   lump-sum / contribution pricing. CR-005 (current)
                       is OPEN: buy at the session open, weekdays only,
                       a weekend/holiday date held to the next session's
                       open. The alternative is the session CLOSE.
  --vehicle SPOT|IBIT|FBTC
                       which price series the BTC leg uses. Spot is the
                       default model; IBIT/FBTC re-base the BTC slice in
                       vehicle units (initial BTC units = $weight /
                       vehicle base close), exactly as book.js does.
                       Dividend buys follow the same rule (STRC cash buys
                       the vehicle at the pay session's vehicle close in
                       ETF mode — locked 29 Oct 2026).
  --dca monthly|weekly DCA schedule. Monthly is the current assumption;
                       weekly is the alternative.

--compare runs the baseline (open + Spot + the contributions/DCA given)
and the three plan scenarios — close-not-open, IBIT-not-spot,
weekly-not-monthly DCA — and prints the difference in $ and %.

Assumptions, documented (not guessed silently):
  * In ETF mode the BTC leg of an open-priced buy uses the vehicle CLOSE,
    because no vehicle opens exist (vehicle-daily.json carries closes
    only; opens.json has no IBIT/FBTC keys). This is the same treatment
    item 3 (vehicle-following for "Your sleeve") uses for the sleeve
    lines, and the same treatment book.js uses for dividend buys. No
    vehicle price is ever synthesised from spot opens.
  * An open that is missing, or more than 25% from that session's close,
    falls back to the close (the same sanity rule compare.js uses).
  * A weekly DCA amount is chosen to match the monthly total:
    weekly = monthly x 12 / 52, so 52 weekly payments total about the
    same as 12 monthly payments. The comparison is about timing, not
    about contributing more.
  * A contribution dated before the base (2025-12-31) is ignored; a
    contribution dated after the last close is ignored (it has not
    happened yet in the data). Both are listed in the output so the
    caller can see what was skipped.

Stdlib only. No network, no API key, no new data source.

Usage:
  python3 tools/backtest.py --history <history.json> --ledger <ledger.js>
      --opens <opens.json> [--vehicle-daily <vehicle-daily.json>]
      [--sleeve <key>] [--contributions <file> | --dca <spec>]
      [--price open|close] [--vehicle SPOT|IBIT|FBTC]
      [--as-of <date>] [--compare] [--out <file>]
Exit 0 = done, 1 = input unreadable, 2 = usage error.

DCA spec: monthly:AMOUNT:DAY:START:END  (DAY = day of month, 1-28)
          weekly:AMOUNT:WEEKDAY:START:END (WEEKDAY = 0 Mon .. 6 Sun)
Contributions file: JSON list of {"date": "2026-03-02", "amount": 1000}
  (a "sleeve" key per entry overrides --sleeve).
"""

import argparse
import ast
import json
import re
import sys
from datetime import date, timedelta

OPEN_SANITY = 0.25  # an open >25% from the close falls back to the close
WEEKS_PER_YEAR = 52
MONTHS_PER_YEAR = 12


def fail(msg):
    print("backtest: " + msg, file=sys.stderr)
    return 1


def parse_ledger(text):
    """Parse the book out of assets/js/ledger.js (same parser as slice 3)."""
    m = re.search(r"base:\s*'([^']+)'", text)
    base = m.group(1) if m else None
    m = re.search(r"start:\s*([0-9]+(?:\.[0-9]+)?)", text)
    start = float(m.group(1)) if m else None
    if not base or not start:
        raise ValueError("ledger: base/start not found")

    sleeves = {}
    for sm in re.finditer(
            r"(\w+):\s*\{\s*w:\s*\{([^}]*)\},\s*div:\s*\{([^}]*)\}\s*\}",
            text):
        key, wtxt, dtxt = sm.group(1), sm.group(2), sm.group(3)
        w = {a: float(v) for a, v in re.findall(r"([A-Z.]+):\s*([0-9.]+)", wtxt)}
        div = {a: float(v) for a, v in
               re.findall(r"([A-Z.]+):\s*([0-9.]+)", dtxt)}
        if w:
            sleeves[key] = {"w": w, "div": div}
    if not sleeves:
        raise ValueError("ledger: no sleeves parsed")

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
    strc = ast.literal_eval(raw)
    return base, start, sleeves, strc


def sess_on_or_after(dates, d):
    """First session date >= d, or None if d is past the last session."""
    for x in dates:
        if x >= d:
            return x
    return None


def build_vehicle_map(dates, vehicle_rows, base):
    """date -> vehicle close for every session (book.js loadVehicleData).

    The vehicle series may lag the Spot sessions by at most 1 session;
    a missing session is filled with the vehicle's prior close. A lag of
    2+ sessions, or an interior gap of 2+ sessions, is an error (the
    same rule book.js enforces, and the same reason vehicle.js falls
    back to Spot).
    """
    raw = {}
    for p in vehicle_rows:
        x = p[1]
        if not isinstance(x, (int, float)) or not (x > 0) or x != x:
            raise ValueError("vehicle: bad value on %s" % p[0])
        raw[p[0]] = float(x)
    raw_dates = sorted(raw)
    if not raw_dates:
        raise ValueError("vehicle: empty series")
    v_end = raw_dates[-1]
    tail_lag = sum(1 for d in dates if d > v_end)
    if tail_lag > 1:
        raise ValueError(
            "vehicle: stale, last close %s, %d sessions behind Spot"
            % (v_end, tail_lag))
    m = {}
    j = -1
    gap = 0
    for d in dates:
        while j + 1 < len(raw_dates) and raw_dates[j + 1] <= d:
            j += 1
        if j < 0:
            raise ValueError("vehicle: missing session %s (no prior close)"
                             % d)
        gap = 0 if raw_dates[j] == d else gap + 1
        if gap > 1:
            raise ValueError("vehicle: missing %d sessions up to %s"
                             % (gap, d))
        m[d] = raw[raw_dates[j]]
    return m


class Engine:
    """The ledger engine, replicating assets/js/book.js.

    price_at(asset, date) is the CLOSE price used for valuation and for
    dividend buys. buy_price(asset, date) is the price a contribution
    pays under the rule being tested (open or close).
    """

    def __init__(self, dates, closes, base, start, sleeves, strc,
                 price_at, buy_price):
        self.dates = dates
        self.closes = closes
        self.base = base
        self.start = start
        self.sleeves = sleeves
        self.price_at = price_at
        self.buy_price = buy_price
        evs = []
        for rec, ex, pay, dps in strc:
            if ex <= base:
                continue
            evs.append({"record": rec, "ex": ex, "pay": pay,
                        "dps": float(dps),
                        "pay_td": sess_on_or_after(dates, pay)})
        # pay order, as in book.js
        evs.sort(key=lambda e: e["pay_td"] or "9999-99-99")
        self.evs = evs

    def run(self, key, contributions):
        """Value a sleeve at every session.

        contributions: list of {"date", "amount"} (target dates; each is
        rolled to the next session, CR-005). Returns (series, summary)
        where series is {date: value} and summary lists what was bought
        and what was skipped.
        """
        s = self.sleeves[key]
        # initial units at the base close (re-based in vehicle units when
        # price_at is a vehicle series — exactly as book.js does).
        init = {a: self.start * w / self.price_at(a, self.base)
                for a, w in s["w"].items()}
        # contribution buys, rolled to the next session (CR-005 hold).
        buys = []  # (buy session, {asset: units}, amount, target date)
        skipped = []
        for c in contributions:
            d, amt = c["date"], float(c["amount"])
            if d <= self.base:
                skipped.append({"date": d, "amount": amt,
                                "reason": "on or before base"})
                continue
            td = sess_on_or_after(self.dates, d)
            if td is None:
                skipped.append({"date": d, "amount": amt,
                                "reason": "after last close"})
                continue
            units = {}
            for a, w in s["w"].items():
                px = self.buy_price(a, td)
                units[a] = amt * w / px
            buys.append((td, units, amt, d))
        # dividend timeline: STRC held at an ex-date includes contribution
        # STRC bought at sessions <= that ex-date (dividend buys never
        # buy STRC, so only contributions change the STRC holding).
        def strc_held(ex):
            h = init.get("STRC") or 0
            for td, units, _amt, _d in buys:
                if td <= ex:
                    h += units.get("STRC") or 0
            return h

        # dividend buys, in pay order
        div_buys = []  # (pay_td, {asset: units})
        ev_cash = []   # (ex, pay_td, cash) for the receivable
        for e in self.evs:
            cash = strc_held(e["ex"]) * e["dps"]
            ev_cash.append((e["ex"], e["pay_td"], cash))
            if e["pay_td"]:
                units = {}
                for a, share in s["div"].items():
                    px = self.price_at(a, e["pay_td"])
                    units[a] = cash * share / px
                div_buys.append((e["pay_td"], units))
        # value each session
        series = {}
        for d in self.dates:
            h = dict(init)
            for td, units, _amt, _t in buys:
                if td <= d:
                    for a, u in units.items():
                        h[a] = (h.get(a) or 0) + u
            for td, units in div_buys:
                if td <= d:
                    for a, u in units.items():
                        h[a] = (h.get(a) or 0) + u
            cash = sum(c for ex, pay_td, c in ev_cash
                       if ex <= d and (not pay_td or d < pay_td))
            v = cash
            for a, units in h.items():
                v += units * self.price_at(a, d)
            series[d] = v
        bought = [{"target_date": t, "buy_session": td, "amount": amt}
                  for td, _u, amt, t in buys]
        return series, {"bought": bought, "skipped": skipped,
                        "contributed": sum(b["amount"] for b in bought)}


def parse_dca(spec):
    """monthly:AMOUNT:DAY:START:END or weekly:AMOUNT:WEEKDAY:START:END."""
    parts = spec.split(":")
    if len(parts) != 5:
        raise ValueError("dca spec: want freq:amount:day:start:end")
    freq, amt, day, start, end = parts
    if freq not in ("monthly", "weekly"):
        raise ValueError("dca spec: freq must be monthly or weekly")
    try:
        amt = float(amt)
        day = int(day)
    except ValueError:
        raise ValueError("dca spec: amount/day must be numbers")
    if amt <= 0:
        raise ValueError("dca spec: amount must be positive")
    if freq == "monthly" and not 1 <= day <= 28:
        raise ValueError("dca spec: monthly day must be 1-28")
    if freq == "weekly" and not 0 <= day <= 6:
        raise ValueError("dca spec: weekday must be 0 (Mon) - 6 (Sun)")
    return freq, amt, day, start, end


def dca_dates(spec):
    """Target dates for a DCA spec (the engine rolls each to a session)."""
    freq, _amt, day, start, end = parse_dca(spec)
    s = date.fromisoformat(start)
    e = date.fromisoformat(end)
    out = []
    if freq == "monthly":
        y, m = s.year, s.month
        while True:
            d = date(y, m, day)
            if d > e:
                break
            if d >= s:
                out.append(d.isoformat())
            m += 1
            if m > 12:
                m, y = 1, y + 1
    else:
        d = s
        # first day >= start with the wanted weekday
        while d.weekday() != day:
            d += timedelta(days=1)
        while d <= e:
            out.append(d.isoformat())
            d += timedelta(days=7)
    return out


def dca_contributions(spec):
    freq, amt, _day, _s, _e = parse_dca(spec)
    return [{"date": d, "amount": amt} for d in dca_dates(spec)]


def run_rules(dates, closes, base, start, sleeves, strc, opens, veh_map,
              vehicle, price_mode, contributions, sleeve_keys, as_of):
    """Run one rule set. Returns {sleeve: {final, contributed, ...}}."""
    def price_at(a, d):
        if vehicle != "SPOT" and a == "BTC":
            return veh_map[d]
        return closes[d][a]

    def buy_price(a, d):
        if price_mode == "close":
            return price_at(a, d)
        # open (CR-005): the session open, except the BTC leg in ETF mode,
        # which has no open — it uses the vehicle close (same treatment as
        # item 3 and as book.js uses for dividend buys).
        if vehicle != "SPOT" and a == "BTC":
            return veh_map[d]
        o = (opens.get(d) or {}).get(a)
        cl = closes[d][a]
        if (isinstance(o, (int, float)) and o > 0
                and abs(o / cl - 1) <= OPEN_SANITY):
            return o
        return cl

    eng = Engine(dates, closes, base, start, sleeves, strc,
                 price_at, buy_price)
    out = {}
    for key in sleeve_keys:
        series, summary = eng.run(key, contributions)
        final = series[as_of]
        contributed = summary["contributed"]
        gain = final - start - contributed
        out[key] = {
            "final": round(final, 2),
            "contributed": round(contributed, 2),
            "gain": round(gain, 2),
            "gain_pct": round(gain / (start + contributed) * 100, 2)
            if start + contributed > 0 else None,
            "bought": summary["bought"],
            "skipped": summary["skipped"],
        }
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--history", required=True)
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--opens", default=None)
    ap.add_argument("--vehicle-daily", default=None)
    ap.add_argument("--sleeve", default=None,
                    help="one sleeve key; default is all four")
    ap.add_argument("--contributions", default=None)
    ap.add_argument("--dca", default=None,
                    help="monthly:AMOUNT:DAY:START:END or "
                         "weekly:AMOUNT:WEEKDAY:START:END")
    ap.add_argument("--price", choices=["open", "close"], default="open")
    ap.add_argument("--vehicle", choices=["SPOT", "IBIT", "FBTC"],
                    default="SPOT")
    ap.add_argument("--as-of", default=None)
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    if args.contributions and args.dca:
        return fail("--contributions and --dca are mutually exclusive")
    if args.vehicle != "SPOT" and not args.vehicle_daily:
        return fail("--vehicle-daily is required for IBIT/FBTC")
    if args.price == "open" and not args.opens:
        return fail("--opens is required for open pricing")

    try:
        with open(args.history) as f:
            hist = json.load(f)
    except (OSError, ValueError) as e:
        return fail("cannot read history.json: %s" % e)
    try:
        with open(args.ledger) as f:
            ledger_text = f.read()
    except OSError as e:
        return fail("cannot read ledger.js: %s" % e)
    try:
        base, start, sleeves, strc = parse_ledger(ledger_text)
    except ValueError as e:
        return fail(str(e))
    opens = {}
    if args.opens:
        try:
            with open(args.opens) as f:
                opens = json.load(f).get("o") or {}
        except (OSError, ValueError) as e:
            return fail("cannot read opens.json: %s" % e)
    veh_map = None
    if args.vehicle_daily:
        try:
            with open(args.vehicle_daily) as f:
                vd = json.load(f)
        except (OSError, ValueError) as e:
            return fail("cannot read vehicle-daily.json: %s" % e)

    closes = hist.get("closes") or {}
    if not closes or base not in closes:
        return fail("history.json has no closes for base %s" % base)
    dates = sorted(closes.keys())
    as_of = args.as_of or dates[-1]
    if as_of not in closes:
        return fail("--as-of %s is not a session" % as_of)
    sleeve_keys = [args.sleeve] if args.sleeve else sorted(sleeves)
    for k in sleeve_keys:
        if k not in sleeves:
            return fail("unknown sleeve %s" % k)

    # contributions for the baseline rule set
    if args.contributions:
        try:
            with open(args.contributions) as f:
                contribs = json.load(f)
        except (OSError, ValueError) as e:
            return fail("cannot read contributions: %s" % e)
        if not isinstance(contribs, list):
            return fail("contributions must be a JSON list")
    elif args.dca:
        try:
            contribs = dca_contributions(args.dca)
        except ValueError as e:
            return fail(str(e))
    else:
        contribs = []

    veh_maps = {}
    if args.vehicle_daily:
        for v in ("IBIT", "FBTC"):
            try:
                veh_maps[v] = build_vehicle_map(
                    dates, vd["vehicles"][v], base)
            except (KeyError, ValueError) as e:
                return fail("vehicle %s: %s" % (v, e))

    def run(vehicle, price_mode, contributions):
        vm = veh_maps.get(vehicle) if vehicle != "SPOT" else None
        return run_rules(dates, closes, base, start, sleeves, strc,
                         opens, vm, vehicle, price_mode, contributions,
                         sleeve_keys, as_of)

    baseline = run(args.vehicle, args.price, contribs)
    result = {
        "as_of": as_of,
        "base": base,
        "start": start,
        "baseline": {"vehicle": args.vehicle, "price": args.price,
                     "contributions": len(contribs),
                     "dca": args.dca},
        "results": baseline,
    }
    if args.compare:
        scenarios = {}
        # 1. close, not open (same contributions, same vehicle)
        if args.price == "open":
            scenarios["close_not_open"] = run(args.vehicle, "close", contribs)
        # 2. IBIT, not spot (same contributions, same pricing)
        if args.vehicle == "SPOT":
            scenarios["ibit_not_spot"] = run("IBIT", args.price, contribs)
        # 3. weekly, not monthly DCA (same total contributed)
        if args.dca:
            freq, amt, _day, s, e = parse_dca(args.dca)
            if freq == "monthly":
                weekly_amt = round(amt * MONTHS_PER_YEAR / WEEKS_PER_YEAR, 2)
                wspec = "weekly:%s:0:%s:%s" % (weekly_amt, s, e)
                scenarios["weekly_not_monthly"] = run(
                    args.vehicle, args.price, dca_contributions(wspec))
                result["baseline"]["weekly_amount"] = weekly_amt
        for name, res in scenarios.items():
            for key in sleeve_keys:
                b, r = baseline[key], res[key]
                r["diff_vs_baseline"] = round(r["final"] - b["final"], 2)
                r["diff_vs_baseline_pct"] = round(
                    (r["final"] / b["final"] - 1) * 100, 2)
        result["scenarios"] = scenarios

    if args.out:
        try:
            with open(args.out, "w") as f:
                json.dump(result, f, indent=1, sort_keys=True)
                f.write("\n")
        except OSError as e:
            return fail("cannot write output: %s" % e)

    # human-readable summary
    print("backtest as of %s (base %s, $%s start)" % (as_of, base, start))
    for key in sleeve_keys:
        b = baseline[key]
        print("  %-10s final $%s  contributed $%s  gain $%s (%s%%)"
              % (key, "{:,.2f}".format(b["final"]),
                 "{:,.2f}".format(b["contributed"]),
                 "{:,.2f}".format(b["gain"]), b["gain_pct"]))
    if args.compare:
        for name, res in result["scenarios"].items():
            print("  scenario %s:" % name)
            for key in sleeve_keys:
                r = res[key]
                print("    %-10s final $%s  diff $%s (%s%%)"
                      % (key, "{:,.2f}".format(r["final"]),
                         "{:,.2f}".format(r["diff_vs_baseline"]),
                         r["diff_vs_baseline_pct"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
