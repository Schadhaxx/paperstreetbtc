#!/usr/bin/env python3
"""TA Drawing Fixes Job 4 checks (22 Nov 2026): label drift. The scan saw
the same level read C$83,548, then C$83,637, then C$83,646 within minutes.
Root cause: tlLabel formatted through fmtP -> window.__BTCP.fmt, which
converts USD->CAD at the LIVE rate (curVal = v * CUR.rate, rate =
lastCad/lastPrice, recomputed on every live tick). The level's USD price
never moved; the exchange rate did. The fix: tlLabel always uses the
level's own USD price (tlPlainFmt) — the label is anchored to the file and
changes only when the file changes. Serves this checkout on localhost,
stubs the price/candle feeds, serves a ta-lines.json fixture, turns
trendlines on, and verifies: the drawn labels are the USD prices, and
they are IDENTICAL after the CAD rate is moved (1.39247 -> 1.39410 -> 1.30)
— i.e. no label drifts with the FX rate. Sloped labels are checked the
same way (their edgePrice legitimately moves one slope-step per new
candle, but must not move with the rate).
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
    # Live price ~77500. Levels near it (rule 3: support <= live <= resistance).
    # The $77,000 support is the anchor check: old code labelled it
    # C$107,220 at rate 1.39247 and C$107,346 at 1.39410; new code '$77,000'.
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

LABELS_JS = """() => {
  const pr = window.__TA_TL_DEBUG ? window.__TA_TL_DEBUG() : null;
  if (!pr || !pr.last) return {error: 'no probe', status: pr ? pr.status : null};
  const rows = (pr.last.lines || []).map(ln => ({
    type: ln.type, kind: ln.kind, tf: ln.tf,
    price: ln.type === 'sloped' ? ln.edgePrice : ln.price,
    label: ln.label || ''}));
  return {status: pr.status, tf: pr.tf, labels: rows.map(r => r.label),
          rows: rows,
          rate: (window.__BTCP && window.__BTCP.CUR) ? window.__BTCP.CUR.rate : null};
}"""

def labels(pg, name):
    try:
        pg.wait_for_function("window.__TA_TL_DEBUG && window.__TA_TL_DEBUG().status === 'live'", timeout=15000)
    except Exception:
        print('  [%s] never reached live' % name)
        return None
    m = pg.evaluate(LABELS_JS)
    print('  [%s] status=%s tf=%s rate=%s labels=%s' % (
        name, m.get('status'), m.get('tf'), m.get('rate'), m.get('labels')))
    return m

def set_rate(pg, rate):
    # Mimics a live FX tick: the clock recomputes fxRate = lastCad/lastPrice
    # and calls BC_setCurrency, which sets CUR.rate and redraws the chart.
    ok = pg.evaluate("""(rate) => {
      if (typeof window.BC_setCurrency !== 'function') return false;
      window.BC_setCurrency('CAD', rate);
      return true;
    }""", rate)
    pg.wait_for_timeout(800)
    return ok

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
        pg.click('#taPill'); pg.wait_for_selector('.ta-panel:not([hidden])', timeout=5000)
        pg.wait_for_timeout(500)
        print('--- 1D Line, rate 1.39247 (scan drift start) ---')
        chk('BC_setCurrency is available (rate control)', set_rate(pg, 1.39247))
        m_a = labels(pg, '1D Line @1.39247')
        print('--- 1D Line, rate 1.39410 (scan drift end) ---')
        set_rate(pg, 1.39410)
        m_b = labels(pg, '1D Line @1.39410')
        print('--- 1D Line, rate 1.30 (large move) ---')
        set_rate(pg, 1.30)
        m_c = labels(pg, '1D Line @1.30')
        print('--- 1W Line, rate 1.45 ---')
        pg.click('#bcRgs button[data-r="1W"]'); pg.wait_for_timeout(1500)
        set_rate(pg, 1.45)
        m_w = labels(pg, '1W Line @1.45')
        b.close()
    # Summary checks (post-fix behaviour)
    if m_a and m_b and m_c:
        chk('1D Line: labels identical across FX rates 1.39247 -> 1.39410 -> 1.30 (anchored)',
            m_a['labels'] == m_b['labels'] == m_c['labels'],
            {'a': m_a['labels'], 'b': m_b['labels'], 'c': m_c['labels']})
        chk('1D Line: the $77,000 support labels its own USD price (not a CAD conversion)',
            '$77,000' in m_a['labels'], m_a['labels'])
        chk('1D Line: no label is a CAD conversion (no C$ prefix)',
            all('C$' not in (lb or '') for lb in m_a['labels']), m_a['labels'])
        chk('1D Line: labels are non-empty (lines still labelled)',
            len(m_a['labels']) >= 4 and all(lb for lb in m_a['labels']), m_a['labels'])
        # Sloped labels must also be rate-stable (their edgePrice moves per
        # new candle, legitimately, but not with the rate).
        sl_a = [r['label'] for r in m_a['rows'] if r['type'] == 'sloped']
        sl_b = [r['label'] for r in m_b['rows'] if r['type'] == 'sloped']
        chk('1D Line: sloped labels identical across FX rates',
            len(sl_a) >= 1 and sl_a == sl_b, {'a': sl_a, 'b': sl_b})
    if m_w:
        chk('1W Line: labels present and USD (anchored)',
            len(m_w['labels']) >= 2 and all(lb.startswith('$') for lb in m_w['labels'] if lb),
            m_w['labels'])
    print('JOB4 %d checks, %d FAIL' % (n, len(fails)))
    for f in fails:
        print('  FAIL:', f)
    sys.exit(1 if fails else 0)

if __name__ == '__main__':
    main()
