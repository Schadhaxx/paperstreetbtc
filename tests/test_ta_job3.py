#!/usr/bin/env python3
"""TA Drawing Fixes Job 3 checks (22 Nov 2026): RSI strip rebuild.
The strip was a 50px box with a bare purple line: no scale, 30/70 lines at
~18% opacity (effectively invisible), no shaded bands, and the header read
"RSI 14 -" because nothing ever wrote the live value into it. On 1D Line
it could not even compute (7 closes, needs 14) — Job 2's pre-warm fixed
the data side (fvRsi=0, warm>=200 on every view). The fix: a taller strip
(76px, 60px short-landscape) with a 0/30/50/70/100 scale in a left gutter,
shaded overbought/oversold bands (Sunil 21 Nov ~22:23: shaded bands, the
most visually available option on iPhone), solid 30/70 band edges, a faint
50 midline, the live RSI value in the header (updated on every draw), and
the header pill moved top-right so it clears the scale labels. RSI is
ungated everywhere. Serves this checkout on localhost with stubbed feeds
(same harness as test_ta_job2.py), seeds RSI on, and verifies per view:
the toggle is enabled, the strip shows, the header value matches the
probe's last RSI, the scale labels and both bands draw, the line draws,
and RSI is valid from index 0. Comparison-on still hides the strip.
"""
import json, math, os, re, sys, threading, functools, http.server, socketserver, urllib.parse, datetime as dt
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
  const el = document.getElementById('taRsi');
  const b = el ? el.querySelector('.ta-rsi-t b') : null;
  const out = {hidden: el ? el.hidden : null,
               height: el ? el.clientHeight : null,
               header: b ? b.textContent : null,
               fvRsi: d ? d.firstValid.rsi : null,
               lastRsi: d ? d.last.rsi : null,
               warm: d ? d.warm : null, n: d ? d.n : null};
  const cv = el ? el.querySelector('canvas') : null;
  if (cv) {
    const ctx = cv.getContext('2d');
    const W = cv.width, H = cv.height;
    const img = ctx.getImageData(0, 0, W, H).data;
    const px = (x, y) => { const i = (y * W + x) * 4; return [img[i], img[i+1], img[i+2]]; };
    let lab = 0;
    for (let y = 0; y < H; y += 1) for (let x = 0; x < 28; x += 1) {
      const c = px(x, y);
      if ((Math.abs(c[0]-148) <= 12 && Math.abs(c[1]-163) <= 12 && Math.abs(c[2]-184) <= 12) ||
          (Math.abs(c[0]-100) <= 12 && Math.abs(c[1]-116) <= 12 && Math.abs(c[2]-139) <= 12)) lab++;
    }
    const meanRG = (y0, y1) => {
      let sr = 0, sg = 0, cnt = 0;
      for (let y = y0; y < y1; y += 2) for (let x = 40; x < W - 140; x += 4) { const c = px(x, y); sr += c[0]; sg += c[1]; cnt++; }
      return cnt ? [sr / cnt, sg / cnt] : [0, 0];
    };
    let purp = 0;
    for (let i = 0; i < img.length; i += 4) {
      if (Math.abs(img[i]-167) <= 12 && Math.abs(img[i+1]-139) <= 12 && Math.abs(img[i+2]-250) <= 12) purp++;
    }
    const top = meanRG(0, Math.floor(H*0.30)), mid = meanRG(Math.floor(H*0.40), Math.floor(H*0.60)), bot = meanRG(Math.floor(H*0.70), H);
    out.labelPx = lab;
    out.topRedness = top[0] - top[1];
    out.midRedness = mid[0] - mid[1];
    out.botGreenness = bot[1] - bot[0];
    out.midGreenness = mid[1] - mid[0];
    out.purpPx = purp;
  }
  return out;
}"""

def disabled(pg, sel):
    return pg.is_disabled(sel)

def measure(pg, name):
    pg.wait_for_timeout(2500)  # let the warm-up land
    m = pg.evaluate(MEASURE_JS)
    print('  [%s] hidden=%s h=%s header=%r fvRsi=%s lastRsi=%s warm=%s n=%s labelPx=%s topRed=%.1f botGreen=%.1f purpPx=%s' % (
        name, m.get('hidden'), m.get('height'), m.get('header'), m.get('fvRsi'),
        (round(m['lastRsi'], 1) if isinstance(m.get('lastRsi'), (int, float)) else m.get('lastRsi')),
        m.get('warm'), m.get('n'), m.get('labelPx'), m.get('topRedness', -99),
        m.get('botGreenness', -99), m.get('purpPx')))
    return m

def check_strip(pg, name, m):
    chk('%s: RSI toggle enabled (ungated, Job 3)' % name, not disabled(pg, '.ta-panel [data-ta-key="rsi"]'))
    chk('%s: RSI strip visible' % name, m.get('hidden') is False, 'hidden=%s' % m.get('hidden'))
    chk('%s: strip taller than before (h>=70)' % name, (m.get('height') or 0) >= 70, 'h=%s' % m.get('height'))
    last = m.get('lastRsi')
    hdr = m.get('header')
    chk('%s: header shows the live value' % name,
        isinstance(hdr, str) and re.fullmatch(r'\d+\.\d', hdr or '') is not None and last is not None and abs(float(hdr) - last) < 0.15,
        'header=%r last=%s' % (hdr, last))
    chk('%s: scale labels draw in the gutter' % name, (m.get('labelPx') or 0) >= 100, 'labelPx=%s' % m.get('labelPx'))
    chk('%s: overbought band draws (top redder than middle)' % name,
        (m.get('topRedness') or 0) - (m.get('midRedness') or 0) > 20,
        'top=%.1f mid=%.1f' % (m.get('topRedness', -99), m.get('midRedness', -99)))
    chk('%s: oversold band draws (bottom greener than middle)' % name,
        (m.get('botGreenness') or 0) - (m.get('midGreenness') or 0) > 20,
        'bot=%.1f mid=%.1f' % (m.get('botGreenness', -99), m.get('midGreenness', -99)))
    chk('%s: RSI line draws' % name, (m.get('purpPx') or 0) >= 50, 'purpPx=%s' % m.get('purpPx'))
    chk('%s: RSI valid from index 0 (Job 2 warm-up)' % name, m.get('fvRsi') == 0, 'fvRsi=%s' % m.get('fvRsi'))

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
        # ---- desktop 1440 dark ----
        pg = b.new_page(viewport={'width': 1440, 'height': 900})
        pg.clock.set_fixed_time(FIXED)
        pg.route('**/*', handler)
        pg.add_init_script("try{localStorage.setItem('ps-ta-v1', JSON.stringify({tl:false,bb:false,ma:false,maSet:{},rsi:true,rsiCol:false,last1DSize:'1h'}));}catch(e){}")
        pg.goto(U + 'clock/', wait_until='domcontentloaded')
        pg.wait_for_selector('#bcC', timeout=10000)
        pg.wait_for_timeout(3000)
        pg.click('#taPill'); pg.wait_for_selector('.ta-panel:not([hidden])', timeout=5000)
        pg.wait_for_timeout(500)
        print('--- 1D Line ---')
        check_strip(pg, '1D Line', measure(pg, '1D Line'))
        print('--- 1D 1H candles ---')
        pick_size(pg, '1h'); check_strip(pg, '1D 1H', measure(pg, '1D 1H'))
        print('--- 1W Line ---')
        go_range(pg, '1W'); pick_line(pg); check_strip(pg, '1W Line', measure(pg, '1W Line'))
        print('--- 1M Line ---')
        go_range(pg, '1M'); pick_line(pg); check_strip(pg, '1M Line', measure(pg, '1M Line'))
        print('--- 3M Line ---')
        go_range(pg, '3M'); pick_line(pg); check_strip(pg, '3M Line', measure(pg, '3M Line'))
        print('--- YTD Line ---')
        go_range(pg, 'YTD'); pick_line(pg); check_strip(pg, 'YTD Line', measure(pg, 'YTD Line'))
        print('--- 1Y Line ---')
        go_range(pg, '1Y'); pick_line(pg); check_strip(pg, '1Y Line', measure(pg, '1Y Line'))
        print('--- 5Y Line ---')
        go_range(pg, '5Y'); check_strip(pg, '5Y Line', measure(pg, '5Y Line'))
        # ---- collapsed: header keeps the value ----
        print('--- collapsed ---')
        pg.click('#taRsi .ta-rsi-t'); pg.wait_for_timeout(600)
        m = pg.evaluate(MEASURE_JS)
        chk('collapsed: strip collapses (canvas hidden)',
            pg.evaluate("document.querySelector('#taRsi canvas').offsetParent === null"))
        chk('collapsed: header still shows the live value',
            isinstance(m.get('header'), str) and re.fullmatch(r'\d+\.\d', m.get('header') or '') is not None,
            'header=%r' % m.get('header'))
        pg.click('#taRsi .ta-rsi-t'); pg.wait_for_timeout(600)
        # ---- comparison on: strip hides (unchanged) ----
        print('--- comparison on ---')
        pg.click('#bcSpx'); pg.wait_for_timeout(900)
        chk('comparison on: RSI strip hides',
            pg.evaluate("document.getElementById('taRsi').hidden"))
        pg.click('#bcSpx'); pg.wait_for_timeout(900)
        chk('comparison off: RSI strip shows again',
            pg.evaluate("!document.getElementById('taRsi').hidden"))
        # ---- phone 390 dark ----
        print('--- phone 390 dark ---')
        pg2 = b.new_page(viewport={'width': 390, 'height': 844})
        pg2.clock.set_fixed_time(FIXED)
        pg2.route('**/*', handler)
        pg2.add_init_script("try{localStorage.setItem('ps-ta-v1', JSON.stringify({tl:false,bb:false,ma:false,maSet:{},rsi:true,rsiCol:false,last1DSize:'1h'}));}catch(e){}")
        pg2.goto(U + 'clock/', wait_until='domcontentloaded')
        pg2.wait_for_selector('#bcC', timeout=10000)
        pg2.wait_for_timeout(3000)
        pg2.click('#taPill'); pg2.wait_for_selector('.ta-panel:not([hidden])', timeout=5000)
        pg2.wait_for_timeout(500)
        m2 = measure(pg2, 'phone 1D Line')
        chk('phone 390 dark: RSI toggle enabled', not disabled(pg2, '.ta-panel [data-ta-key="rsi"]'))
        chk('phone 390 dark: strip visible + taller', m2.get('hidden') is False and (m2.get('height') or 0) >= 70,
            'hidden=%s h=%s' % (m2.get('hidden'), m2.get('height')))
        chk('phone 390 dark: header shows the live value',
            isinstance(m2.get('header'), str) and re.fullmatch(r'\d+\.\d', m2.get('header') or '') is not None,
            'header=%r' % m2.get('header'))
        chk('phone 390 dark: no horizontal overflow',
            pg2.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
        chk('phone 390 dark: scale + bands draw',
            (m2.get('labelPx') or 0) >= 100 and (m2.get('topRedness') or 0) - (m2.get('midRedness') or 0) > 20,
            'labelPx=%s topRed=%.1f' % (m2.get('labelPx'), m2.get('topRedness', -99)))
        # ---- desktop 1440 light ----
        print('--- desktop 1440 light ---')
        pg3 = b.new_page(viewport={'width': 1440, 'height': 900})
        pg3.clock.set_fixed_time(FIXED)
        pg3.route('**/*', handler)
        pg3.add_init_script("try{localStorage.setItem('ps-ta-v1', JSON.stringify({tl:false,bb:false,ma:false,maSet:{},rsi:true,rsiCol:false,last1DSize:'1h'})); localStorage.setItem('ps-theme','light');}catch(e){}")
        pg3.goto(U + 'clock/', wait_until='domcontentloaded')
        pg3.wait_for_selector('#bcC', timeout=10000)
        pg3.wait_for_timeout(3000)
        m3 = measure(pg3, 'light 1D Line')
        chk('light 1440: strip visible + taller', m3.get('hidden') is False and (m3.get('height') or 0) >= 70,
            'hidden=%s h=%s' % (m3.get('hidden'), m3.get('height')))
        chk('light 1440: header shows the live value',
            isinstance(m3.get('header'), str) and re.fullmatch(r'\d+\.\d', m3.get('header') or '') is not None,
            'header=%r' % m3.get('header'))
        chk('light 1440: scale + bands draw',
            (m3.get('labelPx') or 0) >= 100 and (m3.get('topRedness') or 0) - (m3.get('midRedness') or 0) > 20
            and (m3.get('botGreenness') or 0) - (m3.get('midGreenness') or 0) > 20,
            'labelPx=%s topRed=%.1f botGreen=%.1f' % (m3.get('labelPx'), m3.get('topRedness', -99), m3.get('botGreenness', -99)))
        b.close()
    print('JOB3 %d checks, %d FAIL' % (n, len(fails)))
    for f in fails:
        print('  FAIL:', f)
    sys.exit(1 if fails else 0)

if __name__ == '__main__':
    main()
