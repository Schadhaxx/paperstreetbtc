#!/usr/bin/env python3
"""Smart Trendlines job (TA Stage 3a, minimal version).

Computes BTC support/resistance levels + sloped trendlines per timeframe
(1h, 4h, 1d) and writes ta-lines.json (schema 1) for the data branch.
The browser (Stage 4) draws the lines; this job only computes them.

Algorithm (Stage 3a minimal, decided by Chief, agreed by Sunil):
  pivots (fractal swing highs/lows, lookback k=3) -> cluster pivot prices
  with an ATR-based tolerance -> score on touches (diminishing), recency
  in CANDLES, and not-broken-on-close (with flip) -> top 3 levels +
  up to 2 sloped lines per timeframe. No comparative layer, no
  hysteresis, no distance penalty — those return only if the replay
  test (tests/test_ta_lines.py) fires trigger A (flicker) or B
  (distance). See TA-BUILD-DRAFT.md "Stage 3a".

  UPDATE (first replay, Fri Nov 20 2026): BOTH triggers fired on 21
  days of real candles (1h max change 4, 32/42 steps; max distance
  36.7 ATR). So the full-version pieces are back in, as the draft
  prescribes: (B) a distance penalty — score *= 0.5**(distATR/5), so
  far lines are demoted and near lines rank into the top 3; (A) a
  comparative layer — a lower-scored line within 1 ATR of a
  higher-scored one is the same zone and is dropped; and hysteresis —
  an incumbent line ranks with score * 1.15 (from the previous run's
  ta-lines.json via --prev), so a challenger must beat it by >15% to
  displace it. The replay gate re-runs with these layers and must come
  back clean. "score" in the output is the effective score (after the
  distance factor); "rawScore" is the score before it, "distAtr" the
  distance in ATR, "held" marks lines kept only by hysteresis.

Data:
  1h: Coinbase Exchange BTC-USD candles (granularity 3600), last 30 days.
  4h: the same 1h candles aggregated into UTC 4h buckets EXACTLY the way
      the front end does (assets/js/btcchart-panel.js agg4hFromHourly):
      bucket key = floor(t_ms / 14400000) * 14400000, keep only buckets
      with all 4 hourly bars, o = first open, h = max high, l = min low,
      c = last close. (The front end's .slice(-42) is a display limit and
      is NOT part of the aggregation.)
  1d: real daily OHLC from Coinbase (granularity 86400), fetched with
      the same fetch/timeout/backoff/sanitizer path as 1h. The daily
      bars include the FORMING day (today's partial candle), so the 1d
      lastClose tracks the live price instead of a days-old close; the
      job FAILS CLOSED (exit 1, no output) if the newest daily bar is
      older than ~2 days. (Fix 2/3, Fri Nov 20 2026: the old code built
      daily candles from closes only — open = previous close, high/low
      = extremes of open/close — which halved the daily ATR (1,351.79
      vs ~2,775 from true OHLC) and dropped the wicks, so every daily
      distance, cluster width and break buffer was ~2x off. The
      closes-only derivation (daily_from_closes) survives only as the
      offline/fixture fallback for tests.)
  Sloped lines must BOUND the price, never cut through it (rule A,
  fix 2 — replaces the fix-1 allowance): a sloped candidate is valid
  as a kind only if sloped_line_valid() says so — its priceNow never
  sits on the wrong side of the last close, fewer than 3 consecutive
  wrong-side closes, none in the last 6 bars, at most 5 wrong-side
  closes in total (wrong-side = a close more than 0.5 ATR beyond the
  line). A line invalid as its native kind flips to the opposite kind
  only if it is valid as that kind under the same checks; otherwise
  it is dropped. The ranking never emits a support line above a
  concurrent resistance line.
  Every timeframe guarantees at least one level on each side of the
  price when one exists in the data (fix 4): a side left empty by the
  ranking is filled with the range extreme for that side (exempt from
  the 2-touch minimum and from the 8-ATR display cutoff, flagged
  "extreme": true); a side with no candidate at all is flagged
  missingSupport / missingResistance on the timeframe dict.

Output (schema 1) goes to --out (default ta-lines.json in the cwd).
The workflow (ta-lines.yml) publishes it to the data branch; the job
never writes to the data branch itself. Exit 0 = ok, 1 = fetch or
validation failed (no output written — a failed run never publishes a
partial file), 2 = bad arguments.
"""
import argparse
import bisect
import datetime as dt
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request

# --- Tunable constants (Stage 3a) -------------------------------------------
PIVOT_K = 3            # fractal lookback, each side (brief)
ATR_PERIOD = 14        # Wilder ATR period
CLUSTER_TOL_ATR = 0.5  # cluster radius around the cluster mean, in ATR
                       # (a cluster spans ~1 ATR, per the draft)
BREAK_BUFFER_ATR = 0.25  # close must cross a level by this much (ATR)
                         # to count as broken; a broken level FLIPS type
                         # instead of being discarded
RECENCY_HALF_LIFE = 100  # candles: a touch this old scores 0.5 on recency
UNBROKEN_BONUS = 1.0     # score component for a level never broken on close
TOUCH_WEIGHT = 2.0       # touch term weight. The harmonic touch sum spans
                         # ~1 (1 touch) to ~3 (10 touches); unweighted it
                         # is drowned by recency + unbroken (2.0 of
                         # constant terms), so an untested 1-touch pivot
                         # scores ~3.0, nearly as much as a proven 10-touch
                         # level (~5.0) — and the replay showed 1-touch
                         # levels churning in and out of the top 3 every
                         # few hours. Weighting touches x2 makes the primary
                         # evidence (how often a level was tested) dominate
                         # the score: 1 touch -> 4.0, 5 touches -> 6.6,
                         # 10 touches -> 7.9 (fresh, unbroken).
MIN_TOUCHES = 2          # a displayed level needs at least 2 tests. A
                         # 1-touch "level" is a single pivot, not a tested
                         # line; the replay showed they are the main churn
                         # source. Applied at ranking (display) time, not
                         # in cluster_levels, so the raw candidates stay
                         # inspectable.
MAX_LEVELS = 3           # caps per timeframe
MAX_SLOPED = 2
SLOPE_MAX_ATR = 0.25     # sane slope: at most 0.25 ATR of price per candle
SLOPE_MIN_SPAN = 10      # anchor pivots must be >= 10 candles apart
SLOPE_TOUCH_TOL_ATR = 0.5  # a pivot touches a sloped line within this (ATR)
SLOPE_MIN_TOUCHES = 3
# Rule A (fix 2, Nov 2026): sloped-line validity. A line is valid as a
# kind only if sloped_line_valid() says so: its priceNow never sits on
# the wrong side of the last close (no cushion), fewer than
# CONSEC_LIMIT consecutive wrong-side closes, no wrong-side close in
# the last RECENT_BARS bars, and at most TOTAL_CAP wrong-side closes
# in the whole anchor-to-now window (wrong-side = a close more than
# WRONG_TOL_ATR beyond the line). This REPLACES the fix-1 rule
# (max(2, 2% of bars)), which let 1h 58,676.58 (9 wrong, 5
# consecutive) and 1d 57,784.98 (13 wrong) through, and the 0.25 ATR
# flip buffer, which let 4h 60,177.21 escape as a flipped resistance
# with 148 wrong-side closes.
WRONG_TOL_ATR = 0.5    # wrong-side tolerance, in ATR
CONSEC_LIMIT = 3       # >= this many consecutive wrong-side closes -> invalid
RECENT_BARS = 6        # any wrong-side close in the last this many bars -> invalid
TOTAL_CAP = 5          # more than this many wrong-side closes total -> invalid
DAILY_MAX_AGE_DAYS = 2  # (fix 3) fail closed if the newest daily bar is
    # older than this (days) — the 1d levels must be measured against
    # current price, not a days-old close.
# Replay triggers (see tests/test_ta_lines.py):
FLICKER_MAX_CHANGE = 1   # (A) top-3 set changes by more than this -> fire
DIST_TOO_FAR_ATR = 10.0  # (B) a top-3 line further than this (ATR) -> fire
                         # (draft trigger; the test asserts against this)
DISPLAY_MAX_DIST_ATR = 8.0  # display cutoff: a line further than this
                         # (ATR) is never shown. A safety margin below the
                         # 10 ATR trigger: the replay showed levels at
                         # 8-10 ATR popping in and out of a thin top-3
                         # during fast moves (their effective scores are
                         # marginal, so they churn the set). Cutting the
                         # display at 8 ATR removes that marginal churn
                         # while the trigger-B limit stays at the draft's
                         # 10 ATR.
# Layers added because BOTH triggers fired on the first replay
# (21 days of real candles, Nov 2026 — see tests/test_ta_lines.py and
# handback/ta/ta-stage3-replay.json):
DIST_HALF_LIFE_ATR = 5.0  # (B) distance penalty: score *= 0.5**(dist/5);
                          # a line 5 ATR away keeps half its score
COMPARATIVE_MIN_SEP_ATR = 1.0  # (A) comparative layer: a lower-scored
                               # line within 1 ATR of a higher-scored one
                               # is the same zone, not a second line
COMPARATIVE_HYST_SEP_ATR = 1.15  # (C, fix 2) separation hysteresis:
                               # if one of the pair is an incumbent
                               # (in the previous run's set), keep them
                               # merged until they are more than 1.15 ATR
                               # apart — a pair at 1.02 ATR must not
                               # split and re-merge as the ATR wiggles.
                               # 1.15 = 1.0 + HYST_BONUS, consistent
                               # with the ranking hysteresis.
HYST_BONUS = 0.15         # (A) hysteresis: an incumbent line ranks with
                          # score * 1.15, so a challenger must beat it by
                          # more than 15% to displace it
HYST_MATCH_ATR = 0.5      # incumbent match tolerance (price, in ATR)

COINBASE_URL = ("https://api.exchange.coinbase.com/products/BTC-USD/candles"
                "?granularity={gran}&start={start}&end={end}")
UA = {"User-Agent": "Mozilla/5.0 paperstreet"}


def fetch(u, tries=4):
    """GET a URL as JSON, with retries (same pattern as tools/btc_daily.py)."""
    for i in range(tries):
        try:
            req = urllib.request.Request(u, headers=UA)
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep([5, 15, 30][min(i, 2)])


def fetch_1h(hours=720, end=None):
    """Coinbase 1h candles, newest-first API, paginated in 300-candle
    windows (the API caps at 300 rows per request). Returns ascending
    [(t_ms, o, h, l, c), ...] with t_ms the hour's UTC start.
    Rows are [time, low, high, open, close, volume]."""
    end = end or dt.datetime.now(dt.timezone.utc)
    # Round the end down to the current hour start so windows align.
    end = end.replace(minute=0, second=0, microsecond=0)
    out = []
    # Walk backwards in 300-hour windows; the API's `end` is inclusive,
    # so step the next window's end to just before the previous start.
    win_end = end
    remaining = hours
    while remaining > 0:
        n = min(300, remaining)
        win_start = win_end - dt.timedelta(hours=n)
        start_s = win_start.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_s = win_end.strftime("%Y-%m-%dT%H:%M:%SZ")
        rows = fetch(COINBASE_URL.format(gran=3600, start=start_s,
                                         end=end_s))
        if not isinstance(rows, list):
            raise RuntimeError("Coinbase 1h: unexpected response")
        for r in rows:
            if len(r) < 5:
                continue
            t, lo, hi, o, c = r[0], r[1], r[2], r[3], r[4]
            if not all(isinstance(x, (int, float)) and math.isfinite(x)
                       for x in (t, lo, hi, o, c)):
                continue
            if c <= 0 or o <= 0 or hi <= 0 or lo <= 0:
                continue
            out.append((int(t) * 1000, float(o), float(hi), float(lo),
                        float(c)))
        remaining -= n
        win_end = win_start
    # Dedupe by timestamp (window edges overlap by one candle) and sort.
    seen = {}
    for bar in out:
        seen[bar[0]] = bar
    return [seen[t] for t in sorted(seen)]


def agg4h(hourly):
    """Aggregate 1h candles into UTC 4h buckets, matching the front end's
    agg4hFromHourly exactly (same bucket boundaries, same complete-bucket
    rule, same OHLC). The front end's .slice(-42) display limit is NOT
    applied here — the job needs the full 4h series."""
    buckets = {}
    order = []
    for b in hourly:
        key = (b[0] // 14400000) * 14400000
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(b)
    out = []
    for key in sorted(order):
        seg = buckets[key]
        if len(seg) < 4:
            continue
        out.append((key, seg[0][1], max(x[2] for x in seg),
                    min(x[3] for x in seg), seg[-1][4]))
    return out


def fetch_daily(days=730, end=None):
    """Real Coinbase daily candles (granularity 86400), newest-first API,
    paginated in 300-day windows. Same fetch/timeout/backoff/sanitizer
    path as fetch_1h: the same fetch() helper, the same finite/positive
    checks, dedupe by timestamp, ascending. The last bar is the FORMING
    day (today's partial candle) — its close is the live price, so the
    1d lastClose tracks current price (fix 3). Returns ascending
    [(t_ms, o, h, l, c), ...] with t_ms the day's UTC-midnight start.
    Rows are [time, low, high, open, close, volume]."""
    end = end or dt.datetime.now(dt.timezone.utc)
    # Round the end down to today's UTC midnight so windows align; the
    # API's `end` is inclusive, so the forming day is included.
    end = end.replace(hour=0, minute=0, second=0, microsecond=0)
    out = []
    win_end = end
    remaining = days
    while remaining > 0:
        n = min(300, remaining)
        win_start = win_end - dt.timedelta(days=n)
        start_s = win_start.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_s = win_end.strftime("%Y-%m-%dT%H:%M:%SZ")
        rows = fetch(COINBASE_URL.format(gran=86400, start=start_s,
                                         end=end_s))
        if not isinstance(rows, list):
            raise RuntimeError("Coinbase daily: unexpected response")
        for r in rows:
            if len(r) < 5:
                continue
            t, lo, hi, o, c = r[0], r[1], r[2], r[3], r[4]
            if not all(isinstance(x, (int, float)) and math.isfinite(x)
                       for x in (t, lo, hi, o, c)):
                continue
            if c <= 0 or o <= 0 or hi <= 0 or lo <= 0:
                continue
            out.append((int(t) * 1000, float(o), float(hi), float(lo),
                        float(c)))
        remaining -= n
        win_end = win_start
    # Dedupe by timestamp (window edges overlap by one candle) and sort.
    seen = {}
    for bar in out:
        seen[bar[0]] = bar
    return [seen[t] for t in sorted(seen)]


def daily_from_ohlc_rows(rows):
    """Daily bars from real Coinbase daily rows ([t, lo, hi, o, c, ...]
    or [t, lo, hi, o, c]), as saved in tests/fixtures/ta/btc-daily-ohlc.json.
    Same sanitizer as the live path (finite, >0, dedupe, ascending)."""
    seen = {}
    for r in rows:
        if len(r) < 5:
            continue
        t, lo, hi, o, c = r[0], r[1], r[2], r[3], r[4]
        if not all(isinstance(x, (int, float)) and math.isfinite(x)
                   for x in (t, lo, hi, o, c)):
            continue
        if c <= 0 or o <= 0 or hi <= 0 or lo <= 0:
            continue
        seen[int(t) * 1000] = (int(t) * 1000, float(o), float(hi),
                               float(lo), float(c))
    return [seen[t] for t in sorted(seen)]


def daily_from_closes(path, days=730):
    """Daily candles seeded from assets/data/btc-daily.json (closes only).
    open = previous close; high/low = extremes of open/close.
    t_ms is the UTC midnight starting the day. Returns ascending bars.
    OFFLINE/FIXTURE FALLBACK ONLY (the --fixture path and its unit test):
    the live job uses fetch_daily (real OHLC, fix 2) because these
    derived candles halve the daily ATR and drop the wicks."""
    with open(path) as f:
        j = json.load(f)
    rows = j["d"][-days:]
    out = []
    prev = None
    for date_s, close in rows:
        if prev is None:
            prev = close
            continue
        o = prev
        c = float(close)
        h = max(o, c)
        lo = min(o, c)
        t = int(dt.datetime.strptime(date_s, "%Y-%m-%d").replace(
            tzinfo=dt.timezone.utc).timestamp() * 1000)
        out.append((t, o, h, lo, c))
        prev = c
    return out


def atr(bars, period=ATR_PERIOD):
    """Wilder ATR. Returns the ATR at the last bar (None if too few bars)."""
    if len(bars) < period + 1:
        return None
    trs = []
    for i in range(1, len(bars)):
        h, l, pc = bars[i][2], bars[i][3], bars[i - 1][4]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    a = sum(trs[:period]) / period
    for tr in trs[period:]:
        a = (a * (period - 1) + tr) / period
    return a


def pivots(bars, k=PIVOT_K):
    """Fractal swing pivots. A pivot high's high must be the maximum of
    the k-neighbourhood AND strictly greater than the previous bar's
    high — i.e. the pivot is the FIRST bar of a maximal plateau. The
    strict-greater-than-everything version never fires on the derived
    daily candles (open = previous close makes the high of a local max
    shared by two consecutive bars), so plateaus must be handled, not
    skipped. Same rule, mirrored, for lows. Returns
    [(index, price, 'high'|'low'), ...] in index order."""
    out = []
    n = len(bars)
    for i in range(k, n - k):
        hi = bars[i][2]
        lo = bars[i][3]
        if hi > bars[i - 1][2] and all(
                hi >= bars[j][2] for j in range(i - k, i + k + 1)):
            out.append((i, hi, "high"))
        if lo < bars[i - 1][3] and all(
                lo <= bars[j][3] for j in range(i - k, i + k + 1)):
            out.append((i, lo, "low"))
    return out


def _harmonic(n):
    return sum(1.0 / i for i in range(1, n + 1))


def cluster_levels(bars, pivs, atr_v, last_close):
    """Cluster pivot prices (tolerance +/-CLUSTER_TOL_ATR around the
    running cluster mean) and score each cluster. Returns ALL level
    candidates sorted by effective score desc (the top-3 cut happens in
    rank_lines, after the comparative layer and hysteresis). Each level
    carries price, kind, score (effective, after the distance factor),
    rawScore (before it), distAtr, touches, lastTouch, ageCandles,
    broken."""
    if not pivs or atr_v is None or atr_v <= 0:
        return []
    tol = CLUSTER_TOL_ATR * atr_v
    buf = BREAK_BUFFER_ATR * atr_v
    prices = sorted(p[1] for p in pivs)
    clusters = []
    cur = [prices[0]]
    for p in prices[1:]:
        centre = sum(cur) / len(cur)
        if abs(p - centre) <= tol:
            cur.append(p)
        else:
            clusters.append(cur)
            cur = [p]
    clusters.append(cur)
    last_i = len(bars) - 1
    levels = []
    for members in clusters:
        price = sum(members) / len(members)
        # Member pivots, in index order, for touches/recency/type.
        # (Prices are unique floats in practice; match by value via a
        # multiset so duplicate prices can't double-count.)
        pool = sorted(members)
        mem = []
        for p in pivs:
            if p[1] in pool:
                mem.append(p)
                pool.remove(p[1])
        mem.sort(key=lambda p: p[0])
        touches = len(mem)
        last_touch_i = mem[-1][0]
        age = last_i - last_touch_i
        n_low = sum(1 for p in mem if p[2] == "low")
        native = "support" if n_low * 2 >= touches else "resistance"
        broken = False
        kind = native
        if native == "support" and last_close < price - buf:
            kind = "resistance"
            broken = True
        elif native == "resistance" and last_close > price + buf:
            kind = "support"
            broken = True
        raw = (TOUCH_WEIGHT * _harmonic(touches)
               + 0.5 ** (age / RECENCY_HALF_LIFE)
               + (0.0 if broken else UNBROKEN_BONUS))
        dist_atr = abs(price - last_close) / atr_v
        eff = raw * 0.5 ** (dist_atr / DIST_HALF_LIFE_ATR)
        levels.append({
            "price": round(price, 2),
            "kind": kind,
            "score": round(eff, 3),
            "rawScore": round(raw, 3),
            "distAtr": round(dist_atr, 2),
            "touches": touches,
            "lastTouch": iso_ms(bars[last_touch_i][0]),
            "ageCandles": age,
            "broken": broken,
            "held": False,
            "extreme": False,  # set True only by guarantee_sides (fix 4)
        })
    levels.sort(key=lambda l: -l["score"])
    return levels


def _is_incumbent(line, prev, atr_v, price_fn, extra=None):
    """True iff the line was in the previous run's set: a previous line
    with a price within HYST_MATCH_ATR, kind-agnostic — a flipped line
    is the same line, as the replay matcher treats it. extra, when
    given, is an additional match predicate (price_fn, line, atr).
    prev is the previous run's timeframe list (levels or sloped) or
    None."""
    if not prev:
        return False
    for p in prev:
        if abs(price_fn(p) - price_fn(line)) > HYST_MATCH_ATR * atr_v:
            continue
        if extra is not None and not extra(p, line, atr_v):
            continue
        return True
    return False


def comparative_filter(levels, atr_v, prev=None):
    """Comparative layer (replay trigger A): a lower-scored level within
    COMPARATIVE_MIN_SEP_ATR of a higher-scored level is the same zone,
    not a second line — drop it. Keeps the top-3 from being crowded by
    near-duplicates that flip ranks between runs. Separation
    hysteresis (rule C, fix 2): a pair that WAS merged stays merged
    until they are more than COMPARATIVE_HYST_SEP_ATR apart. A merged
    pair has exactly one incumbent (the survivor is in the previous
    set, the suppressed line is not); when BOTH were displayed they
    were separate, so the threshold stays 1.0. (Applying the extension
    to both-displayed pairs made them oscillate in/out as the
    separation drifted across 1.15 — selloff 1h Nov 11: support
    73,556.50 vs resistance 74,076.19 at 1.05-1.16 ATR.)"""
    kept = []
    for lv in levels:
        drop = False
        for k in kept:
            sep = abs(lv["price"] - k["price"]) / atr_v
            if sep <= COMPARATIVE_MIN_SEP_ATR:
                drop = True
                break
            # The 1.15 extension is for a pair that WAS merged: the
            # survivor is the incumbent, the suppressed line is not,
            # so exactly one of the pair is an incumbent. When BOTH
            # were displayed they were separate, not merged —
            # extending the merge to 1.15 for them makes the pair
            # oscillate in/out as the separation drifts across 1.15
            # (selloff 1h Nov 11: support 73,556.50 vs resistance
            # 74,076.19, sep 1.05-1.16 ATR, flipped the support in/out
            # and the extreme slot with it). "Keep them merged" only
            # applies to a pair that was merged.
            if (sep <= COMPARATIVE_HYST_SEP_ATR
                    and _is_incumbent(k, prev, atr_v,
                                      lambda l: l["price"])
                    != _is_incumbent(lv, prev, atr_v,
                                     lambda l: l["price"])):
                drop = True
                break
        if not drop:
            kept.append(lv)
    return kept


def hysteresis_rank(cands, prev, atr_v, match_price, match_extra=None):
    """Hysteresis (replay trigger A): a line that was in the previous
    run's set keeps its place unless a challenger beats it by more than
    HYST_BONUS. Implemented as a ranking bonus for incumbents: a
    candidate matching a previous line (same kind, price within
    HYST_MATCH_ATR, plus match_extra when given) ranks with
    score * (1 + HYST_BONUS). The output score stays the true score;
    lines kept only because of the bonus are marked held=True by the
    caller. Returns the candidates re-ranked by boosted score."""
    if not prev:
        return list(cands)
    boosted = []
    for c in cands:
        b = c["score"] * (1.0 + HYST_BONUS) if _matches_prev(
            c, prev, atr_v, match_price, match_extra) else c["score"]
        boosted.append((b, c))
    boosted.sort(key=lambda bc: -bc[0])
    return [c for _, c in boosted]


def _matches_prev(cand, prev, atr_v, match_price, match_extra=None):
    for p in prev:
        if p["kind"] != cand["kind"]:
            continue
        if abs(match_price(p) - match_price(cand)) > HYST_MATCH_ATR * atr_v:
            continue
        if match_extra is not None and not match_extra(p, cand, atr_v):
            continue
        return True
    return False


def rank_levels(cands, prev, atr_v, cutoff_atr=DISPLAY_MAX_DIST_ATR):
    """Rank levels: comparative filter + hysteresis + top-MAX_LEVELS cut.
    Provisional top-3 by effective score (for the held flag). When a
    previous set exists, incumbents are boosted FIRST and the
    comparative filter runs in boosted order — so an incumbent keeps
    its zone unless a challenger beats it by more than HYST_BONUS.
    (Filtering before boosting would let the comparative layer drop the
    incumbent, which defeats the hysteresis.) Lines in the final set
    that were not in the provisional set are marked held=True.
    Two display gates apply before ranking: a level needs MIN_TOUCHES
    tests, and a level further than cutoff_atr from the price is never
    displayed (the distance layer's hard guard — a margin below the
    DIST_TOO_FAR_ATR trigger). cutoff_atr=None disables the distance
    gate: the replay uses that to measure the distance trigger BEFORE
    the display cutoff (fix, Fri Nov 20 2026 — measuring the displayed
    set made trigger B un-fireable by construction). The side guarantee
    (fix 4) is NOT part of ranking — compute_tf applies it after."""
    cands = [c for c in cands
             if c["touches"] >= MIN_TOUCHES
             and (cutoff_atr is None or c["distAtr"] <= cutoff_atr)]
    prov = comparative_filter(cands, atr_v, prev)[:MAX_LEVELS]
    if not prev:
        return prov
    boosted = hysteresis_rank(cands, prev, atr_v, lambda l: l["price"])
    final = comparative_filter(boosted, atr_v, prev)[:MAX_LEVELS]
    prov_ids = {(l["kind"], l["price"]) for l in prov}
    for l in final:
        if (l["kind"], l["price"]) not in prov_ids:
            l["held"] = True
    return final


def _no_crossing(lines):
    """Fix 1 backstop: never emit a support line above a concurrent
    resistance line. If a pair crosses, drop the lower-scored line of
    the pair and repeat until no support sits above any resistance.
    (Levels cannot cross: rank_levels' comparative filter keeps them
    >1 ATR apart, and a crossing needs them within 0.5 ATR — so this
    guard is only needed for sloped lines, whose comparative filter
    compares same-kind lines only.)"""
    out = list(lines)
    changed = True
    while changed:
        changed = False
        for s in out:
            if s["kind"] != "support":
                continue
            for r in out:
                if r["kind"] != "resistance":
                    continue
                if s["priceNow"] > r["priceNow"]:
                    out.remove(s if s["score"] <= r["score"] else r)
                    changed = True
                    break
            if changed:
                break
    return out


def rank_sloped(cands, prev, atr_v):
    """Rank sloped lines: same order as rank_levels — provisional top-2
    by effective score, then incumbents boosted first and the
    comparative filter in boosted order, then the top-2 cut. The same
    distance guard applies (a sloped line further than
    DISPLAY_MAX_DIST_ATR from the price at priceNow is never
    displayed); sloped lines already need SLOPE_MIN_TOUCHES (3)
    touches, so no extra touch gate is needed here. Finally the
    no-crossing guard (fix 1): no support above a resistance."""
    cands = [c for c in cands if c["distAtr"] <= DISPLAY_MAX_DIST_ATR]
    prov = comparative_filter_sloped(cands, atr_v, prev)[:MAX_SLOPED]
    if not prev:
        return _no_crossing(prov)
    boosted = hysteresis_rank(
        cands, prev, atr_v, lambda s: s["priceNow"],
        lambda p, c, a: abs(p["slope"] - c["slope"]) <= 0.05 * a)
    final = comparative_filter_sloped(boosted, atr_v, prev)[:MAX_SLOPED]
    prov_ids = {(s["kind"], s["priceNow"]) for s in prov}
    for s in final:
        if (s["kind"], s["priceNow"]) not in prov_ids:
            s["held"] = True
    return _no_crossing(final)


def comparative_filter_sloped(cands, atr_v, prev=None):
    """Comparative layer for sloped lines: drop a lower-scored line whose
    priceNow is within COMPARATIVE_MIN_SEP_ATR of a higher-scored line
    of the same kind with a similar slope. Separation hysteresis (rule
    C, fix 2): as comparative_filter — a pair that WAS merged stays
    merged until they are more than COMPARATIVE_HYST_SEP_ATR apart,
    i.e. exactly one of the pair is an incumbent (previous set,
    matched on priceNow and slope). Both-displayed pairs were
    separate, so their threshold stays 1.0."""
    kept = []
    for c in cands:
        dup = False
        for k in kept:
            if (k["kind"] == c["kind"]
                    and abs(k["slope"] - c["slope"]) <= 0.05 * atr_v):
                sep = abs(k["priceNow"] - c["priceNow"]) / atr_v
                if sep <= COMPARATIVE_MIN_SEP_ATR:
                    dup = True
                    break
                slope_match = (lambda p, q, a: abs(p["slope"] - q["slope"])
                               <= 0.05 * a)
                if (sep <= COMPARATIVE_HYST_SEP_ATR
                        and _is_incumbent(k, prev, atr_v,
                                          lambda s: s["priceNow"],
                                          slope_match)
                        != _is_incumbent(c, prev, atr_v,
                                         lambda s: s["priceNow"],
                                         slope_match)):
                    dup = True
                    break
        if not dup:
            kept.append(c)
    return kept


def _t_ms(t):
    """Unix ms for a bar/anchor timestamp: an int/float ms value, or a
    "YYYY-MM-DDTHH:MM:SSZ" string (the anchor format in sloped lines)."""
    if isinstance(t, (int, float)):
        return int(t)
    return int(dt.datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=dt.timezone.utc).timestamp() * 1000)


def sloped_line_valid(line, bars, atr, last_close=None, kind=None):
    """True iff the sloped line is valid as kind (default line["kind"])
    under rule A (fix 2). Wrong-side close = a close more than
    WRONG_TOL_ATR beyond the line, counted from the first anchor
    through the last bar inclusive. Invalid if ANY holds: (1) the
    last-close bound — never support with priceNow > last_close, never
    resistance with priceNow < last_close (equal is allowed); (2) >=
    CONSEC_LIMIT consecutive wrong-side closes; (3) any wrong-side
    close in the last RECENT_BARS bars; (4) more than TOTAL_CAP
    wrong-side closes in total. bars entries are [t, open, high, low,
    close] tuples or [t, close] pairs (the landed fix-2 fixture uses
    the latter)."""
    kind = kind or line["kind"]
    p0, slope = line["anchor"]["price"], line["slope"]
    # Anchor lookup: bars are time-sorted, so bisect on the timestamp
    # list (one cheap comprehension) instead of a min() scan with a
    # lambda per bar. _t_ms parses an ISO anchor string with strptime,
    # so parse it once, not once per bar.
    anchor_ms = _t_ms(line["anchor"]["t"])
    ms = [b[0] if isinstance(b[0], (int, float)) else _t_ms(b[0])
          for b in bars]
    j = bisect.bisect_left(ms, anchor_ms)
    cands = [k for k in (j - 1, j) if 0 <= k < len(ms)]
    i0 = min(cands, key=lambda k: abs(ms[k] - anchor_ms))
    last_i = len(bars) - 1
    price_now = p0 + slope * (last_i - i0)
    close = (lambda b: b[4] if len(b) > 2 else b[1])
    if last_close is None:
        last_close = close(bars[-1])
    if ((kind == "support" and price_now > last_close) or
            (kind == "resistance" and price_now < last_close)):
        return False
    tol = WRONG_TOL_ATR * atr

    def wrong_side(i):
        c, lp = close(bars[i]), p0 + slope * (i - i0)
        return ((kind == "support" and c < lp - tol) or
                (kind == "resistance" and c > lp + tol))

    # Rule (3) first: any wrong-side close in the last RECENT_BARS
    # bars rejects, and it is only a 6-bar scan.
    for i in range(max(i0, last_i - RECENT_BARS + 1), last_i + 1):
        if wrong_side(i):
            return False
    # Rules (2) and (4): both reject conditions are monotone — once
    # CONSEC_LIMIT in a row or TOTAL_CAP + 1 wrong closes have been
    # seen, the verdict is False whatever the rest of the scan shows,
    # so exit early instead of scanning to the last bar. Identical
    # verdict to the full scan, much cheaper in the replay loop.
    wrong, consec = 0, 0
    for i in range(i0, last_i + 1):
        if wrong_side(i):
            wrong += 1
            consec += 1
            if consec >= CONSEC_LIMIT or wrong > TOTAL_CAP:
                return False
        else:
            consec = 0
    return True


def sloped_lines(bars, pivs, atr_v, last_close):
    """Sloped trendlines from pivot pairs of the same kind. A candidate
    line through two pivots needs >= SLOPE_MIN_SPAN candles of span, a
    sane slope (|slope| <= SLOPE_MAX_ATR per candle), and >=
    SLOPE_MIN_TOUCHES same-kind pivots within SLOPE_TOUCH_TOL_ATR of the
    line. Scored like levels (diminishing touches + recency + unbroken),
    then multiplied by the distance factor at priceNow. Returns ALL
    candidates sorted by effective score desc (the top-2 cut happens in
    rank_sloped, after the comparative layer and hysteresis)."""
    if not pivs or atr_v is None or atr_v <= 0:
        return []
    tol = SLOPE_TOUCH_TOL_ATR * atr_v
    last_i = len(bars) - 1
    cands = []
    for kind, want in (("low", "support"), ("high", "resistance")):
        ps = [p for p in pivs if p[2] == kind]
        for a in range(len(ps)):
            for b in range(a + 1, len(ps)):
                i0, p0 = ps[a][0], ps[a][1]
                i1, p1 = ps[b][0], ps[b][1]
                if i1 - i0 < SLOPE_MIN_SPAN:
                    continue
                slope = (p1 - p0) / (i1 - i0)
                if abs(slope) > SLOPE_MAX_ATR * atr_v:
                    continue
                # Touches: same-kind pivots within tol of the line.
                touch_idx = []
                for (i, p, _) in ps:
                    line_p = p0 + slope * (i - i0)
                    if abs(p - line_p) <= tol:
                        touch_idx.append(i)
                if len(touch_idx) < SLOPE_MIN_TOUCHES:
                    continue
                # Rule A (fix 2): a trendline must BOUND the price, not
                # cut through it. Validate as the native kind; if
                # invalid, try the opposite kind under the same four
                # checks — a broken line flips only if it is a valid
                # bound of the other kind — otherwise drop it. This
                # REPLACES the fix-1 allowance (max(2, 2% of bars)) and
                # the 0.25 ATR flip buffer, which let 4h 60,177.21
                # escape as a flipped resistance with 148 wrong-side
                # closes. sloped_line_valid finds the first anchor bar
                # from the anchor timestamp; here that is i0.
                probe = {"kind": want, "slope": slope,
                         "anchor": {"t": iso_ms(bars[i0][0]), "price": p0}}
                if sloped_line_valid(probe, bars, atr_v, last_close,
                                     kind=want):
                    out_kind, broken = want, False
                else:
                    opp = ("resistance" if want == "support"
                           else "support")
                    if sloped_line_valid(probe, bars, atr_v, last_close,
                                         kind=opp):
                        out_kind, broken = opp, True
                    else:
                        continue
                price_now = p0 + slope * (last_i - i0)
                age = last_i - touch_idx[-1]
                raw = (TOUCH_WEIGHT * _harmonic(len(touch_idx))
                       + 0.5 ** (age / RECENCY_HALF_LIFE)
                       + (0.0 if broken else UNBROKEN_BONUS))
                dist_atr = abs(price_now - last_close) / atr_v
                eff = raw * 0.5 ** (dist_atr / DIST_HALF_LIFE_ATR)
                cands.append({
                    "kind": out_kind,
                    "slope": round(slope, 4),
                    "anchor": {"t": iso_ms(bars[i0][0]), "price": round(p0, 2)},
                    "touches": len(touch_idx),
                    "score": round(eff, 3),
                    "rawScore": round(raw, 3),
                    "distAtr": round(dist_atr, 2),
                    "priceNow": round(price_now, 2),
                    "broken": broken,
                    "held": False,
                })
    # Collapse identical lines: different anchor pairs on the same
    # geometric line are the SAME line, not competing candidates. (The
    # comparative layer in rank_sloped handles near-duplicates; this
    # only removes exact duplicates.)
    cands.sort(key=lambda c: -c["score"])
    uniq = []
    seen_keys = set()
    for c in cands:
        key = (c["kind"], round(c["slope"], 4), round(c["priceNow"], 2))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        uniq.append(c)
    return uniq


def iso_ms(t_ms):
    return dt.datetime.fromtimestamp(t_ms / 1000, dt.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _extreme_for_side(all_cands, kind, atr_v, existing):
    """The range-extreme candidate for one side: the lowest-priced
    support candidate (or highest-priced resistance candidate) that is
    not already displayed and not within 1 ATR of a displayed level
    (the comparative layer's zone width — a line that close is the same
    zone, not a second line). Returns a COPY flagged extreme=True, or
    None when no candidate qualifies. The caller exempts it from the
    2-touch minimum and the 8-ATR display cutoff."""
    ordered = sorted((c for c in all_cands if c["kind"] == kind),
                     key=lambda c: c["price"] if kind == "support"
                     else -c["price"])
    shown = {(l["kind"], l["price"]) for l in existing}
    for c in ordered:
        if (c["kind"], c["price"]) in shown:
            continue
        if any(abs(c["price"] - l["price"]) <= COMPARATIVE_MIN_SEP_ATR * atr_v
               for l in existing):
            continue
        ext = dict(c)
        ext["extreme"] = True
        return ext
    return None


def guarantee_sides(levels, all_cands, atr_v):
    """Fix 4: guarantee at least one level on each side of the price
    when one exists in the data. A side left empty by the ranking is
    filled with the range extreme for that side (exempt from the
    2-touch minimum and from the 8-ATR display cutoff, flagged
    "extreme": true so Stage 4 can fade/label it). A side with no
    qualifying candidate at all is flagged missing. Returns
    (levels, missing_support, missing_resistance). The extreme is an
    EXTRA slot beyond the top-3 cap (at most one per timeframe)."""
    out = list(levels)
    has_sup = any(l["kind"] == "support" for l in out)
    has_res = any(l["kind"] == "resistance" for l in out)
    missing_sup = missing_res = False
    if not has_sup:
        ext = _extreme_for_side(all_cands, "support", atr_v, out)
        if ext is None:
            missing_sup = True
        else:
            out.append(ext)
    if not has_res:
        ext = _extreme_for_side(all_cands, "resistance", atr_v, out)
        if ext is None:
            missing_res = True
        else:
            out.append(ext)
    return out, missing_sup, missing_res


def _compute_tf_full(bars, prev=None):
    """Levels + sloped for one timeframe's bars, plus the pre-cutoff
    distance measurement. prev is the previous run's timeframe dict
    (for hysteresis) or None. Returns (tf_dict_or_None, precut_info):
    the tf dict is the DISPLAYED set (ranking gates + side guarantee),
    while precut_info is {"max_dist", "worst_price"} for the farthest
    top-3 level BEFORE the 8-ATR display cutoff — the replay measures
    trigger B on that, because measuring the displayed set made the
    trigger un-fireable by construction (max <= 8 < 10)."""
    if len(bars) < ATR_PERIOD + 2 * PIVOT_K + 2:
        return None, None
    a = atr(bars)
    if a is None or a <= 0:
        return None, None
    last_close = bars[-1][4]
    pivs = pivots(bars)
    prev_levels = prev["levels"] if prev else None
    prev_sloped = prev["sloped"] if prev else None
    cands = cluster_levels(bars, pivs, a, last_close)
    levels = rank_levels(cands, prev_levels, a)
    levels, missing_sup, missing_res = guarantee_sides(levels, cands, a)
    sloped = rank_sloped(sloped_lines(bars, pivs, a, last_close),
                         prev_sloped, a)
    tf = {
        "asOf": iso_ms(bars[-1][0]),
        "lastClose": round(last_close, 2),
        "atr": round(a, 2),
        "levels": levels,
        "sloped": sloped,
        "missingSupport": missing_sup,
        "missingResistance": missing_res,
    }
    precut = rank_levels([dict(c) for c in cands], prev_levels, a,
                         cutoff_atr=None)
    precut_max = 0.0
    precut_worst = None
    for lv in precut:
        if lv["distAtr"] > precut_max:
            precut_max = lv["distAtr"]
            precut_worst = lv["price"]
    return tf, {"max_dist": precut_max, "worst_price": precut_worst}


def compute_tf(bars, prev=None):
    """Levels + sloped for one timeframe's bars. prev is the previous
    run's timeframe dict (for hysteresis) or None. Returns the timeframe
    dict for ta-lines.json, or None if there is too little data."""
    tf, _ = _compute_tf_full(bars, prev)
    return tf


def build(hourly, daily_bars, now, prev=None, daily_max_age_days=None):
    """Build the full schema-1 document from 1h bars + daily bars.
    prev is the previous run's document (for hysteresis) or None.
    daily_max_age_days (fix 3): when set, fail closed if the newest
    daily bar is older than that many days — the 1d levels must be
    measured against current price. The live job passes 2; the offline
    tests leave it unset (their fixtures end when they end)."""
    if daily_max_age_days is not None and daily_bars:
        newest = dt.datetime.fromtimestamp(
            daily_bars[-1][0] / 1000, dt.timezone.utc)
        age_days = (now - newest).total_seconds() / 86400.0
        if age_days > daily_max_age_days:
            raise ValueError(
                f"1d data stale: newest daily bar {newest.date()} is "
                f"{age_days:.1f} days old (max {daily_max_age_days})")
    h4 = agg4h(hourly)
    tfs = {}
    for name, bars in (("1h", hourly), ("4h", h4), ("1d", daily_bars)):
        prev_tf = prev["timeframes"].get(name) if prev else None
        tf = compute_tf(bars, prev_tf)
        if tf is not None:
            tfs[name] = tf
    doc = {
        "v": 1,
        "kind": "ta-lines",
        "asOf": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "timeframes": tfs,
    }
    return doc


def validate(doc):
    """Fail closed: schema-1 shape, caps, finite positive prices."""
    if doc.get("v") != 1 or doc.get("kind") != "ta-lines":
        raise ValueError("bad header")
    tfs = doc.get("timeframes")
    if not isinstance(tfs, dict) or not tfs:
        raise ValueError("no timeframes")
    # Fix 5: a partial document must not validate. If Coinbase returns
    # [] or too few 1h bars, compute_tf drops 1h and 4h, 1d still builds,
    # and without this check main() would write a fresh-asOf partial
    # file. All three timeframes are required, every run.
    needed = ("1h", "4h", "1d")
    missing = [n for n in needed if n not in tfs]
    if missing:
        raise ValueError("missing timeframe(s): " + ", ".join(missing))
    for name, tf in tfs.items():
        for k in ("asOf", "lastClose", "atr", "levels", "sloped"):
            if k not in tf:
                raise ValueError(f"{name}: missing {k}")
        # Cap: at most MAX_LEVELS regular levels, plus at most one
        # range-extreme slot (fix 4) beyond the cap.
        n_ext = sum(1 for lv in tf["levels"] if lv.get("extreme"))
        if len(tf["levels"]) - n_ext > MAX_LEVELS:
            raise ValueError(f"{name}: too many levels")
        if n_ext > 1:
            raise ValueError(f"{name}: too many extreme levels")
        if len(tf["sloped"]) > MAX_SLOPED:
            raise ValueError(f"{name}: too many sloped lines")
        for lv in tf["levels"]:
            if not (math.isfinite(lv["price"]) and lv["price"] > 0):
                raise ValueError(f"{name}: bad level price")
            if lv["kind"] not in ("support", "resistance"):
                raise ValueError(f"{name}: bad level kind")
            if not math.isfinite(lv["score"]):
                raise ValueError(f"{name}: bad level score")
        for sl in tf["sloped"]:
            if not (math.isfinite(sl["priceNow"]) and sl["priceNow"] > 0):
                raise ValueError(f"{name}: bad sloped priceNow")
            if not math.isfinite(sl["slope"]):
                raise ValueError(f"{name}: bad slope")
    json.dumps(doc, allow_nan=False)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--live", action="store_true",
                    help="fetch real Coinbase 1h candles (default: fixture)")
    ap.add_argument("--fixture", default=None,
                    help="1h fixture JSON (Coinbase rows) instead of fetch")
    ap.add_argument("--daily", default=None,
                    help="btc-daily.json path (default: repo assets/data) "
                    "— closes only, offline fallback")
    ap.add_argument("--daily-fixture", default=None,
                    help="real daily OHLC fixture JSON (Coinbase rows) "
                    "instead of the closes-only file")
    ap.add_argument("--out", default="ta-lines.json",
                    help="output path (default ta-lines.json)")
    ap.add_argument("--hours", type=int, default=720,
                    help="1h window in hours (default 720 = 30 days)")
    ap.add_argument("--daily-days", type=int, default=730,
                    help="daily window in days (default 730)")
    ap.add_argument("--now", default=None,
                    help="override now (ISO UTC) for replay/determinism")
    ap.add_argument("--prev", default=None,
                    help="previous ta-lines.json (for hysteresis); the "
                    "workflow reads it from the data branch before "
                    "computing the new one")
    args = ap.parse_args(argv)
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)
    daily_path = args.daily or os.path.join(repo, "assets", "data",
                                            "btc-daily.json")
    now = (dt.datetime.strptime(args.now, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=dt.timezone.utc) if args.now else
        dt.datetime.now(dt.timezone.utc))
    try:
        prev = None
        if args.prev:
            with open(args.prev) as f:
                prev = json.load(f)
            validate(prev)
        if args.fixture:
            with open(args.fixture) as f:
                fx = json.load(f)
            rows = fx["candles"] if isinstance(fx, dict) else fx
            hourly = []
            for r in rows:
                t, lo, hi, o, c = r[0], r[1], r[2], r[3], r[4]
                hourly.append((int(t) * 1000, float(o), float(hi),
                               float(lo), float(c)))
            hourly.sort(key=lambda b: b[0])
            hourly = hourly[-args.hours:]
        elif args.live:
            hourly = fetch_1h(hours=args.hours)
            # Fix 2/3: real daily OHLC (incl. the forming day, so the 1d
            # lastClose tracks the live price); fail closed below if the
            # newest daily bar is older than DAILY_MAX_AGE_DAYS.
            daily_bars = fetch_daily(days=args.daily_days)
            daily_max_age = DAILY_MAX_AGE_DAYS
        else:
            ap.error("need --live or --fixture")
        if not args.live:
            daily_max_age = None
            if args.daily_fixture:
                with open(args.daily_fixture) as f:
                    fx = json.load(f)
                rows = fx["candles"] if isinstance(fx, dict) else fx
                daily_bars = daily_from_ohlc_rows(rows)[-args.daily_days:]
            else:
                daily_bars = daily_from_closes(daily_path,
                                               days=args.daily_days)
    except SystemExit:
        raise
    except Exception as e:
        print(f"::error::ta-lines fetch failed: {type(e).__name__}: {e}")
        return 1
    try:
        doc = build(hourly, daily_bars, now, prev,
                    daily_max_age_days=daily_max_age)
    except Exception as e:
        print(f"::error::ta-lines build failed: {e}")
        return 1
    try:
        validate(doc)
    except Exception as e:
        print(f"::error::ta-lines validation failed: {e}")
        return 1
    tmp = args.out + ".tmp"
    with open(tmp, "w") as f:
        json.dump(doc, f, indent=1, allow_nan=False)
        f.write("\n")
    os.replace(tmp, args.out)
    for name, tf in doc["timeframes"].items():
        print(f"{name}: lastClose {tf['lastClose']} atr {tf['atr']} "
              f"levels {len(tf['levels'])} sloped {len(tf['sloped'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
