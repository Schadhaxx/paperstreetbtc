#!/usr/bin/env python3
"""Stage 3a minimal Smart Trendlines for ALL Desk assets (skunkworks TA 2.0).

Faithful to TA-BUILD-DRAFT.md Stage 3a, generalised from
~/workspace/desk-ta-mockup/ta_lines_gold.py (which computed the same
algorithm for gold alone):
- pivots: fractal swing highs/lows, lookback k=3
- cluster pivot prices with ATR-based tolerance (1.0 ATR)
- score: touches (diminishing 0.7^j), recency in CANDLES, broken-on-close
  counted with flip (0.85^crossed penalty)
- top 3 horizontal levels + up to 2 sloped lines (3+ touches, sane slope)
- ATR(14) Wilder

Reads every Desk weekly file (16 stocks + 8 indicators) from the repo's
assets/data/ and writes assets/data/ta-lines-desk.json, keyed by symbol,
as a locally generated fixture. There is NO workflow file: this is a
test-branch prototype, the fixture is committed as generated.

Gold is the regression check: it MUST reproduce the site-file run
exactly (ATR $232.76, last close $3,644.60, levels $5,510.15 /
$4,836.35 / $4,027.70, sloped resistance -$27.71/wk, 3 touches off the
Jan 2026 high). The gold mockup artifact used a longer Yahoo series
and different numbers; the branch uses the site's 47-week file.

usage: python3 tools/ta_lines_desk.py   (from the repo root)
"""
import json
import os
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(R, 'assets', 'data')
OUT = os.path.join(DATA, 'ta-lines-desk.json')

K = 3               # pivot lookback
ATR_PERIOD = 14
CLUSTER_TOL_ATR = 1.0   # merge pivots within ~1 ATR (per the draft)
SLOPE_TOL_ATR = 0.5     # a pivot "touches" a sloped line within 0.5 ATR

# symbol -> (weekly file, display name)
SYMBOLS = [
    ('TSLA', 'stock-weekly-TSLA.json', 'Tesla'),
    ('PLTR', 'stock-weekly-PLTR.json', 'Palantir'),
    ('MSTR', 'stock-weekly-MSTR.json', 'Strategy'),
    ('IBIT', 'stock-weekly-IBIT.json', 'iShares Bitcoin ETF'),
    ('MU', 'stock-weekly-MU.json', 'Micron'),
    ('META', 'stock-weekly-META.json', 'Meta'),
    ('SPCX', 'stock-weekly-SPCX.json', 'SPDR S&P 500 ETF'),
    ('BRK.B', 'stock-weekly-BRK.B.json', 'Berkshire Hathaway'),
    ('AAPL', 'stock-weekly-AAPL.json', 'Apple'),
    ('AMZN', 'stock-weekly-AMZN.json', 'Amazon'),
    ('MSFT', 'stock-weekly-MSFT.json', 'Microsoft'),
    ('NFLX', 'stock-weekly-NFLX.json', 'Netflix'),
    ('SPOT', 'stock-weekly-SPOT.json', 'Spotify'),
    ('XYZ', 'stock-weekly-XYZ.json', 'Block'),
    ('GOOGL', 'stock-weekly-GOOGL.json', 'Alphabet'),
    ('NVDA', 'stock-weekly-NVDA.json', 'Nvidia'),
    ('GOLD', 'gold-weekly.json', 'Gold'),
    ('WTI', 'wti-weekly.json', 'WTI Crude'),
    ('US10Y', 'us10y-weekly.json', '10-Year Treasury'),
    ('VIX', 'vix-weekly.json', 'VIX'),
    ('DIA', 'dia-weekly.json', 'Dow Jones ETF'),
    ('QQQ', 'qqq-weekly.json', 'Nasdaq 100 ETF'),
    ('USDCAD', 'usdcad-weekly.json', 'CAD/USD'),
    ('DXY', 'dxy-weekly.json', 'US Dollar Index'),
]


def compute(weeks):
    """Stage 3a minimal on one weekly candle series. Returns the per-symbol
    record (levels + sloped lines), or None when there are too few weeks
    to form a pivot."""
    candles = [
        {'monday': w['monday'], 'open': w['open'], 'high': w['high'],
         'low': w['low'], 'close': w['close']}
        for w in weeks
    ]
    n = len(candles)
    closes = [c['close'] for c in candles]
    highs = [c['high'] for c in candles]
    lows = [c['low'] for c in candles]

    # --- ATR(14), Wilder ---
    trs = []
    for i in range(n):
        if i == 0:
            trs.append(highs[i] - lows[i])
        else:
            trs.append(max(highs[i] - lows[i],
                           abs(highs[i] - closes[i - 1]),
                           abs(lows[i] - closes[i - 1])))
    atr = sum(trs[:ATR_PERIOD]) / ATR_PERIOD
    for tr in trs[ATR_PERIOD:]:
        atr = (atr * (ATR_PERIOD - 1) + tr) / ATR_PERIOD
    last_close = closes[-1]

    # --- Pivots (fractal, k=3) ---
    swing_highs, swing_lows = [], []  # (index, price)
    for i in range(K, n - K):
        if highs[i] == max(highs[i - K:i + K + 1]):
            swing_highs.append((i, highs[i]))
        if lows[i] == min(lows[i - K:i + K + 1]):
            swing_lows.append((i, lows[i]))

    # --- Cluster pivots into horizontal levels ---
    def cluster(pivots):
        pts = sorted(pivots, key=lambda p: p[1])
        clusters = []
        for idx, price in pts:
            placed = False
            for cl in clusters:
                if abs(price - cl['price']) <= CLUSTER_TOL_ATR * atr:
                    cl['members'].append((idx, price))
                    cl['price'] = sum(p for _, p in cl['members']) / len(cl['members'])
                    placed = True
                    break
            if not placed:
                clusters.append({'price': price, 'members': [(idx, price)]})
        return clusters

    def score_cluster(cl):
        members = sorted(cl['members'])
        touches = len(members)
        touch_score = sum(0.7 ** j for j in range(touches))
        last_touch = members[-1][0]
        age = (n - 1) - last_touch
        recency = 1.0 / (1.0 + age / 15.0)
        first_idx = members[0][0]
        crossed = sum(1 for i in range(first_idx + 1, n)
                      if (closes[i - 1] - cl['price']) * (closes[i] - cl['price']) < 0)
        score = round(touch_score * (0.7 + 0.3 * recency) * (0.85 ** crossed), 2)
        return {
            'price': round(cl['price'], 2),
            'type': 'support' if cl['price'] < last_close else 'resistance',
            'touches': touches,
            'lastTouch': last_touch,
            'ageCandles': age,
            'brokenOnClose': crossed,
            'flipped': crossed > 0,
            'score': score,
        }

    levels = [score_cluster(cl) for cl in cluster(swing_highs + swing_lows)]
    levels.sort(key=lambda l: l['score'], reverse=True)
    levels = levels[:3]

    # --- Sloped lines: pivot pairs with 3+ touches, sane slope ---
    def sloped_lines(pivots, kind):
        out = []
        pts = sorted(pivots)
        for a in range(len(pts)):
            for b in range(a + 3, len(pts)):  # at least 3 candles apart
                i0, p0 = pts[a]
                i1, p1 = pts[b]
                slope = (p1 - p0) / (i1 - i0)  # $ per week
                if abs(slope) > 1.5 * atr:     # sane slope: < 1.5 ATR per week
                    continue
                touched = []
                for idx, price in pts:
                    line_price = p0 + slope * (idx - i0)
                    if abs(price - line_price) <= SLOPE_TOL_ATR * atr:
                        touched.append(idx)
                if len(touched) >= 3:
                    end_price = p0 + slope * ((n - 1) - i0)
                    if min(lows) - atr <= end_price <= max(highs) + atr:
                        out.append({
                            'type': kind,
                            'slope': round(slope, 2),
                            'anchor': [i0, p0],
                            'anchor2': [i1, p1],
                            'touches': len(touched),
                            'touchIdx': touched,
                            'endPrice': round(end_price, 2),
                        })
        out.sort(key=lambda l: (-l['touches'], l['anchor'][0]))
        kept = []
        for ln in out:
            if any(abs(ln['slope'] - k['slope']) < 0.3 * atr and
                   abs(ln['anchor'][1] - k['anchor'][1]) < 0.5 * atr for k in kept):
                continue
            kept.append(ln)
        return kept[:2]

    sloped = sloped_lines(swing_highs, 'resistance') + sloped_lines(swing_lows, 'support')
    sloped.sort(key=lambda l: -l['touches'])
    sloped = sloped[:2]

    return {
        'lastClose': last_close,
        'atr': round(atr, 2),
        'weeks': n,
        'levels': levels,
        'sloped': sloped,
    }


def main():
    out = {}
    for sym, fname, name in SYMBOLS:
        path = os.path.join(DATA, fname)
        with open(path) as f:
            d = json.load(f)
        weeks = d['weeks']
        if len(weeks) <= 2 * K:
            print(f'{sym}: SKIP — only {len(weeks)} weeks, no pivots possible')
            out[sym] = {'symbol': sym, 'name': name, 'asOf': d.get('asOf'),
                        'lastClose': weeks[-1]['close'] if weeks else None,
                        'atr': None, 'weeks': len(weeks), 'levels': [], 'sloped': []}
            continue
        rec = compute(weeks)
        rec['symbol'] = sym
        rec['name'] = name
        rec['asOf'] = d.get('asOf')
        out[sym] = rec
        lv = ' / '.join(f"${l['price']} ({l['type'][:3]}, {l['touches']}t)" for l in rec['levels'])
        sl = ' / '.join(f"{s['type'][:3]} {s['slope']:+}/wk {s['touches']}t" for s in rec['sloped'])
        print(f"{sym}: weeks={rec['weeks']} atr={rec['atr']} last={rec['lastClose']} "
              f"levels=[{lv}] sloped=[{sl}]")
    with open(OUT, 'w') as f:
        json.dump(out, f, indent=1)
    print('wrote', OUT, f"({len(out)} symbols)")


if __name__ == '__main__':
    main()
