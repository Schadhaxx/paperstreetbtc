#!/usr/bin/env python3
"""TA Drawing Fixes Job 12 checks (22 Nov 2026): scan #2 axis/comparison/
labelling leftovers — the LAST of the original 12.

1. 10Y/Max comparisons flattened by the BTC-only axis (Max axis read
   +179,999,900%). Fix: the chart auto-switches to log scale in compare
   mode when the rebased span is extreme (hi/lo > 50 — Max ~1.8M,
   10Y ~180, nothing else exceeds it), and the scale buttons follow
   (the Linear button is disabled while the data forces log, since a
   click there would be overridden on the next draw). The user's LOG
   toggle is untouched.
2. YTD MSTR -54% below the axis bottom. Fix: the Line axis guarantees
   half a tick step of headroom above the highest and below the lowest
   drawn value, so an extreme never sits on the plot edge.
3. 1D peak clipped at the top. Fix: same half-tick headroom rule — the
   peak now sits a full half-step below the top tick instead of
   flattening against the plot top.
4. 5Y x labels duplicate '2024'. Fix: consecutive identical year labels
   are blanked (gridline stays), so each year appears once.
5. SMA 20 vs EMA 20 inconsistent on 1W Candles. Job 8 found the VALUES
   agree — the visible inconsistency was the gating asymmetry. Fix:
   SMA 20/50 + EMA 50 ungated on 1W (Job 2's pre-warm already gives
   them the data), so they draw there now.
Job 8 leftovers, same family: 1W Line Bollinger upper band poked above
the plot top, and the 200s sat below the 1W daily candle range and drew
nothing. Fix: the axis now widens to include the drawn overlays
(Bollinger + MA extremes, bounded to one span per side, like the
trendlines in Job 1), so they draw instead of being clipped.

Harness: Job 11's (localhost, frozen clock 2026-10-30 20:00 UTC, real daily
closes in the Coinbase stub, all TA overlays on). The 900-granularity stub
gains a sharp single-candle spike at 10:00 UTC (close ~83,900, just below
the 84,000 top tick) for the 1D peak test.
"""
import json, math, os, sys, threading, functools, http.server, socketserver, urllib.parse, datetime as dt
from pathlib import Path

R = Path(__file__).resolve().parents[1]  # the checkout under test

def _find_chrome():
    for p in ['/usr/bin/google-chrome', '/usr/bin/chromium']:
        if os.path.exists(p):
            return p
    cache = Path.home() / '.cache' / 'ms-playwright'
    for pat in ('chromium-*/chrome-linux*/chrome',
                'chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell'):
        hits = sorted(cache.glob(pat))
        if hits:
            return str(hits[0])
    return None

CHROME = os.environ.get('CHROME_PATH') or _find_chrome()
FIXED = dt.datetime(2026, 10, 30, 20, tzinfo=dt.timezone.utc)
PEAK_T = FIXED - dt.timedelta(hours=10)  # 10:00 UTC, the sharp 1D peak
fails, n = [], 0

def chk(name, ok, detail=''):
    global n
    n += 1
    print('ok' if ok else 'FAIL', name, '' if ok else str(detail)[:300], flush=True)
    if not ok:
        fails.append(name)

def base_price(t_ms):
    t = t_ms / 1000.0
    return 77500 + 900 * math.sin(t / 18000.0) + 350 * math.cos(t / 10800.0)

DATA_DAILY = None
def load_data_daily():
    global DATA_DAILY
    if DATA_DAILY is None:
        d = json.load(open(R / 'assets' / 'data' / 'btc-daily.json'))['d']
        DATA_DAILY = [(int(dt.datetime.fromisoformat(p[0]).replace(tzinfo=dt.timezone.utc).timestamp()), p[1]) for p in d]
    return DATA_DAILY

def coinbase(route):
    u = urllib.parse.urlparse(route.request.url); q = urllib.parse.parse_qs(u.query)
    if 'spot' in u.path:
        return route.fulfill(status=200, content_type='application/json', body=json.dumps({'data': {'amount': '77500.00', 'currency': 'USD'}}))
    g = int(q.get('granularity', ['86400'])[0])
    end = int(dt.datetime.fromisoformat(q['end'][0].replace('Z', '+00:00')).timestamp()) if 'end' in q else int(FIXED.timestamp())
    start = int(dt.datetime.fromisoformat(q['start'][0].replace('Z', '+00:00')).timestamp()) if 'start' in q else end - 300 * g
    if g == 86400:
        daily = load_data_daily()
        rows, prev = [], None
        for t, c in daily:
            if start <= t < end:
                o = prev if prev is not None else c
                rows.append([t, min(o, c), max(o, c), o, c, 10])
            prev = c
        rows.sort(key=lambda r: r[0])
        return route.fulfill(status=200, content_type='application/json', body=json.dumps(rows))
    rows, t = [], end - end % g
    while t >= start and len(rows) < 300:
        o = base_price(t * 1000); c = base_price((t + g) * 1000)
        if g == 900 and abs(t - int(PEAK_T.timestamp())) < g:
            # Sharp single-candle spike: close ~83,900 at 10:00 UTC — just
            # below the 84,000 top tick (the scan's clip condition).
            c = c * 1.0912
        rows.append([t, min(o, c) - 120, max(o, c) + 120, o, c, 10]); t -= g
    route.fulfill(status=200, content_type='application/json', body=json.dumps(rows))

def handler(route):
    url = route.request.url
    if 'ta-lines.json' in url:
        return route.fulfill(status=200, content_type='application/json', body=json.dumps(FIXTURE))
    if 'coinbase.com' in url: return coinbase(route)
    if 'paperstreet-quotes' in url:
        return route.fulfill(status=200, content_type='application/json', body=json.dumps({'btc': {'usd': 77500, 'chg24h': 1.2}}))
    if 'coingecko.com' in url:
        if 'simple/price' in url:
            return route.fulfill(status=200, content_type='application/json', body=json.dumps({'bitcoin': {'usd': 77500, 'usd_24h_change': 1.2}}))
        return route.fulfill(status=200, content_type='application/json', body=json.dumps({'prices': [[int(FIXED.timestamp() * 1000) - i * 900000, 77500 + i] for i in range(96, 0, -1)]}))
    if 'raw.githubusercontent.com' in url or 'history.json' in url:
        return route.abort()
    if not url.startswith(U): return route.abort()
    route.continue_()

def lvl(price, kind, brk=False, ext=False):
    return {'price': price, 'kind': kind, 'score': 5.0, 'rawScore': 6.0, 'distAtr': 1.0,
            'touches': 5, 'lastTouch': FIXED.strftime('%Y-%m-%dT%H:%M:%SZ'), 'ageCandles': 3, 'broken': brk, 'held': False, 'extreme': ext}

def slp(kind, slope, anchor, anchor_price):
    return {'kind': kind, 'slope': slope, 'anchor': {'t': anchor.strftime('%Y-%m-%dT%H:%M:%SZ'), 'price': anchor_price},
            'touches': 5, 'score': 5.0, 'rawScore': 6.0, 'distAtr': 1.0, 'priceNow': anchor_price,
            'broken': False, 'held': False}

def tf(asOf, levels, sloped):
    return {'asOf': asOf.strftime('%Y-%m-%dT%H:%M:%SZ'), 'atr': 700, 'lastClose': 77500, 'levels': levels, 'sloped': sloped,
            'missingSupport': False, 'missingResistance': False}

def fixture():
    h1, h4, d1 = FIXED - dt.timedelta(minutes=10), FIXED - dt.timedelta(hours=1), FIXED - dt.timedelta(hours=5)
    t1h = tf(h1, [lvl(79500, 'resistance'), lvl(76000, 'support')], [slp('support', 30, FIXED - dt.timedelta(hours=12), 75500)])
    t4h = tf(h4, [lvl(79500, 'resistance')], [slp('support', 120, FIXED - dt.timedelta(hours=20), 74000)])
    t1d = tf(d1, [lvl(81000, 'resistance'), lvl(75000, 'support')], [slp('support', -30, dt.datetime(2026, 10, 20, tzinfo=dt.timezone.utc), 76000)])
    return {'v': 1, 'kind': 'ta-lines', 'asOf': FIXED.strftime('%Y-%m-%dT%H:%M:%SZ'), 'timeframes': {'1h': t1h, '4h': t4h, '1d': t1d}}

FIXTURE = fixture()

LAYOUT_JS = """() => {
  const L = window.__BTC_LINE_LAYOUT || null;
  const g = window.__BCTA && window.__BCTA.geom ? window.__BCTA.geom() : null;
  const d = window.__TA_DEBUG ? window.__TA_DEBUG() : null;
  const st = window.__BCTA ? window.__BCTA.state() : null;
  const linBtn = document.querySelector('#bcSc button[data-s="lin"]');
  return {layout: L ? {kind: L.kind, yTicks: L.yTicks, xLabels: L.xLabels, padT: L.padT, plotH: L.plotH, log: L.log, sx: L.sx, hasLive: L.hasLive} : null,
          geom: g ? {kind: g.kind, padT: g.pad ? g.pad.t : null, plotH: g.plotH} : null,
          probe: d ? {kind: d.kind, n: d.n, warm: d.warm, closes: d.closes, fvBB: d.firstValid.bb, fvRSI: d.firstValid.rsi, fv: d.firstValidMas, last: d.last} : null,
          state: st ? {rng: st.rng, CT: st.CT, RGCT: st.RGCT, RGGRAN: st.RGGRAN} : null,
          linDisabled: linBtn ? linBtn.disabled : null};
}"""

SPAN_JS = """([rgb, tol]) => {
  const cv = document.querySelector('#bcC');
  if (!cv) return {error: 'no canvas'};
  const ctx = cv.getContext('2d');
  const w = cv.width, h = cv.height;
  const dpr = w / cv.clientWidth;
  const d = ctx.getImageData(0, 0, w, h).data;
  let c = 0, minY = Infinity, maxY = -Infinity, minX = Infinity, maxX = -Infinity;
  for (let i = 0; i < d.length; i += 4) {
    if (Math.abs(d[i] - rgb[0]) <= tol && Math.abs(d[i+1] - rgb[1]) <= tol && Math.abs(d[i+2] - rgb[2]) <= tol) {
      c++;
      const px = (i / 4) % w, py = Math.floor((i / 4) / w);
      if (py < minY) minY = py; if (py > maxY) maxY = py;
      if (px < minX) minX = px; if (px > maxX) maxX = px;
    }
  }
  if (!c) return {count: 0};
  return {count: c, minY: +(minY / dpr).toFixed(1), maxY: +(maxY / dpr).toFixed(1),
          minX: +(minX / dpr).toFixed(1), maxX: +(maxX / dpr).toFixed(1)};
}"""

def span(pg, rgb, tol=10):
    return pg.evaluate(SPAN_JS, [list(rgb), tol])

def layout(pg):
    return pg.evaluate(LAYOUT_JS)

def go_range(pg, r):
    pg.click('#bcRgs button[data-r="%s"]' % r); pg.wait_for_timeout(1500)

def pick_line(pg):
    pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
    pg.click('.ta-menu [data-ta-pick="line"]'); pg.wait_for_timeout(1200)

def pick_candles(pg):
    pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
    pg.click('.ta-menu [data-ta-pick="candles"]'); pg.wait_for_timeout(1200)

def pick_size(pg, size):
    pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
    pg.click('.ta-menu [data-ta-size="%s"]' % size); pg.wait_for_timeout(1200)

BTC = (34, 211, 238); SPX = (196, 181, 253); GLD = (250, 204, 21); MSTR = (249, 115, 22)
BB = (167, 139, 250); SMA20 = (244, 114, 182); SMA50 = (251, 191, 36); SMA200 = (20, 184, 166)
EMA20 = (56, 189, 248); EMA50 = (251, 146, 60); EMA200 = (163, 230, 53)

def main():
    global U
    srv = None
    if len(sys.argv) > 1:
        base = sys.argv[1].rstrip('/'); U = base + '/'
    else:
        class Q(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a): pass
        srv = socketserver.ThreadingTCPServer(('127.0.0.1', 0), functools.partial(Q, directory=str(R))); srv.daemon_threads = True
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        U = 'http://127.0.0.1:%d/' % srv.server_address[1]
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        launch = {'executable_path': CHROME} if CHROME else {}
        b = p.chromium.launch(**launch)
        pg = b.new_page(viewport={'width': 1440, 'height': 900})
        pg.clock.set_fixed_time(FIXED)
        pg.route('**/*', handler)
        pg.add_init_script("try{localStorage.setItem('ps-ta-v1', JSON.stringify({tl:true,bb:true,ma:true,maSet:{sma20:true,sma50:true,sma200:true,ema20:true,ema50:true,ema200:true},rsi:true,rsiCol:false,last1DSize:'1h'}));}catch(e){}")
        pg.goto(U + 'clock/', wait_until='domcontentloaded')
        pg.wait_for_selector('#bcC', timeout=10000)
        pg.wait_for_timeout(3000)

        # ---- Item 4: 5Y x labels — each year once ----
        print('--- Item 4: 5Y x labels ---')
        go_range(pg, '5Y')
        L = layout(pg)
        xl = (L['layout'] or {}).get('xLabels') or []
        nonempty = [x for x in xl if x]
        chk('5Y: no duplicate year labels', len(set(nonempty)) == len(nonempty), 'xLabels=%s' % xl)
        chk('5Y: every year 2021-2026 still labelled once', sorted(set(nonempty)) == ['2021', '2022', '2023', '2024', '2025', '2026'], 'xLabels=%s' % xl)

        # ---- Item 1: Max + S&P comparison auto-logs ----
        print('--- Item 1: Max + S&P 500 comparison ---')
        go_range(pg, 'Max')
        pg.click('#bcSpx'); pg.wait_for_timeout(2000)
        L = layout(pg)
        s_btc, s_spx = span(pg, BTC), span(pg, SPX)
        chk('Max compare: auto-log on', (L['layout'] or {}).get('log') is True, 'layout=%s' % L['layout'])
        chk('Max compare: S&P reads (tall, not 1-2px)', s_spx.get('count', 0) > 0 and (s_spx.get('maxY', 0) - s_spx.get('minY', 0)) >= 50, 'spx=%s' % s_spx)
        chk('Max compare: BTC still reads full plot', s_btc.get('count', 0) > 0 and (s_btc.get('maxY', 0) - s_btc.get('minY', 0)) >= 400, 'btc=%s' % s_btc)
        chk('Max compare: Linear button disabled (data forces log)', L.get('linDisabled') is True, 'linDisabled=%s' % L.get('linDisabled'))
        pg.click('#bcSpx'); pg.wait_for_timeout(1200)

        # ---- Item 1b: 10Y + S&P comparison auto-logs ----
        print('--- Item 1b: 10Y + S&P 500 comparison ---')
        go_range(pg, '10Y')
        pg.click('#bcSpx'); pg.wait_for_timeout(2000)
        L = layout(pg)
        s_btc, s_spx = span(pg, BTC), span(pg, SPX)
        chk('10Y compare: auto-log on', (L['layout'] or {}).get('log') is True, 'layout=%s' % L['layout'])
        chk('10Y compare: S&P reads (tall, not 8px)', s_spx.get('count', 0) > 0 and (s_spx.get('maxY', 0) - s_spx.get('minY', 0)) >= 50, 'spx=%s' % s_spx)
        pg.click('#bcSpx'); pg.wait_for_timeout(1200)

        # ---- Item 1c: 5Y + S&P does NOT auto-log (span is small) ----
        print('--- Item 1c: 5Y + S&P 500 comparison (control) ---')
        go_range(pg, '5Y')
        pg.click('#bcSpx'); pg.wait_for_timeout(2000)
        L = layout(pg)
        s_spx = span(pg, SPX)
        chk('5Y compare: stays linear', (L['layout'] or {}).get('log') is False, 'layout=%s' % L['layout'])
        chk('5Y compare: S&P reads', s_spx.get('count', 0) > 0 and (s_spx.get('maxY', 0) - s_spx.get('minY', 0)) >= 50, 'spx=%s' % s_spx)
        chk('5Y compare: Linear button enabled', L.get('linDisabled') is False, 'linDisabled=%s' % L.get('linDisabled'))
        pg.click('#bcSpx'); pg.wait_for_timeout(1200)

        # ---- Item 2: YTD + MSTR — the low stays off the bottom ----
        print('--- Item 2: YTD + MSTR comparison ---')
        go_range(pg, 'YTD')
        pg.click('#bcMstr'); pg.wait_for_timeout(2000)
        L = layout(pg)
        yt = (L['layout'] or {}).get('yTicks') or []
        padT, plotH = (L['layout'] or {}).get('padT'), (L['layout'] or {}).get('plotH')
        s_mstr = span(pg, MSTR)
        chk('YTD compare: bottom tick stepped out (40, not 50)', yt and yt[0] == 40, 'yTicks=%s' % yt)
        chk('YTD compare: MSTR low sits clear of the plot bottom', s_mstr.get('count', 0) > 0 and s_mstr.get('maxY', 9999) <= padT + plotH - 39, 'mstr=%s bottom=%s' % (s_mstr, padT + plotH))
        pg.click('#bcMstr'); pg.wait_for_timeout(1200)

        # ---- Item 3: 1D peak — headroom above the spike ----
        print('--- Item 3: 1D peak ---')
        go_range(pg, '1D')
        pick_line(pg)
        pg.wait_for_timeout(2000)
        L = layout(pg)
        yt = (L['layout'] or {}).get('yTicks') or []
        padT, plotH = (L['layout'] or {}).get('padT'), (L['layout'] or {}).get('plotH')
        s_btc = span(pg, BTC)
        closes = (L['probe'] or {}).get('closes') or []
        dmax = max(closes) if closes else None
        chk('1D: top tick stepped out (85000, not 84000)', yt and yt[-1] == 85000, 'yTicks=%s' % yt)
        if dmax is not None and yt:
            lo = min(min(closes), yt[0]); hi = max(dmax, yt[-1])
            y_max = padT + plotH * (1 - (dmax - lo) / (hi - lo))
            chk('1D: peak headroom >= 25px above the top', y_max - padT >= 25, 'Y(dataMax)=%.1f padT=%s dmax=%.0f' % (y_max, padT, dmax))
        else:
            chk('1D: peak headroom >= 25px above the top', False, 'no probe closes')
        chk('1D: curve stays clear of the plot top', s_btc.get('count', 0) > 0 and s_btc.get('minY', 0) >= padT + 20, 'btc=%s padT=%s' % (s_btc, padT))

        # ---- Item 5: 1W SMA 20/50 + EMA 50 draw now (ungated) ----
        print('--- Item 5: 1W SMA 20/50 + EMA 50 ---')
        go_range(pg, '1W')
        pg.wait_for_timeout(2000)
        L = layout(pg)
        padT, plotH = (L['layout'] or {}).get('padT'), (L['layout'] or {}).get('plotH')
        chk('1W Line: SMA 20 draws', span(pg, SMA20).get('count', 0) > 0, 'px=%s' % span(pg, SMA20))
        chk('1W Line: SMA 50 draws', span(pg, SMA50).get('count', 0) > 0, 'px=%s' % span(pg, SMA50))
        chk('1W Line: EMA 50 draws', span(pg, EMA50).get('count', 0) > 0, 'px=%s' % span(pg, EMA50))
        # ---- Job 8 leftover: 1W Line Bollinger stays inside the plot ----
        bb = span(pg, BB)
        chk('1W Line: Bollinger stays inside the plot (no poke above the top)', bb.get('count', 0) > 0 and bb.get('minY', 0) >= padT and bb.get('maxY', 9999) <= padT + plotH, 'bb=%s padT=%s bottom=%s' % (bb, padT, padT + plotH))
        pick_candles(pg)
        pg.wait_for_timeout(2000)
        chk('1W 4H candles: SMA 20 draws', span(pg, SMA20).get('count', 0) > 0, 'px=%s' % span(pg, SMA20))
        chk('1W 4H candles: SMA 50 draws', span(pg, SMA50).get('count', 0) > 0, 'px=%s' % span(pg, SMA50))
        chk('1W 4H candles: EMA 50 draws', span(pg, EMA50).get('count', 0) > 0, 'px=%s' % span(pg, EMA50))
        # ---- Job 8 leftover: 1W daily candles — the 200s draw now ----
        pick_size(pg, 'daily')
        pg.wait_for_timeout(2000)
        chk('1W daily candles: SMA 200 draws (was clipped below the range)', span(pg, SMA200).get('count', 0) > 0, 'px=%s' % span(pg, SMA200))
        chk('1W daily candles: EMA 200 draws (was clipped below the range)', span(pg, EMA200).get('count', 0) > 0, 'px=%s' % span(pg, EMA200))
        b.close()
    print('TA JOB12: %s (%d checks, %d failed)' % ('PASS' if not fails else 'FAIL', n, len(fails)))
    if fails:
        print('failed: %s' % ', '.join(fails))
    sys.exit(1 if fails else 0)

if __name__ == '__main__':
    main()
