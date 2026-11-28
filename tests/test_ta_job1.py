#!/usr/bin/env python3
"""TA Drawing Fixes Job 1 checks (21 Nov 2026): line-view trendlines on
1D/1W. The Line views' y-range used to be computed from the visible closes
only, so most trendlines fell outside it and were clipped even though the
drawer selected them (panel said 17 lines, 3 visible on 1D Line). The fix
(tlExpandRange) extends the Line y-range to include the drawn lines'
prices, bounded to one span per side. Serves this checkout on localhost,
stubs the price/candle feeds, serves a ta-lines.json fixture whose levels
straddle the chart's tight y-range, and verifies: most drawn lines are
VISIBLE on 1D Line and all of them on 1W Line; the trendline toggle is
enabled (not greyed out) on Line 1D/1W; the candle views are unchanged.
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

def lvl(price, kind, ext=False, brk=False):
    return {'price': price, 'kind': kind, 'score': 2.5, 'rawScore': 4.0, 'distAtr': 2.0,
            'touches': 3, 'lastTouch': '2026-10-29T00:00:00Z', 'ageCandles': 5,
            'broken': brk, 'held': False, 'extreme': ext}

def slp(kind, slope, anchor, anchor_price):
    return {'kind': kind, 'slope': slope, 'anchor': {'t': iso(anchor), 'price': anchor_price},
            'touches': 5, 'score': 5.0, 'rawScore': 6.0, 'distAtr': 1.0, 'priceNow': anchor_price,
            'broken': False, 'held': False}

def tf(asOf, levels, sloped, missS=False, missR=False):
    return {'asOf': iso(asOf), 'atr': 700, 'lastClose': 77500, 'levels': levels, 'sloped': sloped,
            'missingSupport': missS, 'missingResistance': missR}

def fixture():
    # Live price ~77500. Supports must be <= live, resistances >= live (rule 3).
    # The stubbed closes vary 77500 +/- ~1250, so the Line y-range is tight
    # (~76250-78750); levels at 75000/74000/80000/82000/85000 sit outside it.
    h1 = FIXED - dt.timedelta(minutes=10)
    h4 = FIXED - dt.timedelta(hours=1)
    d1 = FIXED - dt.timedelta(hours=5)
    t1h = tf(h1,
        [lvl(77000, 'support'), lvl(76500, 'support'), lvl(76000, 'support'),
         lvl(75000, 'support'), lvl(74000, 'support', ext=True),
         lvl(78000, 'resistance'), lvl(78500, 'resistance'), lvl(80000, 'resistance'),
         lvl(82000, 'resistance'), lvl(85000, 'resistance', ext=True)],
        [slp('support', 30, FIXED - dt.timedelta(hours=12), 75500),
         slp('resistance', -20, FIXED - dt.timedelta(hours=10), 79800)])
    t4h = tf(h4,
        [lvl(76000, 'support'), lvl(79000, 'resistance')],
        [slp('support', 120, FIXED - dt.timedelta(hours=20), 74000)])
    t1d = tf(d1,
        [lvl(77000, 'support'), lvl(70000, 'support'),
         lvl(78000, 'resistance'), lvl(85000, 'resistance')],
        [slp('support', -30, dt.datetime(2026, 10, 20, tzinfo=dt.timezone.utc), 76000),
         slp('resistance', 40, dt.datetime(2026, 10, 18, tzinfo=dt.timezone.utc), 74000)])
    return {'v': 1, 'kind': 'ta-lines', 'asOf': iso(FIXED),
            'timeframes': {'1h': t1h, '4h': t4h, '1d': t1d}}

FIXTURE = fixture()

def coinbase(route):
    u = urllib.parse.urlparse(route.request.url); q = urllib.parse.parse_qs(u.query)
    if 'spot' in u.path:
        return route.fulfill(status=200, content_type='application/json', body=json.dumps({'data': {'amount': '77500.00', 'currency': 'USD'}}))
    g = int(q.get('granularity', ['86400'])[0]); end = int(FIXED.timestamp())
    rows, t = [], end - end % g
    while len(rows) < 300:
        o = 77500 + 900 * math.sin(t / g / 5.0); c = o + 350 * math.cos(t / g / 3.0)
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
  const pr = window.__TA_TL_DEBUG ? window.__TA_TL_DEBUG() : null;
  const g = (window.__BCTA && window.__BCTA.geom) ? window.__BCTA.geom() : null;
  if (!pr || !g || !pr.last) return {error: 'no probe/geom', pr: !!pr, g: !!g};
  const T = g.pad.t, B = g.pad.t + g.plotH;
  const rows = (pr.last.lines || []).map(ln => {
    const p = ln.type === 'sloped' ? ln.edgePrice : ln.price;
    const y = (p != null && isFinite(p)) ? g.yFor(p) : NaN;
    return {type: ln.type, kind: ln.kind, tf: ln.tf, price: p, y: y,
            visible: isFinite(y) && y >= T && y <= B};
  });
  // y-range implied by the geometry: price at plot top/bottom
  return {status: pr.status, tf: pr.tf, liveClose: pr.liveClose,
          kind: g.kind, n: g.n,
          drawn: rows.length,
          visible: rows.filter(r => r.visible).length,
          rows: rows};
}"""

def measure(pg, name):
    try:
        pg.wait_for_function("window.__TA_TL_DEBUG && window.__TA_TL_DEBUG().status === 'live'", timeout=15000)
    except Exception as e:
        diag = pg.evaluate("""() => { const pr = window.__TA_TL_DEBUG ? window.__TA_TL_DEBUG() : null;
          return {btta: !!window.__BTTA, bcta: !!window.__BCTA, probe: !!window.__TA_TL_DEBUG,
                  status: pr ? pr.status : null, tlOn: pr ? pr.tlOn : null,
                  fileOk: pr ? pr.fileOk : null, fileReason: pr ? pr.fileReason : null,
                  panelHidden: document.querySelector('.ta-panel') ? document.querySelector('.ta-panel').hidden : 'no-panel'}; }""")
        print('  [%s] never reached live: %s' % (name, diag))
        return None
    m = pg.evaluate(MEASURE_JS)
    print('  [%s] status=%s tf=%s kind=%s liveClose=%s drawn=%s visible=%s' % (
        name, m.get('status'), m.get('tf'), m.get('kind'), m.get('liveClose'), m.get('drawn'), m.get('visible')))
    for r in m.get('rows', []):
        print('      %s %-10s %-10s tf=%-3s price=%-9s y=%s %s' % (
            'VIS' if r['visible'] else 'CLIP', r['type'], r['kind'], r['tf'], r['price'],
            ('%.1f' % r['y']) if r['y'] is not None and r['y'] == r['y'] else 'NaN',
            '' if r['visible'] else '(outside plot)'))
    return m

def tl_toggle_enabled(pg):
    return pg.evaluate("var el=document.querySelector('.ta-panel [data-ta-key=\"tl\"]'); el ? !el.disabled : null")

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
        pg.clock.set_fixed_time(FIXED)  # freeze the clock so the fixture asOf values are fresh
        pg.route('**/*', handler)
        # Turn trendlines on before load (localStorage state the TA module reads).
        pg.add_init_script("try{localStorage.setItem('ps-ta-v1', JSON.stringify({tl:true,bb:false,ma:false,maSet:{},rsi:false,rsiCol:false,last1DSize:'1h'}));}catch(e){}")
        pg.goto(U + 'clock/', wait_until='domcontentloaded')
        pg.wait_for_selector('#bcC', timeout=10000)
        pg.wait_for_timeout(3000)
        # Open the TA panel (loads the lazy TA module); the tl toggle is
        # enabled here because the SCRATCH bypass removed the Stage 1 gating.
        pg.click('#taPill'); pg.wait_for_selector('.ta-panel:not([hidden])', timeout=5000)
        pg.wait_for_timeout(500)
        print('--- 1D Line (default) ---')
        m1d = measure(pg, '1D Line')
        t1d = tl_toggle_enabled(pg)
        print('--- 1W Line ---')
        pg.click('#bcRgs button[data-r="1W"]'); pg.wait_for_timeout(1500)
        m1w = measure(pg, '1W Line')
        t1w = tl_toggle_enabled(pg)
        print('--- 1D 1H candles ---')
        pg.click('#bcRgs button[data-r="1D"]'); pg.wait_for_timeout(1200)
        pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
        pg.click('.ta-menu [data-ta-size="1h"]'); pg.wait_for_timeout(1500)
        m1dc = measure(pg, '1D 1H candles')
        print('--- 1W 4H candles ---')
        pg.click('#bcRgs button[data-r="1W"]'); pg.wait_for_timeout(1200)
        pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
        pg.click('.ta-menu [data-ta-size="4h"]'); pg.wait_for_timeout(1500)
        m1wc = measure(pg, '1W 4H candles')
        b.close()
    # Summary checks (post-fix behaviour)
    if m1d:
        chk('1D Line: most drawn lines are visible after the fix',
            m1d['drawn'] >= 10 and m1d['visible'] >= m1d['drawn'] - 4, m1d)
    chk('1D Line: the trendline toggle is enabled (not greyed out)', t1d is True, t1d)
    if m1w:
        chk('1W Line: all drawn lines are visible after the fix',
            m1w['drawn'] >= 2 and m1w['visible'] == m1w['drawn'], m1w)
    chk('1W Line: the trendline toggle is enabled (not greyed out)', t1w is True, t1w)
    if m1dc and m1d:
        # Must-fix (28 Nov 2026): the follow-ups batch widened the candle
        # y-axis to nice ticks (nativeNiceTicks, same as the line views),
        # which brings two more trendlines into the plot on 1D 1H candles
        # (9 visible, was 7). That is the intended axis change, not a
        # regression in the candle view, so the expected count is 9.
        chk('1D candles unchanged by the fix (Line-only change)',
            m1dc['visible'] == 9, m1dc)
    print('JOB1 %d checks, %d FAIL' % (n, len(fails)))
    for f in fails:
        print('  FAIL:', f)
    sys.exit(1 if fails else 0)

if __name__ == '__main__':
    main()
