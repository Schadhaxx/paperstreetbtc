#!/usr/bin/env python3
"""Pre-computed stats for the PaperStreet site (Python supercharge, slice 3).

Reads the published history.json (data branch) + the STRC dividend ledger
(assets/js/ledger.js) and writes two generated files:

  stats.json   monthly returns, best/worst days, drawdown from peak and
               volatility per sleeve/benchmark; Pulse context values;
               the STRC dividend calendar; price badges.
  history.csv  one-click CSV export of history.json closes.

The site DISPLAYS these numbers; it does not re-derive them in JS. All
stats come from the real published history — nothing is invented. A
Tiingo-final date (slice 2) is a published value and is used as published;
it is not special-cased here. Spot mode only: the stats describe the
book's default model ($100,000 sleeves at 2025-12-31, buy-and-hold).
Vehicle (IBIT/FBTC) stats are not in this slice.

Sleeve NAVs replicate assets/js/book.js exactly: initial units at the base
close, STRC cash dividends receivable from the ex-date until the pay
session, cash buying the sleeve's dividend assets at the pay session's
close. Benchmarks replicate book.js too: SPY/QQQ total return
(distributions reinvested at the ex-date close), BTC/BRK.B/MSTR/GLD
price return, all indexed to 100 at the base close.

Stdlib only. No network, no API key, no new data source.

Usage:
  python3 tools/stats.py --history <history.json> --ledger <ledger.js>
      --out-stats <stats.json> --out-csv <history.csv> [--now <ISO>]
Exit 0 = written, 1 = input unreadable, 2 = usage error.
"""

import argparse
import ast
import csv
import json
import math
import re
import sys
from datetime import datetime, timezone

SESSIONS_PER_YEAR = 252  # annualised volatility from daily returns
ROUND_LEVELS = [60000, 65000, 70000, 75000, 80000, 85000, 90000,
                95000, 100000, 110000, 120000, 150000, 200000]
BADGE_LOOKBACK = 30  # sessions to look back for a BTC round-number crossing


def fail(msg):
    print("stats: " + msg, file=sys.stderr)
    return 1


def parse_ledger(text):
    """Parse the book out of assets/js/ledger.js.

    Returns (base, start, sleeves, strc) where sleeves is
    {key: {'w': {asset: weight}, 'div': {asset: share}}} and strc is a
    list of [record, ex, pay, $/share]. The ledger is a JS object literal;
    the strc array is valid Python literal syntax (single-quoted strings),
    the sleeve maps are small enough to regex.
    """
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

    # strc: [ ... ] — bracket-match from the 'strc:' key, then literal_eval.
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
    raw = re.sub(r"/\*.*?\*/", "", raw, flags=re.S)  # JS block comments
    strc = ast.literal_eval(raw)
    return base, start, sleeves, strc


def sess_on_or_after(dates, d):
    """First session date >= d, or None if d is past the last session."""
    for x in dates:
        if x >= d:
            return x
    return None


def build_sleeve_navs(dates, closes, base, start, sleeves, strc):
    """Daily NAV per sleeve, replicating assets/js/book.js.

    Returns {key: {date: nav}} on the $start scale. Events are STRC
    dividends: cash = STRC shares held at ex-date x $/share, receivable
    from the ex-date until the pay session, buying the sleeve's dividend
    assets at the pay session's close.
    """
    evs = []
    for rec, ex, pay, dps in strc:
        if ex <= base:
            continue
        evs.append({"record": rec, "ex": ex, "pay": pay, "dps": float(dps),
                    "pay_td": sess_on_or_after(dates, pay)})
    # pay order, as in book.js
    evs.sort(key=lambda e: e["pay_td"] or "9999-99-99")

    navs = {}
    sleeve_events = {}
    for key, s in sleeves.items():
        # initial units at the base close
        init = {a: start * w / closes[base][a] for a, w in s["w"].items()}
        cur = dict(init)
        # holdings snapshot after each pay session
        hist = []  # [(pay_td, holdings dict)]
        ev_recs = []
        for e in evs:
            # STRC shares held at the ex-date (holdings as of then).
            # STRC is never traded and no dividend route buys it, so this
            # is the initial holding — but it is read from the timeline,
            # not assumed, so a future route change stays correct.
            h = init
            for pay_td, snap in hist:
                if pay_td <= e["ex"]:
                    h = snap
            cash = (h.get("STRC") or 0) * e["dps"]
            e2 = dict(e)
            e2["cash"] = cash
            e2["strc_shares"] = h.get("STRC") or 0
            ev_recs.append(e2)
            if e["pay_td"]:
                for a, share in s["div"].items():
                    px = closes[e["pay_td"]][a]
                    cur[a] = (cur.get(a) or 0) + cash * share / px
                hist.append((e["pay_td"], dict(cur)))
        sleeve_events[key] = ev_recs
        # value each session: holdings as of then + receivable cash
        series = {}
        for d in dates:
            h = init
            for pay_td, snap in hist:
                if pay_td <= d:
                    h = snap
            cash = sum(e["cash"] for e in ev_recs
                       if e["ex"] <= d and (not e["pay_td"] or d < e["pay_td"]))
            v = cash
            for a, units in h.items():
                v += units * closes[d][a]
            series[d] = v
        navs[key] = series
    return navs, evs, sleeve_events


def build_benchmarks(dates, closes, divs, base):
    """Benchmark series indexed to 100 at the base close (book.js bench)."""
    out = {}
    for k, sym in (("btc", "BTC"), ("brk", "BRK.B"), ("mstr", "MSTR"),
                   ("gold", "GLD")):
        b = closes[base][sym]
        out[k] = {d: 100.0 * closes[d][sym] / b for d in dates}
    for k, sym in (("spy", "SPY"), ("qqq", "QQQ")):
        b = closes[base][sym]
        dv = divs.get(sym) or {}
        sh = 1.0 / b
        series = {}
        for d in dates:
            if d > base and dv.get(d):
                sh += sh * dv[d] / closes[d][sym]
            series[d] = 100.0 * sh * closes[d][sym]
        out[k] = series
    return out


def daily_returns(dates, series):
    """{date: pct return vs prior session} (first session has none)."""
    out = {}
    prev = None
    for d in dates:
        v = series[d]
        if prev is not None and prev > 0:
            out[d] = (v / prev - 1.0) * 100.0
        prev = v
    return out


def series_stats(dates, series, base, start_value):
    """Monthly returns, best/worst day, drawdowns, annualised volatility."""
    rets = daily_returns(dates, series)
    last = dates[-1]
    value = series[last]
    # monthly returns: last session of each month vs prior month-end
    monthly = {}
    months = sorted({d[:7] for d in dates if d > base})
    prev_end = series[base]
    for mo in months:
        mdays = [d for d in dates if d[:7] == mo]
        if not mdays:
            continue
        mend = series[mdays[-1]]
        monthly[mo] = (mend / prev_end - 1.0) * 100.0
        prev_end = mend
    # best / worst day
    best_d = max(rets, key=lambda d: rets[d]) if rets else None
    worst_d = min(rets, key=lambda d: rets[d]) if rets else None
    # drawdown: running max, current + worst
    peak = -1.0
    peak_d = None
    dd_now = 0.0
    max_dd = 0.0
    max_dd_d = None
    for d in dates:
        v = series[d]
        if v > peak:
            peak, peak_d = v, d
        dd = (v / peak - 1.0) * 100.0
        if d == last:
            dd_now = dd
        if dd < max_dd:
            max_dd, max_dd_d = dd, d
    # annualised volatility: sample std of daily returns x sqrt(252)
    rs = list(rets.values())
    vol = None
    if len(rs) > 1:
        mean = sum(rs) / len(rs)
        var = sum((x - mean) ** 2 for x in rs) / (len(rs) - 1)
        vol = math.sqrt(var) * math.sqrt(SESSIONS_PER_YEAR)
    ytd = (value / series[base] - 1.0) * 100.0
    cur_mo = last[:7]
    mtd = monthly.get(cur_mo)
    return {
        "value": round(value, 2),
        "ytd_pct": round(ytd, 2),
        "mtd_pct": round(mtd, 2) if mtd is not None else None,
        "mtd_month": cur_mo,
        "monthly": {mo: round(p, 2) for mo, p in monthly.items()},
        "best_day": ({"date": best_d, "pct": round(rets[best_d], 2)}
                     if best_d else None),
        "worst_day": ({"date": worst_d, "pct": round(rets[worst_d], 2)}
                      if worst_d else None),
        "drawdown_pct": round(dd_now, 2),
        "peak_value": round(peak, 2),
        "peak_date": peak_d,
        "max_drawdown_pct": round(max_dd, 2),
        "max_drawdown_date": max_dd_d,
        "vol_ann_pct": round(vol, 2) if vol is not None else None,
    }


def build_calendar(dates, sleeves, evs, sleeve_events):
    """Upcoming STRC dividend calendar (STRC only).

    Upcoming = pay session after the last close, or pay date after the
    last close (pay session not yet known). Per-sleeve cash = STRC shares
    held at the ex-date x $/share, read from the timeline (see
    build_sleeve_navs), not assumed. Month totals are the FULL declared
    month (paid + upcoming) for any month with an upcoming event, so
    November reads $1.00/share — the declared aggregate — while the
    upcoming list shows what is still to come.
    """
    last = dates[-1]
    upcoming = []
    for i, e in enumerate(evs):
        if e["pay_td"] and e["pay_td"] <= last:
            continue  # already paid
        cash = {}
        for key in sleeves:
            cash[key] = round(sleeve_events[key][i]["cash"], 2)
        upcoming.append({
            "record": e["record"], "ex": e["ex"], "pay": e["pay"],
            "pay_session": e["pay_td"],
            "per_share": e["dps"],
            "cash": cash,
        })
    # month totals: full month (all ledger events with a record in that
    # month), for months that still have an upcoming event.
    upcoming_months = {u["record"][:7] for u in upcoming}
    months = {}
    for i, e in enumerate(evs):
        if e["record"][:7] not in upcoming_months:
            continue
        mo = e["record"][:7]
        m = months.setdefault(mo, {"per_share": 0.0, "cash": {}})
        m["per_share"] += e["dps"]
        for key in sleeves:
            c = sleeve_events[key][i]["cash"]
            m["cash"][key] = round(m["cash"].get(key, 0.0) + c, 2)
    for m in months.values():
        m["per_share"] = round(m["per_share"], 4)
    return {"upcoming": upcoming, "month_totals": months}


def build_badges(dates, closes, navs):
    """Price badges, from closes only (no intraday flicker).

    - BTC round-number crossing: the most recent session (within the
      lookback) where the BTC close crossed a round level, up or down.
    - Sleeve new high: a sleeve whose latest close is its all-time high.
    """
    badges = []
    # BTC round crossings, most recent first
    for i in range(len(dates) - 1, max(0, len(dates) - BADGE_LOOKBACK), -1):
        prev, cur = closes[dates[i - 1]]["BTC"], closes[dates[i]]["BTC"]
        for lvl in ROUND_LEVELS:
            if (prev < lvl <= cur) or (prev > lvl >= cur):
                direction = "up" if cur > prev else "down"
                badges.append({
                    "kind": "btc_round",
                    "level": lvl,
                    "direction": direction,
                    "date": dates[i],
                    "text": "BTC crossed %s $%s" % (
                        "above" if direction == "up" else "below",
                        "{:,}".format(lvl)),
                })
                break
        if badges:
            break
    # sleeve new highs
    for key, series in navs.items():
        last = dates[-1]
        if series[last] >= max(series.values()) - 1e-9:
            badges.append({
                "kind": "sleeve_high",
                "sleeve": key,
                "date": last,
                "text": "at a new high",
            })
    return badges


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--history", required=True)
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--out-stats", required=True)
    ap.add_argument("--out-csv", required=True)
    ap.add_argument("--now", default=None)
    args = ap.parse_args(argv)

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

    closes = hist.get("closes") or {}
    if not closes or base not in closes:
        return fail("history.json has no closes for base %s" % base)
    dates = sorted(closes.keys())
    divs = hist.get("divs") or {}

    navs, evs, sleeve_events = build_sleeve_navs(
        dates, closes, base, start, sleeves, strc)
    benches = build_benchmarks(dates, closes, divs, base)

    names = {"berkshire": "Berkshire Killer", "hodlr": "Hodler Jam Sandwich",
             "hf": "Hedge Fund Killer", "saylor": "Saylor Moon",
             "btc": "Spot BTC", "spy": "S&P 500 (SPY, total return)",
             "qqq": "QQQ (total return)", "brk": "Berkshire (BRK.B)",
             "mstr": "MSTR", "gold": "Gold (GLD)"}
    series = {}
    for key, nav in navs.items():
        st = series_stats(dates, nav, base, start)
        st["name"] = names.get(key, key)
        st["kind"] = "sleeve"
        series[key] = st
    for key, bench in benches.items():
        st = series_stats(dates, bench, base, 100.0)
        st["name"] = names.get(key, key)
        st["kind"] = "benchmark"
        series[key] = st

    # Pulse context, per sleeve: $ above the Jan 1 start, $ below the peak.
    pulse = {}
    for key, st in series.items():
        if st["kind"] != "sleeve":
            continue
        pulse[key] = {
            "value": st["value"],
            "above_start": round(st["value"] - start, 2),
            "above_start_pct": st["ytd_pct"],
            "below_peak": round(st["peak_value"] - st["value"], 2),
            "peak_value": st["peak_value"],
            "peak_date": st["peak_date"],
        }

    calendar = build_calendar(dates, sleeves, evs, sleeve_events)
    badges = build_badges(dates, closes, navs)

    now = args.now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    stats = {
        "v": 1,
        "generated": now,
        "as_of": dates[-1],
        "base": base,
        "start_value": start,
        "source": "history.json (data branch) + ledger.js (STRC dividends)",
        "note": ("Pre-computed by Python; the site displays these numbers, "
                 "it does not re-derive them. Spot mode only."),
        "series": series,
        "pulse": pulse,
        "dividends": calendar,
        "badges": badges,
        "csv": "history.csv",
    }

    symbols = sorted({a for d in dates for a in closes[d]})
    try:
        with open(args.out_stats, "w") as f:
            json.dump(stats, f, indent=1, sort_keys=True)
            f.write("\n")
        with open(args.out_csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date"] + symbols)
            for d in dates:
                w.writerow([d] + [closes[d].get(a, "") for a in symbols])
    except OSError as e:
        return fail("cannot write output: %s" % e)
    print("stats: %d closes through %s; %d series, %d upcoming STRC "
          "payments, %d badges" % (len(dates), dates[-1], len(series),
                                    len(calendar["upcoming"]), len(badges)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
