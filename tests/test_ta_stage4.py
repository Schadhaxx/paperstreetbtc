#!/usr/bin/env python3
"""TA Stage 4 checks (21 Nov 2026): trendlines from ta-lines.json drawn on
#bcC when Trends is on, in every native view, with the eight display rules
(Market God SOUND + earlier decisions). Serves this checkout on localhost
(or takes a base URL argv[1] and a shots dir argv[2], as run_all.sh does),
stubs the live-price and candle feeds with deterministic data, serves a
synthetic ta-lines.json fixture (generated here, prices around the stubbed
live price, asOf relative to the fixed clock), and verifies at phone 390
dark + desktop 1440 light: lines appear when Trends is on; EXT faded/dashed
+ labelled "range low"/"range high"; stale/missing/invalid file hides lines
with the panel message; a line crossed by the live close is omitted; a
flipped broken:true level draws as a normal line; sloped lines follow the
anchor in candle-index space; same-or-higher timeframe binding (rule 5 —
a 1h chart draws 1h + 4h + 1d, a 4h chart 4h + 1d, a 1d chart 1d only,
higher-tf lines labelled), 5Y/10Y/Max unavailable; missingSupport never
hides sloped lines. The stubbed closes vary within 77500 +/- 1250, so
fixture levels sit at least 1500 clear of the live price on the side they
must draw on, and at least 250 clear on the side they must be omitted on.
"""
import json, math, os, sys, threading, functools, http.server, socketserver, urllib.parse, datetime as dt
from pathlib import Path

R = Path(__file__).resolve().parents[1]

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
    print('ok' if ok else 'FAIL', name, '' if ok else str(detail)[:200], flush=True)
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

def fixture(kind):
    """kind: fresh | stale | stale_all | crossed | invalid | missing (None body).
    stale: 1h asOf is 3 h old (> 2h20m pack window), 4h/1d fresh.
    stale_all: every timeframe past its pack window (1h 3 h, 4h 9 h, 1d 51 h)."""
    if kind == 'invalid':
        return {'v': 2, 'kind': 'ta-lines', 'timeframes': {}}
    if kind == 'missing':
        return None
    h1 = FIXED - dt.timedelta(minutes=10) if kind not in ('stale', 'stale_all') else FIXED - dt.timedelta(hours=3)
    h4 = FIXED - dt.timedelta(hours=1) if kind != 'stale_all' else FIXED - dt.timedelta(hours=9)
    d1 = FIXED - dt.timedelta(hours=5) if kind != 'stale_all' else FIXED - dt.timedelta(hours=51)
    if kind == 'crossed':
        t1h = tf(h1,
            [lvl(79500, 'resistance'), lvl(76000, 'resistance'), lvl(75800, 'support'), lvl(81000, 'resistance', ext=True)],
            [slp('support', -10, FIXED - dt.timedelta(hours=12), 79800),
             slp('resistance', -20, FIXED - dt.timedelta(hours=10), 79800)])
        t4h = tf(h4,
            [lvl(79500, 'resistance'), lvl(79000, 'support')],
            [slp('support', 120, FIXED - dt.timedelta(hours=20), 74000)])
    else:
        t1h = tf(h1,
            [lvl(79500, 'resistance'), lvl(79000, 'resistance', brk=True), lvl(76000, 'support'), lvl(74800, 'support', ext=True)],
            [slp('support', 30, FIXED - dt.timedelta(hours=12), 75500),
             slp('resistance', -20, FIXED - dt.timedelta(hours=10), 79800)])
        t4h = tf(h4,
            [lvl(79500, 'resistance')],
            [slp('support', 120, FIXED - dt.timedelta(hours=20), 74000),
             slp('support', 90, FIXED - dt.timedelta(hours=24), 73000)],
            missS=True)
    t1d = tf(d1,
        [lvl(81000, 'resistance'), lvl(75000, 'support')],
        [slp('support', -30, dt.datetime(2026, 10, 20, tzinfo=dt.timezone.utc), 76000)])
    return {'v': 1, 'kind': 'ta-lines', 'asOf': iso(FIXED), 'timeframes': {'1h': t1h, '4h': t4h, '1d': t1d}}

FIXTURE = {'body': fixture('fresh')}
IV = {'1h': 3600 * 1000, '4h': 4 * 3600 * 1000, '1d': 24 * 3600 * 1000}

def sloped_edge(sl, last_ms, tfname):
    a_ms = int(dt.datetime.strptime(sl['anchor']['t'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
    return sl['anchor']['price'] + sl['slope'] * ((last_ms - a_ms) / IV[tfname])

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
        if FIXTURE['body'] is None:
            return route.fulfill(status=404, content_type='application/json', body='{}')
        return route.fulfill(status=200, content_type='application/json', body=json.dumps(FIXTURE['body']))
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

def inked(pg, sel='#bcC'):
    return pg.evaluate("""(s) => { const c = document.querySelector(s); if (!c || !c.width || !c.height) return false;
      const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let ink = 0;
      for (let i = 0; i < d.length; i += 16) { if (d[i+3] > 0) ink++; }
      return ink > 50; }""", sel)

def colour_present(pg, rgb, sel='#bcC'):
    """True if an (R,G,B) appears on the canvas (+/-40 per channel)."""
    return pg.evaluate("""([s, rgb]) => { const c = document.querySelector(s); if (!c) return false;
      const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
      for (let i = 0; i < d.length; i += 4) {
        if (Math.abs(d[i] - rgb[0]) <= 40 && Math.abs(d[i+1] - rgb[1]) <= 40 && Math.abs(d[i+2] - rgb[2]) <= 40) return true; }
      return false; }""", [sel, rgb])

def tl(pg):
    return pg.evaluate("window.__TA_TL_DEBUG ? window.__TA_TL_DEBUG() : null")

def wait_status(pg, want, timeout=10000):
    pg.wait_for_function("window.__TA_TL_DEBUG && window.__TA_TL_DEBUG().status === '%s'" % want, timeout=timeout)

def turn_tl_on(pg):
    pg.click('#taPill'); pg.wait_for_selector('.ta-panel:not([hidden])', timeout=5000)
    pg.click('.ta-panel [data-ta-key="tl"]'); pg.wait_for_timeout(400)

def panel_status(pg):
    if pg.evaluate("document.querySelector('.ta-panel').hidden"):
        pg.click('#taPill'); pg.wait_for_selector('.ta-panel:not([hidden])', timeout=5000)
    return pg.inner_text('.ta-panel .ta-tl-status')

def pick_size(pg, size):
    pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
    pg.click('.ta-menu [data-ta-size="%s"]' % size); pg.wait_for_timeout(1200)
def edges_ok(pg, body, chart_tf):
    """Every drawn sloped line's edgePrice matches the Python computation
    from the probe's lastMs (anchor + slope x candles since the anchor),
    using that line's own timeframe's interval. Only timeframes at or
    above the chart's (rule 5) are expected to draw."""
    RANK = {'1h': 0, '4h': 1, '1d': 2}
    pr = tl(pg)
    if not pr or not pr.get('last') or pr.get('lastMs') is None:
        return False
    last_ms = pr['lastMs']
    drawn = [l for l in pr['last']['lines'] if l['type'] == 'sloped']
    want = {}
    for tfname, tfd in body['timeframes'].items():
        if RANK[tfname] < RANK[chart_tf]:
            continue
        for sl in tfd['sloped']:
            want[(tfname, sl['kind'], sl['slope'])] = sloped_edge(sl, last_ms, tfname)
    if len(drawn) != len(want):
        return False
    for ln in drawn:
        exp = want.get((ln['tf'], ln['kind'], ln['slope']))
        if exp is None or abs(ln['edgePrice'] - exp) > 1e-6 * max(1, abs(exp)):
            return False
    return True

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
    shots = Path(sys.argv[2]) if len(sys.argv) > 2 else R / 'handback' / 'ta'
    shots.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright
    overlap = {}
    with sync_playwright() as p:
        launch = {'executable_path': CHROME} if CHROME else {}
        b = p.chromium.launch(**launch)
        # ---- Phase A: fresh fixture, clock 390 dark ----
        FIXTURE['body'] = fixture('fresh')
        ctx = b.new_context(viewport={'width': 390, 'height': 900}, reduced_motion='reduce'); ctx.route('**/*', handler)
        # Seed Trends on, so the 1D Line checks below see the lines draw
        # (Job 1 ungreyed the toggle there; it is no longer gated).
        ctx.add_init_script("localStorage.setItem('ps-ta-v1', JSON.stringify({tl:true}));")
        pg = ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
        pg.clock.set_fixed_time(FIXED)
        try:
            pg.goto(U + 'clock/index.html', wait_until='networkidle')
            pg.wait_for_selector('#bcC', timeout=8000); pg.wait_for_timeout(1500)
            chk('A clock 390 dark: chart paints', inked(pg))
            chk('A clock 390 dark: TA module + TL probe loaded', pg.evaluate("!!window.__BTTA && !!window.__BCTA && !!window.__TA_TL_DEBUG"))
            # Job 1: on 1D Line the Trends switch is ENABLED and the lines
            # draw (the y-range expands to include them); the same toggle
            # works on 1D 1H candles below.
            pg.click('#taPill'); pg.wait_for_selector('.ta-panel:not([hidden])', timeout=5000)
            chk('A 1D Line: Trends toggle enabled (Job 1)', not pg.is_disabled('.ta-panel [data-ta-key="tl"]'))
            wait_status(pg, 'live')
            pr = tl(pg)
            chk('A 1D Line: status live, 12 lines draw (Job 1)', pr['tf'] == '1h' and pr['status'] == 'live' and len(pr['last']['lines']) == 12, str(pr))
            chk('A 1D Line: panel says Live 1h + 4h + 1d 12 lines (Job 1)', panel_status(pg) == 'Live · 1h + 4h + 1d · 12 lines', panel_status(pg))
            pg.keyboard.press('Escape'); pg.wait_for_timeout(400)
            pick_size(pg, '1h'); wait_status(pg, 'live')
            pr = tl(pg)
            chk('A 1D line: tf is 1h', pr['tf'] == '1h', pr['tf'])
            chk('A 1D line: status live, file ok', pr['status'] == 'live' and pr['fileOk'])
            chk('A 1D line: live close in stubbed range', 76250 <= pr['liveClose'] <= 78750, pr['liveClose'])
            chk('A 1D line: 12 lines draw (1h 6 + 4h 3 + 1d 3), 0 omitted', len(pr['last']['lines']) == 12 and len(pr['last']['omitted']) == 0, str(pr['last']))
            chk('A 1D line: tf breakdown is 1h 6 / 4h 3 / 1d 3', len([l for l in pr['last']['lines'] if l['tf'] == '1h']) == 6 and len([l for l in pr['last']['lines'] if l['tf'] == '4h']) == 3 and len([l for l in pr['last']['lines'] if l['tf'] == '1d']) == 3, str(pr['last']))
            chk('A 1D line: higher-tf lines are labelled (4h $79,500 / 1d $81,000)', any(l.get('label') == '4h $79,500' for l in pr['last']['lines']) and any(l.get('label') == '1d $81,000' for l in pr['last']['lines']))
            chk('A 1D line: EXT labelled "range low $74,800"', any(l.get('label') == 'range low $74,800' and l.get('extreme') for l in pr['last']['lines']))
            chk('A 1D line: broken:true 79000 draws as resistance', any(l.get('price') == 79000 and l.get('broken') and l.get('kind') == 'resistance' for l in pr['last']['lines']))
            chk('A 1D line: sloped edges match anchor math (own-tf intervals)', edges_ok(pg, FIXTURE['body'], '1h'))
            chk('A 1D line: support green pixels painted', colour_present(pg, (34, 197, 94)))
            chk('A 1D line: resistance red pixels painted', colour_present(pg, (239, 68, 68)))
            chk('A 1D line: panel says Live 1h + 4h + 1d 12 lines', panel_status(pg) == 'Live · 1h + 4h + 1d · 12 lines', panel_status(pg))
            r = pg.evaluate("window.__taRects()")
            overlap['clock-390-dark-ta-lines-panel'] = r
            chk('A 1D line: overlap 0 with panel open', r['overlaps'] == [], r['overlaps'])
            pg.keyboard.press('Escape'); pg.wait_for_timeout(400)
            pg.screenshot(path=str(shots / 'clock-390-dark-ta-lines.png'), animations='disabled')
            # 1D 4H candles: 4h + 1d lines, missingSupport does not hide sloped
            pick_size(pg, '4h'); pg.wait_for_timeout(600)
            pr = tl(pg)
            chk('A 1D 4H: tf is 4h, live', pr['tf'] == '4h' and pr['status'] == 'live', pr['tf'])
            chk('A 1D 4H: 6 lines draw (4h 3 + 1d 3), 0 omitted, no 1h', len(pr['last']['lines']) == 6 and len(pr['last']['omitted']) == 0 and all(l['tf'] != '1h' for l in pr['last']['lines']), str(pr['last']))
            chk('A 1D 4H: sloped supports draw despite missingSupport (4h 2 + 1d 1)', len([l for l in pr['last']['lines'] if l['type'] == 'sloped' and l['kind'] == 'support']) == 3)
            chk('A 1D 4H: 1d sloped line is labelled 1d', any(l.get('label', '').startswith('1d ') and l['type'] == 'sloped' for l in pr['last']['lines']))
            chk('A 1D 4H: sloped edges match anchor math', edges_ok(pg, FIXTURE['body'], '4h'))
            # 1W daily candles: 1d lines, anchor before the window still draws
            pg.click('#bcRgs button[data-r="1W"]'); pg.wait_for_timeout(900)
            pick_size(pg, 'daily'); pg.wait_for_timeout(600)
            pr = tl(pg)
            chk('A 1W daily: tf is 1d, live', pr['tf'] == '1d' and pr['status'] == 'live', pr['tf'])
            chk('A 1W daily: 3 lines draw (2 levels + 1 sloped)', len(pr['last']['lines']) == 3 and len(pr['last']['omitted']) == 0, str(pr['last']))
            chk('A 1W daily: sloped edge matches anchor math', edges_ok(pg, FIXTURE['body'], '1d'))
            chk('A 1W daily: all drawn lines are 1d (no foreign tf leaks)', all(l.get('tf') == '1d' for l in pr['last']['lines']))
            # 5Y: unavailable
            pg.click('#bcRgs button[data-r="5Y"]'); pg.wait_for_timeout(900)
            pr = tl(pg)
            chk('A 5Y: tf null, status unavailable, no lines', pr['tf'] is None and pr['status'] == 'unavailable' and pr['last']['lines'] == [], str(pr))
            chk('A 5Y: panel says Not available on this range', panel_status(pg) == 'Not available on this range', panel_status(pg))
            pg.click('#bcRgs button[data-r="1D"]'); pg.wait_for_timeout(1200)
            pg.click('#taTyp'); pg.wait_for_selector('.ta-menu:not([hidden])', timeout=5000)
            pg.click('.ta-menu [data-ta-pick="line"]'); pg.wait_for_timeout(1200)
            wait_status(pg, 'live')
            pr = tl(pg)
            chk('A back to 1D Line: live, 12 lines (Job 1)', pr['tf'] == '1h' and pr['status'] == 'live' and len(pr['last']['lines']) == 12, str(pr))
            chk('A back to 1D Line: panel says Live 1h + 4h + 1d 12 lines (Job 1)', panel_status(pg) == 'Live · 1h + 4h + 1d · 12 lines', panel_status(pg))
            pg.keyboard.press('Escape'); pg.wait_for_timeout(400)
            pick_size(pg, '1h'); wait_status(pg, 'live')
            pr = tl(pg)
            chk('A back to 1D 1H: live again, 12 lines', pr['tf'] == '1h' and pr['status'] == 'live' and len(pr['last']['lines']) == 12, str(pr))
            chk('A clock 390 dark: no console errors', not errs, '; '.join(errs[:3]))
        except Exception as e:
            chk('A clock 390 dark', False, str(e)[:200])
        ctx.close()
        # ---- Phase B: stale 1h (fresh 4h + 1d) ----
        FIXTURE['body'] = fixture('stale')
        ctx = b.new_context(viewport={'width': 390, 'height': 900}, reduced_motion='reduce'); ctx.route('**/*', handler)
        pg = ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
        pg.clock.set_fixed_time(FIXED)
        try:
            pg.goto(U + 'clock/index.html', wait_until='networkidle')
            pg.wait_for_selector('#bcC', timeout=8000); pg.wait_for_timeout(1500)
            pick_size(pg, '1h'); turn_tl_on(pg); wait_status(pg, 'live')
            pr = tl(pg)
            chk('B stale 1h: status live (4h + 1d still draw), 6 lines, 1h stale', pr['status'] == 'live' and len(pr['last']['lines']) == 6 and pr['last'].get('stale') and pr['last']['perTf'].get('1h') == 'stale', str(pr))
            chk('B stale 1h: no 1h lines draw, only 4h + 1d', all(l['tf'] != '1h' for l in pr['last']['lines']) and len([l for l in pr['last']['lines'] if l['tf'] == '4h']) == 3 and len([l for l in pr['last']['lines'] if l['tf'] == '1d']) == 3, str(pr['last']))
            chk('B stale 1h: panel says Live 4h + 1d 6 lines', panel_status(pg) == 'Live · 4h + 1d · 6 lines', panel_status(pg))
            pick_size(pg, '4h'); pg.wait_for_timeout(600)
            pr = tl(pg)
            chk('B stale 1h, fresh 4h: 4h still live (stale is per timeframe)', pr['tf'] == '4h' and pr['status'] == 'live' and len(pr['last']['lines']) == 6, str(pr))
            chk('B stale: no console errors', not errs, '; '.join(errs[:3]))
        except Exception as e:
            chk('B stale', False, str(e)[:200])
        ctx.close()
        # ---- Phase B2: every timeframe stale ----
        FIXTURE['body'] = fixture('stale_all')
        ctx = b.new_context(viewport={'width': 390, 'height': 900}, reduced_motion='reduce'); ctx.route('**/*', handler)
        pg = ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
        pg.clock.set_fixed_time(FIXED)
        try:
            pg.goto(U + 'clock/index.html', wait_until='networkidle')
            pg.wait_for_selector('#bcC', timeout=8000); pg.wait_for_timeout(1500)
            pick_size(pg, '1h'); turn_tl_on(pg); wait_status(pg, 'updating')
            pr = tl(pg)
            chk('B2 all stale: status updating, no lines', pr['status'] == 'updating' and pr['last']['lines'] == [] and pr['last'].get('stale'), str(pr))
            chk('B2 all stale: panel says Trendlines updating…', panel_status(pg) == 'Trendlines updating…', panel_status(pg))
            chk('B2 all stale: no console errors', not errs, '; '.join(errs[:3]))
        except Exception as e:
            chk('B2 all stale', False, str(e)[:200])
        ctx.close()
        # ---- Phase C: missing file ----
        FIXTURE['body'] = fixture('missing')
        ctx = b.new_context(viewport={'width': 390, 'height': 900}, reduced_motion='reduce'); ctx.route('**/*', handler)
        pg = ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
        pg.clock.set_fixed_time(FIXED)
        try:
            pg.goto(U + 'clock/index.html', wait_until='networkidle')
            pg.wait_for_selector('#bcC', timeout=8000); pg.wait_for_timeout(1500)
            pick_size(pg, '1h'); turn_tl_on(pg); wait_status(pg, 'updating')
            pr = tl(pg)
            chk('C missing file: status updating, no lines', pr['status'] == 'updating' and pr['last']['lines'] == [] and not pr['fileOk'], str(pr))
            chk('C missing file: panel says Trendlines updating…', panel_status(pg) == 'Trendlines updating…', panel_status(pg))
            chk('C missing file: no console errors', not errs, '; '.join(errs[:3]))
        except Exception as e:
            chk('C missing file', False, str(e)[:200])
        ctx.close()
        # ---- Phase D: invalid file ----
        FIXTURE['body'] = fixture('invalid')
        ctx = b.new_context(viewport={'width': 390, 'height': 900}, reduced_motion='reduce'); ctx.route('**/*', handler)
        pg = ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
        pg.clock.set_fixed_time(FIXED)
        try:
            pg.goto(U + 'clock/index.html', wait_until='networkidle')
            pg.wait_for_selector('#bcC', timeout=8000); pg.wait_for_timeout(1500)
            pick_size(pg, '1h'); turn_tl_on(pg); wait_status(pg, 'updating')
            pr = tl(pg)
            chk('D invalid file: status updating, no lines, bad schema', pr['status'] == 'updating' and pr['last']['lines'] == [] and pr['fileReason'] == 'bad schema', str(pr))
            chk('D invalid file: no console errors', not errs, '; '.join(errs[:3]))
        except Exception as e:
            chk('D invalid file', False, str(e)[:200])
        ctx.close()
        # ---- Phase E: crossed lines ----
        FIXTURE['body'] = fixture('crossed')
        ctx = b.new_context(viewport={'width': 390, 'height': 900}, reduced_motion='reduce'); ctx.route('**/*', handler)
        pg = ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
        pg.clock.set_fixed_time(FIXED)
        try:
            pg.goto(U + 'clock/index.html', wait_until='networkidle')
            pg.wait_for_selector('#bcC', timeout=8000); pg.wait_for_timeout(1500)
            pick_size(pg, '1h'); turn_tl_on(pg); wait_status(pg, 'live')
            pr = tl(pg)
            drawn_levels = {(l['kind'], l['price']) for l in pr['last']['lines'] if l['type'] == 'level'}
            chk('E crossed 1D line: 9 draw (1h 4 + 4h 2 + 1d 3), 3 omitted', len(pr['last']['lines']) == 9 and len(pr['last']['omitted']) == 3, str(pr['last']))
            chk('E crossed 1h: crossed resistance 76000 omitted', any(l.get('price') == 76000 and l.get('kind') == 'resistance' and l.get('omit') == 'resistance below live price' for l in pr['last']['omitted']))
            chk('E crossed 1h: crossed sloped support omitted', any(l['type'] == 'sloped' and l['kind'] == 'support' and l.get('omit') == 'support above live price' for l in pr['last']['omitted']))
            chk('E crossed 4h: crossed support 79000 omitted', any(l.get('price') == 79000 and l.get('kind') == 'support' and l.get('omit') == 'support above live price' for l in pr['last']['omitted']))
            chk('E crossed 1h: good lines still draw', ('resistance', 79500) in drawn_levels and ('support', 75800) in drawn_levels)
            chk('E crossed 1h: EXT resistance labelled "range high $81,000"', any(l.get('label') == 'range high $81,000' and l.get('extreme') for l in pr['last']['lines']))
            pick_size(pg, '4h'); pg.wait_for_timeout(600)
            pr = tl(pg)
            chk('E crossed 4h: 5 draw (4h 2 + 1d 3), 1 omitted', len(pr['last']['lines']) == 5 and len(pr['last']['omitted']) == 1, str(pr['last']))
            chk('E crossed 4h: crossed support 79000 omitted', any(l.get('price') == 79000 and l.get('omit') == 'support above live price' for l in pr['last']['omitted']))
            chk('E crossed: no console errors', not errs, '; '.join(errs[:3]))
        except Exception as e:
            chk('E crossed', False, str(e)[:200])
        ctx.close()
        # ---- Phase F: desktop 1440 light ----
        FIXTURE['body'] = fixture('fresh')
        ctx = b.new_context(viewport={'width': 1440, 'height': 900}, reduced_motion='reduce', color_scheme='light'); ctx.route('**/*', handler)
        pg = ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
        pg.clock.set_fixed_time(FIXED)
        try:
            pg.goto(U + 'clock/index.html', wait_until='networkidle')
            pg.evaluate("document.documentElement.setAttribute('data-theme','light')")
            pg.wait_for_selector('#bcC', timeout=8000); pg.wait_for_timeout(1500)
            chk('F clock 1440 light: chart paints', inked(pg))
            pick_size(pg, '1h'); turn_tl_on(pg); wait_status(pg, 'live')
            pr = tl(pg)
            chk('F clock 1440 light: 12 lines draw', len(pr['last']['lines']) == 12, str(pr['last']))
            chk('F clock 1440 light: panel says Live 1h + 4h + 1d 12 lines', panel_status(pg) == 'Live · 1h + 4h + 1d · 12 lines', panel_status(pg))
            r = pg.evaluate("window.__taRects()")
            overlap['clock-1440-light-ta-lines-panel'] = r
            chk('F clock 1440 light: overlap 0 with panel open', r['overlaps'] == [], r['overlaps'])
            pg.keyboard.press('Escape'); pg.wait_for_timeout(400)
            pg.screenshot(path=str(shots / 'clock-1440-light-ta-lines.png'), animations='disabled')
            chk('F clock 1440 light: no console errors', not errs, '; '.join(errs[:3]))
        except Exception as e:
            chk('F clock 1440 light', False, str(e)[:200])
        ctx.close()
        # ---- Phase G: popover on the homepage, phone 390 dark ----
        ctx = b.new_context(viewport={'width': 390, 'height': 900}, reduced_motion='reduce'); ctx.route('**/*', handler)
        pg = ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
        pg.clock.set_fixed_time(FIXED)
        try:
            pg.goto(U + 'index.html', wait_until='networkidle')
            pg.evaluate("document.getElementById('hdrTick').click()"); pg.wait_for_selector('#bcC', timeout=8000); pg.wait_for_timeout(1500)
            chk('G popover 390 dark: chart paints', inked(pg))
            pick_size(pg, '1h'); turn_tl_on(pg); wait_status(pg, 'live')
            pr = tl(pg)
            chk('G popover 390 dark: 12 lines draw', len(pr['last']['lines']) == 12 and pr['tf'] == '1h', str(pr['last']))
            pg.keyboard.press('Escape'); pg.wait_for_timeout(400)
            pg.screenshot(path=str(shots / 'popover-390-dark-ta-lines.png'), animations='disabled')
            chk('G popover 390 dark: no console errors', not errs, '; '.join(errs[:3]))
        except Exception as e:
            chk('G popover 390 dark', False, str(e)[:200])
        ctx.close()
        b.close()
    (shots / 'overlap-check.json').write_text(json.dumps(overlap, indent=1))
    print('TA STAGE 4:', 'PASS (%d checks)' % n if not fails else 'FAIL (%d/%d)' % (len(fails), n))
    sys.exit(1 if fails else 0)

if __name__ == '__main__':
    main()
