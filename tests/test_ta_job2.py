#!/usr/bin/env python3
"""TA Drawing Fixes Job 2 checks (21 Nov 2026): indicator windows.
Bollinger + the 200s used to be computed from the visible window alone,
because the warm-up fetch only started when an overlay was turned on —
so Bollinger started 19 points late and SMA 200 was missing entirely on
the short views (1D Line: fvBB=19, fvSMA200 null while warm was in
flight). The fix (preWarm at TA init + one retry on failure) fetches the
history before the visible window up front, so the indicators are valid
from index 0 on every view. Serves this checkout on localhost, stubs the
price/candle feeds (the Coinbase stub honours start/end so the paged
warm-up fetches return their own windows), turns Bollinger + all six MAs
on, and verifies per view: warm-up present, Bollinger and SMA 200 valid
from index 0, the toggles enabled (Bollinger everywhere, SMA/EMA 200 on
1D/1W), and the lines actually drawn (pixel counts). SMA 20/50 and EMA 50
stay gated on 1W — per the settled lists, not this job. (RSI was gated
everywhere at Job 2 time; Job 3 ungated it, and Job 12 ungated SMA 20/50
+ EMA 50 on 1W — the checks below were updated.)
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

def base_price(t_ms):
    # One smooth underlying path, a function of absolute time only, so any
    # granularity samples the same series and warm/visible join seamlessly.
    t = t_ms / 1000.0
    return 77500 + 900 * math.sin(t / 18000.0) + 350 * math.cos(t / 10800.0)

def coinbase(route):
    u = urllib.parse.urlparse(route.request.url); q = urllib.parse.parse_qs(u.query)
    if 'spot' in u.path:
        return route.fulfill(status=200, content_type='application/json', body=json.dumps({'data': {'amount': '77500.00', 'currency': 'USD'}}))
    g = int(q.get('granularity', ['86400'])[0])
    end = int(dt.datetime.fromisoformat(q['end'][0].replace('Z', '+00:00')).timestamp()) if 'end' in q else int(FIXED.timestamp())
    start = int(dt.datetime.fromisoformat(q['start'][0].replace('Z', '+00:00')).timestamp()) if 'start' in q else end - 300 * g
    rows, t = [], end - end % g
    while t >= start and len(rows) < 300:
        o = base_price(t * 1000); c = base_price((t + g) * 1000)
        rows.append([t, min(o, c) - 120, max(o, c) + 120, o, c, 10]); t -= g
    route.fulfill(status=200, content_type='application/json', body=json.dumps(rows))

def handler(route):
    url = route.request.url
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
  if (!d) return {error: 'no probe'};
  return {kind: d.kind, n: d.n, warm: d.warm,
          fvBB: d.firstValid.bb, fv: d.firstValidMas,
          lastBBUp: d.last.bbUp, lastBBLo: d.last.bbLo,
          lastSMA200: d.last.mas ? d.last.mas.sma200 : null};
}"""

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

def colour_present(pg, rgb, sel='#bcC', tol=20):
    return colour_count(pg, rgb, sel, tol) > 0

def colour_span(pg, rgb, sel='#bcC', tol=10):
    """Bounding box of a colour on the canvas (CSS px). The raw exact-match
    count for a nearly-horizontal 2px line is anti-aliasing-sensitive
    (22-48 for the 1W 4H SMA 200 after the Job 12 axis widening), so the
    span — does the line extend across the chart — is the robust
    'real line, not edge pixels' check there."""
    return pg.evaluate("""([rgb, sel, tol]) => {
      const cv = document.querySelector(sel);
      if (!cv) return {count: 0};
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
    }""", [list(rgb), sel, tol])

def disabled(pg, sel):
    return pg.is_disabled(sel)

def measure(pg, name):
    pg.wait_for_timeout(2500)  # let the warm-up land
    m = pg.evaluate(MEASURE_JS)
    print('  [%s] kind=%s n=%s warm=%s fvBB=%s fvSMA200=%s' % (
        name, m.get('kind'), m.get('n'), m.get('warm'), m.get('fvBB'),
        (m.get('fv') or {}).get('sma200')))
    return m

def pick_line(pg):
    pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
    pg.click('.ta-menu [data-ta-pick="line"]'); pg.wait_for_timeout(1200)

def pick_size(pg, size):
    pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
    pg.click('.ta-menu [data-ta-size="%s"]' % size); pg.wait_for_timeout(1200)

def go_range(pg, r):
    pg.click('#bcRgs button[data-r="%s"]' % r); pg.wait_for_timeout(1200)

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
        pg.add_init_script("try{localStorage.setItem('ps-ta-v1', JSON.stringify({tl:false,bb:true,ma:true,maSet:{sma20:true,sma50:true,sma200:true,ema20:true,ema50:true,ema200:true},rsi:false,rsiCol:false,last1DSize:'1h'}));}catch(e){}")
        pg.goto(U + 'clock/', wait_until='domcontentloaded')
        pg.wait_for_selector('#bcC', timeout=10000)
        pg.wait_for_timeout(3000)
        pg.click('#taPill'); pg.wait_for_selector('.ta-panel:not([hidden])', timeout=5000)
        pg.wait_for_timeout(500)
        res = {}
        # ---- 1D Line ----
        print('--- 1D Line ---')
        res['1D Line'] = measure(pg, '1D Line')
        chk('1D Line: Bollinger toggle enabled (ungated, Job 2)', not disabled(pg, '.ta-panel [data-ta-key="bb"]'))
        chk('1D Line: SMA 200 chip enabled (ungated, Job 2)', not disabled(pg, '.ta-panel [data-ta-ma="sma200"]'))
        chk('1D Line: EMA 200 chip enabled (ungated, Job 2)', not disabled(pg, '.ta-panel [data-ta-ma="ema200"]'))
        chk('1D Line: Bollinger violet draws', colour_present(pg, (167, 139, 250)))
        chk('1D Line: SMA 200 teal draws (a real line, not edge pixels)',
            colour_count(pg, (20, 184, 166), tol=10) >= 50,
            'count=%d' % colour_count(pg, (20, 184, 166), tol=10))
        # ---- 1D 1H candles ----
        print('--- 1D 1H candles ---')
        pick_size(pg, '1h'); res['1D 1H'] = measure(pg, '1D 1H')
        # ---- 1D 4H candles ----
        print('--- 1D 4H candles ---')
        pick_size(pg, '4h'); res['1D 4H'] = measure(pg, '1D 4H')
        # ---- 1W Line ----
        print('--- 1W Line ---')
        go_range(pg, '1W'); pick_line(pg); res['1W Line'] = measure(pg, '1W Line')
        chk('1W Line: Bollinger toggle enabled (ungated, Job 2)', not disabled(pg, '.ta-panel [data-ta-key="bb"]'))
        chk('1W Line: SMA 200 chip enabled (ungated, Job 2)', not disabled(pg, '.ta-panel [data-ta-ma="sma200"]'))
        chk('1W Line: EMA 200 chip enabled (ungated, Job 2)', not disabled(pg, '.ta-panel [data-ta-ma="ema200"]'))
        chk('1W Line: SMA 20/50 chips enabled (ungated, Job 12)',
            not disabled(pg, '.ta-panel [data-ta-ma="sma20"]') and not disabled(pg, '.ta-panel [data-ta-ma="sma50"]'))
        chk('1W Line: EMA 50 chip enabled (ungated, Job 12)',
            not disabled(pg, '.ta-panel [data-ta-ma="ema50"]'))
        chk('1W Line: RSI toggle enabled (Job 3 ungated it)',
            not disabled(pg, '.ta-panel [data-ta-key="rsi"]'))
        # ---- 1W 4H candles ----
        print('--- 1W 4H candles ---')
        pick_size(pg, '4h'); res['1W 4H'] = measure(pg, '1W 4H')
        chk('1W 4H: Bollinger violet draws', colour_present(pg, (167, 139, 250)))
        s200 = colour_span(pg, (20, 184, 166), tol=10)
        chk('1W 4H: SMA 200 teal draws (a real line across the chart, Job 12)',
            s200.get('count', 0) > 0 and s200.get('maxX', 0) - s200.get('minX', 0) >= 200,
            'span=%s' % s200)
        # ---- 1M Line ----
        print('--- 1M Line ---')
        go_range(pg, '1M'); pick_line(pg); res['1M Line'] = measure(pg, '1M Line')
        chk('1M Line: Bollinger toggle enabled (ungated, Job 2)', not disabled(pg, '.ta-panel [data-ta-key="bb"]'))
        # ---- 3M Line ----
        print('--- 3M Line ---')
        go_range(pg, '3M'); pick_line(pg); res['3M Line'] = measure(pg, '3M Line')
        # ---- YTD Line ----
        print('--- YTD Line ---')
        go_range(pg, 'YTD'); pick_line(pg); res['YTD Line'] = measure(pg, 'YTD Line')
        chk('YTD Line: Bollinger violet draws', colour_present(pg, (167, 139, 250)))
        chk('YTD Line: SMA 200 teal draws (a real line, not edge pixels)',
            colour_count(pg, (20, 184, 166), tol=10) >= 50,
            'count=%d' % colour_count(pg, (20, 184, 166), tol=10))
        # ---- 1Y Line ----
        print('--- 1Y Line ---')
        go_range(pg, '1Y'); pick_line(pg); res['1Y Line'] = measure(pg, '1Y Line')
        chk('1Y Line: Bollinger toggle enabled (ungated, Job 2)', not disabled(pg, '.ta-panel [data-ta-key="bb"]'))
        # ---- 5Y Line (control) ----
        print('--- 5Y Line (control) ---')
        go_range(pg, '5Y'); res['5Y Line'] = measure(pg, '5Y Line')
        b.close()
    # Summary: on every view the warm-up must be present and Bollinger +
    # SMA 200 valid from index 0 (computed from history before the window).
    for name, m in res.items():
        if 'error' in m:
            chk('%s: probe works' % name, False, m); continue
        chk('%s: warm-up present (warm>=200)' % name, m['warm'] is not None and m['warm'] >= 200,
            'warm=%s n=%s' % (m['warm'], m['n']))
        chk('%s: Bollinger valid from index 0' % name, m['fvBB'] == 0,
            'fvBB=%s warm=%s n=%s' % (m['fvBB'], m['warm'], m['n']))
        chk('%s: SMA 200 valid from index 0' % name,
            (m['fv'] or {}).get('sma200') == 0,
            'fvSMA200=%s warm=%s n=%s' % ((m['fv'] or {}).get('sma200'), m['warm'], m['n']))
    print('JOB2 %d checks, %d FAIL' % (n, len(fails)))
    for f in fails:
        print('  FAIL:', f)
    sys.exit(1 if fails else 0)

if __name__ == '__main__':
    main()
