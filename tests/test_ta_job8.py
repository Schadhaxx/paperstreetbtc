#!/usr/bin/env python3
"""TA Drawing Fixes Job 8 checks (22 Nov 2026): scan the 1W range + decide SMA 200 on 6M.

1W was never scanned (the original scan + scan #2 covered 1D/1M/3M/6M/YTD/1Y/
5Y/10Y/Max). Serves this checkout on localhost, stubs the price/candle feeds
(the Coinbase stub serves the repo's own real daily closes for granularity
86400 — the panel's warm-up comes from that same file, so warm + visible
are one series, as on the real site; hourly/4h stay a smooth synthetic
series, where warm and visible both come from the stub), frozen clock
2026-10-30 20:00 UTC, all TA overlays on. Per view it verifies: warm-up
present, Bollinger + SMA 200 + RSI valid from index 0, the lines actually
drawn (pixel counts), trendlines live, RSI strip visible, badge counts, and
the settled gating (SMA 20/50 + EMA 50 disabled on 1W).

SMA 200 on 6M — DECIDED: it reads right on 6M Line (200-day MA) and 6M
weekly candles (200-week MA): valid from index 0, matches an independent
recomputation from the probe's own warm+visible closes, smooth, inside
the visible price range, draws a full line. It stays ungated there.
The 200s ARE gated on monthly-granularity candle views (Job 8): a
200-month average needs 200 months of BTC history and only ~195 exist
(Aug 2010–Nov 2026), so the lines can never compute there — verified on
6M monthly (warm 189, fvSMA200 None, chips disabled).
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
fails, n = [], 0

def chk(name, ok, detail=''):
    global n
    n += 1
    print('ok' if ok else 'FAIL', name, '' if ok else str(detail)[:300], flush=True)
    if not ok:
        fails.append(name)

def iso(d):
    return d.strftime('%Y-%m-%dT%H:%M:%SZ')

def lvl(price, kind, brk=False, ext=False):
    return {'price': price, 'kind': kind, 'score': 5.0, 'rawScore': 6.0, 'distAtr': 1.0,
            'touches': 5, 'lastTouch': iso(FIXED), 'ageCandles': 3, 'broken': brk, 'held': False, 'extreme': ext}

def slp(kind, slope, anchor, anchor_price):
    return {'kind': kind, 'slope': slope, 'anchor': {'t': iso(anchor), 'price': anchor_price},
            'touches': 5, 'score': 5.0, 'rawScore': 6.0, 'distAtr': 1.0, 'priceNow': anchor_price,
            'broken': False, 'held': False}

def tf(asOf, levels, sloped):
    return {'asOf': iso(asOf), 'atr': 700, 'lastClose': 77500, 'levels': levels, 'sloped': sloped,
            'missingSupport': False, 'missingResistance': False}

def fixture():
    h1, h4, d1 = FIXED - dt.timedelta(minutes=10), FIXED - dt.timedelta(hours=1), FIXED - dt.timedelta(hours=5)
    t1h = tf(h1, [lvl(79500, 'resistance'), lvl(76000, 'support')], [slp('support', 30, FIXED - dt.timedelta(hours=12), 75500)])
    t4h = tf(h4, [lvl(79500, 'resistance')], [slp('support', 120, FIXED - dt.timedelta(hours=20), 74000)])
    t1d = tf(d1, [lvl(81000, 'resistance'), lvl(75000, 'support')], [slp('support', -30, dt.datetime(2026, 10, 20, tzinfo=dt.timezone.utc), 76000)])
    return {'v': 1, 'kind': 'ta-lines', 'asOf': iso(FIXED), 'timeframes': {'1h': t1h, '4h': t4h, '1d': t1d}}

FIXTURE = fixture()

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
        # Daily candles: the repo's own real daily closes (o = prior close).
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

MEASURE_JS = """() => {
  const d = window.__TA_DEBUG ? window.__TA_DEBUG() : null;
  const t = window.__TA_TL_DEBUG ? window.__TA_TL_DEBUG() : null;
  if (!d) return {error: 'no probe'};
  const rsiEl = document.querySelector('.ta-rsi');
  const hb = rsiEl ? rsiEl.querySelector('.ta-rsi-t b') : null;
  const pill = document.getElementById('taPill');
  const nn = pill ? pill.querySelector('.ta-n') : null;
  return {kind: d.kind, n: d.n, warm: d.warm,
          closes: d.closes, warmCloses: d.warmCloses,
          fvBB: d.firstValid.bb, fvRSI: d.firstValid.rsi, fv: d.firstValidMas,
          last: d.last,
          tl: t ? {status: t.status, tf: t.tf, lines: (t.last && t.last.lines ? t.last.lines.length : null)} : null,
          rsiStrip: rsiEl ? {hidden: rsiEl.hidden, header: hb ? hb.textContent : null} : null,
          badge: nn ? nn.textContent : null};
}"""

COLOURS = {'bb': (167, 139, 250), 'sma20': (244, 114, 182), 'sma50': (251, 191, 36),
           'sma200': (20, 184, 166), 'ema20': (56, 189, 248), 'ema50': (251, 146, 60),
           'ema200': (163, 230, 53), 'tl': (34, 197, 94)}

def colour_count(pg, rgb, sel='#bcC', tol=10):
    return pg.evaluate("""([rgb, sel, tol]) => {
      const cv = document.querySelector(sel);
      if (!cv) return -1;
      const ctx = cv.getContext('2d');
      const w = cv.width, h = cv.height;
      const d = ctx.getImageData(0, 0, w, h).data;
      let c = 0;
      for (let i = 0; i < d.length; i += 4) {
        if (Math.abs(d[i] - rgb[0]) <= tol && Math.abs(d[i+1] - rgb[1]) <= tol && Math.abs(d[i+2] - rgb[2]) <= tol) c++;
      }
      return c;
    }""", [list(rgb), sel, tol])

def measure(pg, name):
    pg.wait_for_timeout(2500)
    m = pg.evaluate(MEASURE_JS)
    if 'error' in m:
        print('  [%s] PROBE ERROR %s' % (name, m), flush=True)
        return m
    m['px'] = {k: colour_count(pg, v) for k, v in COLOURS.items()}
    print('  [%s] kind=%s n=%s warm=%s fvBB=%s fvRSI=%s fvSMA200=%s px=%s tl=%s badge=%s' % (
        name, m['kind'], m['n'], m['warm'], m['fvBB'], m['fvRSI'],
        (m['fv'] or {}).get('sma200'), m['px'], m['tl'], m['badge']), flush=True)
    return m

def sma(series, per):
    out = []
    for i in range(len(series)):
        out.append(sum(series[i - per + 1:i + 1]) / per if i >= per - 1 else None)
    return out

def sma200_check(m, name):
    """Independent recomputation of SMA 200 from the probe's own warm+visible closes."""
    if 'error' in m or not m.get('warmCloses') or not m.get('closes'):
        chk('%s: SMA 200 recomputation has closes to check' % name, False, m)
        return
    full = m['warmCloses'] + m['closes']
    w = len(m['warmCloses'])
    s = sma(full, 200)
    vis = s[w:]
    exp_last = s[-1]
    got_last = (m['last']['mas'] or {}).get('sma200')
    valid = [v for v in vis if v is not None]
    chk('%s: SMA 200 valid across the whole window' % name, len(valid) == len(vis) and len(vis) > 0,
        'valid=%d/%d' % (len(valid), len(vis)))
    chk('%s: SMA 200 matches independent recomputation' % name,
        exp_last is not None and got_last is not None and abs(exp_last - got_last) < 0.01,
        'expected=%s probe=%s' % (exp_last, got_last))
    if valid:
        lo, hi = min(m['closes']), max(m['closes'])
        chk('%s: SMA 200 inside the visible price range (not a fragment/diagonal off-chart)' % name,
            min(valid) >= lo and max(valid) <= hi,
            'sma200 %.0f..%.0f vs price %.0f..%.0f' % (min(valid), max(valid), lo, hi))
        steps = [abs(vis[i + 1] - vis[i]) for i in range(len(vis) - 1) if vis[i] is not None and vis[i + 1] is not None]
        chk('%s: SMA 200 smooth (max step under 1%% of price)' % name,
            steps and max(steps) < 0.01 * hi, 'max step=%.2f' % (max(steps) if steps else -1))

def pick_line(pg):
    pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
    pg.click('.ta-menu [data-ta-pick="line"]'); pg.wait_for_timeout(1200)

def pick_size(pg, size):
    pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
    pg.click('.ta-menu [data-ta-size="%s"]' % size); pg.wait_for_timeout(1200)

def go_range(pg, r):
    pg.click('#bcRgs button[data-r="%s"]' % r); pg.wait_for_timeout(1200)

def disabled(pg, sel):
    return pg.is_disabled(sel)

def ensure_panel(pg):
    vis = pg.evaluate("""() => {
      const p = document.querySelector('.ta-panel');
      return p ? !p.hidden : false;
    }""")
    if not vis:
        pg.click('#taPill'); pg.wait_for_selector('.ta-panel:not([hidden])', timeout=5000)
        pg.wait_for_timeout(400)

def main():
    global U
    srv = None
    if len(sys.argv) > 1:
        base = sys.argv[1].rstrip('/')
        U = base + '/'
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

        # ---- 1W Line ----
        print('--- 1W Line ---')
        go_range(pg, '1W'); pick_line(pg)
        m = measure(pg, '1W Line')
        chk('1W Line: warm-up present (warm>=200)', m['warm'] is not None and m['warm'] >= 200, 'warm=%s' % m['warm'])
        chk('1W Line: Bollinger + SMA 200 + RSI valid from index 0',
            m['fvBB'] == 0 and (m['fv'] or {}).get('sma200') == 0 and m['fvRSI'] == 0,
            'fvBB=%s fvSMA200=%s fvRSI=%s' % (m['fvBB'], (m['fv'] or {}).get('sma200'), m['fvRSI']))
        chk('1W Line: Bollinger violet draws', m['px']['bb'] > 0, 'px=%d' % m['px']['bb'])
        chk('1W Line: SMA 200 teal draws (a real line, not edge pixels)', m['px']['sma200'] >= 50, 'px=%d' % m['px']['sma200'])
        chk('1W Line: EMA 20 draws', m['px']['ema20'] > 0, 'px=%d' % m['px']['ema20'])
        chk('1W Line: trendlines live with lines', (m['tl'] or {}).get('status') == 'live' and (m['tl'] or {}).get('lines', 0) > 0, str(m['tl']))
        chk('1W Line: RSI strip visible with a live value', (m['rsiStrip'] or {}).get('hidden') is False and (m['rsiStrip'] or {}).get('header') not in (None, '', '—'), str(m['rsiStrip']))
        chk('1W Line: badge counts the drawings (6, gated MAs excluded)', m['badge'] == '6', 'badge=%s' % m['badge'])
        ensure_panel(pg)
        chk('1W Line: SMA 20/50 + EMA 50 chips still disabled (settled lists)',
            disabled(pg, '.ta-panel [data-ta-ma="sma20"]') and disabled(pg, '.ta-panel [data-ta-ma="sma50"]') and disabled(pg, '.ta-panel [data-ta-ma="ema50"]'))
        chk('1W Line: SMA 200 / EMA 200 / BB / RSI / TL enabled',
            not disabled(pg, '.ta-panel [data-ta-ma="sma200"]') and not disabled(pg, '.ta-panel [data-ta-ma="ema200"]')
            and not disabled(pg, '.ta-panel [data-ta-key="bb"]') and not disabled(pg, '.ta-panel [data-ta-key="rsi"]')
            and not disabled(pg, '.ta-panel [data-ta-key="tl"]'))

        # ---- 1W Candles 4h ----
        print('--- 1W 4H candles ---')
        pick_size(pg, '4h')
        m = measure(pg, '1W 4H')
        chk('1W 4H: warm-up present (warm>=200)', m['warm'] is not None and m['warm'] >= 200, 'warm=%s' % m['warm'])
        chk('1W 4H: Bollinger + SMA 200 + RSI valid from index 0',
            m['fvBB'] == 0 and (m['fv'] or {}).get('sma200') == 0 and m['fvRSI'] == 0)
        chk('1W 4H: Bollinger violet draws', m['px']['bb'] > 0, 'px=%d' % m['px']['bb'])
        chk('1W 4H: SMA 200 teal draws', m['px']['sma200'] >= 50, 'px=%d' % m['px']['sma200'])
        chk('1W 4H: trendlines live with lines (4h + higher 1d)', (m['tl'] or {}).get('status') == 'live' and (m['tl'] or {}).get('lines', 0) >= 4, str(m['tl']))
        chk('1W 4H: RSI strip visible with a live value', (m['rsiStrip'] or {}).get('hidden') is False and (m['rsiStrip'] or {}).get('header') not in (None, '', '—'), str(m['rsiStrip']))
        chk('1W 4H: badge counts the drawings (6)', m['badge'] == '6', 'badge=%s' % m['badge'])

        # ---- 1W Candles daily ----
        print('--- 1W daily candles ---')
        pick_size(pg, 'daily')
        m = measure(pg, '1W daily')
        chk('1W daily: warm-up present (warm>=200)', m['warm'] is not None and m['warm'] >= 200, 'warm=%s' % m['warm'])
        chk('1W daily: Bollinger + SMA 200 + RSI valid from index 0',
            m['fvBB'] == 0 and (m['fv'] or {}).get('sma200') == 0 and m['fvRSI'] == 0)
        chk('1W daily: Bollinger violet draws', m['px']['bb'] > 0, 'px=%d' % m['px']['bb'])
        chk('1W daily: EMA 20 draws', m['px']['ema20'] > 0, 'px=%d' % m['px']['ema20'])
        chk('1W daily: trendlines live with lines', (m['tl'] or {}).get('status') == 'live' and (m['tl'] or {}).get('lines', 0) > 0, str(m['tl']))
        chk('1W daily: RSI strip visible with a live value', (m['rsiStrip'] or {}).get('hidden') is False and (m['rsiStrip'] or {}).get('header') not in (None, '', '—'), str(m['rsiStrip']))
        s20 = (m['last']['mas'] or {}).get('sma20'); e20 = (m['last']['mas'] or {}).get('ema20')
        chk('1W daily: SMA 20 vs EMA 20 values agree (within 5%% — the live inconsistency was the gating, not the values)',
            s20 is not None and e20 is not None and abs(s20 - e20) / s20 < 0.05,
            'sma20=%s ema20=%s' % (s20, e20))

        # ---- 6M Line: SMA 200 decision ----
        print('--- 6M Line ---')
        go_range(pg, '6M'); pick_line(pg)
        m = measure(pg, '6M Line')
        chk('6M Line: warm-up present (warm=250)', m['warm'] == 250, 'warm=%s' % m['warm'])
        chk('6M Line: SMA 200 valid from index 0', (m['fv'] or {}).get('sma200') == 0, 'fv=%s' % (m['fv'] or {}).get('sma200'))
        chk('6M Line: SMA 200 teal draws (a real line)', m['px']['sma200'] >= 50, 'px=%d' % m['px']['sma200'])
        sma200_check(m, '6M Line')
        ensure_panel(pg)
        chk('6M Line: SMA 200 chip enabled (ungated — Job 8 decision)',
            not disabled(pg, '.ta-panel [data-ta-ma="sma200"]'))
        chk('6M Line: EMA 200 chip enabled (ungated — SMA 200 twin)',
            not disabled(pg, '.ta-panel [data-ta-ma="ema200"]'))

        # ---- 6M Candles weekly: SMA 200 decision ----
        print('--- 6M weekly candles ---')
        pick_size(pg, 'weekly')
        m = measure(pg, '6M weekly')
        chk('6M weekly: warm-up present (warm=250)', m['warm'] == 250, 'warm=%s' % m['warm'])
        chk('6M weekly: SMA 200 valid from index 0', (m['fv'] or {}).get('sma200') == 0, 'fv=%s' % (m['fv'] or {}).get('sma200'))
        chk('6M weekly: SMA 200 teal draws (a real line)', m['px']['sma200'] >= 50, 'px=%d' % m['px']['sma200'])
        sma200_check(m, '6M weekly')

        # ---- 6M Candles monthly: the 200s can never compute ----
        print('--- 6M monthly candles ---')
        pick_size(pg, 'monthly')
        m = measure(pg, '6M monthly')
        chk('6M monthly: warm-up is short of 200 (only ~195 months of BTC history exist)',
            m['warm'] is not None and m['warm'] < 200, 'warm=%s' % m['warm'])
        chk('6M monthly: SMA 200 has no values (fv None)', (m['fv'] or {}).get('sma200') is None, 'fv=%s' % (m['fv'] or {}).get('sma200'))
        chk('6M monthly: EMA 200 has no values (fv None)', (m['fv'] or {}).get('ema200') is None, 'fv=%s' % (m['fv'] or {}).get('ema200'))
        chk('6M monthly: SMA 20 / EMA 20 / Bollinger still draw', m['px']['sma20'] > 0 and m['px']['ema20'] > 0 and m['px']['bb'] > 0,
            'px=%s' % (m['px'],))
        ensure_panel(pg)
        chk('6M monthly: SMA 200 chip disabled (gated — Job 8, can never compute)',
            disabled(pg, '.ta-panel [data-ta-ma="sma200"]'))
        chk('6M monthly: EMA 200 chip disabled (gated — Job 8, can never compute)',
            disabled(pg, '.ta-panel [data-ta-ma="ema200"]'))
        chk('6M monthly: SMA 20 / EMA 20 chips enabled (only the 200s are gated)',
            not disabled(pg, '.ta-panel [data-ta-ma="sma20"]') and not disabled(pg, '.ta-panel [data-ta-ma="ema20"]'))
        b.close()
    print('JOB8 %d checks, %d FAIL' % (n, len(fails)))
    for f in fails:
        print('  FAIL:', f)
    sys.exit(1 if fails else 0)

if __name__ == '__main__':
    main()
