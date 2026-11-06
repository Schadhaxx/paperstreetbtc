#!/usr/bin/env python3
"""Stale-HTML guard for psC.

Simulates a visitor whose browser still has an OLDER cached HTML page (no theme
head script, no chart-theme.js) but receives the NEW JS files: HTML documents are
served from OLD_HTML_DIR (e.g. a main checkout), every other file from SITE_DIR,
and chart-theme.js is aborted. At 390px in dark mode it opens the BTC chart,
switches to 1H candles, taps a candle and requires the candle pill to appear,
with no page/console errors. Coinbase is stubbed with deterministic candles.

usage: python3 tests/stale_html_psC.py SITE_DIR OLD_HTML_DIR
"""
import os, sys, json, math, threading, functools, http.server, socketserver, urllib.parse, datetime as dt
from playwright.sync_api import sync_playwright

PAGES = ['index.html', 'screener.html', 'compare/index.html', 'custom/index.html', 'recap/index.html', 'recap/2026-10/index.html', 'recap/2026-01/index.html']
exe = next((p for p in ['/usr/bin/google-chrome', '/usr/bin/chromium'] if os.path.exists(p)), None)
site, old = sys.argv[1], sys.argv[2]


class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass


srv = socketserver.ThreadingTCPServer(('127.0.0.1', 0), functools.partial(Q, directory=site)); srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
U = 'http://127.0.0.1:%d/' % srv.server_address[1]


def coinbase(route):
    u = urllib.parse.urlparse(route.request.url); q = urllib.parse.parse_qs(u.query)
    if 'spot' in u.path:
        return route.fulfill(status=200, content_type='application/json', body=json.dumps({'data': {'amount': '77500.00', 'currency': 'USD'}}))
    g = int(q.get('granularity', ['86400'])[0]); end = int(dt.datetime(2026, 10, 30, 20, tzinfo=dt.timezone.utc).timestamp())
    rows, t = [], end - end % g
    while len(rows) < 300:
        o = 77500 + 900 * math.sin(t / g / 5.0); c = o + 350 * math.cos(t / g / 3.0)
        rows.append([t, min(o, c) - 120, max(o, c) + 120, o, c, 10]); t -= g
    route.fulfill(status=200, content_type='application/json', body=json.dumps(rows))


def handler(route):
    url = route.request.url
    if 'coinbase.com' in url: return coinbase(route)
    if not url.startswith(U): return route.abort()
    path = urllib.parse.urlparse(url).path.lstrip('/')
    if 'chart-theme.js' in path: return route.abort()
    if path == '' or path.endswith('/'): path += 'index.html'
    if path.endswith('.html') and os.path.exists(os.path.join(old, path)):
        return route.fulfill(status=200, content_type='text/html; charset=utf-8', body=open(os.path.join(old, path), 'rb').read())
    route.continue_()


fails = 0
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
    for pgname in PAGES:
        ctx = b.new_context(viewport={'width': 390, 'height': 900}, reduced_motion='reduce'); ctx.route('**/*', handler)
        pg = ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text and 'ERR_FAILED' not in m.text else None)
        pg.clock.set_fixed_time('2026-10-30T20:00:00Z')
        ok, why = True, ''
        try:
            pg.goto(U + pgname, wait_until='networkidle')
            stale = pg.evaluate('!document.querySelector("script[src*=chart-theme]") && document.documentElement.getAttribute("data-theme")===null')
            if not stale: raise Exception('page is not the stale HTML')
            pg.evaluate('document.getElementById("hdrTick").click()'); pg.wait_for_selector('#bcC', timeout=8000); pg.wait_for_timeout(1200)
            pg.click('#bcCt button[data-ct="1h"]'); pg.wait_for_timeout(1200)
            bx = pg.locator('#bcC').bounding_box(); pg.mouse.click(bx['x'] + bx['width'] * 0.7, bx['y'] + bx['height'] * 0.5); pg.wait_for_timeout(500)
            if not pg.locator('#bcSel').is_visible(): raise Exception('candle pill not shown')
        except Exception as e:
            ok, why = False, str(e).splitlines()[0][:160]
        if errs: ok, why = False, (why + ' | ' if why else '') + '; '.join(errs[:2])[:200]
        fails += not ok
        print(('PASS' if ok else 'FAIL'), pgname, why, flush=True)
        ctx.close()
    b.close()
print('stale html psC:', 'PASS' if not fails else 'FAIL (%d)' % fails)
sys.exit(1 if fails else 0)
